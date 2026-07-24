import json
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import subtitle_translator_gui as gui


def _response(content, tokens=7):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(total_tokens=tokens),
    )


class SourceLanguageDetectionTest(unittest.TestCase):
    def test_normalize_display_name_code_and_auto(self):
        self.assertEqual(gui.normalize_language_name("spanish"), "Spanish")
        self.assertEqual(gui.normalize_language_name("it"), "Italian")
        self.assertEqual(gui.normalize_language_name("automatic"), gui.AUTO_LANGUAGE)
        self.assertEqual(gui.normalize_language_name("xx", allow_auto=False), "")

    def test_detector_returns_supported_json_language(self):
        with patch.object(
            gui, "_safe_chat_create",
            return_value=_response(json.dumps({"language": "Spanish"})),
        ):
            detected = gui.detect_source_language_with_ai(
                object(), [("1", "00:00:00,000 --> 00:00:01,000", "¿Cómo estás?")],
                "test-model", filename="uno.srt")
        self.assertEqual(detected, "Spanish")

    def test_detector_accepts_iso_code(self):
        with patch.object(
            gui, "_safe_chat_create",
            return_value=_response(json.dumps({"language": "it"})),
        ):
            detected = gui.detect_source_language_with_ai(
                object(), [("1", "", "Come stai?")], "test-model")
        self.assertEqual(detected, "Italian")

    def test_detector_rejects_unsupported_language(self):
        with patch.object(
            gui, "_safe_chat_create",
            return_value=_response(json.dumps({"language": "Esperanto"})),
        ):
            detected = gui.detect_source_language_with_ai(
                object(), [("1", "", "Saluton")], "test-model")
        self.assertEqual(detected, gui.AUTO_LANGUAGE)

    def test_batch_detector_maps_each_file_independently(self):
        response = {"languages": {"0": "Spanish", "1": "Italian"}}
        with patch.object(
            gui, "_safe_chat_create",
            return_value=_response(json.dumps(response)),
        ):
            detected = gui.detect_source_languages_batch_with_ai(
                object(),
                {
                    "uno.srt": [("1", "", "¿Cómo estás?")],
                    "due.srt": [("1", "", "Come stai?")],
                },
                "test-model",
            )
        self.assertEqual(
            detected, {"uno.srt": "Spanish", "due.srt": "Italian"})

    def test_batch_detector_leaves_missing_id_as_auto(self):
        with patch.object(
            gui, "_safe_chat_create",
            return_value=_response(json.dumps({"languages": {"0": "Spanish"}})),
        ):
            detected = gui.detect_source_languages_batch_with_ai(
                object(),
                {
                    "uno.srt": [("1", "", "Hola")],
                    "due.srt": [("1", "", "Ciao")],
                },
                "test-model",
            )
        self.assertEqual(detected["uno.srt"], "Spanish")
        self.assertEqual(detected["due.srt"], gui.AUTO_LANGUAGE)

    def test_detector_empty_input_does_not_call_api(self):
        with patch.object(gui, "_safe_chat_create") as call:
            detected = gui.detect_source_language_with_ai(
                object(), [], "test-model")
        self.assertEqual(detected, gui.AUTO_LANGUAGE)
        call.assert_not_called()

    def test_worker_reads_file_language_from_snapshot(self):
        stub = SimpleNamespace(
            _active_snapshot={
                "src_lang": gui.AUTO_LANGUAGE,
                "file_source_languages": {"a.srt": "Italian"},
            },
            _file_language_vars={
                "a.srt": SimpleNamespace(
                    get=lambda: (_ for _ in ()).throw(
                        AssertionError("worker must not read Tk variable"))
                )
            },
            src_var=SimpleNamespace(
                get=lambda: (_ for _ in ()).throw(
                    AssertionError("worker must not read global Tk variable"))
            ),
        )
        result = {}

        def worker():
            result["language"] = gui.App._get_file_source_language(stub, "a.srt")

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        self.assertEqual(result["language"], "Italian")

    def test_effective_language_falls_back_from_auto(self):
        stub = SimpleNamespace(
            _get_file_source_language=lambda _fp: gui.AUTO_LANGUAGE,
        )
        language = gui.App._effective_file_source_language(
            stub, "a.srt", "Spanish")
        self.assertEqual(language, "Spanish")

    def test_apply_detected_languages_keeps_global_auto_for_mixed_files(self):
        class Var:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

            def set(self, value):
                self.value = value

        stub = SimpleNamespace(
            _file_language_vars={
                "uno.srt": Var(gui.AUTO_LANGUAGE),
                "due.srt": Var("Italian"),
            },
            src_var=Var(gui.AUTO_LANGUAGE),
        )
        gui.App._apply_detected_source_languages(
            stub, {"uno.srt": "Spanish"})
        self.assertEqual(stub._file_language_vars["uno.srt"].get(), "Spanish")
        self.assertEqual(stub._file_language_vars["due.srt"].get(), "Italian")
        self.assertEqual(stub.src_var.get(), gui.AUTO_LANGUAGE)

    def test_build_requests_uses_group_specific_source_language(self):
        spanish = gui._build_sync_system_prompt(
            "Spanish", "Turkish", None, "Orta")
        italian = gui._build_sync_system_prompt(
            "Italian", "Turkish", None, "Orta")
        self.assertIn("from Spanish to Turkish", spanish)
        self.assertIn("from Italian to Turkish", italian)
        self.assertNotEqual(spanish, italian)

    # ── Strict Unresolved Source Language Preflight Tests ──────────────────
    def test_failed_detection_no_user_selection_rejects_continue_no_english_conversion(self):
        detected = {"file1.srt": gui.AUTO_LANGUAGE}
        items = gui.prepare_source_language_confirm_items(detected)
        self.assertEqual(items["file1.srt"]["initial"], gui.UNRESOLVED_LANGUAGE)
        self.assertTrue(items["file1.srt"]["is_failed"])

        user_sels = {"file1.srt": gui.UNRESOLVED_LANGUAGE}
        is_valid, unresolved = gui.validate_source_language_selections(user_sels)
        self.assertFalse(is_valid)
        self.assertEqual(unresolved, ["file1.srt"])

        should_cont, final_map = gui.resolve_source_language_preflight(detected, user_sels, "continue")
        self.assertFalse(should_cont)
        self.assertEqual(final_map["file1.srt"], gui.AUTO_LANGUAGE)
        self.assertNotEqual(final_map["file1.srt"], "English")

    def test_failed_detection_user_selects_spanish_allows_continue(self):
        detected = {"file1.srt": gui.AUTO_LANGUAGE}
        user_sels = {"file1.srt": "Spanish"}
        is_valid, unresolved = gui.validate_source_language_selections(user_sels)
        self.assertTrue(is_valid)
        self.assertEqual(unresolved, [])

        should_cont, final_map = gui.resolve_source_language_preflight(detected, user_sels, "continue")
        self.assertTrue(should_cont)
        self.assertEqual(final_map["file1.srt"], "Spanish")

    def test_real_english_detection_is_not_counted_as_failed(self):
        detected = {"eng.srt": "English"}
        items = gui.prepare_source_language_confirm_items(detected)
        self.assertEqual(items["eng.srt"]["initial"], "English")
        self.assertFalse(items["eng.srt"]["is_failed"])

        user_sels = {"eng.srt": "English"}
        is_valid, unresolved = gui.validate_source_language_selections(user_sels)
        self.assertTrue(is_valid)

        should_cont, final_map = gui.resolve_source_language_preflight(detected, user_sels, "continue")
        self.assertTrue(should_cont)
        self.assertEqual(final_map["eng.srt"], "English")

    def test_english_detection_and_failed_detection_are_distinguished(self):
        detected = {"eng.srt": "English", "fail.srt": gui.AUTO_LANGUAGE}
        items = gui.prepare_source_language_confirm_items(detected)
        self.assertEqual(items["eng.srt"]["initial"], "English")
        self.assertFalse(items["eng.srt"]["is_failed"])
        self.assertEqual(items["fail.srt"]["initial"], gui.UNRESOLVED_LANGUAGE)
        self.assertTrue(items["fail.srt"]["is_failed"])

        user_sels = {"eng.srt": "English", "fail.srt": gui.UNRESOLVED_LANGUAGE}
        is_valid, unresolved = gui.validate_source_language_selections(user_sels)
        self.assertFalse(is_valid)
        self.assertEqual(unresolved, ["fail.srt"])

        should_cont, final_map = gui.resolve_source_language_preflight(detected, user_sels, "continue")
        self.assertFalse(should_cont)
        self.assertEqual(final_map["eng.srt"], "English")
        self.assertEqual(final_map["fail.srt"], gui.AUTO_LANGUAGE)

    def test_all_files_failed_no_selection_cannot_continue(self):
        detected = {"f1.srt": gui.AUTO_LANGUAGE, "f2.srt": gui.AUTO_LANGUAGE}
        user_sels = {"f1.srt": gui.UNRESOLVED_LANGUAGE, "f2.srt": gui.UNRESOLVED_LANGUAGE}
        is_valid, unresolved = gui.validate_source_language_selections(user_sels)
        self.assertFalse(is_valid)
        self.assertEqual(sorted(unresolved), ["f1.srt", "f2.srt"])

        should_cont, final_map = gui.resolve_source_language_preflight(detected, user_sels, "continue")
        self.assertFalse(should_cont)
        self.assertEqual(final_map["f1.srt"], gui.AUTO_LANGUAGE)
        self.assertEqual(final_map["f2.srt"], gui.AUTO_LANGUAGE)

    def test_some_resolved_one_unresolved_cannot_continue(self):
        detected = {"f1.srt": "Italian", "f2.srt": gui.AUTO_LANGUAGE}
        user_sels = {"f1.srt": "Italian", "f2.srt": gui.UNRESOLVED_LANGUAGE}
        is_valid, unresolved = gui.validate_source_language_selections(user_sels)
        self.assertFalse(is_valid)
        self.assertEqual(unresolved, ["f2.srt"])

        should_cont, final_map = gui.resolve_source_language_preflight(detected, user_sels, "continue")
        self.assertFalse(should_cont)
        self.assertEqual(final_map["f1.srt"], "Italian")
        self.assertEqual(final_map["f2.srt"], gui.AUTO_LANGUAGE)

    def test_edit_and_cancel_actions_do_not_start_translation_and_preserve_auto(self):
        detected = {"f1.srt": "Italian", "f2.srt": gui.AUTO_LANGUAGE}
        user_sels = {"f1.srt": "Italian", "f2.srt": gui.UNRESOLVED_LANGUAGE}

        should_edit, map_edit = gui.resolve_source_language_preflight(detected, user_sels, "edit")
        self.assertFalse(should_edit)
        self.assertEqual(map_edit["f1.srt"], "Italian")
        self.assertEqual(map_edit["f2.srt"], gui.AUTO_LANGUAGE)

        should_cancel, map_cancel = gui.resolve_source_language_preflight(detected, user_sels, "cancel")
        self.assertFalse(should_cancel)
        self.assertEqual(map_cancel["f1.srt"], "Italian")
        self.assertEqual(map_cancel["f2.srt"], gui.AUTO_LANGUAGE)

    def test_api_exception_auto_language_sets_unresolved_sentinel_in_confirm_items(self):
        with patch.object(gui, "_safe_chat_create", side_effect=RuntimeError("net")):
            detected = gui.detect_source_languages_batch_with_ai(
                object(),
                {"a.srt": [("1", "", "Hello")], "b.srt": [("1", "", "Bonjour")]},
                "test-model",
            )
        self.assertEqual(detected["a.srt"], gui.AUTO_LANGUAGE)
        self.assertEqual(detected["b.srt"], gui.AUTO_LANGUAGE)

        items = gui.prepare_source_language_confirm_items(detected)
        self.assertEqual(items["a.srt"]["initial"], gui.UNRESOLVED_LANGUAGE)
        self.assertTrue(items["a.srt"]["is_failed"])
        self.assertEqual(items["b.srt"]["initial"], gui.UNRESOLVED_LANGUAGE)
        self.assertTrue(items["b.srt"]["is_failed"])
        self.assertNotEqual(items["a.srt"]["initial"], "English")

    # ── Advanced Response Parsing, Thread Safety, & Batch Boundary Tests ────
    def test_base_url_read_on_main_thread_passed_to_openai_client(self):
        """Preflight captures base_url on main thread before starting worker."""
        captured_base_url = []

        def fake_init(self_client, api_key=None, base_url=None):
            captured_base_url.append(base_url)

        stub = SimpleNamespace(
            _auto_source_language_files=lambda files: files,
            _set_running=lambda val: None,
            _main_model_name=lambda: "test-model",
            _main_api_base_url=lambda: "https://custom.api.endpoint/v1",
            _set_phase=lambda p, msg: None,
            _set_status=lambda msg: None,
            _log=lambda msg, tag="info": None,
            _detect_source_languages_parallel=lambda client, files, model: {f: "Spanish" for f in files},
            _show_source_language_confirm_dialog=lambda detected: True,
            _language_preflight_done=False,
            after=lambda ms, fn: fn(),
            _start=lambda: None,
        )

        with patch("openai.OpenAI.__init__", new=fake_init):
            gui.App._start_source_language_preflight(stub, "fake-key", ["a.srt"])

        self.assertEqual(captured_base_url, ["https://custom.api.endpoint/v1"])

    def test_worker_thread_does_not_call_main_api_base_url_or_tk_get(self):
        """Worker thread does not execute _main_api_base_url or Tk var gets."""
        main_thread_calls = []

        def guarded_base_url():
            if threading.current_thread() is not threading.main_thread():
                raise AssertionError("Worker thread must not call _main_api_base_url()")
            main_thread_calls.append("base_url")
            return "https://main-thread-url.com"

        stub = SimpleNamespace(
            _auto_source_language_files=lambda files: files,
            _set_running=lambda val: None,
            _main_model_name=lambda: "test-model",
            _main_api_base_url=guarded_base_url,
            _set_phase=lambda p, msg: None,
            _set_status=lambda msg: None,
            _log=lambda msg, tag="info": None,
            _detect_source_languages_parallel=lambda client, files, model: {f: "Spanish" for f in files},
            _show_source_language_confirm_dialog=lambda detected: True,
            _language_preflight_done=False,
            after=lambda ms, fn: fn(),
            _start=lambda: None,
        )

        with patch("openai.OpenAI.__init__", return_value=SimpleNamespace()):
            gui.App._start_source_language_preflight(stub, "fake-key", ["a.srt"])

        self.assertEqual(main_thread_calls, ["base_url"])

    def test_missing_id_leaves_only_that_file_unresolved(self):
        """If response misses one ID, only that file stays AUTO_LANGUAGE."""
        response_json = {"languages": {"0": "Spanish"}}
        with patch.object(gui, "_safe_chat_create", return_value=_response(json.dumps(response_json))):
            detected = gui.detect_source_languages_batch_with_ai(
                object(),
                {"file0.srt": [("1", "", "Hola")], "file1.srt": [("1", "", "Ciao")]},
                "test-model"
            )
        self.assertEqual(detected["file0.srt"], "Spanish")
        self.assertEqual(detected["file1.srt"], gui.AUTO_LANGUAGE)

    def test_out_of_order_results_map_to_correct_files(self):
        """Response keys arriving in reverse order map correctly."""
        response_json = {"languages": {"1": "Italian", "0": "Spanish"}}
        with patch.object(gui, "_safe_chat_create", return_value=_response(json.dumps(response_json))):
            detected = gui.detect_source_languages_batch_with_ai(
                object(),
                {"file0.srt": [("1", "", "Hola")], "file1.srt": [("1", "", "Ciao")]},
                "test-model"
            )
        self.assertEqual(detected["file0.srt"], "Spanish")
        self.assertEqual(detected["file1.srt"], "Italian")

    def test_duplicate_or_invalid_id_safely_leaves_unresolved(self):
        """Duplicate keys in JSON or unrecognized IDs leave files AUTO_LANGUAGE."""
        response_json = {"languages": {"999": "Spanish"}}
        with patch.object(gui, "_safe_chat_create", return_value=_response(json.dumps(response_json))):
            detected = gui.detect_source_languages_batch_with_ai(
                object(),
                {"file0.srt": [("1", "", "Hola")]},
                "test-model"
            )
        self.assertEqual(detected["file0.srt"], gui.AUTO_LANGUAGE)

    def test_corrupt_or_fenced_response_handles_gracefully(self):
        """Fenced JSON response is extracted correctly; corrupt text leaves AUTO_LANGUAGE (not English)."""
        fenced_json = "```json\n{\"languages\": {\"0\": \"Spanish\"}}\n```"
        with patch.object(gui, "_safe_chat_create", return_value=_response(fenced_json)):
            detected = gui.detect_source_languages_batch_with_ai(
                object(), {"file0.srt": [("1", "", "Hola")]}, "test-model"
            )
        self.assertEqual(detected["file0.srt"], "Spanish")

        corrupt_text = "Sorry, I cannot identify these languages."
        with patch.object(gui, "_safe_chat_create", return_value=_response(corrupt_text)):
            detected_corrupt = gui.detect_source_languages_batch_with_ai(
                object(), {"file0.srt": [("1", "", "Hola")]}, "test-model"
            )
        self.assertEqual(detected_corrupt["file0.srt"], gui.AUTO_LANGUAGE)
        self.assertNotEqual(detected_corrupt["file0.srt"], "English")

    def test_batching_21_files_splits_into_20_and_1(self):
        """21 files trigger exactly 2 batch API calls (20 and 1)."""
        captured_batch_sizes = []

        def fake_batch_detect(client, file_cues, model, log_fn=None, token_callback=None):
            captured_batch_sizes.append(len(file_cues))
            return {fp: "Spanish" for fp in file_cues}

        stub = SimpleNamespace(
            _cached_blocks_for=lambda fp: [("1", "", "Hola")],
            _update_tokens=lambda *a, **k: None,
            _log=lambda *a, **k: None,
        )

        files = [f"file_{i}.srt" for i in range(21)]
        with patch.object(gui, "detect_source_languages_batch_with_ai", side_effect=fake_batch_detect):
            results = gui.App._detect_source_languages_parallel(stub, object(), files, "test-model")

        self.assertEqual(captured_batch_sizes, [20, 1])
        self.assertEqual(len(results), 21)

    def test_same_basename_different_paths_do_not_mix_up(self):
        """Files sharing basename (e.g. dirA/sub.srt vs dirB/sub.srt) map independently."""
        path_a = r"C:\path\dirA\sub.srt"
        path_b = r"C:\path\dirB\sub.srt"
        response_json = {"languages": {"0": "Spanish", "1": "Italian"}}

        with patch.object(gui, "_safe_chat_create", return_value=_response(json.dumps(response_json))):
            detected = gui.detect_source_languages_batch_with_ai(
                object(),
                {path_a: [("1", "", "Hola")], path_b: [("1", "", "Ciao")]},
                "test-model"
            )

        self.assertEqual(detected[path_a], "Spanish")
        self.assertEqual(detected[path_b], "Italian")

    def test_sdh_only_or_empty_cue_file_returns_unresolved(self):
        """File with only SDH sound descriptors (e.g. [door slamming]) becomes AUTO_LANGUAGE."""
        sdh_only_cues = [("1", "", "[door slamming]"), ("2", "", "[applause]"), ("3", "", "♪♪♪")]
        with patch.object(gui, "_safe_chat_create") as mock_api:
            detected = gui.detect_source_languages_batch_with_ai(
                object(),
                {"sdh_file.srt": sdh_only_cues},
                "test-model"
            )
        self.assertEqual(detected["sdh_file.srt"], gui.AUTO_LANGUAGE)
        mock_api.assert_not_called()

    def test_real_english_result_is_preserved_as_english(self):
        """Valid English response from API stays 'English'."""
        response_json = {"languages": {"0": "English"}}
        with patch.object(gui, "_safe_chat_create", return_value=_response(json.dumps(response_json))):
            detected = gui.detect_source_languages_batch_with_ai(
                object(),
                {"eng.srt": [("1", "", "Hello, how are you?")]},
                "test-model"
            )
        self.assertEqual(detected["eng.srt"], "English")


if __name__ == "__main__":
    unittest.main()
