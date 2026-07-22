import unittest
from unittest.mock import MagicMock, patch
import hybrid_translate as ht


class PassSafetyGuardsTest(unittest.TestCase):

    def test_qc_review_cross_chunk_id_not_returned(self):
        """QC yalnızca aktif chunk içindeki ID için issue üretebilir."""
        cues = [MagicMock(index=i, text=f"Source {i}") for i in range(1, 202)]
        tr_blocks = [
            (str(i), f"00:00:{i % 60:02d},000 --> 00:00:{i % 60:02d},900", f"Çeviri {i}")
            for i in range(1, 202)
        ]
        first = MagicMock()
        first.choices = [MagicMock()]
        first.choices[0].message.content = (
            '{"issues":[{"id":"201","original":"Source 201",'
            '"current":"Çeviri 201","problem":"Sorun","suggestion":"Düzeltme",'
            '"severity":"low"}]}'
        )
        second = MagicMock()
        second.choices = [MagicMock()]
        second.choices[0].message.content = '{"issues":[]}'

        with patch("openai.OpenAI") as mock_openai:
            client = MagicMock()
            mock_openai.return_value = client
            client.chat.completions.create.side_effect = [first, second]

            issues = ht.quality_check_with_helper(cues, tr_blocks, helper_api_key="test_key")

        self.assertEqual(issues, [])

    def test_qc_review_binds_source_and_current_to_chunk_data(self):
        """Geçerli issue modelin kopyaladığı alanlar yerine gerçek cue verisini taşır."""
        cues = [MagicMock(index=1, text="Real source")]
        tr_blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Gerçek çeviri")]
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = (
            '{"issues":[{"id":"1","original":"Hallucinated source",'
            '"current":"Gerçek çeviri","problem":"Sorun","suggestion":"Düzeltme",'
            '"severity":"low"}]}'
        )

        with patch("openai.OpenAI") as mock_openai:
            client = MagicMock()
            mock_openai.return_value = client
            client.chat.completions.create.return_value = response

            issues = ht.quality_check_with_helper(cues, tr_blocks, helper_api_key="test_key")

        self.assertEqual(issues[0]["original"], "Real source")
        self.assertEqual(issues[0]["current"], "Gerçek çeviri")

    def test_critic_context_only_id_not_applied(self):
        """1. Context-only critic ID’si uygulanmaz."""
        cues = [
            MagicMock(index=1, text="Speaker: Hello"),
            MagicMock(index=2, text="World dialogue"),
            MagicMock(index=3, text="Source 3"),
        ]
        tr_blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Konuşmacı: Merhaba"),
            ("2", "00:00:03,000 --> 00:00:04,000", "Dünya diyaloğu"),
            ("3", "00:00:05,000 --> 00:00:06,000", "Büyük mücadele"),
        ]
        with patch("hybrid_translate.run_validators", return_value=[(2, "ts", "text", "SPEAKER_LABEL_ABSORBED_TEXT")]):
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = '[{"id": "1", "fixed": "Anlatıcı: Merhaba"}]'

            with patch("openai.OpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client
                mock_client.chat.completions.create.return_value = mock_resp

                res = ht.critic_pass_with_helper(cues, tr_blocks, helper_api_key="test_key")
                self.assertEqual(res[0][2], "Konuşmacı: Merhaba")

    def test_critic_current_id_applied(self):
        """2. Current critic ID’si uygulanır."""
        cues = [
            MagicMock(index=1, text="Hello world"),
            MagicMock(index=2, text="I am gonna fly"),
        ]
        tr_blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Merhaba dünya"),
            ("2", "00:00:03,000 --> 00:00:04,000", "Gideceğim yapacağım ben"),
        ]
        with patch("hybrid_translate.run_validators", return_value=[(2, "ts", "text", "SPEAKER_LABEL_MISMATCH")]):
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = '[{"id": "2", "fixed": "Gideceğim yapacağım ben efendim"}]'

            with patch("openai.OpenAI") as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client
                mock_client.chat.completions.create.return_value = mock_resp

                res = ht.critic_pass_with_helper(cues, tr_blocks, helper_api_key="test_key")
                self.assertEqual(res[1][2], "Gideceğim yapacağım ben efendim")

    def test_native_reader_cross_chunk_id_not_applied(self):
        """3. Native başka chunk ID’sini değiştiremez."""
        tr_blocks = [(str(i), f"00:00:{i:02d},000 --> 00:00:{i:02d},900", f"Tarih boyunca insanlık {i}") for i in range(1, 201)]

        resp_chunk1 = MagicMock()
        resp_chunk1.choices = [MagicMock()]
        resp_chunk1.choices[0].message.content = '[{"id": "190", "fixed": "Geçmiş boyunca insanlık 190"}]'

        resp_chunk2 = MagicMock()
        resp_chunk2.choices = [MagicMock()]
        resp_chunk2.choices[0].message.content = '[]'

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.side_effect = [resp_chunk1, resp_chunk2]

            res = ht.native_reader_pass(tr_blocks, helper_api_key="test_key")
            self.assertEqual(res[189][2], "Tarih boyunca insanlık 190")

    def test_native_reader_current_chunk_id_applied(self):
        """4. Native current chunk ID’sini değiştirebilir."""
        tr_blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Tarih boyunca boğuştu")]
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = '[{"id": "1", "fixed": "Tarih boyunca boğuştu efendim"}]'

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_resp

            res = ht.native_reader_pass(tr_blocks, helper_api_key="test_key")
            self.assertEqual(res[0][2], "Tarih boyunca boğuştu efendim")

    def test_qc_suggestion_rejected_by_validator_not_applied(self):
        """5. Validator reddettiği suggestion uygulanmaz."""
        issues = [{
            "id": "1",
            "original": "English source",
            "current": "Eski çeviri",
            "problem": "Bad translation",
            "suggestion": "REJECTED SUGGESTION DROP ALL TEXT AND MAKES HUGE OVEREXPANSION" + " x" * 200,
            "severity": "high"
        }]
        tr_blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Eski çeviri")]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.side_effect = Exception("API failure")

            res = ht.qc_auto_fix(issues, tr_blocks, openai_api_key="test_key", model="gpt-4o")
            self.assertEqual(res[0][2], "Eski çeviri")

    def test_qc_api_failure_preserves_original_when_suggestion_rejected(self):
        """6. API failure durumunda original korunur (suggestion geçersizse)."""
        issues = [{
            "id": "1",
            "original": "Source text",
            "current": "Eski çeviri",
            "problem": "Unnatural",
            "suggestion": "INVALID " + "x" * 300,
            "severity": "low"
        }]
        tr_blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Eski çeviri")]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.side_effect = Exception("Network error")

            res = ht.qc_auto_fix(issues, tr_blocks, openai_api_key="test_key", model="gpt-4o")
            self.assertEqual(res[0][2], "Eski çeviri")

    def test_qc_mismatched_current_does_not_overwrite_wrong_cue(self):
        """7. Modelin yanlış current alanı başka cue’yu overwrite etmez."""
        issues = [{
            "id": "1",
            "original": "Source 2 text",
            "current": "Text of cue 2",  # Cue 1 has "Text of cue 1"
            "problem": "Wrong translation",
            "suggestion": "Fixed cue 2 text",
            "severity": "high"
        }]
        tr_blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Text of cue 1"),
            ("2", "00:00:03,000 --> 00:00:04,000", "Text of cue 2"),
        ]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.side_effect = Exception("API error")

            res = ht.qc_auto_fix(issues, tr_blocks, openai_api_key="test_key", model="gpt-4o")
            self.assertEqual(res[0][2], "Text of cue 1")

    def test_qc_missing_current_does_not_bypass_reconciliation(self):
        """Eksik current alanı ID kontrolünü tek başına yeterli kılmaz."""
        issues = [{
            "id": "1",
            "original": "Good morning",
            "problem": "Unnatural",
            "suggestion": "Günaydın",
            "severity": "low",
        }]
        tr_blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Günaydın efendim")]

        with patch("openai.OpenAI") as mock_openai:
            client = MagicMock()
            mock_openai.return_value = client

            res = ht.qc_auto_fix(issues, tr_blocks, openai_api_key="test_key", model="gpt-4o")

        self.assertEqual(res[0][2], "Günaydın efendim")
        client.chat.completions.create.assert_not_called()

    def test_valid_qc_low_med_fix_applied(self):
        """8. Geçerli QC low/medium fix hâlâ uygulanır."""
        issues = [{
            "id": "1",
            "original": "Good morning",
            "current": "Günaydın efendim",
            "problem": "Overly formal",
            "suggestion": "Günaydın",
            "severity": "low"
        }]
        tr_blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Günaydın efendim")]

        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.side_effect = Exception("API failure")

            res = ht.qc_auto_fix(issues, tr_blocks, openai_api_key="test_key", model="gpt-4o")
            self.assertEqual(res[0][2], "Günaydın")


if __name__ == "__main__":
    unittest.main()
