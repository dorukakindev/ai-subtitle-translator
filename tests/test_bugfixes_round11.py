"""
Round 11 bug-fix regresyon testleri:
- _clear_batch_recovery: fmap dosyalarını siler, batch_id.txt'den id'leri çıkarır
- analyze_with_minimax except'inde 'i' bağlı (futures[fut] deseni)
- scene-emotion start/end string→int güvenli karşılaştırma
"""
import unittest

from app_state import state_dir


class ClearBatchRecoveryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import subtitle_translator_gui as gui
        from tests._gui_app import make_app
        cls.gui = gui
        cls.app = make_app(gui)  # açılıştaki yarım-batch penceresi kapalı (bkz. _gui_app)
        cls.app.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def test_removes_fmap_and_prunes_batch_id_txt(self):
        base = state_dir(self.gui.__file__)
        bidp = base / "batch_id.txt"
        # Kullanıcının GERÇEK bekleyen batch_id.txt'si varsa test onu ezmesin/silmesin.
        _saved = bidp.read_text(encoding="utf-8") if bidp.exists() else None
        # Geçici batch_id.txt + fmap dosyaları oluştur
        created = []
        try:
            bidp.write_text("batch_AAA\nbatch_BBB\nbatch_KEEP\n", encoding="utf-8")
            for b in ("batch_AAA", "batch_BBB", "batch_KEEP"):
                f = base / f"batch_fmap_{b}.json"
                f.write_text("{}", encoding="utf-8"); created.append(f)

            self.app._clear_batch_recovery(["batch_AAA", "batch_BBB"])

            # AAA/BBB fmap silindi, KEEP kaldı
            self.assertFalse((base / "batch_fmap_batch_AAA.json").exists())
            self.assertFalse((base / "batch_fmap_batch_BBB.json").exists())
            self.assertTrue((base / "batch_fmap_batch_KEEP.json").exists())
            # batch_id.txt yalnızca KEEP içermeli
            self.assertEqual(bidp.read_text(encoding="utf-8").strip(), "batch_KEEP")
        finally:
            for f in created:
                f.unlink(missing_ok=True)
            if _saved is not None:
                bidp.write_text(_saved, encoding="utf-8")
            else:
                bidp.unlink(missing_ok=True)

    def test_deletes_batch_id_txt_when_all_cleared(self):
        base = state_dir(self.gui.__file__)
        bidp = base / "batch_id.txt"
        _saved = bidp.read_text(encoding="utf-8") if bidp.exists() else None
        try:
            bidp.write_text("batch_X\nbatch_Y\n", encoding="utf-8")
            self.app._clear_batch_recovery(["batch_X", "batch_Y"])
            self.assertFalse(bidp.exists())  # boşaldı → silindi
        finally:
            if _saved is not None:
                bidp.write_text(_saved, encoding="utf-8")
            else:
                bidp.unlink(missing_ok=True)

    def test_empty_input_noop(self):
        self.app._clear_batch_recovery([])
        self.app._clear_batch_recovery(None)  # patlamamalı


class SceneEmotionIntCoercionTest(unittest.TestCase):
    def test_string_start_end_does_not_crash(self):
        # build_batch_requests'in emotion eşleştirme mantığını izole test et:
        # string start/end ('5') int chunk index ile kıyaslanınca patlamamalı
        import hybrid_translate as ht

        class Cue:
            def __init__(self, index):
                self.index = index
                self.text = f"Line {index}."
                self.start = "00:00:01,000"; self.end = "00:00:02,000"
        cues = [Cue(i) for i in range(1, 6)]
        # Eski (legacy) tek-satır 'arc' şekli — _scene_plan_payload_entry bunu
        # 'summary' yoksa 'tone' alanına düşürür (bkz. plans, sahne planı özelliği).
        scene_emotions = [{"start": "1", "end": "3", "arc": "tension rising"}]
        # Patlamadan istek üretmeli
        reqs, fmap = ht.build_batch_requests(cues, "SYS", "gpt-4.1-mini",
                                             chunk_size=3, scene_emotions=scene_emotions)
        self.assertTrue(len(reqs) >= 1)
        # En az bir chunk'ta sahne planı enjekte edilmiş olmalı (1-3 örtüşmesi)
        import json
        payloads = [json.loads(r["body"]["messages"][1]["content"]) for r in reqs]
        self.assertTrue(any(
            any(entry.get("tone") == "tension rising" for entry in p.get("scene", []))
            for p in payloads
        ))


if __name__ == "__main__":
    unittest.main()
