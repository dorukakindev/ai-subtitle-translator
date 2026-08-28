# -*- coding: utf-8 -*-
"""Prompt ile payload arasındaki sözleşme.

CLAUDE.md bunu açık bir değişmez olarak yazıyor — "payload'a anahtar
eklersen iki sistem promptunu da güncelle" — ama bugüne kadar kilitleyen
hiçbir test yoktu. Bozulduğunda hiçbir test patlamaz, hiçbir log uyarmaz:
model ya anlatılmamış bir alan alır, ya da göremediği bir alanın anlatımı.

Ölçüldüğünde tek gerçek boşluk `frag_group` idi: gerçek arşivde 60 dosyada
25.005 cue'da gönderiliyordu ve iki promptun hiçbirinde geçmiyordu.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

import hybrid_translate as ht
import subtitle_translator_gui as gui

LINES = [
    "You can only leave this island,",
    "as the strongest one",
    "alive.",
    "Okay.",
    "The supplies of food were stored",
    "in the event of war.",
]


class Ctx:
    characters = ()
    recurring_terms = {}
    tone = ""
    summary = ""
    setting = ""
    scene_notes = ""


class Cue:
    __slots__ = ("index", "start", "end", "text")

    def __init__(self, index, start, end, text):
        self.index = index
        self.start = start
        self.end = end
        self.text = text


def _sync_request():
    fd, path = tempfile.mkstemp(suffix=".srt")
    os.close(fd)
    Path(path).write_text(
        "".join("%d\n00:00:%02d,000 --> 00:00:%02d,500\n%s\n\n"
                % (i, i, i, text) for i, text in enumerate(LINES, 1)),
        encoding="utf-8")
    try:
        reqs, _ = gui.build_requests(
            [path], "English", "Turkish", "gpt-5.4-mini")
    finally:
        os.unlink(path)
    body = reqs[0]["body"]
    return (body["messages"][0]["content"],
            json.loads(body["messages"][1]["content"]))


def _hybrid_request():
    cues = [Cue(i, "00:00:%02d,000" % i, "00:00:%02d,500" % i, text)
            for i, text in enumerate(LINES, 1)]
    base = ht.build_system_prompt(Ctx(), "English", "Turkish", None)
    reqs, _ = ht.build_batch_requests(cues, base, "gpt-5.4-mini")
    body = reqs[0]["body"]
    return (body["messages"][0]["content"],
            json.loads(body["messages"][1]["content"]))


def _payload_keys(payload):
    keys = set(payload)
    for item in payload.get("tr", []):
        if isinstance(item, dict):
            keys.update(item)
    return keys


def _documented(system_message, key):
    return ('"%s"' % key) in system_message or ("'%s'" % key) in system_message


class PromptPayloadContractTest(unittest.TestCase):
    def test_sync_documents_every_key_it_sends(self):
        system_message, payload = _sync_request()
        undocumented = sorted(
            key for key in _payload_keys(payload)
            if not _documented(system_message, key))
        self.assertEqual(undocumented, [])

    def test_hybrid_documents_every_key_it_sends(self):
        system_message, payload = _hybrid_request()
        undocumented = sorted(
            key for key in _payload_keys(payload)
            if not _documented(system_message, key))
        self.assertEqual(undocumented, [])

    def test_both_flows_send_the_same_keys(self):
        _sync_sys, sync_payload = _sync_request()
        _hyb_sys, hyb_payload = _hybrid_request()
        self.assertEqual(_payload_keys(sync_payload),
                         _payload_keys(hyb_payload))

    def test_both_flows_document_the_same_keys(self):
        # Ölçülen anahtarların TAMAMI, koşullu gönderilenler dahil.
        keys = ["tr", "ctx", "next_ctx", "prev_scene", "prev_tr", "scene",
                "sentence_groups", "glossary", "repair_neighbors",
                "i", "t", "d", "frag", "frag_group", "is_ost"]
        sync_sys, _p = _sync_request()
        hyb_sys, _q = _hybrid_request()
        sync_doc = {k for k in keys if _documented(sync_sys, k)}
        hyb_doc = {k for k in keys if _documented(hyb_sys, k)}
        self.assertEqual(sync_doc, hyb_doc)

    def test_frag_group_is_explained(self):
        for system_message, _payload in (_sync_request(), _hybrid_request()):
            self.assertIn("frag_group", system_message)
            self.assertIn("sentence_groups", system_message)


# Payload ANAHTARLARI yukarida kilitli; bu blok KURALLARIN kendisini kilitler.
# CLAUDE.md iki promptun "semantik olarak hizali" kalmasini istiyor ama bunu
# zorlayan bir sey yoktu: biri kural eklerken digerini unutursa sessizce
# ayrisirlar ve iki akis ayni dosyayi farkli cevirmeye baslar.
#
# TUZAK: karsilastirma GERCEK istegin messages[0]'i uzerinden yapilir.
# `build_system_prompt` ciktisina tek basina bakmak yanlis sonuc verir -
# bicim/payload blogu `build_batch_requests` icinde ekleniyor. Olculdugunde
# izole karsilastirma 8 kurali "eksik" gosteriyordu; gercek istekte 0.
SHARED_PROMPT_RULES = {
    "ID bütünlüğü": ("ID INTEGRITY",),
    "diyalog tiresi": ("DIALOGUE DASHES", "TWO different speakers"),
    "fragment kuralları": ("FRAGMENT RULES", "frag_group"),
    "ekran yazısı": ("is_ost",),
    "güvenilmez referans": ("untrusted reference",),
    "süre anahtarı": ("'d' key", "display duration"),
    "önceki sahne": ("prev_scene",),
    "zincirleme bağlam": ("prev_tr",),
    "cümle grupları": ("sentence_groups",),
    "somut çeviri örnekleri": ("DETONATÖR",),
    "şarkı sözü": ("LYRICS",),
    "sözlük": ("glossary",),
}


class SharedPromptRuleParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sync_system, _ = _sync_request()
        cls.hybrid_system, _ = _hybrid_request()

    def test_every_shared_rule_is_in_both_prompts(self):
        for label, needles in SHARED_PROMPT_RULES.items():
            with self.subTest(rule=label):
                in_sync = any(n in self.sync_system for n in needles)
                in_hybrid = any(n in self.hybrid_system for n in needles)
                self.assertTrue(
                    in_sync, "%s sync promptunda yok" % label)
                self.assertTrue(
                    in_hybrid, "%s hybrid promptunda yok" % label)

    def test_prompts_stay_comparable_in_size(self):
        """Biri digerinin yarisina duserse bir blok dusmus demektir."""
        smaller = min(len(self.sync_system), len(self.hybrid_system))
        larger = max(len(self.sync_system), len(self.hybrid_system))
        self.assertGreater(
            smaller / larger, 0.75,
            "promptlar arasinda buyuk boyut farki: %d vs %d"
            % (len(self.sync_system), len(self.hybrid_system)))


if __name__ == "__main__":
    unittest.main()
