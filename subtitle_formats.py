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


# WebVTT/SRT'de GERÇEKTEN desteklenen biçim etiketleri. Eskiden desen
# `</?[a-zA-Z][^>]*>` idi, yani harfle başlayan HER `<...>` parçası etiket
# sayılıyordu: 'Press <Enter> now.', 'The variable <x>' ve
# '<PRIVATE_PERSON>' gibi anlam taşıyan kaynak metin API'ye gitmeden
# siliniyordu (denetim 2026-08-21, madde 2). Artık yalnız bu allowlist
# temizlenir; bilinmeyen `<...>` parçaları veri olarak korunur.
_SOURCE_HTML_TAG = re.compile(
    r'</?\s*(?:i|b|u|s|em|strong|font|ruby|rt|rp|v|c|lang|br|span)(?:[.\s][^>]*)?\s*/?>',
    re.IGNORECASE,
)
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
# Programın kendi ara/yedek dosyaları: adı tek başına KESİN kanıttır.
_INTERNAL_ARTIFACT_NAME_RE = re.compile(
    r'(?:\.partial|\.wave[12]of2)\.srt$|\.bak\.srt$|\.ham\.srt$',
    re.IGNORECASE,
)
# Belirsiz adlar: '.tr.srt' aynı zamanda internetten indirilmiş meşru bir
# Türkçe altyazının en yaygın dil etiketidir; '.vtt.srt'/'.ass.srt' ise
# aynı-klasör modunda programın VTT/ASS çıktısının adıdır. İkisi de ancak
# KOMŞU KAYNAK kanıtıyla program çıktısı sayılır (denetim 2026-08-21,
# madde 13 ve 30): kanıt yoksa dosya normal bir kaynaktır.
_AMBIGUOUS_TR_NAME_RE = re.compile(r'^(?P<stem>.+)\.tr\.srt$', re.IGNORECASE)
_AMBIGUOUS_FORMAT_NAME_RE = re.compile(
    r'^(?P<stem>.+)\.(?P<ext>vtt|ass|ssa)\.srt$', re.IGNORECASE)
_SOURCE_EXTENSIONS = (".srt", ".vtt", ".ass", ".ssa")
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
    # CP1254'ün CP1252'den TEK farkı bu altı yuvadır (ğĞıİşŞ). Türkçe bir
    # kaynakta bunlar varken rakip kodlamalar aynı baytları tipografik
    # işaretlere çeviriyor ve skorda öne geçebiliyordu: kısa dosyada
    # 'İyi günler' → '›yi g¸nler' (denetim 2026-08-21, madde 24).
    # 'ç/ö/ü' KASITLI olarak listede yok: onlar CP1252 ile ortak, yani
    # Almanca/Fransızca metinde ayırt edici değil.
    "cp1254": set("\u011f\u011e\u0131\u0130\u015f\u015e"),
}
# Aralık işareti/aksan taşıyıcısı gibi karakterler gerçek altyazı metninde
# bulunmaz; yanlış kodlama seçildiğinin güçlü işaretidir.
_LEGACY_IMPLAUSIBLE_CHARS = frozenset(
    "\u02c6\u02dc\u02d8\u02d9\u02da\u02db\u02dd\u00b8\u00a8"
    "\u00af\u00b4\u2039\u203a\u00a4\u00a6\u00ac\u00b1")


# WebVTT ruby: `<rt>` OKUNUŞ alt ağacıdır, ana metnin telaffuzunu gösterir.
# Yalnız etiket kabuğu silindiği için okunuş ana sözcüğe yapışıyor ve
# modele '漢kan' gibi tek bozuk kelime gidiyordu (denetim 2026-08-21,
# madde 39). `<rp>` de yalnız parantez süsüdür.
_VTT_RUBY_READING_RE = re.compile(
    r'<\s*(rt|rp)\b[^>]*>.*?<\s*/\s*\1\s*>|<\s*(?:rt|rp)\b[^>]*>',
    re.IGNORECASE | re.DOTALL,
)


# `<br>` ve inline VTT zaman etiketi GÖRSEL kabuk değil, iki metin parçası
# arasındaki gerçek SINIRDIR. Boş dizeyle silinince komşu sözcükler
# birleşiyor ve modele 'Waithere' gidiyordu (devam denetimi, madde 1).
_SOURCE_LINE_BREAK_TAG = re.compile(r'<\s*br\s*/?\s*>', re.IGNORECASE)
_SOURCE_INLINE_VTT_TS = re.compile(r'<\d{1,2}:\d{2}(?::\d{2})?[.,]\d{1,3}>')
_WORDLIKE_CHAR_RE = re.compile(r"[^\W_]", re.UNICODE)


def _replace_word_separators(text: str) -> str:
    """Ayırıcı etiketleri boşluğa çevirir; sahte boşluk üretmez.

    `<br>` her wrap modunda gerçek satır sonudur, hep ayırır. Inline VTT
    zaman etiketi ise karaoke zamanlamasıdır: yalnız İKİ SÖZCÜĞÜN arasında
    duruyorsa ayırır, `<v Roger><00:00:01.500>Choose` gibi bir etiketin
    hemen ardındaysa boşluk eklemez."""
    value = _SOURCE_LINE_BREAK_TAG.sub(" ", str(text or ""))

    def _timestamp(match):
        before = value[match.start() - 1] if match.start() else ""
        after = value[match.end()] if match.end() < len(value) else ""
        if (before and after
                and _WORDLIKE_CHAR_RE.match(before)
                and _WORDLIKE_CHAR_RE.match(after)):
            return " "
        return ""

    return _SOURCE_INLINE_VTT_TS.sub(_timestamp, value)


# Cümle sonu tespiti: kapanış işaretleri SOYULDUKTAN SONRA kalan boşluk da
# temizlenmeli. Eskiden iki ayrı ikiz vardı (GUI döngülü/doğru, hybrid tek
# geçişli) ve '"Welcome to Miami Beach. "' gibi 'nokta + boşluk + tırnak'
# biçiminde farklı cevap veriyorlardı; hybrid tarafı cümleyi bitmemiş sayıp
# iki ayrı cümleyi tek `sentence_groups` girdisinde birleştiriyordu — model de
# tamamlanmış cümleyi bilerek yarım bırakıyordu (bug taraması madde 18/32).
SENTENCE_CLOSERS = ")]}\"'»”’›"
SENTENCE_ENDERS = ".!?…"


def ends_sentence(text) -> bool:
    """Metin cümle bitiren noktalamayla mı bitiyor? (kapanış işaretleri dâhil)"""
    value = str(text or "").strip()
    while True:
        trimmed = value.rstrip(SENTENCE_CLOSERS).rstrip()
        if trimmed == value:
            break
        value = trimmed
    return bool(value) and value[-1] in SENTENCE_ENDERS


