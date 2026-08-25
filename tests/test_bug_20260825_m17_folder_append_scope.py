# -*- coding: utf-8 -*-
"""Madde 17: klasör ekleme, seçilmeyen dosyaları listeye alıyordu."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as gui


class FoldersInsideTheInputTreeAreRecognisedTest(unittest.TestCase):
    def test_children_are_inside(self):
        root = os.path.abspath(os.path.join("C:", os.sep, "kok"))
        self.assertTrue(gui._folders_all_inside(
            [os.path.join(root, "a"), os.path.join(root, "b")], root))

    def test_the_root_itself_counts(self):
        root = os.path.abspath(os.path.join("C:", os.sep, "kok"))
        self.assertTrue(gui._folders_all_inside([root], root))

    def test_one_outsider_is_enough(self):
        root = os.path.abspath(os.path.join("C:", os.sep, "kok"))
        outside = os.path.abspath(os.path.join("C:", os.sep, "baska"))
        self.assertFalse(gui._folders_all_inside(
            [os.path.join(root, "a"), outside], root))

    def test_a_sibling_with_a_similar_name_is_outside(self):
        root = os.path.abspath(os.path.join("C:", os.sep, "kok"))
        self.assertFalse(gui._folders_all_inside(
            [os.path.abspath(os.path.join("C:", os.sep, "kok2", "a"))], root))

    def test_empty_input_is_not_containment(self):
        self.assertFalse(gui._folders_all_inside(["C:/x"], ""))
        self.assertFalse(gui._folders_all_inside([], "C:/x"))


class AddingSubfoldersDoesNotQueueTheWholeInputTest(unittest.TestCase):
    """Seçim boş + giriş klasörü açıkça seçilmişken "klasör ekle" önce bütün
    giriş klasörünü seçime dolduruyordu. Eklenen klasörler zaten onun
    altında olduğu için added=0 çıkıyor ve kuyrukta seçilmeyen diziler
    görünüyordu. Yanlışlıkla başlatılırsa istenmeyen dosyalar çevrilir ve
    API kotası harcanır."""

    def _app(self, input_dir):
        app = SimpleNamespace(
            _selected_files=[], _content_type_preflight_done=True,
            _language_preflight_done=True,
            _input_folder_explicitly_selected=True, _is_running=False,
            input_var=SimpleNamespace(get=lambda: input_dir),
            _selected_folder_roots=[], _pm=None,
            _file_list_root="", _file_list_files=[],
            logs=[], refreshes=[],
        )
        app._dedupe_paths = lambda paths: gui.App._dedupe_paths(app, paths)
        app._get_srt_files = lambda: gui.App._get_srt_files(app)
        app._log = lambda *args: app.logs.append(args)
        app._refresh_selected_files_ui = lambda text: app.refreshes.append(text)
        return app

    def _tree(self, root):
        """Giriş klasörü: 3 istenen + 3 istenmeyen alt klasör."""
        wanted, unwanted = [], []
        for name in ("belgesel1", "belgesel2", "belgesel3"):
            folder = Path(root, name)
            folder.mkdir(parents=True)
            (folder / f"{name}.srt").write_text("", encoding="utf-8")
            wanted.append(str(folder))
        for name in ("dizi1", "dizi2", "film1"):
            folder = Path(root, name)
            folder.mkdir(parents=True)
            (folder / f"{name}.srt").write_text("", encoding="utf-8")
            unwanted.append(str(folder))
        return wanted, unwanted

    def test_only_the_chosen_subfolders_are_queued(self):
        with tempfile.TemporaryDirectory() as root:
            wanted, unwanted = self._tree(root)
            app = self._app(root)
            added = gui.App._append_folder_files(app, wanted)
            self.assertEqual(added, 3)
            self.assertEqual(len(app._selected_files), 3)
            for folder in unwanted:
                self.assertFalse(
                    any(str(path).startswith(folder)
                        for path in app._selected_files),
                    f"seçilmeyen klasör kuyruğa girdi: {folder}")

    def test_a_folder_outside_the_input_still_extends_it(self):
        # Tasarım korunur: giriş ağacının DIŞINDAN eklenen klasör, örtük
        # giriş seçimini genişletir.
        with tempfile.TemporaryDirectory() as root:
            self._tree(root)
            with tempfile.TemporaryDirectory() as other:
                extra = Path(other, "ek")
                extra.mkdir()
                (extra / "ek.srt").write_text("", encoding="utf-8")
                app = self._app(root)
                gui.App._append_folder_files(app, [str(extra)])
                # 6 giriş dosyası + 1 dışarıdan
                self.assertEqual(len(app._selected_files), 7)

    def test_an_existing_selection_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as root:
            wanted, _ = self._tree(root)
            app = self._app(root)
            keep = os.path.join(root, "elle_secilen.srt")
            Path(keep).write_text("", encoding="utf-8")
            app._selected_files = [keep]
            gui.App._append_folder_files(app, wanted[:1])
            self.assertIn(keep, app._selected_files)
            self.assertEqual(len(app._selected_files), 2)


if __name__ == "__main__":
    unittest.main()
