# -*- coding: utf-8 -*-
"""Satır kırma geçişi kendi çıktısını yeniden bozmasın.

`apply_line_breaks` deterministik bir teslim geçişi; `f(f(x)) == f(x)`
olmalı. Gerçek arşivde değildi: 288 teslimin 124'ünde ikinci uygulama 188
cue'yu değiştiriyordu ve **63 dosyadaki 86 cue hiçbir tekrar sayısında
sabit noktaya ulaşmıyordu** — iki satır düzeni arasında sonsuza dek
salınıyorlardı.

Üç ayrı kök neden vardı:

1. `ile` HEM yukarı-çekilenler HEM aşağı-itilenler listesindeydi; sözcük
   nerede olursa olsun öbür satıra taşınıyordu.
2. `Bu tam` gibi ARDIŞIK iki itme sözcüğünde biri inince öbürü sona
   geçiyor, sonraki geçiş onu da itiyordu.
3. Dengeleme çağrı başına tek sözcük taşıyordu; `için de` gibi ardışık
   edatlarda ikincisi bir sonraki geçişe kalıyordu.

Ölçüm (288 gerçek teslim): salınım 86 cue → 0; ikinci geçiş değişimi
188 cue → 2. Maliyet: 336.100 satırda eşiği aşan satır +7.
"""
import unittest

import subtitle_translator_gui as g


def _cue(text):
    return [("1", "00:00:01,000 --> 00:00:04,000", text)]


def _apply(text, times=1):
    blocks = _cue(text)
    for _ in range(times):
        blocks = g.apply_line_breaks(blocks)
    return blocks[0][2]


class LineBreakWordListTest(unittest.TestCase):
    def test_no_word_is_in_both_lists(self):
        # Bir sözcük iki listede birden olursa dengeleme onu sonsuza dek
        # bir satırdan öbürüne taşır.
        self.assertEqual(
            g._LINE_PULL_UP_WORDS & g._LINE_PUSH_DOWN_WORDS, frozenset())

    def test_ile_is_pulled_up_not_pushed_down(self):
        # 'ile' bir edattır, kendinden ÖNCEKİ adı yönetir; satır başlatmaz.
        self.assertIn("ile", g._LINE_PULL_UP_WORDS)
        self.assertNotIn("ile", g._LINE_PUSH_DOWN_WORDS)


class LineBreakIdempotencyTest(unittest.TestCase):
    CASES = [
        "kardeşi Hippolyte ile yarım maaşla yaşarken,",
        "Bu, fizik ile mühendislik arasındaki sınır.",
        "Ben yapabilir miyim? Bu tam bir felaket olacak... Buyurun, yapın.",
        "çatışmaları çözmemiz için de araçlar sunar.",
        "tahtın geçebileceği kadar bile geniş değil.",
        "Aynı şey IKEA'nın tasarımı için de geçerliydi.",
    ]

    def test_second_pass_changes_nothing(self):
        for text in self.CASES:
            with self.subTest(text=text):
                once = _apply(text, 1)
                twice = _apply(text, 2)
                self.assertEqual(once, twice)

    def test_no_oscillation_between_two_layouts(self):
        for text in self.CASES:
            with self.subTest(text=text):
                seen = [_apply(text, n) for n in range(1, 6)]
                self.assertEqual(len(set(seen[2:])), 1, seen)

    def test_rebalance_alone_reaches_a_fixed_point(self):
        for text in (
            "kardeşi Hippolyte\nile yarım maaşla yaşarken,",
            "kardeşi Hippolyte ile\nyarım maaşla yaşarken,",
            "Ben yapabilir miyim? Bu tam\nbir felaket olacak... Buyurun, yapın.",
            "çatışmaları çözmemiz\niçin de araçlar sunar.",
        ):
            with self.subTest(text=text):
                once = g._rebalance_line_break(text)
                self.assertEqual(g._rebalance_line_break(once), once)

    def test_words_are_preserved(self):
        for text in self.CASES:
            with self.subTest(text=text):
                out = _apply(text, 3)
                self.assertEqual(out.replace("\n", " ").split(), text.split())


if __name__ == "__main__":
    unittest.main()
