"""detect_mixed_term_renderings (subtitle_translator_gui.py) — Görev 3,
future-quality-guards-brief.md: aynı özel ismin dosya içinde tutarsız
çevrildiğini (ör. İnka* vs Incas*) deterministik olarak tespit eder.

DÜRÜSTLÜK NOTU: brief'in kanıt bölümünde "Incas'ı ↔ İnkaların (Explorer 1'de,
ikisi de var)" iddiası vardı — gerçek-dosya doğrulaması sırasında bu YANLIŞ
çıktı (Explorer 1'de "Incas" 28 kez geçiyor, TÜMÜ tutarlı biçimde "İnka/İnkalar"
çevrilmiş, karışıklık yok). Fonksiyon gerçek dosyalarda (Explorer 1&2, düzeltilmiş
Göbekli 1&2) doğru şekilde 0 bulgu veriyor (doğru-negatif) — bu dosyadaki
sentetik testler fonksiyonun GERÇEKTEN çalıştığını (karışıklık VARSA yakaladığını)
kanıtlar.
"""
import unittest

import subtitle_translator_gui as gui


def _b(*rows):
    return [(str(i), "00:00:01,000 --> 00:00:02,000", t) for i, t in rows]


def _s(**kw):
    return {str(k): v for k, v in kw.items()}


