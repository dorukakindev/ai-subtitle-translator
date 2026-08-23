# -*- coding: utf-8 -*-
"""Altıncı tur: rapor modu sözleşmesi, dosya atlama, yanıt bütünlüğü."""
import inspect
import json
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht
import response_integrity as ri
import subtitle_translator_gui as g


class ReportOnlyBlocksSemanticApplyTest(unittest.TestCase):
    """'Yalnız Raporla' otomatik yeniden çeviriyi RAPORLAR, uygulamaz.

    `apply_changes` hiç verilmediği için varsayılan True kullanılıyor ve
    sonuç doğrudan teslim metnine yazılıyordu. Derin Teslim taraması aynı
    pass'i zaten `apply_changes=False` ile çağırıyordu.
    """

    def test_the_pass_receives_the_mode(self):
        source = inspect.getsource(g.App._maybe_semantic_reconciliation)
        self.assertIn("apply_changes=_semantic_apply", source)
        self.assertIn("_delivery_report_only_enabled", source)

    def test_the_result_is_only_written_when_applying(self):
        source = inspect.getsource(g.App._maybe_semantic_reconciliation)
        self.assertIn("if _semantic_apply:", source)
        marker = source.index("if _semantic_apply:")
        self.assertIn("blocks[:] = result", source[marker:marker + 120])

    def test_an_unknown_setting_does_not_apply(self):
        # Resolver bilinmeyende güvenli tarafta kalıp True (rapor modu) döner.
        app = g.App.__new__(g.App)
        app._active_snapshot = None
        self.assertTrue(g.App._delivery_report_only_enabled(app))

    def test_the_deep_scan_still_never_applies(self):
        source = inspect.getsource(g.App._maybe_deep_delivery_semantic_audit)
        self.assertIn("apply_changes=False", source)


class SkipFileStopsTheChunkLoopTest(unittest.TestCase):
    """'Dosyayı atla' koşunun PAYLAŞILAN canceller'ını iptal ediyor.

    Chunk döngüleri yalnız `_stop_flag`e bakıp devam ediyor ve her chunk
    `RequestCancelled` ile düşüyordu. Gerçek loglarda tek atlama 201 ve
    172 sahte "Chunk hatası" üretti.
    """

    def test_both_loops_check_the_skip_flag(self):
        source = inspect.getsource(g.App._run_sync_hybrid)
        self.assertGreaterEqual(source.count("_file_skip_requested("), 2)

    def test_cancellation_is_not_counted_as_a_chunk_error(self):
        source = inspect.getsource(g.App._run_sync_hybrid)
        # Chunk dongulerindeki iptal yakalayicilari (sema tespitininki degil)
        self.assertIn("# Atlama/durdurma iptali hata DEGILDIR.", source)
        marker = source.index("# Atlama/durdurma iptali hata DEGILDIR.")
        self.assertIn("_file_skip_requested(self, filepath)",
                      source[marker:marker + 300])

    def test_pending_futures_are_cancelled_on_skip(self):
        source = inspect.getsource(g.App._run_sync_hybrid)
        self.assertIn("ex.shutdown(wait=False, cancel_futures=True)", source)


class JsonRepairHonestyTest(unittest.TestCase):
    """Onarım kesilmiş yanıtı kabul ediyor ve kısmiyi 'kurtarıldı' sayıyordu."""

    def test_the_repair_response_goes_through_the_validator(self):
        source = inspect.getsource(g.App._json_repair_pass)
        self.assertIn("fixed = _validated_chat_content(resp)", source)

    def test_a_partial_merge_is_not_counted_as_rescued(self):
        source = inspect.getsource(g.App._json_repair_pass)
        self.assertIn("_complete = len(merged) >= len(expected_ids)", source)
        self.assertIn("chunk kurtarılmış sayılmadı", source)

    def test_a_truncated_response_is_rejected(self):
        truncated = SimpleNamespace(
            choices=[SimpleNamespace(
                finish_reason="length",
                message=SimpleNamespace(content='[{"i":"1","t":"X"}]'))])
        with self.assertRaises(RuntimeError):
            g._validated_chat_content(truncated)


class MultiPayloadResponseTest(unittest.TestCase):
    """İki tam JSON bloğunda ilki sessizce seçiliyordu."""

    NL = chr(10)

    def test_two_different_payloads_are_refused(self):
        raw = ('[{"i":1,"t":"X"},{"i":2,"t":"Y"}]' + self.NL
               + '[{"i":1,"t":"A"},{"i":2,"t":"B"}]')
        items, mode = ri.translation_items_from_raw(raw)
        self.assertIsNone(items)
        self.assertEqual(mode, "ambiguous_multiple_payloads")

    def test_an_identical_repeat_is_still_accepted(self):
        raw = '[{"i":1,"t":"X"}]' + self.NL + '[{"i":1,"t":"X"}]'
        items, mode = ri.translation_items_from_raw(raw)
        self.assertEqual(mode, "array")
        self.assertEqual(items, [{"i": 1, "t": "X"}])

    def test_a_single_payload_is_unaffected(self):
        self.assertEqual(
            ri.translation_items_from_raw('[{"i":1,"t":"X"}]')[1], "array")
        self.assertEqual(
            ri.translation_items_from_raw('{"tr":[{"i":1,"t":"X"}]}')[1],
            "envelope")


