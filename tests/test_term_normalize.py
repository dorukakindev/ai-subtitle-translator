"""Terim normalizasyonu (_mixed_term_autofix_plan / _validate_term_normalize_candidate /
_normalize_mixed_terms, subtitle_translator_gui.py) — 2026-07-10, gerçek-dosya vakası
(Strangest Things S02E03) sonrası eklendi: detect_mixed_term_renderings YALNIZCA rapor
ediyordu, bu düzeltmeyi kalıcılaştırır ama YALNIZCA güvenli sınıfı (kaynakla birebir
aynı kalmış 'sızıntı' biçimi) — sayıca çoğunluk ASLA tek başına karar vermez, çünkü
gerçek vakada YANLIŞ biçim (Troy, İngilizce) çoğunluktaydı (14), DOĞRU biçim (Truva)
azınlıktaydı (3)."""
import unittest
from unittest.mock import patch

import subtitle_translator_gui as gui


def _b(*rows):
    return [(str(i), "00:00:01,000 --> 00:00:02,000", t) for i, t in rows]


def _s(**kw):
    return {str(k): v for k, v in kw.items()}


class MixedTermAutofixPlanTest(unittest.TestCase):
    def test_single_locked_english_residue_is_planned(self):
        blocks = _b((48, "Soldano'nun Memories'leri olamazdı."))
        src = _s(**{"48": "Soldano couldn't have the Memories."})
        plan = gui._mixed_term_autofix_plan(
            blocks, src, locked_terms={"Memories": "Anılar"})
        self.assertEqual(plan, {"48": [("Memories", "Anılar")]})

    def test_locked_source_equal_target_is_not_planned(self):
        blocks = _b((1, "Roger Smith geldi."))
        src = _s(**{"1": "Roger Smith arrived."})
        plan = gui._mixed_term_autofix_plan(
            blocks, src, locked_terms={"Roger Smith": "Roger Smith"})
        self.assertEqual(plan, {})

    def test_long_unmatched_lock_does_not_hide_inner_residue(self):
        blocks = _b((1, "gerçek Memories geri döndü."))
        src = _s(**{"1": "the true Memories returned."})
        plan = gui._mixed_term_autofix_plan(
            blocks, src,
            locked_terms={"true Memories": "gerçek Anılar", "Memories": "Anılar"})
        self.assertEqual(plan, {"1": [("Memories", "Anılar")]})

    def test_leak_cluster_targeted_even_when_minority(self):
        # Gerçek vaka: kaynakla birebir aynı 'Troy' ÇOĞUNLUKTA (3), doğru 'Truva' AZINLIKTA (2).
        # Plan yine de 'Troy' örneklerini hedeflemeli (çoğunluk değil, kaynak-eşleşme karar verir).
        blocks = _b(
            (1, "Troy kuşatması başladı."),
            (2, "Sonra Troy yıkıldı."),
            (3, "Truva'nın kalıntıları bulundu."),
            (4, "Ama Troy hâlâ tartışmalı."),
            (5, "Truva'ya dair yeni kanıtlar var."),
        )
        src = _s(**{
            "1": "The Troy siege began.",
            "2": "Then Troy fell.",
            "3": "The ruins of Troy were found.",
            "4": "But Troy is still disputed.",
            "5": "New evidence about Troy exists.",
        })
        plan = gui._mixed_term_autofix_plan(blocks, src)
        # cue 1,2,4'teki 'Troy' (yanlış/sızıntı) hedeflenmeli
        self.assertEqual(set(plan.keys()), {"1", "2", "4"})
        for idx in ("1", "2", "4"):
            self.assertEqual(plan[idx], [("Troy", "Truva")])

    def test_two_valid_turkish_variants_not_planned(self):
        # İki küme de kaynakla (Iliad) birebir aynı DEĞİL (ikisi de Türkçe transliterasyon)
        # — bu bir sızıntı değil, üslup tercihi; otomatik düzeltme YAPILMAMALI.
        blocks = _b(
            (1, "İliada'da anlatılan olaylar."),
            (2, "İlyada'nın kahramanları."),
            (3, "İliada üzerine yeni araştırma."),
            (4, "İlyada'da geçen sahne."),
            (5, "İliada'nın izleri sürüldü."),
        )
        src = _s(**{
            "1": "Events told in the Iliad.",
            "2": "Heroes of the Iliad.",
            "3": "New research on the Iliad.",
            "4": "A scene from the Iliad.",
            "5": "Traces of the Iliad were followed.",
        })
        plan = gui._mixed_term_autofix_plan(blocks, src)
        self.assertEqual(plan, {})

    def test_more_than_two_clusters_not_planned(self):
        blocks = _b(
            (1, "Alpha burada."),
            (2, "Beta orada."),
            (3, "Gamma şurada."),
            (4, "Alpha yine burada."),
            (5, "Beta yine orada."),
            (6, "Gamma yine şurada."),
        )
        src = _s(**{
            "1": "Ephyra is here.", "2": "Ephyra is there.", "3": "Ephyra is over there.",
            "4": "Ephyra is here again.", "5": "Ephyra is there again.", "6": "Ephyra is over there again.",
        })
        plan = gui._mixed_term_autofix_plan(blocks, src)
        self.assertEqual(plan, {})

    def test_no_findings_returns_empty_plan(self):
        blocks = _b((1, "Tutarlı çeviri."), (2, "Yine tutarlı."))
        src = _s(**{"1": "Consistent translation.", "2": "Still consistent."})
        self.assertEqual(gui._mixed_term_autofix_plan(blocks, src), {})


