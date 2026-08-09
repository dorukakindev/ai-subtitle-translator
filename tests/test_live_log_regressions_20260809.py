import sys
import tempfile
import unittest
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import hybrid_translate as ht
import subtitle_translator_gui as gui


class DeliveryLiteralLinebreakTest(unittest.TestCase):
    def test_meditation_bowl_gong_is_removable_sdh(self):
        self.assertTrue(gui._source_cue_is_delivery_removable(
            "[ Meditation bowl gongs ]"))

    def test_speaker_plus_language_sdh_is_removable(self):
        self.assertTrue(gui._source_cue_is_delivery_removable(
            "Garcia:\n[ Speaking Spanish ]"))
        self.assertTrue(gui._source_cue_is_delivery_removable(
            "Woman:\n[ Chanting in Spanish ]"))

    def test_upload_guard_restores_model_linebreak_then_drops_sdh(self):
        ts1 = "00:00:01,000 --> 00:00:02,000"
        ts2 = "00:00:03,000 --> 00:00:04,000"
        source = [
            ("1", ts1, "Garcia:\n[ Speaking Spanish ]"),
            ("2", ts2, "Hello."),
        ]
        translated = [
            ("1", ts1, "Garcia:\\n[ İspanyolca konuşuyor ]"),
            ("2", ts2, "Merhaba."),
        ]
        result = gui._prepare_upload_ready_blocks(
            translated, "Turkish", source_cues=source)
        dialogue = [(ts, text) for _idx, ts, text in result
                    if text != "discord: ceviri2"]
        self.assertEqual(dialogue, [(ts2, "Merhaba.")])
        self.assertFalse(any("\\n" in text for _idx, _ts, text in result))

    def test_upload_guard_restores_literal_linebreak_for_dialogue(self):
        self.assertEqual(
            gui._restore_source_linebreaks(
                "her şeyin tıbbi kullanımla\\nbaşladığını hatırlıyorum.",
                "is where it all began.",
            ),
            "her şeyin tıbbi kullanımla\nbaşladığını hatırlıyorum.",
        )
        self.assertEqual(
            gui._restore_source_linebreaks(r"Kod \\n olarak yazıldı.", r"Use \\n here."),
            r"Kod \\n olarak yazıldı.",
        )

    def test_quality_scan_skips_expected_language_sdh_removal(self):
        warnings = gui.scan_translation_quality(
            "missing.srt",
            [("1", "00:00:01,000 --> 00:00:02,000", "\\n")],
            src_clean_map={"1": "Garcia:\n[ Speaking Spanish ]"},
        )
        self.assertEqual(warnings, 0)

    def test_delivery_audit_hard_gates_literal_newline_marker(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.srt"
            output = Path(td) / "output.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nHello\nthere.\n",
                encoding="utf-8",
            )
            output.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nMerhaba\\norada.\n",
                encoding="utf-8",
            )
            audit = gui._subtitle_delivery_audit(
                str(source), str(output), target_language="English")
        self.assertEqual(audit["residual_literal_newline_cues"], 1)
        self.assertTrue(gui._delivery_audit_has_hard_error(audit))

    def test_delivery_audit_preserves_source_literal_backslash_n(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.srt"
            output = Path(td) / "output.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nUse \\n here.\n",
                encoding="utf-8",
            )
            output.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nKodda \\n kullan.\n",
                encoding="utf-8",
            )
            audit = gui._subtitle_delivery_audit(
                str(source), str(output), target_language="English")
        self.assertEqual(audit["residual_literal_newline_cues"], 0)
        self.assertFalse(gui._delivery_audit_has_hard_error(audit))


class PolishScientificTermTest(unittest.TestCase):
    def test_polish_cannot_corrupt_locked_taxonomic_genus(self):
        ok, reason = ht.validate_polish_candidate(
            "Muhtemelen dünyadaki en güzel psilocybe bu.",
            "Muhtemelen dünyadaki en güzel psilosib bu.",
            "It's probably the most beautiful psilocybe in the world.",
            locked_terms={"psilocybe cubensis": "Psilocybe cubensis"},
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "locked_term_violation")


