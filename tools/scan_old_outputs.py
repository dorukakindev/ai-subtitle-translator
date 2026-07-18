#!/usr/bin/env python3
"""Batch quality scan for previously delivered subtitle translations.

Read-only scanner. It parses delivered SRT/VTT outputs, finds matching sources
under E:\\ALTYAZILAR by basename, runs deterministic quality detectors, and
writes a detailed report to tools/old_outputs_report.txt.
"""

from __future__ import annotations

import io
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

# Windows console: keep Turkish paths/text readable.
if os.name == "nt" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import hybrid_translate as ht  # noqa: E402
from subtitle_translator_gui import (  # noqa: E402
    detect_alignment_issues,
    detect_mixed_term_renderings,
    parse_subtitle,
)

OUTPUT_DIRS = [
    Path(r"C:\Users\K\Downloads\ÇIKTI"),
    REPO_ROOT / "translated",
]
SOURCE_ROOT = Path(r"E:\ALTYAZILAR")
PREFERRED_SOURCE_PART = str(Path("Altyazilar") / "Hulu-Altyazilar").lower()
REPORT_PATH = REPO_ROOT / "tools" / "old_outputs_report.txt"
SUBTITLE_EXTS = {".srt", ".vtt"}
SAMPLE_LEN = 60


@dataclass
class FileScanResult:
    output_path: Path
    source_path: Path | None = None
    output_count: int = 0
    source_count: int = 0
    notes: list[str] = field(default_factory=list)
    alignment: list[dict] = field(default_factory=list)
    garble: list[dict] = field(default_factory=list)
    mixed_terms: list[dict] = field(default_factory=list)

    @property
    def total_findings(self) -> int:
        alignment_score = 0
        for item in self.alignment:
            ids = item.get("ids")
            alignment_score += len(ids) if isinstance(ids, list) else 1
        return alignment_score + len(self.garble) + len(self.mixed_terms)


def _safe_rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except Exception:
        return str(path)


def _norm_stem(path: Path) -> str:
    return path.stem.casefold()


def _is_output_candidate(path: Path) -> bool:
    name = path.name.casefold()
    if path.suffix.casefold() not in SUBTITLE_EXTS:
        return False
    if name.endswith(".ham.srt"):
        return False
    if ".bak" in name:
        return False
    return True


def _iter_output_files() -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for base in OUTPUT_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or not _is_output_candidate(path):
                continue
            key = str(path.resolve()).casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(path)
    return sorted(out, key=lambda p: str(p).casefold())


def _source_score(path: Path, output_ext: str) -> tuple[int, int, int, str]:
    lower = str(path).casefold()
    preferred = 0 if PREFERRED_SOURCE_PART in lower else 1
    same_ext = 0 if path.suffix.casefold() == output_ext.casefold() else 1
    # Prefer VTT over SRT when extension tie is not helpful: delivered files often
    # are SRT converted from VTT sources.
    vtt_first = 0 if path.suffix.casefold() == ".vtt" else 1
    return (preferred, same_ext, vtt_first, lower)


def _build_source_index(root: Path) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    if not root.exists():
        return index
    for dirpath, _dirnames, filenames in os.walk(root):
        base = Path(dirpath)
        for filename in filenames:
            path = base / filename
            if path.suffix.casefold() not in SUBTITLE_EXTS:
                continue
            index.setdefault(_norm_stem(path), []).append(path)
    return index


def _find_source(output_path: Path, source_index: dict[str, list[Path]]) -> Path | None:
    candidates = source_index.get(_norm_stem(output_path), [])
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: _source_score(p, output_path.suffix))[0]


def _parse(path: Path) -> list:
    return list(parse_subtitle(str(path)))


def _src_map(blocks: Sequence) -> dict[str, str]:
    return {str(idx): str(text or "") for idx, _ts, text in blocks}


def _block_map(blocks: Sequence) -> dict[str, str]:
    return {str(idx): str(text or "") for idx, _ts, text in blocks}


def _sample(text: str, limit: int = SAMPLE_LEN) -> str:
    clean = re.sub(r"\s+", " ", str(text or "").replace("\n", " / ")).strip()
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)].rstrip() + "…"


def _ids_from_alignment(item: dict) -> list[str]:
    if isinstance(item.get("ids"), list):
        return [str(x) for x in item["ids"]]
    if "idx" in item:
        return [str(item["idx"])]
    return []


def _scan_garble(blocks: Sequence) -> list[dict]:
    findings: list[dict] = []
    for idx, _ts, text in blocks:
        tokens = ht.find_garble_tokens(text)
        if tokens:
            findings.append({
                "idx": str(idx),
                "tokens": tokens,
                "text": str(text or ""),
            })
    return findings


def _source_term_occurrences(term: str, src_map: dict[str, str]) -> list[str]:
    if not term:
        return []
    pat = re.compile(r"(?<!\w)" + re.escape(str(term)) + r"(?!\w)", re.I)
    ids = [idx for idx, text in src_map.items() if pat.search(text or "")]
    return sorted(ids, key=_sort_key)


def _sort_key(value: str) -> tuple[int, int | str]:
    try:
        return (0, int(value))
    except Exception:
        return (1, str(value))


