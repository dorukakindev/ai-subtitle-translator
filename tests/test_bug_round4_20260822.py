# -*- coding: utf-8 -*-
"""2026-08-22 dördüncü tur: dış denetimin 7 bulgusu + TM'nin yalnız-yazar olması.

Her bulgu gerçek dosyalara veya gerçek koşu loguna karşı ölçüldü; ölçüm
sonuçları ilgili sınıfın docstring'inde.
"""
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht
import provider_retry as pr
import subtitle_formats as sf
import subtitle_translator_gui as g


class TurkishSuffixValidatorTest(unittest.TestCase):
    """Madde 5/6: gövde + serbest harf dizisi çekim eki sanılıyordu."""

    INFLECTED = (
        ("Ada", "Ada"), ("Adaya", "Ada"), ("Adada", "Ada"), ("Adadan", "Ada"),
        ("Adanın", "Ada"), ("Adalar", "Ada"), ("Adaları", "Ada"),
        ("Ada'ya", "Ada"), ("Kediyi", "Kedi"), ("Kediler", "Kedi"),
        ("Kedinin", "Kedi"), ("Kedisi", "Kedi"), ("Marsta", "Mars"),
        ("Memoriesleri", "Memories"), ("Adasında", "Ada"),
    )
    DIFFERENT_WORD = (
        ("Adalet", "Ada"), ("Catalog", "Cat"), ("Ashley", "Ash"),
        ("Samanlık", "Sam"), ("Marshall", "Mars"), ("Benzin", "Ben"),
        ("Catherine", "Cat"), ("Adem", "Ada"), ("Sammy", "Sam"),
        ("Kedigiller", "Kedi"), ("Adamlar", "Ada"),
    )

    def test_real_inflections_are_accepted(self):
        for word, stem in self.INFLECTED:
            with self.subTest(word=word):
                self.assertTrue(sf.is_turkish_suffix_form(word, stem))

    def test_a_different_word_is_not_an_inflection(self):
        for word, stem in self.DIFFERENT_WORD:
            with self.subTest(word=word):
                self.assertFalse(sf.is_turkish_suffix_form(word, stem))

    def test_a_buffer_consonant_never_ends_a_suffix(self):
        # 'Ashley' = Ash + le + y. Kaynaştırma sonda duramaz.
        self.assertFalse(sf._tr_suffix_is_parsable("ley"))
        self.assertTrue(sf._tr_suffix_is_parsable("ya"))

    def test_a_buffer_consonant_needs_a_vowel_after_it(self):
        # 'Samanlık' = Sam + a + n + lık; 'n' ünsüzle devam edemez.
        self.assertFalse(sf._tr_suffix_is_parsable("anlık"))


class SeasonCanonSuffixTest(unittest.TestCase):
    """Madde 5: 'Adalet', 'Ada' kanonunun kullanımı sanılıyordu."""

    SRC = {"1": "The Island arrived."}
    CANON = {"Island": "Ada"}

    def test_a_different_word_no_longer_hides_the_violation(self):
        self.assertEqual(
            g._season_canon_suspect_ids(
                [("1", "ts", "Adalet geldi.")], self.SRC, self.CANON),
            {"1"})

    def test_the_canonical_form_is_still_accepted(self):
        for text in ("Ada geldi.", "Adaya gitti.", "Adanın kuzeyi."):
            with self.subTest(text=text):
                self.assertEqual(
                    g._season_canon_suspect_ids(
                        [("1", "ts", text)], self.SRC, self.CANON), set())


class LockedTermResiduePrefixTest(unittest.TestCase):
    """Madde 6: 'Catalog', kilitli 'Cat' teriminin kalıntısı sanılıyordu."""

    SRC = {"1": "The Cat is here."}
    LOCK = {"Cat": "Kedi"}

    def test_a_word_that_merely_starts_with_the_term_is_not_residue(self):
        self.assertEqual(
            g._locked_term_residue_plan(
                [("1", "ts", "Catalog burada.")], self.SRC, self.LOCK), {})

    def test_real_residue_is_still_planned(self):
        self.assertEqual(
            g._locked_term_residue_plan(
                [("1", "ts", "Cat burada.")], self.SRC, self.LOCK),
            {"1": [("Cat", "Kedi")]})


