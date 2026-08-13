import ast
import inspect
import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import hybrid_translate as ht
import subtitle_translator_gui as gui


_TS = "00:00:01,000 --> 00:00:02,000"


def _response(items):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            content=json.dumps(items, ensure_ascii=False)))],
        usage=None,
    )


def _checkpoint_response(items):
    response = _response(items)
    response.response_checkpoint_hit = True
    return response


class LicensedIdentityRepairTest(unittest.TestCase):
    def test_locked_latin_identity_is_not_missing(self):
        locked = {"coitus interruptus": "coitus interruptus"}
        blocks = [("715", _TS, "Coitus interruptus.")]
        with patch("subtitle_translator_gui._safe_chat_create") as create:
            result, repaired = gui._repair_untranslated_sync(
                blocks, {"715": "Coitus interruptus."}, object(),
                "Portuguese", "Turkish", locked_terms=locked)

        self.assertEqual(result, blocks)
        self.assertEqual(repaired, 0)
        create.assert_not_called()
        self.assertEqual(gui._partial_missing_translation_ids(
            blocks, {"715": "Coitus interruptus."},
            [("715", _TS, "Coitus interruptus.")],
            locked_terms=locked, source_language="Portuguese"), [])

    def test_repeated_locked_latin_identity_is_not_missing(self):
        source = "Mea culpa, mea culpa, mea culpa!"
        locked = {"Mea culpa": "Mea culpa"}
        blocks = [("57", _TS, source)]
        with patch("subtitle_translator_gui._safe_chat_create") as create:
            result, repaired = gui._repair_untranslated_sync(
                blocks, {"57": source}, object(), "English", "Turkish",
                locked_terms=locked)

        self.assertEqual(result, blocks)
        self.assertEqual(repaired, 0)
        create.assert_not_called()
        self.assertEqual(gui._partial_missing_translation_ids(
            blocks, {"57": source}, [("57", _TS, source)],
            locked_terms=locked, source_language="English"), [])

    def test_magna_cum_laude_is_not_english_residue(self):
        source = (
            "Dr. Genoves has three international doctorates, "
            "two of them magna cum laude")
        candidate = (
            "Dr. Genoves'in üç uluslararası doktora derecesi var; "
            "ikisi magna cum laude")
        self.assertFalse(ht.has_source_english_overlap(source, candidate))
        self.assertFalse(gui._is_untranslated(
            source, candidate, source_language="English"))

        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=_response([{"i": "306", "t": candidate}])):
            result, repaired = gui._repair_untranslated_sync(
                [("306", _TS, "[HATA]")], {"306": source}, object(),
                "English", "Turkish")
        self.assertEqual(repaired, 1)
        self.assertEqual(result[0][2], candidate)

    def test_real_english_residue_still_fails(self):
        self.assertTrue(gui._is_untranslated(
            "Use the public phone box outside.",
            "Dışarıdaki public phone box kullan.",
            source_language="English"))
        self.assertTrue(gui._is_untranslated(
            "Please come here.", "Please come here.",
            source_language="English"))

    def test_scientific_binomial_identity_is_not_retried(self):
        source = "Macrolepiota procera."
        blocks = [("321", _TS, source)]

        with patch("subtitle_translator_gui._safe_chat_create") as create:
            result, repaired = gui._repair_untranslated_sync(
                blocks, {"321": source}, object(), "English", "Turkish")

        self.assertEqual(result, blocks)
        self.assertEqual(repaired, 0)
        create.assert_not_called()
        self.assertEqual(gui._partial_missing_translation_ids(
            blocks, {"321": source}, [("321", _TS, source)],
            source_language="English"), [])

    def test_greetings_and_all_caps_dialogue_are_not_name_exempt(self):
        for source in (
                "Good Morning", "Happy Birthday", "Merry Christmas",
                "Sweet Dreams", "GET OUT OF HERE!",
                "WHAT A GREAT ROOM THIS IS. WOW!"):
            with self.subTest(source=source):
                self.assertTrue(gui._is_untranslated(
                    source, source, source_language="English"))
        self.assertFalse(gui._is_untranslated(
            "ODDITIES SEASON FOUR", "ODDITIES SEASON FOUR",
            source_language="English"))


