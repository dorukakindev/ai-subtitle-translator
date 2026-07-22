"""
Behavioral tests for queue removal, path deduplication, multi-folder append,
and output path collision avoidance.

No Tk App() instantiation; all tests exercise pure helpers or minimal stubs.
"""
import os
import sys
import types
import unittest
from pathlib import Path

# ── Resolve repo root so helpers can be imported without installing ──────────
REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


# ────────────────────────────────────────────────────────────────────────────
# Helpers extracted or replicated from subtitle_translator_gui.py
# ────────────────────────────────────────────────────────────────────────────

def _norm_path(p: str) -> str:
    return os.path.normcase(os.path.abspath(str(p)))


def _dedupe_paths(paths: list) -> list:
    seen = set()
    out = []
    for p in paths:
        key = _norm_path(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _paths_equal(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return _norm_path(a) == _norm_path(b)


def _resolve_output_path(input_dir: str, output_dir: str, filepath,
                         same_folder: bool = False) -> Path:
    """Minimal replica of _resolve_output_path for testing."""
    src = Path(filepath)
    if same_folder:
        return src.parent / (src.stem + ".srt")

    in_dir = (input_dir or "").strip()
    out_dir = (output_dir or "").strip()

    if not out_dir or _paths_equal(in_dir, out_dir):
        base = Path(in_dir) if in_dir else src.parent
        try:
            rel = src.relative_to(base)
        except Exception:
            rel = Path(src.name)
        return (base / "ÇIKTI" / rel).with_suffix(".srt")

    if in_dir:
        try:
            rel = src.relative_to(Path(in_dir))
            if len(rel.parts) > 1:
                return (Path(out_dir) / rel.parent / src.stem / src.name).with_suffix(".srt")
        except Exception:
            pass

    if (src.parent and src.parent.name
            and not _paths_equal(str(src.parent), out_dir)
            and not (in_dir and _paths_equal(str(src.parent), in_dir))):
        return (Path(out_dir) / src.parent.name / src.stem / src.name).with_suffix(".srt")

    return (Path(out_dir) / src.stem / src.name).with_suffix(".srt")


# ────────────────────────────────────────────────────────────────────────────
# Minimal stub that mimics only the queue-removal state of App
# ────────────────────────────────────────────────────────────────────────────

class _QueueStub:
    """Minimal stub replicating _norm_path / _is_queued_file_removed / _remove_queued_file."""

    def __init__(self, files=None):
        self._selected_files = list(files or [])
        self._removed_queue_files: set = set()
        self._job_rows: dict = {}
        self._stat_calls: list = []

    # replicated from App
    def _norm_path(self, filepath: str) -> str:
        return os.path.normcase(os.path.abspath(str(filepath)))

    def _is_queued_file_removed(self, filepath: str) -> bool:
        return self._norm_path(filepath) in self._removed_queue_files

    def _dedupe_paths(self, paths):
        return _dedupe_paths(paths)

    def _set_stat(self, var, val):
        self._stat_calls.append(val)

    def _log(self, *a, **kw):
        pass

    def _refresh_job_board_title(self):
        pass

    @property
    def stat_files_var(self):
        return "stat_files_var"  # sentinel

    def _simulate_add_to_job_rows(self, filepath: str):
        self._job_rows[filepath] = {"state": "waiting", "frame": types.SimpleNamespace(destroy=lambda: None)}

    def _remove_queued_file(self, filepath: str):
        row = self._job_rows.get(filepath)
        if not row or row.get("state") != "waiting":
            return
        norm_fp = self._norm_path(filepath)
        self._removed_queue_files.add(norm_fp)
        self._selected_files = [p for p in self._selected_files
                                 if self._norm_path(p) != norm_fp]
        try:
            row["frame"].destroy()
        except Exception:
            pass
        self._job_rows.pop(filepath, None)
        self._log(f"Kuyruktan çıkarıldı: {Path(filepath).name}", "info")
        self._refresh_job_board_title()
        self._set_stat(self.stat_files_var, str(len(self._job_rows)))


# ════════════════════════════════════════════════════════════════════════════
# Test cases
# ════════════════════════════════════════════════════════════════════════════

class NormPathTests(unittest.TestCase):
    """_norm_path normalizes paths for case-insensitive / slash comparison."""

    def test_same_absolute_path_equal(self):
        p = r"C:\Folder\file.srt"
        self.assertEqual(_norm_path(p), _norm_path(p))

    def test_different_case_equal_on_windows(self):
        a = r"C:\Folder\FILE.srt"
        b = r"C:\folder\file.srt"
        # On Windows normcase lowercases; on Linux it doesn't — skip if not Windows
        if os.name == "nt":
            self.assertEqual(_norm_path(a), _norm_path(b))

    def test_forward_vs_backslash_equal(self):
        a = r"C:\Folder\sub\file.srt"
        b = "C:/Folder/sub/file.srt"
        # abspath normalises slashes on Windows
        if os.name == "nt":
            self.assertEqual(_norm_path(a), _norm_path(b))


class DedupePathsTests(unittest.TestCase):

    def test_removes_exact_duplicates(self):
        paths = ["/a/b.srt", "/a/b.srt", "/a/c.srt"]
        result = _dedupe_paths(paths)
        self.assertEqual(len(result), 2)

    def test_preserves_order(self):
        paths = ["/a/1.srt", "/a/2.srt", "/a/3.srt"]
        result = _dedupe_paths(paths)
        self.assertEqual(result, paths)

    def test_empty_input(self):
        self.assertEqual(_dedupe_paths([]), [])


class RemoveQueuedFileTests(unittest.TestCase):
    """_remove_queued_file updates state correctly."""

    def _make_stub(self, files):
        stub = _QueueStub(files)
        for fp in files:
            stub._simulate_add_to_job_rows(fp)
        return stub

    def test_removal_adds_to_removed_set(self):
        fp = r"C:\sub\ep1.srt"
        stub = self._make_stub([fp])
        stub._remove_queued_file(fp)
        self.assertTrue(stub._is_queued_file_removed(fp))

    def test_removal_removes_from_selected_files(self):
        fp = r"C:\sub\ep1.srt"
        fp2 = r"C:\sub\ep2.srt"
        stub = self._make_stub([fp, fp2])
        stub._remove_queued_file(fp)
        norms = [stub._norm_path(p) for p in stub._selected_files]
        self.assertNotIn(stub._norm_path(fp), norms)
        self.assertIn(stub._norm_path(fp2), norms)

    def test_removal_updates_stat_files_var(self):
        fp1 = r"C:\sub\ep1.srt"
        fp2 = r"C:\sub\ep2.srt"
        stub = self._make_stub([fp1, fp2])
        stub._remove_queued_file(fp1)
        # The last stat call should reflect one job row left
        self.assertEqual(stub._stat_calls[-1], "1")

    def test_active_file_not_removable(self):
        fp = r"C:\sub\ep1.srt"
        stub = _QueueStub([fp])
        stub._job_rows[fp] = {"state": "active", "frame": types.SimpleNamespace(destroy=lambda: None)}
        stub._remove_queued_file(fp)
        self.assertFalse(stub._is_queued_file_removed(fp))

    def test_is_queued_file_removed_normalizes_paths(self):
        """Paths with different casing / slashes must match after removal."""
        if os.name != "nt":
            self.skipTest("Windows-only normcase test")
        fp_added   = r"C:\Sub\EP1.srt"
        fp_checked = r"c:\sub\ep1.srt"
        stub = self._make_stub([fp_added])
        stub._remove_queued_file(fp_added)
        self.assertTrue(stub._is_queued_file_removed(fp_checked))


class MultiFolderAppendTests(unittest.TestCase):
    """_append_folder_files must preserve files already in _selected_files."""

    def _make_stub_with_files(self, files):
        stub = _QueueStub(files)
        stub._is_running = False
        # input_var sentinel (not set means empty)
        stub.input_var = types.SimpleNamespace(get=lambda: "")
        return stub

    def _append(self, stub, extra_files):
        """
        Simulate what _append_folder_files does (without filesystem access):
        deduped union of existing + new.
        """
        if not stub._selected_files and stub.input_var.get():
            stub._selected_files = _dedupe_paths(stub._selected_files)
        before = len(stub._selected_files)
        stub._selected_files = _dedupe_paths(list(stub._selected_files) + extra_files)
        return len(stub._selected_files) - before

    def test_first_folder_preserved_when_second_added(self):
        existing = [r"C:\Folder1\ep1.srt", r"C:\Folder1\ep2.srt"]
        stub = self._make_stub_with_files(existing)
        added = self._append(stub, [r"C:\Folder2\ep3.srt"])
        self.assertEqual(added, 1)
        norms = [_norm_path(p) for p in stub._selected_files]
        for fp in existing:
            self.assertIn(_norm_path(fp), norms)

    def test_duplicates_not_added_twice(self):
        existing = [r"C:\Folder1\ep1.srt"]
        stub = self._make_stub_with_files(existing)
        added = self._append(stub, [r"C:\Folder1\ep1.srt", r"C:\Folder1\ep1.srt"])
        self.assertEqual(added, 0)
        self.assertEqual(len(stub._selected_files), 1)

    def test_append_to_empty_input_var_preserves_selected(self):
        """If _selected_files is non-empty and input_var is empty, keep existing."""
        existing = [r"C:\Folder1\ep1.srt"]
        stub = self._make_stub_with_files(existing)
        self._append(stub, [r"C:\Folder2\ep2.srt"])
        self.assertEqual(len(stub._selected_files), 2)


class OutputPathCollisionTests(unittest.TestCase):
    """_resolve_output_path must avoid collisions for same-stem files across different source folders."""

    def test_same_stem_different_folders_distinct_output(self):
        input_dir = r"C:\Base"
        output_dir = r"C:\Out"
        fp_a = r"C:\FolderA\ep1.srt"
        fp_b = r"C:\FolderB\ep1.srt"
        out_a = _resolve_output_path(input_dir, output_dir, fp_a)
        out_b = _resolve_output_path(input_dir, output_dir, fp_b)
        self.assertNotEqual(_norm_path(str(out_a)), _norm_path(str(out_b)),
                            f"Collision detected: both map to same output path.\n{out_a}\n{out_b}")

    def test_no_output_dir_writes_to_cikti(self):
        out = _resolve_output_path(r"C:\Base", "", r"C:\Base\ep1.srt")
        self.assertIn("ÇIKTI", str(out))

    def test_same_folder_flag_writes_to_source_parent(self):
        out = _resolve_output_path(r"C:\Base", r"C:\Out", r"C:\Base\ep1.srt",
                                   same_folder=True)
        self.assertEqual(out.parent, Path(r"C:\Base"))

    def test_input_dir_set_subfolder_preserved(self):
        """When a file is inside input_dir but in a subfolder, rel path is preserved."""
        input_dir = r"C:\Base"
        output_dir = r"C:\Out"
        fp = r"C:\Base\Season1\ep1.srt"
        out = _resolve_output_path(input_dir, output_dir, fp)
        # Should be under C:\Out\Season1\ not directly under C:\Out\
        self.assertIn("Season1", str(out))

    def test_file_outside_input_dir_uses_parent_name(self):
        """File from a different tree than input_dir gets parent folder name to avoid collision."""
        input_dir = r"C:\Series"
        output_dir = r"C:\Out"
        fp = r"C:\OtherSeries\FolderB\ep1.srt"
        out = _resolve_output_path(input_dir, output_dir, fp)
        # Should include FolderB to distinguish from another FolderA\ep1.srt
        self.assertIn("FolderB", str(out))


class WorkerLoopRemovalSkipTests(unittest.TestCase):
    """Simulate worker-loop removal checks without starting a real translation."""

    def test_removed_file_skipped_in_iteration(self):
        files = [r"C:\sub\ep1.srt", r"C:\sub\ep2.srt", r"C:\sub\ep3.srt"]
        stub = _QueueStub(files)
        for fp in files:
            stub._simulate_add_to_job_rows(fp)

        # Remove ep2 from the queue
        stub._remove_queued_file(r"C:\sub\ep2.srt")

        processed = []
        for fp in files:
            if stub._is_queued_file_removed(fp):
                continue
            processed.append(fp)

        self.assertEqual(len(processed), 2)
        self.assertNotIn(r"C:\sub\ep2.srt", processed)
        self.assertIn(r"C:\sub\ep1.srt", processed)
        self.assertIn(r"C:\sub\ep3.srt", processed)

    def test_removed_before_loop_not_processed(self):
        fp = r"C:\sub\ep1.srt"
        stub = _QueueStub([fp])
        stub._simulate_add_to_job_rows(fp)
        stub._remove_queued_file(fp)

        processed = [f for f in [fp] if not stub._is_queued_file_removed(f)]
        self.assertEqual(processed, [])


if __name__ == "__main__":
    unittest.main()
