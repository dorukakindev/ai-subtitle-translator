"""
subtitle_formats.py — Çoklu altyazı formatı dönüştürücüsü.

Desteklenen formatlar: .srt, .vtt (WebVTT), .ass/.ssa (Advanced SubStation Alpha)
Her format → (index_str, timestamp_str, text) üçlülerine dönüştürülür.
"""

import glob as _glob
import os
import re
import unicodedata
from pathlib import Path


_SOURCE_HTML_TAG = re.compile(r'</?[a-zA-Z][^>]*>')
_SOURCE_MALFORMED_FORMAT_TAG = re.compile(
    r'<\s*/?\s*(?:i|b|u|font)\b[^>]*>',
    re.IGNORECASE,
)
_VTT_VOICE_TAG = re.compile(r'(?:<v(?:\s+[^>]*)?>|</v>)', re.IGNORECASE)
# ruby/rt: Japonca WebVTT dosyalarında okunuş etiketleri. SRT'de karşılığı yok;
# geri yüklenirlerse oynatıcılarda '<ruby>Türkçe</ruby>' olarak ekrana basılır.
_VTT_SRT_UNSAFE_TAG = re.compile(
    r'</?(?:c(?:\.[^\s>]*)?|v(?:\s+[^>]*)?|lang(?:\s+[^>]*)?|ruby|rt)\s*>',
    re.IGNORECASE,
)
_SOURCE_VTT_TIMESTAMP = re.compile(r'<\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3}>')
_SOURCE_ASS_OVERRIDE = re.compile(r'\{\\[^}]*\}')
_SOURCE_EMPTY_OVERRIDE = re.compile(r'\{\}')
_GENERATED_SUBTITLE_NAME_RE = re.compile(
    r'(?:\.tr|\.partial|\.wave[12]of2)\.srt$|\.bak\.srt$',
    re.IGNORECASE,
)
_LEGACY_DETECT_ENCODINGS = {
    "big5", "big5hkscs", "cp932", "cp949", "euc_jp", "euc_kr",
    "cp1250", "cp1251", "cp1252", "cp1253", "cp1255", "cp1256",
    "gb18030", "gbk", "koi8_r", "shift_jis",
    "shift_jis_2004", "shift_jisx0213", "windows_1251", "windows_1253",
    "windows_1250", "windows_1252", "windows_1255", "windows_1256",
}


def _legacy_language_score(text: str, encoding: str) -> float:
    """Aynı baytları farklı alfabeler geçerli saydığında dilsel adayı ayır."""
    enc = encoding.lower().replace("-", "_")
    family = {
        "windows_1251": "cp1251", "koi8_r": "cp1251",
        "windows_1250": "cp1250", "windows_1252": "cp1252", "mac_roman": "cp1252",
        "windows_1253": "cp1253", "windows_1255": "cp1255",
        "windows_1256": "cp1256",
    }.get(enc, enc)
    common = _SHORT_LEGACY_COMMON_BIGRAMS.get(family)
    if not common:
        return 0.0
    words = re.findall(r"[^\W\d_]+", text.casefold(), flags=re.UNICODE)
    bigrams = [word[pos:pos + 2] for word in words for pos in range(len(word) - 1)]
    if not bigrams:
        return 0.0
    return sum(pair in common for pair in bigrams) / len(bigrams)
_SHORT_LEGACY_COMMON_LETTERS = {
    "cp1250": set("abcdefghijklmnoprstuwyzáąćčďéěęíĺľłńňóôŕřśšťúůýźżž"),
    "cp1251": set("\u043e\u0435\u0430\u0438\u043d\u0442\u0441\u0440\u0432\u043b\u043a\u043c\u0434\u043f\u0443\u044f\u044b\u044c\u0433\u0437\u0431\u0447\u0439\u0445\u0436\u0448\u044e\u0446\u0449\u044d\u0444\u044a"),
    "cp1252": set("abcdefghijklmnopqrstuvwxyzàâäáåæçéèêëíîïñóôöœúûüÿ"),
    "cp1253": set("\u03b1\u03b5\u03bf\u03b9\u03c4\u03b7\u03c1\u03bd\u03c3\u03ba\u03c0\u03bc\u03bb\u03c5\u03c9\u03b3\u03b4\u03b8\u03c7\u03b2\u03be\u03c6\u03c8\u03b6"),
    "cp1255": set("אבגדהוזחטיכלמנסעפצקרשתךםןףץ"),
    "cp1256": set("\u0627\u0644\u064a\u0648\u0645\u0646\u0631\u062a\u0628\u0643\u062f\u0633\u0639\u0641\u0647\u0642\u062d\u062c\u0634\u0635\u0636\u0637\u0638\u0632\u062e\u0630\u062b\u063a\u0621"),
    "cp1254": set("abc\u00e7defg\u011fh\u0131ijklmno\u00f6prs\u015ftu\u00fcvyz"),
}
_SHORT_LEGACY_COMMON_BIGRAMS = {
    "cp1250": {"ie", "ni", "rz", "sz", "cz", "ow", "po", "pr", "ze", "st", "na", "to", "je", "dz"},
    "cp1251": {"ст", "но", "то", "на", "ен", "ов", "ни", "ра", "во", "ко", "по", "пр", "ри", "ив", "ве", "ет"},
    "cp1252": {"le", "de", "es", "en", "la", "un", "que", "ent", "les", "ion", "th", "he", "in", "er", "an"},
    "cp1253": {"ου", "αι", "ει", "τη", "το", "κα", "αυ", "με", "ρα", "λη", "ερ", "σε", "πρ", "στ", "ον"},
    "cp1255": {"של", "ים", "הי", "את", "על", "לא", "מה", "זה", "אנ", "בע", "ול", "הא", "אד", "לם"},
    "cp1256": {"ال", "لل", "من", "في", "ما", "ها", "مر", "رح", "حب", "با", "لع", "عا", "لم"},
    "cp1254": {"ar", "er", "in", "an", "en", "le", "de", "la", "ya", "ol", "şu", "bu", "mi", "ve"},
}
_SHORT_LEGACY_DISTINCTIVE_CHARS = {
    "cp1250": set("\u0105\u0107\u0119\u0142\u0144\u00f3\u015b\u017a\u017c"),
}


