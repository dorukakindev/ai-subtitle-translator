# -*- coding: utf-8 -*-
"""Doğru silinmiş künye/promosyon "eksik diyalog" sert hatası olmasın.

Teslim denetimi "silinmesi beklenen" kümesini kendi yordamıyla kuruyordu;
silmeyi FİİLEN yapan geçiş ise daha genişti. İki küme ayrışınca doğru
silinmiş cue'lar sert hataya dönüşüyor, gerçek kayıplar da o gürültünün
içinde görünmez oluyordu.

Ölçüm (267 gerçek kaynak/teslim çifti): eksik-diyalog alarmı 92 → 49,
etkilenen dosya 38 → 23; üç GERÇEK diyalog kaybı (Amazon 4of6 #325,
Shock of the New S01E08 #669, Gates of Heaven #855) yakalanmaya devam
ediyor. Künye yordamı 204.031 kaynak cue'da yalnız 136 kez ateşliyor.
"""
import unittest

import subtitle_translator_gui as g


class CreditAndPromoTest(unittest.TestCase):
    def test_subtitle_team_credits(self):
        for text in (
            "Downloaded From www.AllSubs.org",
            "Created, synced and corrected by goanzaloo -",
            "Subtitles by Red Bee Media Ltd",
            "E-mail subtitling@bbc.co.uk",
            "Traduzido do original da BBC! Valeu!",
            "<b>FELIPHEX - The Espartano Boy Apresenta:</b>",
        ):
            with self.subTest(text=text):
                self.assertTrue(g._looks_like_credit_or_promo(text))

    def test_broadcast_promos(self):
        for text in (
            "<i>If you want to know more, visit</i> <i>our website, bbc.co.uk/amazon</i>",
            "To order this program on DVD,",
            "visit shop pbs or call 1-800-play-pbs.",
            "Also available on Amazon prime video.",
        ):
            with self.subTest(text=text):
                self.assertTrue(g._looks_like_credit_or_promo(text))

    def test_real_dialogue_is_not_a_credit(self):
        # Bunlar teslimde GERÇEKTEN kaybolmuş üç replik; künye sayılırlarsa
        # kayıpları sessizce kabul edilmiş olur.
        for text in (
            "You speak Portuguese.",
            "We're usually talking in terms of death and talking in terms of hereafter.",
            "TRANSLATOR: Like all artists, I am in the tradition of self-portraiture.",
            "Bu, fizik ile mühendislik arasındaki sınır.",
            "Visit us again tomorrow, he said quietly.",
        ):
            with self.subTest(text=text):
                self.assertFalse(g._looks_like_credit_or_promo(text))


class ExpectedRemovedExtraTest(unittest.TestCase):
    def _rows(self, texts):
        return [(str(i), "00:00:%02d,000 --> 00:00:%02d,500" % (i, i), t)
                for i, t in enumerate(texts, 1)]

    def test_credits_and_sound_labels_are_expected_removals(self):
        rows = self._rows([
            "Downloaded From www.AllSubs.org",
            "[Horse neighs] [Screech] [Boing]",
            "He walked into the room and sat down.",
            "She never answered the question.",
            "The rain kept falling all afternoon.",
            "They agreed to meet again the next day.",
            "Nobody spoke for a long moment.",
            "It was colder than anyone expected.",
        ])
        extra = g._delivery_expected_removed_extra_ids(rows)
        self.assertIn("1", extra)
        self.assertIn("2", extra)
        for idx in ("3", "4", "5", "6", "7", "8"):
            self.assertNotIn(idx, extra)

    def test_empty_input_is_safe(self):
        self.assertEqual(g._delivery_expected_removed_extra_ids([]), set())
        self.assertEqual(g._delivery_expected_removed_extra_ids(None), set())


class SameTimestampSdhAndDialogueTest(unittest.TestCase):
    """Aynı aralıkta SDH + replik varsa eşleyici repliği tüketmeli.

    Kaynak #193 `ОН КАШЛЯЕТ` (öksürür) ile #194 gerçek replik aynı
    `00:15:09,080 --> 00:15:15,920` aralığında; teslimde o aralıkta
    çevrilmiş replik duruyor. Eşleyici sırayla ilk kullanılmamış kaynağı
    aldığı için SDH'yi tüketiyor, replik eşsiz kalıyor ve "eksik diyalog"
    sert hatası oluyordu.
    """

    SPAN = (909080, 915920)

    def _rows(self):
        # (idx, ts, text, bounds)
        return [
            ("193", "x", "ОН КАШЛЯЕТ", self.SPAN),
            ("194", "x", "И они даже не замечают,", self.SPAN),
        ]

    def test_dialogue_is_preferred_over_the_sound_label(self):
        rows = self._rows()
        positions = g._source_positions_for_delivery_span(
            rows, self.SPAN, used_positions=set(),
            deprioritized_positions={0})
        self.assertEqual(positions, [1])

    def test_without_the_hint_the_first_row_still_wins(self):
        # Eski davranış: ipucu verilmezse sıra korunur.
        rows = self._rows()
        positions = g._source_positions_for_delivery_span(
            rows, self.SPAN, used_positions=set())
        self.assertEqual(positions, [0])


if __name__ == "__main__":
    unittest.main()