class PolishUsageRouteTest(unittest.TestCase):
    def test_polish_uses_custom_route_cost_contract(self):
        calls = []

        class FakeCompletions:
            def create(self, **_kwargs):
                return SimpleNamespace(
                    usage=SimpleNamespace(
                        total_tokens=120,
                        prompt_tokens_details=SimpleNamespace(cached_tokens=20),
                    ),
                    choices=[SimpleNamespace(message=SimpleNamespace(
                        content='[{"id":1,"tr":"Merhaba."}]'))],
                )

        class FakeOpenAI:
            def __init__(self, **_kwargs):
                self.chat = SimpleNamespace(completions=FakeCompletions())

        class MockApp:
            _stop_flag = False
            _active_snapshot = {}

            def _update_tokens(self, *args, **kwargs):
                calls.append((args, kwargs))

            def _log(self, *_args, **_kwargs):
                pass

        with patch.dict(sys.modules, {
                "openai": SimpleNamespace(OpenAI=FakeOpenAI)}):
            gui.App._polish_pass(
                MockApp(),
                [(1, "00:00:01,000 --> 00:00:02,000", "Merhaba.")],
                "Turkish", "key", "https://api.shuaiapi.com/v1", "gpt-5.4",
                src_map={"1": "Hello."},
            )

        self.assertTrue(calls)
        _args, kwargs = calls[0]
        self.assertIsNone(kwargs["price"])
        self.assertEqual(kwargs["pass_name"], "Polish Pass")
        self.assertEqual(kwargs["base_url"], "https://api.shuaiapi.com/v1")


class FragmentProperNameRetryTest(unittest.TestCase):
    @staticmethod
    def _request(group_second=True):
        return {"body": {"messages": [{
            "role": "user",
            "content": json.dumps({"tr": [
                {"i": 132, "t": "Janis Joplin and Pelé",
                 "frag": "mid", "frag_group": 7},
                {"i": 133, "t": "are reported to have made pilgrimages",
                 "frag": "mid", "frag_group": 7 if group_second else 8},
            ]}, ensure_ascii=False),
        }]}}

    def test_source_backed_name_can_move_inside_fragment_group(self):
        raw = json.dumps([
            {"i": 132, "t": "Janis Joplin'in"},
            {"i": 133, "t": "ve Pelé'nin hac yolculuğu yaptığı söylenir"},
        ], ensure_ascii=False)
        self.assertEqual(
            gui._chunk_response_retry_reason(raw, self._request()), "")

    def test_neighbor_outside_fragment_group_still_retries(self):
        raw = json.dumps([
            {"i": 132, "t": "Janis Joplin'in"},
            {"i": 133, "t": "ve Pelé'nin hac yolculuğu yaptığı söylenir"},
        ], ensure_ascii=False)
        self.assertEqual(
            gui._chunk_response_retry_reason(
                raw, self._request(group_second=False)),
            "non_turkish_target",
        )


class HamiltonDeliveryRegressionTest(unittest.TestCase):
    def test_quality_scan_reports_stray_article_even_if_source_contains_a(self):
        logs = []
        warnings = gui.scan_translation_quality(
            "missing.srt",
            [("357", "00:19:00,574 --> 00:19:04,186",
              "Ken adlı, kurbağa takıntılı\na arkadaşına.")],
            src_clean_map={"357": "to a toad-obsessed friend named Ken."},
            log_fn=lambda message, *_args, **_kwargs: logs.append(message),
            source_language="English",
        )
        self.assertGreaterEqual(warnings, 1)
        self.assertTrue(any("#357 'a'" in message for message in logs))

    def test_sdh_prefixed_reaction_repeat_is_not_alignment_shift(self):
        blocks = [
            ("109", "00:08:43,610 --> 00:08:45,002", "Aman Tanrım."),
            ("110", "00:08:45,046 --> 00:08:46,526", "Hemen ona bakar mısın?"),
            ("111", "00:08:49,616 --> 00:08:51,139", "Aman Tanrım."),
        ]
        source = {
            "109": "[ Doorbell rings ]\nOh, God.",
            "110": "Want to check on that real quick?",
            "111": "Oh, my God.",
        }
        findings = gui.detect_alignment_issues(blocks, source)
        self.assertFalse(any(
            finding["type"] == "adjacent_duplicate" for finding in findings))


if __name__ == "__main__":
    unittest.main()
