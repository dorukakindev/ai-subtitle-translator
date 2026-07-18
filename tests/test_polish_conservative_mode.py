"""
Polish conservative mode: content drift, proposition drift, safe edit guards,
regression coverage for existing guards after new guards insertion.
"""

import unittest
from types import SimpleNamespace
import hybrid_translate as ht

_VALIDATE = lambda o, n: ht.validate_polish_candidate(o, n)
_VALIDATE_SRC = lambda o, n, s: ht.validate_polish_candidate(o, n, source_text=s)


class _CtkStub(SimpleNamespace):
    """Minimal customtkinter stub for tests that import GUI modules."""
    CTk = object
    CTkToplevel = object
    CTkFrame = object
    CTkLabel = object
    CTkEntry = object
    CTkButton = object
    CTkCheckBox = object
    CTkComboBox = object
    CTkTextbox = object
    CTkOptionMenu = object
    CTkScrollbar = object
    CTkScrollableFrame = object
    CTkInputDialog = object
    set_appearance_mode = staticmethod(lambda m: None)
    set_default_color_theme = staticmethod(lambda t: None)


class PolishNormTest(unittest.TestCase):
    def test_nfkc_normalizes_combined_chars(self):
        self.assertEqual(ht._polish_norm("h\u00e2l\u00e2"), "hala")

    def test_strips_combining_dot_above(self):
        self.assertEqual(ht._polish_norm("I\u0307stanbul"), "istanbul")

    def test_lowercases_upper_ascii(self):
        self.assertEqual(ht._polish_norm("MERHABA"), "merhaba")

    def test_handles_mixed_content(self):
        self.assertEqual(ht._polish_norm("H\u00c2L\u00c2"), "hala")

    def test_does_not_mutate_plain_text(self):
        self.assertEqual(ht._polish_norm("merhaba dunya"), "merhaba dunya")


class IsSafePolishEditTest(unittest.TestCase):
    def test_identical_is_safe(self):
        self.assertTrue(ht.is_safe_polish_edit("hello world", "hello world"))

    def test_typo_is_safe(self):
        self.assertTrue(ht.is_safe_polish_edit("mikrofom", "mikrofon"))

    def test_case_change_is_safe(self):
        self.assertTrue(ht.is_safe_polish_edit("MERHABA", "Merhaba"))

    def test_punctuation_is_safe(self):
        self.assertTrue(ht.is_safe_polish_edit("nasilsin", "nasilsin?"))

    def test_full_content_rewrite_not_safe(self):
        self.assertFalse(ht.is_safe_polish_edit("bugun hava cok guzel", "yagin yagmur yagacak"))

    def test_local_fix_normalized(self):
        self.assertTrue(ht.is_safe_polish_edit(
            "Vajina ki... \u015fey, \u00fcretradan bahsediyoruz",
            "Vajina de\u011fil... \u015fey, \u00fcretradan bahsediyoruz"
        ))

    def test_empty_old_not_safe(self):
        self.assertFalse(ht.is_safe_polish_edit("", "hello"))

    def test_hyphen_to_space_soft_branch(self):
        self.assertTrue(ht.is_safe_polish_edit("hello-dunya", "hello dunya"))

    def test_full_rewrite_different_word_count_still_unsafe(self):
        self.assertFalse(ht.is_safe_polish_edit("merhaba", "merhaba arkadas nasilsin"))


class ContentWordDriftTest(unittest.TestCase):
    def test_detects_introduced_words(self):
        self.assertTrue(ht._has_content_word_drift(
            "bugun eve gidip yemek yaptim",
            "yarin aksam disari cikip kahvalti edecegim"
        ))

    def test_rejects_three_new_words_on_long_old(self):
        self.assertTrue(ht._has_content_word_drift(
            "bugun gece eve gidip yemek yaptim",
            "yarin sabah ise gidip toplanti yapacagim"
        ))

    def test_accepts_one_new_word_on_short_old(self):
        self.assertFalse(ht._has_content_word_drift("gel", "gel ve otur"))

    def test_long_old_accepts_one_new_word(self):
        self.assertFalse(ht._has_content_word_drift(
            "bugun eve gidip yemek yiyecegim",
            "bugun eve gidip yemek hazirlayacagim"
        ))

    def test_long_old_rejects_two_new_words(self):
        self.assertTrue(ht._has_content_word_drift(
            "bugun eve gidip yemek yiyecegim",
            "bugun eve gidip aksam yemegi hazirlayacagim"
        ))

    def test_identical_content_no_drift(self):
        self.assertFalse(ht._has_content_word_drift("araba al", "araba al"))

    def test_stopwords_not_counted(self):
        iste_word = "\u0069\u015fte"
        self.assertFalse(ht._has_content_word_drift(
            "ben araba al",
            "ben araba al ve " + iste_word + " yani"
        ))

    def test_local_fix_normalized_no_drift(self):
        self.assertFalse(ht._has_content_word_drift(
            "Vajina ki... \u015fey, \u00fcretradan bahsediyoruz",
            "Vajina de\u011fil... \u015fey, \u00fcretradan bahsediyoruz"
        ))

    def test_empty_old_no_drift(self):
        self.assertFalse(ht._has_content_word_drift("", "merhaba"))

    def test_source_aware_leniency_single_new_token(self):
        self.assertFalse(ht._has_content_word_drift(
            "markete bakiyorum",
            "markete bakip yiyecek alacagim",
            source_text="I am looking at the store to buy groceries"
        ))

    def test_source_aware_still_drift_on_unjustified_new_content(self):
        self.assertTrue(ht._has_content_word_drift(
            "bugun eve gidiyorum",
            "yarin aksam disari cikip kahvalti edecegim",
            source_text="I am going home today"
        ))


