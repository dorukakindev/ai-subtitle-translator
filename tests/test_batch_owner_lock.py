"""Canlı batch sahiplik kilidi (_pid_alive / _live_owned_batch_ids / _write_batch_owner).

NEDEN (2026-07-16 gerçek olay): `batch_id.txt` uçuştaki bir batch ile çökmüş/sahipsiz
kalmış bir batch'i AYIRT EDEMİYOR (gönderimde yazılır, bitişte silinir). Bu yüzden bir
batch beklenirken uygulamanın ikinci bir örneği açılınca (veya App kuran bir test
çalışınca) açılış kontrolü CANLI batch'leri 'yarım kalmış' diye listeliyor; oradaki
'Seçilenleri Sil' düğmesi parası ödenmiş, hâlâ işlenen bir batch'in kurtarma verisini
siler. Kilit bunu engeller: sahibi yaşayan batch'ler pencerede gösterilmez.
"""
import json
import inspect
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import subtitle_translator_gui as gui
from app_state import STATE_DIR_ENV, state_path


def _owner_path(pid):
    return state_path(gui.__file__, f"{gui._BATCH_OWNER_PREFIX}{pid}.json")


class PidAliveTest(unittest.TestCase):
    def test_own_pid_is_alive(self):
        self.assertTrue(gui._pid_alive(os.getpid()))

    def test_invalid_pids_not_alive(self):
        for bad in (0, -1, "abc", None):
            self.assertFalse(gui._pid_alive(bad))

    def test_almost_certainly_dead_pid(self):
        # Var olmayan yüksek bir PID; Windows'ta OpenProcess başarısız olur.
        self.assertFalse(gui._pid_alive(999_999_998))

    def test_never_uses_os_kill_on_windows(self):
        # DAVRANIŞ KİLİDİ: Windows'ta os.kill süreci GERÇEKTEN ÖLDÜRÜR. _pid_alive
        # oraya asla düşmemeli — düşerse bu test os.kill'i yakalar ve patlar.
        import sys
        if sys.platform != "win32":
            self.skipTest("yalnızca Windows semantiği")
        with patch("os.kill", side_effect=AssertionError("os.kill Windows'ta ÇAĞRILMAMALI")):
            gui._pid_alive(os.getpid())
            gui._pid_alive(999_999_998)


class LiveOwnedBatchIdsTest(unittest.TestCase):
    def setUp(self):
        self._state = tempfile.TemporaryDirectory()
        self._env = patch.dict(os.environ, {STATE_DIR_ENV: self._state.name})
        self._env.start()
        self._made = []

    def tearDown(self):
        for p in self._made:
            p.unlink(missing_ok=True)
        self._env.stop()
        self._state.cleanup()

    def _write_owner(self, pid, ids, process_start=""):
        p = _owner_path(pid)
        data = {"pid": pid, "ts": 1.0, "batch_ids": ids}
        if process_start:
            data["process_start"] = process_start
        p.write_text(json.dumps(data), encoding="utf-8")
        self._made.append(p)
        return p

    def test_live_other_process_ids_are_owned(self):
        # Canlı bir pid (kendi pid'imizi 'başka süreç' gibi göstermek için getpid patch'lenir)
        self._write_owner(os.getpid(), ["batch_live1", "batch_live2"])
        with patch("os.getpid", return_value=os.getpid() + 1):  # biz 'başka' süreciz
            owned = gui._live_owned_batch_ids()
        self.assertEqual(owned, {"batch_live1", "batch_live2"})

    def test_own_pid_lock_is_ignored(self):
        self._write_owner(os.getpid(), ["batch_mine"])
        self.assertEqual(gui._live_owned_batch_ids(), set())

    def test_dead_pid_lock_ignored_and_cleaned(self):
        dead = 999_999_997
        p = self._write_owner(dead, ["batch_orphan"])
        self.assertEqual(gui._live_owned_batch_ids(), set())
        self.assertFalse(p.exists(), "ölü sürecin kilidi temizlenmeliydi")

    def test_corrupt_lock_ignored(self):
        p = _owner_path(999_999_996)
        p.write_text("{bozuk json", encoding="utf-8")
        self._made.append(p)
        self.assertEqual(gui._live_owned_batch_ids(), set())   # patlamamalı

    def test_reused_pid_marker_is_not_treated_as_live_owner(self):
        p = self._write_owner(
            os.getpid(), ["batch_stale"], process_start="win:old-process")
        with patch("os.getpid", return_value=os.getpid() + 1), \
             patch.object(gui, "_pid_alive", return_value=True), \
             patch.object(gui, "_process_start_marker", return_value="win:new-process"):
            self.assertEqual(gui._live_owned_batch_ids(), set())
        self.assertFalse(p.exists())

    def test_no_lock_files_returns_empty(self):
        # (Ortamda başka kilit olabilir; en azından patlamamalı ve set dönmeli)
        self.assertIsInstance(gui._live_owned_batch_ids(), set)


