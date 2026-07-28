import json
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

import hybrid_translate as ht
import subtitle_translator_gui as gui


class _FakeClient:
    response_items = []

    def __init__(self, *args, **kwargs):
        content = json.dumps(self.response_items, ensure_ascii=False)
        self.chat = SimpleNamespace(completions=SimpleNamespace(
            create=lambda **_kwargs: SimpleNamespace(
                usage=None,
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content=content)
                )],
            )
        ))


class _App:
    _stop_flag = False

    def __init__(self):
        self.logs = []

    def _main_api_key(self):
        return "sk-test"

    def _main_api_base_url(self):
        return "https://api.openai.com/v1"

    def _cached_blocks_for(self, _fp):
        return None

    def _locked_terms_hint(self, _fp, _tgt):
        return ""

    def _get_locked_terms_dict(self, _fp, _tgt):
        return {}

    def _update_tokens(self, *_args, **_kwargs):
        return None

    def _set_status(self, *_args, **_kwargs):
        return None

    def _log(self, msg, level=""):
        self.logs.append((level, msg))

    def _log_exc(self, msg, exc):
        self.logs.append(("err", f"{msg}: {exc}"))


class ReviewPassAtomicityTest(unittest.TestCase):
    cues = [
        ("1", "00:00:01,000 --> 00:00:02,000",
         "Throughout history, humanity has struggled,"),
        ("2", "00:00:02,100 --> 00:00:03,000",
         "with fears of Armageddon."),
    ]
    blocks = [
        ("1", "00:00:01,000 --> 00:00:02,000",
         "Tarih boyunca insanlık boğuştu,"),
        ("2", "00:00:02,100 --> 00:00:03,000",
         "Armageddon korkularıyla."),
    ]

    def _run(self, response_items):
        _FakeClient.response_items = response_items
        app = _App()
        with mock.patch.object(gui, "OpenAI", _FakeClient), \
             mock.patch.object(gui, "parse_subtitle", return_value=self.cues), \
             mock.patch.object(
                 ht, "_tag_fragments",
                 return_value={"1": "start", "2": "end"}), \
             mock.patch.object(
                 ht, "_fragment_groups",
                 return_value=(
                     {"1": "g1", "2": "g1"},
                     [{"id": "g1", "items": ["1", "2"]}],
                 )):
            result, fixed = gui.App._review_pass(
                app, "dummy.srt", self.blocks, "gpt-5.4-mini", "Turkish")
        return app, result, fixed

    def test_partial_fragment_group_response_is_rejected_atomically(self):
        app, result, fixed = self._run([
            {"i": "1", "t": "Tarih boyunca insanlık,"},
        ])

        self.assertEqual(result, self.blocks)
        self.assertEqual(fixed, 0)
        self.assertTrue(any(
            "group_atomic:partial_response" in msg
            for _level, msg in app.logs
        ), app.logs)

    def test_conflicting_duplicate_id_is_rejected(self):
        app, result, fixed = self._run([
            {"i": "1", "t": "Tarih boyunca insanlık mücadele etti,"},
            {"i": "1", "t": "Tarih boyunca insanlar savaştı,"},
        ])

        self.assertEqual(result, self.blocks)
        self.assertEqual(fixed, 0)
        self.assertTrue(any(
            "duplicate_fix_conflict" in msg
            for _level, msg in app.logs
        ), app.logs)

    def test_full_fragment_group_allows_one_changed_and_one_unchanged_member(self):
        _app, result, fixed = self._run([
            {"i": "1", "t": "Tarih boyunca insanlık boğuştu;"},
            {"i": "2", "t": self.blocks[1][2]},
        ])

        self.assertEqual(result[0][2], "Tarih boyunca insanlık boğuştu;")
        self.assertEqual(result[1][2], self.blocks[1][2])
        self.assertEqual(fixed, 1)

    def test_fragment_group_crossing_nominal_chunk_boundary_stays_together(self):
        cues = [
            (str(i), f"00:00:{i % 60:02d},000 --> 00:00:{(i + 1) % 60:02d},000",
             f"Source {i}.")
            for i in range(1, 80)
        ] + [
            ("80", "00:01:20,000 --> 00:01:21,000", "A sentence starts,"),
            ("81", "00:01:21,000 --> 00:01:22,000", "and ends here."),
        ]
        blocks = [
            (idx, ts, f"Çeviri {idx}.") for idx, ts, _text in cues[:-2]
        ] + [
            ("80", cues[-2][1], "Bir cümle başlıyor,"),
            ("81", cues[-1][1], "ve burada bitiyor."),
        ]
        _FakeClient.response_items = [
            {"i": "80", "t": "Bir cümle başlıyor;"},
            {"i": "81", "t": "ve burada bitiyor."},
        ]
        app = _App()
        with mock.patch.object(gui, "OpenAI", _FakeClient), \
             mock.patch.object(gui, "parse_subtitle", return_value=cues), \
             mock.patch.object(
                 ht, "_tag_fragments",
                 return_value={"80": "start", "81": "end"}), \
             mock.patch.object(
                 ht, "_fragment_groups",
                 return_value=(
                     {"80": "g80", "81": "g80"},
                     [{"id": "g80", "items": ["80", "81"]}],
                 )):
            result, fixed = gui.App._review_pass(
                app, "dummy.srt", blocks, "gpt-5.4-mini", "Turkish")

        self.assertEqual(result[-2][2], "Bir cümle başlıyor;")
        self.assertEqual(result[-1][2], "ve burada bitiyor.")
        self.assertEqual(fixed, 1)


class RunSnapshotLifecycleTest(unittest.TestCase):
    class Var:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

    def test_repeated_freeze_does_not_lose_original_getter(self):
        src_var = self.Var("English")
        app = SimpleNamespace(
            _active_snapshot={"src_lang": "Spanish"},
            src_var=src_var,
        )

        gui.App._freeze_run_variable_reads(app)
        gui.App._freeze_run_variable_reads(app)
        src_var.value = "Italian"
        gui.App._unfreeze_run_variable_reads(app)

        self.assertEqual(src_var.get(), "Italian")

    def test_worker_helper_display_name_uses_snapshot_without_tk(self):
        class RaisingVar:
            def get(self):
                raise AssertionError("worker Tk read")

        app = SimpleNamespace(
            _active_snapshot={"helper_models": {"critic": "gpt-5.4"}},
            helper_model_vars={"critic": RaisingVar()},
        )
        seen = []

        def worker():
            seen.append(gui.App._helper_display_name(app, "critic"))

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()

        self.assertEqual(seen, ["gpt-5.4"])


if __name__ == "__main__":
    unittest.main()