class ValidateTermNormalizeCandidateTest(unittest.TestCase):
    def test_valid_simple_swap(self):
        ok, reason = gui._validate_term_normalize_candidate(
            "Schliemann tartışmalı bir kişilikti,",
            "Şlimann tartışmalı bir kişilikti,",
            [("Schliemann", "Şlimann")])
        self.assertTrue(ok, reason)

    def test_valid_swap_with_suffix_change(self):
        # Troy'un (buffer'sız) -> Truva'nın (buffer'lı 'n') — ek TÜMÜYLE değişebilir.
        ok, reason = gui._validate_term_normalize_candidate(
            "Troy'un keşfi, onun aslında",
            "Truva'nın keşfi, onun aslında",
            [("Troy", "Truva")])
        self.assertTrue(ok, reason)

    def test_valid_multiline_swap(self):
        # Zaten TÜRKÇE bir cümlede yalnızca ad değişiyor (ör. gerçek #218 vakası) —
        # bu VALID; tüm satırın diğer dilden çevrildiği durum (#53 gibi) bu
        # fonksiyonun kapsamı DIŞINDA (o bir yeniden-çeviri, terim-swap değil).
        ok, reason = gui._validate_term_normalize_candidate(
            "Schliemann'ın bu maskenin keşfini\nsahtelediğinden şüphelenmesi.",
            "Şlimann'ın bu maskenin keşfini\nsahtelediğinden şüphelenmesi.",
            [("Schliemann", "Şlimann")])
        self.assertTrue(ok, reason)

    def test_rejects_full_line_retranslation_not_just_term_swap(self):
        # Gerçek #53 vakası: satır HİÇ çevrilmemiş kalmıştı (İngilizce). Bu fonksiyon
        # yalnızca dar-kapsamlı terim-swap'i doğrular — tüm cümlenin dilinin
        # değiştiği (yeniden-çeviri) durumları KASITLI OLARAK reddeder; o iş
        # _repair_untranslated_sync gibi ayrı bir mekanizmanın kapsamındadır.
        ok, reason = gui._validate_term_normalize_candidate(
            "German archaeologist Heinrich\nSchliemann,",
            "Alman arkeolog Heinrich\nŞlimann,",
            [("Schliemann", "Şlimann")])
        self.assertFalse(ok)
        self.assertEqual(reason, "unrelated_text_changed")

    def test_rejects_wrong_term_still_present(self):
        ok, reason = gui._validate_term_normalize_candidate(
            "Troy gerçekse, başka hangi",
            "Troy gerçekse, başka hangi",  # model satırı aynen döndürdü — düzeltme yok
            [("Troy", "Truva")])
        self.assertFalse(ok)
        self.assertEqual(reason, "term_not_replaced")

    def test_rejects_correct_term_missing(self):
        ok, reason = gui._validate_term_normalize_candidate(
            "Troy gerçekse, başka hangi",
            "Sparta gerçekse, başka hangi",  # yanlış yere düzeltilmiş
            [("Troy", "Truva")])
        self.assertFalse(ok)
        self.assertEqual(reason, "term_missing_after_fix")

    def test_rejects_unrelated_word_changed(self):
        # Terim doğru değişmiş ama BAŞKA bir kelime de değişmiş — aşırı-düzenleme reddi.
        ok, reason = gui._validate_term_normalize_candidate(
            "Troy gerçekse, başka hangi",
            "Truva gerçekse, çok başka hangi",
            [("Troy", "Truva")])
        self.assertFalse(ok)
        self.assertEqual(reason, "unrelated_text_changed")

    def test_rejects_linebreak_count_change(self):
        ok, reason = gui._validate_term_normalize_candidate(
            "Troy'un keşfi, onun aslında\nöyle yalnızca mitolojik bir yer değil,",
            "Truva'nın keşfi, onun aslında öyle yalnızca mitolojik bir yer değil,",
            [("Troy", "Truva")])
        self.assertFalse(ok)
        self.assertEqual(reason, "linebreak_count")

    def test_rejects_empty(self):
        ok, reason = gui._validate_term_normalize_candidate("Troy burada.", "", [("Troy", "Truva")])
        self.assertFalse(ok)
        self.assertEqual(reason, "empty")