class BareGerundSdhTest(unittest.TestCase):
    """Madde 2: '... speaking/talking' kalıbı gerçek diyaloğu yutuyordu.

    192 gerçek kaynak dosyada (141.676 cue) çıplak biçim 21 ayrı satır
    yakaladı, 20'si düz replikti. Düzeltmeden sonra işaretlenen satır
    186 -> 164; köşeli parantezli gerçek etiketlerin hepsi korundu.
    """

    DIALOGUE = (
        "So start talking.",
        "objectively speaking.",
        "We're usually talking in terms of death...",
        "Then everyone started talking...",
        "and chanting and talking.",
        "while I'm talking!",
        "In a manner of speaking.",
        "Would you mind just talking",
    )
    REAL_SDH = (
        "[MAN SPEAKING ARABIC]",
        "[PEOPLE TALKING]",
        "[LAWRENCE TALKING INDISTINCTLY]",
        "[Laughing and chatting]",
        "[women speaking in tongues]",
        "( tourists bargaining )",
    )

    def test_dialogue_is_not_sdh(self):
        for text in self.DIALOGUE:
            with self.subTest(text=text):
                self.assertFalse(g._is_delivery_sdh_only(text))

    def test_bracketed_labels_are_still_sdh(self):
        for text in self.REAL_SDH:
            with self.subTest(text=text):
                self.assertTrue(g._is_delivery_sdh_only(text))

    def test_a_closed_speaker_prefix_works_without_brackets(self):
        self.assertTrue(g._is_delivery_sdh_only("men speaking quietly"))
        self.assertTrue(g._is_delivery_sdh_only("people talking at once"))

    def test_an_empty_translation_is_marked_not_dropped(self):
        # Kaynak "kaldırılabilir" sayıldığında boş çeviri SESSİZCE düşüyordu.
        blocks = [("1", "00:00:01,000 --> 00:00:03,000", ""),
                  ("2", "00:00:04,000 --> 00:00:06,000", "Merhaba.")]
        cues = [("1", "00:00:01,000 --> 00:00:03,000", "So start talking."),
                ("2", "00:00:04,000 --> 00:00:06,000", "Hello.")]
        out = g._prepare_upload_ready_blocks(blocks, "Turkish", None, cues)
        final = out[0] if isinstance(out, tuple) else out
        self.assertIn("[ÇEVİRİ EKSİK]", [text for _i, _ts, text in final])


class RoleSwapGuardTest(unittest.TestCase):
    """Madde 1: özne ile nesne yer değiştirse de aday kabul ediliyordu."""

    SWAPS = (
        ("Doktor hastayı kurtardı.", "Hasta doktoru kurtardı."),
        ("Ayşe Ali'yi aradı.", "Ali Ayşe'yi aradı."),
        ("Köpek kediyi ısırdı.", "Kedi köpeği ısırdı."),
        ("Adam çocuğu gördü.", "Çocuk adamı gördü."),
        ("Polis hırsızı yakaladı.", "Hırsız polisi yakaladı."),
    )
    LEGITIMATE = (
        ("Doktor hastayı kurtardı.", "Doktor hastayı iyileştirdi."),
        ("Doktor hastayı kurtardı.", "Hekim hastayı kurtardı."),
        ("Kopegi gordum.", "Köpeği gördüm."),
        ("Adam eve gitti.", "Adam eve yürüdü."),
        ("Kitabı masaya koydum.", "Kitabı masanın üstüne koydum."),
        ("Onu görmedim.", "Onu hiç görmedim."),
        ("Çocuk topu attı.", "Çocuk topu fırlattı."),
        ("Seni bekliyorum.", "Seni bekliyordum."),
    )

    def test_a_swap_is_detected(self):
        for old, new in self.SWAPS:
            with self.subTest(old=old):
                self.assertTrue(ht._has_role_swap(old, new))

    def test_an_ordinary_improvement_is_not_a_swap(self):
        for old, new in self.LEGITIMATE:
            with self.subTest(old=old):
                self.assertFalse(ht._has_role_swap(old, new))

    def test_consonant_softening_does_not_hide_half_the_pair(self):
        # 'köpek' -> 'köpeği' gövdesi 'köpeğ'; sert gövde anahtarı birleştirir.
        self.assertTrue(ht._has_role_swap(
            "Köpek kediyi ısırdı.", "Kedi köpeği ısırdı."))

    def test_polish_and_condense_both_reject_it(self):
        for validate in (ht.validate_polish_candidate,
                         ht.validate_condense_candidate):
            with self.subTest(validate=validate.__name__):
                ok, reason = validate(
                    "Doktor hastayı kurtardı.", "Hasta doktoru kurtardı.",
                    source_text="The doctor saved the patient.",
                    tgt_lang="Turkish")
                self.assertFalse(ok)
                self.assertEqual(reason, "role_swap")

    def test_semantic_pass_may_still_repair_a_wrong_role(self):
        # O pass'in İŞİ kaynaktan yeniden çevirmek; düz ret onu da keserdi.
        self.assertIn("role_swap", ht._SEMANTIC_REWRITE_REJECTIONS)


