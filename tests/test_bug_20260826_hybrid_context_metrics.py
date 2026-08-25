# -*- coding: utf-8 -*-
"""Hibrit file_map biçimi dosya yolu sanılıp bütün chunk'lar eleniyordu."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as gui

PAYLOAD = {
    "tr": [{"i": "1", "t": "bir"}, {"i": "2", "t": "iki"}],
    "ctx": [{"i": "0", "t": "önceki"}],
    "next_ctx": [{"i": "3", "t": "sonraki"}],
    "prev_tr": [{"i": "0", "t": "çeviri"}],
}
REQUESTS = [{
    "custom_id": "chunk_0",
    "body": {"messages": [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": json.dumps(PAYLOAD, ensure_ascii=False)},
    ]},
}]

TARGET = os.path.abspath("film.srt")
OTHER = os.path.abspath("baska.srt")

# Düz akış: (cue_id, timestamp, DOSYA YOLU) — gui build_requests:8765
PLAIN_MAP = {"chunk_0": [("1", "00:00:01,000 --> 00:00:02,000", TARGET)]}
# Hibrit: (cue.index, start, END) — ht.build_batch_requests:14598
HYBRID_MAP = {"chunk_0": [(1, "00:00:01,000", "00:00:02,000"),
                          (2, "00:00:02,000", "00:00:04,000")]}


class TheHybridFileMapIsMeasuredTest(unittest.TestCase):
    """file_map'in satır biçimi akışa göre değişiyor: düz akış üçüncü öğeye
    dosya yolu, hibrit ise bitiş zamanı yazıyor. Ölçüm üçüncü öğeyi her
    zaman yol sanıp mutlak yola çeviriyordu; hibritte hiçbir chunk eşleşmiyor
    ve BÜTÜN istekler eleniyordu.

    Gerçek koşuda (20260824-160357) 38 dosyanın 38'i kalite raporunda
    "Zincirleme Bağlam: açık; gerçek enjeksiyon ölçümü bulunamadı" satırını
    aldı — toplam 25.388 cue'nun bağlam ölçümü görünmez kaldı.
    """

    def test_the_hybrid_shape_is_counted(self):
        metrics = gui._context_payload_metrics(
            REQUESTS, filepath=TARGET, file_map=HYBRID_MAP)
        self.assertEqual(metrics["chunks"], 1)
        self.assertEqual(metrics["source_cues"], 2)
        self.assertEqual(metrics["ctx_chunks"], 1)
        self.assertEqual(metrics["next_ctx_chunks"], 1)
        self.assertEqual(metrics["prev_tr_chunks"], 1)
        self.assertEqual(metrics["prev_tr_pairs"], 1)

    def test_the_plain_shape_is_unchanged(self):
        metrics = gui._context_payload_metrics(
            REQUESTS, filepath=TARGET, file_map=PLAIN_MAP)
        self.assertEqual(metrics["chunks"], 1)
        self.assertEqual(metrics["ctx_chunks"], 1)
        self.assertEqual(metrics["prev_tr_chunks"], 1)

    def test_another_file_is_still_filtered_out(self):
        # Düz akışta dosya kapsamı korunmalı — düzeltme onu gevşetmemeli.
        metrics = gui._context_payload_metrics(
            REQUESTS, filepath=OTHER, file_map=PLAIN_MAP)
        self.assertEqual(metrics["chunks"], 0)

    def test_a_mixed_map_still_scopes_by_path(self):
        mixed = {
            "chunk_0": [("1", "ts", TARGET)],
            "chunk_1": [("2", "ts", OTHER)],
        }
        requests = REQUESTS + [{
            "custom_id": "chunk_1",
            "body": {"messages": [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": json.dumps(PAYLOAD)},
            ]},
        }]
        metrics = gui._context_payload_metrics(
            requests, filepath=TARGET, file_map=mixed)
        self.assertEqual(metrics["chunks"], 1)


class TheRowShapeDetectorTest(unittest.TestCase):
    """Zaman damgasında dizin ayracı ya da altyazı uzantısı bulunmaz."""

    def test_a_path_map_is_recognised(self):
        self.assertTrue(gui._file_map_rows_carry_paths(PLAIN_MAP))

    def test_a_timestamp_map_is_not(self):
        self.assertFalse(gui._file_map_rows_carry_paths(HYBRID_MAP))

    def test_a_bare_filename_still_counts_as_a_path(self):
        self.assertTrue(gui._file_map_rows_carry_paths(
            {"c": [("1", "ts", "film.srt")]}))
        self.assertTrue(gui._file_map_rows_carry_paths(
            {"c": [("1", "ts", "bolum.ass")]}))

    def test_empty_and_short_rows_are_safe(self):
        self.assertFalse(gui._file_map_rows_carry_paths({}))
        self.assertFalse(gui._file_map_rows_carry_paths(None))
        self.assertFalse(gui._file_map_rows_carry_paths({"c": [("1", "ts")]}))
        self.assertFalse(gui._file_map_rows_carry_paths({"c": [("1", "ts", "")]}))


if __name__ == "__main__":
    unittest.main()
