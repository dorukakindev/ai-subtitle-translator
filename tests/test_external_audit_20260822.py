# -*- coding: utf-8 -*-
"""Dış derin denetim (2026-08-22) — doğrulanıp kapatılan maddeler."""
import ast
import builtins
import importlib
import inspect
import io
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht
import subtitle_translator_gui as g

MODULES = (
    "subtitle_translator_gui", "hybrid_translate", "subtitle_formats",
    "sdh_cleaner", "series_memory", "project_memory", "translation_memory",
    "provider_retry", "app_state", "credential_store", "response_integrity",
)


class NoUndefinedLocalsTest(unittest.TestCase):
    """Madde 3: `_write_results` iki TANIMSIZ isim kullanıyordu (NameError).

    Biri BAŞARI yolundaydı: teslim SRT'si yazıldıktan hemen sonra patlıyor,
    TM kaydedilmiyor ve batch tamamlanmış sayılmıyordu. Sınıfı bir daha
    kaçırmamak için üst düzey bütün fonksiyonlar taranır.
    """

    @staticmethod
    def _bound(fn):
        names = set()
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                names.add(node.id)
            elif isinstance(node, ast.arg):
                names.add(node.arg)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                names.add(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    names.add((alias.asname or alias.name).split(".")[0])
            elif isinstance(node, (ast.Global, ast.Nonlocal)):
                names.update(node.names)
            elif isinstance(node, ast.comprehension):
                for sub in ast.walk(node.target):
                    if isinstance(sub, ast.Name):
                        names.add(sub.id)
        return names

    @staticmethod
    def _module_level(tree):
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                names.add(node.id)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    names.add((alias.asname or alias.name).split(".")[0])
        return names

    @staticmethod
    def _top_level_functions(tree):
        funcs = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs.append(node)
            elif isinstance(node, ast.ClassDef):
                funcs.extend(
                    sub for sub in node.body
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)))
        return funcs

    def test_top_level_functions_define_every_name_they_read(self):
        problems = []
        for mod_name in MODULES:
            module = importlib.import_module(mod_name)
            src = io.open(mod_name + ".py", encoding="utf-8-sig").read()
            tree = ast.parse(src)
            module_level = self._module_level(tree)
            for fn in self._top_level_functions(tree):
                bound = self._bound(fn)
                for node in ast.walk(fn):
                    if not (isinstance(node, ast.Name)
                            and isinstance(node.ctx, ast.Load)):
                        continue
                    name = node.id
                    if (name in bound or name in module_level
                            or hasattr(builtins, name)
                            or hasattr(module, name)):
                        continue
                    problems.append(
                        "%s.%s: %s (satır %d)"
                        % (mod_name, fn.name, name, node.lineno))
        self.assertEqual(problems, [])


class NegationGuardTest(unittest.TestCase):
    """Madde 7: olumsuzluk guard'ı sıradan isimlerle sağlanıyordu."""

    ORDINARY = ("Bu sinema.", "O öğretmen.", "Bu bir elma.", "Zaman geldi.",
                "Orman yandı.", "Duman var.", "Liman kapalı.", "Tema güzel.")
    NEGATIVE = ("Bu sinema değil.", "Gelmedi.", "Bilmiyorum.", "Asla olmaz.",
                "Hiç yok.", "Gitmeyecek.")

    def test_ordinary_nouns_carry_no_reliable_negation(self):
        for text in self.ORDINARY:
            with self.subTest(text=text):
                self.assertEqual(ht.reliable_turkish_negation_count(text), 0)

    def test_real_negation_is_counted(self):
        for text in self.NEGATIVE:
            with self.subTest(text=text):
                self.assertGreaterEqual(
                    ht.reliable_turkish_negation_count(text), 1)

    def test_dropping_degil_is_rejected_by_both_validators(self):
        cases = (
            ("This is not a cinema.", "Bu sinema değil.", "Bu sinema."),
            ("He is not a teacher.", "O öğretmen değil.", "O öğretmen."),
            ("This is not an apple.", "Bu bir elma değil.", "Bu bir elma."),
            ("He did not come.", "O gelmedi.", "O geldi."),
        )
        for src, old, new in cases:
            with self.subTest(old=old):
                ok, reason = ht.validate_polish_candidate(
                    old, new, source_text=src, tgt_lang="Turkish")
                self.assertFalse(ok)
                self.assertEqual(reason, "source_negation")
                ok, reason = ht.validate_condense_candidate(
                    old, new, source_text=src, tgt_lang="Turkish")
                self.assertFalse(ok)
                self.assertEqual(reason, "source_negation")

    def test_legitimate_repairs_still_pass(self):
        cases = (
            ("This is not a cinema.", "Bu sinema deil.", "Bu sinema değil."),
            ("He did not come.", "O gelmedi ki.", "O gelmedi."),
            ("I do not know.", "Ben bilmiyorum.", "Bilmiyorum."),
        )
        for src, old, new in cases:
            with self.subTest(old=old):
                ok, reason = ht.validate_polish_candidate(
                    old, new, source_text=src, tgt_lang="Turkish")
                self.assertTrue(ok, reason)


