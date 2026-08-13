import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import subtitle_translator_gui as gui


class _EmptyInputApp:
    _selected_files = []

    class input_var:
        @staticmethod
        def get():
            return ""


class TerraGuardTests(unittest.TestCase):
    def test_completed_input_scan_is_reused_on_start(self):
        cached = [r"C:\subs\one.srt", r"C:\subs\two.srt"]
        app = SimpleNamespace(
            _selected_files=[],
            _input_folder_explicitly_selected=True,
            input_var=SimpleNamespace(get=lambda: r"C:\subs"),
            _file_list_root=r"C:\subs",
            _file_list_files=cached,
        )
        with patch.object(gui, "get_subtitle_files") as scan:
            files = gui.App._get_srt_files(app)

        self.assertEqual(files, cached)
        scan.assert_not_called()

    def test_empty_input_does_not_scan_filesystem(self):
        with patch.object(gui, "get_subtitle_files") as scan:
            self.assertEqual(gui.App._get_srt_files(_EmptyInputApp()), [])
        scan.assert_not_called()

    def test_missing_block_retry_keeps_semantic_context(self):
        payload = {
            "tr": [{"i": "1", "t": "one", "frag": "start", "frag_group": "fg_1_2"},
                   {"i": "2", "t": "two", "frag": "end", "frag_group": "fg_1_2"}],
            "ctx": [{"i": "0", "t": "before"}],
            "next_ctx": [{"i": "3", "t": "after"}],
            "prev_scene": [{"i": "x", "t": "bridge"}],
            "scene": {"tone": "calm"},
            "sentence_groups": [{"items": ["1", "2"]}],
            "idioms": ["example"],
            "prev_tr": [{"i": "0", "t": "once"}],
            "glossary": {"term": "translation"},
        }
        req = {
            "custom_id": "chunk_1",
            "body": {
                "model": "gpt-4.1-mini",
                "messages": [
                    {"role": "system", "content": "sys"},
                    {"role": "user", "content": json.dumps(payload)},
                ],
            },
        }
        app = SimpleNamespace(_stop_flag=False, _log=lambda *a: None,
                              _update_tokens=lambda *a, **k: None)
        response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(
                content='[{"i":"1","t":"bir"},{"i":"2","t":"iki"}]'))],
        )
        with patch.object(gui, "_safe_chat_create", return_value=response) as create:
            result = gui.App._resend_missing_blocks(
                app, object(), req, '[{"i":"1","t":""},{"i":"2","t":""}]')
        resent = json.loads(create.call_args.kwargs["messages"][1]["content"])
        for key in ("ctx", "next_ctx", "prev_scene", "scene", "idioms", "prev_tr", "glossary"):
            self.assertEqual(resent[key], payload[key])
        self.assertEqual(resent["sentence_groups"], payload["sentence_groups"])
        self.assertEqual([item["i"] for item in resent["tr"]], ["1", "2"])
        self.assertEqual(json.loads(result)[1]["t"], "iki")


if __name__ == "__main__":
    unittest.main()
