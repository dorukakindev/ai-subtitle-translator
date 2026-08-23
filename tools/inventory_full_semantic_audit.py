from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from subtitle_translator_gui import parse_srt


REQUESTED = [
    "the.rabbit.is.me.(1965).eng.1cd.(9975326)",
    "the.queen.of.spades.(1949).eng.1cd.(9429133)",
    "the.cannibals.(1988).eng.1cd.(7906950)",
    "the.barrier.(1979).pob.1cd.(9187071)",
    "the.ambush.(1969).eng.1cd.(13518581)",
    "silvestre.(1981).eng.1cd.(3134792)",
    "sequences.(1982).eng.1cd.(4458552)",
    "schalcken.the.painter.(1979).eng.1cd.(13719745)",
    "nobody.will.laugh.(1965).eng.1cd.(4191642)",
    "no.or.the.vain.glory.of.command.(1990).fre.1cd.(13137333)",
    "letters.from.marusia.(1975).eng.1cd.(7790341)",
    "let.joy.reign.supreme.(1975).eng.1cd.(9074755)",
    "hadestown.the.musical.(2026).eng.1cd.(13939133)",
    "francisca.(1981).eng.1cd.(8815632)",
    "el.imperio.de.la.fortuna.(1986).eng.1cd.(9257291)",
    "carnival.scenes.(1981).eng.1cd.(13469436)",
    "captain.conan.(1996).eng.1cd.(6272563)",
    "bleach.thousandyear.blood.war.the.calamity.(2026).eng.1cd.(13920991)",
    "angi.vera.(1978).eng.1cd.(8815735)",
    "young.washington.(2026).eng.1cd.(13970566)",
    "wise.blood.(1979).eng.1cd.(3975460)",
    "when.i.am.dead.and.gone.(1967).eng.1cd.(3256249)",
    "the.stunt.man.(1980).eng.1cd.(13885003)",
    "the.secret.nation.(1989).eng.1cd.(7006022)",
]

GENERATED = re.compile(
    r"(?:\.ham|\.bak|upload-ready|partial|superseded|raw|yedek|backup)", re.I
)


def subtitle_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".srt", ".ass", ".vtt"}:
            continue
        if any(part.casefold() in {"raporlar", "kurtarma"} for part in path.parts):
            continue
        if GENERATED.search(path.name):
            continue
        files.append(path)
    return sorted(files, key=lambda p: (len(p.parts), str(p).casefold()))


def main() -> int:
    ready_root = Path(r"G:\HAZIR FİLMLER\YÜKLENECEK")
    source_root = Path(r"G:\FİLMLER")
    rows = []
    for name in REQUESTED:
        ready_dir = ready_root / name
        source_dir = source_root / name
        finals = subtitle_files(ready_dir) if ready_dir.is_dir() else []
        sources = subtitle_files(source_dir) if source_dir.is_dir() else []
        rows.append({
            "name": name,
            "finals": [str(p) for p in finals],
            "sources": [str(p) for p in sources],
            "marker": (ready_dir / "YÜKLEMEYE HAZIR.txt").is_file(),
        })
    json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


