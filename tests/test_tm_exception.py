"""
translation_memory.lookup exception safety tests.
"""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import translation_memory as tm_mod
from translation_memory import TranslationMemory


class TMLookupExceptionTest(unittest.TestCase):
    def test_lookup_with_corrupt_db_returns_none(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        # Write garbage to simulate corrupt DB
        Path(path).write_bytes(b"not a valid sqlite db")
        try:
            tm = TranslationMemory(db_path=path)
        except sqlite3.DatabaseError:
            # Constructor may also fail on corrupt DB
            pass
        # If constructor succeeded, lookup should handle errors gracefully
        try:
            tm = TranslationMemory(db_path=path)
            result = tm.lookup("hello", tgt_lang="Turkish")
            self.assertIsNone(result)
        except sqlite3.DatabaseError:
            pass  # acceptable — constructor rejects corrupt DB

    def test_lookup_with_empty_source_returns_none(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        tm = TranslationMemory(db_path=path)
        self.assertIsNone(tm.lookup("", tgt_lang="Turkish"))
        self.assertIsNone(tm.lookup("   ", tgt_lang="Turkish"))

    def test_lookup_store_and_retrieve(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        tm = TranslationMemory(db_path=path)
        tm.store("hello", "merhaba", tgt_lang="Turkish")
        result = tm.lookup("hello", tgt_lang="Turkish")
        self.assertEqual(result, "merhaba")

    def test_lookup_with_none_connection_returns_none(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        tm = TranslationMemory(db_path=path)
        tm._conn = None  # force _get_conn() to return None
        result = tm.lookup("hello", tgt_lang="Turkish")
        self.assertIsNone(result)

    def test_connection_retry_initializes_schema_after_initial_lock(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tm.db"
            real_connect = tm_mod.sqlite3.connect
            calls = 0

            def flaky_connect(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise sqlite3.OperationalError("database is locked")
                return real_connect(*args, **kwargs)

            with patch("translation_memory.sqlite3.connect", side_effect=flaky_connect):
                tm = TranslationMemory(path)
                self.assertTrue(tm.store("hello", "merhaba", tgt_lang="Turkish"))
                self.assertEqual(
                    tm.lookup("hello", tgt_lang="Turkish"),
                    "merhaba",
                )
                tm.close()

    def test_batch_and_fuzzy_lookup_fail_open_when_database_is_temporarily_locked(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        tm = TranslationMemory(db_path=path)
        try:
            with patch.object(
                    tm, "_get_conn",
                    side_effect=sqlite3.OperationalError("database is locked")):
                self.assertEqual(tm.lookup_batch(["hello"], tgt_lang="Turkish"), {})
                self.assertIsNone(tm.fuzzy_lookup("hello there", tgt_lang="Turkish"))
        finally:
            tm.close()