class ContentWordLossTest(unittest.TestCase):
    def test_detects_loss_of_two_meaningful_tokens(self):
        self.assertTrue(ht._has_content_word_loss(
            "Bir doktor için tıbbi bir şey satın almak istiyorum.",
            "Bir doktor için bir şey almak istiyorum.",
            source_text="I want to buy something medical for a doctor",
        ))

    def test_detects_short_line_critical_loss(self):
        self.assertTrue(ht._has_content_word_loss(
            "Oyuncak diye pazarlanıyor ama",
            "ama 19. yüzyılda",
        ))

    def test_punctuation_only_is_not_loss(self):
        self.assertFalse(ht._has_content_word_loss(
            "Bir doktor için tıbbi bir şey satın almak istiyorum.",
            "Bir doktor için tıbbi bir şey satın almak istiyorum!",
        ))


class PropositionDriftTest(unittest.TestCase):
    def test_all_caps_dropped_detected(self):
        self.assertTrue(ht._has_proposition_drift("WOODSTOCK festivali", "festivali"))

    def test_title_case_not_flagged(self):
        self.assertFalse(ht._has_proposition_drift("Babylon sehri", "Babil sehri"))

    def test_short_caps_not_flagged(self):
        self.assertFalse(ht._has_proposition_drift("AB ve ABD", "AVRUPA ve AMERIKA"))

    def test_identical_caps_ok(self):
        self.assertFalse(ht._has_proposition_drift("WOODSTOCK festivali", "WOODSTOCK festivali"))

    def test_no_caps_in_old_returns_false(self):
        self.assertFalse(ht._has_proposition_drift("merhaba dunya", "MERHABA DUNYA"))


class ValidatePolishNewGuardsTest(unittest.TestCase):
    def test_accepts_no_change(self):
        ok, reason = _VALIDATE("merhaba dunya", "merhaba dunya")
        self.assertTrue(ok)

    def test_proposition_drift_rejected(self):
        ok, reason = _VALIDATE("WOODSTOCK festivali", "festivali")
        self.assertFalse(ok)
        self.assertEqual(reason, "proposition_drift")

    def test_content_drift_rejected(self):
        ok, reason = _VALIDATE(
            "bugun eve gidip yemek yaptim",
            "yarin aksam disari cikip kahvalti edecegim"
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "content_word_drift")

    def test_content_loss_rejected(self):
        ok, reason = _VALIDATE_SRC(
            "Bir doktor için tıbbi bir şey satın almak istiyorum.",
            "Bir doktor için bir şey almak istiyorum.",
            "I want to buy something medical for a doctor",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "medical_adjective_deletion")

    def test_content_loss_general_reason(self):
        ok, reason = _VALIDATE(
            "Oyuncak diye pazarlanıyor ama",
            "ama 19. yüzyılda"
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "content_word_loss")

    def test_existing_guard_sadece_still_rejected(self):
        ok, reason = _VALIDATE("Sadece", "Sadece, yalnizca bir tane var ve o da burada")
        self.assertFalse(ok)
        self.assertEqual(reason, "fragment_expansion_regression")

    def test_existing_guard_deneyim_works(self):
        ok, reason = _VALIDATE("Deneyim", "Dene")
        self.assertFalse(ok)
        self.assertEqual(reason, "first_person_intent_shift")

    def test_existing_guard_research_to_hunting_works(self):
        ok, reason = _VALIDATE(
            "ara\u015ft\u0131r\u0131p se\u00e7erek",
            "avlan\u0131p se\u00e7erek"
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "research_to_hunting_regression")

    def test_existing_guard_woodstock_works(self):
        ok, reason = _VALIDATE("WOODSTOCK", "Woodstoc")
        self.assertFalse(ok)
        self.assertEqual(reason, "proper_noun_regression")

    def test_typo_fix_passess_guard(self):
        ok, reason = _VALIDATE("mikrofom sorunu", "mikrofon sorunu")
        self.assertTrue(ok)

    def test_local_fix_not_content_drift(self):
        ok, reason = _VALIDATE(
            "Vajina ki... \u015fey, \u00fcretradan bahsediyoruz",
            "Vajina de\u011fil... \u015fey, \u00fcretradan bahsediyoruz"
        )
        self.assertTrue(ok)

    def test_fragment_redistribution_regression_priority(self):
        ok, reason = _VALIDATE(
            "yaratt\u0131\u011f\u0131m yarasay\u0131 g\u00f6sterece\u011fim",
            "seni g\u00f6stermeyi istiyorum"
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "fragment_redistribution_regression")

    def test_bracket_labels_still_respected(self):
        ok, reason = _VALIDATE("[MUZIK]", "[MUZIK]")
        self.assertTrue(ok)

    def test_numbers_still_protected(self):
        ok, reason = _VALIDATE("3 elma", "uc elma")
        self.assertFalse(ok)

    def test_speaker_dash_still_protected(self):
        ok, reason = _VALIDATE("- Merhaba", "Merhaba")
        self.assertFalse(ok)

    def test_source_aware_guards_still_work(self):
        ok, reason = _VALIDATE_SRC("iyi gunler", "iyi gunler", "good day")
        self.assertTrue(ok)

    def test_woodstock_before_proposition(self):
        ok, reason = _VALIDATE("WOODSTOCK", "Woodstoc")
        self.assertEqual(reason, "proper_noun_regression")


