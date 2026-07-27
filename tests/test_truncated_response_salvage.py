"""
Kesilmiş API yanıtından tamamlanmış çevirileri kurtarma (parse_response salvage).
Gözlemlenen veri kaybı: chunk yanıtı kelime ortasında kesilince tüm chunk [HATA]
oluyor ve başarıyla çevrilmiş satırlar da kayboluyordu.
"""
import unittest

import subtitle_translator_gui as gui


class SalvageTruncatedTest(unittest.TestCase):
    def test_recovers_complete_objects_before_cut(self):
        # 190,191 tam; 192 kelime ortasında kesilmiş (kapanış yok)
        raw = ('[{"i":190,"t":"Selam ver."},'
               '{"i":191,"t":"İyi oğlan. Sinn?"},'
               '{"i":192,"t":"Mümkünse, lüt')
        chunk_info = [(str(i), "ts", "fp") for i in range(190, 207)]  # 190..206
        tmap = gui.parse_response(raw, chunk_info)
        # Tamamlanan iki blok korunmalı
        self.assertEqual(tmap["190"], "Selam ver.")
        self.assertEqual(tmap["191"], "İyi oğlan. Sinn?")
        # Kesilen 192 ve sonrası [HATA] (retry/eksik-çeviri işareti devralır)
        self.assertEqual(tmap["192"], "[HATA]")
        self.assertEqual(tmap["206"], "[HATA]")
        # Hiçbir index düşmemeli — hepsi haritada
        self.assertEqual(set(tmap.keys()), {str(i) for i in range(190, 207)})

    def test_old_behavior_would_have_lost_all(self):
        # Salvage olmasaydı bu girdi _extract_json_array'de '' dönüp HEPSİ [HATA] olurdu;
        # şimdi en az tamamlananlar kurtarılıyor
        raw = '[{"i":1,"t":"Bir."},{"i":2,"t":"İki."},{"i":3,"t":"Üç'
        info = [("1","ts","fp"),("2","ts","fp"),("3","ts","fp")]
        tmap = gui.parse_response(raw, info)
        self.assertEqual(tmap["1"], "Bir.")
        self.assertEqual(tmap["2"], "İki.")
        self.assertEqual(tmap["3"], "[HATA]")

    def test_valid_full_response_unaffected(self):
        raw = '[{"i":1,"t":"Bir."},{"i":2,"t":"İki."}]'
        info = [("1","ts","fp"),("2","ts","fp")]
        tmap = gui.parse_response(raw, info)
        self.assertEqual(tmap, {"1": "Bir.", "2": "İki."})

    def test_total_garbage_all_hata(self):
        tmap = gui.parse_response("tamamen bozuk yanıt", [("1","ts","fp")])
        self.assertEqual(tmap["1"], "[HATA]")

    def test_salvage_helper_drops_partial_tail(self):
        objs = gui._salvage_json_objects('[{"i":1,"t":"a"},{"i":2,"t":"b"},{"i":3,"t":"par')
        self.assertEqual(len(objs), 2)
        self.assertEqual(objs[0]["i"], 1)
        self.assertEqual(objs[1]["i"], 2)


class MissingBlockItemsTest(unittest.TestCase):
    """Kesilme kurtarması: yalnızca gerçekten eksik bloklar yeniden istenmeli."""
    ALL = [{"i": 190, "t": "Say hello"}, {"i": 191, "t": "Good lad"},
           {"i": 192, "t": "If you would"}, {"i": 193, "t": "draw a bath"},
           {"i": 194, "t": "Brainstorm away"}]

    def test_truncated_raw_reports_only_uncompleted(self):
        # 190,191 tamamlandı; 192 kelime ortasında kesik; 193,194 hiç yok
        raw = '[{"i":190,"t":"Selam ver."},{"i":191,"t":"İyi oğlan."},{"i":192,"t":"Mümkünse'
        missing = gui._missing_block_items(self.ALL, raw)
        miss_ids = {it["i"] for it in missing}
        self.assertEqual(miss_ids, {192, 193, 194})  # 190,191 kurtarıldı, gerisi eksik

    def test_all_done_returns_empty(self):
        raw = '[' + ",".join(f'{{"i":{it["i"]},"t":"x"}}' for it in self.ALL) + ']'
        self.assertEqual(gui._missing_block_items(self.ALL, raw), [])

    def test_hata_counts_as_missing(self):
        raw = '[{"i":190,"t":"[HATA]"},{"i":191,"t":"ok"},{"i":192,"t":"ok"},{"i":193,"t":"ok"},{"i":194,"t":"ok"}]'
        miss_ids = {it["i"] for it in gui._missing_block_items(self.ALL, raw)}
        self.assertEqual(miss_ids, {190})

    def test_reason_specific_hata_counts_as_missing(self):
        raw = '[{"i":190,"t":"[HATA_NON_TURKISH_TARGET]"},{"i":191,"t":"ok"}]'
        miss_ids = {it["i"] for it in gui._missing_block_items(self.ALL, raw)}
        self.assertEqual(miss_ids, {190, 192, 193, 194})

    def test_empty_raw_all_missing(self):
        miss_ids = {it["i"] for it in gui._missing_block_items(self.ALL, "")}
        self.assertEqual(miss_ids, {190, 191, 192, 193, 194})


if __name__ == "__main__":
    unittest.main()
