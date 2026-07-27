"""
subtitle_formats.py — Çoklu altyazı formatı dönüştürücüsü.

Desteklenen formatlar: .srt, .vtt (WebVTT), .ass/.ssa (Advanced SubStation Alpha)
Her format → (index_str, timestamp_str, text) üçlülerine dönüştürülür.
"""

import glob as _glob
import re
import unicodedata
from pathlib import Path


_SOURCE_HTML_TAG = re.compile(r'</?[a-zA-Z][^>]*>')
_VTT_VOICE_TAG = re.compile(r'(?:<v(?:\s+[^>]*)?>|</v>)', re.IGNORECASE)
_SOURCE_VTT_TIMESTAMP = re.compile(r'<\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3}>')
_SOURCE_ASS_OVERRIDE = re.compile(r'\{\\[^}]*\}')
_SOURCE_EMPTY_OVERRIDE = re.compile(r'\{\}')


def clean_translation_source_text(text: str) -> str:
    """Çeviri bağlamında VTT konuşmacısını koruyup görsel etiketleri temizle."""
    text = _SOURCE_HTML_TAG.sub(
        lambda match: match.group(0)
        if _VTT_VOICE_TAG.fullmatch(match.group(0)) else "",
        str(text or ""),
    )
    text = _SOURCE_VTT_TIMESTAMP.sub("", text)
    text = _SOURCE_ASS_OVERRIDE.sub("", text)
    text = _SOURCE_EMPTY_OVERRIDE.sub("", text)
    text = re.sub(r"  +", " ", text)
    return text.strip()


# ── Toleranslı encoding çözümleme ─────────────────────────────────────────────

def normalize_srt_timestamp_separators(text: str) -> str:
    """SRT zaman satırlarındaki hatalı saat ayraçlarını düzeltir."""
    return re.sub(
        r'(?m)^([ \t]*\d{1,3})[;:](\d{2})[;:](\d{2})([,.]\d{1,3}[ \t]*'
        r'-->[ \t]*\d{1,3})[;:](\d{2})[;:](\d{2})([,.]\d{1,3}[^\n]*)$',
        r'\1:\2:\3\4:\5:\6\7',
        str(text or ""),
    )


def read_subtitle_text(filepath) -> str:
    """Altyazı dosyasını toleranslı çözümler: utf-8-sig → utf-16 (BOM) → cp1254 → latin-1(replace).

    Sıra önemli: cp1254 ve latin-1 hemen her bayt dizisini kabul eder, bu yüzden
    önce katı utf-8-sig denenir (geçerliyse doğru olan odur). cp1254 (Windows-Türkçe)
    'şğıİöçü' içeren eski Türkçe altyazıları doğru açar; latin-1 son çare (asla patlamaz).
    UTF-16 yalnızca BOM (FF FE / FE FF) varsa denenir — rastgele cp1254 baytlarını
    bozuk UTF-16 olarak yorumlamamak için."""
    raw = Path(filepath).read_bytes()
    text = None
    if raw and raw.count(b"\x00") / len(raw) >= 0.15:
        even_nuls = raw[0::2].count(0)
        odd_nuls = raw[1::2].count(0)
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
        for enc in ("cp1254",):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
    if text is None:
        text = raw.decode("latin-1", errors="replace")
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
    match = re.fullmatch(r'(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[.,](\d*)', ts)
    if not match:
        return ts
    hour, minute, second, ms = match.groups()
    return f"{int(hour or 0):02d}:{int(minute):02d}:{int(second):02d},{(ms + '000')[:3]}"

def _ass_ts_to_srt(ts: str) -> str:
    """ASS zaman damgasını (H:MM:SS.cc) SRT formatına çevirir."""
    ts = ts.strip()
    # H:MM:SS.cc → HH:MM:SS,mmm (centi-secs → milisecs)
    m = re.match(r'(\d{1,2}):(\d{2}):(\d{2})\.(\d{1,2})$', ts)
    if m:
        h, mm, s, cs = m.groups()
        ms = int(cs.ljust(2, '0')) * 10
        return f'{int(h):02d}:{mm}:{s},{ms:03d}'
    return ts


# ── Format etiketi geri yükleme ───────────────────────────────────────────────
# Çeviri öncesi kaynaktan sökülen <i>/<b>/<font>/{\an8} etiketlerini çeviri
# metnine geri uygular. Model etiketleri hiç görmez; konum ({\an8}) ve
# tam-blok/tam-satır sarmalama (italik iç ses, şarkı sözü) burada geri gelir.

_LEAD_OVERRIDE_RE = re.compile(r'^(?:\{[^}]*\})+')                       # {\an8}{\c&H..}
_TRAIL_OVERRIDE_RE = re.compile(r'(?:\{[^}]*\})+$')                     # {\i0}{\b0}


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

    src = src_text.strip()
    out = tr_text

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
            if line_lead and not out_line.startswith(line_lead):
                out_line = line_lead + out_line
            if line_tail and not out_line.endswith(line_tail):
                out_line += line_tail
            restored.append(out_line)
        out = "\n".join(restored)
    return out


# ── ASS stil/tag temizleme ────────────────────────────────────────────────────

_ASS_OVERRIDE = re.compile(r'\{\\[^}]*\}')
_ASS_SOFTLINE = re.compile(r'\\N', re.IGNORECASE)
_ASS_HARDLINE = re.compile(r'\\n', re.IGNORECASE)
_ASS_HSPACE   = re.compile(r'\\h', re.IGNORECASE)
_ASS_COMMENT  = re.compile(r'\{=[^}]*\}')

