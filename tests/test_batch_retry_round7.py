import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import hybrid_translate as ht
import provider_retry


class TransientBatchError(RuntimeError):
    status_code = 503
    headers = {"Retry-After": "7"}


class BatchRetryCancellationTest(unittest.TestCase):
    def test_batch_wrapper_retries_transient_retry_after(self):
        error = TransientBatchError("temporary")
        call = mock.Mock(side_effect=[error, "ok"])
        with mock.patch("provider_retry._wait_for_transient_retry", return_value=7), \
                mock.patch("provider_retry.record_provider_failure"):
            result = ht.batch_api_call_with_retry(
                SimpleNamespace(), call, "batch_retrieve")
        self.assertEqual(result, "ok")
        self.assertEqual(call.call_count, 2)

    def test_cancelled_before_request_never_calls_provider(self):
        call = mock.Mock()
        with self.assertRaises(provider_retry.ProviderWaitCancelled):
            provider_retry.provider_call_with_retry(
                call, SimpleNamespace(), "batch-api",
                {"operation": "batch_create"}, cancel_check=lambda: True)
        call.assert_not_called()

    def test_cancelled_retry_does_not_start_next_attempt(self):
        stopped = {"value": False}
        call = mock.Mock(side_effect=TransientBatchError("temporary"))

        def _wait(*_args):
            stopped["value"] = True

        with mock.patch("provider_retry._wait_for_transient_retry", side_effect=_wait), \
                mock.patch("provider_retry.record_provider_failure"):
            with self.assertRaises(provider_retry.ProviderWaitCancelled):
                provider_retry.provider_call_with_retry(
                    call, SimpleNamespace(), "batch-api",
                    {"operation": "batch_create"},
                    cancel_check=lambda: stopped["value"])
        self.assertEqual(call.call_count, 1)


class BatchUploadReplayTest(unittest.TestCase):
    def test_retried_upload_rewinds_stream_and_reuses_idempotency_key(self):
        payloads = []
        upload_headers = []

        def _upload(*, file, purpose, extra_headers):
            payloads.append(file.read())
            upload_headers.append(extra_headers)
            if len(payloads) == 1:
                raise TransientBatchError("temporary")
            return SimpleNamespace(id="file-1")

        client = SimpleNamespace(
            files=SimpleNamespace(create=_upload),
            batches=SimpleNamespace(create=mock.Mock(
                return_value=SimpleNamespace(id="batch-1"))),
        )

        def _retry(_client, call, operation, cancel_check=None):
            if operation == "batch_upload":
                try:
                    call()
                except TransientBatchError:
                    return call()
            return call()

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch("openai.OpenAI", return_value=client), \
                mock.patch.object(ht, "state_dir", return_value=Path(tmp)), \
                mock.patch.object(ht, "_batch_id_path", return_value=Path(tmp) / "batch_id.txt"), \
                mock.patch.object(ht, "batch_api_call_with_retry", side_effect=_retry):
            batch_id = ht.submit_batch("key", [{"custom_id": "c1"}])

        self.assertEqual(batch_id, "batch-1")
        self.assertEqual(payloads[0], payloads[1])
        self.assertTrue(payloads[0])
        self.assertEqual(upload_headers[0], upload_headers[1])
        create_headers = client.batches.create.call_args.kwargs["extra_headers"]
        self.assertNotEqual(
            upload_headers[0]["Idempotency-Key"],
            create_headers["Idempotency-Key"])


if __name__ == "__main__":
    unittest.main()
