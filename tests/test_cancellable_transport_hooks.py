"""Taşıma kapatma hook'u ile bounded provider iptali regresyonları."""
import threading
import time
import unittest

from request_cancellation import (
    CancellableCallHandle,
    RequestCancelled,
    RunRequestCanceller,
    run_cancellable_call,
)


class CancellableTransportHookTest(unittest.TestCase):
    def test_cancel_invokes_transport_close_once_and_waits_for_worker_exit(self):
        canceller = RunRequestCanceller()
        started = threading.Event()
        released = threading.Event()
        completed = threading.Event()
        calls = []
        errors = []

        def call():
            started.set()
            released.wait(2)
            completed.set()
            return "late result"

        def close_transport():
            calls.append("close")
            released.set()

        def worker():
            try:
                run_cancellable_call(
                    call, canceller, poll_interval=0.01,
                    transport_close=close_transport, cancel_cleanup_seconds=0.5)
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=worker)
        thread.start()
        self.assertTrue(started.wait(1))
        self.assertEqual(canceller.cancel(), 1)
        thread.join(1)

        self.assertFalse(thread.is_alive())
        self.assertTrue(completed.is_set())
        self.assertEqual(calls, ["close"])
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RequestCancelled)

    def test_no_cancel_does_not_close_transport(self):
        calls = []
        result = run_cancellable_call(
            lambda: "ok", RunRequestCanceller(), transport_close=lambda: calls.append("close"))
        self.assertEqual(result, "ok")
        self.assertEqual(calls, [])

    def test_hook_registered_after_close_runs_immediately(self):
        handle = CancellableCallHandle(threading.Event())
        handle.close()
        calls = []
        self.assertTrue(handle.add_close_hook(lambda: calls.append("close")))
        self.assertEqual(calls, ["close"])

    def test_bad_hook_never_masks_cancellation(self):
        canceller = RunRequestCanceller()
        started = threading.Event()
        release = threading.Event()
        errors = []

        def call():
            started.set()
            release.wait(1)

        def worker():
            try:
                run_cancellable_call(
                    call, canceller, poll_interval=0.01,
                    transport_close=lambda: (_ for _ in ()).throw(RuntimeError("close")),
                    cancel_cleanup_seconds=0)
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=worker)
        thread.start()
        self.assertTrue(started.wait(1))
        canceller.cancel()
        thread.join(1)
        release.set()
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RequestCancelled)

    def test_cleanup_wait_is_bounded_without_transport_hook(self):
        canceller = RunRequestCanceller()
        started = threading.Event()
        release = threading.Event()
        errors = []

        def call():
            started.set()
            release.wait(2)

        def worker():
            try:
                run_cancellable_call(
                    call, canceller, poll_interval=0.01, cancel_cleanup_seconds=0.02)
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=worker)
        thread.start()
        self.assertTrue(started.wait(1))
        begin = time.monotonic()
        canceller.cancel()
        thread.join(0.5)
        elapsed = time.monotonic() - begin
        release.set()

        self.assertFalse(thread.is_alive())
        self.assertLess(elapsed, 0.3)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RequestCancelled)


if __name__ == "__main__":
    unittest.main()
