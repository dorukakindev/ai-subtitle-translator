"""Kalite regresyon corpus runner (bkz. plans/regression-corpus-brief.md,
plans/quality-round2-fixes-brief.md Görev C).

tests/regression_corpus/cases.jsonl'deki gerçek (source, buggy, corrected) üçlülerini
mevcut deterministik katmanlardan geçirir: `find_garble_tokens`, `has_non_turkish_target_leak`,
`validate_polish_candidate` (corrected'ten buggy'e GERİ dönüşü reddeder mi?).

Baseline **id-bazlı**dır (`file:cue`), kategori-toplamı DEĞİL — böylece "A vakası artık
kaçıyor ama B yeni yakalandı, toplam aynı" takası gizlenmez. `clean_corrected_ids` TÜM
vakaların (sov_falsepos dahil) doğru metninin hiçbir guard'ı tetiklemediğini izler; bu
küme daralırsa (önceden temiz sayılan bir corrected artık flagleniyor) o da regresyondur.

`baseline.json` YOKSA test FAIL olur (mesajda oluşturma komutu) — yanlışlıkla silinirse
bozuk bir durumun sessizce yeni baseline olmasını önlemek için. Oluşturma/güncelleme
YALNIZ `REGEN_CORPUS_BASELINE=1` ortam değişkeniyle, bilinçli biçimde yapılır.
"""
import json
import os
import unittest
from collections import defaultdict
from pathlib import Path

import hybrid_translate as ht

CORPUS_DIR = Path(__file__).resolve().parent / "regression_corpus"
CASES_PATH = CORPUS_DIR / "cases.jsonl"
BASELINE_PATH = CORPUS_DIR / "baseline.json"


def _load_cases():
    if not CASES_PATH.exists():
        return []
    cases = []
    with open(CASES_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def _case_id(case):
    return f"{case['file']}:{case['cue']}"


def _is_caught(case):
    """Mevcut deterministik katmanlardan HERHANGİ biri 'buggy' metnini yakalıyor mu?"""
    buggy = case["buggy"]
    corrected = case["corrected"]
    source = case.get("source", "")
    if ht.find_garble_tokens(buggy):
        return True
    if ht.has_non_turkish_target_leak(buggy):
        return True
    # corrected'i mevcut/doğru kabul edip buggy'i ona geri-dönüş adayı olarak sun —
    # safety-net (final_consistency_sweep / Polish ile aynı fonksiyon) bunu reddediyor mu?
    ok, _reason = ht.validate_polish_candidate(corrected, buggy, source_text=source)
    if not ok:
        return True
    return False


def _is_clean(text):
    """Metin hiçbir guard'ı tetiklemiyor mu? (corrected metinler için — TÜM kategoriler)."""
    if ht.find_garble_tokens(text):
        return False
    if ht.has_non_turkish_target_leak(text):
        return False
    return True


class RegressionCorpusTest(unittest.TestCase):
    def test_corpus_report_and_baseline(self):
        cases = _load_cases()
        if not cases:
            self.skipTest(
                "regresyon corpus henüz üretilmedi — "
                "regression corpus fixtures are missing")

        by_cat_total = defaultdict(int)
        by_cat_caught = defaultdict(int)
        caught_ids = set()
        clean_corrected_ids = set()
        for case in cases:
            cid = _case_id(case)
            cat = case["category"]
            by_cat_total[cat] += 1
            if cat != "sov_falsepos" and _is_caught(case):
                caught_ids.add(cid)
                by_cat_caught[cat] += 1
            elif cat == "sov_falsepos" and _is_clean(case["corrected"]):
                by_cat_caught[cat] += 1
            if _is_clean(case["corrected"]):
                clean_corrected_ids.add(cid)

        print("\n=== Regresyon Corpus Raporu (yakalanan/toplam, insan-okunur özet) ===")
        for cat in sorted(by_cat_total):
            note = "  (sov_falsepos: yanlış-pozitif OLMAYAN sayısı)" if cat == "sov_falsepos" else ""
            print(f"  {cat:20s} {by_cat_caught[cat]:3d} / {by_cat_total[cat]:3d}{note}")

        if os.environ.get("REGEN_CORPUS_BASELINE") == "1":
            baseline_v2 = {
                "caught_case_ids": sorted(caught_ids),
                "clean_corrected_ids": sorted(clean_corrected_ids),
            }
            BASELINE_PATH.write_text(
                json.dumps(baseline_v2, indent=2, ensure_ascii=False, sort_keys=True),
                encoding="utf-8")
            print(f"\n(REGEN_CORPUS_BASELINE=1 — baseline.json yeniden yazıldı: {BASELINE_PATH})")
            return

        if not BASELINE_PATH.exists():
            self.fail(
                "tests/regression_corpus/baseline.json yok. Bilinçli oluşturmak için:\n"
                "  REGEN_CORPUS_BASELINE=1 python -m unittest tests.test_regression_corpus")

        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        baseline_caught = set(baseline.get("caught_case_ids", []))
        baseline_clean = set(baseline.get("clean_corrected_ids", []))

        newly_missed = sorted(baseline_caught - caught_ids)
        newly_dirty = sorted(baseline_clean - clean_corrected_ids)

        if newly_missed or newly_dirty:
            msg_parts = []
            if newly_missed:
                msg_parts.append(
                    "Önceden yakalanan ama artık YAKALANMAYAN vakalar:\n    " +
                    "\n    ".join(newly_missed))
            if newly_dirty:
                msg_parts.append(
                    "Önceden temiz kabul edilen ama artık FLAGLENEN corrected metinler:\n    " +
                    "\n    ".join(newly_dirty))
            self.fail(
                "Regresyon corpus'unda GERİLEME tespit edildi (bir kod değişikliği önceki "
                "koruma seviyesini düşürdü):\n  " + "\n  ".join(msg_parts))

        new_catches = sorted(caught_ids - baseline_caught)
        new_clean = sorted(clean_corrected_ids - baseline_clean)
        if new_catches or new_clean:
            print("\n(İyileşme tespit edildi — baseline'ı bilinçli güncellemek için "
                  "REGEN_CORPUS_BASELINE=1 ile çalıştırın.)")
            if new_catches:
                print(f"  yeni yakalanan: {new_catches}")
            if new_clean:
                print(f"  yeni temizlenen: {new_clean}")


if __name__ == "__main__":
    unittest.main()