class ShuaiRouteRotationTest(unittest.TestCase):
    """Rota yarışı yalnız ilk denemede yapılıyordu.

    Gerçek koşu (2026-08-22 22:36-22:46): 11 denemenin hepsi
    api.shuaiapi.com'a gitti, diğer üç rota bir daha hiç sorulmadı.
    """

    class FakeClient:
        def __init__(self, base_url):
            self.base_url = base_url

        def with_options(self, base_url=None, max_retries=None):
            return ShuaiRouteRotationTest.FakeClient(base_url)

    PRIMARY = "https://api.shuaiapi.com/v1"
    CTX = {"checkpoint_label": "main_translation_x"}

    def setUp(self):
        pr.reset_shuai_route_metrics()
        pr.configure_shuai_route_failover(
            enabled=True, preferred_url=self.PRIMARY,
            main_preferred_url=self.PRIMARY)
        self.addCleanup(pr.reset_shuai_route_metrics)
        self.addCleanup(pr.configure_shuai_route_failover, False)

    def _cool(self, *routes):
        for route in routes:
            pr._SHUAI_ROUTE_STATES[route]["cooldown_until"] = (
                time.monotonic() + 60)

    def test_a_healthy_route_is_left_alone(self):
        client = self.FakeClient(self.PRIMARY)
        self.assertIs(pr._rotated_route_client(client, self.CTX), client)

    def test_a_cooling_route_is_replaced_mid_ladder(self):
        self._cool(self.PRIMARY)
        rotated = pr._rotated_route_client(self.FakeClient(self.PRIMARY),
                                           self.CTX)
        self.assertNotEqual(rotated.base_url, self.PRIMARY)

    def test_it_keeps_the_current_route_when_every_route_is_cooling(self):
        self._cool(*[url for _label, url in pr.SHUAI_API_ROUTE_OPTIONS])
        rotated = pr._rotated_route_client(self.FakeClient(self.PRIMARY),
                                           self.CTX)
        self.assertEqual(rotated.base_url, self.PRIMARY)

    def test_a_non_shuai_client_is_untouched(self):
        client = self.FakeClient("https://api.openai.com/v1")
        self.assertIs(pr._rotated_route_client(client, self.CTX), client)

    def test_nothing_rotates_when_failover_is_off(self):
        pr.configure_shuai_route_failover(enabled=False)
        self._cool(self.PRIMARY)
        client = self.FakeClient(self.PRIMARY)
        self.assertIs(pr._rotated_route_client(client, self.CTX), client)

    def test_the_ladder_call_goes_through_the_rotator(self):
        import inspect
        source = inspect.getsource(pr._chat_create_once)
        self.assertIn("_rotated_route_client(", source)


