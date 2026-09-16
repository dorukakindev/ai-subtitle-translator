import ast
import unittest
from pathlib import Path

import subtitle_translator_gui as gui
from ui_localization import DEFAULT_UI_LANGUAGE, normalize_ui_language, translate_ui_text


class _Var:
    def __init__(self, value): self.value = value
    def get(self): return self.value
    def set(self, value): self.value = value


class _Widget:
    def __init__(self, text="", children=()):
        self.text = text
        self.children = list(children)
        self.window_title = "Altyazı Çevirisi"
    def winfo_children(self): return self.children
    def cget(self, key):
        if key != "text": raise KeyError(key)
        return self.text
    def configure(self, **kwargs):
        if "text" in kwargs: self.text = kwargs["text"]
    def title(self, value=None):
        if value is None: return self.window_title
        self.window_title = value


class UiLocalizationTest(unittest.TestCase):
    def test_first_run_language_is_english(self):
        self.assertEqual(DEFAULT_UI_LANGUAGE, "English")
        self.assertEqual(normalize_ui_language(None), "English")

    def test_turkish_aliases_normalize_without_changing_domain_values(self):
        self.assertEqual(normalize_ui_language("tr"), "Türkçe")
        self.assertEqual(translate_ui_text("Otomatik", "English"), "Otomatik")

    def test_core_copy_translates_and_restores(self):
        self.assertEqual(translate_ui_text("Altyazı Çevirisi", "English"), "AI Subtitle Translator")
        self.assertEqual(translate_ui_text("Altyazı Çevirisi", "Türkçe"), "Altyazı Çevirisi")
        self.assertEqual(translate_ui_text("Subtitle Translator", "Türkçe"),
                         "Altyazı Çevirisi")

    def test_live_switch_updates_existing_widgets_without_rebuild(self):
        child = _Widget("▶  Çeviriyi başlat")
        root = _Widget("", [child])
        app = object.__new__(gui.App)
        app.ui_language_var = _Var("English")
        app._ui_language = "English"
        gui.App._localize_widget_tree(app, root)
        self.assertEqual(child.text, "▶  Start translation")
        self.assertEqual(root.window_title, "AI Subtitle Translator")
        app.ui_language_var.set("Türkçe")
        gui.App._localize_widget_tree(app, root)
        self.assertEqual(child.text, "▶  Çeviriyi başlat")
        self.assertEqual(root.window_title, "Altyazı Çevirisi")

    def test_primary_ui_has_no_untranslated_turkish_literals(self):
        from ui_localization import EN

        tree = ast.parse(Path(gui.__file__).read_text(encoding="utf-8-sig"))
        app = next(node for node in tree.body
                   if isinstance(node, ast.ClassDef) and node.name == "App")
        checked = {"_build_ui", "_build_sidebar", "_build_main"}
        literals = set()
        for method in app.body:
            if not isinstance(method, ast.FunctionDef) or method.name not in checked:
                continue
            for node in ast.walk(method):
                if not isinstance(node, ast.Call):
                    continue
                for keyword in node.keywords:
                    if (keyword.arg in {"text", "placeholder_text"}
                            and isinstance(keyword.value, ast.Constant)
                            and isinstance(keyword.value.value, str)):
                        literals.add(keyword.value.value)
                if (isinstance(node.func, ast.Name)
                        and node.func.id in {"section", "lbl"}
                        and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)):
                    literals.add(node.args[0].value)
        missing = sorted(text for text in literals if text not in EN
                         and any(char.isalpha() and ord(char) > 127
                                 for char in text))
        self.assertEqual(missing, [])
    def test_language_setting_is_persisted_by_app(self):
        source = Path(gui.__file__).read_text(encoding="utf-8-sig")
        self.assertIn('"ui_language": normalize_ui_language', source)
        self.assertIn('d.get("ui_language")', source)
        self.assertIn('values=list(UI_LANGUAGES)', source)


if __name__ == "__main__":
    unittest.main()