def _scan_file(output_path: Path, source_index: dict[str, list[Path]]) -> FileScanResult:
    result = FileScanResult(output_path=output_path)
    source_path = _find_source(output_path, source_index)
    if source_path is None:
        result.notes.append("source not found by identical basename under E:\\ALTYAZILAR")
        try:
            result.output_count = len(_parse(output_path))
        except Exception as exc:
            result.notes.append(f"output parse failed: {exc}")
        return result

    result.source_path = source_path
    try:
        out_blocks = _parse(output_path)
        src_blocks = _parse(source_path)
    except Exception as exc:
        result.notes.append(f"parse failed: {exc}")
        return result

    result.output_count = len(out_blocks)
    result.source_count = len(src_blocks)
    src = _src_map(src_blocks)
    out = _block_map(out_blocks)

    try:
        result.alignment = list(detect_alignment_issues(out_blocks, src))
    except Exception as exc:
        result.notes.append(f"detect_alignment_issues failed: {exc}")

    try:
        result.garble = _scan_garble(out_blocks)
    except Exception as exc:
        result.notes.append(f"find_garble_tokens failed: {exc}")

    try:
        mixed = list(detect_mixed_term_renderings(out_blocks, src))
        for item in mixed:
            ids = _source_term_occurrences(str(item.get("term", "")), src)
            result.mixed_terms.append({
                "term": item.get("term", ""),
                "renderings": item.get("renderings", {}),
                "ids": ids,
                "samples": {idx: out.get(idx, "") for idx in ids[:8]},
            })
    except Exception as exc:
        result.notes.append(f"detect_mixed_term_renderings failed: {exc}")

    return result


def _format_alignment(item: dict, out_map: dict[str, str], src_map: dict[str, str]) -> list[str]:
    lines = []
    ids = _ids_from_alignment(item)
    id_part = ", ".join(ids) if ids else "?"
    lines.append(f"  - {item.get('type', 'alignment')} ids=[{id_part}] detail={item.get('detail', '')}")
    for idx in ids[:12]:
        lines.append(f"      #{idx} SRC: {_sample(src_map.get(idx, ''))}")
        lines.append(f"      #{idx} TR : {_sample(out_map.get(idx, ''))}")
    return lines


def _write_report(results: Sequence[FileScanResult]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("OLD OUTPUTS QUALITY SCAN")
    lines.append(f"Repo: {REPO_ROOT}")
    lines.append(f"Output dirs: {', '.join(str(p) for p in OUTPUT_DIRS)}")
    lines.append(f"Source root: {SOURCE_ROOT}")
    lines.append("")

    for res in results:
        lines.append("=" * 88)
        lines.append(f"FILE: {_safe_rel(res.output_path)}")
        lines.append(f"SOURCE: {res.source_path if res.source_path else 'NOT FOUND'}")
        lines.append(f"CUES: output={res.output_count} source={res.source_count}")
        lines.append(f"TOTAL_FINDINGS: {res.total_findings}")
        if res.notes:
            lines.append("NOTES:")
            for note in res.notes:
                lines.append(f"  - {note}")
        if not res.source_path:
            lines.append("")
            continue

        out_blocks = _parse(res.output_path)
        src_blocks = _parse(res.source_path)
        out_map = _block_map(out_blocks)
        src = _src_map(src_blocks)

        lines.append("ALIGNMENT FINDINGS:")
        if not res.alignment:
            lines.append("  - none")
        for item in res.alignment:
            lines.extend(_format_alignment(item, out_map, src))

        lines.append("GARBLE TOKEN FINDINGS:")
        if not res.garble:
            lines.append("  - none")
        for item in res.garble:
            tok = ", ".join(f"{t}:{rule}" for t, rule in item.get("tokens", []))
            idx = str(item.get("idx", "?"))
            lines.append(f"  - #{idx} tokens=[{tok}] sample={_sample(item.get('text', ''))}")

        lines.append("MIXED TERM FINDINGS:")
        if not res.mixed_terms:
            lines.append("  - none")
        for item in res.mixed_terms:
            ids = [str(x) for x in item.get("ids", [])]
            lines.append(
                f"  - term={item.get('term')} ids=[{', '.join(ids[:20])}] "
                f"renderings={item.get('renderings')}"
            )
            samples = item.get("samples", {}) or {}
            for idx in ids[:8]:
                lines.append(f"      #{idx} TR: {_sample(samples.get(idx, ''))}")
        lines.append("")

    lines.append("=" * 88)
    lines.append("RANKED SUMMARY")
    ranked = sorted(results, key=lambda r: (-r.total_findings, str(r.output_path).casefold()))
    for rank, res in enumerate(ranked, 1):
        lines.append(
            f"{rank:3}. findings={res.total_findings:4} "
            f"alignment={sum((len(x.get('ids', [])) if isinstance(x.get('ids'), list) else 1) for x in res.alignment):3} "
            f"garble={len(res.garble):3} mixed={len(res.mixed_terms):3} "
            f"file={res.output_path}"
        )

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def main() -> int:
    print("Indexing sources...")
    source_index = _build_source_index(SOURCE_ROOT)
    print(f"Source basenames indexed: {len(source_index)}")

    outputs = _iter_output_files()
    print(f"Output files to scan: {len(outputs)}")

    results: list[FileScanResult] = []
    for n, output_path in enumerate(outputs, 1):
        print(f"[{n}/{len(outputs)}] {output_path.name}")
        try:
            results.append(_scan_file(output_path, source_index))
        except Exception as exc:  # keep end-to-end scan alive
            results.append(FileScanResult(output_path=output_path, notes=[f"unhandled scan error: {exc}"]))

    _write_report(results)
    total_findings = sum(r.total_findings for r in results)
    no_source = sum(1 for r in results if r.source_path is None)
    print("Scan complete.")
    print(f"Files scanned: {len(results)}")
    print(f"Files without source: {no_source}")
    print(f"Total findings: {total_findings}")
    print(f"Report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

