"""
AI destekli akıllı segmentasyon testleri.

Tasarım sözleşmesi: AI YALNIZCA gruplama + satır kırma önerir; zamanlama (ilk başı →
son sonu) ve okuma hızı (CPS) DETERMİNİSTİK zorlanır, metin orijinal parçalardan kurulur.
AI metni yalnızca SADIK ise (kelime/noktalama birebir) kullanılır; aksi halde deterministik.
Aday yoksa / hata olursa hızlı merge_fragmented_cues'e düşülür (senkron her durumda korunur).

Ağ yok: model çağrısı (ht._safe_chat_create) ve OpenAI istemcisi sahteyle değiştirilir.
"""
import copy
import json
import types
import unittest

import subtitle_translator_gui as gui
import hybrid_translate as ht
from request_cancellation import RequestCancelled


def _fake_chat(response_obj=None, raise_exc=None):
    """ht._safe_chat_create yerine geçen sahte: verilen dict'i JSON içerik olarak döndürür."""
    def _fake(client, **kwargs):
        if raise_exc is not None:
            raise raise_exc
        content = json.dumps(response_obj or {}, ensure_ascii=False)
        msg = types.SimpleNamespace(content=content)
        choice = types.SimpleNamespace(message=msg)
        return types.SimpleNamespace(choices=[choice],
                                     usage=types.SimpleNamespace(total_tokens=42))
    return _fake


class _Patched:
    """ht._safe_chat_create + gui.OpenAI'yi geçici olarak sahteyle değiştiren bağlam yöneticisi."""
    def __init__(self, response_obj=None, raise_exc=None):
        self.fake = _fake_chat(response_obj, raise_exc)

    def __enter__(self):
        self._orig_chat = ht._safe_chat_create
        self._orig_openai = gui.OpenAI
        ht._safe_chat_create = self.fake
        gui.OpenAI = lambda **kw: object()
        return self

    def __exit__(self, *a):
        ht._safe_chat_create = self._orig_chat
        gui.OpenAI = self._orig_openai


# ── Saf yardımcılar ───────────────────────────────────────────────────────────
class NormAndJoinTest(unittest.TestCase):
    def test_norm_ignores_only_whitespace(self):
        # Sadece boşluk/newline sayısı önemsiz — kelimeler aynı kalmalı
        self.assertEqual(gui._norm_for_compare("Peki ne\nyapacaksın"),
                         gui._norm_for_compare("Peki  ne yapacaksın"))

    def test_norm_keeps_tags_case_braces_significant(self):
        # Etiket, harf büyüklüğü, parantez içeriği, kelime sınırı AYNEN korunur → farklı sayılır
        self.assertNotEqual(gui._norm_for_compare("<i>selam</i>"),
                            gui._norm_for_compare("selam"))                # etiket
        self.assertNotEqual(gui._norm_for_compare("{\\an8}selam"),
                            gui._norm_for_compare("{\\an2}selam"))         # konum etiketi
        self.assertNotEqual(gui._norm_for_compare("Igor"),
                            gui._norm_for_compare("igor"))                 # harf büyüklüğü
        self.assertNotEqual(gui._norm_for_compare("New York"),
                            gui._norm_for_compare("NewYork"))              # kelime yapıştırma

    def test_norm_detects_word_change(self):
        a = gui._norm_for_compare("ananla ne yapacaksın")
        b = gui._norm_for_compare("annenle ne yapacaksın")
        self.assertNotEqual(a, b)

    def test_join_drops_second_override_collapses_newline(self):
        out = gui._join_cue_texts(["{\\an8}Biliyorum,\nbabam ölenden beri", "{\\an8}işsizsin"])
        self.assertEqual(out, "{\\an8}Biliyorum, babam ölenden beri işsizsin")

    def test_join_collapses_italic_boundary(self):
        out = gui._join_cue_texts(["<i>devam eden</i>", "<i>cümle</i>"])
        self.assertNotIn("</i> <i>", out)


