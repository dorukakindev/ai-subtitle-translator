"""
Sözlük/deyim eşleştirme kalitesi:
- term_in_text: kelime-sınırı duyarlı (substring false-positive YOK), İngilizce
  çoğul/iyelik toleransı VAR, çok kelimeli/noktalamalı anahtarda substring fallback.
- run_validators: sözlük kaçağında GLOSS_MISS:src=>tr (orijinal yazım) üretir,
  böylece critic fixer zorunlu karşılığı enjekte edebilir.
"""
import json
import unittest
from types import SimpleNamespace

import hybrid_translate as ht


class TermInTextTest(unittest.TestCase):
    def test_single_word_exact(self):
        self.assertTrue(ht.term_in_text("detonator", "we found a detonator here"))

    def test_plural_and_possessive_match(self):
        self.assertTrue(ht.term_in_text("detonator", "two detonators exploded"))
        self.assertTrue(ht.term_in_text("cylon", "the cylon's plan"))

    def test_no_substring_false_positive(self):
        # 'art' eski substring eşleşmesinde 'start'/'artist' içinde tetikleniyordu
        self.assertFalse(ht.term_in_text("art", "let's start now"))
        self.assertFalse(ht.term_in_text("art", "she is an artist"))
        self.assertFalse(ht.term_in_text("win", "open the window"))

    def test_multiword_substring_fallback(self):
        self.assertTrue(ht.term_in_text("new york", "welcome to new york city"))
        self.assertFalse(ht.term_in_text("new york", "old yorkshire"))
        self.assertFalse(ht.term_in_text("new york", "a new yorker wrote"))
        self.assertFalse(ht.term_in_text("the who", "the whole room"))

    def test_punctuated_key_substring(self):
        self.assertTrue(ht.term_in_text("rock'n'roll", "i love rock'n'roll music"))

    def test_empty_inputs(self):
        self.assertFalse(ht.term_in_text("", "anything"))
        self.assertFalse(ht.term_in_text("term", ""))

    def test_mixed_case_key_normalized(self):
        # text_lower zaten küçük harf (çağıran bir kez yapar); anahtar mixed-case olabilir
        self.assertTrue(ht.term_in_text("Warpdrive", "engage the warpdrive"))


class GlossMissReasonTest(unittest.TestCase):
    def _cue(self, idx, text):
        return SimpleNamespace(index=idx, text=text)

    def test_emits_pair_on_miss(self):
        gloss = {"warpdrive": "solucan motoru"}
        cues = [self._cue(1, "Engage the warpdrive now")]
        tr = [(1, "00:00:01,000 --> 00:00:02,000", "Motoru çalıştır")]  # karşılık YOK
        out = ht.run_validators(tr, cues, gloss)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][3], "GLOSS_MISS:warpdrive=>solucan motoru")

    def test_no_miss_when_term_present(self):
        gloss = {"warpdrive": "solucan motoru"}
        cues = [self._cue(1, "Engage the warpdrive now")]
        tr = [(1, "00:00:01,000 --> 00:00:02,000", "Solucan motoru çalıştır")]  # karşılık VAR
        out = ht.run_validators(tr, cues, gloss)
        self.assertEqual(out, [])

    def test_short_boundary_matched_term_is_checked(self):
        gloss = {"cat": "kedi"}
        cues = [self._cue(1, "the cat sleeps")]
        tr = [(1, "00:00:01,000 --> 00:00:02,000", "uyuyor")]
        out = ht.run_validators(tr, cues, gloss)
        self.assertEqual(out[0][3], "GLOSS_MISS:cat=>kedi")

    def test_all_caps_title_term_does_not_override_lowercase_dialogue(self):
        gloss = {"AGITATORS": "AJİTATÖRLER"}
        cues = [self._cue(1, "We send our agitators there.")]
        tr = [(1, "00:00:01,000 --> 00:00:02,000", "Ajitatörlerimizi oraya gönderiyoruz.")]
        self.assertEqual(ht.run_validators(tr, cues, gloss), [])
        self.assertFalse(ht._locked_source_term_present(
            "AGITATORS", "We send our agitators there."))
        self.assertTrue(ht._locked_source_term_present("AGITATORS", "AGITATORS"))

    def test_auto_glossary_drops_polysemous_take_but_keeps_phrase_lock(self):
        logs = []
        gloss = ht.sanitize_glossary_for_turkish(
            {"take": "tekrar", "Take one": "Birinci çekim", "King": "Kral"},
            target_language="tr",
            log_fn=lambda message, *_: logs.append(message),
        )
        self.assertNotIn("take", gloss)
        self.assertEqual(gloss["Take one"], "Birinci çekim")
        self.assertEqual(gloss["King"], "Kral")
        self.assertTrue(any("take->tekrar" in message for message in logs))

    def test_polysemous_take_does_not_force_tekrar_in_critic_validator(self):
        gloss = ht.sanitize_glossary_for_turkish(
            {"take": "tekrar"}, target_language="tr")
        cases = (
            ("Take a good look at this one.", "Şuna iyi bak."),
            ("I can't take it out. It's fake, it's a prop.", "Sahte, dekor."),
            ("Let De Filippis take care of that.", "Onu De Filippis düşünsün."),
            ("Where did I take the photos?", "Fotoğrafları nerede çektim?"),
            ("Take off your glasses.", "Gözlüklerini çıkar."),
            ("Don't take it personally.", "Bunu üstüne alınma."),
            ("I'll take care of horses.", "Atlarla ben ilgilenirim."),
            ("They'll take you to the station.", "Seni istasyona götürecekler."),
            ("They don't take you seriously.", "Seni ciddiye almıyorlar."),
            ("Take it easy.", "Sakin ol."),
            ("Take the first train home.", "İlk trenle eve git."),
        )
        for idx, (source, translation) in enumerate(cases, 1):
            with self.subTest(source=source):
                cues = [self._cue(idx, source)]
                translated = [(idx, "00:00:01,000 --> 00:00:02,000", translation)]
                hits = ht.run_validators(translated, cues, gloss)
                self.assertFalse(any("GLOSS_MISS:take=>tekrar" in hit[3] for hit in hits))

    def test_specific_take_phrase_remains_enforceable(self):
        gloss = ht.sanitize_glossary_for_turkish(
            {"Take one": "Birinci çekim"}, target_language="tr")
        cues = [self._cue(1, "Take one.")]
        translated = [(1, "00:00:01,000 --> 00:00:02,000", "Hazır.")]
        hits = ht.run_validators(translated, cues, gloss)
        self.assertTrue(any(
            "GLOSS_MISS:Take one=>Birinci çekim" in hit[3] for hit in hits))


