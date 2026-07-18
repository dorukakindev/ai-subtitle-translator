import unittest

from hybrid_translate import _extract_json_object, _extract_json_array


class ExtractJsonObjectTest(unittest.TestCase):
    def test_direct_valid_json(self):
        self.assertEqual(_extract_json_object('{"a": 1}'), {"a": 1})

    def test_code_fence_soyulur(self):
        raw = '```json\n{"a": 1}\n```'
        self.assertEqual(_extract_json_object(raw), {"a": 1})

    def test_preamble_ve_fence_soyulur(self):
        raw = 'Here is the translation:\n```\n{"tr": "merhaba"}\n```'
        self.assertEqual(_extract_json_object(raw), {"tr": "merhaba"})

    def test_bos_yanit(self):
        self.assertEqual(_extract_json_object(""), {})
        self.assertEqual(_extract_json_object(None), {})

    def test_trailing_comma_recovery(self):
        raw = '{"a": 1, "b": 2,}'
        self.assertEqual(_extract_json_object(raw), {"a": 1, "b": 2})

    def test_python_bool_values_recovery(self):
        raw = '{"active": True, "done": False}'
        self.assertEqual(_extract_json_object(raw), {"active": True, "done": False})

    def test_python_none_recovery(self):
        raw = '{"data": None}'
        self.assertEqual(_extract_json_object(raw), {"data": None})

    def test_no_json_returns_empty(self):
        self.assertEqual(_extract_json_object("just some text"), {})

    def test_brace_counting_with_nested_objects(self):
        raw = 'Some text {"outer": {"inner": [1, 2]}} trailing'
        self.assertEqual(_extract_json_object(raw), {"outer": {"inner": [1, 2]}})

    def test_brace_counting_ignores_string_braces(self):
        raw = '{"key": "text with {brace}", "num": 42}'
        self.assertEqual(_extract_json_object(raw), {"key": "text with {brace}", "num": 42})


class ExtractJsonArrayTest(unittest.TestCase):
    def test_direct_valid_array(self):
        result = _extract_json_array('[{"id": 1}, {"id": 2}]')
        self.assertEqual(result, '[{"id": 1}, {"id": 2}]')

    def test_code_fence_soyulur(self):
        raw = '```json\n[{"id": 1}]\n```'
        result = _extract_json_array(raw)
        self.assertEqual(result, '[{"id": 1}]')

    def test_preamble_text_ve_fence(self):
        raw = 'Here are translations:\n```\n[{"id": 1, "tr": "a"}]\n```\nDone.'
        result = _extract_json_array(raw)
        self.assertEqual(result, '[{"id": 1, "tr": "a"}]')

    def test_find_bracket_region(self):
        raw = 'some text before [{"id": 1}] and after'
        result = _extract_json_array(raw)
        self.assertEqual(result, '[{"id": 1}]')

    def test_bos_yanit(self):
        self.assertEqual(_extract_json_array(""), "")
        self.assertEqual(_extract_json_array("   "), "")

    def test_non_array_returns_raw_if_valid_json(self):
        # Valid JSON passes through even if it's an object
        self.assertEqual(_extract_json_array('{"a": 1}'), '{"a": 1}')

    def test_malformed_array_returns_empty(self):
        self.assertEqual(_extract_json_array("[broken json"), "")
