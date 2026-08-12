import inspect
import unittest
from unittest.mock import patch

import subtitle_translator_gui as gui


class JsonlTranslationIntegrityTest(unittest.TestCase):
    def test_cross_response_duplicate_is_removed_fail_closed(self):
        translations = {}
        rejected = set()
        gui._merge_jsonl_translation_payload(
            translations, rejected, '[{"i":"1","t":"Bir."}]', {"1", "2"})
        gui._merge_jsonl_translation_payload(
            translations, rejected, '[{"i":"1","t":"Farklı."}]', {"1", "2"})

        self.assertEqual(translations, {})
        self.assertEqual(rejected, {"1"})

    def test_in_payload_duplicate_and_unknown_id_are_not_accepted(self):
        translations = {}
        rejected = set()
        parsed = gui._merge_jsonl_translation_payload(
            translations,
            rejected,
            '[{"i":"2","t":"A"},{"i":"2","t":"B"},'
            '{"i":"99","t":"Yabancı"}]',
            {"1", "2"},
        )

        self.assertEqual(translations, {})
        self.assertEqual(rejected, {"2"})
        self.assertEqual(parsed.duplicate_ids, {"2"})
        self.assertEqual(parsed.unexpected_ids, {"99"})

    def test_rejected_id_cannot_be_reintroduced_later(self):
        translations = {}
        rejected = set()
        gui._merge_jsonl_translation_payload(
            translations, rejected,
            '[{"i":"1","t":"A"},{"i":"1","t":"B"}]', {"1"})
        gui._merge_jsonl_translation_payload(
            translations, rejected, '[{"i":"1","t":"C"}]', {"1"})

        self.assertEqual(translations, {})
        self.assertEqual(rejected, {"1"})

    def test_subgroup_recovery_retries_only_conflicting_duplicate(self):
        items = [
            {"i": "1", "t": "Source one"},
            {"i": "2", "t": "Source two"},
        ]
        current = (
            '[{"i":"1","t":"Bir"},{"i":"1","t":"Başka"},'
            '{"i":"2","t":"İki"}]'
        )

        missing = gui._missing_block_items(items, current)

        self.assertEqual([str(item["i"]) for item in missing], ["1"])

    def test_subgroup_recovery_uses_central_integrity_parser(self):
        source = inspect.getsource(gui.App._resend_missing_blocks)
        self.assertIn("parse_translation_payload(current_raw, expected_ids)", source)
        self.assertNotIn("recovered[str(it[\"i\"])] = it[\"t\"]", source)


class FinalizationFailClosedTest(unittest.TestCase):
    def test_missing_dialogue_is_reinserted_and_marked(self):
        blocks = [("1", "00:00:00,000 --> 00:00:01,000", "Merhaba.")]
        cues = [
            ("1", "00:00:00,000 --> 00:00:01,000", "<i>Hello.</i>"),
            ("2", "00:00:01,000 --> 00:00:02,000", "Missing dialogue."),
        ]
        raw = {"1": "<i>Hello.</i>", "2": "Missing dialogue."}

        finalized, marked = gui._finalize_translation_blocks(
            blocks, raw, source_cues=cues)

        self.assertEqual(marked, 1)
        self.assertEqual(finalized[0][2], "<i>Merhaba.</i>")
        self.assertEqual(finalized[1][2], "[ÇEVİRİ EKSİK]")
        self.assertEqual(gui._count_hata_cps(finalized)[0], marked)

    def test_tag_restore_failure_is_not_swallowed(self):
        with patch.object(gui, "_restore_tags_blocks",
                          side_effect=RuntimeError("restore failed")):
            with self.assertRaisesRegex(RuntimeError, "restore failed"):
                gui._finalize_translation_blocks(
                    [("1", "ts", "Tamam.")], {"1": "<i>Okay.</i>"})

    def test_production_writers_finalize_before_writing(self):
        for flow in (
            gui.App._run_sync_hybrid,
            gui.App._wait_batch_hybrid,
            gui.App._write_results,
            gui.App._run_hybrid,
            gui.App._import_jsonl,
        ):
            with self.subTest(flow=flow.__name__):
                source = inspect.getsource(flow)
                finalize_pos = source.rfind("_finalize_translation_blocks(")
                write_pos = source.rfind("write_srt(")
                self.assertTrue(0 <= finalize_pos < write_pos)

    def test_jsonl_incomplete_output_is_separated_from_final(self):
        source = inspect.getsource(gui.App._import_jsonl)
        self.assertIn(
            "_write_path = _partial_output_path(out_path) if missing else Path(out_path)",
            source,
        )
        self.assertIn("_quarantine_incomplete_final(out_path)", source)
        self.assertIn("write_srt(_write_path", source)

    def test_partial_is_written_before_existing_final_is_quarantined(self):
        for flow in (
            gui.App._run_sync_hybrid,
            gui.App._write_results,
            gui.App._run_hybrid,
            gui.App._import_jsonl,
        ):
            with self.subTest(flow=flow.__name__):
                source = inspect.getsource(flow)
                write_pos = source.rfind("write_srt(")
                quarantine_pos = source.rfind("_quarantine_incomplete_final(")
                self.assertTrue(0 <= write_pos < quarantine_pos)

    def test_season_canon_guards_source_target_and_final_structure(self):
        source = inspect.getsource(gui.App._run_season_canon_audit)
        baseline_pos = source.find("output_baseline = _file_state_signature")
        finalize_pos = source.find("_finalize_translation_blocks(")
        completeness_pos = source.find("_existing_output_is_complete(")
        guard_pos = source.find("_batch_write_guard_reason(")
        write_pos = source.find("write_srt(")
        self.assertTrue(
            0 <= baseline_pos < finalize_pos < completeness_pos < guard_pos < write_pos)

    def test_partial_repair_reinserts_missing_cues_before_api_and_finalizes_after(self):
        source = inspect.getsource(gui.App._run_partial_repair_only_file)
        reinsert_pos = source.find("_reinsert_missing_dialogue_markers(")
        repair_pos = source.find("_repair_untranslated_sync(")
        finalize_pos = source.find("_finalize_translation_blocks(")
        write_pos = source.find("_write_srt_preserving_text(")
        self.assertTrue(0 <= reinsert_pos < repair_pos < finalize_pos < write_pos)

    def test_hybrid_resume_never_promotes_missing_output_to_final(self):
        source = inspect.getsource(gui.App._wait_batch_hybrid)
        finalize_pos = source.rfind("_finalize_translation_blocks(")
        missing_pos = source.find("_has_missing = _hata_n_pre > 0", finalize_pos)
        partial_pos = source.find("_partial_output_path(output_path)", missing_pos)
        write_pos = source.find("write_srt(_write_path", partial_pos)
        quarantine_pos = source.find(
            "_quarantine_incomplete_final(output_path)", write_pos)
        memory_pos = source.find("_update_resumed_series_memory(", quarantine_pos)
        self.assertTrue(
            0 <= finalize_pos < missing_pos < partial_pos < write_pos
            < quarantine_pos < memory_pos)
        self.assertIn('result_out["status"] = "failed"', source[write_pos:memory_pos])


if __name__ == "__main__":
    unittest.main()
