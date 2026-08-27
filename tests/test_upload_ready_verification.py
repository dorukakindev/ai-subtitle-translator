# -*- coding: utf-8 -*-
"""`YÜKLEMEYE HAZIR.txt` doğrulanabilir olsun.

İşaret dosya başına SHA-256 yazıyordu ama hiçbir yer onu GERİ OKUYUP
doğrulamıyordu. Arşivde 159 işaret var; 158'i okunabilir girdi bile
taşımıyor (eski/elle yazılmış), programın yazdığı tek işaret ise artık
var olmayan bir dosyayı gösteriyor.

Doğrulanamayan bir işaret, işaretsizlikten kötüdür: güven verir ve
dayanağı yoktur.
"""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

import subtitle_translator_gui as g


class UploadReadyVerificationTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def _write(self, name, body):
        path = self.dir / name
        path.write_text(body, encoding="utf-8")
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _marker(self, entries):
        text = g._upload_ready_marker_text(
            {"run_id": "r1", "ended_at": "2026-08-27"}, entries)
        path = self.dir / g._UPLOAD_READY_MARKER_NAME
        path.write_text(text, encoding="utf-8")
        return path

    def test_matching_files_verify(self):
        digest = self._write("a.srt", "bir\n")
        result = g.verify_upload_ready_marker(self._marker([("a.srt", digest)]))
        self.assertEqual(result["ok"], ["a.srt"])
        self.assertTrue(result["verifiable"])
        self.assertEqual(result["changed"], [])

    def test_edited_file_is_reported_as_changed(self):
        digest = self._write("a.srt", "bir\n")
        marker = self._marker([("a.srt", digest)])
        (self.dir / "a.srt").write_text("başka\n", encoding="utf-8")
        result = g.verify_upload_ready_marker(marker)
        self.assertEqual(result["changed"], ["a.srt"])
        self.assertEqual(result["ok"], [])

    def test_deleted_file_is_reported_as_missing(self):
        digest = self._write("a.srt", "bir\n")
        marker = self._marker([("a.srt", digest)])
        (self.dir / "a.srt").unlink()
        result = g.verify_upload_ready_marker(marker)
        self.assertEqual(result["missing"], ["a.srt"])

    def test_entry_without_a_hash_makes_it_unverifiable(self):
        # Arşivdeki eski işaretlerin tamamı bu sınıfta.
        marker = self._marker([("a.srt", "")])
        result = g.verify_upload_ready_marker(marker)
        self.assertEqual(result["no_hash"], ["a.srt"])
        self.assertFalse(result["verifiable"])

    def test_hand_written_marker_yields_no_entries(self):
        path = self.dir / g._UPLOAD_READY_MARKER_NAME
        path.write_text("YÜKLEMEYE HAZIR\nelle yazılmış\n", encoding="utf-8")
        result = g.verify_upload_ready_marker(path)
        self.assertEqual(result["total"], 0)
        self.assertFalse(result["verifiable"])

    def test_missing_marker_is_safe(self):
        result = g.verify_upload_ready_marker(self.dir / "yok.txt")
        self.assertEqual(result["total"], 0)
        self.assertFalse(result["verifiable"])


if __name__ == "__main__":
    unittest.main()