def clean_translation_source_text(text: str) -> str:
    """Çeviri bağlamında VTT konuşmacısını koruyup görsel etiketleri temizle."""
    text = _SOURCE_MALFORMED_FORMAT_TAG.sub("", str(text or ""))
    text = _SOURCE_HTML_TAG.sub(
        lambda match: match.group(0)
        if _VTT_VOICE_TAG.fullmatch(match.group(0)) else "",
        text,
    )
    text = _SOURCE_VTT_TIMESTAMP.sub("", text)
    text = _SOURCE_ASS_OVERRIDE.sub("", text)
    text = _SOURCE_EMPTY_OVERRIDE.sub("", text)
    text = re.sub(r"  +", " ", text)
    return text.strip()


# ── Toleranslı encoding çözümleme ─────────────────────────────────────────────

def normalize_srt_timestamp_separators(text: str) -> str:
    """SRT zaman satırlarındaki hatalı ayraçları ve kısa milisaniyeleri düzeltir."""
    pattern = re.compile(
        r'(?m)^([ \t]*)(\d+)[;:](\d{2})[;:](\d{2})[,.](\d{1,3})([ \t]*'
        r'-->[ \t]*)(\d+)[;:](\d{2})[;:](\d{2})[,.](\d{1,3})([^\n]*)$'
    )

    def replace(match):
        lead, sh, sm, ss, sms, arrow, eh, em, es, ems, tail = match.groups()
        # Saat 2 haneye tamamlanmalı: '0:01:23,456' biçimini donanımsal oynatıcılar
        # ve bazı yazılımlar yüklemiyor.
        return (
            f"{lead}{int(sh):02d}:{sm}:{ss},{(sms + '000')[:3]}{arrow}"
            f"{int(eh):02d}:{em}:{es},{(ems + '000')[:3]}{tail}"
        )

    return pattern.sub(replace, str(text or ""))


