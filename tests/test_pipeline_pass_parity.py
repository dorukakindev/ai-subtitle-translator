import ast
import textwrap
import unittest
from unittest.mock import MagicMock, patch
import inspect
import subtitle_translator_gui as gui


class PipelinePassParityTest(unittest.TestCase):

    def test_quality_passes_receive_run_scene_gap(self):
        names = {
            "critic_pass_with_helper",
            "native_reader_pass",
            "semantic_reconciliation_pass",
        }
        found = 0
        tree = ast.parse(textwrap.dedent(inspect.getsource(gui.App)))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", "")
            if name not in names:
                continue
            found += 1
            self.assertIn(
                "scene_gap_sec",
                {keyword.arg for keyword in node.keywords},
                f"line {node.lineno}: {name}",
            )
        self.assertEqual(found, 11)

    def test_post_process_resolves_real_source_without_reusing_target(self):
        """Existing translated SRT must not be reused as its own source."""
        src = inspect.getsource(gui.App._run_post_process)
        self.assertNotIn("_store_tm_pairs", src, "post-process must not store translation-to-translation TM pairs")
        self.assertIn("source_path = _resolve_postprocess_source(fp)", src)
        self.assertIn("ht.load_subtitle(str(source_path), source_language)", src)
        self.assertIn("analysis_result = None", src)
        self.assertNotIn("ht.load_subtitle(fp)", src)
        self.assertNotIn("ht.load_context_cache(", src)
        self.assertIn("source_driven=False", src)
        self.assertIn("if do_critic and orig_cues:", src)
        self.assertIn("if do_polish and orig_cues:", src)
        self.assertIn("if do_native and orig_cues:", src)
        self.assertIn("if do_qc and orig_cues:", src)
        self.assertIn("QC atlandı: post-işlemde gerçek kaynak altyazı seçilmedi.", src)

    def test_write_results_condense_order(self):
        """Verify _maybe_condense runs after critic/polish/native in _write_results."""
        src = inspect.getsource(gui.App._write_results)
        condense_pos = src.find("_maybe_condense")
        critic_pos = src.find("ht.critic_pass_with_helper")
        self.assertGreater(condense_pos, critic_pos, "In _write_results, _maybe_condense must run after critic_pass_with_helper!")

    def test_hata_unresolved_check_before_pre_pass_and_quality_passes(self):
        """[HATA] count must run before it is converted to a visible marker."""
        src = inspect.getsource(gui.App._run_hybrid)
        unresolved_pos = src.find("_unresolved_missing = sum(")
        fill_pos = src.find("_finalize_translation_blocks")
        critic_pos = src.find("ht.critic_pass_with_helper")
        self.assertGreater(fill_pos, unresolved_pos, "finalization must not hide unresolved markers")
        self.assertLess(unresolved_pos, critic_pos, "_unresolved_missing must be checked before ht.critic_pass_with_helper!")

    def test_write_results_uses_canonical_tail_order_and_review_gate(self):
        src = inspect.getsource(gui.App._write_results)
        condense_pos = src.find("_maybe_condense")
        sdh_pos = src.find("clean_sdh")
        linebreak_pos = src.find("apply_line_breaks")
        qc_pos = src.find("_run_quality_check_inline")
        finalize_pos = src.find("_finalize_translation_blocks")
        self.assertTrue(condense_pos < sdh_pos < linebreak_pos < qc_pos < finalize_pos)
        self.assertNotIn("ht.qc_auto_fix", src, "plain batch QC must retain severity split and user review")

    def test_resume_qc_counters_record_applied_diffs(self):
        src = inspect.getsource(gui.App._wait_batch_hybrid)
        self.assertNotIn("_qc_fixes += len(", src)
        self.assertNotIn("_qc_auto_fixes += len(", src)

    def test_qc_counters_record_applied_diffs(self):
        """Verify QC counters use _record_pass_change rather than issue count."""
        src_sh = inspect.getsource(gui.App._run_sync_hybrid)
        src_rh = inspect.getsource(gui.App._run_hybrid)
        
        self.assertIn("_n_auto = _record_pass_change", src_sh, "_run_sync_hybrid must record actual QC auto changes!")
        self.assertIn("_n_auto = _record_pass_change", src_rh, "_run_hybrid must record actual QC auto changes!")

    def test_plain_report_records_actual_pass_and_qc_changes(self):
        src = inspect.getsource(gui.App._write_results)
        self.assertIn("_pass_fix = sum(", src)
        self.assertIn('stats=_qc_stats', src)
        self.assertIn('"pass_fix": _pass_fix', src)
        self.assertIn('"qc_auto": _qc_stats["qc_auto"]', src)
        self.assertIn('"qc": _qc_stats["qc"]', src)

    def test_batch_consistency_status_is_initialized_and_reported(self):
        for flow in (gui.App._write_results, gui.App._run_hybrid):
            with self.subTest(flow=flow.__name__):
                src = inspect.getsource(flow)
                consistency_pos = src.find("ht.consistency_sweep(")
                self.assertGreaterEqual(consistency_pos, 0)
                self.assertLess(src.find("_pass_status = {}"), consistency_pos)
                self.assertIn('_pass_status["Consistency"]', src)

    def test_final_semantic_checks_have_four_flow_parity(self):
        flows = [
            gui.App._run_sync_hybrid,
            gui.App._wait_batch_hybrid,
            gui.App._write_results,
            gui.App._run_hybrid,
        ]
        for flow in flows:
            with self.subTest(flow=flow.__name__):
                src = inspect.getsource(flow)
                semantic_pos = src.rfind("_run_final_semantic_checks(")
                finalize_pos = src.rfind("_finalize_translation_blocks(")
                self.assertGreaterEqual(semantic_pos, 0)
                self.assertTrue(semantic_pos < finalize_pos)
                self.assertIn('changed_ids=_pass_history.keys()', src)

    def test_final_quality_scans_receive_locked_terms_and_source_language(self):
        flows = [
            gui.App._run_sync_hybrid,
            gui.App._wait_batch_hybrid,
            gui.App._write_results,
            gui.App._run_hybrid,
        ]
        for flow in flows:
            with self.subTest(flow=flow.__name__):
                tree = ast.parse(textwrap.dedent(inspect.getsource(flow)))
                calls = [
                    node for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and getattr(node.func, "id", "") == "scan_translation_quality"
                ]
                self.assertEqual(len(calls), 1)
                keywords = {keyword.arg for keyword in calls[0].keywords}
                self.assertIn("locked_terms", keywords)
                self.assertIn("source_language", keywords)

    def test_term_normalize_precedes_canonical_tail_in_all_four_flows(self):
        flows = [
            gui.App._run_sync_hybrid,
            gui.App._wait_batch_hybrid,
            gui.App._write_results,
            gui.App._run_hybrid,
        ]
        for flow in flows:
            with self.subTest(flow=flow.__name__):
                src = inspect.getsource(flow)
                normalize_pos = src.rfind("_normalize_mixed_terms(")
                finalize_pos = src.rfind("_finalize_translation_blocks(")
                self.assertTrue(normalize_pos < finalize_pos)

    def test_plain_sync_without_chain_can_run_opt_in_review(self):
        src = inspect.getsource(gui.App._write_results)
        self.assertIn('or not App._run_setting(', src)
        self.assertIn('"chain_ctx", "chain_ctx_var", True', src)
        self.assertIn("ek API maliyeti", src)

    def test_final_sdh_cleanup_is_terminal_in_all_quality_flows(self):
        flows = [
            gui.App._run_sync_hybrid,
            gui.App._wait_batch_hybrid,
            gui.App._write_results,
            gui.App._run_hybrid,
        ]
        for flow in flows:
            with self.subTest(flow=flow.__name__):
                src = inspect.getsource(flow)
                semantic_pos = src.rfind("_run_final_semantic_checks(")
                final_sdh_pos = src.rfind('"Final-SDH"')
                finalize_pos = src.rfind("_finalize_translation_blocks(")
                self.assertTrue(semantic_pos < final_sdh_pos < finalize_pos)

    def test_jsonl_import_repeats_source_driven_sdh_after_polish(self):
        src = inspect.getsource(gui.App._import_jsonl)
        polish_pos = src.find("self._polish_pass(")
        terminal_sdh_pos = src.rfind("source_driven=True")
        finalize_pos = src.rfind("_finalize_translation_blocks(")
        self.assertTrue(polish_pos < terminal_sdh_pos < finalize_pos)

    def test_jsonl_import_first_sdh_pass_is_source_driven(self):
        src = inspect.getsource(gui.App._import_jsonl)
        first_sdh_pos = src.find("blocks = clean_sdh(")
        polish_pos = src.find("self._polish_pass(")
        first_call = src[first_sdh_pos:polish_pos]
        self.assertGreaterEqual(first_sdh_pos, 0)
        self.assertIn("src_map=_src_map_from_cues(cues)", first_call)
        self.assertIn("source_driven=True", first_call)

    def test_jsonl_import_loads_consistency_module_before_polish_sweep(self):
        src = inspect.getsource(gui.App._import_jsonl)
        import_pos = src.find("import hybrid_translate as ht")
        sweep_pos = src.find("ht.final_consistency_sweep(")
        self.assertTrue(0 <= import_pos < sweep_pos)

    def test_plain_batch_report_does_not_claim_helper_analysis(self):
        src = inspect.getsource(gui.App._write_results)
        self.assertIn('"helper_analysis": False', src)
        self.assertIn('"analysis_status": "kapalı (düz batch)"', src)
        self.assertIn('"translation_chunks": _translation_chunks', src)

    def test_hybrid_reports_include_actual_analysis_and_chain_state(self):
        flows = (
            gui.App._run_sync_hybrid,
            gui.App._wait_batch_hybrid,
            gui.App._run_hybrid,
        )
        for flow in flows:
            with self.subTest(flow=flow.__name__):
                src = inspect.getsource(flow)
                self.assertIn('"helper_analysis": True', src)
                self.assertIn('"analysis_status":', src)
                self.assertIn('"chain_ctx":', src)
                self.assertIn('"translation_chunks":', src)

    def test_hybrid_final_tail_reuses_single_raw_map(self):
        src = inspect.getsource(gui.App._run_hybrid)
        tail = src[src.rfind("_run_final_semantic_checks("):src.find(
            "write_srt(", src.rfind("_run_final_semantic_checks(")
        )]
        self.assertEqual(tail.count("_raw_src_map_from_cues(cues)"), 1)

    def test_normal_flows_run_term_normalization_before_final_semantic(self):
        for flow in (gui.App._run_sync_hybrid, gui.App._write_results,
                     gui.App._run_hybrid):
            with self.subTest(flow=flow.__name__):
                src = inspect.getsource(flow)
                self.assertLess(
                    src.rfind("_normalize_mixed_terms("),
                    src.rfind("_run_final_semantic_checks("),
                )

    def test_hybrid_batch_final_semantic_receives_full_analysis_and_locks(self):
        src = inspect.getsource(gui.App._run_hybrid)
        call_start = src.rfind("_run_final_semantic_checks(")
        call = src[call_start:call_start + 600]
        self.assertIn("locked_terms=_locked_terms", call)
        self.assertIn("analysis_result=_full_analysis", call)

    def test_sync_hybrid_locks_analysis_terms_for_all_quality_passes(self):
        src = inspect.getsource(gui.App._run_sync_hybrid)
        self.assertIn("_analysis_locked_terms = ht.sanitize_glossary_for_turkish", src)
        self.assertIn("**self._get_locked_terms_dict(filepath, tgt)", src)
        self.assertGreaterEqual(src.count("locked_terms=_locked_terms"), 6)
        self.assertIn("glossary=_locked_terms", src)
        self.assertIn("locked_terms=_locked_terms)", src)

    def test_sync_hybrid_critic_receives_all_analysis_fields(self):
        src = inspect.getsource(gui.App._run_sync_hybrid)
        call_start = src.find("ht.critic_pass_with_helper(")
        call = src[call_start:call_start + 1400]
        for name in (
                "context", "char_examples", "pronoun_map", "character_styles",
                "scene_emotions", "idiom_map", "cultural_refs"):
            self.assertIn(name, call)

    def test_sync_hybrid_commits_analysis_memory_only_after_final_write(self):
        src = inspect.getsource(gui.App._run_sync_hybrid)
        write_pos = src.find("write_srt(")
        pm_pos = src.find("_file_pm.merge_glossary_from_analysis(")
        series_pos = src.find("self._update_series_memory_from_analysis(")
        self.assertTrue(write_pos < pm_pos < series_pos)
        self.assertNotIn("self._stage_series_memory_from_analysis(", src)

    def test_hybrid_batch_commits_project_memory_only_after_quality_success(self):
        src = inspect.getsource(gui.App._run_hybrid)
        success_pos = src.find("if (not _hybrid_quality_failed and analysis_ok")
        pm_pos = src.find("_file_pm.merge_glossary_from_analysis(")
        complete_pos = src.find(
            'ht.update_batch_session(\n                    session, filepath, "completed"')

        self.assertTrue(0 <= success_pos < pm_pos < complete_pos)
        self.assertEqual(src.count("_file_pm.merge_glossary_from_analysis("), 1)

    def test_hybrid_batch_reuses_only_source_bound_delivery_and_writes_binding(self):
        src = inspect.getsource(gui.App._run_hybrid)
        existing_pos = src.find("_output_matches_source_fingerprint(")
        analysis_pos = src.find("ht.analyze_with_helper(")
        write_pos = src.find("write_srt(_write_path")
        fingerprint_pos = src.find(
            "_write_output_source_fingerprint(", write_pos)
        delivery_pos = src.find("_delivery_scan_failed = not _fingerprint_ok")

        self.assertTrue(0 <= existing_pos < analysis_pos)
        self.assertTrue(0 <= write_pos < fingerprint_pos < delivery_pos)

    def test_chain_retries_invalid_chunk_before_building_next_context(self):
        for flow in (gui.App._run_sync, gui.App._run_sync_hybrid):
            with self.subTest(flow=flow.__name__):
                src = inspect.getsource(flow)
                invalid_pos = src.find("if _chunk_response_retry_reason(text, req):")
                retry_pos = src.find("self._retry_hata(", invalid_pos)
                pair_pos = src.find("_chain_pairs_from_result(", retry_pos)
                self.assertTrue(0 <= invalid_pos < retry_pos < pair_pos)

    def test_plain_sync_freezes_precontext_terms_for_quality_passes(self):
        src = inspect.getsource(gui.App._run_sync)
        self.assertIn('_precontext_locked_terms = {}', src)
        self.assertIn('pre_data.get("terms")', src)
        self.assertIn('locked_terms_by_file=', src)
        self.assertIn('_precontext_locked_terms', src)


if __name__ == "__main__":
    unittest.main()