# ── Aday pencere tespiti ──────────────────────────────────────────────────────
class CandidatesTest(unittest.TestCase):
    def test_simple_fragment_run_is_one_window(self):
        b = [
            ("1", "00:00:05,706 --> 00:00:07,475", "Peki, ananla ne yapacaksın"),
            ("2", "00:00:07,475 --> 00:00:07,975", "ki?"),
            ("3", "00:00:14,715 --> 00:00:16,000", "Hurlan: Merhaba dostum."),
        ]
        self.assertEqual(gui._segmentation_candidates(b), [(0, 1)])

    def test_dialogue_breaks_window(self):
        b = [("1", "00:00:01,000 --> 00:00:02,000", "- Selam"),
             ("2", "00:00:02,000 --> 00:00:03,000", "- Naber")]
        self.assertEqual(gui._segmentation_candidates(b), [])

    def test_large_gap_breaks_window(self):
        b = [("1", "00:00:01,000 --> 00:00:02,000", "devam eden"),
             ("2", "00:00:05,000 --> 00:00:06,000", "cümle")]
        self.assertEqual(gui._segmentation_candidates(b), [])

    def test_all_sentence_ends_no_window(self):
        # Her cue tam cümle bitiriyor → 'devam' sınırı yok → pencere yok (token harcanmaz)
        b = [("1", "00:00:01,000 --> 00:00:02,000", "Bitti."),
             ("2", "00:00:02,000 --> 00:00:03,000", "Tamam.")]
        self.assertEqual(gui._segmentation_candidates(b), [])

    def test_window_capped_by_max_window(self):
        b = [(str(i + 1), f"00:00:0{i},000 --> 00:00:0{i},500", "parça")
             for i in range(6)]  # hepsi 0 boşluk, devam
        wins = gui._segmentation_candidates(b, max_window=3)
        # 6 cue, pencere başına en çok 3 → iki pencere
        self.assertEqual(wins, [(0, 2), (3, 5)])


# ── Deterministik zorlama ─────────────────────────────────────────────────────
class EnforceTest(unittest.TestCase):
    WIN = [("1", "00:00:05,706 --> 00:00:07,475", "Peki, ananla ne yapacaksın"),
           ("2", "00:00:07,475 --> 00:00:07,975", "ki?")]

    def test_faithful_ai_break_kept_timing_spans_window(self):
        groups = [{"ids": ["1", "2"], "text": "Peki, ananla ne\nyapacaksın ki?"}]
        out = gui._enforce_segment_groups(self.WIN, groups)
        self.assertEqual(len(out), 1)
        ts, text = out[0]
        self.assertEqual(ts, "00:00:05,706 --> 00:00:07,975")  # ilk başı → son sonu
        self.assertEqual(text, "Peki, ananla ne\nyapacaksın ki?")  # AI kırması korundu
        self.assertLessEqual(text.count("\n") + 1, 2)

    def test_unfaithful_ai_text_falls_back_to_deterministic(self):
        # AI 'ananla' → 'annenle' diye kelime değiştirdi → AI metni reddedilir
        groups = [{"ids": ["1", "2"], "text": "Peki, annenle ne yapacaksın ki?"}]
        out = gui._enforce_segment_groups(self.WIN, groups)
        joined = out[0][1].replace("\n", " ")
        self.assertIn("ananla", joined)
        self.assertNotIn("annenle", joined)

    def test_non_partition_rejected(self):
        self.assertIsNone(gui._enforce_segment_groups(self.WIN, [{"ids": ["1"], "text": "x"}]))
        self.assertIsNone(gui._enforce_segment_groups(
            self.WIN, [{"ids": ["1", "2", "9"], "text": "x"}]))
        # sıra bozuk
        self.assertIsNone(gui._enforce_segment_groups(
            self.WIN, [{"ids": ["2", "1"], "text": "x"}]))

    def test_cps_too_fast_rejected(self):
        win = [("1", "00:00:00,000 --> 00:00:00,100", "kelimebir on"),
               ("2", "00:00:00,100 --> 00:00:00,200", "devamxx")]
        groups = [{"ids": ["1", "2"], "text": "kelimebir on devamxx"}]
        self.assertIsNone(gui._enforce_segment_groups(win, groups))  # ~95 cps → red

    def test_single_id_groups_keep_original_text(self):
        # AI birleştirmemeyi seçti (iki ayrı tek-id grup) → orijinal metin/zaman korunur
        win = [("1", "00:00:01,000 --> 00:00:02,000", "ilk\nsatır"),
               ("2", "00:00:02,000 --> 00:00:03,000", "ikinci")]
        groups = [{"ids": ["1"], "text": ""}, {"ids": ["2"], "text": ""}]
        out = gui._enforce_segment_groups(win, groups)
        self.assertEqual(out, [("00:00:01,000 --> 00:00:02,000", "ilk\nsatır"),
                               ("00:00:02,000 --> 00:00:03,000", "ikinci")])

    def test_an8_override_preserved_once(self):
        win = [("1", "00:00:01,000 --> 00:00:02,000", "{\\an8}devam eden"),
               ("2", "00:00:02,000 --> 00:00:03,000", "{\\an8}cümle")]
        groups = [{"ids": ["1", "2"], "text": "{\\an8}devam eden cümle"}]
        out = gui._enforce_segment_groups(win, groups)
        self.assertEqual(out[0][1].count("{\\an8}"), 1)
        self.assertTrue(out[0][1].startswith("{\\an8}"))


