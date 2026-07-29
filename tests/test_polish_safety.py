import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import hybrid_translate as ht


class _DummyWidget:
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class _CtkStub(SimpleNamespace):
    def __getattr__(self, name):
        if name.startswith("CTk"):
            return _DummyWidget
        return lambda *args, **kwargs: None


class PolishCandidateSafetyTest(unittest.TestCase):
    def test_accepts_meaning_preserving_simple_polish(self):
        ok, reason = ht.validate_polish_candidate(
            "Bu benim için iyi değil.",
            "Bu bence iyi değil.",
        )
        self.assertTrue(ok, reason)

    def test_rejects_changed_linebreak_count(self):
        ok, reason = ht.validate_polish_candidate("Merhaba\ndostum.", "Merhaba dostum.")
        self.assertFalse(ok)
        self.assertEqual(reason, "linebreak_count")

    def test_rejects_missing_placeholder_polish(self):
        ok, reason = ht.validate_polish_candidate("[ÇEVİRİ EKSİK]", "sohbet başlatıcı parçalar.")
        self.assertFalse(ok)
        self.assertEqual(reason, "missing_placeholder")

    def test_rejects_filling_empty_old_text(self):
        ok, reason = ht.validate_polish_candidate("", "sohbet başlatıcı parçalar.")
        self.assertFalse(ok)
        self.assertEqual(reason, "old_empty")

    def test_rejects_missing_numbers(self):
        ok, reason = ht.validate_polish_candidate("Bana 100 dolar ver.", "Bana para ver.")
        self.assertFalse(ok)
        self.assertEqual(reason, "numbers")

    def test_rejects_changed_format_tags(self):
        ok, reason = ht.validate_polish_candidate("<i>Git buradan.</i>", "Git buradan.")
        self.assertFalse(ok)
        self.assertEqual(reason, "format_tags")

    def test_rejects_changed_speaker_dash(self):
        ok, reason = ht.validate_polish_candidate("- Geliyorum.", "Geliyorum.")
        self.assertFalse(ok)
        self.assertEqual(reason, "speaker_dash")

    def test_rejects_english_backslide_phrase(self):
        ok, reason = ht.validate_polish_candidate(
            "-WOOD: Yani buradaki ates bu mu?\n-Bu, ates iste.",
            "-WOOD: So is this the fire here?\n-Bu, ates iste.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "english_backslide")

    def test_rejects_single_new_english_residue(self):
        ok, reason = ht.validate_polish_candidate(
            "bu bayağı sik kadar acınası.",
            "bu bayağı fucking acınası.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "english_residue")

    def test_rejects_new_holiday_english_residue(self):
        ok, reason = ht.validate_polish_candidate(
            "Mutlu tatiller.",
            "Mutlu holidays.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "english_residue")

    def test_rejects_single_new_english_function_word(self):
        ok, reason = ht.validate_polish_candidate(
            "Ve bu yolculuğun\nher adımında benimleydi.",
            "Ve bu yolculuğun\nevery adımında benimleydi.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "english_residue")

    def test_rejects_new_english_sdh_residue(self):
        ok, reason = ht.validate_polish_candidate(
            "(SEYİRCİ KAHKAHA ATIYOR)",
            "(AUDIENCE LAUGHING)",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "english_residue")

    def test_rejects_known_model_corruption_words(self):
        ok, reason = ht.validate_polish_candidate(
            "annemi ayık hale getirmenin\ntek yolu, bence,",
            "annemi ayık hale getirmenin\nthek yolu, bence,",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "model_corruption")

    def test_rejects_new_turkic_target_drift(self):
        ok, reason = ht.validate_polish_candidate(
            "Tatillere yakın diye,",
            "Holidaýlere yakın diye,",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "non_turkish_target")

    def test_model_corruption_guard_does_not_reject_normal_turkish_labels(self):
        ok, reason = ht.validate_polish_candidate(
            "YÖNETMEN: Tamam.",
            "YÖNETMEN: Tamam.",
        )
        self.assertTrue(ok, reason)

    def test_rejects_source_echo_when_source_available(self):
        ok, reason = ht.validate_polish_candidate(
            "Buradaki ates bu mu?",
            "Ist das hier das Feuer?",
            "Ist das hier das Feuer?",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "source_echo")

    def test_rejects_source_negation_loss(self):
        ok, reason = ht.validate_polish_candidate(
            "Bilmiyorum.",
            "Biliyorum.",
            source_text="I don't know.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "source_negation")

    def test_allows_cannot_wait_idiom_without_visible_negation(self):
        ok, reason = ht.validate_polish_candidate(
            "Gormek icin sabirsizlaniyorum.",
            "Gormeyi cok istiyorum.",
            source_text="I can't wait to see it.",
        )
        self.assertTrue(ok, reason)

    def test_rejects_source_question_loss(self):
        ok, reason = ht.validate_polish_candidate(
            "Emin misin?",
            "Eminsin.",
            source_text="Are you sure?",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "source_question")

    def test_rejects_source_number_loss(self):
        ok, reason = ht.validate_polish_candidate(
            "On iki kisi vardi.",
            "On bir kisi vardi.",
            source_text="There were 12 people.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "source_numbers")

    def test_rejects_causative_want_backslide(self):
        ok, reason = ht.validate_polish_candidate(
            "insani icine cekiyor ve devamini izlemek istetiyordu.",
            "insani icine cekiyor ve devamini izlemek istiyordu.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "causative_backslide")

    def test_rejects_changed_bracket_label(self):
        ok, reason = ht.validate_polish_candidate(
            "[anlatıcı] Tut'un mezarının",
            "[narrator] Tut'un mezarının",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "bracket_labels")

    def test_rejects_neighbor_text_echo(self):
        ok, reason = ht.validate_polish_candidate(
            "ölümcül olabilecek patojenler\niçerebilir.",
            "Eski Mısır mezarlarındaki\ninsan kalıntıları",
            neighbor_texts=["Eski Mısır mezarlarındaki\ninsan kalıntıları"],
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "neighbor_echo")

    def test_rejects_fragment_terminal_backslide(self):
        ok, reason = ht.validate_polish_candidate(
            "<i>muhabirlik yaparak</i>",
            "<i>muhabirlik yapıyordu.</i>",
            fragment_tag="start",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "fragment_terminal")

    def test_rejects_new_foreign_script(self):
        ok, reason = ht.validate_polish_candidate(
            "mesela sirke,\nelektrik üretebilir.",
            "mesela sirke,\n电 üretebilir.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "foreign_script")

    def test_rejects_destructive_shorten(self):
        ok, reason = ht.validate_polish_candidate(
            (
                "[Doktor Sahni] Gavin polisle konuşurken, ailesinin iyi oluşunu "
                "ya da esenliğini hiç sormuyor. Kendini iyi bir çocuk, her şekilde "
                "yardım etmeye ve işbirliğine hazır biri gibi göstermeye çalışıyor."
            ),
            "[Doktor Sahni] Gavin polisle konuşurken,",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "too_short")


class PolishRiskHintTest(unittest.TestCase):
    def test_flags_literal_and_english_residue(self):
        hints = ht.polish_risk_hints(
            "This is not good for me, bro.",
            "Bu benim için good değil bro.",
        )
        self.assertIn("english_residue", hints)
        self.assertIn("literal_or_stilted_turkish", hints)

    def test_flags_possibly_untranslated(self):
        hints = ht.polish_risk_hints("Hello there.", "Hello there.")
        self.assertIn("possibly_untranslated", hints)


class LocalFixesTest(unittest.TestCase):
    def test_cleans_common_dutch_residue(self):
        fixed, count = ht._apply_local_fixes(
            "hoofse liefde, metafoor, the Laatste Avondmaal, "
            "Het Barre Land'in, De Toverberg’i, "
            "Wereld als Wil en Voorstelling’ını, queeste'ye ve mytle."
        )
        self.assertGreater(count, 0)
        self.assertEqual(
            fixed,
            "saray aşkı, metafor, Son Akşam Yemeği, "
            "Çorak Ülke'nin, Büyülü Dağ’ı, "
            "İrade ve Tasarım Olarak Dünya’sını, arayışa ve mit.",
        )


class PolishContextHintTest(unittest.TestCase):
    def test_context_hint_includes_pronouns_and_idioms(self):
        ctx = SimpleNamespace(
            tone="street comedy",
            setting="mansion",
            summary="Reality show conflict.",
            characters=[SimpleNamespace(name="Alex", speaking_style="fast slang")],
        )
        hint = ht.build_polish_context_hint(
            (
                ctx,
                {},
                {"Alex-Bora": "sen"},
                {},
                [],
                {"spill the beans": "ağzındaki baklayı çıkarmak"},
                [{"src": "Netflix", "action": "keep"}],
            ),
            tgt_lang="Turkish",
        )

        self.assertIn("street comedy", hint)
        self.assertIn("Alex-Bora=sen", hint)
        self.assertIn("spill the beans", hint)
        self.assertIn("Netflix=keep", hint)


class NativeReaderPassSafetyTest(unittest.TestCase):
    def _fake_openai_module(self, fixes, prompts=None):
        class FakeCompletions:
            def create(self, **kwargs):
                if prompts is not None:
                    prompts.append(kwargs["messages"][0]["content"])
                return SimpleNamespace(
                    usage=None,
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content=ht.json.dumps(fixes, ensure_ascii=False))
                        )
                    ],
                )

        class FakeOpenAI:
            def __init__(self, api_key=None, base_url=None):
                self.api_key = api_key
                self.base_url = base_url
                self.chat = SimpleNamespace(completions=FakeCompletions())

        return SimpleNamespace(OpenAI=FakeOpenAI)

    def _fake_openai_sequence(self, responses, prompts=None):
        queued = list(responses)

        class FakeCompletions:
            def create(self, **kwargs):
                if prompts is not None:
                    prompts.append(kwargs["messages"][0]["content"])
                payload = queued.pop(0)
                if isinstance(payload, Exception):
                    raise payload
                return SimpleNamespace(
                    usage=None,
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content=ht.json.dumps(payload, ensure_ascii=False)
                            )
                        )
                    ],
                )

        class FakeOpenAI:
            def __init__(self, api_key=None, base_url=None):
                self.api_key = api_key
                self.base_url = base_url
                self.chat = SimpleNamespace(completions=FakeCompletions())

        return SimpleNamespace(OpenAI=FakeOpenAI)

    def test_native_reader_pass_caps_changes_to_twenty_percent(self):
        blocks = [(i, "00:00:00,000 --> 00:00:01,000", f"Satır {i}.") for i in range(1, 11)]
        fixes = [{"id": str(i), "fixed": f"Düzeltilmiş satır {i}."} for i in range(1, 6)]
        prompts = []
        logs = []

        with patch.dict("sys.modules", {"openai": self._fake_openai_module(fixes, prompts)}):
            result = ht.native_reader_pass(
                blocks,
                helper_api_key="test",
                log_fn=lambda msg, level="info": logs.append((level, msg)),
            )

        changed = [text for _, _, text in result if text.startswith("Düzeltilmiş")]
        self.assertEqual(len(changed), 2)
        self.assertIn("En fazla 2 satır düzelt", prompts[0])
        self.assertTrue(any("%20 sınırı" in msg for _, msg in logs))

    def test_native_reader_pass_rejects_validator_failures(self):
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "<i>Git buradan.</i>")]
        fixes = [{"id": "1", "fixed": "Git buradan."}]
        logs = []

        with patch.dict("sys.modules", {"openai": self._fake_openai_module(fixes)}):
            result = ht.native_reader_pass(
                blocks,
                helper_api_key="test",
                log_fn=lambda msg, level="info": logs.append((level, msg)),
            )

        self.assertEqual(result[0][2], "<i>Git buradan.</i>")
        self.assertTrue(any("güvenlik filtresinden" in msg and "format_tags" in msg for _, msg in logs))

    def test_native_reader_pass_rejects_english_backslide(self):
        original = "-WOOD: Yani buradaki ates bu mu?\n-Bu, ates iste."
        blocks = [(71, "00:05:09,797 --> 00:05:12,027", original)]
        fixes = [{"id": "71", "fixed": "-WOOD: So is this the fire here?\n-Bu, ates iste."}]
        logs = []

        with patch.dict("sys.modules", {"openai": self._fake_openai_module(fixes)}):
            result = ht.native_reader_pass(
                blocks,
                helper_api_key="test",
                src_map={"71": "WOOD: So is this the fire here?\nThis is the fire."},
                log_fn=lambda msg, level="info": logs.append((level, msg)),
            )

        self.assertEqual(result[0][2], original)
        self.assertTrue(any("english_backslide" in msg for _, msg in logs))

    def test_native_reader_pass_rejects_neighbor_echo(self):
        blocks = [
            (1350, "00:00:00,000 --> 00:00:01,000", "Eski Mısır mezarlarındaki\ninsan kalıntıları"),
            (1351, "00:00:01,000 --> 00:00:02,000", "ölümcül olabilecek patojenler\niçerebilir."),
        ]
        fixes = [{"id": "1351", "fixed": "Eski Mısır mezarlarındaki\ninsan kalıntıları"}]
        logs = []

        with patch.dict("sys.modules", {"openai": self._fake_openai_module(fixes)}):
            result = ht.native_reader_pass(
                blocks,
                helper_api_key="test",
                log_fn=lambda msg, level="info": logs.append((level, msg)),
            )

        self.assertEqual(result[1][2], "ölümcül olabilecek patojenler\niçerebilir.")
        self.assertTrue(any("neighbor_echo" in msg for _, msg in logs))

    def test_native_reader_source_aware_change_requires_second_review(self):
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "Bu sabahın nesi iyi?")]
        fixes = [{"id": "1", "fixed": "Bu sabahta iyi olan ne?"}]
        decisions = [{"id": "1", "accept": False}]
        prompts = []
        logs = []

        with patch.dict(
            "sys.modules",
            {"openai": self._fake_openai_sequence([fixes, decisions], prompts)},
        ):
            result = ht.native_reader_pass(
                blocks,
                helper_api_key="test",
                src_map={"1": "What's good about this morning?"},
                log_fn=lambda msg, level="info": logs.append((level, msg)),
            )

        self.assertEqual(result, blocks)
        self.assertEqual(len(prompts), 2)
        self.assertIn('"before": "Bu sabahın nesi iyi?"', prompts[1])
        self.assertIn('"after": "Bu sabahta iyi olan ne?"', prompts[1])
        self.assertTrue(any("native_second_review" in msg for _, msg in logs))

    def test_native_reader_second_review_accepts_clear_improvement(self):
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "Ne yapıyorsun sen burada?")]
        fixes = [{"id": "1", "fixed": "Sen burada ne yapıyorsun?"}]
        decisions = [{"id": "1", "accept": True}]

        with patch.dict(
            "sys.modules",
            {"openai": self._fake_openai_sequence([fixes, decisions])},
        ):
            result = ht.native_reader_pass(
                blocks,
                helper_api_key="test",
                src_map={"1": "What are you doing here?"},
            )

        self.assertEqual(result[0][2], "Sen burada ne yapıyorsun?")

    def test_native_reader_second_review_rejects_duplicate_decisions(self):
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "Ne yapıyorsun sen burada?")]
        fixes = [{"id": "1", "fixed": "Sen burada ne yapıyorsun?"}]
        decisions = [
            {"id": "1", "accept": True},
            {"id": "1", "accept": False},
        ]

        with patch.dict(
            "sys.modules",
            {"openai": self._fake_openai_sequence([fixes, decisions])},
        ):
            result = ht.native_reader_pass(
                blocks,
                helper_api_key="test",
                src_map={"1": "What are you doing here?"},
            )

        self.assertEqual(result, blocks)

    def test_native_reader_rejects_conflicting_duplicate_fixes(self):
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "Eski çeviri.")]
        fixes = [
            {"id": "1", "fixed": "İlk öneri."},
            {"id": "1", "fixed": "Çelişen ikinci öneri."},
        ]
        logs = []

        with patch.dict("sys.modules", {"openai": self._fake_openai_module(fixes)}):
            result = ht.native_reader_pass(
                blocks,
                helper_api_key="test",
                log_fn=lambda msg, level="info": logs.append((level, msg)),
            )

        self.assertEqual(result, blocks)
        self.assertTrue(any("duplicate_fix_conflict" in msg for _, msg in logs))

    def test_native_reader_rejects_partial_fragment_rewrite(self):
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Onları görünce"),
            (2, "00:00:01,000 --> 00:00:02,000", "eski aşkım gelir aklıma."),
        ]
        fixes = [{"id": "2", "fixed": "eski aşkım gelir aklıma ya."}]
        logs = []

        with patch.dict("sys.modules", {"openai": self._fake_openai_module(fixes)}):
            result = ht.native_reader_pass(
                blocks,
                helper_api_key="test",
                src_map={
                    "1": "Seeing them reminds me",
                    "2": "of an old love.",
                },
                log_fn=lambda msg, level="info": logs.append((level, msg)),
            )

        self.assertEqual(result, blocks)
        self.assertTrue(any("fragment_group_partial" in msg for _, msg in logs))

    def test_native_reader_fragment_review_is_atomic(self):
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Onları görünce"),
            (2, "00:00:01,000 --> 00:00:02,000", "eski aşkım gelir aklıma."),
        ]
        fixes = [
            {"id": "1", "fixed": "Onları görünce ya"},
            {"id": "2", "fixed": "eski aşkım gelir aklıma ya."},
        ]
        decisions = [
            {"id": "1", "accept": True},
            {"id": "2", "accept": False},
        ]

        with patch.dict(
            "sys.modules",
            {"openai": self._fake_openai_sequence([fixes, decisions])},
        ):
            result = ht.native_reader_pass(
                blocks,
                helper_api_key="test",
                src_map={
                    "1": "Seeing them reminds me",
                    "2": "of an old love.",
                },
            )

        self.assertEqual(result, blocks)


