import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import hybrid_translate as ht


class BatchRecoveryLostPersiaTests(unittest.TestCase):
    def _mkout(self):
        fd, path = tempfile.mkstemp(suffix=".srt")
        os.close(fd)
        return path

    def test_salvage_json_objects_keeps_complete_items_only(self):
        raw = '[{"i":514,"t":"Bu sat\u0131r tamam"},{"i":515,"t":"Marduk onu se\u00e7ti"},{"i":516,"t":"yar\u0131m'
        out = ht._salvage_json_objects(raw)
        self.assertEqual([x["i"] for x in out], [514, 515])
        self.assertEqual(out[1]["t"], "Marduk onu se\u00e7ti")

    def test_save_results_salvages_truncated_batch_chunk(self):
        out_path = self._mkout()
        log_calls = []

        def log_fn(msg, level="info"):
            log_calls.append((level, msg))

        raw_translation = '[{"i":514,"t":"Cyrus me\u015fru bir h\u00fck\u00fcmdar oldu\u011funu g\u00f6sterir."},{"i":515,"t":"Marduk onu y\u00f6netmesi i\u00e7in se\u00e7mi\u015ftir."},{"i":516,"t":"yar\u0131m'
        response_line = {
            "custom_id": "chunk_513",
            "response": {
                "body": {
                    "choices": [{"message": {"content": raw_translation}}],
                    "usage": {"total_tokens": 10},
                }
            },
        }
        mock_client = mock.MagicMock()
        mock_client.files.content.return_value.text = json.dumps(response_line, ensure_ascii=False)
        file_map = {
            "chunk_513": [
                (514, "00:00:01,000", "00:00:02,000"),
                (515, "00:00:02,000", "00:00:03,000"),
                (516, "00:00:03,000", "00:00:04,000"),
            ]
        }
        cues = [
            SimpleNamespace(index=514, text="In this line, Cyrus is trying to show that he's a legitimate ruler,"),
            SimpleNamespace(index=515, text="the God Marduk himself chose him to rule."),
            SimpleNamespace(index=516, text="But Cyrus doesn't just use the foreign religion"),
        ]

        try:
            with mock.patch("openai.OpenAI", return_value=mock_client):
                count, n_marked = ht.save_results(
                    openai_api_key="fake",
                    output_file_id="fid",
                    file_map=file_map,
                    output_path=out_path,
                    log_fn=log_fn,
                    src_cues=cues,
                )
            written = Path(out_path).read_text(encoding="utf-8")
            self.assertEqual(count, 3)
            self.assertEqual(n_marked, 1)
            self.assertIn("Cyrus me\u015fru bir h\u00fck\u00fcmdar", written)
            self.assertIn("Marduk onu y\u00f6netmesi", written)
            self.assertIn("[\u00c7EV\u0130R\u0130 EKS\u0130K]", written)
            self.assertTrue(any("JSON k\u0131smi kurtar\u0131ld\u0131" in msg for _level, msg in log_calls))
        finally:
            Path(out_path).unlink(missing_ok=True)

    def test_final_write_cleanup_common_documentary_residue(self):
        text = "[Ali speaking]\n21 feet mesafe var. Babylon b\u00fcy\u00fckt\u00fc."
        out = ht._normalize_output_text(text)
        self.assertIn("[Ali konu\u015fuyor]", out)
        self.assertIn("21 fit", out)
        self.assertIn("Babil", out)
        self.assertNotIn("speaking", out)
        self.assertNotIn("feet", out)
        self.assertNotIn("Babylon", out)

    def test_neighbor_start_duplicate_is_flagged(self):
        blocks = [
            (122, "00:00:01,000 --> 00:00:02,000", "Yunanlar ayr\u0131ca \u015fu efsanevi metropol\u00fcn hazinelerle dolu oldu\u011funu s\u00f6ylerler."),
            (123, "00:00:02,000 --> 00:00:03,000", "Yunanlar ayr\u0131ca \u015fu efsanevi metropol\u00fcn ak\u0131l almaz zenginliklerle dolu oldu\u011funu s\u00f6ylerler."),
        ]
        hits = ht.run_validators(blocks)
        self.assertTrue(any(reason == "NEIGHBOR_PREFIX_ECHO" for *_rest, reason in hits))


if __name__ == "__main__":
    unittest.main()
