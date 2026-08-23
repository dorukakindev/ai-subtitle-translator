from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import hybrid_translate as ht
import subtitle_translator_gui as gui


ROOT_NAMES = ("HAZIR DİZİLER", "HAZIR FİLMLER")
SPEAKER_RE = re.compile(
    r"^\s*(?:<[^>]+>|\{[^}]*\})*\s*-?\s*"
    r"([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ0-9 _.-]{1,30}):"
)


def _blocks(cues) -> list:
    out = []
    for cue in cues or []:
        if hasattr(cue, "index") and not callable(getattr(cue, "index")):
            out.append((str(cue.index), f"{cue.start} --> {cue.end}", str(cue.text or "")))
        else:
            out.append((str(cue[0]), str(cue[1]), str(cue[2] or "")))
    return out


def _plain(blocks: list) -> list:
    return [
        row for row in blocks
        if not gui._DELIVERY_SIGNATURE_RE.fullmatch(str(row[2] or "").strip())
    ]


def _pairs(repo: Path) -> list[tuple[Path, Path, Path]]:
    pairs = []
    for root_name in ROOT_NAMES:
        root = repo / root_name
        if not root.is_dir():
            continue
        for source in root.rglob("*.srt"):
            if (source.parent.name.casefold() != "kaynak"
                    or source.parent.parent.name.casefold() != "raporlar"):
                continue
            delivery = source.parents[2] / source.name
            ham_dir = source.parents[1] / "Ham"
            hams = sorted(
                ham_dir.glob("*.ham.srt"),
                key=lambda path: (path.stat().st_mtime_ns, path.name),
            )
            if delivery.is_file() and hams:
                pairs.append((source, delivery, hams[-1]))
    return sorted(pairs, key=lambda item: str(item[0]).casefold())


def _allowed_source_pairs(source_blocks: list) -> set:
    _ids, groups = gui._fragment_groups_gui(source_blocks)
    bounds = {
        str(idx): gui._srt_timestamp_bounds(ts)
        for idx, ts, _text in source_blocks
    }
    return {
        (bounds[str(left)], bounds[str(right)])
        for group in groups
        for left, right in zip(group.get("items", []), group.get("items", [])[1:])
        if str(left) in bounds and str(right) in bounds
    }


def _span_members(before: list, after: list) -> list[tuple[tuple, list]]:
    timed = []
    for row in before:
        try:
            timed.append((row, gui._srt_timestamp_bounds(row[1])))
        except ValueError:
            pass
    timed.sort(key=lambda item: (item[1][0], item[1][1]))
    starts = [bounds[0] for _row, bounds in timed]
    groups = []
    for row in after:
        try:
            start, end = gui._srt_timestamp_bounds(row[1])
        except ValueError:
            continue
        members = []
        cursor = bisect.bisect_left(starts, start)
        while cursor < len(timed) and timed[cursor][1][0] <= end:
            item, (item_start, item_end) = timed[cursor]
            if item_start >= start and item_end <= end:
                members.append(item)
            cursor += 1
        if len(members) > 1:
            groups.append((row, members))
    return groups


def _source_map_by_span(blocks: list, source_blocks: list) -> dict:
    timed = []
    for _idx, ts, text in source_blocks:
        try:
            timed.append((*gui._srt_timestamp_bounds(ts), str(text or "")))
        except ValueError:
            pass
    timed.sort(key=lambda item: (item[0], item[1]))
    starts = [item[0] for item in timed]
    by_start = {}
    by_end = {}
    for start, end, text in timed:
        by_start.setdefault(start, []).append(text)
        by_end.setdefault(end, []).append(text)
    result = {}
    for idx, ts, _text in blocks:
        try:
            start, end = gui._srt_timestamp_bounds(ts)
        except ValueError:
            continue
        matched = []
        cursor = bisect.bisect_left(starts, start)
        while cursor < len(timed) and timed[cursor][0] <= end:
            src_start, src_end, src_text = timed[cursor]
            if src_start >= start and src_end <= end:
                matched.append(src_text)
            cursor += 1
        if not matched:
            matched = by_start.get(start, []) or by_end.get(end, [])
        if matched:
            result[str(idx)] = "\n".join(matched)
    return result


def _speaker_marker(text: str) -> str:
    value = str(text or "")
    match = SPEAKER_RE.match(value)
    if match:
        return match.group(1).strip()
    first = re.sub(r"^\s*(?:<[^>]+>|\{[^}]*\})+", "", value).lstrip()
    return "-" if first.startswith(("-", "–", "—")) else ""


