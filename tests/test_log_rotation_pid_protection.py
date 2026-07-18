"""rotate_logs — CANLI süreç logları sayıya bakılmaksızın korunur.

NEDEN (2026-07-16 gerçek olay): kullanıcı bir batch'i saatlerce beklerken (log dosyası
sessiz — mtime bayatlıyor) art arda çalıştırılan test App() örnekleri onlarca yeni (taze
mtime'lı) log oluşturdu; eski sayı-bazlı 'en yeni N' kuralı kullanıcının sessiz ama CANLI
oturum logunu rotasyondan düşürüp SİLDİ — geri getirilemedi. Dosya adına pid gömülüp
_pid_alive ile kontrol edilerek bu artık imkânsız kılınıyor: log ne kadar sessiz/bayat
kalırsa kalsın, sahibi yaşadığı sürece silinmez.
"""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import subtitle_translator_gui as gui


class RotateLogsPidProtectionTest(unittest.TestCase):
    def test_live_pid_log_never_deleted_even_if_stale_and_over_keep(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            # Kendi pid'imizle (kesin canlı) BAYAT bir log — mtime çok eski.
            live = d / f"2026-01-01_000000.pid{os.getpid()}.log"
            live.write_text("x", encoding="utf-8")
            old_ts = time.time() - 999_999
            os.utime(live, (old_ts, old_ts))
            # keep sınırını dolduracak kadar TAZE, sıradan log
            for i in range(5):
                (d / f"fresh_{i}.log").write_text("x", encoding="utf-8")
            removed = gui.rotate_logs(d, keep=2)
            self.assertTrue(live.exists(), "canlı sürecin logu SİLİNMEMELİYDİ")
            self.assertGreater(removed, 0)   # sıradan bayat/taşan loglar yine de silindi

    def test_dead_pid_log_is_deletable(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            dead_pid = 999_999_997
            dead = d / f"2026-01-01_000000.pid{dead_pid}.log"
            dead.write_text("x", encoding="utf-8")
            old_ts = time.time() - 999_999
            os.utime(dead, (old_ts, old_ts))
            for i in range(5):
                (d / f"fresh_{i}.log").write_text("x", encoding="utf-8")
            gui.rotate_logs(d, keep=2)
            self.assertFalse(dead.exists(), "ölü sürecin logu diğerleri gibi rotasyona tabi olmalı")

    def test_ordinary_numeric_filenames_not_misparsed_as_pid(self):
        # REGRESYON KANITI: ilk tasarım `_(\d+)\.log$` kullanıyordu — 'log_04.log' gibi
        # sıradan test dosyaları da eşleşip pid=4 (Windows'ta System, HER ZAMAN canlı)
        # sanılıp YANLIŞLIKLA korunuyordu. '.pid<N>.log' işaretleyicisi bunu önler.
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            for i in range(10):
                p = d / f"log_{i:02d}.log"
                p.write_text("x", encoding="utf-8")
                ts = time.time() - (10 - i) * 60
                os.utime(p, (ts, ts))
            removed = gui.rotate_logs(d, keep=4)
            self.assertEqual(removed, 6, "sıradan adlar pid-korumalı sanılmamalı")

    def test_pid_alive_never_called_for_files_without_marker(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            for i in range(3):
                (d / f"plain_{i}.log").write_text("x", encoding="utf-8")
            with patch.object(gui, "_pid_alive") as mock_alive:
                gui.rotate_logs(d, keep=1)
            mock_alive.assert_not_called()

    def test_default_keep_is_100(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            for i in range(50):
                (d / f"l_{i:03d}.log").write_text("x", encoding="utf-8")
            removed = gui.rotate_logs(d)   # keep verilmedi -> varsayılan
            self.assertEqual(removed, 0, "50 < varsayılan keep(100), hiçbiri silinmemeli")


if __name__ == "__main__":
    unittest.main()