# ── Uçtan uca (sahte model) ───────────────────────────────────────────────────
class AiResegmentTest(unittest.TestCase):
    BLOCKS = [
        ("1", "00:00:05,706 --> 00:00:07,475", "Peki, ananla ne yapacaksın"),
        ("2", "00:00:07,475 --> 00:00:07,975", "ki?"),
        ("3", "00:00:14,715 --> 00:00:16,000", "Hurlan: Merhaba dostum."),
    ]

    def test_happy_path_merges_via_ai(self):
        resp = {"results": [{"window": 0, "groups": [
            {"ids": ["1", "2"], "text": "Peki, ananla ne\nyapacaksın ki?"}]}]}
        with _Patched(response_obj=resp):
            out = gui.ai_resegment_cues(self.BLOCKS, "fake-key")
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0], ("1", "00:00:05,706 --> 00:00:07,975",
                                  "Peki, ananla ne\nyapacaksın ki?"))
        self.assertEqual(out[1][0], "2")               # yeniden numaralandı
        self.assertIn("Hurlan", out[1][2])

    def test_garbage_response_falls_back_to_deterministic_merge(self):
        # Geçersiz id'ler → enforce None → pencere deterministik birleşir (yine de birleşir)
        resp = {"results": [{"window": 0, "groups": [
            {"ids": ["999"], "text": "alakasız"}]}]}
        with _Patched(response_obj=resp):
            out = gui.ai_resegment_cues(self.BLOCKS, "fake-key")
        self.assertEqual(len(out), 2)                  # 1+2 yine birleşti (yedek)
        self.assertIn("ananla", out[0][2].replace("\n", " "))
        self.assertIn("ki?", out[0][2])

    def test_api_exception_falls_back(self):
        with _Patched(raise_exc=RuntimeError("boom")):
            out = gui.ai_resegment_cues(self.BLOCKS, "fake-key")
        self.assertEqual(len(out), 2)                  # deterministik yedekle birleşti

    def test_request_cancellation_is_not_downgraded_to_fallback(self):
        with _Patched(raise_exc=RequestCancelled("stopped")):
            with self.assertRaises(RequestCancelled):
                gui.ai_resegment_cues(self.BLOCKS, "fake-key")

    def test_app_merge_wrapper_preserves_request_cancellation(self):
        app = types.SimpleNamespace(
            ai_segment_var=types.SimpleNamespace(get=lambda: True),
            merge_cues_var=types.SimpleNamespace(get=lambda: False),
            _helper_api_key=lambda role: "fake-key",
            _helper_api_base_url=lambda role: "https://example.invalid/v1",
            _helper_api_model=lambda role: "fake-model",
            _merge_max_chars=84,
            _merge_max_gap_ms=800,
            _cached_blocks_for=lambda _path: self.BLOCKS,
            _log=lambda *args: None,
        )
        original = gui.ai_resegment_cues
        gui.ai_resegment_cues = lambda *args, **kwargs: (_ for _ in ()).throw(
            RequestCancelled("stopped"))
        try:
            with self.assertRaises(RequestCancelled):
                gui.App._maybe_merge_cues(app, self.BLOCKS, "movie.srt")
        finally:
            gui.ai_resegment_cues = original

    def test_no_candidates_uses_deterministic_path(self):
        # Tam cümleler → aday pencere yok → AI hiç çağrılmaz, merge_fragmented_cues döner
        plain = [("1", "00:00:01,000 --> 00:00:02,000", "Bitti."),
                 ("2", "00:00:02,000 --> 00:00:03,000", "Tamam.")]
        called = {"n": 0}

        def _spy(client, **kw):
            called["n"] += 1
            raise AssertionError("aday yokken model çağrılmamalı")

        orig = ht._safe_chat_create
        ht._safe_chat_create = _spy
        try:
            out = gui.ai_resegment_cues(plain, "fake-key")
        finally:
            ht._safe_chat_create = orig
        self.assertEqual(called["n"], 0)
        self.assertEqual(len(out), 2)                  # değişmeden

    def test_input_not_mutated(self):
        snapshot = copy.deepcopy(self.BLOCKS)
        resp = {"results": [{"window": 0, "groups": [
            {"ids": ["1", "2"], "text": "Peki, ananla ne yapacaksın ki?"}]}]}
        with _Patched(response_obj=resp):
            gui.ai_resegment_cues(self.BLOCKS, "fake-key")
        self.assertEqual(self.BLOCKS, snapshot)