def _line_metrics(blocks: list) -> Counter:
    result = Counter()
    for _idx, _ts, text in blocks:
        lines = str(text or "").splitlines() or [""]
        result["cues"] += 1
        result["over_2_lines"] += len(lines) > 2
        result["over_42_lines"] += sum(gui._visible_len(line) > 42 for line in lines)
        result["one_char_lines"] += sum(gui._visible_len(line) == 1 for line in lines)
        result["tagged_over_42"] += (
            any(mark in str(text or "") for mark in ("<", "{"))
            and any(gui._visible_len(line) > 42 for line in lines)
        )
        result["long_single_word"] += any(
            gui._visible_len(line) > 42 and len(line.split()) == 1 for line in lines
        )
    return result


def _caps_ratio(src_map: dict) -> float:
    eligible = []
    for text in src_map.values():
        letters = [char for char in str(text or "") if char.isalpha()]
        if len(letters) >= 4:
            eligible.append(all(char.isupper() for char in letters))
    return (sum(eligible) / len(eligible)) if eligible else 0.0


def _best_two_line_width(text: str) -> int | None:
    value = re.sub(r"\s*\n\s*", " ", str(text or "").strip())
    spans = gui._tag_spans(value)
    widths = []
    for cut, char in enumerate(value):
        if char != " " or gui._position_is_inside_tag(cut, spans):
            continue
        left = value[:cut].rstrip()
        right = value[cut + 1:].lstrip()
        if left and right:
            widths.append(max(gui._visible_len(left), gui._visible_len(right)))
    return min(widths) if widths else None


def _bucket(value: float, edges: tuple) -> str:
    low = None
    for edge in edges:
        if value <= edge:
            return f"<={edge:g}" if low is None else f"{low:g}-{edge:g}"
        low = edge
    return f">{edges[-1]:g}"


