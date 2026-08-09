"""
Ham çeviri yedeği (.ham.srt) + Geri Çeviri Anlam Kontrolü (rapor-only).

- _save_raw_backup: toggle açıkken <stem>.ham.srt yazar, kapalıyken yazmaz.
- back_translation_check: prefilter ([HATA]/çok kısa/etiket-only) hepsini elerse
  API'ye GİTMEDEN [] döner (ağ gerektirmeyen yol).
"""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import subtitle_translator_gui as gui
import hybrid_translate as ht

_TS = "00:00:01,000 --> 00:00:02,000"


class RawBackupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = SimpleNamespace(
            backup_raw_var=SimpleNamespace(get=lambda: True, set=lambda _v: None),
            _log=lambda *_args, **_kwargs: None,
        )

    @classmethod
    def tearDownClass(cls):
        pass

    def test_writes_ham_srt_when_on(self):
        d = tempfile.mkdtemp()
        out = os.path.join(d, "movie.srt")
        self.app.backup_raw_var = SimpleNamespace(get=lambda: True)
        gui.App._save_raw_backup(
            self.app, out, [("1", _TS, "Merhaba")], {"1": "Hello"})
        self.assertEqual(len(list(Path(d, "Raporlar", "Ham").glob("movie.*.ham.srt"))), 1)

    def test_partial_path_still_uses_single_top_level_report_tree(self):
        d = Path(tempfile.mkdtemp())
        partial = d / "Raporlar" / "Kurtarma" / "movie.partial.srt"
        self.app.backup_raw_var = SimpleNamespace(get=lambda: True)
        gui.App._save_raw_backup(
            self.app, partial, [("1", _TS, "Merhaba")], {"1": "Hello"})

        self.assertEqual(
            len(list((d / "Raporlar" / "Ham").glob("movie.*.ham.srt"))), 1)
        self.assertFalse((partial.parent / "Raporlar").exists())

    def test_skips_when_off(self):
        d = tempfile.mkdtemp()
        out = os.path.join(d, "movie.srt")
        self.app.backup_raw_var = SimpleNamespace(get=lambda: False)
        try:
            gui.App._save_raw_backup(
                self.app, out, [("1", _TS, "x")], {"1": "y"})
            self.assertFalse(list(Path(d, "Raporlar", "Ham").glob("movie.*.ham.srt")))
        finally:
            self.app.backup_raw_var = SimpleNamespace(get=lambda: True)

    def test_backup_unaffected_by_later_pass_mutation(self):
        # Ham snapshot (list kopyası) sonradan pass'ler listeyi değiştirse de korunur
        d = tempfile.mkdtemp()
        out = os.path.join(d, "m.srt")
        raw = [("1", _TS, "ham metin")]
        snapshot = list(raw)            # akışlardaki _raw_backup_blocks ile aynı desen
        raw[0] = ("1", _TS, "DEĞİŞTİ")  # bir pass yeniden atadı
        self.app.backup_raw_var = SimpleNamespace(get=lambda: True)
        gui.App._save_raw_backup(self.app, out, snapshot, {"1": "raw text"})
        backup = next(Path(d, "Raporlar", "Ham").glob("m.*.ham.srt"))
        with open(backup, encoding="utf-8") as fh:
            self.assertIn("ham metin", fh.read())