class QcSeveritySplitTest(unittest.TestCase):
    def test_missing_or_unknown_severity_fails_closed(self):
        self.assertEqual(ht.normalize_qc_severity(None), "high")
        self.assertEqual(ht.normalize_qc_severity("unknown"), "high")
        self.assertEqual(ht.normalize_qc_severity("medium"), "med")

    def test_low_severity_valid_suggestion_auto_applies(self):
        issues = [
            {
                "id": "1",
                "current": "Bu benim için iyi değil.",
                "suggestion": "Bu bence iyi değil.",
                "severity": "low",
            }
        ]

        auto_issues, review_issues = ht.split_qc_issues_for_review(issues)

        self.assertEqual(len(auto_issues), 1)
        self.assertEqual(review_issues, [])

    def test_low_severity_invalid_suggestion_still_needs_review(self):
        issues = [
            {
                "id": "1",
                "current": "<i>Git buradan.</i>",
                "suggestion": "Git buradan.",
                "severity": "low",
            }
        ]

        auto_issues, review_issues = ht.split_qc_issues_for_review(issues)

        self.assertEqual(auto_issues, [])
        self.assertEqual(len(review_issues), 1)


class NativeReaderPassSourceAwareTest(unittest.TestCase):
    def _fake_openai_module(self, fixes, prompts=None):
        class FakeCompletions:
            def create(self, **kwargs):
                if prompts is not None:
                    prompts.append(kwargs["messages"][0]["content"])
                return SimpleNamespace(
                    usage=None,
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content=ht.json.dumps(fixes, ensure_ascii=False))
                        )
                    ],
                )

        class FakeOpenAI:
            def __init__(self, api_key=None, base_url=None):
                self.api_key = api_key
                self.base_url = base_url
                self.chat = SimpleNamespace(completions=FakeCompletions())

        return SimpleNamespace(OpenAI=FakeOpenAI)

    def test_native_reader_pass_sends_source_and_frag(self):
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Tarih boyunca insanlık boğuştu,"),
            (2, "00:00:01,000 --> 00:00:02,000", "Armageddon korkularıyla,")
        ]
        src_map = {
            "1": "Throughout history, humanity has struggled,",
            "2": "with fears of Armageddon,"
        }
        fixes = []
        prompts = []

        with patch.dict("sys.modules", {"openai": self._fake_openai_module(fixes, prompts)}):
            ht.native_reader_pass(
                blocks,
                helper_api_key="test",
                src_map=src_map
            )

        self.assertEqual(len(prompts), 1)
        self.assertIn("Cümle Akışı (Söz Dizimi)", prompts[0])
        self.assertIn('"en": "Throughout history, humanity has struggled,"', prompts[0])
        self.assertIn('"frag": "start"', prompts[0])
        self.assertIn('"frag": "end"', prompts[0])


