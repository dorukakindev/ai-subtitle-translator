from dataclasses import dataclass
import re


@dataclass
class Cue:
    index: int
    start: str
    end: str
    text: str


_TIME_RE = re.compile(
    r"(?P<start>\d+:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
    r"(?P<end>\d+:\d{2}:\d{2}[,.]\d{3})(?:\s+.*)?"
)


def parse_srt(text: str) -> list[Cue]:
    """Numaralı veya numarasız SRT metnini Cue listesine çevirir."""
    if not text:
        return []

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip("\ufeff\n ")
    if not normalized:
        return []

    parsed = []
    lines = normalized.split("\n")

    def _cue_start(pos):
        if pos >= len(lines):
            return None
        current = lines[pos].strip()
        if _TIME_RE.match(current):
            return None, current, pos + 1
        if (re.fullmatch(r"\d+", current) and pos + 1 < len(lines)
                and _TIME_RE.match(lines[pos + 1].strip())):
            return int(current), lines[pos + 1].strip(), pos + 2
        return None

    i = 0
    while i < len(lines):
        start = _cue_start(i)
        if start is None:
            i += 1
            continue
        idx, time_line, i = start
        match = _TIME_RE.match(time_line)
        if not match:
            continue
        body_lines = []
        while i < len(lines):
            if _cue_start(i) is not None:
                break
            if not lines[i].strip():
                next_nonblank = i + 1
                while next_nonblank < len(lines) and not lines[next_nonblank].strip():
                    next_nonblank += 1
                if _cue_start(next_nonblank) is not None or next_nonblank >= len(lines):
                    i = next_nonblank
                    break
                i = next_nonblank
                continue
            body_lines.append(lines[i].rstrip())
            i += 1
        body = "\n".join(body_lines).strip()
        if body:
            parsed.append((idx, match.group("start").replace(".", ","),
                           match.group("end").replace(".", ","), body))

    raw_ids = [idx for idx, _start, _end, _body in parsed]
    valid_ids = bool(raw_ids) and all(idx is not None for idx in raw_ids)
    if valid_ids:
        valid_ids = all(a < b for a, b in zip(raw_ids, raw_ids[1:]))
    return [Cue(idx if valid_ids else pos, start, end, body)
            for pos, (idx, start, end, body) in enumerate(parsed, 1)]
