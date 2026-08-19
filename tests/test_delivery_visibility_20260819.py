"""Teslim görünürlüğü bulguları (2026-08-19 kod taraması).

Dört sınıf: (1) kalite raporu eksik cue indekslerini hiç yazmıyordu,
(2) boş çeviri teslimden sessizce düşüyordu, (3) diske yazılan bloklar hiçbir
taramadan geçmiyordu, (4) birleştirme sonrası kaynak eşleşmesi id'ye düşüp
yanlış kaynakla karşılaştırıyordu.
"""
import unittest

import subtitle_translator_gui as gui


class HataIndexReportingTest(unittest.TestCase):
    def test_indices_carry_id_and_timestamp(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Normal satır."),
            ("2", "00:12:34,500 --> 00:12:36,000", "[ÇEVİRİ EKSİK]"),
            ("3", "00:20:00,000 --> 00:20:01,000", "[HATA]"),
        ]
        entries = gui._hata_index_entries(blocks)
        self.assertEqual(entries, ["2 (00:12:34)", "3 (00:20:00)"])

    def test_report_renders_indices_and_banner(self):
        rows = [{
            "name": "bolum.srt", "total": 3, "hata": 2,
            "hata_indices": ["12 (00:01:02)", "3 (00:00:30)"],
        }]
        text = gui.build_quality_report_text(
            rows, "gpt-5.4", "Turkish", "sync", total_tokens=0)
        self.assertIn("!!! UYARI", text)
        # Sayısal id sırası (metin sıralaması '12' < '3' derdi)
        self.assertIn(
            ">>> [ÇEVİRİ EKSİK] kalan satır indeksleri: 3 (00:00:30), 12 (00:01:02)",
            text)
        # Ana başlık uyarının ÜSTÜNDE kalmalı
        self.assertLess(text.index("ÇEVİRİ KALİTE RAPORU"), text.index("!!! UYARI"))


class EmptyCueIsNotSilentlyDroppedTest(unittest.TestCase):
    def _source(self):
        return [
            ("1", "00:00:01,000 --> 00:00:02,000", "This is a real dialogue line."),
            ("2", "00:00:02,000 --> 00:00:03,000", "Another real spoken line here."),
        ]

    def test_empty_translation_with_real_source_is_marked(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Bu gerçek bir replik."),
            ("2", "00:00:02,000 --> 00:00:03,000", ""),
        ]
        result = gui._prepare_upload_ready_blocks(
            blocks, "Turkish", None, source_cues=self._source())
        texts = [text for _idx, _ts, text in result]
        self.assertIn("[ÇEVİRİ EKSİK]", texts)
        # İşaret kaldığı için imza eklenmemeli
        self.assertNotIn(gui._DELIVERY_SIGNATURE, texts)

    def test_marked_cue_is_counted_as_missing(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Bu gerçek bir replik."),
            ("2", "00:00:02,000 --> 00:00:03,000", ""),
        ]
        result = gui._prepare_upload_ready_blocks(
            blocks, "Turkish", None, source_cues=self._source())
        hata, _cps = gui._count_hata_cps(result)
        self.assertEqual(hata, 1)

    def test_empty_cue_with_sfx_source_is_still_dropped(self):
        source = [
            ("1", "00:00:01,000 --> 00:00:02,000", "This is a real dialogue line."),
            ("2", "00:00:02,000 --> 00:00:03,000", "[DOOR SLAMS]"),
        ]
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Bu gerçek bir replik."),
            ("2", "00:00:02,000 --> 00:00:03,000", ""),
        ]
        result = gui._prepare_upload_ready_blocks(
            blocks, "Turkish", None, source_cues=source)
        self.assertNotIn(
            "[ÇEVİRİ EKSİK]", [text for _idx, _ts, text in result])


class DeliveryScanTest(unittest.TestCase):
    def test_scan_counts_delivery_side_problems(self):
        long_line = "A" * 60
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "[ÇEVİRİ EKSİK]"),
            ("2", "00:00:02,000 --> 00:00:03,000", long_line),
            ("3", "00:00:03,000 --> 00:00:04,000", "Kısa satır."),
        ]
        stats = gui._scan_delivery_blocks(blocks, None)
        self.assertEqual(stats["missing"], 1)
        self.assertEqual(stats["over_width"], 1)
        self.assertGreaterEqual(stats["cps"], 1)

    def test_clean_delivery_reports_nothing(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:04,000", "Kısa ve temiz bir satır."),
        ]
        stats = gui._scan_delivery_blocks(blocks, None)
        self.assertEqual(
            [stats["missing"], stats["over_width"], stats["over_lines"]],
            [0, 0, 0])


class MergedCueSourceAlignmentTest(unittest.TestCase):
    def test_duplicate_count_uses_timestamp_span_not_id(self):
        """Birleştirme id'leri 1..N yeniden numaralandırır; eşleme zaman
        aralığına göre yapılmazsa cue yanlış kaynakla karşılaştırılır.

        Burada KAYNAK da tekrar ediyor (meşru nakarat) — doğru davranış 'yineleme
        değil'. Kimlik tabanlı eşlemede kaynak hiç bulunamadığı için bu koruma
        devreye girmez ve iki cue yanlışlıkla yineleme sayılırdı."""
        source = [
            ("10", "00:00:01,000 --> 00:00:02,000", "The bells are ringing"),
            ("11", "00:00:02,000 --> 00:00:03,000", "loudly tonight."),
            ("12", "00:00:04,000 --> 00:00:05,000", "The bells are ringing"),
            ("13", "00:00:05,000 --> 00:00:06,000", "loudly tonight."),
        ]
        # Birleştirilmiş teslim: her cue İKİ kaynak cue'sunu kapsar ve kimlikler
        # 1'den yeniden numaralanmıştır — hiçbir kaynak zaman damgasıyla birebir
        # eşleşmez, id de tutmaz.
        blocks = [
            ("1", "00:00:01,000 --> 00:00:03,000", "Çanlar bu gece yüksek sesle çalıyor."),
            ("2", "00:00:04,000 --> 00:00:06,000", "Çanlar bu gece yüksek sesle çalıyor."),
        ]
        self.assertEqual(gui._delivery_duplicate_count(blocks, source), 0)


if __name__ == "__main__":
    unittest.main()