# ── Türkçe 2. tekil hitap eki morfolojisi ────────────────────────────────────
# Tek kaynak: GUI teslim taraması (detect_address_register_mix) ve hybrid
# tutarlılık taraması (_turkish_second_person_register) aynı kuralı
# kullanmalı. İkisi de ekleri gövdeden ayırmadığı için 3. tekil istek kipini
# ('olsun', 'gelsin') ve tamlayan ekini ('herkesin', 'kentin') 'sen' sayıyordu
# (bug taraması madde 29/30/33).
TR_VOICELESS_STOPS = "pçtkfhsş"
TR_TENSE_MARKERS = (
    "yor", "acak", "ecek", "mış", "miş", "muş", "müş",
    "ar", "er", "ır", "ir", "ur", "ür", "maz", "mez",
    "malı", "meli", "abilir", "ebilir",
)
# Yapısal kuralların eleyemediği, gerçek teslim dosyalarında ölçülen kalıntı.
TR_ADDRESS_FALSE_STEMS = frozenset({
    "resin", "esin", "kesin", "basın", "yasin", "hüsün", "üstün", "bütün",
    "düşün", "görüşün", "yazın", "kışın", "yarısın",
    "kadın", "aydın", "günaydın", "vücudun", "gidin", "affedin", "edin",
    "odun", "düğün", "üzüldün",
})
_TR_SIN_RE = re.compile(
    r"(?<!\w)([^\W\d_]{2,}?)(sın|sin|sun|sün)(?!\w)", re.IGNORECASE)
_TR_DIN_RE = re.compile(
    r"(?<!\w)([^\W\d_]+?)([dt])(ın|in|un|ün)(?!\w)", re.IGNORECASE)


def is_turkish_second_person_token(token) -> bool:
    """Bu tek sözcük 2. TEKİL hitap eki mi taşıyor?

    -sIn yalnız bir kip/zaman işaretinden sonra 2. tekildir (geliyorsun,
    gelirsin); çıplak köke gelen -sIn istek kipidir (olsun, gelsin).
    -DIn'de ünsüz uyumu aranır: -tIn yalnız sert ünsüzden sonra gelebilir,
    böylece 'kent+in', 'hayat+ın', 'sa+tın' elenir, 'yap+tın' korunur.
    """
    word = str(token or "")
    if not word or word.casefold() in TR_ADDRESS_FALSE_STEMS:
        return False
    match = _TR_SIN_RE.fullmatch(word)
    if match:
        stem = match.group(1).casefold()
        # Kısa fiil kökleri kısa aorist işaretiyle çakışıyor ('dur+sun',
        # 'ver+sin' istek kipidir): gövde işaretten belirgin ölçüde uzun olmalı.
        return any(
            stem.endswith(marker) and len(stem) >= len(marker) + 2
            for marker in TR_TENSE_MARKERS)
    match = _TR_DIN_RE.fullmatch(word)
    if match:
        stem = match.group(1).casefold()
        consonant = match.group(2).casefold()
        if not stem:
            return False
        previous = stem[-1]
        if consonant == "t":
            return previous in TR_VOICELESS_STOPS
        return previous not in TR_VOICELESS_STOPS
    return False

def clean_translation_source_text(text: str) -> str:
    """Çeviri bağlamında VTT konuşmacısını koruyup görsel etiketleri temizle."""
    text = _VTT_RUBY_READING_RE.sub("", str(text or ""))
    # Ayırıcılar ÖNCE boşluğa çevrilir; görsel kabuk temizliği sonra gelir.
    text = _replace_word_separators(text)
    text = _SOURCE_MALFORMED_FORMAT_TAG.sub("", text)
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

def _srt_fraction_to_millis(fraction: str) -> str:
    """Kesir alanını üç haneli milisaniyeye indirger.

    Kural DETERMİNİSTİK: eksikse '000', kısaysa sağdan sıfırla tamamlanır,
    4+ haneyse İLK ÜÇ hane alınır (mikro saniyeli araç çıktıları).
    """
    digits = str(fraction or "")
    if not digits:
        return "000"
    return (digits + "000")[:3]