class BackTranslationPrefilterTest(unittest.TestCase):
    def test_empty_src_map_returns_empty(self):
        self.assertEqual(ht.back_translation_check({}, [("1", _TS, "Merhaba dünya")], api_key="x"), [])

    def test_all_filtered_no_network(self):
        # [HATA] + çok kısa (<12 öz karakter) + bracket-only → hepsi elenir → ağsız []
        blocks = [("1", _TS, "[HATA]"), ("2", _TS, "Tamam"), ("3", _TS, "[KAHKAHA]")]
        src = {"1": "whatever", "2": "Okay", "3": "[LAUGHS]"}
        self.assertEqual(ht.back_translation_check(src, blocks, api_key="x"), [])

    def test_total_stage_failure_is_reported(self):
        blocks = [("1", _TS, "Bu yeterince uzun bir çeviri satırıdır.")]
        src = {"1": "This is a sufficiently long source subtitle line."}
        status = {}

        with patch("openai.OpenAI"), patch(
                "hybrid_translate._safe_chat_create",
                side_effect=RuntimeError("provider unavailable")):
            result = ht.back_translation_check(
                src, blocks, api_key="x", status_out=status)

        self.assertEqual(result, [])
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["successful_chunks"], 0)
        self.assertEqual(status["failed_chunks"], 1)

    def test_two_stage_success_is_reported_completed(self):
        blocks = [("1", _TS, "Bu yeterince uzun bir çeviri satırıdır.")]
        src = {"1": "This is a sufficiently long source subtitle line."}
        responses = [
            SimpleNamespace(
                usage=None,
                choices=[SimpleNamespace(message=SimpleNamespace(
                    content='[{"id":"1","en":"A long translated line."}]'))],
            ),
            SimpleNamespace(
                usage=None,
                choices=[SimpleNamespace(message=SimpleNamespace(content="[]"))],
            ),
        ]
        status = {}

        with patch("openai.OpenAI"), patch(
                "hybrid_translate._safe_chat_create", side_effect=responses):
            result = ht.back_translation_check(
                src, blocks, api_key="x", status_out=status)

        self.assertEqual(result, [])
        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["successful_chunks"], 1)
        self.assertEqual(status["failed_chunks"], 0)

    def test_stage_one_maps_reordered_response_by_id(self):
        blocks = [
            ("1", _TS, "Birinci yeterince uzun çeviri satırıdır."),
            ("2", _TS, "İkinci yeterince uzun çeviri satırıdır."),
        ]
        src = {"1": "First source line.", "2": "Second source line."}
        prompts = []

        def respond(_client, **kwargs):
            prompts.append(kwargs["messages"][0]["content"])
            if len(prompts) == 1:
                return SimpleNamespace(
                    usage=None,
                    choices=[SimpleNamespace(message=SimpleNamespace(content=(
                        '[{"id":"2","en":"Second back translation."},'
                        '{"id":"1","en":"First back translation."}]')))],
                )
            return SimpleNamespace(
                usage=None,
                choices=[SimpleNamespace(message=SimpleNamespace(content="[]"))],
            )

        with patch("openai.OpenAI"), patch(
                "hybrid_translate._safe_chat_create", side_effect=respond):
            ht.back_translation_check(src, blocks, api_key="x")

        self.assertIn('"id": "1", "src": "First source line.", "back": "First back translation."', prompts[1])
        self.assertIn('"id": "2", "src": "Second source line.", "back": "Second back translation."', prompts[1])

    def test_stage_one_retries_only_missing_ids_after_duplicate_response(self):
        blocks = [
            ("1", _TS, "Birinci yeterince uzun çeviri satırıdır."),
            ("2", _TS, "İkinci yeterince uzun çeviri satırıdır."),
        ]
        src = {"1": "First source line.", "2": "Second source line."}
        prompts = []
        status = {}

        def respond(_client, **kwargs):
            prompts.append(kwargs["messages"][0]["content"])
            if len(prompts) == 1:
                return SimpleNamespace(
                    usage=None,
                    choices=[SimpleNamespace(message=SimpleNamespace(content=(
                        '[{"id":"1","en":"First candidate."},'
                        '{"id":"1","en":"Wrong duplicate."}]')))],
                )
            if len(prompts) == 2:
                return SimpleNamespace(
                    usage=None,
                    choices=[SimpleNamespace(message=SimpleNamespace(content=(
                        '[{"id":"1","en":"First back translation."},'
                        '{"id":"2","en":"Second back translation."}]')))],
                )
            return SimpleNamespace(usage=None, choices=[SimpleNamespace(
                message=SimpleNamespace(content="[]"))])

        with patch("openai.OpenAI"), patch(
                "hybrid_translate._safe_chat_create", side_effect=respond):
            ht.back_translation_check(
                src, blocks, api_key="x", status_out=status)

        self.assertEqual(len(prompts), 3)
        self.assertEqual(status["status"], "completed")
        self.assertIn('"id": "1"', prompts[1])
        self.assertIn('"id": "2"', prompts[1])

    def test_persistent_missing_stage_one_ids_are_reported_as_partial(self):
        blocks = [
            ("1", _TS, "Birinci yeterince uzun çeviri satırıdır."),
            ("2", _TS, "İkinci yeterince uzun çeviri satırıdır."),
        ]
        src = {"1": "First source line.", "2": "Second source line."}
        responses = [
            SimpleNamespace(usage=None, choices=[SimpleNamespace(
                message=SimpleNamespace(content=(
                    '[{"id":"1","en":"First back translation."}]')))]),
            SimpleNamespace(usage=None, choices=[SimpleNamespace(
                message=SimpleNamespace(content="[]"))]),
            SimpleNamespace(usage=None, choices=[SimpleNamespace(
                message=SimpleNamespace(content="[]"))]),
            SimpleNamespace(usage=None, choices=[SimpleNamespace(
                message=SimpleNamespace(content="[]"))]),
            SimpleNamespace(usage=None, choices=[SimpleNamespace(
                message=SimpleNamespace(content="[]"))]),
        ]
        status = {}
        logs = []

        with patch("openai.OpenAI"), patch(
                "hybrid_translate._safe_chat_create", side_effect=responses):
            ht.back_translation_check(
                src, blocks, api_key="x", status_out=status,
                log_fn=lambda message, level: logs.append((message, level)))

        self.assertEqual(status["status"], "partial")
        self.assertEqual(status["successful_chunks"], 1)
        self.assertEqual(status["failed_chunks"], 0)
        self.assertEqual(status["partial_chunks"], 1)
        self.assertEqual(status["missing_items"], 1)
        self.assertTrue(any("1 pakette 1 cue" in message for message, _ in logs))

    def test_empty_stage_one_after_repairs_counts_missing_items(self):
        blocks = [("1", _TS, "Yeterince uzun bir çeviri satırıdır.")]
        src = {"1": "A sufficiently long source subtitle line."}
        empty = SimpleNamespace(usage=None, choices=[SimpleNamespace(
            message=SimpleNamespace(content="[]"))])
        status = {}

        with patch("openai.OpenAI"), patch(
                "hybrid_translate._safe_chat_create",
                side_effect=[empty, empty, empty, empty]):
            ht.back_translation_check(
                src, blocks, api_key="x", status_out=status)

        self.assertEqual(status["status"], "partial")
        self.assertEqual(status["successful_chunks"], 0)
        self.assertEqual(status["failed_chunks"], 1)
        self.assertEqual(status["partial_chunks"], 1)
        self.assertEqual(status["missing_items"], 1)

    def test_stage_two_malformed_json_retries_only_comparison(self):
        blocks = [("1", _TS, "Bu yeterince uzun bir çeviri satırıdır.")]
        src = {"1": "This is a sufficiently long source subtitle line."}
        responses = [
            SimpleNamespace(usage=None, choices=[SimpleNamespace(
                message=SimpleNamespace(content=(
                    '[{"id":"1","en":"A sufficiently long source line."}]')))]),
            SimpleNamespace(usage=None, choices=[SimpleNamespace(
                message=SimpleNamespace(content="not json"))]),
            SimpleNamespace(usage=None, choices=[SimpleNamespace(
                message=SimpleNamespace(content="[]"))]),
        ]
        status = {}

        with patch("openai.OpenAI"), patch(
                "hybrid_translate._safe_chat_create", side_effect=responses) as call:
            result = ht.back_translation_check(
                src, blocks, api_key="x", status_out=status)

        self.assertEqual(result, [])
        self.assertEqual(status["status"], "completed")
        self.assertEqual(call.call_count, 3)
        self.assertEqual(
            call.call_args_list[1].kwargs["_checkpoint_label"],
            "backtranslation_compare",
        )
        self.assertEqual(
            call.call_args_list[2].kwargs["_checkpoint_label"],
            "backtranslation_compare",
        )


if __name__ == "__main__":
    unittest.main()
