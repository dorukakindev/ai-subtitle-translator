"""apply_polish_group_atomic (hybrid_translate.py) — Polish Pass kabul mantığını
cue-cue'dan grup-atomik'e çevirir (bkz. plans/polish-group-atomicity-brief.md).

Sorun: bir fragment grubunun (start/mid/end) bazı üyeleri kabul edilip bazıları
reddedildiğinde, kalan cue'lar arasında cümle bölünmesi/anlam kayması oluşuyordu
(bu oturumda Solve Et Coagula ve Sumerian dosyalarında canlı örnekleri görüldü).
Artık bir gruptan DEĞİŞEN herhangi bir üye reddedilirse, o grubun TÜM
değişiklikleri geri alınır (hep-ya-da-hiç). Singleton (group_id=None) cue'lar
bağımsız uygulanır — mevcut davranış korunur.
"""
import unittest

import hybrid_translate as ht


class AllGroupPassAppliesAllTest(unittest.TestCase):
    def test_three_cue_group_all_ok_applies_all(self):
        proposals = {
            "1": ("Yeni metin 1", True, "", "fg_1_3"),
            "2": ("Yeni metin 2", True, "", "fg_1_3"),
            "3": ("Yeni metin 3", True, "", "fg_1_3"),
        }
        original_by_id = {"1": "Eski metin 1", "2": "Eski metin 2", "3": "Eski metin 3"}
        result_map, rejected, reasons = ht.apply_polish_group_atomic(proposals, original_by_id)
        self.assertEqual(result_map, {"1": "Yeni metin 1", "2": "Yeni metin 2", "3": "Yeni metin 3"})
        self.assertEqual(rejected, 0)


class OneGroupFailRevertsAllTest(unittest.TestCase):
    def test_middle_cue_rejected_reverts_whole_group(self):
        proposals = {
            "1": ("Yeni metin 1", True, "", "fg_1_3"),
            "2": ("Bozuk metin 2", False, "content_word_loss", "fg_1_3"),
            "3": ("Yeni metin 3", True, "", "fg_1_3"),
        }
        original_by_id = {"1": "Eski metin 1", "2": "Eski metin 2", "3": "Eski metin 3"}
        result_map, rejected, reasons = ht.apply_polish_group_atomic(proposals, original_by_id)
        # Hiçbiri uygulanmamalı — 1 ve 3 de geçse bile grup bütünlüğü için geri alınır.
        self.assertEqual(result_map, {})
        self.assertEqual(rejected, 3)
        self.assertIn("group_atomic:content_word_loss", reasons)
        self.assertEqual(reasons["group_atomic:content_word_loss"], 3)


class SingletonIndependentTest(unittest.TestCase):
    def test_singleton_reject_does_not_affect_neighbor(self):
        proposals = {
            "10": ("Yeni tekil", False, "too_long", None),
            "11": ("Yeni komşu", True, "", None),
        }
        original_by_id = {"10": "Eski tekil", "11": "Eski komşu"}
        result_map, rejected, reasons = ht.apply_polish_group_atomic(proposals, original_by_id)
        self.assertEqual(result_map, {"11": "Yeni komşu"})
        self.assertEqual(rejected, 1)
        self.assertEqual(reasons.get("too_long"), 1)


class UnchangedGroupMemberIgnoredTest(unittest.TestCase):
    def test_only_actually_changed_member_counts(self):
        # Grupta 1 cue gerçekten değişmiş (ve geçmiş); diğerleri model tarafından
        # aynen döndürülmüş (new_text == original) — onlar "değişen" sayılmamalı.
        proposals = {
            "5": ("Aynı metin 5", True, "", "fg_5_7"),   # değişmemiş
            "6": ("Yeni metin 6", True, "", "fg_5_7"),   # gerçekten değişmiş, geçti
            "7": ("Aynı metin 7", True, "", "fg_5_7"),   # değişmemiş
        }
        original_by_id = {"5": "Aynı metin 5", "6": "Eski metin 6", "7": "Aynı metin 7"}
        result_map, rejected, reasons = ht.apply_polish_group_atomic(proposals, original_by_id)
        self.assertEqual(result_map, {"6": "Yeni metin 6"})
        self.assertEqual(rejected, 0)


class PartialResponseGroupTest(unittest.TestCase):
    def test_partial_group_response_with_one_rejected_reverts_changed_only(self):
        # Model grubun yalnız 2/3 cue'sunu döndürmüş (3. hiç önerilmemiş, proposals'ta yok);
        # dönenlerden biri red alırsa yalnızca DÖNEN ve DEĞİŞEN öneriler geri alınır.
        proposals = {
            "20": ("Yeni metin 20", True, "", "fg_20_22"),
            "21": ("Bozuk metin 21", False, "format_tags", "fg_20_22"),
            # "22" modelden hiç gelmemiş — proposals'ta yok.
        }
        original_by_id = {"20": "Eski metin 20", "21": "Eski metin 21", "22": "Eski metin 22"}
        result_map, rejected, reasons = ht.apply_polish_group_atomic(proposals, original_by_id)
        self.assertEqual(result_map, {})
        self.assertEqual(rejected, 2)
        self.assertEqual(reasons.get("group_atomic:format_tags"), 2)


