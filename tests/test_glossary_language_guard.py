"""
Sözlük hedef-dil guard'ı: denylist → sözlük-seviyesi reddi.

Bkz. plans/sozluk-hedef-dil-guard-brief.md — The Blood of Hussain (2026-07-16)
olayı: analiz geçişinin ürettiği 13 terimlik sözlük Somalice çıktı, ana model
sözlüğe sadık kalarak hatayı tüm dosyaya yaydı. Mevcut guard (non_turkish_leak_token)
bir DENYLIST'ti — yalnızca bilinen yabancı script/Turkic-drift-kelime-listesi/
Latin-extended-diakritik arıyordu; saf-Latin, kelime-listesi-dışı, diakritiksiz
Somalice'yi ("madaxweynaha", "Bangiga Adduunka") yapısal olarak göremiyordu.

Bu testler:
  - yeni R_wqx sinyalini (Türkçe'de q/w/x yok) kilitler,
  - sözlük-seviyesi reddi kilitler (bir terim açıkça yabancıysa TÜM sözlük atılır —
    "Bangiga Adduunka" ve "mu'addinka" gibi tekil kuralları tetiklemeyen terimler
    de bu sayede gider — asıl kazanç budur),
  - precontext yolunun (Yardımcı Analiz KAPALIYKEN) artık sanitize edildiğini
    kilitler (KRİTİK BOŞLUK — eskiden hiç sanitize edilmiyordu),
  - target_language="tr" DIŞINDA guard'ın devre dışı kaldığını kilitler.
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

import hybrid_translate as ht


class WqxTargetGuardTest(unittest.TestCase):
    def test_wqx_target_rejected(self):
        cleaned = ht.sanitize_glossary_for_turkish({
            "Armed Forces": "Qawweyaha Xoogga Dalka / ciidamada qalabka sida",
        })
        self.assertEqual(cleaned, {})

    def test_lowercase_wqx_rejected(self):
        cleaned = ht.sanitize_glossary_for_turkish({"President": "madaxweynaha"})
        self.assertEqual(cleaned, {})

    def test_single_word_proper_noun_kept(self):
        cleaned = ht.sanitize_glossary_for_turkish({"Washington": "Washington"})
        self.assertEqual(cleaned, {"Washington": "Washington"})

    def test_whole_glossary_dropped_on_one_leak(self):
        # Gerçek olay: The Blood of Hussain analiz sözlüğü (bkz. brief).
        dirty = {
            "Armed Forces": "Qawweyaha Xoogga Dalka / ciidamada qalabka sida",
            "President": "madaxweynaha",
            "World Bank": "Bangiga Adduunka",      # hiçbir tekil kural tetiklenmiyor
            "Muezzin": "mu'addinka",                # hiçbir tekil kural tetiklenmiyor
            "Karbala": "Kerbela",                   # tertemiz bir terim
        }
        cleaned = ht.sanitize_glossary_for_turkish(dirty)
        self.assertEqual(cleaned, {})
        # Asıl kazanç: bireysel olarak "temiz görünen" terimler de gider.
        self.assertNotIn("World Bank", cleaned)
        self.assertNotIn("Muezzin", cleaned)
        self.assertNotIn("Karbala", cleaned)

    def test_clean_turkish_glossary_untouched(self):
        clean = {"Armed Forces": "Silahlı Kuvvetler"}
        self.assertEqual(ht.sanitize_glossary_for_turkish(clean), clean)

    def test_ascii_turkish_target_kept(self):
        clean = {"church": "kilise"}
        self.assertEqual(ht.sanitize_glossary_for_turkish(clean), clean)

    def test_non_turkish_target_language_skips_guard(self):
        dirty = {"Armed Forces": "Qawweyaha Xoogga Dalka"}
        cleaned = ht.sanitize_glossary_for_turkish(dirty, target_language="de")
        self.assertEqual(cleaned, dirty)

    def test_single_bad_term_does_not_drop_whole_glossary_via_older_rules(self):
        """Regresyon koruması: whole-glossary-drop SADECE R_wqx'e bağlı olmalı.
        Turkic-drift-listesi gibi eski 3 kural hâlâ SADECE o terimi düşürür —
        tests/test_source_language_leftover.py:155 ile aynı sözleşme."""
        cleaned = ht.sanitize_glossary_for_turkish({
            "holiday party": "bäýram/holidaý oturylyşyğı",  # Turkic-drift ile düşer
            "taxidermy": "taksidermi",                        # temiz, kalmalı
        })
        self.assertEqual(cleaned, {"taxidermy": "taksidermi"})


class GlossaryGlossOrInstructionGuardTest(unittest.TestCase):
    """bkz. plans/sozluk-gloss-ve-half-sayi-brief.md — Ishanou/Salome/Blood of
    Hussain'de üst üste görülen ayrı sınıf: analiz geçişi hedefe ÇEVİRİ değil
    META-YORUM yazıyor ('Caesar (Sezar)', 'Bembem (özel ad, aynen korunacak)',
    'görümce / yenge bağlama göre'). Bugün eklenen q/w/x guard'ı bunu görmüyordu
    çünkü hiçbirinde q/w/x yok.

    POLİTİKA AYRIMI (en kritik nokta, KARIŞTIRILMASIN):
      - R_wqx (mevcut): TÜM sözlüğü atar -- toplu dil çökmesi sinyali.
      - Bu guard (yeni): YALNIZCA o terimi atar -- model Türkçe üretmiş, sadece
        karar verememiş; diğer terimler sağlam kalabilir.
    """

    def test_paren_gloss_target_dropped(self):
        cleaned = ht.sanitize_glossary_for_turkish({"Caesar": "Caesar (Sezar)"})
        self.assertEqual(cleaned, {})

    def test_instruction_target_dropped(self):
        cleaned = ht.sanitize_glossary_for_turkish({
            "Bembem": "Bembem (özel ad, aynen korunacak)",
        })
        self.assertEqual(cleaned, {})

    def test_slash_options_target_dropped(self):
        cleaned = ht.sanitize_glossary_for_turkish({
            "sister-in-law": "görümce / yenge bağlama göre",
        })
        self.assertEqual(cleaned, {})

    def test_bracket_target_dropped(self):
        cleaned = ht.sanitize_glossary_for_turkish({"X": "Y [açıklama]"})
        self.assertEqual(cleaned, {})

    def test_clean_terms_survive_alongside(self):
        # POLİTİKA TESTİ: bir terim gloss nedeniyle atılırken TÜM sözlük atılmamalı.
        cleaned = ht.sanitize_glossary_for_turkish({
            "Caesar": "Caesar (Sezar)",
            "Armed Forces": "Silahlı Kuvvetler",
        })
        self.assertEqual(cleaned, {"Armed Forces": "Silahlı Kuvvetler"})

    def test_tight_slash_not_dropped(self):
        # Boşluksuz eğik çizgi (gerçek terim) elenmemeli.
        cleaned = ht.sanitize_glossary_for_turkish({"band": "AC/DC"})
        self.assertEqual(cleaned, {"band": "AC/DC"})

    def test_wqx_still_drops_whole_glossary(self):
        # Eski politika (R_wqx) bozulmamalı: Somalice + eğik-çizgi aynı terimde
        # birlikte olsa bile TÜM sözlük atılmalı (whole-glossary-drop kazanır).
        dirty = {
            "Armed Forces": "Qawweyaha Xoogga Dalka / ciidamada qalabka sida",
            "President": "madaxweynaha",
            "Karbala": "Kerbela",
        }
        self.assertEqual(ht.sanitize_glossary_for_turkish(dirty), {})


class PrecontextGlossaryGuardTest(unittest.TestCase):
    """KRİTİK BOŞLUK (Adım 3): precontext yolu (Yardımcı Analiz KAPALIYKEN) eskiden
    hiç sanitize edilmiyordu."""

    def test_precontext_terms_sanitized(self):
        import subtitle_translator_gui as gui
        data = {
            "summary": "x",
            "terms": {
                "Armed Forces": "Qawweyaha Xoogga Dalka / ciidamada qalabka sida",
                "Karbala": "Kerbela",
            },
        }
        hint = gui.build_precontext_hint(data)
        self.assertNotIn("Qawweyaha", hint)
        self.assertNotIn("Kerbela", hint)  # whole-glossary-drop: temiz terim de gider

    def test_precontext_terms_untouched_when_clean(self):
        import subtitle_translator_gui as gui
        data = {"terms": {"the Precinct": "Karakol"}}
        hint = gui.build_precontext_hint(data)
        self.assertIn("'the Precinct' → 'Karakol'", hint)

    def test_sanitize_precontext_data_does_not_mutate_caller_dict(self):
        import subtitle_translator_gui as gui
        data = {"terms": {"President": "madaxweynaha"}}
        gui.build_precontext_hint(data)
        # build_precontext_hint kendi kopyası üzerinde çalışmalı — orijinal `data`
        # (örn. data_by_fp / series_memory tarafından ayrıca kullanılan) bozulmamalı.
        self.assertEqual(data["terms"], {"President": "madaxweynaha"})


class SeriesMemoryGlossaryGuardTest(unittest.TestCase):
    """Adım 3.3 — en tehlikeli boşluk: precontext'ten series_memory'ye sanitize
    edilmeden kalıcılaştırılıyordu (zehir diziler arası taşınır)."""

    @classmethod
    def setUpClass(cls):
        if importlib.util.find_spec("customtkinter") is None:
            raise unittest.SkipTest("customtkinter yüklü değil; GUI testi atlandı")
        import subtitle_translator_gui as gui
        from tests._gui_app import make_app
        cls.app = make_app(gui)  # açılıştaki yarım-batch penceresi kapalı (bkz. _gui_app)
        cls.app.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def test_series_memory_not_poisoned(self):
        with tempfile.TemporaryDirectory() as td:
            fp = str(Path(td) / "Show.S01E01.srt")
            Path(fp).write_text("1\n00:00:01,000 --> 00:00:02,000\nHello.\n", encoding="utf-8")
            self.app.series_memory_var.set(True)
            self.app.input_var.set(td)
            data = {
                "terms": {
                    "Armed Forces": "Qawweyaha Xoogga Dalka",
                    "Karbala": "Kerbela",
                },
            }
            self.app._update_series_memory_from_precontext(fp, data, target_language="tr")
            sm_obj, _season, _ep = self.app._series_mem_for(fp)
            self.assertIsNotNone(sm_obj)
            self.assertNotIn("Armed Forces", sm_obj._data["terms"])
            self.assertNotIn("Karbala", sm_obj._data["terms"])  # whole-glossary-drop


if __name__ == "__main__":
    unittest.main()