class NormalizeMixedTermsTest(unittest.TestCase):
    def _fake_openai_module(self, fixes):
        from types import SimpleNamespace
        class FakeCompletions:
            def create(self, **kwargs):
                return SimpleNamespace(
                    usage=None,
                    choices=[SimpleNamespace(
                        message=SimpleNamespace(content=gui.json.dumps(fixes, ensure_ascii=False))
                    )],
                )
        class FakeOpenAI:
            def __init__(self, api_key=None, base_url=None):
                self.chat = SimpleNamespace(completions=FakeCompletions())
        return SimpleNamespace(OpenAI=FakeOpenAI)

    def test_no_plan_returns_unchanged_without_api_call(self):
        blocks = _b((1, "Tutarlı çeviri."), (2, "Yine tutarlı."))
        src = _s(**{"1": "Consistent translation.", "2": "Still consistent."})
        result, n = gui._normalize_mixed_terms(blocks, src, "key", "url", "model")
        self.assertEqual(result, blocks)
        self.assertEqual(n, 0)

    def test_applies_valid_fix_from_mocked_response(self):
        blocks = _b(
            (1, "Troy kuşatması başladı."),
            (2, "Sonra Troy yıkıldı."),
            (3, "Truva'nın kalıntıları bulundu."),
            (4, "Ama Troy hâlâ tartışmalı."),
            (5, "Truva'ya dair yeni kanıtlar var."),
        )
        src = _s(**{
            "1": "The Troy siege began.",
            "2": "Then Troy fell.",
            "3": "The ruins of Troy were found.",
            "4": "But Troy is still disputed.",
            "5": "New evidence about Troy exists.",
        })
        fixes = [
            {"id": "1", "tr": "Truva kuşatması başladı."},
            {"id": "2", "tr": "Sonra Truva yıkıldı."},
            {"id": "4", "tr": "Ama Truva hâlâ tartışmalı."},
        ]
        import sys
        with patch.dict(sys.modules, {"openai": self._fake_openai_module(fixes)}):
            result, n = gui._normalize_mixed_terms(blocks, src, "key", "url", "model")
        self.assertEqual(n, 3)
        result_map = {idx: text for idx, _ts, text in result}
        self.assertEqual(result_map["1"], "Truva kuşatması başladı.")
        self.assertEqual(result_map["2"], "Sonra Truva yıkıldı.")
        self.assertEqual(result_map["4"], "Ama Truva hâlâ tartışmalı.")
        # Zaten doğru olan satırlara (3,5) dokunulmadı (plan'da yoktu)
        self.assertEqual(result_map["3"], "Truva'nın kalıntıları bulundu.")
        self.assertEqual(result_map["5"], "Truva'ya dair yeni kanıtlar var.")

    def test_rejects_invalid_response_keeps_original(self):
        blocks = _b(
            (1, "Troy kuşatması başladı."),
            (2, "Sonra Troy yıkıldı."),
            (3, "Truva'nın kalıntıları bulundu."),
            (4, "Ama Troy hâlâ tartışmalı."),
            (5, "Truva'ya dair yeni kanıtlar var."),
        )
        src = _s(**{
            "1": "The Troy siege began.",
            "2": "Then Troy fell.",
            "3": "The ruins of Troy were found.",
            "4": "But Troy is still disputed.",
            "5": "New evidence about Troy exists.",
        })
        # Model satırı hem düzeltmiş HEM başka kelime değiştirmiş -> reddedilmeli
        fixes = [
            {"id": "1", "tr": "Truva büyük kuşatması başladı."},
            {"id": "2", "tr": "Sonra Truva yıkıldı."},
            {"id": "4", "tr": "Ama Truva hâlâ tartışmalı."},
        ]
        import sys
        with patch.dict(sys.modules, {"openai": self._fake_openai_module(fixes)}):
            result, n = gui._normalize_mixed_terms(blocks, src, "key", "url", "model")
        self.assertEqual(n, 2)  # yalnızca 2 ve 4 uygulandı, 1 reddedildi
        result_map = {idx: text for idx, _ts, text in result}
        self.assertEqual(result_map["1"], "Troy kuşatması başladı.")  # değişmedi

    def test_ignores_outside_id_non_string_and_conflicting_duplicate(self):
        blocks = _b(
            (1, "Troy kuşatması başladı."),
            (2, "Sonra Troy yıkıldı."),
            (3, "Truva'nın kalıntıları bulundu."),
            (4, "Ama Troy hâlâ tartışmalı."),
            (5, "Truva'ya dair yeni kanıtlar var."),
        )
        src = _s(**{
            "1": "The Troy siege began.", "2": "Then Troy fell.",
            "3": "The ruins of Troy were found.",
            "4": "But Troy is still disputed.",
            "5": "New evidence about Troy exists.",
        })
        fixes = [
            {"id": "1", "tr": "Truva kuşatması başladı."},
            {"id": "2", "tr": 123},
            {"id": "3", "tr": "Bu cue planda değil."},
            {"id": "4", "tr": "Ama Truva hâlâ tartışmalı."},
            {"id": "4", "tr": "Ama Troya hâlâ tartışmalı."},
        ]
        import sys
        with patch.dict(sys.modules, {"openai": self._fake_openai_module(fixes)}):
            result, n = gui._normalize_mixed_terms(
                blocks, src, "key", "url", "model")

        result_map = {idx: text for idx, _ts, text in result}
        self.assertEqual(n, 1)
        self.assertEqual(result_map["1"], "Truva kuşatması başladı.")
        self.assertEqual(result_map["2"], "Sonra Troy yıkıldı.")
        self.assertEqual(result_map["3"], "Truva'nın kalıntıları bulundu.")
        self.assertEqual(result_map["4"], "Ama Troy hâlâ tartışmalı.")

    def test_missing_helper_key_returns_unchanged(self):
        blocks = _b(
            (1, "Troy kuşatması başladı."),
            (2, "Sonra Troy yıkıldı."),
            (3, "Truva'nın kalıntıları bulundu."),
            (4, "Ama Troy hâlâ tartışmalı."),
        )
        src = _s(**{
            "1": "The Troy siege began.", "2": "Then Troy fell.",
            "3": "The ruins of Troy were found.", "4": "But Troy is still disputed.",
        })
        result, n = gui._normalize_mixed_terms(blocks, src, "", "url", "model")
        self.assertEqual(result, blocks)
        self.assertEqual(n, 0)

    def test_rejects_wrong_case_suffix_and_accepts_harmonized_suffix(self):
        bad = gui._validate_term_normalize_candidate(
            "Troy'un kitabı", "Truva'na kitabı", [("Troy", "Truva")])
        good = gui._validate_term_normalize_candidate(
            "Troy'un kitabı", "Truva'nın kitabı", [("Troy", "Truva")])
        wrong_harmony = gui._validate_term_normalize_candidate(
            "Troy'un kitabı", "Truva'nin kitabı", [("Troy", "Truva")])
        self.assertEqual(bad, (False, "suffix_case_drift"))
        self.assertEqual(good, (True, ""))
        self.assertEqual(wrong_harmony, (False, "suffix_harmony"))

        repeated = gui._validate_term_normalize_candidate(
            "Troy'un kitabı Troy'a gitti.",
            "Truva'nın kitabı Truva'na gitti.", [("Troy", "Truva")])
        self.assertEqual(repeated, (False, "suffix_case_drift"))


if __name__ == "__main__":
    unittest.main()