class PartialResponseAllPassRevertsTest(unittest.TestCase):
    def test_group_expected_with_missing_member_reverts_even_if_returned_pass(self):
        # 3 üyeli grup ama model yalnız 2/3'ünü döndürmüş; ikisi de per-cue geçiyor.
        # group_expected VERİLDİĞİNDE bu artık yetmez — grubun tamamı görülmeden
        # cümle bütünlüğü doğrulanamaz, hiçbiri uygulanmamalı.
        proposals = {
            "20": ("Yeni metin 20", True, "", "fg_20_22"),
            "21": ("Yeni metin 21", True, "", "fg_20_22"),
            # "22" modelden hiç gelmemiş.
        }
        original_by_id = {"20": "Eski metin 20", "21": "Eski metin 21", "22": "Eski metin 22"}
        group_expected = {"fg_20_22": ["20", "21", "22"]}
        result_map, rejected, reasons = ht.apply_polish_group_atomic(
            proposals, original_by_id, group_expected=group_expected)
        self.assertEqual(result_map, {})
        self.assertEqual(rejected, 2)
        self.assertEqual(reasons.get("group_atomic:partial_response"), 2)


class FullResponseAllPassAppliesTest(unittest.TestCase):
    def test_group_expected_full_response_and_joined_ok_applies_all(self):
        # İçerik kelimeleri AYNI, yalnız eksik noktalama düzeltilmiş — hem per-cue
        # hem birleşik doğrulama geçmeli, grubun tamamı uygulanmalı.
        proposals = {
            "30": ("Bu iş hakkında konuşalım,", True, "", "fg_30_32"),
            "31": ("gerçekten önemli.", True, "", "fg_30_32"),
            "32": ("Devam edelim.", True, "", "fg_30_32"),
        }
        original_by_id = {
            "30": "Bu iş hakkında konuşalım",
            "31": "gerçekten önemli",
            "32": "Devam edelim",
        }
        group_expected = {"fg_30_32": ["30", "31", "32"]}
        result_map, rejected, reasons = ht.apply_polish_group_atomic(
            proposals, original_by_id, group_expected=group_expected)
        self.assertEqual(result_map, {
            "30": "Bu iş hakkında konuşalım,",
            "31": "gerçekten önemli.",
            "32": "Devam edelim.",
        })
        self.assertEqual(rejected, 0)


class JoinedMeaningFailureRevertsTest(unittest.TestCase):
    def test_joined_number_loss_reverts_despite_per_cue_ok(self):
        # Her cue tek başına "geçti" (ok=True) sayılıyor (test kendi proposals'ını
        # elle veriyor) ama BİRLEŞİK metinde kaynaktaki "144.000" sayısı tamamen
        # düşürülmüş — gerçek validate_polish_candidate bunu joined seviyede yakalamalı.
        proposals = {
            "40": ("kurtarma görevi", True, "", "fg_40_41"),
            "41": ("görevine.", True, "", "fg_40_41"),
        }
        original_by_id = {
            "40": "144.000 ruhu kurtarma",
            "41": "görevine.",
        }
        group_expected = {"fg_40_41": ["40", "41"]}
        result_map, rejected, reasons = ht.apply_polish_group_atomic(
            proposals, original_by_id, group_expected=group_expected)
        self.assertEqual(result_map, {})
        self.assertEqual(rejected, 1)  # yalnız "40" gerçekten değişti ("41" aynı kaldı)
        self.assertTrue(any(k.startswith("group_atomic_joined:") for k in reasons))


class RedistributionAcrossCuesPassesJoinedTest(unittest.TestCase):
    def test_word_moved_between_cues_passes_joined_check(self):
        # "kırmızı" kelimesi cue 50'den cue 51'e taşınmış (meşru SOV yeniden-dağıtımı).
        # Her cue tek başına bakılsa kelime kaybı gibi görünebilir ama BİRLEŞİK metinde
        # kelime hâlâ var — joined kontrol GEÇMELİ, grup uygulanmalı.
        proposals = {
            "50": ("kral ve", True, "", "fg_50_51"),
            "51": ("kırmızı beyaz kraliçedir.", True, "", "fg_50_51"),
        }
        original_by_id = {
            "50": "kırmızı kral ve",
            "51": "beyaz kraliçedir.",
        }
        group_expected = {"fg_50_51": ["50", "51"]}
        result_map, rejected, reasons = ht.apply_polish_group_atomic(
            proposals, original_by_id, group_expected=group_expected)
        self.assertEqual(result_map, {"50": "kral ve", "51": "kırmızı beyaz kraliçedir."})
        self.assertEqual(rejected, 0)


if __name__ == "__main__":
    unittest.main()