class AdversarialFixesTest(unittest.TestCase):
    """Adversaryal doğrulamada (13 onaylı bulgu) bulunan kelime-güvenliği / senkron /
    yedek kusurlarının regresyon testleri. Hepsinde 'sadık olmayan' AI metni reddedilip
    deterministik birleştirmeye düşülmeli; kelime/etiket/konum/zamanlama hiç bozulmamalı."""

    # #2 — AI etiket (italik vb.) ekleyemez: sadık değil → deterministik düz metin
    def test_tag_injection_rejected(self):
        win = [("1", "00:00:01,000 --> 00:00:02,000", "He really"),
               ("2", "00:00:02,100 --> 00:00:04,000", "meant it")]
        out = gui._enforce_segment_groups(win, [{"ids": ["1", "2"], "text": "<i>He really meant it</i>"}])
        self.assertNotIn("<i>", out[0][1])
        self.assertIn("He really meant it", out[0][1].replace("\n", " "))

    # #1 — AI parantez içeriğini ({...}) değiştiremez
    def test_brace_content_change_rejected(self):
        win = [("1", "00:00:01,000 --> 00:00:02,000", "Fiyat {indirimli}"),
               ("2", "00:00:02,100 --> 00:00:05,000", "elli lira")]
        out = gui._enforce_segment_groups(win, [{"ids": ["1", "2"], "text": "Fiyat {ARTIRILMIS} elli lira"}])
        self.assertIn("{indirimli}", out[0][1])
        self.assertNotIn("ARTIRILMIS", out[0][1])

    # #1b — AI konum etiketini ({\anN}) değiştirip altyazıyı taşıyamaz
    def test_position_tag_change_rejected(self):
        win = [("1", "00:00:01,000 --> 00:00:02,000", "{\\an8}Selam"),
               ("2", "00:00:02,100 --> 00:00:05,000", "dünya")]
        out = gui._enforce_segment_groups(win, [{"ids": ["1", "2"], "text": "{\\an2}Selam dünya"}])
        self.assertIn("{\\an8}", out[0][1])
        self.assertNotIn("an2", out[0][1])

    # #5/#7/#8 — AI kelimeleri yapıştıramaz/bölemez (boşluk tek boşluğa indirilir, silinmez)
    def test_word_glue_rejected(self):
        win = [("1", "00:00:01,000 --> 00:00:02,000", "Kapat"),
               ("2", "00:00:02,100 --> 00:00:05,000", "kapıyı")]
        out = gui._enforce_segment_groups(win, [{"ids": ["1", "2"], "text": "Kapatkapıyı"}])
        self.assertIn("Kapat kapıyı", out[0][1].replace("\n", " "))
        self.assertNotIn("Kapatkapıyı", out[0][1].replace("\n", ""))

    # #10 — AI harf büyüklüğünü değiştiremez (özel ad küçültülemez)
    def test_case_change_rejected(self):
        win = [("1", "00:00:01,000 --> 00:00:05,000", "Igor")]
        out = gui._enforce_segment_groups(win, [{"ids": ["1"], "text": "igor"}])
        self.assertEqual(out[0][1], "Igor")

    # #3 — tamamlanmış cümleyi sonrakine yapıştırma (enforce reddeder)
    def test_no_merge_across_sentence_boundary(self):
        win = [("1", "00:00:00,000 --> 00:00:01,000", "Run!"),
               ("2", "00:00:01,100 --> 00:00:02,000", "I am"),
               ("3", "00:00:02,100 --> 00:00:03,000", "so tired.")]
        self.assertIsNone(gui._enforce_segment_groups(
            win, [{"ids": ["1", "2", "3"], "text": "Run! I am so tired."}]))

    # #3 — aday pencere baştaki tam cümleyi içermez
    def test_candidates_exclude_leading_sentence(self):
        b = [("1", "00:00:00,000 --> 00:00:01,000", "Run!"),
             ("2", "00:00:01,100 --> 00:00:02,000", "I am"),
             ("3", "00:00:02,100 --> 00:00:03,000", "so tired.")]
        self.assertEqual(gui._segmentation_candidates(b), [(1, 2)])

    # #4 — birleşim deterministik temelle aynı sert karakter tavanını aşamaz
    def test_overlong_merge_rejected_like_baseline(self):
        long1, long2 = "x" * 50, "y" * 50          # birleşik ~101 > 84
        win = [("1", "00:00:00,000 --> 00:00:04,000", long1),
               ("2", "00:00:04,100 --> 00:00:08,000", long2)]   # CPS ~12 (zaman bol), sadece genişlik aşıyor
        self.assertIsNone(gui._enforce_segment_groups(
            win, [{"ids": ["1", "2"], "text": long1 + " " + long2}]))

    # #6/#12 — tekrarlı index'li pencere reddedilir (cue düşürme/çoğaltma yok)
    def test_duplicate_ids_rejected(self):
        win = [("1", "00:00:01,000 --> 00:00:02,000", "Peki"),
               ("1", "00:00:02,000 --> 00:00:03,000", "ne")]
        self.assertIsNone(gui._enforce_segment_groups(
            win, [{"ids": ["1", "1"], "text": "Peki ne"}]))

    # Whitespace-smuggle: AI normal boşluk yerine CR/NBSP/ideografik/TAB koyup
    # sadakat kapısını geçemez — çıktı yalnız ASCII boşluk + \n + orijinal kelimeler
    def test_control_whitespace_smuggle_neutralized(self):
        win = [("1", "00:00:01,000 --> 00:00:02,000", "Hello"),
               ("2", "00:00:02,100 --> 00:00:05,000", "world")]
        for weird in ["Hello\rworld", "Hello\xa0world", "Hello　world", "Hello\tworld"]:
            out = gui._enforce_segment_groups(win, [{"ids": ["1", "2"], "text": weird}])
            self.assertIsNotNone(out)
            txt = out[0][1]
            for bad in ("\r", "\xa0", "　", "\t"):
                self.assertNotIn(bad, txt)
            self.assertIn("Hello", txt)
            self.assertIn("world", txt)

    # #11 — hızlı tek-üye kaynak cue tüm pencereyi reddetmez (CPS yalnız birleşmelere)
    def test_fast_single_source_cue_does_not_reject_window(self):
        win = [("3", "00:00:01,000 --> 00:00:01,400", "I think that"),
               ("4", "00:00:01,500 --> 00:00:03,000", "we should go."),
               ("5", "00:00:03,200 --> 00:00:03,640", "Run now, hurry up everyone!")]  # ~61 CPS tek cue
        out = gui._enforce_segment_groups(win, [
            {"ids": ["3", "4"], "text": "I think that\nwe should go."},
            {"ids": ["5"], "text": "Run now, hurry up everyone!"}])
        self.assertIsNotNone(out)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[1][1], "Run now, hurry up everyone!")  # tek cue dokunulmadan geçti


if __name__ == "__main__":
    unittest.main()
