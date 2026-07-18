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

    cues: list[Cue] = []
    blocks = re.split(r"\n\s*\n", normalized)
    auto_index = 1
    for block in blocks:
        lines = [line.rstrip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue

        idx = auto_index
        time_line_pos = 0
        if lines and re.fullmatch(r"\d+", lines[0].strip()):
            idx = int(lines[0].strip())
            time_line_pos = 1
        if time_line_pos >= len(lines):
            continue

        m = _TIME_RE.match(lines[time_line_pos].strip())
        if not m:
            continue

        body = "\n".join(lines[time_line_pos + 1:]).strip()
        cues.append(Cue(idx, m.group("start").replace(".", ","), m.group("end").replace(".", ","), body))
        auto_index = max(auto_index + 1, idx + 1)

    return cues