class MixedTermDetectionTest(unittest.TestCase):
    def test_consistently_mixed_term_detected(self):
        # Kaynakta "Incas" 5 kez, cümle-ortasında geçiyor; çeviri YARI YARIYA
        # İnka*/Incas* arasında bölünmüş — gerçek karışıklık, tespit edilmeli.
        blocks = _b(
            (1, "İnkalar bunu inşa etti."),
            (2, "Sonra İnkalar ayrıldı."),
            (3, "Ama Incas geri döndü."),
            (4, "Sonunda Incas kayboldu."),
            (5, "Böylece İnkaların hikâyesi bitti."),
        )
        src = _s(**{
            "1": "The Incas built this.",
            "2": "Later the Incas left.",
            "3": "But the Incas returned.",
            "4": "Finally the Incas vanished.",
            "5": "Thus the Incas' story ended.",
        })
        findings = gui.detect_mixed_term_renderings(blocks, src)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["term"], "Incas")
        renderings = findings[0]["renderings"]
        self.assertEqual(len(renderings), 2)
        self.assertEqual(sum(renderings.values()), 5)

    def test_consistently_single_rendering_not_flagged(self):
        # Aynı senaryo ama HEP "İnkalar" — tutarlı, TETİKLEMEMELİ.
        blocks = _b(
            (1, "İnkalar bunu inşa etti."),
            (2, "Sonra İnkalar ayrıldı."),
            (3, "Ama İnkalar geri döndü."),
            (4, "Sonunda İnkalar kayboldu."),
            (5, "Böylece İnkaların hikâyesi bitti."),
        )
        src = _s(**{
            "1": "The Incas built this.",
            "2": "Later the Incas left.",
            "3": "But the Incas returned.",
            "4": "Finally the Incas vanished.",
            "5": "Thus the Incas' story ended.",
        })
        self.assertEqual(gui.detect_mixed_term_renderings(blocks, src), [])

    def test_below_frequency_threshold_not_flagged(self):
        # Yalnızca 2 geçiş (eşik ≥3) — TETİKLEMEMELİ.
        blocks = _b((1, "İnkalar bunu inşa etti."), (2, "Ama Incas geri döndü."))
        src = _s(**{"1": "The Incas built this.", "2": "But the Incas returned."})
        self.assertEqual(gui.detect_mixed_term_renderings(blocks, src), [])

    def test_sentence_initial_only_not_flagged(self):
        # Terim HER ZAMAN cümle/cue BAŞINDA — cümle-ortası kanıtı yok,
        # TETİKLEMEMELİ (başlık/konuşmacı-adı gibi yanlış-pozitif riskini azaltır).
        blocks = _b(
            (1, "İnkalar bunu inşa etti."),
            (2, "Incas ayrıldı."),
            (3, "İnkalar geri döndü."),
        )
        src = _s(**{"1": "Incas built this.", "2": "Incas left.", "3": "Incas returned."})
        self.assertEqual(gui.detect_mixed_term_renderings(blocks, src), [])

    def test_single_example_cluster_not_flagged(self):
        # Bir küme yalnızca 1 örnekse (≥2 şart) — o küme sayılmaz, tek küme kalırsa
        # TETİKLEMEMELİ (5 tutarlı İnka* + 1 tekil Incas* → gerçek küme sayısı 1).
        blocks = _b(
            (1, "İnkalar bunu inşa etti."),
            (2, "Sonra İnkalar ayrıldı."),
            (3, "Ama İnkalar geri döndü."),
            (4, "Sonunda İnkalar kayboldu."),
            (5, "Böylece Incas'ın hikâyesi bitti."),
        )
        src = _s(**{
            "1": "The Incas built this.",
            "2": "Later the Incas left.",
            "3": "But the Incas returned.",
            "4": "Finally the Incas vanished.",
            "5": "Thus the Incas' story ended.",
        })
        self.assertEqual(gui.detect_mixed_term_renderings(blocks, src), [])

    def test_neighbor_tolerance_finds_term_in_adjacent_cue(self):
        # Terim kaynakta cue #2'de ama SOV dağıtımıyla çeviri #1 veya #3'e
        # kaymış olabilir — ±1 tolerans bunu bulmalı. Çeviri TUTARLI (hep
        # İnkalar/İnkaların, hiç "Incas" aynen bırakılmamış) — TEK kümeye
        # düşmeli, TETİKLEMEMELİ (asıl amaç: tutarlı-ama-dağınık-konumlu terim
        # yanlış-pozitif üretmesin).
        blocks = _b(
            (1, "İnkaların yaptığı,"),
            (2, "burada."),
            (3, "Sonra İnkalar ayrıldı."),
            (4, "İnkaların bıraktığı,"),
            (5, "buradaydı."),
            (6, "Ama İnkalar döndü."),
            (7, "İnkaların"),
            (8, "hikâyesi sürdü."),
        )
        src = _s(**{
            "1": "The Incas built,", "2": "here.",
            "3": "Later the Incas left.",
            "4": "The Incas left,", "5": "there.",
            "6": "But the Incas returned.",
            "7": "The Incas'", "8": "story continued.",
        })
        self.assertEqual(gui.detect_mixed_term_renderings(blocks, src), [])

    def test_all_caps_source_function_words_not_terms(self):
        blocks = _b(
            (1, "Bu epey ilginç."),
            (2, "Sanırım bunu beğeneceksin."),
            (3, "Evet, elimizde var."),
            (4, "Bakmakta fayda var."),
            (5, "Tabii, böyle olabilir."),
        )
        src = _s(**{
            "1": "WE HAVE THIS.",
            "2": "I THINK YOU WILL LIKE THIS.",
            "3": "SURE, WE HAVE THAT.",
            "4": "TAKE A LOOK AT THIS.",
            "5": "THIS IS WHAT THEY WANT.",
        })
        self.assertEqual(gui.detect_mixed_term_renderings(blocks, src), [])

    def test_all_caps_look_and_contraction_fragments_not_terms(self):
        blocks = _b(
            (1, "Biraz bakınıyorum."),
            (2, "Bunu henüz yapmadım."),
            (3, "Dükkâna bakıyorum."),
            (4, "Bunu daha önce yapmadım."),
        )
        src = _s(**{
            "1": "I AM LOOKING AT THIS.",
            "2": "I HAVEN'T DONE THIS.",
            "3": "HE LOOKS AT THIS.",
            "4": "WE HAVEN'T SEEN THAT.",
        })
        self.assertEqual(gui.detect_mixed_term_renderings(blocks, src), [])

    def test_all_caps_source_ordinary_words_not_in_stoplist_not_terms(self):
        # Gerçek olay (Oddities S05E06, 2026-07-20): kaynağın %99'u ALL-CAPS
        # closed-caption stiliydi. "YEAH"/"RIGHT"/"COOL"/"ABSOLUTELY" gibi 27
        # sıradan kelime (mevcut stop-word listesinde OLMAYAN) "hep büyük harf,
        # hiç küçük harf görülmedi" diye özel-isim sanılıp 27 ayrı yanlış-alarm
        # üretti (ör. "COOL" -> "Daddy×3" -- bir karakterin lakabı, çeviri bile
        # değil). ALL-CAPS bir satırda büyük/küçük harf ayrımı sinyal vermez.
        blocks = _b(
            (1, "Evet, bunu aldığımız şey."),
            (2, "Doğru, bunu biliyorum."),
            (3, "Kesinlikle harika bir şey."),
            (4, "Evet, çok soğuk görünüyor."),
            (5, "Sanırım muhtemelen doğru."),
        )
        src = _s(**{
            "1": "YEAH, THAT'S THE THING WE GOT.",
            "2": "RIGHT, I KNOW THAT.",
            "3": "ABSOLUTELY A COOL THING.",
            "4": "YEAH, THAT LOOKS REAL COOL.",
            "5": "I GUESS THAT'S PROBABLY RIGHT.",
        })
        self.assertEqual(gui.detect_mixed_term_renderings(blocks, src), [])

    def test_real_proper_noun_still_detected_when_file_mixes_caps_and_normal_case(self):
        # ALL-CAPS satırları göz ardı etmek gerçek bir tutarsızlığı GİZLEMEMELİ --
        # aynı özel isim normal-case satırlarda da yeterince (>=3, iki farklı
        # çeviri kümesinde >=2'şer) geçiyorsa bulgu hâlâ üretilmeli.
        blocks = _b(
            (1, "Bunu İnkalar yaptı."),
            (2, "SONRA BU ESER BULUNDU."),
            (3, "Sonra İnkalar ayrıldı."),
            (4, "Ama Incas geri döndü."),
            (5, "BU INSANLAR BUNU BILIYORDU."),
            (6, "Sonunda Incas kayboldu."),
        )
        src = _s(**{
            "1": "The Incas built this.",
            "2": "THEN THIS ARTIFACT WAS FOUND.",
            "3": "Later the Incas left.",
            "4": "But the Incas returned.",
            "5": "THESE PEOPLE KNEW THIS.",
            "6": "Finally the Incas vanished.",
        })
        findings = gui.detect_mixed_term_renderings(blocks, src)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["term"], "Incas")

    def test_same_cue_double_mention_not_double_counted(self):
        """Gerçek olay (Massacre in Rome, 2026-07-20): kaynak cue'da terim
        AYNI CUE içinde iki kez geçince ("Radio Rome... Rome One station"),
        her iki geçiş de aynı (yanlış) ilk-kelime fallback'ini ("Burası")
        seçip kendi kendini "2 örnekli küme" diye onaylıyordu. Bir cue, bir
        terim için en fazla BİR occurrence saymalı -- diğer 3 cue'da tutarlı
        "Roma" varken TETİKLEMEMELİ."""
        blocks = _b(
            (1, "Burası Roma Radyosu, Roma Bir istasyonu."),
            (2, "Roma bombalandı."),
            (3, "Roma yeniden inşa edildi."),
            (4, "Sonunda Roma kurtuldu."),
        )
        src = _s(**{
            "1": "This is Radio Rome, Rome One station.",
            "2": "Rome was bombed.",
            "3": "Rome was rebuilt.",
            "4": "Finally Rome was saved.",
        })
        self.assertEqual(gui.detect_mixed_term_renderings(blocks, src), [])

    def test_larger_established_cluster_preferred_over_sentence_position(self):
        """Gerçek olay (Massacre in Rome, 2026-07-20): 'Demek' (söylem sözcüğü,
        'So,') erken bir cue'da fallback ile yanlış küme kurunca, SONRAKİ bir
        cue'da hem 'Demek' hem de doğru/devasa 'Kale' kümesiyle eşleşen 'Y'
        birlikte geçince -- cümle sırasında ÖNCE gelen 'Demek' körlemesine
        kazanıyordu. Artık en büyük/en yerleşik kümeyle eşleşen kazanmalı."""
        blocks = _b(
            (1, "Demek kale bombalandı."),
            (2, "Kale yeniden yapıldı."),
            (3, "Kale hâlâ ayakta."),
            (4, "Sonunda Kale kurtarıldı."),
            (5, "Demek Kale hâlâ oradaydı."),
        )
        src = _s(**{
            "1": "So, the Castle was bombed.",
            "2": "The Castle was rebuilt.",
            "3": "The Castle still stands.",
            "4": "Finally the Castle was saved.",
            "5": "So, the Castle was still there.",
        })
        self.assertEqual(gui.detect_mixed_term_renderings(blocks, src), [])

    def test_phrase_component_term_excluded_from_candidacy(self):
        """Gerçek olay (Massacre in Rome, 2026-07-20): 'Command' hep 'German
        High Command'/'High Command' içinde bitişik başka bir büyük-harfli
        adayla ('High') birlikte geçiyordu -- hedefte 'Komutanlığı' hiçbir
        cue'da ilk sırada olmadığı için asla kendi kümesini kuramıyor, bunun
        yerine yanındaki sıfatlar ('Alman'/'Yüksek') rastgele küme
        oluşturuyordu. Kaynakta HEP bitişik büyük-harfli komşusu olan bir
        kelime aday listesinden çıkarılmalı."""
        blocks = _b(
            (1, "Alman Yüksek Komutanlığı bildiri yayınladı."),
            (2, "Yüksek Komutanlıkta isteniyorsunuz."),
            (3, "Bu durum Yüksek Komutanlığa bildirilmeli."),
            (4, "Berlin'i arayın, Alman Yüksek Komutanlığını."),
        )
        src = _s(**{
            "1": "The German High Command issued a communiqué.",
            "2": "You're requested at High Command.",
            "3": "This must be reported to the High Command.",
            "4": "Call Berlin, High Command.",
        })
        self.assertEqual(gui.detect_mixed_term_renderings(blocks, src), [])

    def test_second_sentence_in_merged_cue_not_mid_sentence_false_signal(self):
        """Gerçek olay (Indiana Jones belgeseli, 2026-07-20): 'Undskyld' (Danca
        'pardon', tekrar eden bir espri) çoğu cue'da ham kelime-pozisyonuna
        göre (wi>0, cue'nun İKİNCİ cümlesinin başı) yanlışlıkla mid-sentence
        sayılıyor, bu da sırf cümle-başı bir söz kalıbını (farklı Türkçe
        karşılıklarla -- Affedersin/Pardon/Özür -- çevrilmiş olsa bile) aday
        yapıyordu. Kendi cümlesinin/repliğin başında olan bir kelime, ham
        pozisyonu >0 olsa bile mid-sentence SAYILMAMALI -- burada 'Hello' HER
        cue'da kendi cümlesinin başında, TETİKLEMEMELİ (farklı render'lara
        rağmen)."""
        blocks = _b(
            (1, "Bir şey oldu. Merhaba dedi."),
            (2, "Başka bir şey oldu. Selam dedi."),
            (3, "Merhaba, dedi üçüncü kez."),
        )
        src = _s(**{
            "1": "Something happened. Hello he said.",
            "2": "Something else happened. Hello he said.",
            "3": "Hello, he said a third time.",
        })
        self.assertEqual(gui.detect_mixed_term_renderings(blocks, src), [])

    def test_transliterated_name_beats_unrelated_sentence_initial_word(self):
        blocks = _b(
            (1, "- Merhaba.\n- İçeri gir, Dmitri."),
            (2, "Kal Dmitri, nereye gidebiliriz?"),
            (3, "Merhaba, Dmitri."),
            (4, "Teşekkür ederim, Dmitri."),
        )
        src = _s(**{
            "1": "- Hello.\n- Go inside, Dmitry.",
            "2": "Stay Dmitry, where can we go?",
            "3": "Hello, Dmitry.",
            "4": "Thank you, Dmitry.",
        })
        self.assertEqual(gui.detect_mixed_term_renderings(blocks, src), [])

    def test_bracketed_narrator_label_not_a_mixed_term(self):
        blocks = _b(
            (1, "Josh bunu biliyordu."),
            (2, "Josh daha sonra ayrıldı."),
            (3, "Myspace bunu kabul etmedi."),
            (4, "Myspace sonunda satıldı."),
        )
        src = _s(**{
            "1": "- [Narrator] He knew this.",
            "2": r"{\an8}- [Narrator] He later left.",
            "3": "- [Narrator] It didn't accept this.",
            "4": "- [Narrator] It was eventually sold.",
        })
        self.assertEqual(gui.detect_mixed_term_renderings(blocks, src), [])

    def test_kinship_address_is_not_treated_as_proper_term(self):
        blocks = _b(
            (1, "- Timmy!\n- Baba!"),
            (2, "Hadi, bakalım babanın ne planladığını."),
            (3, "Babam bugün geliyor."),
            (4, "Hadi, babam bizi bekliyor."),
            (5, "Babacığım, burada mısın?"),
        )
        src = _s(**{
            "1": "- Timmy!\n- Daddy!",
            "2": "So, guess what Daddy's got planned?",
            "3": "Daddy is coming today.",
            "4": "Come on, Daddy is waiting for us.",
            "5": "Daddy, are you here?",
        })
        self.assertEqual(gui.detect_mixed_term_renderings(blocks, src), [])

    def test_empty_blocks_returns_empty(self):
        self.assertEqual(gui.detect_mixed_term_renderings([], {}), [])


class ScanIntegrationTest(unittest.TestCase):
    def test_scan_reports_mixed_term_warning(self):
        blocks = _b(
            (1, "İnkalar bunu inşa etti."),
            (2, "Sonra İnkalar ayrıldı."),
            (3, "Ama Incas geri döndü."),
            (4, "Sonunda Incas kayboldu."),
            (5, "Böylece İnkaların hikâyesi bitti."),
        )
        src = _s(**{
            "1": "The Incas built this.",
            "2": "Later the Incas left.",
            "3": "But the Incas returned.",
            "4": "Finally the Incas vanished.",
            "5": "Thus the Incas' story ended.",
        })
        logs = []
        gui.scan_translation_quality("dummy.srt", blocks,
                                     log_fn=lambda m, lvl=None: logs.append((m, lvl)),
                                     src_clean_map=src)
        self.assertTrue(any("karışık çevrilmiş" in m for m, _ in logs))


if __name__ == "__main__":
    unittest.main()