class PersistentRepairRetryTest(unittest.TestCase):
    def test_locked_term_does_not_match_prefix_of_another_turkish_word(self):
        self.assertTrue(ht.locked_term_violation(
            "The Island is burning.",
            "Adam yanıyor.",
            {"Island": "Ada"},
        ))

    def test_locked_term_accepts_attached_and_apostrophic_case_suffixes(self):
        self.assertFalse(ht.locked_term_violation(
            "They stayed on the Island.",
            "Adada kaldılar.",
            {"Island": "Ada"},
        ))
        self.assertFalse(ht.locked_term_violation(
            "They stayed on the Island.",
            "Ada'da kaldılar.",
            {"Island": "Ada"},
        ))

    def test_turkish_capital_i_does_not_break_locked_term_match(self):
        self.assertFalse(ht.locked_term_violation(
            "The invaders have installed a transmitter.",
            "İstilacılar bir verici yerleştirdi.",
            {"invaders": "istilacılar"},
        ))

    def test_fragment_neighbor_proper_name_is_licensed_during_repair(self):
        source_cues = [
            ("4", "00:00:01,000 --> 00:00:02,000",
             "After twenty one years of blockade, the effort and kindness"),
            ("5", "00:00:02,001 --> 00:00:03,000",
             "of Pierre-André Boutang and other friends,"),
            ("6", "00:00:03,001 --> 00:00:04,000",
             "allowed composing a new complete negative print."),
        ]
        raw = {str(idx): text for idx, _ts, text in source_cues}
        candidate = "Yirmi bir yılın ardından Pierre-André Boutang'ın çabası"
        blocks = [
            ("4", source_cues[0][1], "[HATA]"),
            ("5", source_cues[1][1], "diğer dostların desteği"),
            ("6", source_cues[2][1], "yeni bir kopya hazırlanmasını sağladı."),
        ]
        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=_response([{"i": "4", "t": candidate}])) as create:
            result, repaired = gui._repair_untranslated_sync(
                blocks, raw, object(), "English", "Turkish",
                source_cues=source_cues,
                retry_wait_fn=lambda *_args: self.fail("retry should not run"))

        self.assertEqual(repaired, 1)
        self.assertEqual(result[0][2], candidate)
        self.assertEqual(create.call_count, 1)

    def test_fragment_neighbor_locked_term_is_not_required_in_each_cue(self):
        source_cues = [
            ("4", "00:00:01,000 --> 00:00:02,000", "Gerrit Dou painted"),
            ("5", "00:00:02,001 --> 00:00:03,000", "while Rembrandt watched."),
        ]
        raw = {str(idx): text for idx, _ts, text in source_cues}
        advisories = []
        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=_response([{"i": "4", "t": "Gerrit Dou resim yaptı"}])):
            result, repaired = gui._repair_untranslated_sync(
                [("4", source_cues[0][1], "[HATA]"),
                 ("5", source_cues[1][1], "Rembrandt izledi.")],
                raw, object(), "English", "Turkish", source_cues=source_cues,
                locked_terms={"Gerrit Dou": "Gerrit Dou", "Rembrandt": "Rembrandt"},
                retry_wait_fn=lambda *_args: self.fail("retry should not run"),
                advisory_reviews_out=advisories)

        self.assertEqual(repaired, 1)
        self.assertEqual(result[0][2], "Gerrit Dou resim yaptı")
        self.assertEqual(advisories, [])

    def test_fragment_repair_keeps_translated_sentence_neighbors_in_payload(self):
        source_cues = [
            ("4", "00:00:01,000 --> 00:00:02,000",
             "After twenty one years of blockade, the effort and kindness"),
            ("5", "00:00:02,001 --> 00:00:03,000",
             "of Pierre-André Boutang and other friends,"),
            ("6", "00:00:03,001 --> 00:00:04,000",
             "allowed composing a new complete negative print."),
        ]
        raw = {str(idx): text for idx, _ts, text in source_cues}
        blocks = [
            ("4", source_cues[0][1], "[HATA]"),
            ("5", source_cues[1][1], "Pierre-André Boutang ve diğer dostların"),
            ("6", source_cues[2][1], "çabası yeni bir negatif kopya hazırlanmasını sağladı."),
        ]
        with patch("subtitle_translator_gui._safe_chat_create", return_value=_response([
                {"i": "4", "t": "Yirmi bir yıllık ablukanın ardından"},
        ])) as create:
            _result, repaired = gui._repair_untranslated_sync(
                blocks, raw, object(), "English", "Turkish",
                source_cues=source_cues)

        self.assertEqual(repaired, 1)
        payload = json.loads(create.call_args.kwargs["messages"][1]["content"])
        self.assertEqual(payload["tr"][0]["frag"], "start")
        self.assertEqual(payload["sentence_groups"], [
            {"id": "fg_4_6", "items": ["4", "5", "6"]},
        ])
        self.assertEqual(
            [str(item["i"]) for item in payload["repair_neighbors"]], ["5", "6"])

    def test_ambiguous_memory_lock_is_removed_inside_repair(self):
        source = "It's a different part of psychedelic history."
        candidate = "Bu, psikedelik tarihinin farklı bir bölümü."
        ambiguous = {
            "psychedelic": (
                "“psikedelik”; “halüsinojenik” ile bağlama göre "
                "ayrıştırılmalı."
            ),
            "history": "tarih",
            "unrelated": "ilgisiz",
        }

        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=_response([{"i": "101", "t": candidate}])) as create:
            result, repaired = gui._repair_untranslated_sync(
                [("101", _TS, "[HATA]")], {"101": source}, object(),
                "English", "Turkish", locked_terms=ambiguous,
                retry_wait_fn=lambda *_args: self.fail("retry should not run"))

        self.assertEqual(repaired, 1)
        self.assertEqual(result[0][2], candidate)
        system_prompt = create.call_args.kwargs["messages"][0]["content"]
        payload = json.loads(create.call_args.kwargs["messages"][1]["content"])
        self.assertNotIn("ayrıştırılmalı", system_prompt)
        self.assertEqual(payload["glossary"], {"history": "tarih"})

    def test_checkpoint_repair_is_attempted_only_once(self):
        waits = []
        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=_checkpoint_response([
                       {"i": "8", "t": "Please come here."}])) as create:
            result, repaired = gui._repair_untranslated_sync(
                [("8", _TS, "[HATA]")], {"8": "Please come here."},
                object(), "English", "Turkish",
                retry_wait_fn=lambda delay, _cancelled: waits.append(delay) or True)

        self.assertEqual(create.call_count, 1)
        self.assertEqual(waits, [])
        self.assertEqual(repaired, 0)
        self.assertEqual(result[0][2], "[HATA]")

    def test_locked_term_warning_is_accepted_once_and_reported(self):
        log = MagicMock()
        advisories = []
        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=_response([{"i": "4", "t": "Mary geldi."}])) as create:
            result, repaired = gui._repair_untranslated_sync(
                [("4", _TS, "[HATA]")], {"4": "John arrived."}, object(),
                "English", "Turkish", locked_terms={"John": "John"},
                log_fn=log,
                retry_wait_fn=lambda *_args: self.fail("retry should not run"),
                advisory_reviews_out=advisories)

        log_text = " ".join(str(call.args[0]) for call in log.call_args_list)
        self.assertEqual(create.call_count, 1)
        self.assertEqual(repaired, 1)
        self.assertEqual(result[0][2], "Mary geldi.")
        self.assertIn("Onarım inceleme özeti", log_text)
        self.assertIn("locked_term_violation", log_text)
        self.assertIn("kaynak='John arrived.'", log_text)
        self.assertIn("aday='Mary geldi.'", log_text)
        self.assertNotIn("Onarım reddi", log_text)
        self.assertEqual(advisories, [{
            "id": "4",
            "reason": "locked_term_violation",
            "source": "John arrived.",
            "candidate": "Mary geldi.",
        }])

    def test_shifted_question_repair_is_accepted_once_and_reported(self):
        log = MagicMock()
        advisories = []
        source = "How did I know he would lie there all night?"
        candidate = "Dondurma bütün gece soğuktu."
        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=_response([{"i": "1417", "t": candidate}])) as create:
            result, repaired = gui._repair_untranslated_sync(
                [("1417", _TS, "[HATA]")], {"1417": source}, object(),
                "English", "Turkish", log_fn=log,
                retry_wait_fn=lambda *_args: self.fail("retry should not run"),
                advisory_reviews_out=advisories)

        log_text = " ".join(str(call.args[0]) for call in log.call_args_list)
        self.assertEqual(create.call_count, 1)
        self.assertEqual(repaired, 1)
        self.assertEqual(result[0][2], candidate)
        self.assertIn("source_question", log_text)
        self.assertNotIn("Onarım reddi", log_text)
        self.assertEqual(advisories, [{
            "id": "1417",
            "reason": "source_question",
            "source": source,
            "candidate": candidate,
        }])

    def test_negation_and_number_mismatches_are_advisory(self):
        cases = (
            ("He did not leave.", "Gitti.", "source_negation"),
            ("There were 15 people.", "Orada 5 kişi vardı.", "source_numbers"),
        )
        for source, candidate, expected in cases:
            with self.subTest(expected=expected):
                reason = gui._repair_candidate_rejection_reason(
                    source, candidate, src_lang="English", tgt_lang="Turkish")
                self.assertEqual(reason, expected)
                self.assertTrue(gui._repair_reason_is_advisory(reason))

    def test_quoted_song_title_translation_is_accepted_without_retry(self):
        source = (
            'One seven-inch single - "I\'m the Leader of the Gang," brackets, '
            '"I Am" by Gary Glitter.'
        )
        candidate = (
            'Bir tane yedi inçlik plak: Gary Glitter\'dan '
            '"I\'m the Leader of the Gang", parantez içinde, "I Am".'
        )
        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=_response([{"i": "318", "t": candidate}])) as create:
            result, repaired = gui._repair_untranslated_sync(
                [("318", _TS, "[HATA]")], {"318": source}, object(),
                "English", "Turkish",
                retry_wait_fn=lambda *_args: self.fail("retry should not run"))

        self.assertEqual(repaired, 1)
        self.assertEqual(result[0][2], candidate)
        self.assertEqual(create.call_count, 1)

    def test_each_missing_cue_is_sent_once_and_alone(self):
        blocks = [("1", _TS, "[HATA]"), ("2", _TS, "[HATA]")]
        source = {"1": "First source.", "2": "Second source."}
        responses = [
            _response([{"i": "1", "t": "Birinci kaynak."}]),
            _response([{"i": "2", "t": "İkinci kaynak."}]),
        ]
        waits = []

        with patch("subtitle_translator_gui._safe_chat_create",
                   side_effect=responses) as create:
            result, repaired = gui._repair_untranslated_sync(
                blocks, source, object(), "English", "Turkish",
                retry_wait_fn=lambda delay, _cancelled: waits.append(delay) or True)

        self.assertEqual(repaired, 2)
        self.assertEqual([row[2] for row in result], [
            "Birinci kaynak.", "İkinci kaynak."])
        first_payload = json.loads(
            create.call_args_list[0].kwargs["messages"][1]["content"])
        second_payload = json.loads(
            create.call_args_list[1].kwargs["messages"][1]["content"])
        self.assertEqual([str(item["i"]) for item in first_payload["tr"]], ["1"])
        self.assertEqual([str(item["i"]) for item in second_payload["tr"]], ["2"])
        self.assertEqual(waits, [])

    def test_failed_candidate_is_reported_without_retry(self):
        log = MagicMock()
        waits = []
        advisories = []
        response = _response([{"i": "8", "t": "Please come here."}])
        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=response) as create:
            result, repaired = gui._repair_untranslated_sync(
                [("8", _TS, "[HATA]")], {"8": "Please come here."},
                object(), "English", "Turkish", log_fn=log,
                retry_wait_fn=lambda delay, _cancelled: waits.append(delay) or True,
                advisory_reviews_out=advisories)

        self.assertEqual(create.call_count, 1)
        self.assertEqual(waits, [])
        self.assertEqual(repaired, 0)
        self.assertEqual(result[0][2], "[HATA]")
        log_text = " ".join(str(call.args[0]) for call in log.call_args_list)
        self.assertIn("Onarım reddi #8", log_text)
        self.assertIn("identical_source", log_text)
        self.assertIn("deneme 1/1", log_text)
        self.assertIn("tek API denemesinde", log_text)
        payload = json.loads(
            create.call_args.kwargs["messages"][1]["content"])
        self.assertEqual(payload["repair_attempt"], 1)
        self.assertNotIn("repair_retry", payload)
        self.assertEqual(advisories, [{
            "id": "8",
            "reason": "identical_source",
            "source": "Please come here.",
            "candidate": "Please come here.",
            "unresolved": True,
        }])

    def test_retry_wait_is_never_used(self):
        waits = []

        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=SimpleNamespace(choices=[], usage=None)) as create:
            gui._repair_untranslated_sync(
                [("1", _TS, "[HATA]")], {"1": "Translate me."},
                object(), "English", "Turkish",
                retry_wait_fn=lambda delay, _cancelled: waits.append(delay) or True)

        self.assertEqual(create.call_count, 1)
        self.assertEqual(waits, [])

    def test_permanent_http_400_stops_all_batches(self):
        class BadRequest(RuntimeError):
            status_code = 400

        blocks = [
            (str(idx), _TS, "[HATA]") for idx in range(1, 31)
        ]
        source = {
            str(idx): f"Source dialogue {idx}." for idx in range(1, 31)
        }
        permanent = MagicMock()
        with patch("subtitle_translator_gui._safe_chat_create",
                   side_effect=BadRequest("invalid request")) as create:
            gui._repair_untranslated_sync(
                blocks, source, object(), "English", "Turkish",
                permanent_failure_cb=permanent,
                retry_wait_fn=lambda _delay, _cancelled: True)

        self.assertEqual(create.call_count, 1)
        permanent.assert_called_once_with()


