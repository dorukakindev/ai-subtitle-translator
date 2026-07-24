"""Resume (kurtarma) yolunun GÖNDERİM ANINDA saklanan bilgileri kullanması.

KÖK SORUN (2026-07-17): resume, kaynak dosyayı ÇIKTI YOLUNDAN GERİYE HESAPLIYORDU
(`rel = out_path.relative_to(output_var); src = input_var / rel`) ve raporu O ANKİ
`output_var`a yazıyordu. İkisi de kırılgan:

1. Çıktı-klasörü kuralları (2026-07-10) araya alt-klasör koydu — Kural 2:
   `<çıktı>/<dosya-adı>/<ad>.srt`, Kural 1: `<girdi>/ÇIKTI/...`. Geriye hesaplama bu
   fazladan segmenti kaynağa da ekleyip dosyayı BULAMAZ oldu → gerçek bir koşuda
   "Resume: kaynak dosya bulunamadı" → etiket geri yükleme, [HATA] işaretleme, TM ve QC
   sessizce ATLANDI. (Bu bir regresyondu; çıktı-klasörü özelliği getirdi.)
2. Ayrıca çıktı DAİMA .srt iken kaynak .vtt/.ass olabilir — geriye hesaplama bu durumda
   zaten en baştan yanlış uzantı üretiyordu.
3. Rapor: program yeniden başlatılınca `output_var` ayarlardaki eski varsayılana
   (`./translated`) dönüyor; resume raporu oraya düşüyordu (gerçek koşuda görüldü),
   çıktı .srt'leri ise saklanan doğru yola gidiyordu.

ÇÖZÜM: `submit_batch` artık `source_path` + `output_dir`'i fmap'e yazıyor; resume
bunları kullanıyor. Eski (source_path'siz) fmap'ler için eski yönteme düşülür.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hybrid_translate as ht
from app_state import STATE_DIR_ENV


class SubmitBatchPersistsRecoveryInfoTest(unittest.TestCase):
    def setUp(self):
        self._state = tempfile.TemporaryDirectory()
        self._env = patch.dict(os.environ, {STATE_DIR_ENV: self._state.name})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._state.cleanup()

    def _fake_client(self):
        from types import SimpleNamespace

        class _Files:
            def create(self, file=None, purpose=None):
                return SimpleNamespace(id="file_x")

        class _Batches:
            def create(self, **kw):
                return SimpleNamespace(id="batch_srcpath_test")

        return SimpleNamespace(files=_Files(), batches=_Batches())

    def test_fmap_stores_source_path_and_output_dir(self):
        fmap_path = ht._batch_fmap_path("batch_srcpath_test")
        bid_path = ht._batch_id_path()
        # Kullanıcının GERÇEK batch_id.txt'si varsa test onu ezmesin/silmesin.
        saved_bid = bid_path.read_text(encoding="utf-8") if bid_path.exists() else None
        try:
            with patch("openai.OpenAI", return_value=self._fake_client()):
                ht.submit_batch("k", [{"a": 1}], None, {"c1": [("f", 1)]},
                                output_path=r"C:\out\ÇIKTI\Film\Film.srt",
                                source_path=r"C:\in\Film.vtt",
                                output_dir=r"C:\out\ÇIKTI",
                                source_language="Spanish")
            data = json.loads(fmap_path.read_text(encoding="utf-8"))
            self.assertEqual(data["source_path"], r"C:\in\Film.vtt")
            self.assertEqual(data["output_dir"], r"C:\out\ÇIKTI")
            self.assertEqual(data["output_path"], r"C:\out\ÇIKTI\Film\Film.srt")
            self.assertEqual(data["source_language"], "Spanish")
            self.assertEqual(data["type"], "hybrid")
        finally:
            fmap_path.unlink(missing_ok=True)
            if saved_bid is not None:
                bid_path.write_text(saved_bid, encoding="utf-8")
            else:
                bid_path.unlink(missing_ok=True)

    def test_missing_optional_args_default_to_empty(self):
        # Geriye uyum: eski çağrı biçimi (source_path/output_dir verilmeden) patlamamalı
        fmap_path = ht._batch_fmap_path("batch_srcpath_test")
        bid_path = ht._batch_id_path()
        saved_bid = bid_path.read_text(encoding="utf-8") if bid_path.exists() else None
        try:
            with patch("openai.OpenAI", return_value=self._fake_client()):
                ht.submit_batch("k", [{"a": 1}], None, {"c1": [("f", 1)]},
                                output_path=r"C:\out\Film.srt")
            data = json.loads(fmap_path.read_text(encoding="utf-8"))
            self.assertEqual(data["source_path"], "")
            self.assertEqual(data["output_dir"], "")
            self.assertEqual(data["source_language"], "")
        finally:
            fmap_path.unlink(missing_ok=True)
            if saved_bid is not None:
                bid_path.write_text(saved_bid, encoding="utf-8")
            else:
                bid_path.unlink(missing_ok=True)


class ResumeSourceResolutionTest(unittest.TestCase):
    """_wait_batch_hybrid'in kaynak çözümleme mantığı (saklanan yol > geriye hesaplama).

    Not: tüm _wait_batch_hybrid'i koşturmak ağ/OpenAI gerektirir; burada asıl regresyonun
    yaşandığı KARAR mantığı, gerçek dosya sistemi üzerinde birebir aynı sırayla test edilir.
    """

    def _resolve(self, source_path, output_path, input_dir, output_dir):
        """_wait_batch_hybrid içindeki _orig_cues bloğunun kaynak-seçme mantığı."""
        _src_path = None
        try:
            if source_path and Path(source_path).exists():
                _src_path = Path(source_path)
            else:
                _out_p = Path(output_path)
                _rel = _out_p.relative_to(output_dir) if output_dir else _out_p.name
                _cand = Path(input_dir) / _rel
                if _cand.exists():
                    _src_path = _cand
        except Exception:
            pass
        return _src_path

    def test_stored_source_path_wins_over_broken_derivation(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            src = base / "in" / "Film.vtt"      # kaynak .vtt, DÜZ (alt-klasörsüz)
            src.parent.mkdir(parents=True)
            src.write_text("x", encoding="utf-8")
            # Kural 2 çıktısı: <çıktı>/<ad>/<ad>.srt — geriye hesaplama bunu bulamaz
            out = base / "out" / "Film" / "Film.srt"
            resolved = self._resolve(str(src), str(out), str(base / "in"), str(base / "out"))
            self.assertEqual(resolved, src)

    def test_derivation_alone_fails_under_rule2(self):
        # REGRESYONUN KANITI: saklanan kaynak yolu YOKKEN (eski fmap) Kural 2 çıktısından
        # geriye hesaplama kaynağı bulamaz → _orig_cues None → TM/QC/etiket atlanır.
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            src = base / "in" / "Film.srt"
            src.parent.mkdir(parents=True)
            src.write_text("x", encoding="utf-8")
            out = base / "out" / "Film" / "Film.srt"   # Kural 2: fazladan 'Film' segmenti
            resolved = self._resolve("", str(out), str(base / "in"), str(base / "out"))
            self.assertIsNone(resolved, "geriye hesaplama Kural 2'de bulamamalı (regresyon kanıtı)")

    def test_derivation_still_works_for_old_flat_layout(self):
        # Geriye uyum: ESKİ fmap + ESKİ düz yerleşim (<çıktı>/<ad>.srt) hâlâ çalışmalı
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            src = base / "in" / "Film.srt"
            src.parent.mkdir(parents=True)
            src.write_text("x", encoding="utf-8")
            out = base / "out" / "Film.srt"
            resolved = self._resolve("", str(out), str(base / "in"), str(base / "out"))
            self.assertEqual(resolved, src)

    def test_stale_stored_path_falls_back_to_derivation(self):
        # Saklanan yol artık yoksa (dosya taşınmış) eski yönteme düşülmeli
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            src = base / "in" / "Film.srt"
            src.parent.mkdir(parents=True)
            src.write_text("x", encoding="utf-8")
            out = base / "out" / "Film.srt"
            resolved = self._resolve(str(base / "yok" / "Film.srt"), str(out),
                                     str(base / "in"), str(base / "out"))
            self.assertEqual(resolved, src)


if __name__ == "__main__":
    unittest.main()
