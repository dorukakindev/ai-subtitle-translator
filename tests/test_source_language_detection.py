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


if __name__ == "__main__":
    unittest.main()