def normalize_srt_timestamp_separators(text: str) -> str:
    """SRT zaman satırlarındaki hatalı ayraçları ve milisaniyeleri düzeltir.

    Kesir alanı OPSİYONELDİR: '00:00:01 --> 00:00:03' ve mikro saniyeli
    '00:00:01,123456' biçimleri eskiden hiç cue üretmiyor, dosya boş
    sanılıyordu (denetim 2026-08-21, madde 25). Tolerans yalnız İKİ UCU da
    tam 'HH:MM:SS' olan satırlara uygulanır."""
    pattern = re.compile(
        r'(?m)^([ \t]*)(\d+)[;:](\d{2})[;:](\d{2})(?:[,.](\d+))?([ \t]*'
        r'-->[ \t]*)(\d+)[;:](\d{2})[;:](\d{2})(?:[,.](\d+))?([^\n]*)$'
    )

    def replace(match):
        lead, sh, sm, ss, sms, arrow, eh, em, es, ems, tail = match.groups()
        # Saat 2 haneye tamamlanmalı: '0:01:23,456' biçimini donanımsal oynatıcılar
        # ve bazı yazılımlar yüklemiyor.
        return (
            f"{lead}{int(sh):02d}:{sm}:{ss},{_srt_fraction_to_millis(sms)}"
            f"{arrow}{int(eh):02d}:{em}:{es},"
            f"{_srt_fraction_to_millis(ems)}{tail}"
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


_SHORT_CJK_ENCODINGS = ("cp932", "gb18030", "gbk", "big5", "cp949", "euc_jp",
                        "euc_kr")
_SHORT_CJK_MIN_SCRIPT_RATIO = 0.9


def _decode_short_cjk(raw: bytes) -> str | None:
    """80 bayttan kısa CJK altyazıyı tek-baytlı Batı kodlamalarından önce dener.

    Kısa dosya kısayolu yalnız cp125x ailesini deniyordu; geçerli 35-37 baytlık
    CP932/GBK dosyaları CP1254 mojibake'i olarak okunuyordu (denetim 2026-08-20,
    madde 22). Ölçüt çok dar: çözülen metnin harflerinin en az %90'ı o kodlamanın
    kendi yazı sisteminde olmalı — Latin/Türkçe metin bu eşiğe hiç yaklaşmaz."""
    if not raw or not any(byte > 0x7F for byte in raw):
        return None
    best = None
    for encoding in _SHORT_CJK_ENCODINGS:
        try:
            text = raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
        letters = [char for char in text if char.isalpha()]
        if not letters:
            continue
        ratio = _legacy_script_ratio(text, encoding)
        if ratio < _SHORT_CJK_MIN_SCRIPT_RATIO:
            continue
        cjk = sum(
            "぀" <= char <= "ヿ" or "㐀" <= char <= "鿿"
            or "가" <= char <= "힯" for char in letters)
        if not cjk:
            continue
        # Kana üreten çözüm Japonca kanıtıdır; Korece/Çince baytları kana
        # üretmez. Aksi hâlde tek karakterlik CJK dosyalarında sıra rastgele.
        kana = sum("぀" <= char <= "ヿ" for char in letters)
        score = (1 if kana else 0, ratio, cjk)
        if best is None or score > best[0]:
            best = (score, text)
    return best[1] if best else None


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
        suspicious += sum(ch in _LEGACY_IMPLAUSIBLE_CHARS for ch in text)
        candidates.append(((common_ratio * 0.2) + (bigram_ratio * 1.2)
                            + (script_ratio * 0.15) + distinctive_bonus
                            - (suspicious * 0.75), text))
    if not candidates:
        return None
    score, text = max(candidates, key=lambda item: item[0])
    if score >= 0.45:
        return text
    # Batı adayları eşiği tutmuyorsa CJK dene: gerçek cp125x metinleri 0.59+
    # alırken CJK dosyalarının batı skoru 0.21-0.35'te kalıyor (ölçüldü).
    return _decode_short_cjk(raw)


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


# cp1252'de tipografik kesme/tirnak olan C1 baytlari; MacRoman'da ayni
# baytlar aksanli harftir ('\x92' -> 'i').
_CP1252_APOSTROPHE_CONTROLS = frozenset("\x91\x92")
# Kesmeden sonra gelebilecek Ingilizce kisaltma ekleri.
_ENGLISH_CONTRACTION_TAILS = frozenset(
    ("s", "t", "d", "m", "ll", "re", "ve"))


def _cp1252_punctuation_in_context(text: str, pos: int) -> bool:
    """Bu C1 bayti cp1252 noktalamasi mi, MacRoman aksanli harfi mi?

    Iki sinyal ayirt eder: (1) bayt iki harfin ARASINDA degilse noktalamadir
    (MacRoman aksani kelime icinde durur), (2) kesme bayti ise ardindan gelen
    kelime sonu Ingilizce kisaltma ekiyse ('It\u2019s', 'Don\u2019t') yine
    noktalamadir. 'Rodr\\x92guez' ikisini de gecemez ve MacRoman'a birakilir."""
    char = text[pos]
    before = text[pos - 1] if pos > 0 else ""
    after = text[pos + 1] if pos + 1 < len(text) else ""
    if not (before.isalpha() and after.isalpha()):
        return True
    if char not in _CP1252_APOSTROPHE_CONTROLS:
        return False
    tail = ""
    for ch in text[pos + 1:]:
        if not ch.isalpha():
            break
        tail += ch
        if len(tail) > 2:
            return False
    return tail.casefold() in _ENGLISH_CONTRACTION_TAILS


def _repair_embedded_mac_roman_controls(text: str) -> str:
    """Latin-1 fallback'inde kontrol karakterine dönüşmüş baytları geri kazanır.

    Bu baytlar İngilizce/Batı Avrupa altyazılarında çoğunlukla Windows-1252
    noktalama işaretleridir (“ ” ’ – — …); koşulsuz MacRoman uygulamak onları
    anlamsız 'ì', 'î', 'Ö' harflerine çeviriyordu. Ayırt edici sinyal konumdur:
    MacRoman'da bu baytlar kelime İÇİNDEKİ aksanlı harflerdir (Rodr•guez), cp1252
    noktalamasıysa ağırlıklı olarak kelime sınırlarında durur."""
    # Eskiden esik 2'ydi: tek bir \x92 tasiyan "It\x92s here." hic onarilmadan
    # ham C1 kontrol karakteriyle altyaziya yaziliyordu (Part 2, madde 24).
    controls = [pos for pos, ch in enumerate(text) if "\x80" <= ch <= "\x9f"]
    if not controls:
        return text
    # Yalniz cp1252 NOKTALAMA baytlari varsa karar nettir; konum sezgisine
    # basvurma. MacRoman'da ayni baytlar aksanli HARFtir ve "It's" -> "Itis"
    # gibi bozulma uretir.
    if all(_cp1252_punctuation_in_context(text, pos) for pos in controls):
        cp1252_only = _decode_embedded_controls(text, "cp1252")
        if cp1252_only is not None:
            return cp1252_only
    base_penalty = _legacy_decode_penalty(text)
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


# Bu üç karakter ARTEFAKT DEĞİL, anlam taşır:
#   U+200D ZWJ   — emoji dizisini tek gliften yapar (👩‍👩‍👧‍👦),
#   U+200C ZWNJ  — Farsça/Arapça/Hintçe yazımında harf birleşimini keser,
#   U+2066-2069  — bidi isolate; RTL metindeki Latin ad/sayının görsel
#                  sırasını korur.
# Hepsi hedef dilden bağımsız siliniyordu: aile emojisi dört ayrı glife
# düşüyor, Arapça altyazıda Latin isimlerin sırası bozulabiliyordu
# (denetim 2026-08-21, madde 5). Artık BAĞLAMA bakılır.
_JOINER_CHARS = frozenset("\u200c\u200d")
_BIDI_ISOLATE_CHARS = frozenset("\u2066\u2067\u2068\u2069")
_LATIN_LETTER_RE = re.compile(r"[A-Za-z\u00c0-\u024f]")


def _joiner_is_meaningful(value: str, position: int) -> bool:
    """ZWJ/ZWNJ burada gerçek bir birleştirici mi?

    Latin harfleri ARASINDA duruyorsa kopyala-yapıştır artefaktıdır ve
    silinir (eski davranış). Emoji/sembol ya da Latin dışı yazı arasında
    duruyorsa anlam taşır ve korunur."""
    before = value[position - 1] if position > 0 else ""
    after = value[position + 1] if position + 1 < len(value) else ""
    if not before or not after:
        return False
    if _LATIN_LETTER_RE.match(before) and _LATIN_LETTER_RE.match(after):
        return False
    return True


def normalize_subtitle_control_artifacts(text: str) -> str:
    """Repair model-emitted NUL+hex escapes and remove other C0 controls.

    Ayrıca sıfır-genişlik/BOM/yön işareti gibi görünmez biçim karakterlerini SİLER
    ve alışılmadık boşlukları normal boşluğa indirger. ZWJ/ZWNJ ve bidi
    isolate işaretleri anlam taşıdıkları bağlamda KORUNUR."""
    value = _NUL_HEX_ARTIFACT_RE.sub(
        lambda match: chr(int(match.group(1), 16)), str(text or ""))
    out = []
    for position, char in enumerate(value):
        if char in _BIDI_ISOLATE_CHARS:
            out.append(char)
            continue
        if char in _JOINER_CHARS:
            if _joiner_is_meaningful(value, position):
                out.append(char)
            continue
        if char in _INVISIBLE_FORMAT_CHARS:
            continue
        if char in _UNUSUAL_SPACE_CHARS:
            out.append(" ")
            continue
        out.append(char if ord(char) >= 32 or char in "\n\r\t" else " ")
    return "".join(out)


_NUL_BYTE = bytes([0])


def _looks_like_subtitle_text(value: str) -> bool:
    """Çözülen metin gerçekten altyazı mı? (kodlama tahminini doğrulamak için)"""
    head = str(value or "")[:8192]
    return "-->" in head or "Dialogue:" in head or "[Script Info]" in head


def _bom_less_utf16_lane_signature(sample: bytes) -> bool:
    """Bir bayt şeridinde NUL yığılması, diğerinde neredeyse hiç yoksa True.

    UTF-16'nın imzası budur ve metnin dilinden bağımsızdır; toplam NUL oranı
    ise Latin dışı alfabelerde çöker (CJK örneğinde %11).
    """
    even = sample[0::2]
    odd = sample[1::2]
    if not even or not odd:
        return False
    even_ratio = even.count(0) / len(even)
    odd_ratio = odd.count(0) / len(odd)
    strong, weak = max(even_ratio, odd_ratio), min(even_ratio, odd_ratio)
    return strong >= 0.08 and weak <= strong / 4


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
    if text is None and sample:
        even_nuls = sample[0::2].count(0)
        odd_nuls = sample[1::2].count(0)
        enc = "utf-16-be" if even_nuls > odd_nuls else "utf-16-le"
        if sample.count(_NUL_BYTE) / len(sample) >= 0.15:
            try:
                text = raw.decode(enc)
            except UnicodeDecodeError:
                text = None
        elif _bom_less_utf16_lane_signature(sample):
            # Toplam NUL oranı BOM'suz UTF-16 için güvenilir bir ölçü değil:
            # Çince/Japonca/Korece/Arapça metnin KENDİSİ NUL üretmez, yalnız
            # zaman damgaları üretir; oran %11'e düşüp eşiği geçemiyor ve
            # dosya sessizce mojibake oluyordu (denetim Tur 4, madde 8).
            # Şerit asimetrisi dilden bağımsızdır — ama tek başına da
            # yanılabilir, bu yüzden çözülen metin altyazıya benzemiyorsa
            # tahmin kabul edilmez ve eski zincir işlemeye devam eder.
            try:
                candidate = raw.decode(enc)
            except UnicodeDecodeError:
                candidate = None
            if candidate and _looks_like_subtitle_text(candidate):
                text = candidate
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
    match = re.fullmatch(r'(?:(\d+):)?(\d{1,2}):(\d{2})(?:[.,](\d*))?', ts)
    if not match:
        return ts
    hour, minute, second, ms = match.groups()
    ms = ms or ''
    return f"{int(hour or 0):02d}:{int(minute):02d}:{int(second):02d},{(ms + '000')[:3]}"

# HLS/WebVTT'de cue zamanları YEREL, video zamanı MPEG-TS tabanlıdır.
# `X-TIMESTAMP-MAP=LOCAL:...,MPEGTS:...` bu ikisini bağlar ve hiç
# okunmuyordu: HLS segmentinden gelen altyazı videonun gerçek timeline'ına
# oturmuyordu (denetim 2026-08-21, madde 15). MPEGTS saati 90 kHz'dir.
_MPEGTS_HZ = 90000.0
_MPEGTS_WRAP = 1 << 33  # 33-bit sayaç
_VTT_TIMESTAMP_MAP_RE = re.compile(
    r'X-TIMESTAMP-MAP\s*=\s*(?P<body>[^\r\n]+)', re.IGNORECASE)


def _vtt_ts_to_seconds(ts: str):
    """WebVTT zaman damgasını saniyeye çevirir; çözülemezse None."""
    match = re.fullmatch(r'(?:(\d+):)?(\d{1,2}):(\d{2})(?:[.,](\d*))?',
                         str(ts or "").strip())
    if not match:
        return None
    hour, minute, second, ms = match.groups()
    ms = ms or ''
    return (int(hour or 0) * 3600 + int(minute) * 60 + int(second)
            + int((ms + '000')[:3]) / 1000.0)


def _seconds_to_srt_ts(seconds: float) -> str:
    total_ms = max(0, int(round(float(seconds) * 1000)))
    hours, remainder = divmod(total_ms, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def parse_vtt_timestamp_map(content: str) -> float:
    """`X-TIMESTAMP-MAP` başlığından saniye cinsinden medya ofseti.

    Ofset = MPEGTS/90000 - LOCAL. Başlık yoksa ya da çözülemezse 0.0."""
    match = _VTT_TIMESTAMP_MAP_RE.search(str(content or ""))
    if not match:
        return 0.0
    local_seconds = 0.0
    mpegts_ticks = None
    for part in match.group("body").split(","):
        key, sep, value = part.partition(":")
        if not sep:
            continue
        key = key.strip().upper()
        value = value.strip()
        if key == "LOCAL":
            parsed = _vtt_ts_to_seconds(value)
            if parsed is not None:
                local_seconds = parsed
        elif key == "MPEGTS":
            try:
                mpegts_ticks = int(value)
            except ValueError:
                mpegts_ticks = None
    if mpegts_ticks is None:
        return 0.0
    # Sayaç 33 bitte sarar; negatif/aşırı değerleri aralığa indir.
    mpegts_ticks %= _MPEGTS_WRAP
    return (mpegts_ticks / _MPEGTS_HZ) - local_seconds


# ASS/SSA `[Script Info] Timer` script saatinin YÜZDE hız çarpanıdır
# (100.0000 = normal). Hiç okunmuyordu: Timer'ı 100 olmayan dosyalarda
# bütün altyazı zamanları film boyunca sistematik kayıyordu (denetim
# 2026-08-21, madde 19). Kaynak ve hedef aynı parser çıktısını kullandığı
# için iç kayma denetimi bunu göremiyordu.
_ASS_TIMER_RE = re.compile(
    r'^\s*Timer\s*:\s*([0-9]+(?:[.,][0-9]+)?)\s*$',
    re.IGNORECASE | re.MULTILINE)


def parse_ass_timer_scale(content: str) -> float:
    """`Timer` yüzdesinden medya zamanı katsayısı (100/Timer).

    Eksik, sıfır, negatif veya çözülemez değer güvenle 1.0 kabul edilir.
    Ondalık ayracı locale'e göre ',' olabilir."""
    match = _ASS_TIMER_RE.search(str(content or ""))
    if not match:
        return 1.0
    try:
        timer = float(match.group(1).replace(",", "."))
    except ValueError:
        return 1.0
    if timer <= 0:
        return 1.0
    return 100.0 / timer


def _ass_ts_to_seconds(ts: str):
    """ASS zaman damgasını saniyeye çevirir; çözülemezse None."""
    match = re.fullmatch(r'\s*(\d+):(\d{1,2}):(\d{1,2})[.,](\d+)\s*',
                         str(ts or ""))
    if not match:
        return None
    hour, minute, second, fraction = match.groups()
    if len(fraction) == 2:
        millis = int(fraction) * 10
    else:
        millis = int((fraction + "000")[:3])
    return (int(hour) * 3600 + int(minute) * 60 + int(second)
            + millis / 1000.0)


# ASS alpha kanalı: `&HFF` TAMAMEN saydamdır. Parser stil tablosunu hiç
# okumuyor, inline `{\alpha&HFF&}` bloğunu da yalnız silip metni
# bırakıyordu; kaynakta bilerek görünmeyen teknik/maskeleme metinleri
# çeviriye ve teslim SRT'sine geçiyordu (madde 20).
_ASS_ALPHA_OVERRIDE_RE = re.compile(
    r'\\(?:1?a|alpha)\s*&H([0-9A-Fa-f]{1,2})&', re.IGNORECASE)
# ADI ÇAKIŞMASIN: aşağıda aynı adla başka bir desen daha var (yalnız
# ters-bölüyle başlayan override blokları) ve bu tanımı gölgeliyordu.
_ASS_ALPHA_BLOCK_RE = re.compile(r'\{([^{}]*)\}')
_ASS_STYLE_SECTION_RE = re.compile(
    r'\[V4\+? Styles\](.*?)(?:\n\s*\[|\Z)', re.S | re.IGNORECASE)


def parse_ass_invisible_styles(content: str) -> set:
    """PrimaryColour alpha'sı tamamen saydam olan stil adları."""
    section = _ASS_STYLE_SECTION_RE.search(str(content or ""))
    if not section:
        return set()
    columns = None
    invisible = set()
    for line in section.group(1).splitlines():
        stripped = line.strip()
        low = stripped.lower()
        if low.startswith("format:"):
            columns = [part.strip().lower()
                       for part in stripped[7:].split(",")]
            continue
        if not low.startswith("style:") or not columns:
            continue
        values = [part.strip() for part in stripped[6:].split(",")]
        if len(values) < len(columns):
            continue
        row = dict(zip(columns, values))
        colour = row.get("primarycolour") or ""
        digits = re.fullmatch(r'&H([0-9A-Fa-f]{1,8})&?', colour.strip())
        if not digits:
            continue
        value = digits.group(1)
        # &HAABBGGRR — alpha en anlamlı iki hanedir; 8 haneden kısaysa
        # alpha verilmemiş demektir (görünür).
        if len(value) == 8 and value[:2].upper() == "FF":
            invisible.add(row.get("name", "").strip())
    invisible.discard("")
    return invisible


def ass_visible_text(raw_text: str) -> str:
    """Inline alpha override'larına göre GÖRÜNÜR kalan metni döner.

    `\\alpha&HFF&gizli\\alpha&H00&görünür` → `görünür`. Alpha animasyonu
    (`\\t(...)`) çözülemez; o durumda metin olduğu gibi korunur.
    """
    value = str(raw_text or "")
    if "\\t(" in value.replace(" ", ""):
        return value
    if not _ASS_ALPHA_OVERRIDE_RE.search(value):
        return value
    out = []
    hidden = False
    position = 0
    for match in _ASS_ALPHA_BLOCK_RE.finditer(value):
        segment = value[position:match.start()]
        if not hidden:
            out.append(segment)
        alpha = None
        for alpha_match in _ASS_ALPHA_OVERRIDE_RE.finditer(match.group(1)):
            alpha = alpha_match.group(1)
        if alpha is not None:
            hidden = alpha.upper().zfill(2) == "FF"
        if not hidden:
            out.append(match.group(0))
        position = match.end()
    if not hidden:
        out.append(value[position:])
    return "".join(out)


def _ass_ts_to_srt(ts: str) -> str:
    """ASS zaman damgasını (H:MM:SS.cc) SRT formatına çevirir.

    Standart ASS santisaniye kullanır ama bazı araçlar 3 haneli milisaniye yazar;
    o dosyalarda eskiden ham '1:23:45.678' değeri SRT'ye olduğu gibi geçiyordu."""
    ts = ts.strip()
    # H:MM:SS.cc → HH:MM:SS,mmm (centi-secs → milisecs)
    # 4+ haneli mikro-saniye taşıyan araçlar da var; eskiden regex hiç
    # eşleşmeyip HAM geçersiz metin SRT'ye yazılıyordu (Part 2, madde 46).
    m = re.match(r'(\d{1,2}):(\d{2}):(\d{2})\.(\d+)$', ts)
    if m:
        h, mm, s, frac = m.groups()
        if len(frac) == 2:
            ms = int(frac) * 10          # santisaniye (standart ASS)
        elif len(frac) == 1:
            ms = int(frac) * 100
        else:
            ms = int(frac[:3])           # 3+ hane: ilk üçü milisaniyedir
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


# WebVTT'nin izin verdiği adlandırılmış karakter referansları. Parser bunları
# hiç çözmüyordu: model gerçek '&' yerine '&amp;' görüyor, teslim SRT'sinde
# de literal kalabiliyordu (denetim 2026-08-21, madde 9). Bilinmeyen
# varlıklar ('&filmname;') olduğu gibi KORUNUR.
_VTT_ENTITIES = {
    "amp": "&", "lt": "<", "gt": ">", "quot": '"',
    "apos": "'", "nbsp": "\u00a0", "lrm": "\u200e",
    "rlm": "\u200f", "hellip": "\u2026", "mdash": "\u2014",
    "ndash": "\u2013", "ldquo": "\u201c", "rdquo": "\u201d",
    "lsquo": "\u2018", "rsquo": "\u2019", "laquo": "\u00ab",
    "raquo": "\u00bb", "deg": "\u00b0", "eacute": "\u00e9",
}
_VTT_ENTITY_RE = re.compile(
    r"&(#[xX][0-9a-fA-F]+|#\d+|[A-Za-z][A-Za-z0-9]*);")
# Unicode surrogate aralığı ve noncharacter değerleri GEÇERLİ scalar değil:
# `chr(0xD800)` bir Python str üretir ama UTF-8'e yazılamaz ve nihai SRT
# yazımını, logu, JSONL'i kırar (devam denetimi, madde 3).
_UNICODE_NONCHARACTERS = frozenset(
    list(range(0xFDD0, 0xFDF0))
    + [plane * 0x10000 + offset
       for plane in range(17) for offset in (0xFFFE, 0xFFFF)]
)


def _valid_entity_codepoint(code: int) -> bool:
    """WebVTT/HTML karakter referansı geçerli bir Unicode scalar mı?"""
    if code <= 0 or code > 0x10FFFF:
        return False
    if 0xD800 <= code <= 0xDFFF:
        return False  # surrogate
    if code in _UNICODE_NONCHARACTERS:
        return False
    if code < 0x20 and chr(code) not in "\t\n\r":
        return False  # C0 kontrol
    if 0x7F <= code <= 0x9F:
        return False  # DEL ve C1 kontrol
    return True


def decode_vtt_entities(text: str) -> str:
    """WebVTT karakter referanslarını çözer; bilinmeyenleri korur.

    `&lt;`/`&gt;` çözülünce ETİKET GİBİ duran bir yapı oluşuyorsa
    (`&lt;i&gt;` → `<i>`) o iki referans kodlu bırakılır: sonraki temizlik
    katmanı onu gerçek biçim etiketi sanıp yazarın ekranda göstermek
    istediği metni silerdi."""
    def _replace(match):
        body = match.group(1)
        if body.startswith("#"):
            try:
                code = (int(body[2:], 16) if body[1:2].lower() == "x"
                        else int(body[1:]))
            except ValueError:
                return match.group(0)
            if _valid_entity_codepoint(code):
                return chr(code)
            # Geçersiz scalar: kaynağı bozmadan olduğu gibi bırak.
            return match.group(0)
        return _VTT_ENTITIES.get(body.casefold(), match.group(0))

    decoded = _VTT_ENTITY_RE.sub(_replace, str(text or ""))
    if _SOURCE_HTML_TAG.search(decoded) and not _SOURCE_HTML_TAG.search(
            str(text or "")):
        # Etiket YALNIZ çözümden doğduysa açı parantezlerini geri kodla.
        decoded = _VTT_ENTITY_RE.sub(
            lambda match: (match.group(0)
                           if match.group(1).casefold() in ("lt", "gt")
                           else _replace(match)),
            str(text or ""))
    return decoded


# SRT teslimlerinde GERÇEKTEN desteklenen sarmalama etiketleri. Eskiden desen
# `<[a-zA-Z][^>]*>` idi, yani kaynaktaki HERHANGİ bir etiket ('<blink>',
# '<script>') çeviriye geri sarılıp teslim dosyasına yazılabiliyordu ve nihai
# denetim yalnız ASS komutlarına baktığı için görmüyordu (madde 11).
_SUPPORTED_WRAP_TAG = r'(?:i|b|u|s|em|strong|font)'
_FULL_WRAP_RE = re.compile(
    r'^\s*((?:<' + _SUPPORTED_WRAP_TAG + r'(?:\s[^>]*)?>)+)'
    r'(.*?)((?:</' + _SUPPORTED_WRAP_TAG + r'\s*>)+)\s*$',
    re.DOTALL | re.IGNORECASE,
)


def _match_full_wrap(src_body: str):
    """Metin tam bir DESTEKLENEN açılış/kapanış etiket çiftiyle sarılı mı?
    İçeride matematiksel '<' veya '>' karakterleri bulunabilir, ancak ek kapanış
    etiketleri (</...) olmamalıdır."""
    m = _FULL_WRAP_RE.match(src_body)
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
# ASS'te büyük `\N` HER wrap modunda zorunlu satır sonudur; küçük `\n`
# YALNIZ `WrapStyle: 2` altında kırılır, diğer modlarda normal boşluktur.
# İki desen de IGNORECASE derlenmişti, yani ikisi de her ikisiyle eşleşiyor
# ve küçük `\n` koşulsuz satır sonuna dönüyordu (denetim 2026-08-21,
# madde 21). Artık büyük/küçük harfe duyarlı.
_ASS_SOFTLINE = re.compile(r'\\N')
_ASS_HARDLINE = re.compile(r'\\n')
_ASS_WRAPSTYLE_RE = re.compile(
    r'^\s*WrapStyle\s*:\s*([0-9]+)\s*$',
    re.IGNORECASE | re.MULTILINE)


def parse_ass_wrap_style(content: str) -> int:
    """`[Script Info] WrapStyle`; okunamazsa ASS varsayılanı olan 0."""
    match = _ASS_WRAPSTYLE_RE.search(str(content or ""))
    if not match:
        return 0
    try:
        return int(match.group(1))
    except ValueError:
        return 0


# ASS `\p1` ve üzeri VEKTÖR ÇİZİM modunu açar, `\p0` kapatır. Aradaki
# 'm 0 0 l 100 0' koordinatları görünür dil metni değildir; override blokları
# silinince gerçek kelimelerle karışıp modele gidiyordu (madde 22).
_ASS_DRAWING_MODE_RE = re.compile(r'\\p\s*([0-9]+)', re.IGNORECASE)


def strip_ass_drawing_segments(text: str) -> str:
    """Çizim modu AÇIKKEN gelen içeriği atar, görünür metni korur.

    Çizim modu kapanmadan event biterse kalan bölüm tamamen çizimdir.
    """
    value = str(text or "")
    if not _ASS_DRAWING_MODE_RE.search(value):
        return value
    out = []
    drawing = False
    position = 0
    for match in _ASS_ALPHA_BLOCK_RE.finditer(value):
        if not drawing:
            out.append(value[position:match.start()])
        mode = None
        for mode_match in _ASS_DRAWING_MODE_RE.finditer(match.group(1)):
            mode = mode_match.group(1)
        if mode is not None:
            drawing = mode != "0"
        out.append(match.group(0))
        position = match.end()
    if not drawing:
        out.append(value[position:])
    return "".join(out)
_ASS_HSPACE   = re.compile(r'\\h', re.IGNORECASE)
# Aegisub içi yorum / çevirmen notu blokları. '{=13}' eski biçimdi; '{TL Note:
# ...}', '{SFX}', '{Scene 2}' gibi notlar da diyalog metni sanılıp çeviri
# modeline gidiyordu (denetim Part 2, madde 48).
# DAR tutulur: ASS override komutları ('{\an8}') ve şablon yer tutucuları
# ('{username}') bu desene GİRMEZ — ikisi de korunmalı.
_ASS_COMMENT  = re.compile(
    r'\{=[^}]*\}'
    r'|\{(?![^}]*\\)\s*(?:tl\s*note|t/n|çn|ç/n|note|not|sfx|scene|sahne|'
    r'music|müzik|song|şarkı|translator|çevirmen|comment|yorum)\b[^}]*\}',
    re.IGNORECASE,
)
_ASS_DRAWING_MODE = re.compile(r'\{[^}]*\\p([1-9]\d*)\b[^}]*\}', re.IGNORECASE)
_ASS_DRAWING_DATA = re.compile(
    r'^[\s,.-]*(?:[mnlbspc]\s+)?[-\d.,\s mnlbspc]+$', re.IGNORECASE)

def _clean_ass_text(text: str, wrap_style: int = 2) -> str:
    """ASS override tag'lerini kaldır, satır kırma karakterlerini dönüştür.

    `wrap_style` varsayılanı 2'dir: küçük `\n` de satır sonu sayılır. Bu,
    wrap modunu bilmeyen eski çağrıların davranışını korur."""
    text = _ASS_COMMENT.sub('', text)
    text = _ASS_OVERRIDE.sub('', text)
    text = _ASS_SOFTLINE.sub('\n', text)
    text = _ASS_HARDLINE.sub('\n' if wrap_style == 2 else ' ', text)
    text = _ASS_HSPACE.sub(' ', text)
    return text.strip()


def _format_ass_text(text: str, wrap_style: int = 2) -> str:
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
        value = _ASS_HARDLINE.sub('\n' if wrap_style == 2 else ' ', value)
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
    previous = str(previous_id or "").strip()
    if re.fullmatch(r'[A-Za-z]{2,}[A-Za-z_-]*\d+[A-Za-z0-9_.:-]*', value):
        if re.match(r"(?i)(?:cue|note)[-_.:]?\d", value):
            return True
        # 'cue'/'note' dışındaki üretici önekleri ('sub-2', 'item-2', 'seq-2')
        # ancak ÖNCEKİ KİMLİKLE aynı deseni paylaşıyorsa kimliktir. Ad tek
        # başına yeterli değil: 'Caption1' ve 'line-0-797' gerçek repliktir
        # (denetim Part 2, madde 45 — düzeltme dar tutuldu).
        return _shares_vtt_id_pattern(value, previous)
    if not previous:
        return False
    return _shares_vtt_id_pattern(value, previous)


def _shares_vtt_id_pattern(value: str, previous: str) -> bool:
    """İki satır aynı kimlik desenini mi paylaşıyor ('sub-1' ↔ 'sub-2')?"""
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
    timestamp_offset = parse_vtt_timestamp_map(content)

    blocks = []
    idx = 1
    lines = content.replace('\r\n', '\n').replace('\r', '\n').splitlines()
    # Kesir alani WebVTT'de de SRT normalizasyonunda da OPSIYONEL olmali:
    # zorunlu tutulunca '00:00:01 --> 00:00:02' satiri hic taninmiyor ve
    # cue SESSIZCE dusuyordu (denetim Tur 4, madde 9).
    ts_re = re.compile(r'^\d+:\d{2}(?::\d{2})?(?:[.,]\d+)?\s*-->')
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
        if timestamp_offset:
            start_seconds = _vtt_ts_to_seconds(start_raw)
            end_seconds = _vtt_ts_to_seconds(end_parts[0])
            if start_seconds is not None and end_seconds is not None:
                timestamp = (
                    f'{_seconds_to_srt_ts(start_seconds + timestamp_offset)}'
                    ' --> '
                    f'{_seconds_to_srt_ts(end_seconds + timestamp_offset)}')
            else:
                timestamp = (f'{_vtt_ts_to_srt(start_raw)} --> '
                             f'{_vtt_ts_to_srt(end_parts[0])}')
        else:
            timestamp = (f'{_vtt_ts_to_srt(start_raw)} --> '
                         f'{_vtt_ts_to_srt(end_parts[0])}')

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
        # Karakter referansları BURADA, etiket ayrımından SONRA çözülür:
        # önce çözülseydi '&lt;i&gt;' gerçek bir etiket sanılıp silinirdi
        # (denetim 2026-08-21, madde 9).
        text = decode_vtt_entities(text)
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


_ASS_SPOKEN_HINT_RE = re.compile(r"[.!?…»”\"']\s*$|[,;:]\s")


def _ass_style_skip_is_safe(raw_text: str) -> bool:
    """'Note'/'Credit' stilindeki satır gerçekten atılabilir mi?

    Stil adı tek başına kanıt değil: keyfi adlandırılmış bir stille yazılmış
    GERÇEK replik de 'Note' olabiliyor ve içerik incelenmeden siliniyordu
    (denetim 2026-08-20, madde 23). Cümle noktalaması taşıyan çok kelimeli
    metin replik sayılır ve korunur."""
    text = _clean_ass_text(_format_ass_text(str(raw_text or ""))).strip()
    if not text:
        return True
    words = [word for word in re.split(r"\s+", text) if any(
        char.isalpha() for char in word)]
    if len(words) < 4:
        return True  # kısa künye/etiket
    return not bool(_ASS_SPOKEN_HINT_RE.search(text))

def parse_ass(filepath: str, lyric_language: str | None = None) -> list:
    """ASS/SSA dosyasını parse eder. Anlam taşıyan diyalog/ekran metnini alır,
    yalnız salt efekt, karaoke, kredi ve çevirmen notu stillerini atlar.
    Returns: [(index_str, 'HH:MM:SS,mmm --> HH:MM:SS,mmm', text), ...]
    """
    content = read_subtitle_text(filepath)
    timer_scale = parse_ass_timer_scale(content)
    wrap_style = parse_ass_wrap_style(content)
    invisible_styles = parse_ass_invisible_styles(content)

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
        if _SKIP_STYLES.search(style) and _ass_style_skip_is_safe(parts[text_i]):
            continue  # gerçekten kredi/not satırı

        if timer_scale != 1.0:
            start_seconds = _ass_ts_to_seconds(parts[start_i])
            end_seconds = _ass_ts_to_seconds(parts[end_i])
        else:
            start_seconds = end_seconds = None
        if start_seconds is not None and end_seconds is not None:
            start_ts = _seconds_to_srt_ts(start_seconds * timer_scale)
            end_ts = _seconds_to_srt_ts(end_seconds * timer_scale)
        else:
            start_ts = _ass_ts_to_srt(parts[start_i])
            end_ts   = _ass_ts_to_srt(parts[end_i])
        timestamp = f'{start_ts} --> {end_ts}'
        if style in invisible_styles:
            continue  # stil tamamen saydam — ekranda hiç görünmez
        raw_text = ass_visible_text(parts[text_i])
        if not _clean_ass_text(raw_text, wrap_style).strip():
            continue  # inline alpha ile baştan sona gizlenmiş event
        # Aynı event hem çizim hem gerçek yazı taşıyabilir; koordinatlar
        # override blokları silinince kelimelerle karışıyordu (madde 22).
        raw_text = strip_ass_drawing_segments(raw_text)
        if _ass_is_drawing_only(raw_text):
            continue
        if _ass_is_pure_decorative_fx(style, raw_text):
            continue
        text = _format_ass_text(raw_text, wrap_style)
        if not _clean_ass_text(text, wrap_style).strip():
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
            # Ön ek BAŞTAKİ konum/override etiketlerinin ARKASINA yazılır:
            # '{\\an8}' bloğun ilk karakteri olmazsa oynatıcı hizalamayı
            # uygulamaz (denetim Part 2, madde 13).
            lead = re.match(r'^(?:\{[^}]*\}|</?[a-zA-Z][^>]*>)+', text)
            if lead:
                text = f"{lead.group(0)}{name}: {text[lead.end():]}"
            else:
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


# ── Görünür anlam katmanı ────────────────────────────────────────────────
# Eksik/hatalı çeviri denetimleri HAM dize üzerinde yapılıyordu: '[HATA]'
# yalnız dizenin BAŞINDA aranıyor, biçim etiketleri hiç soyulmuyordu. Bu
# yüzden '<i>[HATA]</i>', '<i></i>' ve '—' gibi teslim edilemez hedefler
# tamamlanma, teslim denetimi ve TM kapılarının üçünden de geçiyordu
# (denetim 2026-08-21, madde 1). Bu katman üç kapının ortak ölçütüdür.
# Süslü parantez YALNIZ ters-bölüyle başlayan gerçek ASS override bloğuysa
# görünmezdir. Her `{...}`'yi markup saymak `{username}`, `{red}` gibi
# ekranda GÖRÜNEN literal metni boş hedefe çeviriyordu (devam denetimi,
# madde 2) — parser katmanı bunları özellikle koruyor.
_VISIBLE_MARKUP_RE = re.compile(
    r"</?[a-zA-Z][^>]*>|\{\s*\\[^{}]*\}")
_VISIBLE_INVISIBLE_RE = re.compile(
    "[\u00ad\u200b-\u200f\u202a-\u202e\u2060\u2066-\u2069\ufeff]")
_TRANSLATION_FAILURE_MARKER_RE = re.compile(
    r"\[\s*(?:HATA|ÇEVİRİ\s+EKSİK)", re.IGNORECASE)
_WORDLIKE_RE = re.compile(r"[^\W\d_]", re.UNICODE)


def visible_semantic_text(value) -> str:
    """Biçim etiketleri ve görünmez kontroller çıkarılmış görünür metin."""
    text = _VISIBLE_MARKUP_RE.sub("", str(value or ""))
    text = _VISIBLE_INVISIBLE_RE.sub("", text)
    return text.strip()


def has_visible_wordlike_text(value) -> bool:
    """Görünür metinde en az bir harf var mı?"""
    return bool(_WORDLIKE_RE.search(visible_semantic_text(value)))


def translation_failure_reason(target, source=None) -> str:
    """Bu hedef teslim edilebilir mi? Edilemezse nedeni, edilebilirse ''.

    `source` verilmezse yalnız hedefin kendisinden anlaşılan hatalar
    (hata işareti, görünür içeriğin tamamen boş olması) bildirilir.
    Kaynak verilirse sözcük taşıyan bir kaynağın karşısındaki sözcüksüz
    hedef ('...', '—') de hata sayılır; kaynağın kendisi sözcüksüzse
    aynı hedef meşrudur."""
    raw = str(target or "")
    if _TRANSLATION_FAILURE_MARKER_RE.search(raw):
        return "hata_isareti"
    visible = visible_semantic_text(raw)
    if not visible:
        return "bos_hedef"
    if _WORDLIKE_RE.search(visible):
        return ""
    if source is None:
        return ""
    if has_visible_wordlike_text(source):
        return "sozcuksuz_hedef"
    return ""


def is_generated_subtitle_name(name: str) -> bool:
    """Ad, programın ÜRETTİĞİ bir altyazı artifact'ına mı ait?

    '.tr.srt', '.ham.srt', '.partial.srt', gizli '.stage.srt' vb. asla kaynak
    olamaz; aksi hâlde sonraki koşu kendi çıktısını yeniden çevirir. GUI taraması
    bunu zaten uyguluyordu, standalone batch yolunda parite yoktu (denetim
    2026-08-20, madde 16)."""
    low = str(name or "").lower()
    if _GENERATED_SUBTITLE_NAME_RE.search(low):
        return True
    if low.endswith(".ham.srt"):
        return True
    return low.startswith(".") and low.endswith(".stage.srt")


def _sibling_exists(folder, stem: str, extensions) -> bool:
    try:
        names = {entry.name.casefold() for entry in Path(folder).iterdir()}
    except OSError:
        return False
    return any(f"{stem}{ext}".casefold() in names for ext in extensions)


def is_generated_subtitle_file(path) -> bool:
    """Bu DOSYA programın ürettiği bir artifact mı?

    `is_generated_subtitle_name` yalnız ada bakıyordu; bu yüzden meşru
    `movie.tr.srt` kaynakları hiç keşfedilmiyor (madde 30), programın
    `movie.vtt.srt` çıktısı ise kaynak sanılıyordu (madde 13). Burada
    belirsiz adlar için KOMŞU KAYNAK kanıtı aranır."""
    target = Path(path)
    name = target.name
    low = name.casefold()
    if _INTERNAL_ARTIFACT_NAME_RE.search(low):
        return True
    if low.startswith(".") and low.endswith(".stage.srt"):
        return True
    folder = target.parent
    match = _AMBIGUOUS_FORMAT_NAME_RE.match(name)
    if match:
        return _sibling_exists(
            folder, match.group("stem"), ("." + match.group("ext"),))
    match = _AMBIGUOUS_TR_NAME_RE.match(name)
    if match:
        return _sibling_exists(folder, match.group("stem"), _SOURCE_EXTENSIONS)
    return False


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
                if is_generated_subtitle_file(Path(root) / name):
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
            if is_generated_subtitle_file(fp):
                continue
            result.append(str(fp))
    return sorted(result)  # alfabetik sıra — tekrarlanabilir
