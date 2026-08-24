# -*- coding: utf-8 -*-
"""İki sistem promptu birbiriyle ve kendi içinde çelişmemeli."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht
import subtitle_translator_gui as g
from prompt_constants import JSON_INSTRUCTION

NL = chr(10)


def _hybrid_prompt(**kwargs):
    context = types.SimpleNamespace(
        tone=kwargs.pop("tone", "belgesel"), summary="", setting="",
        characters=[], recurring_terms=kwargs.pop("terms", {}),
        scene_notes=[], source_language="İngilizce")
    return ht.build_system_prompt(context, "İngilizce", "Türkçe", **kwargs)


class TheOutputFormatIsAskedForOnceTest(unittest.TestCase):
    """Hibrit prompt aynı mesajda hem düz metin hem JSON istiyordu.

    `build_batch_requests` her sistem promptunun sonuna JSON_INSTRUCTION
    ekliyor, yani iki emir ~11.000 karakter arayla aynı isteğe giriyordu.
    Düz metin satırı, çıktı JSON'a geçtiğinde unutulmuş bayat bir kalıntı.
    """

    def test_the_stale_plain_text_order_is_gone(self):
        prompt = _hybrid_prompt() + JSON_INSTRUCTION
        self.assertNotIn("Output ONLY the translated text", prompt)

    def test_the_json_contract_still_stands(self):
        prompt = _hybrid_prompt() + JSON_INSTRUCTION
        self.assertIn("Return ONLY the JSON array", prompt)

    def test_the_no_commentary_rule_survived(self):
        # Kaldırılan satırın DOĞRU olan yarısı korunmalı.
        self.assertIn("Do NOT add notes", _hybrid_prompt())

    def test_every_hybrid_request_appends_the_json_contract(self):
        import inspect
        self.assertIn("system_prompt + json_instruction",
                      inspect.getsource(ht.build_batch_requests))


class TheGlossaryIsNotBothAbsoluteAndOverridableTest(unittest.TestCase):
    """Sistem bloğu 'asla sapma' derken payload 'bağlam üstün gelir' diyordu.

    Aynı sözlüğü tarif eden iki metin. Bağlamın üstün gelmesi yeni ve doğru
    politika: 202 gerçek dosyada modeli 'pupil → göz bebeği' gibi yanlış
    dayatmalardan kurtaran şey buydu.
    """

    TERMS = {"Coven": "Coven", "magic hour": "sihirli saat"}

    def test_the_absolute_wording_is_gone(self):
        self.assertNotIn("no substitutions allowed",
                         _hybrid_prompt(terms=self.TERMS))

    def test_the_terms_are_still_delivered(self):
        prompt = _hybrid_prompt(terms=self.TERMS)
        self.assertIn("MANDATORY TERM TRANSLATIONS", prompt)
        self.assertIn("magic hour", prompt)

    def test_the_two_texts_now_agree(self):
        prompt = _hybrid_prompt(terms=self.TERMS) + JSON_INSTRUCTION
        self.assertIn("Only depart from one when the scene clearly shows",
                      prompt.replace(NL, " "))
        self.assertIn("prioritize scene intent", prompt)


class BothPromptsCarryTheRegisterGuidanceTest(unittest.TestCase):
    """REGISTER_GUIDANCE paylaşılan bir sabit ama yalnız hibrit kullanıyordu.

    Düz sync ve batch belgeselde teknik kesinlik, komedide zamanlama,
    dramda alt metin kurallarını hiç almıyordu.
    """

    CASES = (("comedy", "COMEDY"), ("action_crime", "ACTION"),
             ("drama_general", "DRAMA"))

    def test_the_sync_prompt_carries_the_genre_register(self):
        for key, expected in self.CASES:
            schema = g.CONTENT_SCHEMAS.get(key)
            with self.subTest(key=key):
                self.assertIsNotNone(schema)
                prompt = g._build_sync_system_prompt(
                    "İngilizce", "Türkçe", schema, "Orta")
                self.assertIn(f"## REGISTER — {expected}", prompt)

    def test_a_documentary_schema_gets_the_documentary_register(self):
        schema = next((v for v in g.CONTENT_SCHEMAS.values()
                       if "elgesel" in (v.get("name") or "")), None)
        self.assertIsNotNone(schema)
        prompt = g._build_sync_system_prompt(
            "İngilizce", "Türkçe", schema, "Orta")
        self.assertIn("## REGISTER — DOCUMENTARY", prompt)

    def test_a_schema_name_alone_can_decide_the_register(self):
        # Düz sync'in tonu yok; karar yalnız şema adından çıkmalı.
        self.assertEqual(
            ht._infer_register("", schema={"name": "Komedi (Sitcom)"}), "comedy")
        self.assertEqual(
            ht._infer_register("", schema={"name": "Aksiyon / Suç"}), "action")
        self.assertEqual(
            ht._infer_register("", schema={"name": "Dram (Genel)"}), "drama")

    def test_the_tone_still_wins_for_hybrid(self):
        self.assertEqual(ht._infer_register("documentary narrator"), "documentary")
        self.assertEqual(ht._infer_register("comedy, funny"), "comedy")

    def test_no_schema_falls_back_to_general(self):
        self.assertEqual(ht._infer_register("", schema=None), "general")


if __name__ == "__main__":
    unittest.main()
