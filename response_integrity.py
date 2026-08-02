import json
from dataclasses import dataclass, field


@dataclass
class TranslationParseResult:
    translations: dict[str, str] = field(default_factory=dict)
    missing_ids: set[str] = field(default_factory=set)
    duplicate_ids: set[str] = field(default_factory=set)
    unexpected_ids: set[str] = field(default_factory=set)
    invalid_text_ids: set[str] = field(default_factory=set)
    malformed_items: int = 0
    parse_mode: str = "invalid"
    fatal_reason: str | None = None


def _strip_fence(raw: str) -> str:
    value = str(raw or "").strip()
    if not value.startswith("```"):
        return value
    # Bazı sağlayıcılar tüm JSON'u açılış fence satırında döndürür
    # (````json [{...}]````). Satırlara bölmek bu tek satırı atıp geçerli
    # batch sonucunu hatalı yanıta dönüştürürdü.
    if "\n" not in value and value.endswith("```") and value.count("```") >= 2:
        inner = value[3:-3].strip()
        if inner.lower().startswith("json"):
            inner = inner[4:].strip()
        return inner
    lines = value.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _balanced_json(raw: str) -> str:
    start = -1
    opener = ""
    for pos, ch in enumerate(raw):
        if ch in "[{":
            start, opener = pos, ch
            break
    if start < 0:
        return ""
    closer = "]" if opener == "[" else "}"
    depth = 0
    in_string = False
    escaped = False
    for pos in range(start, len(raw)):
        ch = raw[pos]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return raw[start:pos + 1]
    return ""


def _salvage_array(raw: str) -> list:
    start = raw.find("[")
    if start < 0:
        return []
    decoder = json.JSONDecoder()
    pos = start + 1
    items = []
    while pos < len(raw):
        while pos < len(raw) and raw[pos] in " \t\r\n,":
            pos += 1
        if pos >= len(raw) or raw[pos] == "]":
            break
        try:
            item, end = decoder.raw_decode(raw, pos)
        except Exception:
            break
        items.append(item)
        pos = end
    return items


def translation_items_from_raw(raw: str) -> tuple[list | None, str]:
    value = _strip_fence(raw)
    if not value:
        return None, "invalid"
    candidates = [value]
    for pos, char in enumerate(value):
        if char not in "[{":
            continue
        balanced = _balanced_json(value[pos:])
        if balanced and balanced not in candidates:
            candidates.append(balanced)
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, list):
            return parsed, "array"
        if isinstance(parsed, dict) and isinstance(parsed.get("tr"), list):
            return parsed["tr"], "envelope"
        continue
    salvaged = _salvage_array(value)
    if salvaged:
        return salvaged, "salvaged"
    return None, "invalid"


def parse_translation_payload(raw: str, expected_ids) -> TranslationParseResult:
    expected = {str(value) for value in (expected_ids or [])}
    result = TranslationParseResult()
    items, mode = translation_items_from_raw(raw)
    result.parse_mode = mode
    if items is None:
        result.missing_ids = set(expected)
        result.fatal_reason = "invalid_json"
        return result
    seen = set()
    for item in items:
        if not isinstance(item, dict) or "i" not in item or "t" not in item:
            result.malformed_items += 1
            continue
        cue_id = str(item["i"])
        if cue_id in seen:
            result.duplicate_ids.add(cue_id)
            result.translations.pop(cue_id, None)
            continue
        seen.add(cue_id)
        if expected and cue_id not in expected:
            result.unexpected_ids.add(cue_id)
            continue
        if not isinstance(item["t"], str):
            result.invalid_text_ids.add(cue_id)
            continue
        result.translations[cue_id] = item["t"]
    for cue_id in result.duplicate_ids:
        result.translations.pop(cue_id, None)
    result.missing_ids = expected - set(result.translations)
    if result.duplicate_ids:
        result.fatal_reason = "duplicate_id"
    elif result.unexpected_ids:
        result.fatal_reason = "unexpected_id"
    elif result.invalid_text_ids:
        result.fatal_reason = "invalid_text_type"
    return result
