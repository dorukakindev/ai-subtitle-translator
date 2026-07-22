from dataclasses import dataclass
import re


@dataclass
class Cue:
    index: int
    start: str
    end: str
    text: str


_TIME_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
    r"(?P<end>\d{1,2}:\d{2}:\d{2}[,.]\d{3})(?:\s+.*)?"
)


def parse_srt(text: str) -> list[Cue]:
    """Numaralı veya numarasız SRT metnini Cue listesine çevirir."""
    if not text:
        return []

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip("\ufeff\n ")
    if not normalized:
        return []

    parsed = []
    blocks = re.split(r"\n\s*\n", normalized)
    for block in blocks:
        lines = [line.rstrip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue

        idx = None
        time_line_pos = 0
        if len(lines) >= 2 and _TIME_RE.match(lines[1].strip()):
            idx = int(lines[0].strip()) if re.fullmatch(r"\d+", lines[0].strip()) else None
            time_line_pos = 1
        elif not _TIME_RE.match(lines[0].strip()):
            continue

        m = _TIME_RE.match(lines[time_line_pos].strip())
        if not m:
            continue

        body = "\n".join(lines[time_line_pos + 1:]).strip()
        parsed.append((idx, m.group("start").replace(".", ","),
                       m.group("end").replace(".", ","), body))

    raw_ids = [idx for idx, _start, _end, _body in parsed]
    valid_ids = bool(raw_ids) and all(idx is not None for idx in raw_ids)
    if valid_ids:
        valid_ids = all(a < b for a, b in zip(raw_ids, raw_ids[1:]))
    return [Cue(idx if valid_ids else pos, start, end, body)
            for pos, (idx, start, end, body) in enumerate(parsed, 1)]
