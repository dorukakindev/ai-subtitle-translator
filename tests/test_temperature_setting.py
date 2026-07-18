"""'Gelişmiş Ayarlar' panelindeki Temperature slider'ı ('_temperature') daha önce
GERÇEK isteklere hiç bağlı değildi — hem sync (`build_requests`) hem hybrid
(`ht.build_batch_requests`) çağrıları temperature'ı 0.2 sabit kodluyordu, slider'ın
değeri yalnızca ayar dosyasına kaydediliyordu. Artık her iki fonksiyon da bir
`temperature` parametresi alıyor (varsayılan None -> 0.2, eski davranışla birebir
aynı) ve App'teki 6 çağrı noktası `self._temperature`'ı geçiriyor.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

import hybrid_translate as ht
import subtitle_translator_gui as gui


class Cue:
    def __init__(self, index, text):
        self.index = index
        self.text = text
        self.start = "00:00:01,000"
        self.end = "00:00:02,000"


class SyncBuildRequestsTemperatureTest(unittest.TestCase):
    SRT = ("1\n00:00:01,000 --> 00:00:02,000\nHello.\n\n"
           "2\n00:00:02,100 --> 00:00:03,000\nWorld.\n")

    def _write(self):
        fd, fp = tempfile.mkstemp(suffix=".srt")
        os.close(fd)
        Path(fp).write_text(self.SRT, encoding="utf-8")
        return fp

    def test_default_temperature_is_0_2(self):
        fp = self._write()
        try:
            reqs, _ = gui.build_requests([fp], "English", "Turkish", "gpt-4.1-mini")
            self.assertEqual(reqs[0]["body"]["temperature"], 0.2)
        finally:
            os.unlink(fp)

    def test_custom_temperature_is_respected(self):
        fp = self._write()
        try:
            reqs, _ = gui.build_requests([fp], "English", "Turkish", "gpt-4.1-mini",
                                         temperature=0.7)
            self.assertEqual(reqs[0]["body"]["temperature"], 0.7)
        finally:
            os.unlink(fp)

    def test_gpt5_model_still_drops_temperature_regardless_of_slider(self):
        # gpt-5/reasoning modelleri temperature parametresini desteklemiyor —
        # slider'a bakılmaksızın anahtar isteğe hiç eklenmemeli.
        fp = self._write()
        try:
            reqs, _ = gui.build_requests([fp], "English", "Turkish", "gpt-5.4-mini",
                                         temperature=0.9)
            self.assertNotIn("temperature", reqs[0]["body"])
        finally:
            os.unlink(fp)


class HybridBuildBatchRequestsTemperatureTest(unittest.TestCase):
    def _cues(self):
        return [Cue(i, f"Line {i}.") for i in range(1, 4)]

    def test_default_temperature_is_0_2(self):
        reqs, _ = ht.build_batch_requests(self._cues(), "system", "gpt-4.1-mini")
        self.assertEqual(reqs[0]["body"]["temperature"], 0.2)

    def test_custom_temperature_is_respected(self):
        reqs, _ = ht.build_batch_requests(self._cues(), "system", "gpt-4.1-mini",
                                          temperature=0.6)
        self.assertEqual(reqs[0]["body"]["temperature"], 0.6)

    def test_gpt5_model_still_drops_temperature_regardless_of_slider(self):
        reqs, _ = ht.build_batch_requests(self._cues(), "system", "gpt-5.4-mini",
                                          temperature=0.9)
        self.assertNotIn("temperature", reqs[0]["body"])


class AppCallSitesPassTemperatureTest(unittest.TestCase):
    """App'in build_requests/build_batch_requests çağıran metotlarının kaynak
    kodunda temperature=self._temperature geçtiğini doğrular (regresyon kilidi —
    6 çağrı noktasından biri gelecekte eklenip bu argümanı unutursa yakalar)."""

    def test_source_wires_temperature_at_every_call_site(self):
        src = Path("subtitle_translator_gui.py").read_text(encoding="utf-8")
        call_sites = src.count("temperature=self._temperature")
        self.assertGreaterEqual(call_sites, 6, "beklenen 6 çağrı noktasından az")


if __name__ == "__main__":
    unittest.main()