class TranslationRunOwnerTest(unittest.TestCase):
    def setUp(self):
        self._state = tempfile.TemporaryDirectory()
        self._env = patch.dict(os.environ, {STATE_DIR_ENV: self._state.name})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._state.cleanup()

    def test_second_live_process_cannot_claim_translation(self):
        owner = gui._translation_run_owner_path()
        owner.write_text(json.dumps({"pid": 424242}), encoding="utf-8")
        with patch.object(gui, "_pid_alive", return_value=True):
            self.assertFalse(gui._claim_translation_run_owner())

    def test_reused_pid_owner_is_replaced(self):
        owner = gui._translation_run_owner_path()
        owner.write_text(json.dumps({
            "pid": 424242,
            "process_start": "old-process",
        }), encoding="utf-8")
        with patch.object(gui, "_pid_alive", return_value=True), \
             patch.object(gui, "_process_start_marker", return_value="new-process"):
            self.assertTrue(gui._claim_translation_run_owner())
        self.assertEqual(
            json.loads(owner.read_text(encoding="utf-8"))["pid"], os.getpid())

    def test_current_process_claims_and_releases_translation(self):
        self.assertTrue(gui._claim_translation_run_owner())
        owner = gui._translation_run_owner_path()
        self.assertEqual(
            json.loads(owner.read_text(encoding="utf-8"))["pid"], os.getpid())
        gui._release_translation_run_owner()
        self.assertFalse(owner.exists())

    def test_pending_recovery_ids_are_detected(self):
        batch_ids = Path(self._state.name) / "batch_id.txt"
        batch_ids.write_text("batch_safe\nnot safe id\n", encoding="utf-8")
        with patch.object(gui, "_batch_id_path", return_value=batch_ids):
            self.assertEqual(gui._pending_recovery_batch_ids(), ["batch_safe"])

    def test_resume_claims_same_interprocess_owner(self):
        source = inspect.getsource(gui.App._resume)
        self.assertIn("if not _claim_translation_run_owner()", source)
        self.assertLess(
            source.index("if not _claim_translation_run_owner()"),
            source.index("self._set_running(True)"),
        )


class CheckPendingBatchesFiltersLiveTest(unittest.TestCase):
    """_check_pending_batches canlı sahipli id'ler için pencere AÇMAMALI.

    HERMETİK: gerçek batch_id.txt'ye DOKUNULMAZ — _batch_id_path patch'lenip geçici
    dosyaya yönlendirilir. (Eski testler gerçek dosyayı yedekleyip geri koyuyordu;
    canlı bir batch sürerken o pencere bile kabul edilemez.)"""

    def _run_check(self, bid_content, owned):
        import tempfile
        shown = []
        with tempfile.TemporaryDirectory() as td:
            bidp = Path(td) / "batch_id.txt"
            bidp.write_text(bid_content, encoding="utf-8")
            with patch.object(gui, "_batch_id_path", return_value=bidp), \
                 patch.object(gui, "_live_owned_batch_ids", return_value=owned), \
                 patch.object(gui.App, "_show_pending_batches_dialog",
                              lambda self, ids: shown.append(list(ids))):
                gui.App._check_pending_batches(object.__new__(gui.App))
        return shown

    def test_all_ids_live_owned_no_dialog(self):
        shown = self._run_check("batch_aaa\nbatch_bbb\n", {"batch_aaa", "batch_bbb"})
        self.assertEqual(shown, [], "canlı batch'ler için pencere AÇILMAMALIYDI")

    def test_only_unowned_ids_shown(self):
        shown = self._run_check("batch_aaa\nbatch_bbb\n", {"batch_aaa"})
        self.assertEqual(shown, [["batch_bbb"]])

    def test_no_owner_shows_all(self):
        shown = self._run_check("batch_aaa\nbatch_bbb\n", set())
        self.assertEqual(shown, [["batch_aaa", "batch_bbb"]])


if __name__ == "__main__":
    unittest.main()
