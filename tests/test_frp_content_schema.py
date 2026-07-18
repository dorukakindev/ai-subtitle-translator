import ast
import unittest
from pathlib import Path


def load_content_schemas():
    source = Path("subtitle_translator_gui.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "CONTENT_SCHEMAS":
                    return ast.literal_eval(node.value)
    raise AssertionError("CONTENT_SCHEMAS not found")


class FrpContentSchemaTest(unittest.TestCase):
    def test_frp_mode_is_available(self):
        schemas = load_content_schemas()

        names = [schema["name"] for schema in schemas.values()]

        self.assertIn("FRP / Masaustu Rol Yapma", names)

    def test_frp_prompt_rules_cover_lore_terms_and_mechanics(self):
        schemas = load_content_schemas()
        frp = schemas["frp"]
        rules = "\n".join(frp["rules"]).lower()

        self.assertIn("lore", rules)
        self.assertIn("spell", rules)
        self.assertIn("mechanic", rules)
        self.assertIn("character dialogue", rules)
        self.assertIn("turkish", rules)

    def test_frp_prompt_rules_cover_grimdark_settings_and_books(self):
        schemas = load_content_schemas()
        frp = schemas["frp"]
        rules = "\n".join(frp["rules"]).lower()

        for term in (
            "warhammer 40k",
            "trench crusade",
            "dark sun",
            "youtube",
            "books",
            "codex",
            "grimdark",
            "psionics",
            "warp",
        ):
            self.assertIn(term, rules)


if __name__ == "__main__":
    unittest.main()