class DeepScanCoverageTest(unittest.TestCase):
    """Madde 4: kapsam sayacı sahne kırpmasını görmüyordu.

    60 gerçek kaynak/teslim çiftinde "Tam (%100)" ayarı %80-96 arasında
    kalıyordu (60/60 hedefin altında). Düzeltmeden sonra 60/60 tutuyor;
    varsayılan "Ekonomik (%35)" iki durumda da %79,2 — maliyet değişmiyor.
    """

    def test_the_counter_and_the_cluster_use_one_scene_layout(self):
        import inspect
        builder = inspect.getsource(ht.build_semantic_reconciliation_clusters)
        adaptive = inspect.getsource(ht._adaptive_semantic_suspects)
        self.assertIn("_scene_layout(", builder)
        self.assertIn("_scene_layout(", adaptive)

    def test_scene_layout_bounds_each_scene(self):
        class Cue:
            def __init__(self, start, end):
                self.start, self.end = start, end

        cues = [Cue("00:00:00,000", "00:00:01,000"),
                Cue("00:00:02,000", "00:00:03,000"),
                Cue("00:01:00,000", "00:01:01,000")]
        scene_by_pos, bounds = ht._scene_layout(cues, 10.0)
        self.assertEqual(scene_by_pos, [0, 0, 1])
        self.assertEqual(bounds[0], [0, 1])
        self.assertEqual(bounds[1], [2, 2])

    def test_empty_cues_do_not_crash(self):
        self.assertEqual(ht._scene_layout([], 2.0), ([], {}))


class TranslationMemoryReadPathTest(unittest.TestCase):
    """TM dört akışta da YAZILIYOR, yalnız birinde okunuyordu.

    Gerçek veritabanı: 494.907 satır, bütün ceviri_raporu.txt kayıtlarında
    ömür boyu ~58 isabet (22 dosya kaydının 20'sinde sıfır). `_run_sync`
    Yardımcı Analiz açıkken ilk satırda `_run_sync_hybrid`'e devredip
    dönüyor, TM doldurma kodu o `return`'ün ALTINDA kalıyordu.
    """

    @staticmethod
    def _req(cid, items):
        body = {"messages": [{"role": "system", "content": ""},
                             {"role": "user",
                              "content": json.dumps({"tr": items})}]}
        return {"custom_id": cid, "body": body}

    class FakeTM:
        def __init__(self, rows):
            self.rows = rows

        def lookup_batch(self, sources, **kwargs):
            return {s: self.rows[s] for s in sources if s in self.rows}

    def setUp(self):
        self.requests = [
            self._req("c1", [{"i": "1", "t": "Hello."},
                             {"i": "2", "t": "Bye."}]),
            self._req("c2", [{"i": "3", "t": "Missing."},
                             {"i": "4", "t": "Bye."}]),
        ]
        self.tm = self.FakeTM({"Hello.": "Merhaba.", "Bye.": "Hoşça kal."})

    def test_a_fully_cached_chunk_is_prefilled(self):
        filled = g._tm_prefill_chunks(self.tm, self.requests, "fp")
        self.assertEqual(sorted(filled), ["c1"])
        self.assertEqual(
            json.loads(filled["c1"]),
            [{"i": "1", "t": "Merhaba."}, {"i": "2", "t": "Hoşça kal."}])

    def test_a_partially_cached_chunk_still_goes_to_the_api(self):
        self.assertNotIn(
            "c2", g._tm_prefill_chunks(self.tm, self.requests, "fp"))

    def test_no_fingerprint_means_no_prefill(self):
        self.assertEqual(g._tm_prefill_chunks(self.tm, self.requests, ""), {})

    def test_a_missing_memory_is_not_an_error(self):
        self.assertEqual(g._tm_prefill_chunks(None, self.requests, "fp"), {})

    def test_the_hybrid_flow_now_reads_the_memory(self):
        import inspect
        source = inspect.getsource(g.App._run_sync_hybrid)
        self.assertIn("_tm_prefill_chunks(", source)