class IdOrderIsNotAnIntegrityErrorTest(unittest.TestCase):
    """Eşleme KİMLİK üzerinden; yalnız sıra farkı veriyi bozmaz."""

    SRC = {"1": "The red door is open.",
           "2": "The blue car is fast.",
           "3": "The green book is old."}

    def _req(self):
        payload = {"tr": [{"i": k, "t": v} for k, v in self.SRC.items()]}
        return {"body": {"messages": [
            {"role": "system", "content": ""},
            {"role": "user", "content": json.dumps(payload)}]}}

    def _reason(self, items):
        return g._chunk_response_retry_reason(
            json.dumps(items, ensure_ascii=False), self._req())

    def test_a_shuffled_but_complete_answer_is_accepted(self):
        self.assertEqual(self._reason([
            {"i": "2", "t": "Mavi araba hızlı."},
            {"i": "1", "t": "Kırmızı kapı açık."},
            {"i": "3", "t": "Yeşil kitap eski."}]), "")

    def test_a_missing_id_is_still_an_error(self):
        self.assertEqual(self._reason([
            {"i": "1", "t": "Kırmızı kapı açık."},
            {"i": "3", "t": "Yeşil kitap eski."}]), "id_integrity")

    def test_a_duplicate_id_is_still_an_error(self):
        self.assertEqual(self._reason([
            {"i": "1", "t": "Kırmızı kapı açık."},
            {"i": "1", "t": "X."},
            {"i": "2", "t": "Mavi araba hızlı."},
            {"i": "3", "t": "Yeşil kitap eski."}]), "id_integrity")

    def test_an_unexpected_id_is_still_an_error(self):
        self.assertEqual(self._reason([
            {"i": "1", "t": "Kırmızı kapı açık."},
            {"i": "2", "t": "Mavi araba hızlı."},
            {"i": "3", "t": "Yeşil kitap eski."},
            {"i": "9", "t": "Z."}]), "id_integrity")


class SemanticExemptionDoesNotForgiveNewDamageTest(unittest.TestCase):
    """Muafiyet 'eski sorunlardan biri kayboldu'ya bakıyordu.

    Adayın AYNI ANDA yeni bir bozulma eklemesini engellemiyordu.
    """

    def test_fixing_a_question_mark_cannot_swap_the_roles(self):
        ok, reason = ht.validate_semantic_reconciliation_candidate(
            "Doktor hastayı kurtardı.", "Hasta doktoru kurtardı mı?",
            source_text="Did the doctor save the patient?",
            tgt_lang="Turkish")
        self.assertFalse(ok)
        self.assertEqual(reason, "role_swap")

    def test_the_exemption_list_still_carries_role_swap(self):
        # Semantic pass'in İŞİ kaynaktan yeniden çevirmek; düz ret onu keserdi.
        self.assertIn("role_swap", ht._SEMANTIC_REWRITE_REJECTIONS)



class DeterministicFileOrderTest(unittest.TestCase):
    """Dosya sırası CHUNK TAMAMLANMA sırasına düşüyordu.

    `raw_map` paralel akışta `as_completed` ile dolduğu için ağ hızı sonraki
    adımların sırasını belirliyordu; dizi hafızası "ilk karar kanon"
    politikasıyla bu sırayla commit edildiğinden aynı girdi farklı kanon
    üretebiliyordu.
    """

    FILE_MAP = {
        "cA": [("1", "ts", "A.srt"), ("2", "ts", "A.srt")],
        "cB": [("1", "ts", "B.srt")],
    }

    @staticmethod
    def _raw(ids):
        return json.dumps([{"i": i, "t": "X" + i} for i in ids],
                          ensure_ascii=False)

    def test_completion_order_does_not_change_file_order(self):
        forward = {"cA": self._raw(["1", "2"]), "cB": self._raw(["1"])}
        reverse = {"cB": self._raw(["1"]), "cA": self._raw(["1", "2"])}
        self.assertEqual(list(g.collect_results(forward, self.FILE_MAP)),
                         ["A.srt", "B.srt"])
        self.assertEqual(list(g.collect_results(reverse, self.FILE_MAP)),
                         ["A.srt", "B.srt"])

    def test_the_content_is_identical_either_way(self):
        forward = {"cA": self._raw(["1", "2"]), "cB": self._raw(["1"])}
        reverse = {"cB": self._raw(["1"]), "cA": self._raw(["1", "2"])}
        self.assertEqual(g.collect_results(forward, self.FILE_MAP),
                         g.collect_results(reverse, self.FILE_MAP))

    def test_a_file_missing_from_the_map_is_still_kept(self):
        raw = {"cA": self._raw(["1", "2"]), "cB": self._raw(["1"])}
        result = g.collect_results(raw, self.FILE_MAP)
        self.assertEqual(set(result), {"A.srt", "B.srt"})


class AlignmentComparisonIgnoresMarkupTest(unittest.TestCase):
    """Biçim etiketleri benzerlik hesabına giriyordu.

    202 gerçek çiftte bulgu 2.122 -> 2.118; adjacent_duplicate 75 -> 70.
    Elle doğrulanmış üç gerçek desync'in üçü de korundu.
    """

    def test_tags_are_stripped_before_comparing(self):
        self.assertEqual(
            g._align_visible('<font color="#FFFFFF">Merhaba dostum.</font>'),
            "Merhaba dostum.")
        self.assertEqual(g._align_visible("<i>Eğik</i>"), "Eğik")

    def test_plain_text_is_unchanged(self):
        self.assertEqual(g._align_visible("  iki   boşluk "), "iki boşluk")

    def test_two_cues_differing_only_in_tags_compare_as_equal(self):
        a = g._align_visible('<font color="#FF0000">Bir.</font>')
        b = g._align_visible("Bir.")
        self.assertEqual(a, b)

    def test_the_reverted_sentence_rule_is_documented(self):
        # Denenip GERI ALINDI: gercek bir desync'i kaciriyordu.
        source = inspect.getsource(g._find_adjacent_duplicate_ids)
        self.assertIn("DENENDİ VE GERİ ALINDI", source)

if __name__ == "__main__":
    unittest.main()