def _clean_ass_text(text: str) -> str:
    """ASS override tag'lerini kaldır, satır kırma karakterlerini dönüştür."""
    text = _ASS_COMMENT.sub('', text)
    text = _ASS_OVERRIDE.sub('', text)
    text = _ASS_SOFTLINE.sub('\n', text)
    text = _ASS_HARDLINE.sub('\n', text)
    text = _ASS_HSPACE.sub(' ', text)
    return text.strip()


def _format_ass_text(text: str) -> str:
    """ASS satır kırma karakterlerini dönüştür ve yorumları kaldır, ancak biçim/konum etiketlerini (\\an8 vb.) koru."""
    text = _ASS_COMMENT.sub('', text)
    text = _ASS_SOFTLINE.sub('\n', text)
    text = _ASS_HARDLINE.sub('\n', text)
    text = _ASS_HSPACE.sub(' ', text)
    return text.strip()



# ── VTT tag temizleme ─────────────────────────────────────────────────────────

_VTT_TAG = re.compile(
    r'</?(?:b|i|u|c(?:\.[^\s>]*)?|v(?:\s+[^>]*)?|lang(?:\s+[^>]*)?|ruby|rt)\s*>',
    re.IGNORECASE)
_VTT_CUE_TS_TAG = re.compile(r'<\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3}>')

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
    ts_re = re.compile(r'^\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3}\s*-->')
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
                i += 1
            continue

        if ts_re.match(line):
            ts_idx = i
        elif i + 1 < len(lines) and ts_re.match(lines[i + 1].strip()):
            ts_idx = i + 1
        else:
            i += 1
            continue

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
                if re.fullmatch(r'(?:\d+|[A-Za-z_-]*\d+[A-Za-z0-9_.:-]*)', current):
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


def parse_ass(filepath: str) -> list:
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

    entries = []
    # Yalnızca salt efekt/çevirmen notu stillerini atla. Sign/Caption/Title/OP/ED
    # ekrandaki anlamlı metin veya şarkı sözü taşıyabilir.
    _SKIP_STYLES = re.compile(
        r'^(fx|karaoke|credit|note)$',
        re.IGNORECASE)

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
        text = _format_ass_text(parts[text_i])
        if not _clean_ass_text(text).strip():
            continue

        entries.append((timestamp, text, style))

    english_lyric_keys = {
        (track[0], timestamp)
        for timestamp, _, style in entries
        if (track := _ass_lyric_track(style)) and track[1] == 'en'
    }
    blocks = [
        (str(i + 1), timestamp, text)
        for i, (timestamp, text, style) in enumerate(entries)
        if not (
            (track := _ass_lyric_track(style))
            and track[1] == 'jp'
            and (track[0], timestamp) in english_lyric_keys
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


def parse_any(filepath: str) -> list:
    """Uzantıya göre uygun parser'ı seçer.
    Returns: [(index_str, timestamp_str, text), ...]
    Bilinmeyen uzantı → [] döner.
    """
    ext = Path(filepath).suffix.lower()
    if ext == '.srt':
        from subtitle_translator_gui import parse_srt
        return parse_srt(filepath)
    if ext == '.vtt':
        return parse_vtt(filepath)
    if ext in ('.ass', '.ssa'):
        return parse_ass(filepath)
    return []


def get_subtitle_files(directory: str, recursive: bool = True,
                       exclude_dir_names=("ÇIKTI",),
                       exclude_suffixes=(".ham.srt",)) -> list:
    """Bir klasördeki tüm altyazı dosyalarını listeler (.srt, .vtt, .ass, .ssa).
    Sıra deterministik (set() kullanılmaz): aynı giriş klasörü için aynı sıra garantili.

    exclude_dir_names: taranan klasöre GÖRELİ bir alt-dizin bu adı taşıyorsa dışlanır
    (varsayılan 'ÇIKTI' — çıktı klasörü kuralı; bkz. _resolve_output_path). Taranan
    klasörün KENDİSİ bu adı taşısa bile dışlanmaz (Kural 2'de Downloads/ÇIKTI seçilebilir).
    exclude_suffixes: bu son-eklerle biten dosyalar dışlanır (varsayılan '.ham.srt' ham
    yedekleri — asla girdi olmamalı, yoksa yeniden çalıştırmada kendi çıktısını çevirir)."""
    exts = ('*.srt', '*.vtt', '*.ass', '*.ssa')
    seen = {}  # path → None, ekleme sırasını korur (dict insertion order)
    base = Path(directory)
    for ext in exts:
        iterator = base.rglob(ext) if recursive else base.glob(ext)
        for fp in iterator:
            seen[str(fp)] = None
    def _path_key(value: str) -> str:
        return unicodedata.normalize("NFKD", str(value)).casefold().replace("ı", "i")
    excl_dirs = {_path_key(d) for d in (exclude_dir_names or ())}
    excl_sfx = tuple(s.lower() for s in (exclude_suffixes or ()))
    result = []
    for fp in seen:
        low = fp.lower()
        if excl_sfx and low.endswith(excl_sfx):
            continue
        if excl_dirs:
            try:
                rel = Path(fp).relative_to(base)
                dir_parts = {_path_key(p) for p in rel.parts[:-1]}  # sadece dizin bileşenleri
            except Exception:
                dir_parts = set()
            if dir_parts & excl_dirs:
                continue
        result.append(fp)
    return sorted(result)  # alfabetik sıra — tekrarlanabilir
