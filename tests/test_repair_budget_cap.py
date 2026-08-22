# -*- coding: utf-8 -*-
"""Eksik Cue API Onarımı'nın üst sınırı.

Onarım cue başına BİR istek gönderir ve her istek tam sistem promptunu
taşır (~5.000 token), tekrar yoktur. Birkaç eksik cue için bu ucuzdur —
ölçüm: tipik dosyada ana çevirinin %2'si, bir chunk çöktüğünde %18'i.

Ama sağlayıcı dosyanın ortasında ölürse binlerce cue [HATA] kalır ve
onarım bunları tek tek çevirmeye kalkar. 2026-08-22 koşusunda Domestic
Violence'ta 4.551 cue'nun 4.473'ü eksikti: onarım açık olsaydı yaklaşık
22 milyon token, yani bütün koşunun ana çevirisinin on katı harcanacaktı.

O durum "eksik satır" değil "çeviri başarısız"tır; yamayla değil baştan
çeviriyle düzelir.
"""
import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as gui


def _response(payload):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=payload))],
        usage=SimpleNamespace(total_tokens=12), usage_available=True)


class BudgetThresholdTest(unittest.TestCase):
    def test_the_four_real_files_stay_repairable(self):
        # 2026-08-22 koşusunun gerçek sayıları.
        for missing, total, name in ((31, 1864, "Marjoe"),
                                     (6, 1977, "Dying at Grace"),
                                     (1, 741, "Primate"),
                                     (10, 388, "The Contestant")):
            self.assertFalse(gui._repair_budget_exceeded(missing, total), name)

    def test_a_collapsed_run_is_blocked(self):
        self.assertTrue(gui._repair_budget_exceeded(4473, 4551))

    def test_the_absolute_cap_bites_before_the_ratio(self):
        # Büyük dosyada %10'a varmadan da 150 cue çok fazladır.
        self.assertTrue(gui._repair_budget_exceeded(150, 5000))
        self.assertFalse(gui._repair_budget_exceeded(149, 5000))

    def test_the_ratio_bites_once_the_floor_is_passed(self):
        # Oran eşiği ekonomiden gelir: onarım cue başına ~5.000 token,
        # baştan çeviri cue başına ~480. %10'un üstünde yamamak pahalıdır.
        self.assertTrue(gui._repair_budget_exceeded(60, 200))
        self.assertFalse(gui._repair_budget_exceeded(49, 200))

    def test_a_tiny_file_is_never_blocked(self):
        # Üç cue'luk dosyada bir eksik %33'tür ama maliyeti tek istektir.
        self.assertFalse(gui._repair_budget_exceeded(1, 1))
        self.assertFalse(gui._repair_budget_exceeded(1, 3))
        self.assertFalse(gui._repair_budget_exceeded(3, 10))
        # 50 isteğin altında oran tartışması yapılmaz; onarım hep denenir.
        self.assertFalse(gui._repair_budget_exceeded(30, 30))

    def test_nothing_missing_is_never_over_budget(self):
        self.assertFalse(gui._repair_budget_exceeded(0, 100))

    def test_broken_input_does_not_block_repair(self):
        # Tavan bir güvenlik kontrolü değil; sayamıyorsa yol vermeli.
        self.assertFalse(gui._repair_budget_exceeded(None, 100))
        self.assertFalse(gui._repair_budget_exceeded(5, None))


class BudgetWiringTest(unittest.TestCase):
    def _run(self, blocks, sources, logs):
        with patch.object(gui, "_safe_chat_create") as chat:
            chat.return_value = _response(json.dumps([{"i": "1", "t": "Merhaba."}]))
            out, repaired = gui._repair_untranslated_sync(
                blocks, sources, client=object(), src_lang="English",
                tgt_lang="Turkish", model="gpt-test", enabled=True,
                log_fn=lambda message, level="info": logs.append((level, message)),
            )
            return out, repaired, chat.call_count

    def test_a_small_gap_is_still_repaired(self):
        blocks = [(str(i), "00:00:01,000 --> 00:00:02,000",
                   "[HATA]" if i == 1 else "Tamam.") for i in range(1, 31)]
        sources = {str(i): "Hello there my friend." for i in range(1, 31)}
        logs = []
        _out, _repaired, calls = self._run(blocks, sources, logs)
        self.assertEqual(calls, 1)

    def test_a_collapsed_file_sends_nothing_to_the_api(self):
        blocks = [(str(i), "00:00:01,000 --> 00:00:02,000", "[HATA]")
                  for i in range(1, 201)]
        sources = {str(i): "Hello there my friend." for i in range(1, 201)}
        logs = []
        _out, repaired, calls = self._run(blocks, sources, logs)
        self.assertEqual(calls, 0, "tavanı aşan dosyada API çağrılmamalı")
        self.assertEqual(repaired, 0)

    def test_the_block_is_reported_as_an_error_not_a_silent_skip(self):
        blocks = [(str(i), "00:00:01,000 --> 00:00:02,000", "[HATA]")
                  for i in range(1, 201)]
        sources = {str(i): "Hello there my friend." for i in range(1, 201)}
        logs = []
        self._run(blocks, sources, logs)
        errors = [msg for level, msg in logs if level == "err"]
        self.assertTrue(errors, "sessizce atlanmamalı")
        self.assertIn("baştan çevrilmeli", errors[0])

    def test_the_blocked_cues_still_reach_the_review_report(self):
        blocks = [(str(i), "00:00:01,000 --> 00:00:02,000", "[HATA]")
                  for i in range(1, 201)]
        sources = {str(i): "Hello there my friend." for i in range(1, 201)}
        reviews = []
        with patch.object(gui, "_safe_chat_create") as chat:
            chat.return_value = _response("[]")
            gui._repair_untranslated_sync(
                blocks, sources, client=object(), src_lang="English",
                tgt_lang="Turkish", model="gpt-test", enabled=True,
                advisory_reviews_out=reviews)
        self.assertTrue(reviews)
        self.assertEqual({row["reason"] for row in reviews},
                         {"repair_budget_exceeded"})

    def test_repair_switched_off_still_reads_as_switched_off(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "[HATA]")]
        sources = {"1": "Hello there my friend."}
        logs = []
        with patch.object(gui, "_safe_chat_create") as chat:
            chat.return_value = _response("[]")
            gui._repair_untranslated_sync(
                blocks, sources, client=object(), src_lang="English",
                tgt_lang="Turkish", model="gpt-test", enabled=False,
                log_fn=lambda message, level="info": logs.append((level, message)))
        self.assertTrue(any("Onarımı kapalı" in msg for _lvl, msg in logs))


if __name__ == "__main__":
    unittest.main()