class PolishPassSourceAndFragTest(unittest.TestCase):
    def _fake_openai_module(self, fixes, prompts=None):
        class FakeCompletions:
            def create(self, **kwargs):
                if prompts is not None:
                    prompts.append(kwargs["messages"][1]["content"]) # index 1 is user content in _polish_pass
                return SimpleNamespace(
                    usage=None,
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content=ht.json.dumps(fixes, ensure_ascii=False))
                        )
                    ],
                )

        class FakeOpenAI:
            def __init__(self, api_key=None, base_url=None):
                self.api_key = api_key
                self.base_url = base_url
                self.chat = SimpleNamespace(completions=FakeCompletions())

        return SimpleNamespace(OpenAI=FakeOpenAI)

    def test_polish_pass_sends_source_and_frag(self):
        with patch.dict(sys.modules, {
            "customtkinter": _CtkStub(),
            "openai": SimpleNamespace(OpenAI=object),
        }):
            import subtitle_translator_gui as gui
        class MockApp:
            _stop_flag = False
            def _update_tokens(self, *args, **kwargs):
                pass
            def _log(self, *args, **kwargs):
                pass

        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Tarih boyunca insanlık boğuştu,"),
            (2, "00:00:01,000 --> 00:00:02,000", "Armageddon korkularıyla,")
        ]
        src_map = {
            "1": "Throughout history, humanity has struggled,",
            "2": "with fears of Armageddon,"
        }
        fixes = []
        prompts = []

        with patch.dict("sys.modules", {"openai": self._fake_openai_module(fixes, prompts)}):
            gui.App._polish_pass(
                MockApp(),
                blocks,
                "Turkish",
                "test",
                "http://test",
                "gpt-5.4-mini",
                src_map=src_map
            )

        self.assertEqual(len(prompts), 1)
        self.assertIn('"en": "Throughout history, humanity has struggled,"', prompts[0])
        self.assertIn('"frag": "start"', prompts[0])
        self.assertIn('"frag": "end"', prompts[0])


if __name__ == "__main__":
    unittest.main()
