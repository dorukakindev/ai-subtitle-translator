import os
import unittest
from unittest import mock
import folder_picker


class FolderPickerTest(unittest.TestCase):
    def test_normalize_folder_paths_deduplicates_canonical_paths(self):
        paths = [r"C:\FolderA", r"c:\foldera", r"C:\FolderA\\", r"D:\FolderB"]
        result = folder_picker._normalize_folder_paths(paths)
        self.assertEqual(len(result), 2)
        self.assertEqual(os.path.normcase(result[0]), os.path.normcase(r"C:\FolderA"))
        self.assertEqual(os.path.normcase(result[1]), os.path.normcase(r"D:\FolderB"))

    def test_pick_multiple_folders_returns_empty_list_on_cancel_hresult(self):
        if os.name != "nt":
            self.skipTest("Windows-only COM test")

        mock_ole32 = mock.MagicMock()
        mock_ole32.CoInitializeEx.return_value = 0

        def fake_cocreate(clsid, outer, context, iid, dialog_ptr):
            import ctypes
            ctypes.cast(dialog_ptr, ctypes.POINTER(ctypes.c_void_p)).contents.value = 12345
            return 0

        mock_ole32.CoCreateInstance.side_effect = fake_cocreate

        # Mock _method calls: Show returns 0x800704C7 (ERROR_CANCELLED) as signed int -2147023673
        def fake_method(ptr, index, restype, *argtypes):
            def prototype(instance, *args):
                if index == 3:  # Show
                    return -2147023673
                return 0
            return prototype

        with mock.patch("ctypes.OleDLL", return_value=mock_ole32), \
             mock.patch("folder_picker._method", side_effect=fake_method):
            res = folder_picker.pick_multiple_folders()
            self.assertEqual(res, [])

    def test_pick_multiple_folders_returns_none_on_com_failure(self):
        if os.name != "nt":
            self.skipTest("Windows-only COM test")

        mock_ole32 = mock.MagicMock()
        mock_ole32.CoInitializeEx.return_value = 0
        mock_ole32.CoCreateInstance.return_value = -2147467259  # E_FAIL

        with mock.patch("ctypes.OleDLL", return_value=mock_ole32):
            res = folder_picker.pick_multiple_folders()
            self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
