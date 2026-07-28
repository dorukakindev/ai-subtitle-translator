import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import hybrid_translate as ht
import subtitle_translator_gui as gui


class _Cue:
    def __init__(self, index, start, end, text):
        self.index = index
        self.start = start
        self.end = end
        self.text = text


class LocalFixOrderTest(unittest.TestCase):
    def test_my_ass_runs_before_ass(self):
        self.assertEqual(ht._apply_local_fixes("my ass")[0], "benim götüm")

    def test_my_ass_ate_preserves_specific_phrase(self):
        self.assertEqual(ht._apply_local_fixes("my ass ate")[0], "benim götüm ate")

    def test_plain_ass_still_works(self):
        self.assertEqual(ht._apply_local_fixes("ass")[0], "göt")

    def test_asses_still_works(self):
        self.assertEqual(ht._apply_local_fixes("asses")[0], "götler")


class FinalConsistencySweepTest(unittest.TestCase):
    def test_no_majority_tie_leaves_unchanged(self):
        # 1 vs 1 (çoğunluk yok) — first_seen fallback KALDIRILDI (bkz.
        # plans/quality-quickwins-brief.md Görev 1): bağlam-bağımlı farklı
        # çeviriler artık zorla tek forma normalize edilmiyor.
        cues = [
            _Cue("1", "00:00:01,000", "00:00:02,000", "Same source line."),
            _Cue("2", "00:00:02,000", "00:00:03,000", "Different line."),
            _Cue("3", "00:00:03,000", "00:00:04,000", "Same source line."),
        ]
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Aynı çeviri."),
            ("2", "00:00:02,000 --> 00:00:03,000", "Başka satır."),
            ("3", "00:00:03,000 --> 00:00:04,000", "Aynı çeviri!"),
        ]
        swept, fixes = ht.final_consistency_sweep(cues, blocks)
        self.assertEqual(fixes, 0)
        self.assertEqual(swept[2][2], "Aynı çeviri!")


class ReviewPassFragmentGuardTest(unittest.TestCase):
    def test_review_pass_rejects_fragment_terminal_backslide(self):
        cues = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Hello"),
            ("2", "00:00:02,100 --> 00:00:03,000", "world."),
        ]
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Merhaba"),
            ("2", "00:00:02,100 --> 00:00:03,000", "dünya."),
        ]

        class _FakeCompletions:
            def create(self, **kwargs):
                return SimpleNamespace(
                    usage=None,
                    choices=[SimpleNamespace(
                        message=SimpleNamespace(content=json.dumps([{"i": "1", "t": "Merhaba."}], ensure_ascii=False))
                    )],
                )

        class _FakeClient:
            def __init__(self, *args, **kwargs):
                self.chat = SimpleNamespace(completions=_FakeCompletions())

        class _Var:
            def __init__(self, value):
                self._value = value

            def get(self):
                return self._value

        class _App:
            _stop_flag = False

            def __init__(self):
                self.api_url_var = _Var("")
                self.api_key_entry = _Var("sk-test")
                self.logs = []

            # Ana Model — Özel Sağlayıcı devre dışı (bu stub'da hiç ayarlanmamış) —
            # gerçek App'in resolver'larının varsayılan (custom kapalı) davranışı.
            def _main_api_key(self):
                return self.api_key_entry.get()

            def _main_api_base_url(self):
                return gui._normalize_api_base_url(self.api_url_var.get())

            def _cached_blocks_for(self, _fp):
                return None

            def _locked_terms_hint(self, _fp, _tgt):
                return ""

            def _update_tokens(self, *args, **kwargs):
                return None

            def _set_status(self, *args, **kwargs):
                return None

            def _log(self, msg, level=""):
                self.logs.append((level, msg))

            def _log_exc(self, msg, exc):
                self.logs.append(("err", f"{msg}: {exc}"))

        app = _App()
        with mock.patch.object(gui, "OpenAI", _FakeClient), \
             mock.patch.object(gui, "parse_subtitle", return_value=cues):
            out_blocks, fixes = gui.App._review_pass(app, "dummy.srt", blocks, "gpt-5.4-mini", "Turkish")

        self.assertEqual(out_blocks[0][2], "Merhaba")
        self.assertEqual(fixes, 0)
        self.assertTrue(any("fragment_terminal:1" in msg for _lvl, msg in app.logs), app.logs)


class GitIgnoreCoverageTest(unittest.TestCase):
    def test_sensitive_files_are_ignored(self):
        gitignore = Path(__file__).resolve().parent.parent / ".gitignore"
        content = gitignore.read_text(encoding="utf-8")
        for needle in (
            ".credentials",
            ".gui_settings.json",
            ".gui_settings.json.bak.*",
            "batch_fmap_*.json",
            "batch_id.txt",
            "_batch_sessions/",
        ):
            self.assertIn(needle, content)


if __name__ == "__main__":
    unittest.main()
