import unittest
import os
import json
from hybrid_translate import load_glossary

class TestGlossaryLoading(unittest.TestCase):
    def setUp(self):
        self.test_file = "test_glossary.txt"

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def write_file(self, ext, content):
        self.test_file = f"test_glossary{ext}"
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write(content)

    def test_json_dict(self):
        self.write_file(".json", '{"hello": "merhaba"}')
        self.assertEqual(load_glossary(self.test_file), {"hello": "merhaba"})

    def test_json_list(self):
        self.write_file(".json", '["hello"]')
        self.assertEqual(load_glossary(self.test_file), {})

    def test_json_null(self):
        self.write_file(".json", 'null')
        self.assertEqual(load_glossary(self.test_file), {})

    def test_json_broken(self):
        self.write_file(".json", '{broken')
        self.assertEqual(load_glossary(self.test_file), {})

    def test_txt_tab(self):
        self.write_file(".txt", 'hello\tmerhaba')
        self.assertEqual(load_glossary(self.test_file), {"hello": "merhaba"})

    def test_txt_equals(self):
        self.write_file(".txt", 'hello=merhaba')
        self.assertEqual(load_glossary(self.test_file), {"hello": "merhaba"})

    def test_txt_comma(self):
        self.write_file(".csv", 'hello,merhaba')
        self.assertEqual(load_glossary(self.test_file), {"hello": "merhaba"})

    def test_txt_quoted_csv(self):
        self.write_file(".csv", '"Smith, John","John Smith"')
        self.assertEqual(load_glossary(self.test_file), {"Smith, John": "John Smith"})

    def test_skip_empty(self):
        self.write_file(".txt", 'key1=\n=value2\nkey3=value3')
        self.assertEqual(load_glossary(self.test_file), {"key3": "value3"})

    def test_skip_no_separator(self):
        self.write_file(".txt", 'noseparator\nkey=val')
        self.assertEqual(load_glossary(self.test_file), {"key": "val"})

if __name__ == "__main__":
    unittest.main()