class SchemaGlossaryInjectionTest(unittest.TestCase):
    """Şema gömülü sözlüğü (Warhammer) build_requests'e enjekte oluyor mu +
    build_requests'in ht.term_in_text yolu çökmüyor mu (modül-seviyesi fn, local import)."""
    import tempfile as _tf

    def _srt(self, text):
        import os
        d = self._tf.mkdtemp()
        fp = os.path.join(d, "t.srt")
        with open(fp, "w", encoding="utf-8") as f:
            f.write(f"1\n00:00:01,000 --> 00:00:03,000\n{text}\n")
        return fp

    def _payload(self, fp, **kw):
        import subtitle_translator_gui as gui
        reqs, _ = gui.build_requests([fp], "English", "Turkish", "gpt-5.4-mini", **kw)
        return json.loads(reqs[0]["body"]["messages"][1]["content"])

    def test_warhammer_glossary_injected(self):
        import subtitle_translator_gui as gui
        sch = gui.CONTENT_SCHEMAS["warhammer40k"]
        self.assertIn("glossary", sch)
        pl = self._payload(self._srt("The High Marshall of the Black Templars"), schema=sch)
        gl = pl.get("glossary", {})
        self.assertEqual(gl.get("Black Templars"), "Black Templars")   # Qora kilitlenir
        self.assertEqual(gl.get("High Marshall"), "Yüksek Mareşal")    # Yuqori kilitlenir

    def test_user_glossary_overrides_schema(self):
        import subtitle_translator_gui as gui
        sch = gui.CONTENT_SCHEMAS["warhammer40k"]
        pl = self._payload(self._srt("The Black Templars charge"),
                           schema=sch, glossary={"Black Templars": "Kara Tapınakçılar"})
        self.assertEqual(pl["glossary"].get("Black Templars"), "Kara Tapınakçılar")

    def test_glossary_path_no_crash(self):
        # Regression: build_requests modül-seviyesi fonksiyon; ht local-import edilmeli,
        # yoksa eşleşen terimli sözlükte NameError('ht') atardı.
        pl = self._payload(self._srt("Hello world"), glossary={"world": "dünya"})
        self.assertEqual(pl["glossary"].get("world"), "dünya")


    def test_each_file_uses_its_own_glossary(self):
        import subtitle_translator_gui as gui
        fp_a = self._srt("Alpha term")
        fp_b = self._srt("Beta term")
        reqs, _ = gui.build_requests(
            [fp_a, fp_b], "English", "Turkish", "gpt-5.4-mini",
            file_glossaries={
                fp_a: {"Alpha": "Alfa"},
                fp_b: {"Beta": "BetaTR"},
            })
        payloads = {}
        for req in reqs:
            payload = json.loads(req["body"]["messages"][1]["content"])
            payloads[payload["tr"][0]["t"]] = payload
        self.assertEqual(payloads["Alpha term"]["glossary"], {"Alpha": "Alfa"})
        self.assertEqual(payloads["Beta term"]["glossary"], {"Beta": "BetaTR"})


if __name__ == "__main__":
    unittest.main()