# ── Prompt phrase presence ───────────────────────────────────────────

class PolishPromptPhraseTest(unittest.TestCase):
    def test_source_contains_conservative_mode_rules(self):
        import os
        gui_path = os.path.join(os.path.dirname(__file__), "..", "subtitle_translator_gui.py")
        with open(gui_path, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("MUHAFAZAK", src)
        self.assertIn("DE\u011e\u0130\u015e\u0130M R\u0130SK\u0130", src)


# ── Stem matching ───────────────────────────────────────────────────

class StemMatchTest(unittest.TestCase):
    def test_konusmak_konusacagiz_share_stem(self):
        self.assertTrue(ht._share_stem("konusmak", "konusacagiz"))

    def test_araba_arabam_share_stem(self):
        self.assertTrue(ht._share_stem("araba", "arabam"))

    def test_benim_bence_share_stem(self):
        self.assertTrue(ht._share_stem("benim", "bence"))

    def test_gelmek_gitmek_no_stem(self):
        self.assertFalse(ht._share_stem("gelmek", "gitmek"))

    def test_gel_gelmek_share_stem(self):
        self.assertTrue(ht._share_stem("gel", "gelmek"))

    def test_different_words_no_stem(self):
        self.assertFalse(ht._share_stem("araba", "evler"))

    def test_short_tokens_no_match(self):
        self.assertFalse(ht._share_stem("ev", "ev"))


# ── Change ratio revert loop (integration) ───────────────────────────

class PolishPassRevertLoopTest(unittest.TestCase):
    def _fake_openai_module(self, fixes):
        from types import SimpleNamespace
        class FakeCompletions:
            def create(self, **kwargs):
                return SimpleNamespace(
                    usage=None,
                    choices=[SimpleNamespace(
                        message=SimpleNamespace(content=ht.json.dumps(fixes, ensure_ascii=False))
                    )],
                )
        class FakeOpenAI:
            def __init__(self, api_key=None, base_url=None):
                self.chat = SimpleNamespace(completions=FakeCompletions())
        return SimpleNamespace(OpenAI=FakeOpenAI)

    def test_revert_loop_keeps_safe_edits_reverts_unsafe(self):
        """When >25% of lines change, non-safe edits are reverted but safe edits kept."""
        import sys
        from unittest.mock import patch
        from types import SimpleNamespace
        with patch.dict(sys.modules, {
            "customtkinter": _CtkStub(),
            "openai": SimpleNamespace(OpenAI=object),
        }):
            import subtitle_translator_gui as gui

        class MockApp:
            _stop_flag = False
            def _update_tokens(self, *a, **k): pass
            def _log(self, *a, **k): pass
            def _log_exc(self, *a, **k): pass

        blocks = [(i, "00:00:00,000 --> 00:00:01,000", f"satir {i}") for i in range(1, 11)]
        # fix[1] passes guards (1 new word, typo-level change on line 1)
        # fix[2] full rewrite on line 2 → rejected by content_word_drift (3+ new stems)
        # fix[3] unchanged from original → no change
        # fix[4] passes guards (1 new word, typo-level on line 4)
        # fix[5] full rewrite on line 5 → rejected by content_word_drift (3+ new stems)
        fixes = [
            {"id": 1, "tr": "satir 1 duzeltilmis"},
            {"id": 2, "tr": "tamamen farkli icerik"},
            {"id": 3, "tr": "satir 3"},
            {"id": 4, "tr": "satir 4 duzeltilmis"},
            {"id": 5, "tr": "yepyeni bambaska icerik"},
        ]

        with patch.dict("sys.modules", {"openai": self._fake_openai_module(fixes)}):
            result = gui.App._polish_pass(
                MockApp(),
                blocks,
                "Turkish",
                "test",
                "http://test",
                "gpt-5.4-mini",
            )

        result_map = {str(idx): text for idx, ts, text in result}
        # Safely-polished edits pass guards and survive revert loop
        self.assertEqual(result_map["1"], "satir 1 duzeltilmis")
        # Full rewrites rejected by content_word_drift → original restored
        self.assertEqual(result_map["2"], "satir 2")
        # Unchanged line stays as-is
        self.assertEqual(result_map["3"], "satir 3")
        # Safely-polished edit kept
        self.assertEqual(result_map["4"], "satir 4 duzeltilmis")
        # Full rewrite rejected → original restored
        self.assertEqual(result_map["5"], "satir 5")
        # Remaining lines unchanged
        for i in range(6, 11):
            self.assertEqual(result_map[str(i)], f"satir {i}",
                             f"line {i} should be unchanged")
        changed = sum(1 for idx, ts, text in result
                      if text != f"satir {idx}")
        self.assertEqual(changed, 2, f"Expected 2 safe edits kept, got {changed}")


# ── Runtime prompt verification ─────────────────────────────────────

class PolishRuntimePromptTest(unittest.TestCase):
    """Verify the actual system prompt and payload sent to the API contain conservative rules."""

    def test_prompt_contains_conservative_rules_at_runtime(self):
        """Mock OpenAI and capture system prompt + payload to verify conservative rules."""
        import sys
        import json
        from unittest.mock import patch
        from types import SimpleNamespace

        captured = {"messages": []}

        class CapturingFake:
            def __init__(self, api_key=None, base_url=None):
                self.chat = SimpleNamespace(completions=self)

            def create(self, **kwargs):
                captured["messages"] = kwargs.get("messages", [])
                return SimpleNamespace(
                    usage=SimpleNamespace(
                        completion_tokens=10, prompt_tokens=100,
                        completion_tokens_details=SimpleNamespace(cached_tokens=0),
                    ),
                    choices=[SimpleNamespace(
                        message=SimpleNamespace(content='[{"id": 1, "tr": "merhaba dunya"}]')
                    )],
                )

        with patch.dict(sys.modules, {
            "customtkinter": _CtkStub(),
            "openai": SimpleNamespace(OpenAI=CapturingFake),
        }):
            import subtitle_translator_gui as gui

            class MockApp:
                _stop_flag = False
                def _update_tokens(self, *a, **k): pass
                def _log(self, *a, **k): pass
                def _log_exc(self, *a, **k): pass

            blocks = [(1, "00:00:00,000 --> 00:00:01,000", "merhaba dunya")]
            gui.App._polish_pass(
                MockApp(),
                blocks,
                "Turkish", "test", "http://test", "gpt-5.4-mini",
            )

        self.assertTrue(len(captured["messages"]) >= 2,
                        f"Expected at least 2 messages (system+user), got {len(captured['messages'])}")
        system_msg = captured["messages"][0]["content"] if len(captured["messages"]) >= 1 else ""
        user_msg_content = captured["messages"][1]["content"] if len(captured["messages"]) >= 2 else ""

        self.assertIn("MUHAFAZAK", system_msg,
                       "System prompt missing MUHAFAZAK conservative rule")
        self.assertIn("AŞIRI DEĞİŞİM RİSKİ", system_msg,
                       "System prompt missing AŞIRI DEĞİŞİM RİSKİ warning")
        self.assertIn("CPS", system_msg,
                       "System prompt missing CPS guidance")
        self.assertIn("satır sayısı", system_msg.lower(),
                       "System prompt missing line count preservation")

        payload = json.loads(user_msg_content) if user_msg_content else {}
        self.assertIn("polish", payload,
                       "User payload missing 'polish' key")
        self.assertTrue(len(payload.get("polish", [])) > 0,
                        "User payload has empty polish array")
        first_item = payload["polish"][0]
        self.assertIn("id", first_item, "Polish item missing 'id'")
        self.assertIn("tr", first_item, "Polish item missing 'tr'")


if __name__ == "__main__":
    unittest.main()