class AccentRepairIsNotDriftTest(unittest.TestCase):
    """Aksan onarımı içerik sürüklenmesi/kaybı sayılmamalı."""

    def test_ascii_folded_equal_words_are_the_same_word(self):
        ok, reason = ht.validate_polish_candidate(
            "Kopegi gordum.", "Köpeği gördüm.",
            source_text="I saw the dog.", tgt_lang="Turkish")
        self.assertTrue(ok, reason)

    def test_real_content_loss_is_still_rejected(self):
        ok, reason = ht.validate_polish_candidate(
            "Büyük köpeği orada gördüm.", "Köpeği gördüm.",
            source_text="I saw the big dog there.", tgt_lang="Turkish")
        self.assertFalse(ok)
        self.assertEqual(reason, "content_word_loss")


class BatchOwnershipTest(unittest.TestCase):
    """Madde 1/2: ücretli batch kayıtları korunmalı, hash dosyaya ait olmalı."""

    def test_resume_can_be_scoped_without_touching_the_store(self):
        self.assertIn("only_batch_ids", inspect.signature(g.App._resume).parameters)

    def test_the_pending_dialog_no_longer_clears_unselected(self):
        source = inspect.getsource(g.App._show_pending_batches_dialog)
        marker = source.index("_resume(only_batch_ids=")
        window = source[max(0, marker - 900):marker]
        self.assertNotIn("_clear_batch_recovery", window)
        self.assertNotIn("replace=selected", window)

    def test_completed_entry_uses_the_per_file_hash(self):
        # Faz-2 tamamlama kaydı: dosyanın KENDİ hash'i yazılmalı.
        # Faz-1'deki `_expected_source_hash` kullanımları DOĞRUDUR (o an
        # işlenen dosyaya aittir); hata yalnız Faz-2 tamamlama kaydındaydı.
        source = io.open(
            "subtitle_translator_gui.py", encoding="utf-8").read()
        marker = source.index(
            'session, filepath, "completed", out_path=out_path,')
        window = source[marker:marker + 900]
        self.assertIn("source_hash=expected_source_hash,", window)


class CancelNeedsTerminalStatusTest(unittest.TestCase):
    """Madde 6: iptal kabul edilmesi terminal durum demek değildir."""

    @staticmethod
    def _status_of(value):
        client = MagicMock()
        client.batches.retrieve.return_value = SimpleNamespace(status=value)
        return g.App._remote_batch_terminal_status(None, client, "batch_A")

    def test_only_terminal_states_are_accepted(self):
        for terminal in ("cancelled", "failed", "expired", "completed"):
            with self.subTest(status=terminal):
                self.assertEqual(self._status_of(terminal), terminal)
        for pending in ("cancelling", "in_progress", "validating", "finalizing"):
            with self.subTest(status=pending):
                self.assertIsNone(self._status_of(pending))

    def test_unreadable_status_is_treated_as_not_terminal(self):
        client = MagicMock()
        client.batches.retrieve.side_effect = RuntimeError("offline")
        self.assertIsNone(
            g.App._remote_batch_terminal_status(None, client, "batch_A"))


if __name__ == "__main__":
    unittest.main()
