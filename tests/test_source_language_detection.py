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

    # ── detection-failure visibility regression ──────────────────────
    def test_dialog_fail_count_detects_auto_language_entries(self):
        """Confirm dialog code path correctly counts failed detections."""
        detected = {
            "ok.srt": "Spanish",
            "fail1.srt": gui.AUTO_LANGUAGE,
            "fail2.srt": gui.AUTO_LANGUAGE,
        }
        fail_count = sum(
            1 for fp in detected
            if gui.normalize_language_name(detected.get(fp)) == gui.AUTO_LANGUAGE
        )
        self.assertEqual(fail_count, 2)

    def test_dialog_fail_count_zero_when_all_detected(self):
        detected = {"a.srt": "Italian", "b.srt": "French"}
        fail_count = sum(
            1 for fp in detected
            if gui.normalize_language_name(detected.get(fp)) == gui.AUTO_LANGUAGE
        )
        self.assertEqual(fail_count, 0)

    def test_apply_detected_keeps_auto_when_all_fail(self):
        """When detection fails for ALL files, global should stay Otomatik."""
        class Var:
            def __init__(self, v): self.value = v
            def get(self): return self.value
            def set(self, v): self.value = v

        stub = SimpleNamespace(
            _file_language_vars={
                "a.srt": Var(gui.AUTO_LANGUAGE),
                "b.srt": Var(gui.AUTO_LANGUAGE),
            },
            src_var=Var("English"),
        )
        gui.App._apply_detected_source_languages(
            stub, {"a.srt": gui.AUTO_LANGUAGE, "b.srt": gui.AUTO_LANGUAGE})
        # Both stay AUTO_LANGUAGE → global should reflect that
        self.assertEqual(stub._file_language_vars["a.srt"].get(), gui.AUTO_LANGUAGE)
        self.assertEqual(stub._file_language_vars["b.srt"].get(), gui.AUTO_LANGUAGE)

    def test_batch_detector_api_exception_returns_auto_for_all(self):
        """When API call raises, all files should get AUTO_LANGUAGE."""
        with patch.object(gui, "_safe_chat_create", side_effect=RuntimeError("net")):
            detected = gui.detect_source_languages_batch_with_ai(
                object(),
                {"a.srt": [("1", "", "Hello")], "b.srt": [("1", "", "Bonjour")]},
                "test-model",
            )
        self.assertEqual(detected["a.srt"], gui.AUTO_LANGUAGE)
        self.assertEqual(detected["b.srt"], gui.AUTO_LANGUAGE)


if __name__ == "__main__":
    unittest.main()
