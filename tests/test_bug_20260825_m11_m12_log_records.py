# -*- coding: utf-8 -*-
"""Madde 11 ve 12: bir log kaydı bir satır; klasör sayacı tek kaynaktan."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as gui


class OneLogRecordIsOnePhysicalLineTest(unittest.TestCase):
    """Mesajın İÇİNDE gerçek satır sonu olabiliyor: tutarlılık ve onarım
    satırları cue metnini alıntılıyor. O zaman tek kayıt birden çok fiziksel
    satıra yayılıyor, devam satırlarında zaman damgası olmuyor ve satır
    bazlı ayrıştırma iki kaydı birleşmiş görüyordu.

    102 gerçek log dosyası ölçüldü: 19.434 dolu satırın 776'sında (%4,0)
    zaman damgası yok. Katlama bunları tek kayda indirir.
    """

    def test_an_embedded_newline_is_folded(self):
        folded = gui._fold_log_record(
            "Tutarlılık #581 | kaynak='♪ Please don't\nKeep me waiting ♪'")
        self.assertNotIn("\n", folded)
        self.assertIn("⏎", folded)

    def test_carriage_returns_are_folded_too(self):
        self.assertEqual(gui._fold_log_record("a\r\nb\rc"), "a ⏎ b ⏎ c")

    def test_a_single_line_is_untouched(self):
        self.assertEqual(gui._fold_log_record("tek satır"), "tek satır")

    def test_empty_input_is_safe(self):
        self.assertEqual(gui._fold_log_record(""), "")
        self.assertEqual(gui._fold_log_record(None), "")

    def test_the_writer_folds_before_writing(self):
        import inspect
        source = inspect.getsource(gui.App._log)
        self.assertIn("_fold_log_record(disk_msg)", source)
        self.assertIn("{disk_line}", source)


class TheFolderCounterHasOneSourceTest(unittest.TestCase):
    """Gerçek logda (run_20260824-121939) üç ardışık deneme sırasıyla
    'toplam 488', 'toplam 484', 'toplam 484' yazdı ve üçü de '+0 yeni'
    dedi. Kök neden madde 17'dir: seçim boşken bütün giriş klasörü
    tohumlanıyor, sayı bir kez önbellekten bir kez taze taramadan geliyordu.
    Tohumlama kalkınca sayı eklenen klasörlerden gelir ve tekrarlanabilir.
    """

    def _app(self, input_dir):
        app = SimpleNamespace(
            _selected_files=[], _content_type_preflight_done=True,
            _language_preflight_done=True,
            _input_folder_explicitly_selected=True, _is_running=False,
            input_var=SimpleNamespace(get=lambda: input_dir),
            _selected_folder_roots=[], _pm=None,
            _file_list_root=input_dir, _file_list_files=[],
            logs=[], refreshes=[],
        )
        app._dedupe_paths = lambda paths: gui.App._dedupe_paths(app, paths)
        app._get_srt_files = lambda: gui.App._get_srt_files(app)
        app._log = lambda *args: app.logs.append(args)
        app._refresh_selected_files_ui = lambda text: app.refreshes.append(text)
        return app

    def test_repeating_the_same_add_gives_the_same_total(self):
        with tempfile.TemporaryDirectory() as root:
            wanted = []
            for name in ("a", "b", "c"):
                folder = Path(root, name)
                folder.mkdir()
                (folder / f"{name}.srt").write_text("", encoding="utf-8")
                wanted.append(str(folder))
            # Onbellek BAYAT: listede fazladan dosya var.
            totals = []
            for _ in range(3):
                app = self._app(root)
                app._file_list_files = [os.path.join(root, "hayalet.srt")]
                gui.App._append_folder_files(app, wanted)
                totals.append(len(app._selected_files))
            self.assertEqual(totals, [3, 3, 3], f"sayaç oynadı: {totals}")

    def test_the_added_count_is_not_zero(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root, "a")
            folder.mkdir()
            (folder / "a.srt").write_text("", encoding="utf-8")
            app = self._app(root)
            app._file_list_files = [str(folder / "a.srt")]
            added = gui.App._append_folder_files(app, [str(folder)])
            self.assertEqual(added, 1, "gerçek logdaki '+0 yeni' geri geldi")


if __name__ == "__main__":
    unittest.main()
