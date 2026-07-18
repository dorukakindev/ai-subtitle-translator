"""Yarım-Kalan-Batch penceresinin OpenAI durum kontrolü (_fetch_batch_statuses /
_batch_status_label) ve 'Seçilenleri Sil'in canlı-batch onay kapısı.

NEDEN: batch_owner kilidi (2026-07-16) yanlış pencereyi bastırıyor ama pencere HAKLI
olarak çıktığında kullanıcı hâlâ kördü — hangi batch'in bitmiş/hâlâ işlendiğini
bilmeden 'Seçilenleri Sil' tıklıyordu. Bu, işlenmekte olan (parası ödenmiş) bir
batch'in kurtarma verisini silme riski taşır."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import subtitle_translator_gui as gui


class FetchBatchStatusesTest(unittest.TestCase):
    def _fake_client(self, statuses: dict, raise_for=()):
        class _Batches:
            def retrieve(self, bid):
                if bid in raise_for:
                    raise RuntimeError("network error")
                return SimpleNamespace(status=statuses.get(bid, "completed"))
        return SimpleNamespace(batches=_Batches())

    def test_fetches_status_per_id(self):
        with patch("openai.OpenAI",
                    return_value=self._fake_client({"b1": "in_progress", "b2": "completed"})):
            result = gui._fetch_batch_statuses("key", ["b1", "b2"])
        self.assertEqual(result, {"b1": "in_progress", "b2": "completed"})

    def test_per_id_failure_isolated_as_unknown(self):
        with patch("openai.OpenAI",
                    return_value=self._fake_client({"b1": "completed"}, raise_for={"b2"})):
            result = gui._fetch_batch_statuses("key", ["b1", "b2"])
        self.assertEqual(result, {"b1": "completed", "b2": "unknown"})

    def test_empty_api_key_returns_all_unknown_no_call(self):
        with patch("openai.OpenAI") as mock_oai:
            result = gui._fetch_batch_statuses("", ["b1", "b2"])
        mock_oai.assert_not_called()
        self.assertEqual(result, {"b1": "unknown", "b2": "unknown"})

    def test_empty_batch_ids_returns_empty_dict(self):
        result = gui._fetch_batch_statuses("key", [])
        self.assertEqual(result, {})

    def test_client_construction_failure_falls_back_to_unknown_for_all(self):
        with patch("openai.OpenAI", side_effect=RuntimeError("bad key")):
            result = gui._fetch_batch_statuses("key", ["b1", "b2"])
        self.assertEqual(result, {"b1": "unknown", "b2": "unknown"})


class BatchStatusLabelTest(unittest.TestCase):
    def test_live_statuses(self):
        for s in ("validating", "in_progress", "finalizing", "cancelling"):
            text, kind = gui._batch_status_label(s)
            self.assertEqual(kind, "live", s)
            self.assertIn(s, text)

    def test_completed_is_done(self):
        text, kind = gui._batch_status_label("completed")
        self.assertEqual(kind, "done")

    def test_dead_statuses(self):
        for s in ("failed", "expired", "cancelled"):
            text, kind = gui._batch_status_label(s)
            self.assertEqual(kind, "dead", s)

    def test_unknown_status_maps_to_unknown_kind(self):
        text, kind = gui._batch_status_label("unknown")
        self.assertEqual(kind, "unknown")

    def test_unrecognized_future_status_falls_back_to_unknown(self):
        # OpenAI yeni bir durum değeri eklerse (bilinen 8 değerin dışında) -> unknown.
        # Bu GÜVENLİ TARAF: bilinmeyen durum silme onayında CANLI sayılır (aşağıya bkz.).
        text, kind = gui._batch_status_label("some_future_status")
        self.assertEqual(kind, "unknown")


class DeleteConfirmationGateSourceTest(unittest.TestCase):
    """Modal Tk penceresini (grab_set) test sürecinde tetiklemek riskli (bkz.
    tests/_gui_app.py'deki 2026-07-16 dersi) — bu yüzden risk-kapısının varlığı
    kaynak düzeyinde kilitlenir: hem canlı hem bilinmeyen durum onay istemeli."""

    def test_delete_selected_checks_live_and_unknown_status(self):
        src = gui.__file__
        with open(src, encoding="utf-8") as f:
            text = f.read()
        # _delete_selected içindeki risk-kontrolü bölümünü izole al
        start = text.index("def _delete_selected")
        end = text.index("ctk.CTkButton(btn_fr, text=\"Tümünü Seç\"")
        block = text[start:end]
        self.assertIn("_BATCH_LIVE_STATUSES", block)
        self.assertIn('== "unknown"', block)
        self.assertIn("askyesno", block)


if __name__ == "__main__":
    unittest.main()
