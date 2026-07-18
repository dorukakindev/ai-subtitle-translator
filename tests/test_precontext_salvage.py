"""
_salvage_precontext_json: ön-bağlam analizinde model JSON'u kesilirse (max_tokens) tam
nesne yerine tamamlanmış üst-düzey alanları kurtarır. (Asıl kök neden max_tokens 1200→4000
ile çözüldü; bu kurtarma yine de kesik yanıtlarda dosyayı bağlamsız bırakmamak için.)
"""
import unittest

import subtitle_translator_gui as gui


class PrecontextSalvageTest(unittest.TestCase):
    def test_complete_object_unchanged(self):
        s = '{"summary":"A","tone":"comedy","characters":[{"name":"X"}],"terms":{"a":"b"}}'
        out = gui._salvage_precontext_json(s)
        self.assertEqual(out["summary"], "A")
        self.assertEqual(out["terms"], {"a": "b"})
        self.assertEqual(len(out["characters"]), 1)

    def test_truncated_mid_array_recovers_complete_elements(self):
        # characters dizisi ikinci eleman ortasında kesildi (gerçek hatadaki gibi)
        s = ('{"summary":"A show","tone":"comedy","characters":'
             '[{"name":"Hurlan","role":"dad"},{"name":"Hambr')
        out = gui._salvage_precontext_json(s)
        self.assertEqual(out["summary"], "A show")
        self.assertEqual(out["tone"], "comedy")
        self.assertEqual(len(out["characters"]), 1)            # tamamlanan ilk eleman kurtarıldı
        self.assertEqual(out["characters"][0]["name"], "Hurlan")

    def test_truncated_scalar_recovers_prior_field(self):
        s = '{"summary":"A show","tone":"com'                  # tone ortasında kesildi
        out = gui._salvage_precontext_json(s)
        self.assertEqual(out["summary"], "A show")

    def test_key_boundary_not_closed_invalid(self):
        # "name" bir KEY — burada kapatmak {"name"} (geçersiz) üretmemeli
        s = '{"summary":"A","characters":[{"name'
        out = gui._salvage_precontext_json(s)
        self.assertEqual(out.get("summary"), "A")
        # characters ya hiç yok ya da geçerli liste — bozuk değer yok
        self.assertIsInstance(out, dict)

    def test_garbage_returns_empty(self):
        self.assertEqual(gui._salvage_precontext_json("not json at all"), {})
        self.assertEqual(gui._salvage_precontext_json(""), {})


if __name__ == "__main__":
    unittest.main()
