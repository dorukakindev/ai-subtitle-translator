import inspect
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import hybrid_translate as ht
import subtitle_formats as sf
import subtitle_translator_gui as gui
from translation_memory import TranslationMemory


class FinalWriteAndMemoryRegressionTest(unittest.TestCase):
    def test_write_srt_does_not_rewrite_proper_names_with_slang_words(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "names.srt"
            gui.write_srt(
                out,
                [
                    ("1", "00:00:01,000 --> 00:00:02,000", "Hell Fest'e gidiyoruz."),
                    ("2", "00:00:03,000 --> 00:00:04,000", "Damn Yankees'i izledim."),
                ],
            )
            text = out.read_text(encoding="utf-8")
            self.assertIn("Hell Fest'e", text)
            self.assertIn("Damn Yankees'i", text)
            self.assertNotIn("cehennem Fest", text)
            self.assertNotIn("kahretsin Yankees", text)
            self.assertEqual(ht._normalize_output_text("Hell Fest'e gidiyoruz."),
                             "Hell Fest'e gidiyoruz.")

    def test_fuzzy_tm_rejects_semantic_anchor_changes(self):
        with tempfile.TemporaryDirectory() as d:
            tm = TranslationMemory(Path(d) / "tm.db")
            settings = dict(model="m", tgt_lang="tr", profanity="orta", schema_name="doc")
            tm.store("The patient should not receive it.", "Hastaya verilmemeli.", **settings)
            tm.store("The amount is 100 dollars today.", "Tutar bugün 100 dolar.", **settings)
            tm.store("There are fourteen people waiting here.", "Burada on dört kişi bekliyor.", **settings)
            self.assertIsNone(tm.fuzzy_lookup(
                "The patient should receive it.", threshold=0.95, **settings))
            self.assertIsNone(tm.fuzzy_lookup(
                "The amount is 900 dollars today.", threshold=0.95, **settings))
            self.assertIsNone(tm.fuzzy_lookup(
                "There are forty people waiting here.", threshold=0.95, **settings))
            self.assertIsNotNone(tm.fuzzy_lookup(
                "The patient should not receive it!", threshold=0.95, **settings))
            tm.close()

    def test_batch_writer_defines_schema_before_repair_and_tm(self):
        source = inspect.getsource(gui.App._write_results)
        definition = source.index("schema_dict = (self._schema_by_name(schema_name)")
        repair_use = source.index("schema=schema_dict")
        tm_use = source.index("schema_name=schema_dict")
        self.assertLess(definition, repair_use)
        self.assertLess(definition, tm_use)


class ContextAndParserRegressionTest(unittest.TestCase):
    @staticmethod
    def _request(**payload):
        return {
            "body": {
                "messages": [
                    {"role": "system", "content": "prompt"},
                    {"role": "user", "content": json.dumps(payload)},
                ]
            }
        }

    def test_checkpoint_hash_covers_context_glossary_and_scene(self):
        base = {"tr": [{"i": "1", "t": "It is ready."}]}
        first = gui.App._chunk_src_hash(self._request(
            **base, ctx=[{"t": "The bomb"}],
            glossary={"ready": "hazır"}, scene={"tone": "tense"}))
        for changed in (
            {"ctx": [{"t": "Dinner"}], "glossary": {"ready": "hazır"}, "scene": {"tone": "tense"}},
            {"ctx": [{"t": "The bomb"}], "glossary": {"ready": "pişmiş"}, "scene": {"tone": "tense"}},
            {"ctx": [{"t": "The bomb"}], "glossary": {"ready": "hazır"}, "scene": {"tone": "calm"}},
        ):
            self.assertNotEqual(first, gui.App._chunk_src_hash(
                self._request(**base, **changed)))

    def test_unnumbered_empty_cue_does_not_swallow_next_timestamp(self):
        text = (
            "00:00:01,000 --> 00:00:02,000\n\n"
            "00:00:03,000 --> 00:00:04,000\n"
            "Important dialogue.\n"
        )
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "input.srt"
            path.write_text(text, encoding="utf-8")
            blocks = gui.parse_srt(path)
        self.assertEqual(
            blocks,
            [("1", "00:00:03,000 --> 00:00:04,000", "Important dialogue.")],
        )

    def test_consistency_sweep_preserves_sen_siz_distinction(self):
        cues = [
            ("1", "", "What are you doing here?"),
            ("2", "", "What are you doing here?"),
            ("3", "", "What are you doing here?"),
        ]
        blocks = [
            ("1", "", "Burada ne yapıyorsun?"),
            ("2", "", "Burada ne yapıyorsun?"),
            ("3", "", "Burada ne yapıyorsunuz?"),
        ]
        result, fixes = ht.consistency_sweep(cues, blocks)
        self.assertEqual(result, blocks)
        self.assertEqual(fixes, 0)


class GlossaryAndFormatRegressionTest(unittest.TestCase):
    def test_valid_web_term_does_not_drop_whole_glossary(self):
        glossary = {
            "website": "web sitesi",
            "black hole": "kara delik",
        }
        self.assertEqual(ht.sanitize_glossary_for_turkish(glossary), glossary)

    def test_literal_braces_and_vtt_speaker_survive_source_cleaning(self):
        source = "<v Roger><00:00:01.500>Choose {red} or {blue}.</v>"
        expected = "<v Roger>Choose {red} or {blue}.</v>"
        self.assertEqual(gui._clean_src(source), expected)
        self.assertEqual(ht._clean_source_text(source), expected)
        self.assertEqual(
            ht._clean_source_text(r"{\an8}Choose {red}."), "Choose {red}.")

    def test_ass_meaningful_text_styles_are_parsed(self):
        content = (
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,Sign,,0,0,0,,EXIT\n"
            "Dialogue: 0,0:00:03.00,0:00:04.00,Title,,0,0,0,,Breaking News\n"
            "Dialogue: 0,0:00:05.00,0:00:06.00,FX,,0,0,0,,{\\blur5}spark\n"
        )
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "input.ass"
            path.write_text(content, encoding="utf-8")
            blocks = sf.parse_ass(path)
        self.assertEqual([block[2] for block in blocks], ["EXIT", "Breaking News"])

    def test_cached_gloss_action_cannot_request_parenthetical_note(self):
        context = SimpleNamespace(
            tone="", summary="", setting="", characters=[],
            scene_notes=[], recurring_terms={},
        )
        prompt = ht.build_system_prompt(
            context, "English", "Turkish",
            cultural_refs=[{"src": "IRS", "action": "gloss"}],
        )
        self.assertIn('"IRS" → keep unchanged', prompt)
        self.assertNotIn("Add brief parenthetical gloss", prompt)
        self.assertIn("NEVER add parenthetical translator notes", prompt)


if __name__ == "__main__":
    unittest.main()
