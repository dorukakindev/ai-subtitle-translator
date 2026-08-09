import unittest
from types import SimpleNamespace

import hybrid_translate as ht


class _UsageCallback:
    def __init__(self):
        self.calls = []
        self.missing_calls = 0

    def __call__(self, total, cached=0, **kwargs):
        self.calls.append((total, cached, kwargs))

    def report_missing_usage(self):
        self.missing_calls += 1


class HelperUsageMissingReportTest(unittest.TestCase):
    def test_absent_usage_is_reported_without_fake_zero_usage(self):
        callback = _UsageCallback()

        ht._report_helper_usage(SimpleNamespace(), callback)

        self.assertEqual(callback.missing_calls, 1)
        self.assertEqual(callback.calls, [])

    def test_explicitly_unavailable_usage_is_reported(self):
        callback = _UsageCallback()
        response = SimpleNamespace(
            usage=SimpleNamespace(total_tokens=80), usage_available=False)

        ht._report_helper_usage(response, callback)

        self.assertEqual(callback.missing_calls, 1)
        self.assertEqual(callback.calls, [])

    def test_real_zero_usage_remains_normal_usage_report(self):
        callback = _UsageCallback()
        response = SimpleNamespace(
            usage=SimpleNamespace(total_tokens=0, prompt_tokens=0, completion_tokens=0),
            usage_available=True,
        )

        ht._report_helper_usage(response, callback)

        self.assertEqual(callback.missing_calls, 0)
        self.assertEqual(callback.calls, [(0, 0, {})])


if __name__ == "__main__":
    unittest.main()
