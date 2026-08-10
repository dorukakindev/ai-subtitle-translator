import copy
import json
import unittest

import subtitle_translator_gui as gui


class SyncStageRequestHashTests(unittest.TestCase):
    @staticmethod
    def _request(payload):
        return {
            "custom_id": "chunk_0",
            "body": {
                "model": "gpt-5.4",
                "messages": [
                    {"role": "system", "content": "Kurallara uy."},
                    {"role": "user", "content": json.dumps(payload)},
                ],
            },
        }

    def test_derived_chain_context_does_not_invalidate_its_stage(self):
        request = self._request({
            "tr": [{"i": "1", "t": "Hello."}],
            "ctx": [{"i": "0", "t": "Earlier."}],
            "next_ctx": [{"i": "2", "t": "Later."}],
            "glossary": {"Hello": "Merhaba"},
        })
        saved = copy.deepcopy(request)
        payload = json.loads(saved["body"]["messages"][1]["content"])
        payload["prev_tr"] = [{"i": "0", "t": "Daha önce."}]
        saved["body"]["messages"][1]["content"] = json.dumps(payload)

        self.assertEqual(
            gui._sync_stage_request_hash([request]),
            gui._sync_stage_request_hash([saved]),
        )

    def test_real_request_context_change_invalidates_stage(self):
        request = self._request({
            "tr": [{"i": "1", "t": "Hello."}],
            "ctx": [{"i": "0", "t": "Earlier."}],
            "glossary": {"Hello": "Merhaba"},
        })
        changed = copy.deepcopy(request)
        payload = json.loads(changed["body"]["messages"][1]["content"])
        payload["glossary"] = {"Hello": "Selam"}
        changed["body"]["messages"][1]["content"] = json.dumps(payload)

        self.assertNotEqual(
            gui._sync_stage_request_hash([request]),
            gui._sync_stage_request_hash([changed]),
        )


if __name__ == "__main__":
    unittest.main()