def inspect_known() -> int:
    ready_root = Path(r"G:\HAZIR FİLMLER\YÜKLENECEK")
    ids = {
        "captain.conan.(1996).eng.1cd.(6272563)": [583, 970, 1014, 1365, 1454, 1455, 1757],
        "francisca.(1981).eng.1cd.(8815632)": [81, 82, 194, 261, 262, 267, 268, 269, 270, 271, 276, 769, 881, 1068, 1069, 1093, 1308, 1309, 1310, 1311, 1312, 1313, 1436, 1440, 1441, 1442, 1521, 1558, 1562, 1609, 1610, 1622],
        "carnival.scenes.(1981).eng.1cd.(13469436)": [341, 380, 381, 398, 480, 653, 657, 708, 801, 802, 846, 853, 857, 858, 861],
        "el.imperio.de.la.fortuna.(1986).eng.1cd.(9257291)": [16, 19, 20, 30, 144, 311, 349, 441, 463, 567, 998],
    }
    for name, wanted in ids.items():
        finals = subtitle_files(ready_root / name)
        print("\n", name)
        if len(finals) != 1:
            print("final_count", len(finals))
            continue
        final_blocks = parse_srt(str(finals[0]))
        final_by_ts = {str(x[1]): x[2] for x in final_blocks}
        ham_files = sorted((ready_root / name).rglob("*.ham.srt"))
        raw_by_id = {}
        if ham_files:
            raw_by_id = {int(x[0]): x for x in parse_srt(str(ham_files[0])) if str(x[0]).isdigit()}
        for cue_id in wanted:
            raw = raw_by_id.get(cue_id)
            if raw:
                print(cue_id, repr(raw[2]), "=>", repr(final_by_ts.get(str(raw[1]))))
            else:
                print(cue_id, "NO_RAW")
    return 0


def validate_recovered() -> int:
    ready_root = Path(r"G:\HAZIR FİLMLER\YÜKLENECEK")
    recovered = Path(__file__).resolve().parents[1] / ".audit_sources"
    mapping = {
        "schalcken": "schalcken.the.painter.(1979).eng.1cd.(13719745)",
        "wise_blood": "wise.blood.(1979).eng.1cd.(3975460)",
        "captain_conan": "captain.conan.(1996).eng.1cd.(6272563)",
        "stunt_man": "the.stunt.man.(1980).eng.1cd.(13885003)",
        "francisca": "francisca.(1981).eng.1cd.(8815632)",
        "angi_vera": "angi.vera.(1978).eng.1cd.(8815735)",
        "el_imperio": "el.imperio.de.la.fortuna.(1986).eng.1cd.(9257291)",
    }
    signature = "discord: ceviri2"
    for slug, name in mapping.items():
        source = parse_srt(str(recovered / f"{slug}.srt"))
        finals = subtitle_files(ready_root / name)
        output = parse_srt(str(finals[0])) if len(finals) == 1 else []
        src_ts = {str(row[1]) for row in source}
        out_ts = {str(row[1]) for row in output if str(row[2]).strip().casefold() != signature}
        common = src_ts & out_ts
        print(slug, "source", len(src_ts), "output", len(out_ts), "common", len(common),
              "src%", round(100 * len(common) / max(1, len(src_ts)), 2),
              "out%", round(100 * len(common) / max(1, len(out_ts)), 2),
              "first", source[0][1] if source else None,
              output[1][1] if len(output) > 1 else None)
    return 0


def scan_finals() -> int:
    ready_root = Path(r"G:\HAZIR FİLMLER\YÜKLENECEK")
    patterns = {
        "error_marker": re.compile(r"\[(?:HATA|ÇEVİRİ EKSİK)\]", re.I),
        "soft_hyphen": re.compile("\u00ad"),
        "replacement_char": re.compile("\ufffd"),
        "ass_command": re.compile(r"\{\\(?:pos|frz|an|fad|fs|move|org)\b", re.I),
        "circumflex": re.compile(r"[âîûÂÎÛ]"),
    }
    for name in REQUESTED:
        finals = subtitle_files(ready_root / name)
        if len(finals) != 1:
            print(name, "FINAL_COUNT", len(finals))
            continue
        text = finals[0].read_text(encoding="utf-8-sig", errors="replace")
        hits = {key: len(rx.findall(text)) for key, rx in patterns.items()}
        sigs = len(re.findall(r"(?im)^discord:\s*ceviri2\s*$", text))
        print(name, json.dumps(hits, ensure_ascii=False), "signatures", sigs)
    return 0


if __name__ == "__main__":
    if "--inspect-known" in sys.argv:
        raise SystemExit(inspect_known())
    if "--validate-recovered" in sys.argv:
        raise SystemExit(validate_recovered())
    if "--scan-finals" in sys.argv:
        raise SystemExit(scan_finals())
    raise SystemExit(main())