def run(repo: Path) -> dict:
    metrics = Counter()
    hist = {
        "cps": Counter(),
        "fragment_gap_ms": Counter(),
        "fragment_chars": Counter(),
        "fragment_cps": Counter(),
    }
    samples = {
        "ai_unproven_boundaries": [],
        "cue_fill_moves": [],
        "mixed_file_caps_changes": [],
        "merged_speaker_crossings": [],
        "remaining_one_char_lines": [],
        "remaining_over_2_lines": [],
        "remaining_reflowable_wide": [],
        "tagged_line_violations": [],
    }
    typography = Counter()

    for source_path, delivery_path, ham_path in _pairs(repo):
        metrics["pairs"] += 1
        source = _blocks(gui.parse_subtitle(str(source_path)))
        raw = _plain(_blocks(gui.parse_subtitle(str(ham_path))))
        delivery = _plain(_blocks(gui.parse_subtitle(str(delivery_path))))
        if not source or not raw or not delivery:
            metrics["parse_incomplete_pairs"] += 1
            continue

        metrics["source_cues"] += len(source)
        metrics["raw_cues"] += len(raw)
        metrics["delivery_cues"] += len(delivery)

        before_lines = _line_metrics(delivery)
        after_line_blocks = gui.apply_line_breaks(delivery)
        after_lines = _line_metrics(after_line_blocks)
        for key, value in before_lines.items():
            metrics[f"delivery_line_before_{key}"] += value
        for key, value in after_lines.items():
            metrics[f"delivery_line_after_{key}"] += value
        metrics["delivery_line_changed"] += sum(
            old[2] != new[2] for old, new in zip(delivery, after_line_blocks)
        )
        metrics["delivery_line_text_loss"] += sum(
            old[2].replace("\n", " ").split() != new[2].replace("\n", " ").split()
            for old, new in zip(delivery, after_line_blocks)
        )
        for idx, _ts, text in after_line_blocks:
            lines = str(text or "").splitlines() or [""]
            if len(lines) > 2:
                metrics["delivery_line_after_over_2_dialogue"] += (
                    gui._is_dialogue_cue(text))
                if len(samples["remaining_over_2_lines"]) < 8:
                    samples["remaining_over_2_lines"].append(
                        f"{delivery_path}#{idx}: {text!r}")
            for line in lines:
                if gui._visible_len(line) == 1 and len(
                        samples["remaining_one_char_lines"]) < 8:
                    samples["remaining_one_char_lines"].append(
                        f"{delivery_path}#{idx}: {text!r}")
            if any(gui._visible_len(line) > 42 for line in lines):
                total = gui._visible_len(str(text or "").replace("\n", " "))
                metrics["delivery_line_after_wide_cues"] += 1
                metrics["delivery_line_after_wide_total_gt_84"] += total > 84
                metrics["delivery_line_after_wide_dialogue"] += (
                    gui._is_dialogue_cue(text))
                reflowable = (
                    total <= 84 and not gui._is_dialogue_cue(text)
                    and len(lines) <= 2)
                metrics["delivery_line_after_reflowable_wide"] += reflowable
                best_width = _best_two_line_width(text) if reflowable else None
                metrics["delivery_line_after_wordbreak_satisfiable"] += (
                    best_width is not None and best_width <= 42)
                if best_width is not None and best_width > 42:
                    hist.setdefault("remaining_best_width", Counter())[
                        _bucket(best_width, (43, 44, 45, 46, 48, 52, 58))] += 1
                if (reflowable
                        and len(samples["remaining_reflowable_wide"]) < 8):
                    samples["remaining_reflowable_wide"].append(
                        f"{delivery_path}#{idx}: {text!r}")
        if (before_lines["tagged_over_42"] and len(samples["tagged_line_violations"]) < 8):
            for idx, _ts, text in delivery:
                if (any(mark in text for mark in ("<", "{"))
                        and any(gui._visible_len(line) > 42 for line in text.splitlines())):
                    samples["tagged_line_violations"].append(
                        f"{delivery_path}#{idx}: {text!r}")
                    break

        source_map_raw = _source_map_by_span(raw, source)
        allowed = _allowed_source_pairs(source)
        permissions = gui._source_merge_permissions(source)

        deterministic = gui.merge_fragmented_cues(raw, source_cues=source)
        merge_groups = _span_members(raw, deterministic)
        metrics["merge_groups"] += len(merge_groups)
        metrics["merge_removed_cues"] += len(raw) - len(deterministic)
        for merged, members in merge_groups:
            markers = [_speaker_marker(source_map_raw.get(str(item[0]), "")) for item in members]
            named = {marker for marker in markers if marker and marker != "-"}
            crossing = len(named) > 1 or sum(marker == "-" for marker in markers) > 1
            metrics["merge_speaker_crossings"] += crossing
            if crossing and len(samples["merged_speaker_crossings"]) < 8:
                samples["merged_speaker_crossings"].append(
                    f"{ham_path}#{merged[0]}: {markers!r} => {merged[2]!r}")

        candidates = gui._segmentation_candidates(raw)
        for start, end in candidates:
            for pos in range(start, end):
                left = gui._srt_timestamp_bounds(raw[pos][1])
                right = gui._srt_timestamp_bounds(raw[pos + 1][1])
                metrics["ai_candidate_boundaries"] += 1
                if (left, right) not in allowed:
                    metrics["ai_unproven_boundaries"] += 1
                    if len(samples["ai_unproven_boundaries"]) < 10:
                        samples["ai_unproven_boundaries"].append(
                            f"{ham_path}#{raw[pos][0]}-#{raw[pos + 1][0]}: "
                            f"{raw[pos][2]!r} | {raw[pos + 1][2]!r}")

        guarded_candidates = gui._segmentation_candidates(
            raw, source_permissions=permissions)
        for start, end in guarded_candidates:
            metrics["ai_guarded_candidate_boundaries"] += end - start
            for pos in range(start, end):
                left = gui._srt_timestamp_bounds(raw[pos][1])
                right = gui._srt_timestamp_bounds(raw[pos + 1][1])
                metrics["ai_guarded_unproven_boundaries"] += (
                    (left, right) not in allowed)

        raw_by_bounds = {}
        for row in raw:
            try:
                raw_by_bounds.setdefault(gui._srt_timestamp_bounds(row[1]), []).append(row)
            except ValueError:
                pass
        for left, right in allowed:
            left_rows = raw_by_bounds.get(left, [])
            right_rows = raw_by_bounds.get(right, [])
            if len(left_rows) != 1 or len(right_rows) != 1:
                continue
            a, b = left_rows[0], right_rows[0]
            gap = right[0] - left[1]
            chars = gui._visible_len(a[2]) + 1 + gui._visible_len(b[2])
            span = max((right[1] - left[0]) / 1000.0, 0.001)
            speed = chars / span
            metrics["fragment_pairs_measured"] += 1
            hist["fragment_gap_ms"][_bucket(gap, (0, 100, 250, 500, 750, 1000))] += 1
            hist["fragment_chars"][_bucket(chars, (42, 60, 84, 100, 120))] += 1
            hist["fragment_cps"][_bucket(speed, (12, 17, 21, 24, 30))] += 1
            metrics["fragment_blocked_gap_only"] += (
                gap > gui.MERGE_MAX_GAP_MS and chars <= gui.MERGE_MAX_CHARS
                and speed <= gui.CPS_WARN_LIMIT
            )
            metrics["fragment_blocked_chars_only"] += (
                chars > gui.MERGE_MAX_CHARS and 0 <= gap <= gui.MERGE_MAX_GAP_MS
                and speed <= gui.CPS_WARN_LIMIT
            )

        plan = gui._cue_fill_move_plan(
            deterministic, _source_map_by_span(deterministic, source))
        metrics["cue_fill_moves"] += len(plan)
        deterministic_by_id = {str(row[0]): row for row in deterministic}
        for prev_id, idx, new_prev, new_text in plan:
            prev_row = deterministic_by_id.get(prev_id)
            row = deterministic_by_id.get(idx)
            proven = False
            if prev_row and row:
                prev_bounds = gui._srt_timestamp_bounds(prev_row[1])
                bounds = gui._srt_timestamp_bounds(row[1])
                proven = any(
                    left[1] == prev_bounds[1] and right[0] == bounds[0]
                    for left, right in allowed
                )
            metrics["cue_fill_source_fragment_proven"] += proven
            if len(samples["cue_fill_moves"]) < 12:
                source_before = _source_map_by_span(
                    [prev_row, row] if prev_row and row else [], source)
                samples["cue_fill_moves"].append(
                    f"{ham_path}#{idx}->#{prev_id} proven={proven} "
                    f"ts={row[1] if row else ''}: {new_prev!r} || {new_text!r} "
                    f"src={source_before!r}")

        raw_fast = ht.find_fast_lines(raw, 21.0)
        merged_fast = ht.find_fast_lines(deterministic, 21.0)
        metrics["condense_fast_before_merge"] += len(raw_fast)
        metrics["condense_fast_after_merge"] += len(merged_fast)
        metrics["condense_merge_resolved_ids"] += len(
            gui._merge_resolved_fast_ids(raw, source))
        for merged, members in merge_groups:
            member_fast = sum(
                (gui._cue_reading_speed(item[2], item[1]) or 0.0) > 21.0
                for item in members
            )
            merged_fast_cps = gui._cue_reading_speed(merged[2], merged[1]) or 0.0
            if member_fast and merged_fast_cps <= 21.0:
                metrics["condense_avoidable_groups"] += 1
                metrics["condense_avoidable_cues"] += member_fast

        caps_ratio = _caps_ratio(source_map_raw)
        metrics["source_files_caps_ratio_ge_080"] += caps_ratio >= 0.80
        caps_blocks, caps_changed = gui._normalize_all_caps_delivery(raw, source_map_raw)
        metrics["caps_changed"] += caps_changed
        if caps_ratio < 0.8:
            mixed_changes = [
                (old, new) for old, new in zip(raw, caps_blocks) if old[2] != new[2]
            ]
            metrics["caps_changed_in_mixed_source_files"] += len(mixed_changes)
            if mixed_changes and len(samples["mixed_file_caps_changes"]) < 10:
                old, new = mixed_changes[0]
                samples["mixed_file_caps_changes"].append(
                    f"{ham_path}#{old[0]} ratio={caps_ratio:.3f}: {old[2]!r} -> {new[2]!r}")

        for _idx, ts, text in delivery:
            try:
                duration = max(gui._ts_end_sec_gui(ts) - gui._ts_to_sec_gui(ts), 0.001)
            except Exception:
                continue
            speed = gui._visible_len(text) / duration
            hist["cps"][_bucket(speed, (12, 17, 21, 24, 30))] += 1

        for label, rows in (("raw", raw), ("delivery", delivery)):
            for _idx, _ts, text in rows:
                for char in str(text or ""):
                    if (ord(char) in gui._DELIVERY_TYPOGRAPHY_MAP
                            or char in "′″"):
                        typography[f"{label}:{ord(char):04X}"] += 1

    return {
        "metrics": dict(sorted(metrics.items())),
        "histograms": {
            name: dict(counter) for name, counter in hist.items()
        },
        "typography": dict(sorted(typography.items())),
        "samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(run(args.repo.resolve()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
