import json
import os
import unittest
from unittest.mock import patch

import hybrid_translate as ht
import subtitle_translator_gui as gui
from app_state import STATE_DIR_ENV


class FmapLoadStatusTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self._env = patch.dict(os.environ, {STATE_DIR_ENV: self._td.name})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._td.cleanup()

    def _write(self, batch_id, value):
        path = ht._batch_fmap_path(batch_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, str):
            path.write_text(value, encoding="utf-8")
        else:
            path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_detailed_loader_distinguishes_missing_invalid_and_empty(self):
        self.assertEqual(
            ht.load_fmap_for_batch("batch_missing", detailed=True),
            ("missing", None),
        )

        corrupt = self._write("batch_corrupt", "{not json")
        self.assertEqual(
            ht.load_fmap_for_batch("batch_corrupt", detailed=True),
            ("invalid_json", None),
        )
        self.assertTrue(corrupt.exists())

        self._write("batch_schema", {"fmap": {"cid": "not-a-list"}})
        self.assertEqual(
            ht.load_fmap_for_batch("batch_schema", detailed=True),
            ("invalid_schema", None),
        )

        self._write("batch_empty", {"fmap": {}})
        self.assertEqual(
            ht.load_fmap_for_batch("batch_empty", detailed=True),
            ("valid_empty", {}),
        )

    def test_valid_fmap_is_converted_to_tuples(self):
        self._write("batch_ok", {"fmap": {"cid": [["1", "start", "end"]]}})
        status, fmap = ht.load_fmap_for_batch("batch_ok", detailed=True)
        self.assertEqual(status, "ok")
        self.assertEqual(fmap, {"cid": [("1", "start", "end")]})
        self.assertEqual(ht.load_fmap_for_batch("batch_ok"), fmap)


class SavedRegularRequestSafetyTest(unittest.TestCase):
    def test_legacy_fmap_without_requests_is_not_rebuilt_from_ui(self):
        requests, reason = gui._saved_regular_requests(
            {"type": "regular", "fmap": {"cid": []}},
            {"cid": []},
        )
        self.assertIsNone(requests)
        self.assertEqual(reason, "missing_requests")

    def test_request_ids_must_cover_saved_fmap(self):
        requests, reason = gui._saved_regular_requests(
            {"requests": [{"custom_id": "other"}]},
            {"cid": []},
        )
        self.assertIsNone(requests)
        self.assertEqual(reason, "id_mismatch")

    def test_matching_saved_requests_are_reused(self):
        saved = [{"custom_id": "cid", "body": {"messages": []}}]
        requests, reason = gui._saved_regular_requests(
            {"requests": saved},
            {"cid": []},
        )
        self.assertIs(requests, saved)
        self.assertEqual(reason, "")


if __name__ == "__main__":
    unittest.main()