class CueLocalLeakLicenseTest(unittest.TestCase):
    def test_neighbor_source_cannot_license_foreign_token(self):
        sources = {"1": "Buñuel arrived.", "2": "The girl arrived."}
        self.assertEqual(gui._chunk_leak_source_text(sources, "2"),
                         "The girl arrived.")
        self.assertTrue(ht.has_non_turkish_target_leak(
            "Buñuel geldi.", source_text=gui._chunk_leak_source_text(sources, "2")))


class RepairFlowParityTest(unittest.TestCase):
    def test_every_production_repair_call_passes_locked_terms(self):
        tree = ast.parse(inspect.getsource(gui))
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "_repair_untranslated_sync"
        ]
        self.assertGreaterEqual(len(calls), 6)
        for call in calls:
            with self.subTest(line=call.lineno):
                self.assertIn("locked_terms", {
                    keyword.arg for keyword in call.keywords})

    def test_jsonl_import_uses_semantic_missing_scan_and_stops_before_write(self):
        source = inspect.getsource(gui.App._import_jsonl)
        scan_pos = source.find("missing_ids = _partial_missing_translation_ids(")
        stop_pos = source.find("if self._stop_flag:", scan_pos)
        write_pos = source.find("write_srt(_write_path", stop_pos)
        self.assertTrue(0 <= scan_pos < stop_pos < write_pos)


