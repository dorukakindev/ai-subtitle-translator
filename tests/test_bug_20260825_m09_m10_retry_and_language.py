# -*- coding: utf-8 -*-
"""Madde 9 ve 10: terim normalizasyonu tekrarı, kaynak dil log satırı."""
import inspect
import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as gui


def _response(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=None)


_GOOD = _response(json.dumps([{"id": "1", "tr": "Truva geldi."}]))
_BLOCKS = [("1", "ts", "Troy geldi.")]
_SRC = {"1": "Troy came."}


class TermNormalisationRetriesABrokenResponseTest(unittest.TestCase):
    """Bozuk yanıtta paket sessizce düşüyordu: tek 'response_not_array' o
    paketin bütün normalizasyonunu kaybettiriyor ve koşu bitene kadar fark
    edilmiyordu (gerçek koşuda 1 dosyada oldu)."""

    def _run(self, responses):
        logs = []
        with patch.object(gui, "_mixed_term_autofix_plan",
                          return_value={"1": [("Troy", "Truva")]}), \
                patch("openai.OpenAI", return_value=SimpleNamespace()), \
                patch.object(gui, "_safe_chat_create",
                             side_effect=responses) as create:
            result, changed = gui._normalize_mixed_terms(
                _BLOCKS, _SRC, "key", "url", "model",
                log_fn=lambda msg, kind="info": logs.append(msg))
        return create, result, changed, logs

    def test_a_broken_response_is_retried_and_then_succeeds(self):
        create, result, changed, logs = self._run(
            [_response("bu bir dizi değil"), _GOOD])
        self.assertEqual(create.call_count, 2)
        self.assertEqual(changed, 1)
        self.assertEqual(result[0][2], "Truva geldi.")
        self.assertTrue(any("yeniden deneniyor" in m for m in logs),
                        f"tekrar bildirilmedi: {logs}")

    def test_a_persistently_broken_response_is_reported_not_silent(self):
        create, result, changed, logs = self._run(
            [_response("hâlâ dizi değil")] * 5)
        self.assertEqual(create.call_count,
                         gui.TERM_NORMALIZATION_MAX_ATTEMPTS)
        self.assertEqual(changed, 0)
        self.assertEqual(result[0][2], "Troy geldi.")
        self.assertTrue(any("denemede alınamadı" in m for m in logs),
                        f"açık hata satırı yok: {logs}")
        self.assertTrue(any("normalize edilmedi" in m for m in logs))

    def test_a_good_response_still_costs_one_call(self):
        create, _result, changed, _logs = self._run([_GOOD])
        self.assertEqual(create.call_count, 1)
        self.assertEqual(changed, 1)


class TheSourceLanguageIsWrittenToTheLogTest(unittest.TestCase):
    """Hangi dilden çevrildiği log'da hiç yazmıyordu; teşhis sırasında dosya
    ADINA bakmak zorunda kalınıyordu ve addaki dil etiketi otorite değil."""

    def _app(self, chosen, fallback="English"):
        app = SimpleNamespace(
            _active_snapshot=None,
            src_var=SimpleNamespace(get=lambda: fallback),
            _file_language_vars={"x.srt": SimpleNamespace(get=lambda: chosen)},
        )
        app._get_file_source_language = (
            lambda fp: gui.App._get_file_source_language(app, fp))
        app._effective_file_source_language = (
            lambda fp, fb="English":
            gui.App._effective_file_source_language(app, fp, fb))
        return app

    def test_an_explicit_choice_says_so(self):
        app = self._app("French")
        self.assertEqual(gui.App._source_language_log_text(app, "x.srt"),
                         "French (seçildi)")

    def test_an_automatic_choice_says_so(self):
        app = self._app(gui.AUTO_LANGUAGE, fallback="English")
        self.assertEqual(gui.App._source_language_log_text(app, "x.srt"),
                         "English (otomatik tespit)")

    def test_both_flows_log_the_language(self):
        source = inspect.getsource(gui)
        self.assertEqual(
            source.count("_source_language_log_text(self, filepath)"), 2)


if __name__ == "__main__":
    unittest.main()
