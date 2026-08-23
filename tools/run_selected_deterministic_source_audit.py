from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import hybrid_translate as ht
from subtitle_translator_gui import _DELIVERY_SIGNATURE_RE, parse_subtitle

from inventory_full_semantic_audit import REQUESTED, subtitle_files


READY_ROOT = Path(r"G:\HAZIR FİLMLER\YÜKLENECEK")
SOURCE_ROOT = Path(r"G:\FİLMLER")


RECOVERED = {
    "schalcken.the.painter.(1979).eng.1cd.(13719745)": Path(".audit_sources/schalcken.srt"),
    "wise.blood.(1979).eng.1cd.(3975460)": Path(".audit_sources/wise_blood.srt"),
    "captain.conan.(1996).eng.1cd.(6272563)": Path(".audit_sources/captain_conan.srt"),
    "the.stunt.man.(1980).eng.1cd.(13885003)": Path(".audit_sources/stunt_man.srt"),
    "francisca.(1981).eng.1cd.(8815632)": Path(".audit_sources/francisca.srt"),
    "angi.vera.(1978).eng.1cd.(8815735)": Path(".audit_sources/angi_vera.srt"),
    "el.imperio.de.la.fortuna.(1986).eng.1cd.(9257291)": Path(".audit_sources/el_imperio.srt"),
    "the.secret.nation.(1989).eng.1cd.(7006022)": Path(".audit_sources/secret_nation.srt"),
}


@dataclass
class Cue:
    index: str
    timestamp: str
    text: str


def source_for(name: str) -> Path | None:
    originals = [p for p in (SOURCE_ROOT / name).rglob("*.srt") if p.is_file()]
    if originals:
        return originals[0]
    candidate = RECOVERED.get(name)
    return candidate if candidate and candidate.exists() else None


def dialogue(rows):
    return [row for row in rows if not _DELIVERY_SIGNATURE_RE.fullmatch(str(row[2] or "").strip())]


def align(source_rows, output_rows):
    src_by_ts = {str(ts): str(text) for _idx, ts, text in source_rows}
    timestamp_hits = sum(str(ts) in src_by_ts for _idx, ts, _text in output_rows)
    if output_rows and timestamp_hits / len(output_rows) >= 0.8:
        return [Cue(str(idx), str(ts), src_by_ts.get(str(ts), "")) for idx, ts, _text in output_rows]
    if len(source_rows) == len(output_rows):
        return [Cue(str(out[0]), str(out[1]), str(src[2])) for src, out in zip(source_rows, output_rows)]
    return []


def main() -> None:
    if "--tm-coverage" in sys.argv or "--tm-ham-coverage" in sys.argv:
        connection = sqlite3.connect("translation_memory.db")
        try:
            source_sets = {}
            for source, target in connection.execute("select source, target from tm"):
                source_sets.setdefault(str(target), set()).add(str(source))
            for name in REQUESTED:
                if source_for(name) is not None:
                    continue
                finals = subtitle_files(READY_ROOT / name)
                if not finals:
                    continue
                selected = finals[0]
                if "--tm-ham-coverage" in sys.argv:
                    ham_files = list((READY_ROOT / name).rglob("*.ham.srt"))
                    if ham_files:
                        selected = ham_files[0]
                rows = dialogue(list(parse_subtitle(str(selected))))
                unique = ambiguous = 0
                for _idx, _ts, target in rows:
                    hits = source_sets.get(str(target), ())
                    if len(hits) == 1:
                        unique += 1
                    elif len(hits) > 1:
                        ambiguous += 1
                print(name, "cues", len(rows), "unique_tm", unique, "ambiguous", ambiguous)
        finally:
            connection.close()
        return
    results = []
    for name in REQUESTED:
        finals = subtitle_files(READY_ROOT / name)
        source = source_for(name)
        if not finals or not source:
            results.append({"name": name, "status": "missing_source_or_final"})
            continue
        final = finals[0]
        source_rows = list(parse_subtitle(str(source)))
        output_rows = dialogue(list(parse_subtitle(str(final))))
        cues = align(source_rows, output_rows)
        if not cues:
            results.append({
                "name": name,
                "status": "unaligned",
                "source_count": len(source_rows),
                "output_count": len(output_rows),
            })
            continue
        blocks = [(str(idx), str(ts), str(text)) for idx, ts, text in output_rows]
        suspicious = ht.run_validators(blocks, cues=cues)
        results.append({
            "name": name,
            "status": "scanned",
            "source": str(source),
            "final": str(final),
            "cue_count": len(blocks),
            "suspicious_count": len(suspicious),
            "suspicious": [
                {"id": str(idx), "timestamp": str(ts), "target": str(text), "reasons": str(reason)}
                for idx, ts, text, reason in suspicious
            ],
        })
    if "--summary" in sys.argv:
        summary = [
            {
                "name": row["name"],
                "status": row["status"],
                "cue_count": row.get("cue_count"),
                "suspicious_count": row.get("suspicious_count"),
                "source_count": row.get("source_count"),
                "output_count": row.get("output_count"),
            }
            for row in results
        ]
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
