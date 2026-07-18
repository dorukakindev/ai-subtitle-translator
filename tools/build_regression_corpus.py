# -*- coding: utf-8 -*-
"""Kalite regresyon corpus'u üretici (bkz. plans/regression-corpus-brief.md).

Read-only: bu oturumda düzeltilen dosyaların .bak (bozuk, gpt-5.4-mini çıktısı,
guard'lardan geçmiş) ve final (elle doğrulanmış) sürümlerini karşılaştırır,
her değişen cue için (source, buggy, corrected, category) üçlüsünü
tests/regression_corpus/cases.jsonl'e yazar.

Kategoriler elle küratörlüktür — bu script'i yazan oturumda her dosya derinlemesine
analiz edilip plans/*-fixes-brief.md dosyalarında belgelendi; kategoriler o analize
dayanır (icat edilmiş otomatik sınıflandırma değildir).

Çalıştır: python tools/build_regression_corpus.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import subtitle_translator_gui as gui  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "tests" / "regression_corpus" / "cases.jsonl"


def _load(path):
    """{cue_id: text} — path yoksa boş dict (dosya taşınmış/silinmiş olabilir)."""
    p = Path(path)
    if not p.exists():
        return {}
    return {str(i): t for i, ts, t in gui.parse_subtitle(str(p))}


# ── Manifest: (label, source_path, bak_path, final_path, [(cue_id, category, note), ...]) ──
# cue_id'ler bu oturumda uygulanan plans/*-fixes-brief.md dosyalarındaki tam listeyle eşleşir.

JOHNDEE_SRC = r"E:\ALTYAZILAR\Altyazilar\Hulu-Altyazilar\john-dee-renaissance-alchemist-jason-louv.vtt"
JOHNDEE_BAK = r"C:\Users\K\Downloads\ÇIKTI\john-dee-renaissance-alchemist-jason-louv.srt.bak"
JOHNDEE_FINAL = r"C:\Users\K\Downloads\ÇIKTI\john-dee-renaissance-alchemist-jason-louv.srt"

SATAN_SRC = r"E:\ALTYAZILAR\Altyazilar\Hulu-Altyazilar\Satan - Prince Of Darkness.en.srt"
SATAN_BAK = r"C:\Users\K\Downloads\ÇIKTI\Satan - Prince Of Darkness.en.srt.bak"
SATAN_FINAL = r"C:\Users\K\Downloads\ÇIKTI\Satan - Prince Of Darkness.en.srt"

SUMER_SRC = (r"E:\ALTYAZILAR\Altyazilar\HBO-Max\Unearthed\Season 8\Sumerian Pyramid of Death"
             r"\Unearthed_S08E09_Sumerian Pyramid of Death.English(US).srt")
SUMER_BAK = (r"C:\Users\K\Downloads\ÇIKTI\Unearthed_S08E09_Sumerian Pyramid of Death.English(US).srt.bak")
SUMER_FINAL = (r"C:\Users\K\Downloads\ÇIKTI\Unearthed_S08E09_Sumerian Pyramid of Death.English(US).srt")

SOLVE_SRC = (r"C:\Users\K\Desktop\Altyazılar\Solve Et Coagula - The Great Work of Alchemy"
             r"\Solve Et Coagula - The Great Work of Alchemy (HD).en.srt")
SOLVE_BAK = (r"C:\Users\K\Desktop\Altyazılar\Solve Et Coagula - The Great Work of Alchemy\ÇIKTI"
             r"\Solve Et Coagula - The Great Work of Alchemy (HD).en.srt.bak")
SOLVE_FINAL = (r"C:\Users\K\Desktop\Altyazılar\Solve Et Coagula - The Great Work of Alchemy\ÇIKTI"
               r"\Solve Et Coagula - The Great Work of Alchemy (HD).en.srt")

MANIFEST = [
    ("john_dee", JOHNDEE_SRC, JOHNDEE_BAK, JOHNDEE_FINAL, [
        ("71", "english_leak", "untranslated 'church' left in"),
        ("73", "english_leak", "untranslated \"he's a fascinating person\" left in"),
        ("982", "desync", "content shifted -1 starting here (Kelley content bled from #982->wrong cue)"),
        ("990", "desync", "adjacent_duplicate: 'Dee ve benzerleri icin de belirmeye basladi' repeated in #991"),
        ("991", "desync", "adjacent_duplicate: same phrase as #990, chunk-boundary-spanning dup Fix C missed"),
        ("1064", "desync", "byte-level '?' corruption + content shift (Turkish diacritics replaced with ASCII '?')"),
        ("1070", "desync", "adjacent_duplicate: '>>LOUV: Dogru' repeated pattern"),
        ("1082", "desync", "byte-level '?' corruption + content shift"),
        ("1083", "desync", "adjacent_duplicate: 'melek alemleri' repeated"),
        ("1132", "polish_garble", "stray bare 'a' left between words (R1_stray_letter pattern)"),
        ("427", "english_leak", "untranslated 'church' left in (missed by first pass, found by broad leak scan)"),
        ("430", "english_leak", "untranslated 'church' left in"),
        ("590", "english_leak", "untranslated 'church' left in"),
        ("594", "english_leak", "untranslated 'church' left in"),
    ]),
    ("satan_prince", SATAN_SRC, SATAN_BAK, SATAN_FINAL, [
        ("327", "truncation", "JSON-repair fragment truncated to just 'Halk a'"),
        ("24", "mixed_term", "'Satan' left untranslated instead of 'Seytan' (file mixed Seytan x72/Satan x39)"),
        ("75", "mixed_term", "'Satan' left untranslated"),
        ("82", "mixed_term", "'Satan' left untranslated"),
        ("213", "mixed_term", "'Satan' left untranslated"),
        ("130", "term_inconsistency", "'Jesus' left untranslated instead of 'Isa' (16 occurrences)"),
        ("148", "term_inconsistency", "'Jesus' left untranslated instead of 'Isa'"),
        ("167", "term_inconsistency", "'Jesus' with curly apostrophe left untranslated"),
        ("307", "english_leak", "'Science cagi' left untranslated instead of 'Bilim cagi'"),
        ("32", "term_inconsistency", "'Michael' left untranslated instead of 'Mikail'"),
        ("33", "term_inconsistency", "'Michael' left untranslated instead of 'Mikail'"),
    ]),
    ("sumerian_pyramid", SUMER_SRC, SUMER_BAK, SUMER_FINAL, [
        ("603", "desync", "content shifted -1 starting here"),
        ("604", "desync", "content shifted -1"),
        ("605", "desync", "content shifted -1"),
        ("606", "desync", "adjacent_duplicate + wrong imperative mood ('koyun' instead of 'koydular')"),
        ("439", "english_leak", "sentence trails off, content moved to #440"),
        ("440", "english_leak", "'Garden of Eden' left completely untranslated"),
        ("480", "english_leak", "'King Shulgi' — 'King' left untranslated (file uses 'Kral' elsewhere)"),
        ("562", "term_inconsistency", "'Eden Bahcesi' instead of dominant 'Cennet Bahcesi' (7 other occurrences)"),
        ("392", "desync", "'benzedigine dair' stutter/repetition across #392-393"),
        ("481", "polish_garble", "typo 'parcalayip' (Latin i) instead of 'parcalayip' (Turkish i-with-dot)"),
    ]),
    ("solve_et_coagula", SOLVE_SRC, SOLVE_BAK, SOLVE_FINAL, [
        ("442", "polish_garble", "Polish Pass introduced stray bare 'g' before 'gectiginde'"),
        ("192", "polish_garble", "Polish Pass corrupted 'verebildiginizdir' into garbled 'dali tutabildiginizdir'"),
        ("163", "polish_garble", "Polish Pass corrupted 'Buyuk Is' into garbled 'Ulu isi'"),
        ("4", "element_leak", "'Earth' and 'fire' left untranslated instead of 'Topragi'/'atesten'"),
        ("74", "element_leak", "fire/water/air/Earth left untranslated (classical 4 elements passage)"),
        ("77", "element_leak", "'Fire' left untranslated instead of 'Ates'"),
        ("78", "element_leak", "'Water' left untranslated instead of 'Su'"),
        ("80", "element_leak", "'Air'/'Earth' left untranslated instead of 'Hava'/'toprak'"),
        ("45", "term_inconsistency", "'Mercury' left untranslated instead of dominant 'Merkur'"),
        ("91", "term_inconsistency", "'ether' left untranslated instead of dominant 'eter'"),
        ("92", "term_inconsistency", "'quintessence' left untranslated instead of 'besinci oz'"),
        ("201", "truncation", "dangling fragment 'Bunun' — rest of sentence missing (0.12x length ratio)"),
        ("120", "english_leak", "'coutop' (source's own corrupted term) left untranslated"),
    ]),
]

# ── sov_falsepos: doğrulanmış YANLIŞ-POZİTİF adayları — "corrected" hiçbir guard'ı
# tetiklememeli. Bu oturumda "DOKUNMA" olarak belgelenen, gerçek-dosyada doğrulanmış cue'lar.
SOV_FALSEPOS = [
    ("sumerian_pyramid", SUMER_FINAL, "563", "SOV word-order puts verb 'lives on' at sentence end — looks "
     "disconnected in isolation but is correct in context (#560-563 one sentence)"),
    ("sumerian_pyramid", SUMER_FINAL, "391", "short outlier length cue (city states.) is benign SOV "
     "redistribution, not truncation"),
    ("solve_et_coagula", SOLVE_FINAL, "301", "Turkish word 'sol' (left) — not the Latin alchemical 'Sol' (sun)"),
    ("solve_et_coagula", SOLVE_FINAL, "327", "Turkish word 'sol' (left hand) — not Latin 'Sol'"),
    ("solve_et_coagula", SOLVE_FINAL, "44", "'Luna' is a deliberately-kept Latin alchemical term"),
    ("solve_et_coagula", SOLVE_FINAL, "121", "'albedo'/'nigrado' are legitimate alchemy stage names"),
    # Not: John Dee #1452 (benign cue drop, kaynak #1451'e birleşmiş) bu formata uymuyor —
    # "corrected" metni yok, doğru davranış cue'nun YOKLUĞU. Bu corpus'a dahil edilemez.
]


def main():
    cases = []
    for label, src_path, bak_path, final_path, cue_specs in MANIFEST:
        src_map = _load(src_path)
        bak_map = _load(bak_path)
        final_map = _load(final_path)
        if not bak_map or not final_map:
            print(f"[atla] {label}: .bak veya final dosyası bulunamadı, atlanıyor.")
            continue
        for cue_id, category, note in cue_specs:
            buggy = bak_map.get(cue_id)
            corrected = final_map.get(cue_id)
            source = src_map.get(cue_id, "")
            if buggy is None or corrected is None:
                print(f"[uyarı] {label}#{cue_id}: .bak veya final'de cue bulunamadı, atlanıyor.")
                continue
            if buggy == corrected:
                print(f"[uyarı] {label}#{cue_id}: .bak ve final AYNI (beklenmiyordu), atlanıyor.")
                continue
            cases.append({
                "file": label, "cue": cue_id, "source": source,
                "buggy": buggy, "corrected": corrected,
                "category": category, "note": note,
            })

    for label, final_path, cue_id, note in SOV_FALSEPOS:
        final_map = _load(final_path)
        corrected = final_map.get(cue_id)
        if corrected is None:
            print(f"[uyarı] sov_falsepos {label}#{cue_id}: final'de cue bulunamadı, atlanıyor.")
            continue
        cases.append({
            "file": label, "cue": cue_id, "source": "",
            "buggy": corrected, "corrected": corrected,
            "category": "sov_falsepos", "note": note,
        })

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")

    by_cat = {}
    for c in cases:
        by_cat[c["category"]] = by_cat.get(c["category"], 0) + 1
    print(f"\n{len(cases)} vaka yazıldı -> {OUT_PATH}")
    for cat, n in sorted(by_cat.items()):
        print(f"  {cat}: {n}")


if __name__ == "__main__":
    main()