class IdentityInterjectionRegressionTest(unittest.TestCase):
    def test_quoted_date_only_cues_are_valid_identity_translations(self):
        for text in ('"12/8/54."', '"9/9/54."', "'03-11-1986'"):
            with self.subTest(text=text):
                self.assertTrue(gui._src_is_numeric_only(text))
                self.assertEqual(gui._untranslated_reason(text, text), "")

    def test_short_identity_interjections_are_valid_translations(self):
        self.assertEqual(gui._untranslated_reason("Hey, hey!", "Hey, hey!"), "")
        self.assertEqual(gui._untranslated_reason("Jack, hey.", "Jack, hey."), "")
        self.assertEqual(gui._untranslated_reason("Bravo, bravo.", "Bravo, bravo."), "")
        self.assertEqual(
            gui._untranslated_reason("Hello everyone.", "Hello everyone."),
            "identical_source",
        )
        self.assertEqual(
            gui._untranslated_reason("No, no!", "No, no!"),
            "identical_source",
        )

    def test_real_repair_flow_accepts_identity_interjections_without_retry(self):
        source = {"96": "Hey, hey!", "981": "Jack, hey.", "1441": "Hey, hey."}
        blocks = [(idx, _TS, "[HATA]") for idx in source]
        responses = [
            _response([{"i": idx, "t": text}])
            for idx, text in source.items()
        ]

        with patch("subtitle_translator_gui._safe_chat_create",
                   side_effect=responses) as create:
            result, repaired = gui._repair_untranslated_sync(
                blocks, source, object(), "English", "Turkish",
                retry_wait_fn=lambda *_args: self.fail("retry should not run"))

        self.assertEqual(repaired, 3)
        self.assertEqual([text for _idx, _ts, text in result], list(source.values()))
        self.assertEqual(create.call_count, 3)
        self.assertEqual(gui._partial_missing_translation_ids(
            result, source, result, source_language="English"), [])


if __name__ == "__main__":
    unittest.main()