class TmFingerprintReproducibilityTest(unittest.TestCase):
    """Madde 7 + kayıt/arama uyuşmazlığı.

    Kayıt GENİŞ sözlüğü (şema + ANALİZ + dosya), arama DAR sözlüğü
    kullanıyordu; ikisi hiçbir zaman eşleşemezdi. Analizin katkısı artık
    ayrı bir kanonik bağlam anahtarında.
    """

    HASH = "abc123"
    NARROW = {"Oracle": "Kahin"}

    def _fp(self, context):
        return g._tm_context_fingerprint(self.HASH, self.NARROW, context)

    def test_an_empty_analysis_keeps_the_old_fingerprint(self):
        self.assertEqual(g._analysis_prompt_fingerprint(None, None, None), "")
        self.assertEqual(self._fp({"analysis": ""}), self._fp({}))

    def test_the_same_analysis_reproduces_the_same_key(self):
        first = g._analysis_prompt_fingerprint(
            {"Alice-Bob": "sen"}, {"Alice": "formal"}, {"Vessel": "Kap"})
        second = g._analysis_prompt_fingerprint(
            {"Alice-Bob": "sen"}, {"Alice": "formal"}, {"Vessel": "Kap"})
        self.assertTrue(first)
        self.assertEqual(self._fp({"analysis": first}),
                         self._fp({"analysis": second}))

    def test_a_different_pronoun_decision_changes_the_key(self):
        sen = g._analysis_prompt_fingerprint({"Alice-Bob": "sen"}, {}, {})
        siz = g._analysis_prompt_fingerprint({"Alice-Bob": "siz"}, {}, {})
        self.assertNotEqual(self._fp({"analysis": sen}),
                            self._fp({"analysis": siz}))

    def test_a_different_character_style_changes_the_key(self):
        formal = g._analysis_prompt_fingerprint({}, {"Alice": "formal"}, {})
        casual = g._analysis_prompt_fingerprint({}, {"Alice": "casual"}, {})
        self.assertNotEqual(self._fp({"analysis": formal}),
                            self._fp({"analysis": casual}))

    def test_resume_reuses_the_stored_fingerprint(self):
        import inspect
        source = inspect.getsource(g.App._wait_batch_hybrid)
        self.assertIn("context_fingerprint=(", source)
        self.assertIn("tm_context_fingerprint", source)

    def test_submit_persists_the_fingerprint_for_resume(self):
        import inspect
        self.assertIn(
            "tm_context_fingerprint",
            inspect.signature(ht.submit_batch).parameters)
        self.assertIn('"tm_context_fingerprint"',
                      inspect.getsource(ht.submit_batch))


class ManualPostProcessLockedTermsTest(unittest.TestCase):
    """Madde 3: manuel post-işlem kilitli terimleri hiçbir pass'e vermiyordu."""

    def test_delivery_prep_honours_the_locked_term(self):
        cues = [("1", "00:00:01,000 --> 00:00:03,000", "Mr. Blake arrived.")]
        blocks = [("1", "00:00:01,000 --> 00:00:03,000", "Mr. Blake geldi.")]
        without = g._prepare_upload_ready_blocks(blocks, "Turkish", None, cues)
        with_lock = g._prepare_upload_ready_blocks(
            blocks, "Turkish", None, cues,
            locked_terms={"Mr. Blake": "Mr. Blake"})
        texts = lambda out: [
            t for _i, _ts, t in (out[0] if isinstance(out, tuple) else out)]
        self.assertIn("Bay Blake geldi.", texts(without))
        self.assertIn("Mr. Blake geldi.", texts(with_lock))

    def test_every_pass_receives_the_same_dict(self):
        import inspect
        source = inspect.getsource(g.App._run_post_process)
        self.assertIn("_pp_locked_terms = self._get_locked_terms_dict(fp, tgt)",
                      source)
        self.assertIn("glossary=_pp_locked_terms", source)
        self.assertIn("locked_terms=_pp_locked_terms", source)
        self.assertNotIn("glossary=None,", source)


if __name__ == "__main__":
    unittest.main()
