"""Tests for deep-audit bugfixes: glossary, finish_reason, mojibake, atomic writes, polling, TM identity, VTT."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import hybrid_translate as ht
import subtitle_formats as sf
from app_state import STATE_DIR_ENV


class LoadGlossaryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        for f in self.tmp.rglob("*"):
            try:
                f.unlink()
            except Exception:
                pass
        self.tmp.rmdir()

    def _write_json(self, data, encoding="utf-8-sig"):
        p = self.tmp / "glossary.json"
        p.write_text(json.dumps(data, ensure_ascii=False), encoding=encoding)
        return str(p)

    def _write_txt(self, text, encoding="utf-8-sig"):
        p = self.tmp / "glossary.txt"
        p.write_text(text, encoding=encoding)
        return str(p)

    def test_normal_json_ok(self):
        fp = self._write_json({"merhaba": "hello"})
        self.assertEqual(ht.load_glossary(fp), {"merhaba": "hello"})

    def test_cp1254_json_ok(self):
        fp = self._write_json({"merhaba": "hello"}, encoding="cp1254")
        self.assertEqual(ht.load_glossary(fp), {"merhaba": "hello"})

    def test_broken_json_returns_empty(self):
        p = self.tmp / "glossary.json"
        p.write_text("not json at all", encoding="utf-8")
        self.assertEqual(ht.load_glossary(str(p)), {})

    def test_cp1254_txt_ok(self):
        fp = self._write_txt("merhaba\thello", encoding="cp1254")
        self.assertEqual(ht.load_glossary(fp), {"merhaba": "hello"})

    def test_nonexistent_file_returns_empty(self):
        self.assertEqual(ht.load_glossary("/nonexistent/glossary.json"), {})

    def test_empty_json_returns_empty(self):
        p = self.tmp / "glossary.json"
        p.write_text("", encoding="utf-8")
        self.assertEqual(ht.load_glossary(str(p)), {})


class FinishReasonGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.out = self.tmp / "_test_out.srt"

    def tearDown(self):
        for f in self.tmp.rglob("*"):
            try:
                f.unlink()
            except Exception:
                pass
        self.tmp.rmdir()

    def _make_body(self, content: str, finish_reason: str = "stop") -> dict:
        return {
            "choices": [{"finish_reason": finish_reason, "message": {"content": content}}],
            "usage": {"total_tokens": 10},
        }

    def _make_line(self, cid: str, body: dict) -> str:
        return json.dumps({
            "custom_id": cid,
            "response": {"body": body},
        })

    def _make_src_cue(self, idx, text="foo"):
        return SimpleNamespace(index=str(idx), text=text)

    def test_length_reason_triggers_hata(self):
        line = self._make_line("cid1", self._make_body("partial", finish_reason="length"))
        fake_fmap = {"cid1": [("0", "00:00:01,000", "00:00:04,000")]}
        fp = self.tmp / "output.srt"
        fake_client = MagicMock()
        fake_client.files.content.return_value.text = line
        logs = []
        src_cues = [self._make_src_cue(0)]
        with patch("openai.OpenAI", return_value=fake_client), patch("hybrid_translate.time.sleep"):
            written, marked = ht.save_results(
                "dummy_key", "fid", fake_fmap, str(fp),
                log_fn=lambda msg, lvl="": logs.append(msg),
                src_cues=src_cues,
            )
        self.assertGreater(marked, 0)
        self.assertTrue(any("kesildi" in m for m in logs))

    def test_content_filter_reason_triggers_hata(self):
        line = self._make_line("cid2", self._make_body("harmful", finish_reason="content_filter"))
        fake_fmap = {"cid2": [("1", "00:01", "00:02")]}
        fp = self.tmp / "output.srt"
        fake_client = MagicMock()
        fake_client.files.content.return_value.text = line
        logs = []
        src_cues = [self._make_src_cue(1)]
        with patch("openai.OpenAI", return_value=fake_client), patch("hybrid_translate.time.sleep"):
            written, marked = ht.save_results(
                "dummy_key", "fid", fake_fmap, str(fp),
                log_fn=lambda msg, lvl="": logs.append(msg),
                src_cues=src_cues,
            )
        self.assertGreater(marked, 0)
        self.assertTrue(any("kesildi" in m for m in logs))

    def test_stop_reason_not_flagged(self):
        line = self._make_line("cid3", self._make_body('{"ok":true}', finish_reason="stop"))
        fake_fmap = {"cid3": [("2", "00:02", "00:03")]}
        fp = self.tmp / "output.srt"
        fake_client = MagicMock()
        fake_client.files.content.return_value.text = line
        logs = []
        with patch("openai.OpenAI", return_value=fake_client):
            written, marked = ht.save_results(
                "dummy_key", "fid", fake_fmap, str(fp),
                log_fn=lambda msg, lvl="": logs.append(msg),
            )
        self.assertEqual(marked, 0)


class MojibakePromptTest(unittest.TestCase):
    def test_no_mojibake_in_sfx_examples(self):
        ctx = SimpleNamespace(
            tone="", summary="", setting="", characters=[], scene_notes=[], key_concepts="",
        )
        prompt = ht.build_system_prompt(ctx, "en", "tr", {"name": "Belgesel"})
        self.assertNotIn("â†", prompt)
        self.assertNotIn("Ã‡", prompt)
        self.assertIn("[SIGHS]→[İÇ ÇEKİŞ]", prompt)
        self.assertIn("[GASPS]→[NEFES KESİLİŞ]", prompt)
        self.assertIn("[GAGGING]→[ÖĞÜRME]", prompt)
        self.assertIn("[CRYING]→[AĞLAMA]", prompt)
        self.assertIn("[GROANS]→[İNLEME]", prompt)
        self.assertIn("[WHISPERING]→[FISILDAMA]", prompt)
        self.assertIn("KONUŞURUZ, DOSTUM", prompt)
        self.assertIn("'EXIT'→'ÇIKIŞ'", prompt)
        self.assertIn("'On my way'→'Yoldayım'", prompt)


class AtomicBatchWriteTest(unittest.TestCase):
    def setUp(self):
        self._state = tempfile.TemporaryDirectory()
        self._env = patch.dict(os.environ, {STATE_DIR_ENV: self._state.name})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._state.cleanup()

    def test_save_batch_session_atomic(self):
        session = {"version": 1, "input_dir": str(Path.cwd()), "files": {}}
        ht._save_batch_session(session)
        p = ht._session_path(str(Path.cwd()))
        self.assertTrue(p.exists())
        self.assertFalse(p.with_suffix(".tmp").exists(), ".tmp leftover")
        data = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], 1)

    def test_submit_batch_fmap_atomic(self):
        fake_client = MagicMock()
        fake_client.files.create.return_value.id = "file_abc"
        fake_client.batches.create.return_value.id = "batch_test_atomic"
        requests = [{"custom_id": "1", "body": {"messages": [{"role": "user", "content": "test"}]}}]
        file_map = {"1": [("0", "00:00:01", "00:00:04")]}
        # submit_batch gerçek proje köküne HEM batch_fmap_<id>.json HEM batch_id.txt yazar.
        # Test kirliliği: eskiden yalnız fmap temizleniyordu, batch_id.txt kalıp her uygulama
        # açılışında "Yarım Kalan Batch" hayalet dialog'unu tetikliyordu. Ayrıca kullanıcının
        # GERÇEK bekleyen batch'i varsa üzerine yazılmasın diye yedekle-geri-yükle.
        bid_path = ht._batch_id_path()
        _saved = bid_path.read_text(encoding="utf-8") if bid_path.exists() else None
        fmap_path = None
        try:
            with patch("openai.OpenAI", return_value=fake_client):
                bid = ht.submit_batch("dummy_key", requests, file_map=file_map)
            self.assertEqual(bid, "batch_test_atomic")
            fmap_path = ht._batch_fmap_path(bid)
            self.assertTrue(fmap_path.exists())
            self.assertFalse(fmap_path.with_suffix(".json.tmp").exists())
        finally:
            if fmap_path is not None:
                fmap_path.unlink(missing_ok=True)
            if _saved is not None:
                bid_path.write_text(_saved, encoding="utf-8")
            else:
                bid_path.unlink(missing_ok=True)


class WaitForBatchPollingTest(unittest.TestCase):
    def test_transient_error_then_success(self):
        fake_client = MagicMock()
        completed = MagicMock()
        completed.request_counts.total = 5
        completed.request_counts.completed = 5
        completed.request_counts.failed = 0
        completed.status = "completed"
        completed.output_file_id = "out_123"
        fake_client.batches.retrieve.side_effect = [Exception("geçici hata"), completed]
        logs = []
        with patch("openai.OpenAI", return_value=fake_client), patch("hybrid_translate.time.sleep"):
            result = ht.wait_for_batch(
                "dummy_key", "batch_test",
                log_fn=lambda msg, lvl="": logs.append(msg),
            )
        self.assertEqual(result, "out_123")
        self.assertTrue(any("geçici" in m for m in logs))

    def test_too_many_errors_returns_none(self):
        fake_client = MagicMock()
        fake_client.batches.retrieve.side_effect = Exception("kalıcı hata")
        logs = []
        with patch("openai.OpenAI", return_value=fake_client), patch("hybrid_translate.time.sleep"):
            result = ht.wait_for_batch(
                "dummy_key", "batch_test",
                log_fn=lambda msg, lvl="": logs.append(msg),
            )
        self.assertIsNone(result)

    def test_polling_abort_is_nonterminal_in_detailed_mode(self):
        fake_client = MagicMock()
        fake_client.batches.retrieve.side_effect = Exception("kalıcı hata")
        with patch("openai.OpenAI", return_value=fake_client) as factory, patch("hybrid_translate.time.sleep"):
            result = ht.wait_for_batch(
                "dummy_key", "batch_test", detailed=True,
                base_url="https://batch.example/v1")
        factory.assert_called_once_with(
            api_key="dummy_key", base_url="https://batch.example/v1")
        self.assertEqual(result["status"], "polling_aborted")
        self.assertFalse(result["terminal"])
        self.assertIsNone(result["output_file_id"])


class TMIdentityFilterTest(unittest.TestCase):
    def setUp(self):
        from translation_memory import TranslationMemory
        self.tm = TranslationMemory(":memory:")

    def test_identity_pair_rejected(self):
        self.assertFalse(self.tm.store("Merhaba", "Merhaba"))

    def test_identity_pair_case_insensitive_rejected(self):
        self.assertFalse(self.tm.store("merhaba", "MERHABA"))

    def test_normal_pair_stored(self):
        self.assertTrue(self.tm.store("hello", "merhaba"))
        result = self.tm.lookup("hello")
        self.assertIsNotNone(result)
        self.assertEqual(result, "merhaba")

    def test_identity_batch_rejected(self):
        pairs = [("hello", "merhaba"), ("goodbye", "goodbye"), ("cat", "cat")]
        self.tm.store_batch(pairs)
        self.assertIsNotNone(self.tm.lookup("hello"))
        self.assertIsNone(self.tm.lookup("goodbye"), "identity batch pair should be rejected")

    def test_hata_pair_skipped(self):
        self.assertFalse(self.tm.store("hello", "[HATA]"))
        self.assertFalse(self.tm.store("hello", "[ÇEVİRİ EKSİK]"))


class VTTTimestampRegexTest(unittest.TestCase):
    def test_normal_vtt_parses(self):
        with tempfile.TemporaryDirectory() as d:
            fp = Path(d) / "test.vtt"
            fp.write_text(
                "WEBVTT\n\n"
                "1\n"
                "00:00:01.000 --> 00:00:04.000\n"
                "Hello world\n\n"
                "2\n"
                "00:00:05.000 --> 00:00:08.000\n"
                "Second cue\n",
                encoding="utf-8",
            )
            blocks = sf.parse_vtt(str(fp))
            self.assertEqual(len(blocks), 2)

    def test_text_with_arrow_does_not_confuse(self):
        with tempfile.TemporaryDirectory() as d:
            fp = Path(d) / "arrow.vtt"
            fp.write_text(
                "WEBVTT\n\n"
                "1\n"
                "00:00:01.000 --> 00:00:04.000\n"
                "He said --> really\n\n"
                "2\n"
                "00:00:05.000 --> 00:00:08.000\n"
                "More text\n",
                encoding="utf-8",
            )
            blocks = sf.parse_vtt(str(fp))
            self.assertEqual(len(blocks), 2)
            texts = [t for _, _, t in blocks]
            self.assertIn("More text", texts)

    def test_three_cues_all_present(self):
        with tempfile.TemporaryDirectory() as d:
            fp = Path(d) / "three.vtt"
            fp.write_text(
                "WEBVTT\n\n"
                "00:00:01.000 --> 00:00:04.000\n"
                "First\n\n"
                "00:00:05.000 --> 00:00:08.000\n"
                "Second --> with arrow\n\n"
                "00:00:09.000 --> 00:00:12.000\n"
                "Third\n",
                encoding="utf-8",
            )
            blocks = sf.parse_vtt(str(fp))
            self.assertEqual(len(blocks), 3)


if __name__ == "__main__":
    unittest.main()
