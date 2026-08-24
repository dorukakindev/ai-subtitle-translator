# -*- coding: utf-8 -*-
"""Tanımsız isim = çalışma anında çökme. Ruff bunu saniyede yakalıyor."""
import os
import shutil
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ruff kuralları:
#   F821 tanımsız isim   — NameError/UnboundLocalError
#   F811 yeniden tanım   — sessizce ezilen fonksiyon
#   E9   sözdizimi       — dosya hiç içe aktarılamaz
#   W605 geçersiz kaçış  — bozuk regex ('\d' yerine r'\d')
RULES = "F821,F811,E9,W605"

MODULES = (
    "subtitle_translator_gui.py", "hybrid_translate.py", "subtitle_formats.py",
    "provider_retry.py", "series_memory.py", "project_memory.py",
    "translation_memory.py", "sdh_cleaner.py", "helper_models.py",
    "prompt_constants.py", "credential_store.py", "response_integrity.py",
    "app_state.py", "video_subtitles.py", "subtitle_batch_translate.py",
    "repair_batches.py", "request_cancellation.py", "folder_picker.py",
)


class NoUndefinedNamesTest(unittest.TestCase):
    """2026-08-24'te ruff üç gerçek çökme buldu; hiçbiri teste yakalanmıyordu:

    - `do_linebrk` (_import_jsonl) başka bir metotta tanımlıydı → NameError
    - `schema_dict` (_run_sync_hybrid) atanmadan 44 satır önce okunuyordu
      → UnboundLocalError
    - `_expected_source_hash` (_run_hybrid) o akışta hiç atanmıyordu
      → NameError

    Üçü de ayrı bir akışta, yani normal koşuda görünmüyorlardı. Bu test
    onların geri sızmasını engeller.
    """

    def test_ruff_is_available(self):
        if shutil.which("ruff") is None:
            self.skipTest("ruff kurulu değil: python -m pip install ruff")

    def test_no_module_has_an_undefined_name(self):
        if shutil.which("ruff") is None:
            self.skipTest("ruff kurulu değil")
        present = [m for m in MODULES
                   if os.path.exists(os.path.join(ROOT, m))]
        self.assertTrue(present, "denetlenecek modül bulunamadı")
        result = subprocess.run(
            ["ruff", "check", f"--select={RULES}", "--output-format=concise",
             *present],
            cwd=ROOT, capture_output=True, text=True)
        if result.returncode != 0:
            self.fail(
                "Ruff gerçek hata buldu (tanımsız isim / yeniden tanım / "
                "sözdizimi / bozuk kaçış):\n" + (result.stdout or result.stderr))

    def test_the_tests_themselves_are_clean(self):
        if shutil.which("ruff") is None:
            self.skipTest("ruff kurulu değil")
        result = subprocess.run(
            ["ruff", "check", f"--select={RULES}", "--output-format=concise",
             "tests"],
            cwd=ROOT, capture_output=True, text=True)
        if result.returncode != 0:
            self.fail("Testlerde gerçek hata:\n"
                      + (result.stdout or result.stderr))


if __name__ == "__main__":
    unittest.main()