def _legacy_script_ratio(text: str, encoding: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    enc = encoding.lower().replace("-", "_")
    if enc in {"cp932", "euc_jp", "shift_jis", "shift_jis_2004", "shift_jisx0213"}:
        matched = sum(
            "\u3040" <= ch <= "\u30ff" or "\u3400" <= ch <= "\u9fff"
            for ch in letters)
    elif enc in {"gb18030", "gbk", "big5", "big5hkscs"}:
        matched = sum("\u3400" <= ch <= "\u9fff" for ch in letters)
    elif enc in {"cp949", "euc_kr"}:
        matched = sum(
            "\uac00" <= ch <= "\ud7af" or "\u3400" <= ch <= "\u9fff"
            for ch in letters)
    elif enc in {"cp1250", "cp1252", "cp1254", "mac_roman",
                 "windows_1250", "windows_1252", "windows_1254"}:
        matched = sum("\u0041" <= ch <= "\u024f" for ch in letters)
    elif enc in {"cp1251", "windows_1251", "koi8_r"}:
        matched = sum("\u0400" <= ch <= "\u052f" for ch in letters)
    elif enc in {"cp1253", "windows_1253"}:
        matched = sum("\u0370" <= ch <= "\u03ff" or "\u1f00" <= ch <= "\u1fff"
                      for ch in letters)
    elif enc in {"cp1256", "windows_1256"}:
        matched = sum("\u0600" <= ch <= "\u06ff" or "\u0750" <= ch <= "\u077f"
                      for ch in letters)
    elif enc in {"cp1255", "windows_1255"}:
        matched = sum("\u0590" <= ch <= "\u05ff" for ch in letters)
    else:
        matched = sum(ord(ch) > 127 for ch in letters)
    return matched / len(letters)


def _decode_short_legacy(raw: bytes) -> str | None:
    """Kısa eski kodlu metni Yunanca/Arapçayı Kiril saymadan seçer."""
    candidates = []
    for encoding in ("cp1250", "cp1251", "cp1252", "cp1253", "cp1255",
                     "cp1256", "cp1254", "mac_roman"):
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        letters = [ch.casefold() for ch in text if ch.isalpha()]
        if not letters:
            continue
        family = "cp1252" if encoding == "mac_roman" else encoding
        common = _SHORT_LEGACY_COMMON_LETTERS[family]
        common_ratio = sum(ch in common for ch in letters) / len(letters)
        bigram_ratio = _legacy_language_score(text, encoding)
        script_ratio = _legacy_script_ratio(text, encoding)
        distinctive = _SHORT_LEGACY_DISTINCTIVE_CHARS.get(family, set())
        distinctive_bonus = min(
            0.6, sum(ch in distinctive for ch in letters) * 0.1)
        # CP1254'te ASCII ve Türkçe harfler birlikte normaldir; diğer adayların
        # gerçekten kendi yazı sistemine benzemesi gerekir.
        if encoding not in {"cp1250", "cp1252", "cp1254"} and script_ratio < 0.55:
            continue
        suspicious = len(re.findall(
            r"(?<=[^\W\d_])(?:[\u2010-\u2017\u2020-\u2027]|[‡–—])"
            r"(?=[^\W\d_])", text))
        candidates.append(((common_ratio * 0.2) + (bigram_ratio * 1.2)
                            + (script_ratio * 0.15) + distinctive_bonus
                            - (suspicious * 0.75), text))
    if not candidates:
        return None
    score, text = max(candidates, key=lambda item: item[0])
    return text if score >= 0.45 else None


def _decode_detected_legacy(raw: bytes) -> str | None:
    if not raw:
        return None
    if len(raw) < 80:
        return _decode_short_legacy(raw)
    try:
        from charset_normalizer import from_bytes
        matches = list(from_bytes(raw))[:10]
    except Exception:
        return None
    candidates = []
    for match in matches:
        encoding = str(match.encoding or "").lower().replace("-", "_")
        if encoding not in _LEGACY_DETECT_ENCODINGS:
            continue
        try:
            text = raw.decode(match.encoding)
        except (LookupError, UnicodeDecodeError):
            continue
        if re.search(
                r"(?<=[^\W\d_])(?:[\u2010-\u2017\u2020-\u2027]|[‡–—])"
                r"(?=[^\W\d_])", text):
            continue
        coherence = float(getattr(match, "coherence", 0.0) or 0.0)
        chaos_value = getattr(match, "chaos", None)
        chaos = float(chaos_value) if chaos_value is not None else 1.0
        if chaos > 0.2:
            continue
        ratio = _legacy_script_ratio(text, encoding)
        punctuation_bonus = 0.0
        if encoding in {
            "cp932", "euc_jp", "shift_jis", "shift_jis_2004", "shift_jisx0213",
        }:
            punctuation_bonus = min(0.5, sum(ch in "。、！？" for ch in text) / 20)
        language_score = _legacy_language_score(text, encoding)
        score = ratio + (coherence * 2.0) - chaos + punctuation_bonus + (language_score * 2.0)
        if coherence >= 0.15 or ratio >= 0.2:
            candidates.append((score, text))
    return max(candidates, default=(0.0, None), key=lambda item: item[0])[1]


def _legacy_decode_penalty(text: str) -> int:
    c1 = sum("\x80" <= ch <= "\x9f" for ch in text)
    internal_punctuation = len(re.findall(
        r"(?<=[^\W\d_])[\u2010-\u2027](?=[^\W\d_])", text))
    return (c1 * 4) + internal_punctuation


def _decode_embedded_controls(text: str, encoding: str) -> str | None:
    out = []
    for ch in text:
        if "\x80" <= ch <= "\x9f":
            try:
                out.append(bytes((ord(ch),)).decode(encoding))
            except UnicodeDecodeError:
                return None
        else:
            out.append(ch)
    return "".join(out)


def _repair_embedded_mac_roman_controls(text: str) -> str:
    """Latin-1 fallback'inde kontrol karakterine dönüşmüş baytları geri kazanır.

    Bu baytlar İngilizce/Batı Avrupa altyazılarında çoğunlukla Windows-1252
    noktalama işaretleridir (“ ” ’ – — …); koşulsuz MacRoman uygulamak onları
    anlamsız 'ì', 'î', 'Ö' harflerine çeviriyordu. Ayırt edici sinyal konumdur:
    MacRoman'da bu baytlar kelime İÇİNDEKİ aksanlı harflerdir (Rodr•guez), cp1252
    noktalamasıysa ağırlıklı olarak kelime sınırlarında durur."""
    if sum("\x80" <= ch <= "\x9f" for ch in text) < 2:
        return text
    base_penalty = _legacy_decode_penalty(text)
    controls = [
        pos for pos, ch in enumerate(text) if "\x80" <= ch <= "\x9f"
    ]
    inside_word = sum(
        1 for pos in controls
        if pos > 0 and pos + 1 < len(text)
        and text[pos - 1].isalpha() and text[pos + 1].isalpha()
    )
    if inside_word < len(controls) / 2:
        cp1252 = _decode_embedded_controls(text, "cp1252")
        if cp1252 is not None and _legacy_decode_penalty(cp1252) <= base_penalty:
            return cp1252
    repaired = _decode_embedded_controls(text, "mac_roman")
    if repaired is not None and _legacy_decode_penalty(repaired) < base_penalty:
        return repaired
    return text


def _decode_cp1254_or_mac_roman(raw: bytes) -> str | None:
    try:
        cp1254 = raw.decode("cp1254")
    except UnicodeDecodeError:
        try:
            return raw.decode("mac_roman")
        except UnicodeDecodeError:
            return None
    try:
        mac_roman = raw.decode("mac_roman")
    except UnicodeDecodeError:
        return cp1254

    cp_penalty = _legacy_decode_penalty(cp1254)
    mac_penalty = _legacy_decode_penalty(mac_roman)
    return mac_roman if cp_penalty >= 2 and mac_penalty < cp_penalty else cp1254


_NUL_HEX_ARTIFACT_RE = re.compile(r"\x00([0-9A-Fa-f]{2})")
# Model çıktısında kelime İÇİNDE görülen görünmez karakterler (sıfır-genişlik,
# BOM, yön işaretleri): ekranda hiçbir şey göstermez ama 'gülleleri' → 'gül​leri'
# gibi kelimeyi böler, aramayı/karşılaştırmayı ve TM eşleşmesini bozar.
_INVISIBLE_FORMAT_CHARS = frozenset(
    "​‌‍‎‏⁠⁡⁢⁣⁤"
    "‪‫‬‭‮⁦⁧⁨⁩"
    "﻿᠎"
    # U+00AD (soft hyphen): bazı oynatıcılar kelime ortasında GÖRÜNÜR tire basıyor
    # ('ay­nı' -> 'ay-nı'). Kaynakta satır kırma ipucu olarak duruyor, teslimde işi yok.
    "­"
)
# Görünür boşluk gibi davranan ama SRT'de sorun çıkaran boşluk çeşitleri.
_UNUSUAL_SPACE_CHARS = frozenset("       "
                                 "       　")


def normalize_subtitle_control_artifacts(text: str) -> str:
    """Repair model-emitted NUL+hex escapes and remove other C0 controls.

    Ayrıca sıfır-genişlik/BOM/yön işareti gibi görünmez biçim karakterlerini SİLER
    ve alışılmadık boşlukları normal boşluğa indirger."""
    value = _NUL_HEX_ARTIFACT_RE.sub(
        lambda match: chr(int(match.group(1), 16)), str(text or ""))
    out = []
    for char in value:
        if char in _INVISIBLE_FORMAT_CHARS:
            continue
        if char in _UNUSUAL_SPACE_CHARS:
            out.append(" ")
            continue
        out.append(char if ord(char) >= 32 or char in "\n\r\t" else " ")
    return "".join(out)


def read_subtitle_text(filepath) -> str:
    """Altyazı dosyasını toleranslı çözümler: utf-8-sig → utf-16 (BOM) → cp1254 → latin-1(replace).

    Sıra önemli: cp1254 ve latin-1 hemen her bayt dizisini kabul eder, bu yüzden
    önce katı utf-8-sig denenir (geçerliyse doğru olan odur). cp1254 (Windows-Türkçe)
    'şğıİöçü' içeren eski Türkçe altyazıları doğru açar; latin-1 son çare (asla patlamaz).
    UTF-16 yalnızca BOM (FF FE / FE FF) varsa denenir — rastgele cp1254 baytlarını
    bozuk UTF-16 olarak yorumlamamak için."""
    raw = Path(filepath).read_bytes()
    text = None
    sample = raw[:4096]
    if raw[:4] in (b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff"):
        try:
            text = raw.decode("utf-32")
        except UnicodeDecodeError:
            text = None
    if text is None and sample and sample.count(b"\x00") / len(sample) >= 0.5:
        lane_ratios = [
            sample[offset::4].count(0) / max(1, len(sample[offset::4]))
            for offset in range(4)
        ]
        enc = None
        if all(lane_ratios[offset] >= 0.6 for offset in (1, 2, 3)):
            enc = "utf-32-le"
        elif all(lane_ratios[offset] >= 0.6 for offset in (0, 1, 2)):
            enc = "utf-32-be"
        if enc:
            try:
                text = raw.decode(enc)
            except UnicodeDecodeError:
                text = None
    if text is None and raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            text = raw.decode("utf-16")
        except UnicodeDecodeError:
            text = None
    if text is None and sample and sample.count(b"\x00") / len(sample) >= 0.15:
        even_nuls = sample[0::2].count(0)
        odd_nuls = sample[1::2].count(0)
        enc = "utf-16-be" if even_nuls > odd_nuls else "utf-16-le"
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            text = None
    for enc in ("utf-8-sig",):
        if text is not None:
            break
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None and raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            text = raw.decode("utf-16")
        except UnicodeDecodeError:
            pass
    if text is None:
        text = _decode_detected_legacy(raw)
    if text is None:
        text = _decode_cp1254_or_mac_roman(raw)
    if text is None:
        text = raw.decode("latin-1", errors="replace")
    text = _repair_embedded_mac_roman_controls(text)
    # Satır sonlarını normalize et (eski metin-modu açılışın yaptığı gibi):
    # read_bytes()+decode() \r\n çevirmez; parser'lar \n\n'e güvenir.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if Path(filepath).suffix.lower() == ".srt":
        text = normalize_srt_timestamp_separators(text)
    return text


# ── Zaman damgası dönüştürme ──────────────────────────────────────────────────

def _vtt_ts_to_srt(ts: str) -> str:
    """WebVTT zaman damgasını (HH:MM:SS.mmm veya MM:SS.mmm) SRT formatına çevirir.
    Milisaniye kısmı 3 haneye tamamlanır (SRT geçerliliği: ,5 → ,500; ,12 → ,120)."""
    ts = ts.strip()
    match = re.fullmatch(r'(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d*)', ts)
    if not match:
        return ts
    hour, minute, second, ms = match.groups()
    return f"{int(hour or 0):02d}:{int(minute):02d}:{int(second):02d},{(ms + '000')[:3]}"

def _ass_ts_to_srt(ts: str) -> str:
    """ASS zaman damgasını (H:MM:SS.cc) SRT formatına çevirir.

    Standart ASS santisaniye kullanır ama bazı araçlar 3 haneli milisaniye yazar;
    o dosyalarda eskiden ham '1:23:45.678' değeri SRT'ye olduğu gibi geçiyordu."""
    ts = ts.strip()
    # H:MM:SS.cc → HH:MM:SS,mmm (centi-secs → milisecs)
    m = re.match(r'(\d{1,2}):(\d{2}):(\d{2})\.(\d{1,3})$', ts)
    if m:
        h, mm, s, frac = m.groups()
        ms = int(frac.ljust(3, '0')) if len(frac) == 3 else int(frac.ljust(2, '0')) * 10
        return f'{int(h):02d}:{mm}:{s},{ms:03d}'
    return ts


# ── Format etiketi geri yükleme ───────────────────────────────────────────────
# Çeviri öncesi kaynaktan sökülen <i>/<b>/<font>/{\an8} etiketlerini çeviri
# metnine geri uygular. Model etiketleri hiç görmez; konum ({\an8}) ve
# tam-blok/tam-satır sarmalama (italik iç ses, şarkı sözü) burada geri gelir.

_LEAD_OVERRIDE_RE = re.compile(r'^(?:\{\\[^}]*\})+')                    # {\an8}{\c&H..}
_TRAIL_OVERRIDE_RE = re.compile(r'(?:\{\\[^}]*\})+$')                  # {\i0}{\b0}
_ASS_OVERRIDE_BLOCK_RE = re.compile(r'\{\\[^}]*\}')
_SRT_SAFE_ASS_OVERRIDE_RE = re.compile(r'^\{(?:\\[ibus][01])+\}$', re.IGNORECASE)


def _strip_srt_unsafe_ass_overrides(text: str) -> str:
    def _safe_part(match):
        block = match.group(0)
        if _SRT_SAFE_ASS_OVERRIDE_RE.fullmatch(block):
            return block
        safe = re.findall(r'\\[ibus][01]', block, re.IGNORECASE)
        return "{" + "".join(safe) + "}" if safe else ""

    return _ASS_OVERRIDE_BLOCK_RE.sub(_safe_part, text)


def _match_full_wrap(src_body: str):
    """Metin tam bir açılış/kapanış etiket çiftiyle sarmalanmış mı?
    İçeride matematiksel '<' veya '>' karakterleri bulunabilir, ancak ek kapanış
    etiketleri (</...) olmamalıdır."""
    m = re.match(r'^\s*((?:<[a-zA-Z][^>]*>)+)(.*?)((?:</[a-zA-Z][^>]*>)+)\s*$', src_body, re.DOTALL)
    if not m:
        return None
    open_run, inner, close_run = m.groups()
    if re.search(r'</[a-zA-Z]', inner):
        return None
    return open_run, inner, close_run


def restore_format_tags(src_text: str, tr_text: str) -> str:
    """Kaynak satırın biçim etiketlerini çeviriye geri uygular.

    Desteklenen durumlar (güvenli olanlar):
    - Satır başındaki ASS override etiketleri ({\\an8} gibi konum etiketleri)
    - Tam blok sarmalama: <i>...</i>, <b><i>...</i></b>, <font ...>...</font>
    - Tam satır sarmalama: kaynağın TÜM dolu satırları aynı etiketle sarılı mı?
      çevirinin her satırı da sarılır
    Kısmi/satır-içi etiketler ('he said <i>no</i>') güvenle geri konamaz — atlanır.
    Çeviri zaten etiket içeriyorsa (idempotenlik) dokunulmaz."""
    if not src_text or not tr_text or tr_text.startswith("[HATA") or tr_text.strip() == "[ÇEVİRİ EKSİK]":
        return tr_text

    src = _VTT_SRT_UNSAFE_TAG.sub("", src_text).strip()
    out = _VTT_SRT_UNSAFE_TAG.sub("", tr_text)

    # 1) Baştaki ASS override etiketleri (konum bilgisi)
    m_lead = _LEAD_OVERRIDE_RE.match(src)
    lead = m_lead.group(0) if m_lead else ""
    src_body = src[len(lead):].strip() if lead else src
    m_tail = _TRAIL_OVERRIDE_RE.search(src_body)
    tail = m_tail.group(0) if m_tail else ""
    if tail:
        src_body = src_body[:-len(tail)].rstrip()

    # 2) Sarmalama — çeviri zaten BAŞTAN etiketliyse dokunma.
    if not re.match(r'^\s*<[a-zA-Z]', out):
        wm = _match_full_wrap(src_body)
        if wm:
            open_run, _inner, close_run = wm
            out = f"{open_run}{out}{close_run}"
        else:
            # Tam satır sarmalama: kaynağın TÜM dolu satırları aynı etiketle sarılı mı?
            src_lines = [ln.strip() for ln in src_body.split("\n") if ln.strip()]
            if len(src_lines) > 1:
                wraps = [_match_full_wrap(ln) for ln in src_lines]
                if all(wraps) and len({(w[0], w[2]) for w in wraps if w}) == 1:
                    o, c = wraps[0][0], wraps[0][2]
                    out = "\n".join(f"{o}{ln}{c}" if ln.strip() else ln
                                    for ln in out.split("\n"))

    # 3) Konum etiketini başa ekle
    if lead and not out.startswith(lead):
        out = lead + out
    if tail and not out.endswith(tail):
        out += tail
    src_lines = src.split("\n")
    out_lines = out.split("\n")
    if len(src_lines) == len(out_lines) and len(src_lines) > 1:
        restored = []
        for src_line, out_line in zip(src_lines, out_lines):
            src_line = src_line.strip()
            lm = _LEAD_OVERRIDE_RE.match(src_line)
            line_lead = lm.group(0) if lm else ""
            tm = _TRAIL_OVERRIDE_RE.search(src_line)
            line_tail = tm.group(0) if tm else ""
            # Satır bazlı HTML sarmalama: çok konuşmacılı bloklarda yalnızca BİR
            # satır italik olabilir ('<i>- Telsiz: Sorun var.</i>' + '- Anlaşıldı.').
            # Blok düzeyindeki all(wraps) kontrolü bu durumda başarısız olduğu için
            # tek satırlık iç ses/telsiz italikleri kalıcı olarak siliniyordu.
            line_body = src_line[len(line_lead):] if line_lead else src_line
            if line_tail and line_body.endswith(line_tail):
                line_body = line_body[:-len(line_tail)]
            line_wrap = _match_full_wrap(line_body.strip())
            if (line_wrap and out_line.strip()
                    and not re.match(r'^\s*(?:\{\\[^}]*\})*\s*<[a-zA-Z]', out_line)):
                out_line = f"{line_wrap[0]}{out_line.strip()}{line_wrap[2]}"
            if line_lead and not out_line.startswith(line_lead):
                out_line = line_lead + out_line
            if line_tail and not out_line.endswith(line_tail):
                out_line += line_tail
            restored.append(out_line)
        out = "\n".join(restored)
    return _strip_srt_unsafe_ass_overrides(out)


# ── ASS stil/tag temizleme ────────────────────────────────────────────────────

_ASS_OVERRIDE = re.compile(r'\{\\[^}]*\}')
_ASS_SOFTLINE = re.compile(r'\\N', re.IGNORECASE)
_ASS_HARDLINE = re.compile(r'\\n', re.IGNORECASE)
_ASS_HSPACE   = re.compile(r'\\h', re.IGNORECASE)
_ASS_COMMENT  = re.compile(r'\{=[^}]*\}')
_ASS_DRAWING_MODE = re.compile(r'\{[^}]*\\p([1-9]\d*)\b[^}]*\}', re.IGNORECASE)
_ASS_DRAWING_DATA = re.compile(
    r'^[\s,.-]*(?:[mnlbspc]\s+)?[-\d.,\s mnlbspc]+$', re.IGNORECASE)

def _clean_ass_text(text: str) -> str:
    """ASS override tag'lerini kaldır, satır kırma karakterlerini dönüştür."""
    text = _ASS_COMMENT.sub('', text)
    text = _ASS_OVERRIDE.sub('', text)
    text = _ASS_SOFTLINE.sub('\n', text)
    text = _ASS_HARDLINE.sub('\n', text)
    text = _ASS_HSPACE.sub(' ', text)
    return text.strip()


def _format_ass_text(text: str) -> str:
    """ASS satır kırma karakterlerini dönüştür ve yorumları kaldır, ancak biçim/konum etiketlerini (\\an8 vb.) koru.

    Dönüşümler yalnızca `{...}` override blokları DIŞINDA uygulanır: blok içine
    satır sonu koymak `_ASS_OVERRIDE_BLOCK_RE`'nin bloğu tanımasını bozar ve
    etiket kalıntıları teslim SRT'sine diyalog metni gibi sızar."""
    text = _ASS_COMMENT.sub('', text)

    def _convert_outside_blocks(value: str) -> str:
        parts = []
        position = 0
        for match in _ASS_OVERRIDE_BLOCK_RE.finditer(value):
            parts.append(_convert_breaks(value[position:match.start()]))
            parts.append(match.group(0))
            position = match.end()
        parts.append(_convert_breaks(value[position:]))
        return "".join(parts)

    def _convert_breaks(value: str) -> str:
        value = _ASS_SOFTLINE.sub('\n', value)
        value = _ASS_HARDLINE.sub('\n', value)
        return _ASS_HSPACE.sub(' ', value)

    return _convert_outside_blocks(text).strip()


# ASS Name/Actor sütununda konuşmacı yerine sık sık stil veya teknik etiket bulunur.
_ASS_TECHNICAL_NAMES = frozenset({
    "default", "def", "main", "alt", "alternate", "sign", "signs", "sign_text",
    "top", "bottom", "left", "right", "overlap", "staff", "caption", "captions",
    "title", "titles", "text", "comment", "note", "notes", "credit", "credits",
    "op", "ed", "opening", "ending", "karaoke", "song", "lyrics", "italics",
    "flashback", "narration", "screen", "onscreen", "on-screen", "subtitle",
    "subtitles", "dialogue", "dialog", "style", "fx", "effect", "effects",
})


def _ass_name_is_technical(name: str) -> bool:
    key = re.sub(r"[\s_\-]+", "", str(name or "").strip().casefold())
    if not key:
        return False
    if key in {re.sub(r"[\s_\-]+", "", value) for value in _ASS_TECHNICAL_NAMES}:
        return True
    # 'Sign 12', 'Default2', 'Caption-3' gibi numaralı stil türevleri
    stripped = key.rstrip("0123456789")
    return bool(stripped) and stripped != key and stripped in {
        re.sub(r"[\s_\-]+", "", value) for value in _ASS_TECHNICAL_NAMES}


def _ass_is_drawing_only(text: str) -> bool:
    if not _ASS_DRAWING_MODE.search(str(text or "")):
        return False
    visible = _clean_ass_text(text).strip("(){} ")
    return bool(visible and _ASS_DRAWING_DATA.fullmatch(visible))


_PURE_DECORATIVE_FX_WORDS = {
    "spark", "sparks", "glow", "glowing", "flash", "flare", "shimmer",
}


def _ass_is_pure_decorative_fx(style: str, raw_text: str) -> bool:
    """Yalnız görünür bir ekran sözü taşımayan dar FX süslerini ayıklar."""
    if str(style or "").strip().casefold() != "fx":
        return False
    if not _ASS_OVERRIDE.search(str(raw_text or "")):
        return False
    visible = _clean_ass_text(raw_text).casefold()
    return visible in _PURE_DECORATIVE_FX_WORDS



# ── VTT tag temizleme ─────────────────────────────────────────────────────────

_VTT_TAG = re.compile(
    r'</?(?:b|i|u|c(?:\.[^\s>]*)?|v(?:\s+[^>]*)?|lang(?:\s+[^>]*)?|ruby|rt)\s*>',
    re.IGNORECASE)
_VTT_CUE_TS_TAG = re.compile(r'<\d+:\d{2}(?::\d{2})?[.,]\d{3}>')


def _adjacent_vtt_cue_id(value: str, expected_index: int,
                         previous_id: str = "") -> bool:
    """Boş ayraç eksik VTT'de gerçek ID ile replik satırını ayır."""
    value = value.strip()
    if value.isdigit():
        return value == str(expected_index) or str(previous_id).strip().isdigit()
    if re.fullmatch(r'[A-Za-z]{2,}[A-Za-z_-]*\d+[A-Za-z0-9_.:-]*', value):
        return bool(re.match(r"(?i)(?:cue|note)[-_.:]?\d", value))
    previous = str(previous_id or "").strip()
    if not previous:
        return False
    value_tokens = {token.casefold() for token in re.findall(r"[A-Za-z]{2,}", value)}
    previous_tokens = {
        token.casefold() for token in re.findall(r"[A-Za-z]{2,}", previous)
    }
    return bool(
        value_tokens & previous_tokens
        and re.search(r"[-_.:]", value)
        and re.search(r"[-_.:]", previous)
    )

def _clean_vtt_text(text: str) -> str:
    """WebVTT inline tag'lerini ve position bilgisini kaldır."""
    text = _VTT_CUE_TS_TAG.sub('', text)
    text = _VTT_TAG.sub('', text)
    return text.strip()


# ── Parser'lar ────────────────────────────────────────────────────────────────

def parse_vtt(filepath: str) -> list:
    """WebVTT dosyasını parse eder.
    Returns: [(index_str, 'HH:MM:SS,mmm --> HH:MM:SS,mmm', text), ...]
    """
    content = read_subtitle_text(filepath)

    blocks = []
    idx = 1
    lines = content.replace('\r\n', '\n').replace('\r', '\n').splitlines()
    ts_re = re.compile(r'^\d+:\d{2}(?::\d{2})?[.,]\d+\s*-->')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith('WEBVTT'):
            i += 1
            continue
        upper = line.upper()
        if upper in {'NOTE', 'STYLE', 'REGION'} or any(
                upper.startswith(prefix + ' ') for prefix in ('NOTE', 'STYLE', 'REGION')):
            i += 1
            while i < len(lines) and lines[i].strip():
                if ts_re.match(lines[i].strip()):
                    break
                if i + 1 < len(lines) and ts_re.match(lines[i + 1].strip()):
                    break
                i += 1
            continue

        if ts_re.match(line):
            ts_idx = i
        elif i + 1 < len(lines) and ts_re.match(lines[i + 1].strip()):
            ts_idx = i + 1
        else:
            i += 1
            continue

        cue_id = line if ts_idx > i else ""
        ts_line = lines[ts_idx].strip()
        ts_parts = ts_line.split('-->')
        if len(ts_parts) < 2:
            i = ts_idx + 1
            continue
        start_raw = ts_parts[0].strip()
        end_parts = ts_parts[1].strip().split()
        if not end_parts:
            i = ts_idx + 1
            continue
        timestamp = f'{_vtt_ts_to_srt(start_raw)} --> {_vtt_ts_to_srt(end_parts[0])}'

        text_lines = []
        i = ts_idx + 1
        while i < len(lines):
            current = lines[i].strip()
            if not current:
                i += 1
                break
            if ts_re.match(current):
                break
            if i + 1 < len(lines) and ts_re.match(lines[i + 1].strip()):
                if _adjacent_vtt_cue_id(current, idx + 1, cue_id):
                    break
                text_lines.append(current)
                i += 1
                continue
            text_lines.append(current)
            i += 1
        text = '\n'.join(text_lines)
        if not _clean_vtt_text(text).strip():
            continue
        blocks.append((str(idx), timestamp, text))
        idx += 1

    return blocks


def _ass_lyric_track(style: str):
    compact = re.sub(r'[\s._-]+', '', style).casefold()
    for family in ('op', 'ed'):
        if not compact.startswith(family):
            continue
        suffix = compact[len(family):]
        if suffix in {'e', 'en', 'eng', 'english'}:
            return family, 'en'
        if suffix in {'j', 'jp', 'jpn', 'jap', 'japanese', 'romaji'}:
            return family, 'jp'
    return None


def parse_ass(filepath: str, lyric_language: str | None = None) -> list:
    """ASS/SSA dosyasını parse eder. Anlam taşıyan diyalog/ekran metnini alır,
    yalnız salt efekt, karaoke, kredi ve çevirmen notu stillerini atlar.
    Returns: [(index_str, 'HH:MM:SS,mmm --> HH:MM:SS,mmm', text), ...]
    """
    content = read_subtitle_text(filepath)

    # [Events] bölümünü gerçek section sınırlarıyla ayır; içerikteki [ karakteri
    # (ör. Comment veya diyalog metni) Format satırı aramasını kesmemeli.
    events_match = re.search(r'^\s*\[Events\]\s*$([\s\S]*?)(?=^\s*\[[^\r\n]+\]\s*$|\Z)',
                             content, re.IGNORECASE | re.MULTILINE)
    format_match = (re.search(r'^\s*Format\s*:\s*(.*?)\s*$', events_match.group(1),
                              re.IGNORECASE | re.MULTILINE)
                    if events_match else None)
    if format_match:
        cols = [c.strip().lower() for c in format_match.group(1).split(',')]
    else:
        # [Events] yok veya içinde Format satırı yok -> V4+ varsayılan
        cols = ['marked','start','end','style','name','marginl','marginr',
                'marginv','effect','text']

    try:
        start_i  = cols.index('start')
        end_i    = cols.index('end')
        style_i  = cols.index('style')
        text_i   = cols.index('text')
    except ValueError:
        return []

    name_i = cols.index('name') if 'name' in cols else None
    entries = []
    # Yalnızca salt efekt/çevirmen notu stillerini atla. Sign/Caption/Title/OP/ED
    # ve Karaoke ekrandaki anlamlı metin veya şarkı sözü taşıyabilir.
    _SKIP_STYLES = re.compile(r'^(credit|note)$', re.IGNORECASE)

    # Dialogue satırlarını yalnızca [Events] bölümünden çek.
    event_text = events_match.group(1) if events_match else content
    for line in event_text.splitlines():
        cleaned_line = line.strip()
        if not cleaned_line.lower().startswith('dialogue:'):
            continue
        # Sütunları ayır (text sütunu virgül içerebilir)
        dialogue_content = cleaned_line[9:].strip()
        parts = dialogue_content.split(',', len(cols) - 1)
        if len(parts) < len(cols):
            continue

        style = parts[style_i].strip()
        if _SKIP_STYLES.search(style):
            continue  # efekt/sign satırları çevirmeye gerek yok

        start_ts = _ass_ts_to_srt(parts[start_i])
        end_ts   = _ass_ts_to_srt(parts[end_i])
        timestamp = f'{start_ts} --> {end_ts}'
        raw_text = parts[text_i]
        if _ass_is_drawing_only(raw_text):
            continue
        if _ass_is_pure_decorative_fx(style, raw_text):
            continue
        text = _format_ass_text(raw_text)
        if not _clean_ass_text(text).strip():
            continue
        name = parts[name_i].strip() if name_i is not None else ""
        if not any(ch.isalpha() for ch in name):
            name = ""
        if _ass_name_is_technical(name):
            # Aegisub'da Name sütunu sık sık stil/teknik etiket taşır ('Default',
            # 'Sign', 'Main'). Bunlar konuşmacı değildir; ön ek olarak eklenirse
            # çevrilip 'Default: Merhaba' diye teslim SRT'sine yazılıyordu.
            name = ""
        if name and not re.match(rf'^\s*{re.escape(name)}\s*:', text, re.IGNORECASE):
            # Name sütunu konuşmacı bağlamıdır. Analize/çeviriye ulaşır; kaynak
            # güdümlü son temizlik yüklemeye hazır SRT'deki eş ön eki kaldırır.
            text = f"{name}: {text}"

        entries.append((timestamp, text, style))

    preferred_track_language = str(lyric_language or "en").strip().casefold()
    preferred_track_language = {
        "english": "en", "en-us": "en", "en-gb": "en",
        "japanese": "jp", "jpn": "jp", "ja": "jp", "romaji": "jp",
    }.get(preferred_track_language, preferred_track_language)
    if preferred_track_language not in {"en", "jp"}:
        preferred_track_language = "en"
    preferred_lyric_keys = {
        (track[0], timestamp)
        for timestamp, _, style in entries
        if (track := _ass_lyric_track(style)) and track[1] == preferred_track_language
    }
    blocks = [
        (str(i + 1), timestamp, text)
        for i, (timestamp, text, style) in enumerate(entries)
        if not (
            (track := _ass_lyric_track(style))
            and track[1] != preferred_track_language
            and (track[0], timestamp) in preferred_lyric_keys
        )
    ]

    # Zaman damgasına göre sırala (ASS dosyaları her zaman sıralı olmayabilir)
    def _ts_key(block):
        ts = block[1].split('-->')[0].strip().replace(',', '.')
        try:
            h, m, s = ts.split(':')
            return int(h) * 3600 + int(m) * 60 + float(s)
        except Exception:
            return 0.0

    blocks.sort(key=_ts_key)
    # İndeksleri yeniden numara ver
    return [(str(i + 1), ts, text) for i, (_, ts, text) in enumerate(blocks)]


def parse_any(filepath: str, lyric_language: str | None = None) -> list:
    """Uzantıya göre uygun parser'ı seçer.
    Returns: [(index_str, timestamp_str, text), ...]
    Bilinmeyen uzantı → [] döner.
    """
    ext = Path(filepath).suffix.lower()
    if ext == '.srt':
        from subtitle_localizer.srt import parse_srt
        return [
            (str(cue.index), f"{cue.start} --> {cue.end}", cue.text)
            for cue in parse_srt(read_subtitle_text(filepath))
        ]
    if ext == '.vtt':
        return parse_vtt(filepath)
    if ext in ('.ass', '.ssa'):
        return parse_ass(filepath, lyric_language=lyric_language)
    return []


def get_subtitle_files(directory: str, recursive: bool = True,
                        exclude_dir_names=("ÇIKTI", "Raporlar"),
                        exclude_suffixes=(".ham.srt",),
                        exclude_paths=(),
                        cancel_check=None) -> list:
    """Bir klasördeki tüm altyazı dosyalarını listeler (.srt, .vtt, .ass, .ssa).
    Sıra deterministik (set() kullanılmaz): aynı giriş klasörü için aynı sıra garantili.

    exclude_dir_names: taranan klasöre GÖRELİ bir alt-dizin bu adı taşıyorsa dışlanır
    (varsayılan 'ÇIKTI' — çıktı klasörü kuralı; bkz. _resolve_output_path). Taranan
    klasörün KENDİSİ bu adı taşısa bile dışlanmaz (Kural 2'de Downloads/ÇIKTI seçilebilir).
    exclude_suffixes: bu son-eklerle biten dosyalar dışlanır (varsayılan '.ham.srt' ham
    yedekleri — asla girdi olmamalı, yoksa yeniden çalıştırmada kendi çıktısını çevirir).
    Programın ürettiği aynı-klasör sonuçları, kısmi/manuel-yedek sonuçları ve gizli stage
    dosyaları da kaynak değildir; bunlar ad deseninden ayrıca dışlanır."""
    base = Path(directory)
    if not base.is_dir():
        return []

    def _path_key(value: str) -> str:
        return unicodedata.normalize("NFKD", str(value)).casefold().replace("ı", "i")

    excl_dirs = {_path_key(d) for d in (exclude_dir_names or ())}
    excl_sfx = tuple(s.lower() for s in (exclude_suffixes or ()))
    excl_paths = {
        os.path.normcase(os.path.abspath(str(path)))
        for path in (exclude_paths or ()) if str(path or "").strip()
    }
    allowed_exts = {".srt", ".vtt", ".ass", ".ssa"}
    result = []

    # Raporlar yalnizca teslim, kurtarma ve kalite yan-artifaktlarini tutar.
    if (_path_key(base.name) == _path_key("Raporlar")
            and _path_key("Raporlar") in excl_dirs):
        return []

    def _cancelled() -> bool:
        if cancel_check is None:
            return False
        try:
            return bool(cancel_check())
        except Exception:
            return True

    def _is_generated_subtitle_name(name: str) -> bool:
        low = str(name or "").lower()
        if _GENERATED_SUBTITLE_NAME_RE.search(low):
            return True
        return low.startswith(".") and low.endswith(".stage.srt")

    if recursive:
        for root, dirnames, filenames in os.walk(base):
            if _cancelled():
                return []
            if excl_dirs:
                dirnames[:] = [
                    name for name in dirnames
                    if _path_key(name) not in excl_dirs
                    and os.path.normcase(os.path.abspath(
                        str(Path(root) / name))) not in excl_paths
                ]
            for pos, name in enumerate(filenames):
                if pos % 64 == 0 and _cancelled():
                    return []
                low = name.lower()
                if Path(name).suffix.lower() not in allowed_exts:
                    continue
                if excl_sfx and low.endswith(excl_sfx):
                    continue
                if _is_generated_subtitle_name(name):
                    continue
                result.append(str(Path(root) / name))
    else:
        try:
            entries = base.iterdir()
        except OSError:
            return []
        for pos, fp in enumerate(entries):
            if pos % 64 == 0 and _cancelled():
                return []
            if not fp.is_file() or fp.suffix.lower() not in allowed_exts:
                continue
            if excl_sfx and fp.name.lower().endswith(excl_sfx):
                continue
            if _is_generated_subtitle_name(fp.name):
                continue
            result.append(str(fp))
    return sorted(result)  # alfabetik sıra — tekrarlanabilir
