import re
import unicodedata


FORMAT_TAG_RE = re.compile(r"</?(i|b|u|font)[^>]*>", re.IGNORECASE)
MUSIC_NOTE_RE = re.compile(r"[♪♫♬♩]+")
EMPTY_DASH_RE = re.compile(r"^\s*[-–—_]+\s*$")
_MAX_DESCRIPTOR_GROUP = 300
SPEAKER_PREFIX_RE = re.compile(r"^\s*-?\s*(\[[^\]\n]{1,40}\]|\([^)\n]{1,40}\))\s*:?\s*")
CHEVRON_SPEAKER_RE = re.compile(r"^\s*(?:(?:&gt;|>){2})\s*", re.IGNORECASE)


def _bracket_group_spans(text: str) -> list:
    """Dengeli []/() gruplarını satır bazında ve sınırlı uzunlukta bulur."""
    text = str(text or "")
    spans = []
    stack = []
    start = None
    pairs = {"]": "[", ")": "("}
    for pos, char in enumerate(text):
        if char == "\n":
            stack.clear()
            start = None
            continue
        if char in "[(":
            if not stack:
                start = pos
            stack.append(char)
        elif char in "])" and stack:
            if stack[-1] != pairs[char]:
                stack.clear()
                start = None
                continue
            stack.pop()
            if not stack and start is not None:
                if pos - start - 1 <= _MAX_DESCRIPTOR_GROUP:
                    spans.append((start, pos + 1))
                start = None
        if start is not None and pos - start > _MAX_DESCRIPTOR_GROUP + 2:
            stack.clear()
            start = None
    return spans


def _replace_bracket_groups(text: str, replacer) -> str:
    text = str(text or "")
    spans = _bracket_group_spans(text)
    if not spans:
        return text
    out = []
    cursor = 0
    for start, end in spans:
        out.append(text[cursor:start])
        out.append(replacer(text[start:end]))
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


_LABEL_CONTEXT_NOISE_RE = re.compile(r"[\s\-–—>♪♫♬♩:;,.]+")


def _replace_bracket_groups_ctx(text: str, replacer) -> str:
    """_replace_bracket_groups gibi, ama replacer'a (raw, standalone) verir.

    `standalone`: grup, bulunduğu SATIRIN tamamını kaplıyor mu? '[Soft Power]
    A documentary.' gibi başlık ön ekleriyle '[uğultu]' gibi tek başına duran
    ses etiketlerini ayırt etmenin tek güvenilir yolu bu — ikisi de kısa ve
    Title Case olabiliyor."""
    text = str(text or "")
    spans = _bracket_group_spans(text)
    if not spans:
        return text
    out = []
    cursor = 0
    for start, end in spans:
        line_start = text.rfind("\n", 0, start) + 1
        line_end = text.find("\n", end)
        if line_end == -1:
            line_end = len(text)
        context = text[line_start:start] + " " + text[end:line_end]
        context = _replace_bracket_groups(context, lambda raw: " ")
        # <i>(etiket)</i>: biçim etiketleri bağlam sayılmaz, yoksa italikle
        # sarılmış her etiket "tek başına değil" görünüyordu.
        context = FORMAT_TAG_RE.sub("", context)
        standalone = not _LABEL_CONTEXT_NOISE_RE.sub("", context).strip()
        out.append(text[cursor:start])
        out.append(replacer(text[start:end], standalone))
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


def _has_bracket_group(text: str) -> bool:
    return bool(_bracket_group_spans(text))

_SDH_KEYWORDS = {
    # English hearing-impaired captions
    "applause", "applauding", "cheering", "cheers", "booing",
    # 290 gercek kaynakta olculen ciplak CAPS kacaklari: sozluk bu ses
    # sozcuklerini bilmiyordu. 'garbled voices' 12 cue ile en cogu.
    "garbled", "voices", "groans", "shrieks", "shrieking", "buzzing",
    "surge", "musicians", "static", "crackling", "hissing",
    "laugh", "laughs", "laughing", "laughter", "chuckle", "chuckles",
    "chuckling", "giggle", "giggles", "giggling",
    "sigh", "sighs", "sighing", "gasp", "gasps", "gasping",
    "exhale", "exhales", "exhaling", "inhale", "inhales", "inhaling",
    "groan", "groans", "groaning", "moan", "moans", "moaning",
    "scream", "screams", "screaming", "crying", "cries", "sobbing",
    "sniffles", "cough", "coughs", "coughing", "sneeze", "sneezes",
    "breathing", "panting", "grunting", "whisper", "whispers",
    "whispering", "murmur", "murmurs", "murmuring", "chanting",
    "music", "song", "singing", "sings", "plays", "playing", "speaking in tongues",
    "tense", "dramatic", "ominous", "somber", "upbeat", "soft", "sing songy",
    "door", "knock", "knocks", "phone", "ringing", "beeping", "alarm",
    "thunder", "thundering", "thunderclap", "explosion", "gunshot", "siren", "engine", "crowd",
    "noise", "silence", "chatter", "conversation", "inaudible", "indistinct", "overlapping",
    "chord", "lock",
    "continues", "distant", "nearby", "indistinctly", "overhead", "honk",
    # Turkish captions
    "alkis", "alkislar", "alkisliyor", "tezahurat", "yuhalama",
    "guluyor", "gulusme", "gulusmeler", "kahkaha", "kahkahalar",
    "kikirder", "ic ceker", "ic cekis", "nefes", "soluk", "oksurur",
    "hapsirir", "bagirir", "ciglik", "aglar", "hickirik", "inler",
    "homurdanir", "fisildar", "mirildanir", "muzik", "sarki",
    "soyluyor", "calar", "caliyor", "gerilimli", "dramatik",
    "duygusal", "kapi", "telefon", "zil", "alarm", "gok gurultusu",
    "patlama", "silah", "siren", "motor", "kalabalik", "gurultu",
    "anlasilmiyor", "boguk", "devam ediyor",
    # Additional English keywords
    "footsteps", "footstep", "steps", "walking", "running",
    "crash", "crashes", "crashing", "breaking", "shatter", "shattering",
    "smash", "smashing", "bark", "barks", "barking", "howl", "howling",
    "growl", "growling", "meow", "roar", "roaring", "chirping",
    "wind", "blowing", "rain", "raining", "rainfall", "storm", "waves", "water",
    "door slam", "slamming", "door closes", "door opens", "door creaks",
    "heartbeat", "heart beating", "pulse",
    "clock ticking", "ticking", "clock",
    "phone rings", "phone ringing", "cellphone", "dialing", "dial tone",
    "car engine", "car", "truck", "train", "horn", "honking", "honks", "whistles",
    "tires", "tire squeal", "brakes", "squealing",
    "gunfire", "gun", "gunshots", "shot", "rifle", "pistol", "weapon",
    "bullet", "bullet impact", "humming", "hum", "buzzing", "rumbling", "rumbles",
    "click", "clicks", "clicking", "clap", "claps", "clapping", "keyboard", "typing", "beep", "ping",
    "whistle", "whistling", "shout", "shouts", "shouting",
    "yell", "yells", "yelling", "hum", "humming", "rapping",
    "starts", "stops", "stopping", "tolls", "crowing", "cooing", "shivers",
    "voices", "echoing", "shrieks", "rattles", "backfires", "backfiring",
    "sputters", "sputtering", "audible", "dialogue", "dialonue", "cranks",
    "cranking", "revs", "idling", "chattering", "blowing", "distance",
    "rumbles", "heavily", "hitting", "revving",
    # Kaynak dosya İngilizce olmayabilir: Fransızca/Almanca/İspanyolca/İtalyanca
    # SDH tanımlayıcıları da silinmeli ('[rires]', '[Lachen]', '[risas]').
    # (Anahtarlar _descriptor_key ile aksansız/küçük harfe indirgenerek aranır.)
    # Fransızca
    "rires", "rire", "rit", "soupir", "soupire", "musique", "applaudissements",
    "cris", "crie", "chuchote", "chuchotement", "sanglots", "pleure",
    "bruit", "bruits", "silence", "porte", "telephone", "sonnerie", "coup de feu",
    "tonnerre", "explosion", "pas", "vent", "pluie", "inaudible", "indistinct",
    "haletant", "grogne", "toux", "tousse", "sifflement",
    # Almanca
    "lachen", "lacht", "gelachter", "seufzt", "seufzen", "musik", "applaus",
    "schreit", "schreie", "flustert", "flustern", "weint", "schluchzt",
    "gerausch", "gerausche", "stille", "tur", "telefon", "klingelt", "schuss",
    "donner", "explosion", "schritte", "wind", "regen", "unverstandlich",
    "keucht", "stohnt", "hustet", "pfeift", "atmet",
    # İspanyolca / Portekizce
    "risas", "rie", "risa", "suspira", "suspiro", "musica", "aplausos",
    "grita", "gritos", "susurra", "susurro", "llora", "sollozos", "ruido",
    "silencio", "puerta", "telefono", "timbre", "disparo", "trueno",
    "explosion", "pasos", "viento", "lluvia", "inaudible", "jadea", "tose",
    "gruñe", "gruñido", "risos", "chora", "porta", "telefone", "passos",
    "vento", "chuva", "ruido de fundo",
    # İtalyanca
    "risate", "ride", "sospira", "sospiro", "musica di sottofondo", "applausi",
    "urla", "grida", "sussurra", "piange", "singhiozza", "rumore", "silenzio",
    "porta", "telefono", "squillo", "sparo", "tuono", "esplosione", "passi",
    "vento", "pioggia", "incomprensibile", "ansima", "tossisce",
}

_SPEAKER_WORDS = {
    "man", "woman", "male", "female", "boy", "girl", "child", "kid",
    "narrator", "announcer", "speaker", "voice", "voiceover", "interviewer",
    "host", "co host", "co hosts", "both", "reporter", "crowd",
    "congregant", "congregation", "sheriff", "deputy", "sergeant",
    "spokesman", "spokesperson", "detective", "agent",
    "adam", "kadin", "erkek", "cocuk", "anlatici", "sunucu", "konusmaci",
    "ses", "dis ses", "roportajci", "muhabir", "kalabalik",
    "doctor", "nurse", "officer", "teacher", "judge",
    "king", "queen", "prince", "princess", "soldier", "captain", "priest",
    "cook", "minister", "storyteller", "maid", "servant", "baby", "patient",
}

_TR_ASCII_MAP = str.maketrans({
    "İ": "I", "I": "I", "Ş": "S", "Ğ": "G", "Ç": "C", "Ö": "O", "Ü": "U",
    "ı": "i", "ş": "s", "ğ": "g", "ç": "c", "ö": "o", "ü": "u",
})


_SDH_TRANSLATION_PATTERNS = [
    (re.compile(r"\blaughing\s+continues\b", re.IGNORECASE), "KAHKAHALAR SÜRÜYOR"),
    (re.compile(r"\bdisco\s+music\s+playing\b", re.IGNORECASE), "DİSKO MÜZİĞİ ÇALIYOR"),
    (re.compile(r"\bmusic\s+playing\b", re.IGNORECASE), "MÜZİK ÇALIYOR"),
    (re.compile(r"\blive\s+rock\s+music\b", re.IGNORECASE), "CANLI ROCK MÜZİĞİ"),
    (re.compile(r"\baudience\b", re.IGNORECASE), "SEYİRCİ"),
    (re.compile(r"\bcrowd\b", re.IGNORECASE), "KALABALIK"),
    (re.compile(r"\blaughing\b|\blaughter\b", re.IGNORECASE), "KAHKAHA ATIYOR"),
    (re.compile(r"\bchuckles?\b|\bchuckling\b", re.IGNORECASE), "KIKIRDAR"),
    (re.compile(r"\bgiggles?\b|\bgiggling\b", re.IGNORECASE), "KIKIRDAR"),
    (re.compile(r"\bapplauding\b|\bapplause\b", re.IGNORECASE), "ALKIŞLIYOR"),
    (re.compile(r"\bcheering\b|\bcheers\b", re.IGNORECASE), "TEZAHÜRAT YAPIYOR"),
    (re.compile(r"\bbooing\b", re.IGNORECASE), "YUH ÇEKİYOR"),
    (re.compile(r"\bsighs?\b|\bsighing\b", re.IGNORECASE), "İÇ ÇEKER"),
    (re.compile(r"\bgasps?\b|\bgasping\b", re.IGNORECASE), "NEFESİ KESİLİR"),
    (re.compile(r"\bgroans?\b|\bgroaning\b", re.IGNORECASE), "İNLER"),
    (re.compile(r"\bmoans?\b|\bmoaning\b", re.IGNORECASE), "İNİLTİ"),
    (re.compile(r"\bscreams?\b|\bscreaming\b", re.IGNORECASE), "ÇIĞLIK ATAR"),
    (re.compile(r"\bcrying\b|\bcries\b|\bsobbing\b", re.IGNORECASE), "AĞLIYOR"),
    (re.compile(r"\bcoughs?\b|\bcoughing\b", re.IGNORECASE), "ÖKSÜRÜR"),
    (re.compile(r"\bsneezes?\b|\bsneezing\b", re.IGNORECASE), "HAPŞIRIR"),
    (re.compile(r"\bwhispers?\b|\bwhispering\b", re.IGNORECASE), "FISILDAR"),
    (re.compile(r"\binaudible\b|\bindistinct\b", re.IGNORECASE), "ANLAŞILMIYOR"),
    (re.compile(r"\boverlapping\b", re.IGNORECASE), "ÜST ÜSTE"),
    (re.compile(r"\bengine(?:s)?\b", re.IGNORECASE), "MOTOR"),
    (re.compile(r"\bthunder\b", re.IGNORECASE), "GÖK GÜRÜLTÜSÜ"),
    (re.compile(r"\bexplosion\b", re.IGNORECASE), "PATLAMA"),
    (re.compile(r"\bgunshot\b", re.IGNORECASE), "SİLAH SESİ"),
    (re.compile(r"\bsiren\b", re.IGNORECASE), "SİREN"),
    (re.compile(r"\bdramatic\b", re.IGNORECASE), "DRAMATİK"),
    (re.compile(r"\btense\b", re.IGNORECASE), "GERİLİMLİ"),
    (re.compile(r"\bominous\b", re.IGNORECASE), "TEHDİTKÂR"),
    (re.compile(r"\bsoft\b", re.IGNORECASE), "HAFİF"),
    (re.compile(r"\bmusic\b", re.IGNORECASE), "MÜZİK"),
    (re.compile(r"\bplaying\b", re.IGNORECASE), "ÇALIYOR"),
]


_SPEAKER_LABEL_TRANSLATIONS = {
    "narrator": "Anlatıcı",
    "man": "Adam",
    "woman": "Kadın",
    "male": "Erkek",
    "female": "Kadın",
    "male speaker": "Erkek Konuşmacı",
    "female speaker": "Kadın Konuşmacı",
    "boy": "Oğlan",
    "girl": "Kız",
    "child": "Çocuk",
    "kid": "Çocuk",
    "announcer": "Sunucu",
    "speaker": "Konuşmacı",
    "voice": "Ses",
    "voiceover": "Dış Ses",
    "voice-over": "Dış Ses",
    "interviewer": "Röportajcı",
    "host": "Sunucu",
    "reporter": "Muhabir",
    "crowd": "Kalabalık",
    "audience": "Seyirci",
    "congregant": "Cemaat Üyesi",
    "congregation": "Cemaat",
    "news anchor": "Haber Sunucusu",
    "anchor": "Sunucu",
    "director": "Yönetmen",
    "producer": "Yapımcı",
    "film crew": "Film Ekibi",
    "crew": "Ekip",
    "police": "Polis",
    "doctor": "Doktor",
    "nurse": "Hemşire",
    "officer": "Memur",
    "teacher": "Öğretmen",
    "judge": "Hakim",
    "king": "Kral",
    "queen": "Kraliçe",
    "soldier": "Asker",
    "captain": "Kaptan",
    "priest": "Rahip",
    "baby": "Bebek",
    "patient": "Hasta",
}

_SPEAKER_LABEL_ALTS = "|".join(
    re.escape(label) for label in sorted(_SPEAKER_LABEL_TRANSLATIONS, key=len, reverse=True)
)


def _ascii_fold(value: str) -> str:
    value = str(value or "").translate(_TR_ASCII_MAP)
    value = unicodedata.normalize("NFKD", value)
    return value.encode("ascii", "ignore").decode("ascii").lower()


_SENTENCE_END_RE = re.compile(r"[.!?…]['\"”’»]?\s*$")


# Anlatısal EKRAN KARTLARI: tamamı büyük harf oldukları için yapısal SDH
# testine takılıyorlardı ama bunlar ses/konuşmacı etiketi değil, çevrilmesi
# gereken ekran yazılarıdır (denetim 2026-08-20, madde 6).
# Ölçüt iki somut sinyal: yıl içeren yer/tarih kartı ve yerleşik film kartı
# kalıpları. Çıplak yer adı ('LONDON') bu testle ayırt EDİLEMEZ — sözcük
# dağarcığı gerektirir; bilinçli olarak kapsam dışıdır.
_SCREEN_CARD_YEAR_RE = re.compile(r"(?<!\d)(1[0-9]{3}|2[0-9]{3})(?!\d)")
_SCREEN_CARD_PHRASES = frozenset({
    "the end", "fin", "ende", "son", "the beginning", "intermission",
    "epilogue", "prologue", "epilog", "prolog", "meanwhile", "later",
    "earlier", "the next day", "that night", "based on a true story",
    "based on true events", "inspired by true events", "to be continued",
    "in memory of", "dedicated to",
    # Ekran tabelaları ve uyarı levhaları: bunlar SES etiketi değil, ekranda
    # görünen ve ÇEVRİLMESİ gereken yazılardır (denetim Part 2, madde 27).
    "emergency exit", "exit", "entrance", "no entry", "danger", "warning",
    "caution", "police", "police department", "hospital", "fire department",
    "for sale", "sold out", "closed", "open", "vacancy", "no vacancy",
    "keep out", "private", "restricted area", "wanted", "missing",
    "welcome", "help", "stop", "quiet please", "do not disturb",
})
_SCREEN_CARD_PREFIX_RE = re.compile(
    r"^(?:act|part|chapter|episode|volume|book|scene|day|year|week|month)\b"
    r"[\s.:-]*"
    r"(?:[ivxlcdm]+|\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|first|second|third|fourth|fifth|final|last)?$",
    re.IGNORECASE,
)


def is_narrative_screen_card(text: str) -> bool:
    """Tamamı büyük harfli metin bir ekran kartı mı (SDH etiketi DEĞİL)?"""
    value = FORMAT_TAG_RE.sub("", str(text or ""))
    value = re.sub(r"^\s*[-–—]\s*", "", value).strip()
    if not value or "\n" in value:
        return False
    if _SCREEN_CARD_YEAR_RE.search(value):
        return True
    folded = _ascii_fold(value.rstrip(".!?").strip()).lower()
    if folded in _SCREEN_CARD_PHRASES:
        return True
    return bool(_SCREEN_CARD_PREFIX_RE.match(folded))


def is_structural_sdh_label(text: str) -> bool:
    """Beyaz listeye BAKMADAN, yapısal olarak SDH etiketi mi?

    Ayırt edici sinyal biçimdir, kelime değil: satırın harfleri TAMAMEN büyük ve
    satır cümle noktalamasıyla bitmiyorsa bu bir altyazı repliği değil, bir ses/
    konuşmacı etiketidir ('АПЛОДИСМЕНТЫ', 'ВОЙ СИРЕНЫ', 'МУЗЫКА:', 'APPLAUSE').
    Bu test alfabeden bağımsızdır — Kiril, Yunan ve Latin aynı kuralla yakalanır;
    dile özel anahtar kelime listeleri her yeni kaynakta köstebek-vurmacaya
    dönüşüyordu.

    DİKKAT: Kaynağın TAMAMI büyük harfle yazılmış dosyalarda (ABD closed-caption
    geleneği) bu sinyal anlamsızdır — çağıran taraf dosya düzeyinde oranı ölçüp
    öyle kullanmalı (bkz. _delivery_removable_source_ids)."""
    value = FORMAT_TAG_RE.sub("", str(text or ""))
    value = MUSIC_NOTE_RE.sub(" ", value)
    value = CHEVRON_SPEAKER_RE.sub("", value)
    value = re.sub(r"^\s*[-–—]\s*", "", value).strip()
    if not value or len(value) > 60 or "\n" in value:
        return False
    if _SENTENCE_END_RE.search(value):
        return False
    letters = [char for char in value if char.isalpha()]
    if len(letters) < 2:
        return False
    if not all(char.isupper() for char in letters):
        return False
    # Sayı/zaman kartları ('1975', 'BERLIN 1961') ve film kartları
    # ('THE END', 'ACT I') etiket değil, ekran yazısıdır; bunlar çevrilmeli.
    if is_narrative_screen_card(value):
        return False
    # Harf oranı çok düşükse dokunma.
    return len(letters) >= max(2, len(re.sub(r"\s", "", value)) // 2)


# Title Case eser adlarında küçük yazılan bağlaç/edatlar.
_TITLE_CASE_PARTICLES = frozenset({
    "of", "the", "a", "an", "and", "or", "for", "in", "on",
    "at", "to", "from", "with", "by", "de", "la", "le", "du",
    "des", "von", "van", "der", "die", "das", "und", "el", "y",
    "ve", "ile", "da", "e", "di", "il", "no", "na",
})
_TITLED_LABEL_RE = re.compile(
    r"^\s*(?:[-–—]\s*)?([^\W\d_][^:\n]{0,29}):\s*(\S.*)$")


def is_titled_sdh_label(text: str) -> bool:
    """TAMAMI BÜYÜK etiket + iki nokta + ESER ADI biçimi mi?

    'МУЗЫКА: "Theme 21"' / 'MUSIC: "Rite of Spring"' gibi künyeler
    is_structural_sdh_label'ın 'satırın TAMAMI büyük harf' testine takılmıyordu:
    şarkı adı Latin ve karışık harfli. Sonuç, SDH temizliğinin doğru şekilde
    düşürdüğü cue'nun teslim denetiminde 'kayıp diyalog' (SERT HATA) sayılması
    ve iyi bir teslimin karantinaya alınmasıydı — gerçek dosyalarda ölçüldü:
    tek bölümde 12 cue.

    Ayırt edici ölçüt, kalan kısmın CÜMLE OLMAMASI: tırnaklı ya da Title Case
    bir ad. Böylece 'JOHN: Get out' gibi gerçek replikler korunur — orada
    küçük harfle başlayan bir sözcük var.
    """
    value = FORMAT_TAG_RE.sub("", str(text or ""))
    value = MUSIC_NOTE_RE.sub(" ", value)
    value = CHEVRON_SPEAKER_RE.sub("", value).strip()
    if not value or len(value) > 120:
        return False
    lines = [line.strip() for line in value.split("\n") if line.strip()]
    if not lines:
        return False
    match = _TITLED_LABEL_RE.match(lines[0])
    if not match:
        return False
    label, first_rest = match.group(1).strip(), match.group(2).strip()
    label_letters = [char for char in label if char.isalpha()]
    if len(label_letters) < 2 or not all(
            char.isupper() for char in label_letters):
        return False
    rest = " ".join([first_rest, *lines[1:]]).strip()
    if not rest:
        # Yalnız etiket: bu zaten is_structural_sdh_label'ın işi.
        return False
    if _SENTENCE_END_RE.search(rest):
        return False
    # POZİTİF KANIT ŞART: künyenin ayırt edici yanı ETİKETİN büyük,
    # ESER ADININ olmamasıdır. Bu kontrol olmayınca TAMAMI BÜYÜK yazılmış
    # kaynaklarda (ABD closed-caption geleneği) 'JOHN: GET OUT OF HERE'
    # gibi GERÇEK replikler künye sayılıyor ve teslimden düşürülüyordu.
    if not (any(char.islower() for char in rest)
            or any(char in rest for char in "\"“”«»")
            or "(" in rest):
        return False
    # Parantezli niteleyici künyede olağandır ve küçük harfle
    # başlayabilir: '(часть 1)', '(Side 2 Part 4)'.
    rest = re.sub(r"\([^()]*\)", " ", rest).strip()
    if not rest:
        return True
    # Kalan kısımda küçük harfle BAŞLAYAN sözcük varsa bu bir replik olabilir.
    # İstisna: Title Case eser adlarındaki bağlaç/edatlar küçük yazılır
    # ('Rite of Spring', 'The Threshold of Liberty').
    for word in re.findall(r"[^\W\d_][^\s]*", rest):
        first = word[0]
        if not (first.isalpha() and first.islower()):
            continue
        if word.strip("'\"()[].,;:-").casefold() in _TITLE_CASE_PARTICLES:
            continue
        return False
    return True

def strip_structural_sdh_label_prefix(text: str) -> str:
    """'МУЗЫКА: gerçek replik' → 'gerçek replik' (etiket kısmı atılır).

    Yalnız iki nokta ile ayrılmış, tamamı büyük harfli ÖN EK'i keser; kalan replik
    korunur. Etiketten sonra içerik yoksa metin olduğu gibi bırakılır (cue'yu
    burada silmek çağıranın işi)."""
    value = str(text or "")
    match = re.match(r"^(\s*(?:[-–—]\s*)?)([^\n:]{1,40}):\s*(?=\S)", value)
    if not match:
        return value
    label = match.group(2).strip()
    letters = [char for char in label if char.isalpha()]
    if not letters or not all(char.isupper() for char in letters):
        return value
    rest = value[match.end():]
    return f"{match.group(1)}{rest}" if rest.strip() else value


def _descriptor_key(value: str) -> str:
    value = _ascii_fold(value)
    value = re.sub(r"(?<!\w)0wn(?!\w)", "own", value)
    value = MUSIC_NOTE_RE.sub(" ", value)
    value = re.sub(r"[\[\](){}]+", " ", value)
    value = re.sub(r"[_\-–—:;,.!?]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


_SDH_ACTION_VERBS = {
    "break", "breaks", "breaking", "shatter", "shatters", "shattering",
    "crash", "crashes", "crashing", "slam", "slams", "slamming", "closes", "closing",
    "opens", "opening", "creaks", "creaking", "ticking", "rings", "ringing",
    "beeping", "honking", "squealing", "humming", "buzzing", "rumbling",
    "clicking", "clapping", "typing", "whistling", "shouting", "yelling", "coughing",
    "sneezing", "whispering", "murmuring", "cheering", "booing", "laughing",
    "laughter", "sighing", "gasping", "groaning", "moaning", "screaming",
    "crying", "sobbing", "panting", "grunting", "singing", "playing",
    "continues", "fades", "applause", "applauding", "chuckle", "chuckles",
    "chuckling", "giggle", "giggles", "giggling", "sniffles", "chatter",
    "barking", "howling", "growling", "meow", "roaring", "chirping", "knocks", "knocking",
    "jingling", "clamoring", "chanting", "yell", "yells", "whoop",
    "whoops", "roars", "splashing", "calls", "swelling", "plays",
    "turns", "rewinds", "whirs", "strikes", "rattling", "bugles",
    "passing", "howls", "climbs", "spits", "sloshes", "exclaiming",
    "exclaim", "exclaims", "squeaking", "grinds", "blows", "continue",
    "laughs", "scoffs", "clear", "clearing", "clears", "sniffles", "sobs", "chiming",
    "trilling", "speaking", "speaks", "conversing", "konusur", "konusuyor",
    "kapanir", "kapaniyor",
    "thudding", "clattering", "pattering", "smacking", "sloshing",
    "squawking", "croaking", "rustling", "neighing", "vocalizing",
    "clanking", "crackling", "rasping", "retching", "squelching",
    "whining", "clinking", "clicks", "thuds", "squeaks", "clinks",
    "burbling", "sploshing", "slices", "fluttering", "snorts", "cooing",
    "babbling", "whimpering", "rattle", "neighs", "bangs", "clangs",
    "scrapes", "stomp", "bubbling", "snoring", "whinnies", "whinny",
    "blaring", "slaps", "gasps", "grunts", "shut", "tuned", "flicking", "turning",
    "screams", "growls", "groans", "sighs", "chattering",
    "vomits", "vomiting", "breathes", "breathing", "weeps", "weeping",
    "yelps", "yelping", "orgasms", "orgasming", "bursts", "dialling",
    "dialing", "kissing", "chokes", "choking", "sniffs", "sniffing",
    "wails", "wailing", "yawns", "yawning", "whirrs", "bleeping",
    "play", "tolling", "beating", "jingle", "blasts", "neigh",
    "clatters", "draw", "departing", "muttering", "cursing", "chatters",
    "shivering", "stomps", "pounding", "arguing", "jabbering", "approaching",
}

_TITLE_ACTION_PHRASE_VERBS = {
    "approaching", "arguing", "blows", "chatters", "clatters", "cursing",
    "departing", "draw", "gasping", "jabbering", "muttering", "pounding",
    "shivering", "shouting", "stomps",
}

_SDH_SOUND_MODIFIERS = {
    "loud", "sudden", "distant", "faint", "soft", "heavy", "sharp",
    "quiet", "continuous", "muffled", "nearby", "disappointed",
}

_SDH_SOUND_NOUNS = {
    "crash", "slam", "bang", "boom", "thud", "click", "beep", "buzz",
    "rumble", "scream", "shout", "whisper", "knock", "ring", "grunt",
    "zip", "siren", "sirens", "thud", "feedback", "ringtone", "yelp",
    "gong", "gongs", "bell", "bells", "blast", "rhythm", "cry", "throat",
}

_KNOWN_LANGUAGES = {
    "french", "german", "spanish", "english", "italian", "russian", "japanese",
    "chinese", "korean", "arabic", "portuguese", "hindi", "turkish", "latin",
    "greek", "dutch", "swedish", "polish", "hebrew", "vietnamese", "thai",
    "tagalog", "swahili", "persian", "danish", "norwegian", "finnish", "czech",
    "hungarian", "romanian", "ukrainian", "cantonese", "mandarin",
    "urdu", "punjabi", "bengali", "tamil", "telugu", "foreign",
    "welsh", "gaelic",
}


# Latin dışı alfabelerde SDH betimlemesi için POZİTİF kanıt. Yalnız bu
# sözcükler görülürse cue SDH sayılır; gerçek ekran yazıları korunur.
_NON_LATIN_SDH_WORDS = (
    # Japonca
    "音", "音楽", "効果音", "笑い", "拍手", "悲鳴", "足音", "鳴",
    "開く", "閉まる", "ため息", "咳", "叫", "銃声", "爆発",
    # Çince
    "音乐", "掌声", "笑声", "脚步", "枪声", "爆炸",
    # Korece
    "음악", "박수", "웃음", "발소리", "총성",
    # Kiril
    "музык", "аплодисмент", "смех", "шаги", "выстрел", "звонок",
    "крик", "вздох", "кашель", "взрыв", "звук",
    # Yunan
    "μουσικ", "χειροκρότ", "γέλι", "βήματα",
    # Arapça
    "موسيق", "تصفيق", "ضحك", "صوت", "خطوات", "صرخة",
)


def _non_latin_sdh_evidence(content: str) -> bool:
    """Latin dışı metinde SDH betimlemesi olduğuna dair pozitif kanıt."""
    value = str(content or "").casefold()
    return any(word in value for word in _NON_LATIN_SDH_WORDS)


# Parantez içi içerik için DİLDEN BAĞIMSIZ biçim kuralı.
#
# Beyaz liste (_SDH_KEYWORDS, _SDH_ACTION_VERBS...) İngilizce sözcüklere
# dayanıyordu; Türkçeye çevrilmiş etiketler ('[uğultu]', '[KEDİ MİYAVLAR]',
# '[Keçi melemesi]', '[Burnunu sümkürüyor]') hiçbir kurala uymadığı için
# teslim dosyasında kalıyordu. GERÇEK teslimlerde ölçüldü: 274 dosyanın
# 23'ünde artık etiket vardı. Proje kuralı ses/dil/konuşmacı etiketlerinin
# TAMAMEN silinmesi olduğu için parantez içi kısa, cümle olmayan içerik
# artık VARSAYILAN OLARAK etiket sayılır; korumalar aşağıda tek tek sayılı.
_LABEL_QUOTE_CHARS = "\"“”«»„‟"
# Programın kendi işaretleri: bunlar sonradan kaynakla doldurulur, silinmez.
_SELF_MARKER_KEYS = {"ceviri eksik", "ceviri hatasi", "hata"}
# Bağlaçla başlayan parantez içi metin replik/şarkı sözü parçasıdır,
# etiket değil ('[çünkü sobama şeker döktüm]' gerçek bir teslimde vardı).
_CLAUSE_STARTER_KEYS = {
    "cunku", "ama", "fakat", "ancak", "yani", "veya", "oysa",
    "eger", "ki", "ve", "ya", "hem", "ise", "belki", "sanki",
    "keske", "madem", "ustelik", "halbuki", "cunki",
    "because", "but", "and", "or", "if", "so", "then", "that",
}


def _bracket_shape_is_label(content: str, standalone: bool = True) -> bool:
    """Parantez içi içerik, sözcük listesine BAKMADAN etiket mi?

    Ayırt edici sinyal biçimdir: kısa, cümle noktalamasıyla bitmeyen,
    tırnaksız bir parantez içi metin altyazı repliği değildir. Korumalar:
    ekran kartları ('[I. KSENAKİS, 1978]', '[THE END]'), başlık etiketleri,
    tırnaklı alıntılar, '#' ile başlayan şarkı künyeleri, formül/eşitlik
    içerenler, bağlaçla başlayan replik parçaları ve programın kendi
    '[ÇEVİRİ EKSİK]' işareti."""
    raw = str(content or "").strip()
    if not raw or "\n" in raw or len(raw) > 60:
        return False
    if raw[0] in "#♪♫":
        return False
    if any(char in raw for char in _LABEL_QUOTE_CHARS):
        return False
    if _is_protected_bracket_content("[" + raw + "]"):
        return False
    if _SENTENCE_END_RE.search(raw):
        return False
    if is_narrative_screen_card(raw) or _is_heading_label(raw):
        return False
    key = _descriptor_key(raw)
    if not key or key.casefold() in _SELF_MARKER_KEYS:
        return False
    words = key.split()
    if not words or words[0].casefold() in _CLAUSE_STARTER_KEYS:
        return False
    # Çıplak sayı taşıyan içerik ekran yazısıdır ('[404 ERROR]', '[SAAT 3]'),
    # ses etiketi değil. Bilinen etiketleri ('[NARRATOR 2]') aşağıdaki
    # sözcük kuralları yine yakalar.
    if any(word.isdigit() for word in words):
        return False
    letters = [char for char in raw if char.isalpha()]
    if len(letters) < 2:
        return False
    # Tamamı büyük harf = klasik SDH/konuşmacı etiketi; biraz daha uzun
    # olanına da izin verilir. Karışık/küçük harfte replik riski yüksek
    # olduğu için sınır dar tutulur.
    if all(char.isupper() for char in letters):
        return len(words) <= 6
    # İki nokta ile biten içerik konuşmacı etiketidir: '[Bayan Milagros:]'.
    if raw.rstrip().endswith(":"):
        return len(words) <= 4
    # Karışık/küçük harfte replik ve özel ad riski var. İki koşul birden:
    #  • grup satırın TAMAMINI kaplamalı ('[Soft Power] A documentary.'
    #    korunur, '[uğultu]' silinir);
    #  • en az bir sözcük küçük harfle başlamalı — böylece '[Keçi
    #    melemesi]' silinirken '[Sesame Street]' gibi saf Title Case
    #    ekran yazıları/özel adlar korunur.
    has_lower_initial = any(
        word[:1].isalpha() and word[:1].islower() for word in raw.split())
    return standalone and has_lower_initial and len(words) <= 4


# Türkçe ses etiketleri tanınmıyordu: 377 anahtar sözcüğün tamamına yakını
# İngilizce. 377 gerçek teslimde 284.076 cue tarandığında 10 dosyada 17
# parantezli etiket ayakta kalmıştı ve 15'i Türkçe ses tarifiydi
# ('KEDİ MİYAVLAR', 'KEÇİ MELEMESİ', 'YAZAR KASA ZİLİ').
#
# Sözcük listesi yerine KÖK listesi tutulur: Türkçe eklemeli bir dildir ve
# 'ulu-' kökü 'uluma', 'ulumasi', 'uluyor', 'ulur' hepsini üretir.
_TR_SDH_SOUND_ROOTS = (
    # Yalnız ses TARİFİNE özgü kökler. Sıradan replikte geçen genel adlar
    # (ses, zil, telefon, muzik, sarki, nefes, patlama...) BİLEREK yok:
    # ilk deneme onları içeriyordu ve 'Sesi duydun mu?' repliğini etiket
    # sayıp siliyordu. Bu geçiş cue SİLER; yanlış pozitifin bedeli ağırdır.
    "miyav", "havla", "uluma", "ulumasi", "meleme", "melemesi",
    "kisne", "bogur", "tisla", "hirla", "civil", "vizil",
    "inleme", "inlemesi", "hickir", "misilda", "mirilda", "homurdan",
    "oksurme", "oksuruk", "hapsir", "horlama", "islik",
    "gicirt", "gicirda", "cinlama", "tikirti", "catirti", "gumburtu",
    "vinlama", "ugultu", "tezahurat", "kahkaha", "tukurme",
    "cigliklar", "fisilti", "homurtu", "iniltisi", "hirilti",
)

# Bu ekler konuşmacıyı işaret eder: gerçek replik demektir, etiket değil.
# Ölçülen iki gerçek vaka: 'yukarı çıkıyoruz.' ve 'beni davet etselerdi...!'
_TR_SPEECH_PERSON_RE = re.compile(
    r"(?:\b(?:ben|sen|biz|siz|beni|seni|bizi|sizi|bana|sana|bize|size)\b"
    r"|(?:yorum|yoruz|yorsun|yorsunuz|acagim|acağım|ecegim|eceğim"
    r"|acagiz|acağız|ecegiz|eceğiz|misin|mısın|musun|müsün"
    r"|dim|dık|dim|dik|duk|dük|tim|tik|selerdi|salardi|salardı)\b)",
    re.IGNORECASE)


def _tr_sdh_label(content: str, bracketed_hint: bool = False) -> bool:
    """Türkçe ses/eylem etiketi mi? Konuşma eki taşıyan metin etiket sayılmaz."""
    text = str(content or "").strip()
    if not text:
        return False
    if _TR_SPEECH_PERSON_RE.search(text):
        return False
    # Kök TEK BASINA ayirt edici degil: olculdugunde 'kibirli bir homurtuyla
    # cekip gittiler;', 'Kahkaha, demokrasiden yana bir guctur' gibi GERCEK
    # replikleri siliyordu. Gercek etiketin ortak bicimi: parantez icinde ya
    # da bastan sona buyuk harf, ve kisa bir ad obegi.
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    if not (bracketed_hint or all(ch.isupper() for ch in letters)):
        return False
    folded = _ascii_fold(text).lower()
    words = re.findall(r"[a-z]+", folded)
    if not words or len(words) > 4:
        return False
    for root in _TR_SDH_SOUND_ROOTS:
        key = _ascii_fold(root).lower()
        if " " in key:
            if key in folded:
                return True
            continue
        if any(word.startswith(key) for word in words):
            return True
    return False


_SPEECH_LABEL_RE = re.compile(
    r"^(?:[A-Z][A-Za-z'’.-]*\s+)*"          # istege bagli konusmaci adi
    r"(?:SPEAK(?:S|ING)?|TALK(?:S|ING)?|CONVERSE(?:S|ING)?|CHANT(?:S|ING)?|"
    r"RECITE(?:S|ING)?|SING(?:S|ING)?|REPEAT(?:S|ING)?|MUTTER(?:S|ING)?|"
    r"PRAY(?:S|ING)?|GREET(?:S|ING|INGS)?|ORDER(?:S|ING)?|DISCUSS(?:ES|ING)?)"
    # 'SPEAKING OF WHICH' bir deyimdir, etiket degil: fiilden sonra 'of'
    # gelirse eslesme reddedilir.
    r"(?:\s+IN)?\s+(?!(?:OF)\b)\S.*$",
    re.IGNORECASE)


def _is_speech_activity_label(inner: str) -> bool:
    """'<Ad> SPEAKING <dil>' kalibi — dil adi sozlukte olmasa bile etiket.

    Betimleyici sozlugu GERCEK dil adlariyla calisiyor; 'SPEAKING NATIVE
    LANGUAGE', 'SPEAKS CORNISH', 'SPEAKING IN QUECHUA' gibi genel ya da
    listede olmayan biçimleri kaciriyordu. Bu kalip konusma FIILINE bakar,
    dil adina degil.

    Bicim (parantez + buyuk harf) TEK BASINA yetmez: '[PARIS]' ve
    '[CHAPTER ONE]' de oyle gorunur ama konum/baslik karti olarak korunur.
    """
    text = str(inner or "").strip().strip(".!?,;:")
    if not text or not text.isascii():
        return False
    words = re.findall(r"[A-Za-z]+", text)
    if len(words) < 2:
        return False
    return bool(_SPEECH_LABEL_RE.match(text))


def is_sdh_descriptor(content: str, bare_text: bool = False,
                      bracketed: bool = False,
                      standalone: bool = True) -> bool:
    # `bracketed`: içerik gerçekten [..]/(..) içinden geldiyse biçim kuralı
    # uygulanır. Çıplak metinde (bare_text) parantez sinyali yoktur.
    if bracketed and _bracket_shape_is_label(content, standalone):
        return True
    if _tr_sdh_label(content, bracketed_hint=bracketed):
        return True
    key = _descriptor_key(content)
    if not key:
        # ASCII'ye indirgenince boşalan içerik = Latin dışı alfabe (Kiril,
        # Yunan, Arap, Japonca...). Parantez içinde olmak TEK BAŞINA kanıt
        # DEĞİLDİR: köşeli parantez o dillerde gerçek ekran yazısı için de
        # kullanılıyor ve '[東京都庁]' gibi anlamlı tabelalar tamamen
        # siliniyordu (denetim 2026-08-21, madde 38). Pozitif kanıt aranır.
        if _non_latin_sdh_evidence(content):
            return True
        return is_structural_sdh_label(content)
    if _is_heading_label(content):
        return False
    raw_words = str(content or "").strip().split()
    raw_keys = [_descriptor_key(word) for word in raw_words]
    title_action_phrase = bool(
        raw_keys and (
            raw_keys[0] in _TITLE_ACTION_PHRASE_VERBS
            or (len(raw_keys) > 1
                and raw_keys[1] in _TITLE_ACTION_PHRASE_VERBS)
        )
    )
    title_case = (2 <= len(raw_words) <= 6
                  and any(any(ch.islower() for ch in word) for word in raw_words)
                  and all(not word[:1].isalpha() or word[:1].isupper()
                          for word in raw_words))
    if title_case:
        first_key = _descriptor_key(raw_words[0])
        last_key = _descriptor_key(raw_words[-1])
        if (first_key not in _SPEAKER_WORDS
                and not title_action_phrase
                and last_key not in _KNOWN_LANGUAGES
                and last_key not in _SPEAKER_WORDS
                and last_key not in _SDH_ACTION_VERBS
                and (last_key not in _SDH_KEYWORDS
                     or (last_key == "music"
                         and first_key not in _SDH_SOUND_MODIFIERS))):
            return False
    if key in _SDH_KEYWORDS or key in _SPEAKER_WORDS:
        return True
    if key in {
            "non english", "unintelligible speech", "indistinct speech",
            "on tv", "on recording", "together", "clears throat",
            "foreign language", "battle commands", "commands",
            "religious ceremonies", "bagpipers", "drum roll", "festivity",
            "banging hammer", "rubbing stone",
            "yabanci dilde", "savas komutlari", "komutlar",
            "dini torenler", "gaydacilar", "davul rulosu", "senlik",
            "cekic darbesi", "tas ovalama", "black speech"}:
        return True

    words = key.split()
    if not words:
        return True

    # Language descriptor check: [speaking French], [speaks Latin], [in Spanish]
    if len(words) >= 2 and words[0] in ("speaking", "speaks", "in") and words[1] in _KNOWN_LANGUAGES:
        return True
    if (words[-1] in _KNOWN_LANGUAGES
            and any(word in _SDH_ACTION_VERBS for word in words)):
        return True
    if (len(words) >= 3 and words[-2:] == ["own", "language"]
            and any(word in {"speaking", "speaks", "conversing"}
                    for word in words[:-2])):
        return True

    words_no_digits = [w for w in words if not w.isdigit()]
    if not words_no_digits:
        return True

    if len(words_no_digits) == 1:
        return (words_no_digits[0] in _SDH_KEYWORDS
                or words_no_digits[0] in _SPEAKER_WORDS
                or words_no_digits[0] in _SDH_ACTION_VERBS
                or words_no_digits[0] in _SDH_SOUND_NOUNS)

    pronouns = {"i", "you", "he", "she", "we", "they", "it"}
    if not bare_text and not any(word in pronouns for word in words):
        if title_action_phrase and len(words) <= 6:
            return True
        if (words[0] in _SPEAKER_WORDS
                and all(word in _SPEAKER_WORDS
                        or word in _SDH_SOUND_MODIFIERS
                        or word in {"on", "off", "over", "the", "radio", "tv"}
                        for word in words[1:])):
            return True
    instruments = {
        "trumpet", "piano", "violin", "drums", "guitar", "flute", "solo",
    }
    if (not bare_text and len(words_no_digits) <= 10
            and not any(word in pronouns for word in words_no_digits)
             and (words_no_digits[-1].endswith("ing")
                  or "music" in words_no_digits
                  or words_no_digits[0] == "chanting"
                  or (words_no_digits[0] in {"all", "both"}
                      and words_no_digits[-1] in _SDH_KEYWORDS)
                  or words_no_digits[-1] in instruments
                  or words_no_digits[-1] in _SDH_ACTION_VERBS)):
        return True

    # All non-digit words are SDH/speaker keywords: [soft music], [door closes], [narrator 2]
    if all(w in _SDH_KEYWORDS or w in _SPEAKER_WORDS for w in words_no_digits):
        return True

    # Sound action verb ending: [glass breaking], [Glass Breaking], [GLASS BREAKING], [woman whispering]
    if len(words_no_digits) >= 2 and words_no_digits[-1] in _SDH_ACTION_VERBS:
        return True
    if (not bare_text
            and any(w in _SDH_ACTION_VERBS or w in _SDH_KEYWORDS
                    for w in words_no_digits)
            and (words_no_digits[-1].endswith("ly")
                 or any(w in _SDH_KEYWORDS or w in _SPEAKER_WORDS
                        for w in words_no_digits))):
        return True
    if (len(words_no_digits) >= 2
            and words_no_digits[-1] in _SDH_SOUND_NOUNS
            and not any(word in pronouns for word in words_no_digits)):
        return True
    if (len(words_no_digits) >= 2
            and words_no_digits[-1] in {"sound", "sounds", "noise", "noises"}
            and not any(word in pronouns for word in words_no_digits)):
        return True

    return False


def _strip_standalone_music_notes(line: str) -> str:
    """Remove pure music-note captions, but keep notes that mark real lyrics."""
    value = str(line or "")
    if not MUSIC_NOTE_RE.search(value):
        return value
    without_notes = MUSIC_NOTE_RE.sub("", value)
    if not without_notes.strip() or is_sdh_descriptor(without_notes, bare_text=True):
        return without_notes
    return value


_MIXED_CAPS_WORD = r"[A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ'’]+"
_MIXED_CAPS_LABEL_RE = re.compile(
    r"^(?P<dash>[-–—]?\s*)"
    r"(?P<label>%s(?:\s+%s){0,4})"
    r"(?::\s+|\s+(?=[A-ZÇĞİÖŞÜ][a-zçğıöşü]))" % (
        _MIXED_CAPS_WORD, _MIXED_CAPS_WORD))
_MIXED_CAPS_RESIDUE_RE = re.compile(r"\b[A-ZÇĞİÖŞÜ]{2,}\b")


def strip_mixed_caps_label(line: str) -> tuple[str, bool]:
    """Diyalogla AYNI cue'da duran BÜYÜK HARF ses/konuşmacı etiketini atar.

    `HE WHISTLES She's a smasher.` -> `She's a smasher.`
    `KUKLA: İn aşağı!`            -> `İn aşağı!`

    Tek başına duran caps cue'ya DOKUNULMAZ: orada etiket ile ekran
    yazısı/tabela (`SATILIK`, `EUROPCAR CAR RENTAL`) ayırt edilemiyor ve o
    karar dosya düzeyindeki caps kapısına ait.

    Kalanda başka bir caps sözcük varsa da dokunulmaz: o zaman bu bir etiket
    değil, karışık düzende yazılmış BAŞLIKTIR (`HER ŞEYİ BİR Gergedan GİBİ`,
    `VE TAJINDER'İN Nektar Havuzu'NDA`). Ölçüm: bu kayıt olmadan 21 adayın
    4'ü yanlıştı, kayıtla 17/17 doğru.
    """
    value = str(line or "")
    match = _MIXED_CAPS_LABEL_RE.match(value)
    if not match:
        return value, False
    remainder = value[match.end():].strip()
    if len(remainder) < 8 or _MIXED_CAPS_RESIDUE_RE.search(remainder):
        return value, False
    return (match.group("dash") or "") + remainder, True


def _strip_mojibake_music_ornament(text: str) -> str:
    return re.sub(r"^\s*(?:Âª|Aª|ª)\s*(?=[\[(])", "", str(text or ""))


def _is_speaker_name(inner: str, colon_follows: bool = False) -> bool:
    if not inner:
        return False
    if re.search(r'[?!,;:]', inner):
        return False
    if _is_heading_label(inner):
        return False
    role_suffix = re.search(
        r"\s+(?:on\s+tv|over\s+comm|over\s+pa|on\s+recording)\s*$",
        inner, re.IGNORECASE)
    base = re.sub(
        r"\s+(?:on\s+tv|over\s+comm|over\s+pa|on\s+recording)\s*$",
        "", inner, flags=re.IGNORECASE)
    numbered_speaker = bool(re.search(r"\s+#?\s*\d+\s*$", base))
    base = re.sub(r"\s+#?\s*\d+\s*$", "", base).strip()
    base_key = _descriptor_key(base)
    if base_key in _SPEAKER_WORDS:
        return True
    if (numbered_speaker and 1 <= len(base.split()) <= 5
            and (base[:1].isupper() or base.isupper())):
        return True
    if (role_suffix and len(base.split()) == 1
            and (base.istitle() or base.isupper())):
        return True
    words = inner.split()
    if not words or len(words) > 3:
        return False
    if inner.strip().casefold().rstrip(".!?") in {"ok", "no", "yes", "hey"}:
        return False

    # A colon explicitly marks a speaker prefix: [DR. SMITH]: Hello
    if colon_follows:
        return True

    # Without a colon, only single-word proper names ([John], [MARY]) are treated as speaker tags.
    # 2-3 word TitleCase/uppercase phrases ([New York], [Chapter One]) without a colon are kept.
    if len(words) == 1:
        w = words[0]
        if (w.casefold() not in _KNOWN_LANGUAGES
                and w.isalpha() and (w.isupper() or w[:1].isupper())):
            return True

    return False


def _is_protected_bracket_content(raw: str) -> bool:
    inner = raw[1:-1].strip()
    if inner.casefold().rstrip(".!?") in {"ok", "no", "yes", "hey"}:
        return True
    if any(ch in inner for ch in "[]()=+*/<>"):
        return True
    return False


def _strip_speaker_prefix(line: str) -> str:
    while True:
        match = SPEAKER_PREFIX_RE.match(line)
        if not match:
            return line
        raw = match.group(1)
        inner = raw[1:-1].strip()
        colon_follows = line[match.start(1) + len(raw):match.end()].strip().startswith(":")
        # Ön ek konumunda grup satırın tamamını kaplamaz: '[Soft Power] A
        # documentary.' gibi başlıklar korunsun diye standalone=False.
        if (colon_follows
                or is_sdh_descriptor(
                    inner, bracketed=True, standalone=False)
                or _is_speaker_name(inner, colon_follows)):
            line = line[match.end():]
            continue
        return line


def strip_sdh_line(line: str, strip_format_tags: bool = True) -> str:
    line = _strip_mojibake_music_ornament(line)
    line = CHEVRON_SPEAKER_RE.sub("", line)
    line = _strip_speaker_prefix(line)
    if strip_format_tags:
        line = FORMAT_TAG_RE.sub("", line)

    line = _strip_standalone_music_notes(line)

    def replace_descriptor(raw, standalone):
        inner = raw[1:-1]
        return "" if is_sdh_descriptor(
            inner, bracketed=True, standalone=standalone) else raw

    line = _replace_bracket_groups_ctx(line, replace_descriptor)
    line = re.sub(r"\s+([,.;:!?])", r"\1", line)
    line = re.sub(r"(^|\s)[-–—]\s*$", "", line)
    line = re.sub(r"\s{2,}", " ", line).strip()
    return "" if is_sdh_only(line) else line


def is_sdh_only(text: str) -> bool:
    text = str(text or "").strip()
    if not text:
        return True
    text = FORMAT_TAG_RE.sub("", text).strip()
    text = MUSIC_NOTE_RE.sub("", text).strip()
    if re.fullmatch(r"[-–—]?\s*#+", text):
        return True
    if not text or EMPTY_DASH_RE.match(text):
        return True

    had_bracket_group = _has_bracket_group(text)
    stripped = _replace_bracket_groups_ctx(
        text,
        lambda raw, standalone: "" if is_sdh_descriptor(
            raw[1:-1], bracketed=True, standalone=standalone) else raw)
    stripped = re.sub(r"[\s,.;:!?_\-–—]+", "", stripped)
    if not stripped:
        return True
    if _bracket_group_spans(stripped):
        return False
    letters = [char for char in text if char.isalpha()]
    if (not had_bracket_group and re.search(r"[.!?…]\s*$", text)
            and letters and not all(char.isupper() for char in letters)):
        return False
    return is_sdh_descriptor(text, bare_text=True)


def translate_sdh_descriptor(content: str) -> str:
    """Translate English SDH descriptor words while preserving existing Turkish text."""
    text = str(content or "").strip()
    if not text:
        return text
    translated = _apply_sdh_translations(text)
    if translated == text:
        return text
    if is_sdh_descriptor(text) or is_sdh_descriptor(translated):
        return translated
    return text


def _apply_sdh_translations(text: str) -> str:
    out = str(text or "")
    for pattern, replacement in _SDH_TRANSLATION_PATTERNS:
        out = pattern.sub(replacement, out)
    out = re.sub(r"\s*,\s*", ", ", out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


def normalize_sdh_descriptors(text: str) -> str:
    """Translate English words inside SDH brackets/parentheses without removing them."""
    def replace_descriptor(raw):
        opener, closer = raw[0], raw[-1]
        inner = raw[1:-1]
        translated = translate_sdh_descriptor(inner)
        return f"{opener}{translated}{closer}"

    return _replace_bracket_groups(str(text or ""), replace_descriptor)


_EMPTY_FORMAT_PAIR_RE = re.compile(
    r"<\s*(i|b|u|font)[^>]*>\s*</\s*\1\s*>", re.IGNORECASE)


def strip_sdh_descriptors(text: str) -> str:
    """SDH ses/efekt tanımlayıcılarını ÇEVİRMEK yerine tamamen kaldırır.

    Proje kuralı: ses, dil ve konuşmacı etiketleri teslim altyazısında kalmaz
    ('[LAUGHS]' → '[GÜLER]' değil, hiç). Satırı tümüyle boşaltacaksa satır olduğu
    gibi bırakılır — bu aşamada cue düşürülemez, boş metin '[ÇEVİRİ EKSİK]' olarak
    ekrana basılırdı; salt-SDH cue'ları zaten clean_sdh aşaması düşürür."""
    def replace_descriptor(raw, standalone):
        return "" if is_sdh_descriptor(
            raw[1:-1], bracketed=True, standalone=standalone) else raw

    original = str(text or "")
    out_lines = []
    for line in original.split("\n"):
        stripped = _replace_bracket_groups_ctx(line, replace_descriptor)
        stripped = re.sub(r"\s+([,.;:!?])", r"\1", stripped)
        # '<i>[uğultu]</i>' → '<i></i>': boşalan biçim etiketi çifti ekranda
        # görünmez ama satırı 'dolu' gösterip cue'nun düşmesini engelliyordu.
        stripped = _EMPTY_FORMAT_PAIR_RE.sub("", stripped)
        # Etiket sökülünce yalnız diyalog tiresi kalan satır ekranda '-' olarak
        # görünürdü; tamamen boşalmış say.
        stripped = re.sub(r"^\s*[-–—]\s*$", "", stripped)
        stripped = re.sub(r"\s{2,}", " ", stripped).strip()
        if stripped:
            out_lines.append(stripped)
    return "\n".join(out_lines) if out_lines else original


_STRIP_SPEAKER_COLON_RE = re.compile(
    rf"^(\s*-?\s*)\[?\(?({_SPEAKER_LABEL_ALTS})"
    rf"(?:\s+\(?(?:V\.?O\.?|O\.?S\.?|VO|OS)\)?)?\]?\)?\s*:\s*",
    re.IGNORECASE,
)
_STRIP_SPEAKER_BRACKET_RE = re.compile(
    rf"^(\s*-?\s*)[\[\(](?:{_SPEAKER_LABEL_ALTS})"
    rf"(?:\s+\(?(?:V\.?O\.?|O\.?S\.?|VO|OS)\)?)?[\]\)]\s*",
    re.IGNORECASE,
)


def strip_speaker_labels(text: str) -> str:
    """Konuşmacı etiketlerini Türkçeleştirmek yerine satır başından kaldırır.

    'MAN:' → 'ADAM:' dönüşümü etiketi teslim dosyasında bırakıyordu; proje kuralı
    etiketin tamamen silinmesi. Etiket satırdaki tek içerikse satır korunur."""
    def strip_line(line: str) -> str:
        for pattern in (_STRIP_SPEAKER_COLON_RE, _STRIP_SPEAKER_BRACKET_RE):
            match = pattern.match(line)
            if not match:
                continue
            rest = line[match.end():].strip()
            if not rest:
                return ""
            return f"{match.group(1)}{rest}"
        return line

    original = str(text or "")
    lines = [value for value in (strip_line(line) for line in original.split("\n")) if value]
    return "\n".join(lines) if lines else original


def _tr_upper(s: str) -> str:
    res = []
    for char in s:
        if char == "i":
            res.append("İ")
        elif char == "ı":
            res.append("I")
        elif char == "ş":
            res.append("Ş")
        elif char == "ç":
            res.append("Ç")
        elif char == "ğ":
            res.append("Ğ")
        elif char == "ö":
            res.append("Ö")
        elif char == "ü":
            res.append("Ü")
        else:
            res.append(char.upper())
    return "".join(res)


def normalize_speaker_labels(text: str) -> str:
    """Translate common English speaker labels at the start of subtitle lines."""
    if not text:
        return text

    colon_re = re.compile(
        rf"^(\s*-?\s*\[?\(?)({_SPEAKER_LABEL_ALTS})"
        rf"(?:\s+\(?(V\.?O\.?|O\.?S\.?|VO|OS)\)?)?(\]?\)?\s*:\s*)",
        re.IGNORECASE,
    )
    bracket_re = re.compile(
        rf"^(\s*-?\s*[\[\(])({_SPEAKER_LABEL_ALTS})"
        rf"(?:\s+\(?(V\.?O\.?|O\.?S\.?|VO|OS)\)?)?([\]\)]\s*)",
        re.IGNORECASE,
    )

    def replace_line(line: str) -> str:
        match = colon_re.match(line) or bracket_re.match(line)
        if not match:
            return line
        prefix, name, vo, suffix = match.groups()
        mapped = _SPEAKER_LABEL_TRANSLATIONS.get(name.lower(), name)
        if name.isupper():
            mapped = _tr_upper(mapped)

        vo_text = ""
        if vo:
            is_upper = vo.isupper()
            has_dots = "." in vo
            val = "D.S." if is_upper and has_dots else "DS" if is_upper else "d.s." if has_dots else "ds"
            matched_all = match.group(0)
            vo_idx = matched_all.lower().find(vo.lower())
            vo_text = f" ({val})" if vo_idx > 0 and matched_all[vo_idx - 1] == "(" else f" {val}"

        return f"{prefix}{mapped}{vo_text}{suffix}{line[match.end():]}"

    return "\n".join(replace_line(line) for line in str(text or "").split("\n"))


def normalize_turkish_artifacts(text: str) -> str:
    """Clean small model artifacts that are invalid Turkish or malformed known names."""
    out = str(text or "")

    def fix_pronoun(match):
        return f"{match.group(1)}{match.group(2)}"

    out = re.sub(r"\b([Oo])['’](nu|na|nun|nda|ndan)\b", fix_pronoun, out)
    out = re.sub(r"\bİsrael\b", "Israel", out)
    replacements = (
        (r"\bbäýram/holidaý\s+oturylyşyğı\b", "yılbaşı partisi"),
        (r"\bbäýram/holidaý\s+oturylyşyğını\b", "yılbaşı partisini"),
        (r"\bbäýram/holidaý\s+oturylyşyğına\b", "yılbaşı partisine"),
        (r"\bbäýram/holidaý\s+oturylyşyığında\b", "yılbaşı partisinde"),
        (r"\bholidaý\s+geňlikleri\b", "tatil tuhaflıkları"),
        (r"\bholidaýlere\b", "tatillere"),
        (r"\bholidaý\b", "tatil"),
        (r"\bortadagy\s+bezeg\b", "masa süsü"),
        (r"\btaksidermiya\b", "taksidermi"),
        (r"\bavtomatonofobi\b", "otomatonofobi"),
        (r"\bventriloq\b", "ventrilok"),
        (r"\bventriloquistler['’]in\b", "ventrilokların"),
        (r"\bventriloquistler\b", "ventriloklar"),
        (r"\bk[əƏ]ll[əƏ]\b", "kelle"),
        (r"\bpatlatılmış\s+k[âa]se\b", "patlatılmış kafatası"),
        (r"\bpartlatılmış\s+k[əƏ]ll[əƏ]\b", "patlatılmış kafatası"),
        (r"\bpartlatılmış\s+kelle\b", "patlatılmış kafatası"),
        (r"\bbir\s+kelle\s+alıp\b", "bir kafatası alıp"),
        (r"\bbir\s+kelle\s+tasarlamam\b", "bir kafatası tasarlamam"),
        (r"\bchiropraktör\b", "kiropraktör"),
        (r"\bpolio\s+için\s+brasekler\b", "polio korseleri"),
        (r"\bbrasekleri\b", "korseleri"),
        (r"\bbrasekler\b", "korseler"),
        (r"\bbrasek\b", "korse"),
        (r"\benjamlary\b", "cihazlar"),
        (r"\bmortuary\s+school['’]a\b", "cenaze hizmetleri okuluna"),
        (r"\bmortuary\s+school\b", "cenaze hizmetleri okulu"),
        (r"\bwound-filler['’]ı\b", "yara dolgusunu"),
        (r"\bwound-filler\b", "yara dolgusu"),
        (r"\bwound\s+filler\b", "yara dolgusu"),
        (r"\bsideshow\s+performerı[mn]?\b", "yan gösteri sanatçısıyım"),
        (r"\bsideshow\s+performer\b", "yan gösteri sanatçısı"),
        (r"\bsideshow\s+gösterilerinde\b", "yan gösteri numaralarında"),
        (r"\bsideshow\b", "yan gösteri"),
        (r"\bbody\s+modification\s+merkez\s+parçası\b", "beden modifikasyonu parçası"),
        (r"\bbody\s+modification\b", "beden modifikasyonu"),
        (r"\bcollection['’]ında\b", "koleksiyonunda"),
        (r"\bcollection['’]ını\b", "koleksiyonunu"),
        (r"\bcollection\b", "koleksiyon"),
        (r"\brat['’]le\b", "sıçanla"),
        (r"\brat\b", "sıçan"),
        (r"\bbizim\s+bir\s+client['’]ımızın\b", "müşterilerimizden birinin"),
        (r"\bclient['’]ımızın\b", "müşterimizin"),
        (r"\bclient['’]ımız\b", "müşterimiz"),
        (r"\bclient\s+için\b", "müşterimiz için"),
        (r"\bclient\b", "müşteri"),
        (r"\bmacabre\s+mobile['’]ında\b", "ürkütücü arabasında"),
        (r"\bmacabre\s+tarzında\b", "ürkütücü/ölüm temalı"),
        (r"\bmacabre\b", "ürkütücü"),
        (r"\blukmançylyk\s+degişli\s+zatlar\b", "tıbbi şeyler"),
        (r"\bbasically\s+kanatır\b", "temelde kanatır"),
        (r"\bkoroner['’]s\s+office['’]?i\b", "adli tabip ofisini"),
        (r"\bcoroner['’]s\s+office\b", "adli tabip ofisi"),
        (r"\bcoroner['’]s\s+table\s+araçları\b", "adli tabip aletleri"),
        (r"\bcoroner['’]s\s+table\b", "adli tabip masası"),
        (r"\bcoroner['’]s\s+tools\b", "adli tabip aletleri"),
        (r"\bcoroner['’]s\s+gurney,\s*table\b", "adli tabip sedyesi, masa"),
        (r"\bcoroner['’]s\s+gurney\b", "adli tabip sedyesi"),
        (r"\bHUNTER\s+VE\s+SEÇEREK\b", "ARAŞTIRIP SEÇEREK"),
        (r"\bhunter\s+ve\s+seçerek\b", "araştırıp seçerek"),
        (r"\btuaf\b", "tuhaf"),
        (r"\byasıyoruz\b", "yaşıyoruz"),
        (r"\bclockwork\s+oreriler\b", "saat mekanizmalı gök modelleri"),
        (r"\bmekanik\s+saat\s+i(?:ş|s)i\s+oreriler\b", "mekanik saat mekanizmalı gök modelleri"),
        (r"\boreriler\b", "gök modelleri"),
        (r"\bbu\s+elektromıknatısların\s+açabiliyorum\b", "bu elektromıknatısları açabiliyorum"),
        (r"\bçok\s+düşündürücüsün,\s*dostum\b", "sağ ol, dostum"),
        (r"\bMummy parts\b", "Mumya parçaları"),
        (r"\bmummy parts\b", "mumya parçaları"),
        (r"\bbirkaç\s+ja(?:a)?lam\b", "birkaç yara izim"),
        (r"\bjaalimi\b", "yara izimi"),
        (r"\bjaalim\b", "yara izim"),
        (r"\bjaal\s+ile\b", "yara iziyle"),
        (r"\bjaal\b", "yara izi"),
        (r"\bjalam\b", "yara izim"),
        (r"\bDüğmeye\s+basma\s+beni\b", "Beni düğmeye bastırma"),
        (r"\bmummy'nin\b", "mumyanın"),
        (r"\bmummy'den\b", "mumyadan"),
        (r"\bmummy'ler\b", "mumyalar"),
        (r"\bphallus'un\b", "fallusun"),
        (r"\bphallus'u\b", "fallusu"),
        (r"\bphallus\b", "fallus"),
        (r'"devamlı müşteri"ım\b', "devamlı müşteriyim"),
        (r"\brepeat customer['’]?ım\b", "devamlı müşteriyim"),
        (r'"repeat customer"ım\b', "devamlı müşteriyim"),
        (r'\b"repeat customer"\b', "devamlı müşteri"),
        (r"\brepeat customer\b", "devamlı müşteri"),
        (r"\bauthentic\b", "gerçek"),
        (r"\beleler\b", "eller"),
        (r"\byükseltme indirebilir\b", "aparkat indirebilir"),
        (r"\btek kişi senin dedin\b", "aklıma gelen tek kişi sendin"),
        (
            r"- NOW, THE SECOND THING,\n- OTHER THAN THE DARK COLOR,",
            "- Şimdi ikinci şey,\n- koyu rengin dışında,",
        ),
        (
            r"- THAT WE WOULD NORMALLY LOOK FOR - IS\nGILDING\.\.\. SO, AS WE SEE ON THE MASK HERE,",
            "- normalde arayacağımız şey\naltın yaldızdır... Maskede gördüğümüz gibi,",
        ),
        (r"THIS APPLICATION OF GOLD LEAF\.", "Bu altın varak uygulaması."),
        (
            r"AND WE TEND TO SEE THAT ON THE\nGENITALIA, ON BOTH OF MALES AND FEMALES\.",
            "Bunu genelde hem erkeklerde hem kadınlarda\ngenital bölgede görürüz.",
        ),
        (r"ON THE ACTUAL MUMMY ITSELF\?", "Gerçek mumyanın üzerinde mi?"),
        (r"ON THE ACTUAL mumya ITSELF\?", "Gerçek mumyanın üzerinde mi?"),
        (r"ON THE LINEN WRAPPINGS\.", "Keten sargılarda."),
        (
            r"SO WE WOULD EXPECT TO SEE\nIT ON SOMETHING LIKE THIS\.",
            "Böyle bir şeyde de\nonu görmeyi beklerdik.",
        ),
        (r"\bMINICIK,\s*TINY\b", "MİNİCİK"),
        (r"\bminicik,\s*tiny\b", "minicik"),
        (r"\bKAFATLARI\b", "KAFATASLARI"),
        (r"\bkafatları\b", "kafatasları"),
        (r"\bbäseke\s+işi\b", "yarışma parçası"),
        (r"\bbäseke\b", "yarışma"),
    )
    for pattern, replacement in replacements:
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)
    out = re.sub(r"\byada\b", "ya da", out)
    return out


def _src_is_real_dialogue(src_text: str) -> bool:
    """Kaynak satır gerçek diyalog mu (boş/SFX-only DEĞİL)."""
    s = str(src_text or "").strip()
    return bool(s) and not is_sdh_only(s)


def _is_translation_failure_marker(text: str) -> bool:
    value = str(text or "").strip()
    return value.startswith("[HATA") or value == "[ÇEVİRİ EKSİK]"


# ── Kaynak-güdümlü yapısal SFX tespiti ──────────────────────────────────────
# Beyaz liste sorgulamaz: ayırt edici işaret parantezin/köşeli parantezin
# KENDİSİ, içindeki kelimeler değil. clean_sdh çeviriden SONRA çalıştığı için
# Türkçeleşmiş etiketleri (ör. "[ÇAN SESLERİ]") beyaz liste tanımayabiliyor;
# bu yol kaynağa (henüz çevrilmemiş İngilizce metne) bakarak karar verir.
# Karakter kümesi baştan sona işaret olduğu için harf içeremez; ¶ burada
# güvenle nota sayılır (gerekçe: _STRUCTURAL_NOTES_RE'nin üstündeki not).
SFX_ONLY_STRUCTURAL_RE = re.compile(
    r'^(?:\([^)]*\)|\[[^\]]*\]|[#¶♪♫♬♩_\s]+)+$')
_VTT_VOICE_TAG_RE = re.compile(r'(?:<v(?:\s+[^>]*)?>|</v>)', re.IGNORECASE)
_BARE_FRENCH_SDH_RE = re.compile(
    r"^(?:"
    r"musique(?:\s+(?:douce|joyeuse|gaie|triste|melancolique|rythmee|"
    r"instrumentale|populaire|inquietante|d'intrigue|intrigante|"
    r"de\s+bal|au\s+piano|au\s+violon)){1,4}|"
    r"on\s+frappe|(?:une?|la)\s+porte\s+s'ouvre|"
    r"(?:il|elle)\s+soupire|rire\s+nerveux"
    r")[.!…]?\s*$",
    re.IGNORECASE,
)
_BARE_CYRILLIC_SDH_RE = re.compile(r"^музыка[.!…]?\s*$", re.IGNORECASE)


def _src_is_bare_sdh_line(src_text: str) -> bool:
    value = re.sub(r"<[^>\n]+>", "", str(src_text or ""))
    return bool(_BARE_FRENCH_SDH_RE.fullmatch(_ascii_fold(value).strip()))


def src_is_sfx_only(src_text: str, allow_caps_heuristic: bool = False) -> bool:
    """Kaynak cue'su tamamen parantez/köşeli parantez/nota mı (gerçek diyalog
    kelimesi YOK)? Boş kaynak SFX-only sayılmaz — bkz. _src_is_real_dialogue.

    allow_caps_heuristic=True ise parantezsiz, tamamı büyük harfli ve cümle
    noktalamasıyla bitmeyen etiketler de (Kiril 'ВОЙ СИРЕНЫ' dahil) SFX sayılır.
    Bu yalnız kaynağın TAMAMI büyük harf OLMAYAN dosyalarda güvenlidir; kararı
    çağıran taraf dosya düzeyinde verir."""
    text = _strip_mojibake_music_ornament(
        re.sub(r'\{\\[^}]*\}', '', str(src_text or '')))
    text = _VTT_VOICE_TAG_RE.sub('', text)
    text = FORMAT_TAG_RE.sub('', text)
    text = CHEVRON_SPEAKER_RE.sub("", text).strip()
    text = re.sub(r"(?m)^\s*[-–—]\s*(?=[\[(#])", "", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    if not text:
        return False
    if _BARE_CYRILLIC_SDH_RE.fullmatch(text):
        return True
    if allow_caps_heuristic and is_structural_sdh_label(text):
        return True
    if _src_is_bare_sdh_line(text):
        return True
    spans = _bracket_group_spans(text)
    residue = _replace_bracket_groups(text, lambda _raw: "")
    residue = MUSIC_NOTE_RE.sub("", residue).replace("_", "").replace("#", "").strip()
    residue = residue.strip(" .,!?:;…")
    if not spans:
        return bool(SFX_ONLY_STRUCTURAL_RE.match(text))
    if residue:
        return bool(MUSIC_NOTE_RE.search(text)) and not residue
    has_descriptor_group = any(
        is_sdh_descriptor(text[start + 1:end - 1].strip())
        for start, end in spans
    )
    for start, end in spans:
        raw = text[start:end]
        inner = raw[1:-1].strip()
        if re.match(r'^#\s*(?:["“‘\']|(?:theme|music|song)\b)', inner, re.I):
            continue
        colon_follows = text[end:].lstrip().startswith(":")
        # Salt nota taşıyan grup ('[ ♪♪♪ ]') ne betimleyici ne konuşmacıdır,
        # bu yüzden reddediliyordu; oysa çıplak hâli ('♪♪♪') SFX sayılıyor.
        # 300 gerçek kaynakta 6 dosyanın 211 cue'su bu yüzden "çeviri eksik"
        # işaretlenip dosyaları partial bıraktı (How We Got to Now S01E01-06).
        if (MUSIC_NOTE_RE.search(inner)
                and not re.search(r"[^\W_]", MUSIC_NOTE_RE.sub("", inner))):
            continue
        # Parantez içi BAŞTAN SONA büyük harf Latin ise etiket olduğu
        # biçiminden bellidir; sözlükte olmasına gerek yok. Betimleyici
        # sözlüğü gerçek dil adlarıyla çalıştığı için genel ifadeleri
        # ('SPEAKING NATIVE LANGUAGE'), 'IN' biçimini ('SPEAKING IN
        # GEORGIAN') ve listede olmayan ses sözcüklerini ('SHEEP BAAS',
        # 'SNAPS FINGERS') kaçırıyordu.
        #
        # Latin DIŞI içerik bilerek dışarıda: '[東京都庁]' gibi gerçek ekran
        # tabelaları o yolda korunuyor (denetim 2026-08-21, madde 38).
        if _is_speech_activity_label(inner):
            continue
        is_descriptor = is_sdh_descriptor(inner)
        is_speaker = _is_speaker_name(inner, colon_follows=colon_follows)
        if (is_speaker and not colon_follows and len(spans) > 1
                and has_descriptor_group and not is_descriptor):
            return False
        if not (is_descriptor or is_speaker):
            return False
    return True


_DASH_ONLY_LINE_RE = re.compile(r'^[-–—]\s*$')
_ORPHANED_LABEL_COLON_RE = re.compile(r'^(\s*[-–—]?\s*):\s*')
_SRC_NARRATOR_LABEL_RE = re.compile(
    r'(?:(?:&gt;|>){2})\s*Narrator\s*:', re.IGNORECASE
)
_TR_NARRATOR_LABEL_RE = re.compile(
    r'\b(?:Narrator|Anlatıcı|Anlatici)\s*:\s*', re.IGNORECASE
)
_HEADING_LABEL_PATTERNS = (
    re.compile(r"^\s*(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:chapter|episode|part|act|scene|season|book|volume|b\u00f6l\u00fcm|kisim|k\u0131s\u0131m|sahne|sezon|cilt)\s*(?:\d+|[ivxlcdm]+|one|two|three|four|five|six|seven|eight|nine|ten)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:breaking news|news flash|special report|live report|son dakika|son dakika haberi)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:location|date|time|konum|tarih|saat|note|warning|caution|notice|disclaimer)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:solution|destination|çözüm|varış\s+noktası)\s*$", re.IGNORECASE),
    re.compile(
        r"^\s*(?:problem|result|outcome|step|rule|question|answer|example"
        r"|summary|tip|goal|method|status|objective|purpose|conclusion"
        r"|sonuç|adım|kural|soru|cevap|yanıt|örnek|özet|ipucu|amaç|hedef"
        r"|yöntem|durum|çıkarım)\s*(?:\d+|[ivxlcdm]+)?\s*$",
        re.IGNORECASE),
    re.compile(r"^\s*(?:esteemed\s+sir|dear\s+sir|your\s+honou?r|superior\s+court)\s*$", re.IGNORECASE),
)


def _is_heading_label(label_text: str) -> bool:
    clean = str(label_text or "").strip()
    return any(p.match(clean) for p in _HEADING_LABEL_PATTERNS)


def _src_has_plain_speaker_label(src_line: str) -> bool:
    src_line = FORMAT_TAG_RE.sub("", str(src_line or ""))
    m = _SRC_PLAIN_SPEAKER_LABEL_RE.search(src_line)
    if not m:
        return False
    matched_text = m.group(0).rstrip(":\n\r\t ")
    label = re.sub(r"^\s*-\s*", "", matched_text).strip()
    if m.start() > 0 and src_line[:m.start()].strip() and label.casefold() == "listen":
        return False
    if label.casefold() in {"translation", "translator"}:
        return False
    if len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", label)) > 4:
        return False
    return not _is_heading_label(label)


_SRC_PLAIN_SPEAKER_LABEL_RE = re.compile(
    r"(?m)(?:^|(?<=[.!?…]))\s*(?:(?:>>|&gt;&gt;)\s*)?(?:-\s*)?"
    r"(?:[A-Z][A-Z0-9 .'\-]{1,30}(?:,\s*(?:VOICE[- ]OVER|V\.?O\.?))?|"
    r"[A-Z][a-z]+(?:[-'][A-Za-z][a-z]*)?(?:\s+[A-Z][a-z]+(?:[-'][A-Za-z][a-z]*)?){0,2})"
    r"(?:\s*\((?:OFFSCREEN|ONSCREEN|O\.?S\.?|V\.?O\.?)\))?:\s*"
)
# Konuşmacı/dış ses etiketleri yalnız Türkçe harf kümesiyle aranınca Almanca
# (ERZÄHLER:), Fransızca (NARRATEUR:) ve İspanyolca (NARRADOR:) etiketleri son
# altyazıda kalıyordu: harf sınıfları Latin aksanlarını, dış ses ekleri de
# yabancı karşılıklarını kapsar.
_UPPER_LETTER = r"A-ZÇĞİÖŞÜÀ-ÖØ-Þ"
_ANY_LETTER = r"A-Za-zÇĞİÖŞÜçğıöşüÀ-ÖØ-öø-ÿ"
_VOICE_OVER_ALT = (
    r"SES ÜSTÜ|DIŞ SES|ANLATICI|V\.?O\.?|VOICE[- ]OVER|OFF|AUS DEM OFF|"
    r"ERZÄHLER(?:IN)?|VOIX OFF|EN OFF|FUERA DE CAMPO|VOCE FUORI CAMPO"
)
_TR_PLAIN_SPEAKER_LABEL_RE = re.compile(
    r"(?m)(^|(?<=[.!?…]))(\s*(?:-\s*)?)"
    rf"(?:[{_UPPER_LETTER}][{_ANY_LETTER}0-9 .'\-]{{1,30}}"
    rf"(?:,\s*(?:{_VOICE_OVER_ALT}))?:\s*(?=\S)|"
    rf"[{_UPPER_LETTER}][{_UPPER_LETTER}0-9 .'\-]{{1,30}}"
    rf"(?:,\s*(?:{_VOICE_OVER_ALT}))?:\s*$)"
)
_TR_LABEL_ONLY_RE = re.compile(
    rf"^\s*(?:-\s*)?[{_UPPER_LETTER}][{_ANY_LETTER}0-9 .'\-]{{1,30}}"
    rf"(?:,\s*(?:{_VOICE_OVER_ALT}))?:\s*$")
_TR_PLAIN_SPEAKER_LABEL_CAPTURE_RE = re.compile(
    r"(?m)(?:^|(?<=[.!?…]))\s*(?:-\s*)?"
    rf"(?P<label>[{_UPPER_LETTER}][{_ANY_LETTER}0-9 .'\-]{{1,30}}"
    rf"(?:,\s*(?:{_VOICE_OVER_ALT}))?):\s*(?=\S)")
_SRC_BRACKET_SPEAKER_PREFIX_RE = re.compile(
    r"(?m)^\s*(?:-\s*)?\[[^\]\n]{1,40}\]\s*"
)
_SRC_MALFORMED_BRACKET_SPEAKER_PREFIX_RE = re.compile(
    r"(?mi)^\s*(?:-\s*)?['\"“]?(?P<label>[A-Z][A-Za-z'\-]{1,30})\]\s+(?=\S)"
)
_SRC_PIPE_SPEAKER_PREFIX_RE = re.compile(
    r"(?mi)^\s*(?:-\s*)?(?P<label>[A-Z][A-Za-z'\-]{1,30})\|+\s+(?=\S)"
)
_SRC_QUOTED_SPEAKER_PREFIX_RE = re.compile(
    r"(?mi)^\s*(?:-\s*)?[A-Z][A-Za-z'\-]*"
    r"(?:\s+[A-Z][A-Za-z'\-]*){0,2},\s*[\"“]"
)


def _target_is_source_speaker_label_only(tr_line: str, src_line: str) -> bool:
    tr_plain = FORMAT_TAG_RE.sub("", str(tr_line or ""))
    src_plain = FORMAT_TAG_RE.sub("", str(src_line or ""))
    if not _TR_LABEL_ONLY_RE.fullmatch(tr_plain):
        return False
    source_match = _SRC_PLAIN_SPEAKER_LABEL_RE.search(src_plain)
    if not source_match:
        return False
    source_label = source_match.group(0).strip().lstrip("-").rstrip(":").strip()
    target_label = tr_plain.strip().lstrip("-").rstrip(":").strip()
    source_key = _plain_speaker_label_key(source_label)
    target_key = _plain_speaker_label_key(target_label)
    mapped = _SPEAKER_LABEL_TRANSLATIONS.get(source_key, source_label)
    return target_key in {source_key, _plain_speaker_label_key(mapped)}


def _plain_speaker_label_key(value: str) -> str:
    value = re.sub(r"^\s*(?:(?:>>|&gt;&gt;)\s*)?-?\s*", "", str(value or ""))
    value = re.sub(
        r"\s*\((?:OFFSCREEN|ONSCREEN|O\.?S\.?|V\.?O\.?)\)\s*$",
        "", value, flags=re.IGNORECASE)
    value = re.sub(
        r",\s*(?:VOICE[- ]OVER|V\.?O\.?|VO|SES ÜSTÜ|DIŞ SES)\s*$",
        "", value, flags=re.IGNORECASE)
    return _ascii_fold(value.strip().rstrip(":").strip())


def _target_has_source_plain_speaker_label(tr_line: str, src_line: str) -> bool:
    source_match = _SRC_PLAIN_SPEAKER_LABEL_RE.search(
        FORMAT_TAG_RE.sub("", str(src_line or "")))
    target_match = _TR_PLAIN_SPEAKER_LABEL_CAPTURE_RE.search(
        FORMAT_TAG_RE.sub("", str(tr_line or "")))
    if not source_match or not target_match:
        return False
    source_label = source_match.group(0).strip().lstrip("-").rstrip(":").strip()
    target_label = target_match.group("label").strip()
    source_key = _plain_speaker_label_key(source_label)
    target_key = _plain_speaker_label_key(target_label)
    mapped_key = _plain_speaker_label_key(
        _SPEAKER_LABEL_TRANSLATIONS.get(source_key, source_label))
    aliases = {
        "news anchor": {"haber sunucusu", "haber spikeri"},
        "both": {"ikisi birlikte", "ikisi"},
        "recording": {"kayit"},
    }
    if re.search(
            r"\((?:OFFSCREEN|ONSCREEN|O\.?S\.?|V\.?O\.?)\)\s*$",
            source_label, re.IGNORECASE):
        return True
    return target_key in {source_key, mapped_key, *aliases.get(source_key, set())}


def _strip_target_source_plain_speaker_label(tr_line: str, src_line: str) -> str:
    if not _target_has_source_plain_speaker_label(tr_line, src_line):
        return tr_line
    target_plain = FORMAT_TAG_RE.sub("", str(tr_line or ""))
    target_match = _TR_PLAIN_SPEAKER_LABEL_CAPTURE_RE.search(target_plain)
    if not target_match:
        return tr_line
    label = re.escape(target_match.group("label").strip())
    tag = r"</?(?:i|b|u|font)\b[^>]*>"
    pattern = re.compile(
        rf"(?m)(^|(?<=[.!?…]))(?P<prefix>\s*(?:{tag}\s*)*(?:-\s*)?)"
        rf"{label}:\s*(?=\S)")
    return pattern.sub(r"\1\g<prefix>", tr_line, count=1)


def _source_ocr_speaker_prefix(src_line: str):
    """Return a source-confirmed OCR-damaged speaker prefix, if present."""
    plain = FORMAT_TAG_RE.sub("", str(src_line or ""))
    for kind, pattern in (
            ("bracket", _SRC_MALFORMED_BRACKET_SPEAKER_PREFIX_RE),
            ("pipe", _SRC_PIPE_SPEAKER_PREFIX_RE)):
        match = pattern.search(plain)
        if match:
            return kind, match.group("label")
    return None


def _target_has_source_ocr_speaker_prefix(tr_line: str, src_line: str) -> bool:
    found = _source_ocr_speaker_prefix(src_line)
    if not found:
        return False
    kind, label = found
    plain = FORMAT_TAG_RE.sub("", str(tr_line or ""))
    escaped = re.escape(label)
    if kind == "bracket":
        pattern = rf"(?mi)^\s*(?:-\s*)?['\"“]?\[?{escaped}\]\s+(?=\S)"
    else:
        pattern = rf"(?mi)^\s*(?:-\s*)?{escaped}\|+\s+(?=\S)"
    return bool(re.search(pattern, plain, re.IGNORECASE))


def _strip_target_source_ocr_speaker_prefix(tr_line: str, src_line: str) -> str:
    found = _source_ocr_speaker_prefix(src_line)
    if not found:
        return tr_line
    kind, label = found
    escaped = re.escape(label)
    tag = r"</?(?:i|b|u|font)\b[^>]*>"
    if kind == "bracket":
        label_pattern = rf"['\"“]?\[?{escaped}\]"
    else:
        label_pattern = rf"{escaped}\|+"
    pattern = re.compile(
        rf"(?mi)(^|(?<=[.!?…]))(?P<prefix>\s*(?:{tag}\s*)*(?:-\s*)?)"
        rf"{label_pattern}\s+(?=\S)")
    return pattern.sub(r"\1\g<prefix>", str(tr_line or ""), count=1)


def _has_bracket_speaker_prefix(text: str) -> bool:
    plain = FORMAT_TAG_RE.sub("", str(text or ""))
    return bool(re.search(
        r"(?m)^\s*(?:-\s*)?\[[^\]\n]{1,40}\]\s*(?=\S)", plain))


def _target_has_source_bracket_speaker_prefix(tr_line: str, src_line: str) -> bool:
    """Whether a source-leading bracket label also survived in the target."""
    return _has_bracket_speaker_prefix(src_line) and _has_bracket_speaker_prefix(tr_line)


def _same_line_structural_speaker_label(content: str) -> bool:
    """Strong speaker evidence for ``[label] dialogue`` on the same line.

    A bracket prefix alone is not enough: ``[Soft Power] A documentary.`` and
    ``[Sesame Street] is a show.`` contain visible title text.  Single-token
    names/roles and caption qualifiers such as ``Bill, sarcastically`` or
    ``Buck on radio`` are speaker labels; ambiguous multiword title case is
    preserved.
    """
    value = str(content or "").strip()
    if not value or _is_heading_label(value):
        return False
    if re.fullmatch(r"[A-Za-z][A-Za-z'\-]{1,30}", value):
        return True
    return bool(re.fullmatch(
        r"[A-Za-z][A-Za-z'\-]{1,30}"
        r"(?:\s+[A-Za-z][A-Za-z'\-]{1,30}){0,2}"
        r"(?:\s*,\s*(?:sarcastically|whispering|shouting|laughing|"
        r"crying|angrily|softly|quietly)|\s+(?:on|over)\s+(?:radio|tv)|"
        r"\s+(?:voice[- ]?over|off[- ]?screen))",
        value, re.IGNORECASE))


def strip_labels_by_source(tr_line: str, src_line: str) -> str:
    """Kaynak satırında (cue'nun kaynak metninde) parantez/köşeli grup VARSA,
    çeviri satırındaki tüm parantez/köşeli gruplarını sök (kalan repliği bırak).
    Kaynakta grup YOKSA çeviriye DOKUNMA — parantez orada gerçek nesir olabilir.

    '<i>'/'<b>' gibi biçim etiketlerine hiç dokunulmaz (bracket tarayıcı zaten
    '<>' içeriğini eşlemiyor — strip_sdh_line'ın aksine format-tag sökme adımı
    burada hiç çalıştırılmaz). '- ' diyalog tiresi korunur; etiket sökülünce
    satırda yalnızca '-'/'- ' kalıyorsa satır boş sayılır (tek başına tire
    ekrana sızmasın).

    Model çoğu zaman '[Name]: metin' biçimini ham çeviride aynen koruyor;
    bracket sökülünce '[Name]' gider ama ':' satır başında sarkık kalır
    (ör. '[Caine]: Hoş geldin' -> ': Hoş geldin'). Bu artık etiketin bir
    parçası, gerçek noktalama değil — bracket sökümünden HEMEN SONRA temizlenir
    (dış boşluk kırpımından önce, aksi halde '- :' gibi ara boşluklu varyantlar
    kaçar)."""
    tr_line = CHEVRON_SPEAKER_RE.sub("", str(tr_line or ""))
    src_line = str(src_line or "")
    tr_line = _strip_target_source_ocr_speaker_prefix(tr_line, src_line)
    if _SRC_NARRATOR_LABEL_RE.search(src_line):
        tr_line = _TR_NARRATOR_LABEL_RE.sub("", tr_line)
    plain_source_label = _src_has_plain_speaker_label(src_line)
    bracket_or_quoted_source = bool(
        _SRC_BRACKET_SPEAKER_PREFIX_RE.search(src_line)
        or _SRC_QUOTED_SPEAKER_PREFIX_RE.search(src_line))
    if plain_source_label or bracket_or_quoted_source:
        if (plain_source_label
                and _target_is_source_speaker_label_only(tr_line, src_line)):
            return ""
        if (bracket_or_quoted_source
                or _target_has_source_plain_speaker_label(tr_line, src_line)):
            stripped = _TR_PLAIN_SPEAKER_LABEL_RE.sub(r"\1\2", tr_line)
            tr_line = _strip_target_source_plain_speaker_label(
                stripped, src_line)
        if _DASH_ONLY_LINE_RE.match(tr_line.strip()):
            return ""
    source_spans = _bracket_group_spans(src_line)
    source_has_descriptor = any(
        is_sdh_descriptor(src_line[start + 1:end - 1].strip())
        for start, end in source_spans
    )
    source_groups = []
    source_remove_flags = []
    source_has_unverified_group = False
    for start, end in source_spans:
        raw = src_line[start:end]
        inner = raw[1:-1].strip()
        colon_follows = src_line[end:].lstrip().startswith(":")
        is_descriptor = is_sdh_descriptor(inner)
        is_speaker = _is_speaker_name(inner, colon_follows=colon_follows)
        followed_by_dialogue = bool(
            src_line[end:].lstrip()
            and not src_line[end:].lstrip().startswith(("[", "(")))
        source_prefix = FORMAT_TAG_RE.sub("", src_line[:start])
        source_prefix = re.sub(r"^\s*-\s*", "", source_prefix)
        structural_speaker = (
            not source_prefix.strip()
            and (bool(re.match(r"\s*\r?\n", src_line[end:]))
                 or (followed_by_dialogue
                     and _same_line_structural_speaker_label(inner)))
            and not _is_heading_label(inner)
        )
        ambiguous_mixed_label = (
            is_speaker and not colon_follows and len(source_spans) > 1
            and source_has_descriptor and not is_descriptor
            and not followed_by_dialogue
        )
        if (is_descriptor or is_speaker or structural_speaker) and not ambiguous_mixed_label:
            source_groups.append(raw)
            source_remove_flags.append(True)
        else:
            source_has_unverified_group = True
            source_remove_flags.append(False)
    if not source_groups:
        return tr_line
    target_spans = _bracket_group_spans(tr_line)
    source_delimiters = [src_line[start] for start, _end in source_spans]
    target_delimiters = [tr_line[start] for start, _end in target_spans]
    positional_flags = (
        source_remove_flags
        if (len(target_spans) == len(source_remove_flags)
            and target_delimiters == source_delimiters)
        else None
    )
    target_group_pos = 0
    def _strip_verified(raw):
        nonlocal target_group_pos
        if positional_flags is not None:
            remove = positional_flags[target_group_pos]
            target_group_pos += 1
            return "" if remove else raw
        inner = raw[1:-1].strip()
        if _is_protected_bracket_content(raw):
            return raw
        if not is_sdh_descriptor(inner) and not _is_speaker_name(inner):
            return raw
        return ""
    stripped = _replace_bracket_groups(tr_line, _strip_verified)
    stripped = _ORPHANED_LABEL_COLON_RE.sub(r"\1", stripped)
    stripped = re.sub(r"\s{2,}", " ", stripped).strip()
    if _DASH_ONLY_LINE_RE.match(FORMAT_TAG_RE.sub("", stripped)):
        return "".join(re.findall(r"</(?:i|b|u|font)\s*>", stripped, re.I))
    return stripped


def _source_has_split_speaker_prefix(src_text: str) -> bool:
    lines = str(src_text or "").splitlines()
    if len(lines) < 2:
        return False
    first = lines[0].strip()
    bracketed = re.fullmatch(r"[\[(]([^\])\n]{1,40})[\])]", first)
    if bracketed and not _is_heading_label(bracketed.group(1)):
        return True
    letters = [ch for ch in first if ch.isalpha()]
    if not letters or len(first) > 40 or not all(ch.isupper() for ch in letters):
        return False
    second = lines[1].lstrip()
    if _src_has_plain_speaker_label(second):
        return True
    m = re.match(r"^\(([^)\n]{1,40})\)\s*:?", second)
    return bool(m and is_sdh_descriptor(m.group(1)))


def _strip_split_speaker_prefix(tr_text: str, src_text: str) -> str:
    if not _source_has_split_speaker_prefix(src_text):
        return tr_text
    lines = str(tr_text or "").splitlines()
    if not lines:
        return tr_text
    first = lines[0].strip()
    bracketed = re.fullmatch(r"[\[(]([^\])\n]{1,40})[\])]", first)
    if bracketed and not _is_heading_label(bracketed.group(1)):
        return "\n".join(lines[1:])
    letters = [ch for ch in first if ch.isalpha()]
    if (letters and len(first) <= 40
            and all(ch.isupper() for ch in letters)
            and not re.search(r"[.!?…]$", first)):
        remainder = "\n".join(lines[1:])
        src_remainder = "\n".join(str(src_text or "").splitlines()[1:])
        if ":" in src_remainder:
            trailing = src_remainder.split(":", 1)[1]
            if (src_is_sfx_only(trailing)
                    or re.fullmatch(
                        r"\s*(?:\([^)\n]+\)|\[[^\]\n]+\])\s*", trailing
                    )):
                return ""
        return remainder
    return tr_text


def clean_sdh_blocks(blocks, src_map=None, source_driven=False):
    """src_map verilirse {idx_str: kaynak_metin}: çevirisi boş gelen bir cue YALNIZCA
    kaynağı gerçek diyalogsa korunur (modelce atlanmış gerçek repliğin sessizce
    silinmesini önler — bkz. plans/s04e12-cue-shift-without-repair-brief.md Görev 6);
    kaynağı ZATEN boş/SFX olan cue'lar düşürülür (aksi hâlde kaynak-boş cue'lar ekranda
    [ÇEVİRİ EKSİK] olarak görünür). src_map verilmezse boş cue'lar düşürülür (güvenli
    eski davranış — atlanmış gerçek replikleri o durumda dedektör yakalar).

    source_driven=True VE src_map verilmişse, doldurulmuş (boş olmayan) cue'lar için
    KAYNAK-GÜDÜMLÜ YAPISAL tespit kullanılır (beyaz liste hiç sorgulanmaz):
      1. Kaynak cue'su tamamen parantez/köşeli/nota ise (src_is_sfx_only) → cue düşürülür.
      2. Değilse, cue'nun her satırı için strip_labels_by_source(line, kaynak_metni)
         çağrılır — kaynakta parantez/köşeli grup varsa çeviridekiler sökülür, yoksa
         çeviriye dokunulmaz.
      3. Tüm satırlar boşaldıysa cue düşürülür.
    source_driven=False (varsayılan) → eski beyaz-liste tabanlı davranış (strip_sdh_line)
    aynen korunur; mevcut testler bu yoldan etkilenmez."""
    result = []
    for idx, ts, text in blocks:
        original = str(text or "")
        src_text = src_map.get(str(idx), "") if src_map is not None else ""
        if not original.strip():
            if src_map is not None and _src_is_real_dialogue(src_text):
                # Kaynağı gerçek diyalog ama çeviri boş → SESSİZCE SİLME, koru ki
                # sonraki _repair_untranslated_sync doğru kaynakla yeniden çevirsin.
                result.append((idx, ts, text))
            # else: kaynak boş/SFX ya da src_map yok → düşür (eski güvenli davranış)
            continue
        if source_driven and src_map is not None:
            if _is_translation_failure_marker(original):
                if _src_is_real_dialogue(src_text):
                    result.append((idx, ts, text))
                continue
            if src_is_sfx_only(src_text):
                continue
            original = _strip_split_speaker_prefix(original, src_text)
            lines = []
            target_lines = original.split("\n")
            source_lines = str(src_text or "").split("\n")
            aligned_source = (
                source_lines if len(source_lines) == len(target_lines)
                else [src_text] * len(target_lines)
            )
            for line, source_line in zip(target_lines, aligned_source):
                if _src_is_bare_sdh_line(source_line):
                    continue
                cleaned = strip_labels_by_source(line, source_line)
                if cleaned:
                    lines.append(cleaned)
            if lines:
                joined = "\n".join(lines)
                joined = re.sub(
                    r"\n+(</(?:i|b|u|font)\s*>)", r"\1", joined,
                    flags=re.IGNORECASE)
                result.append((idx, ts, joined))
            continue
        lines = []
        for line in original.split("\n"):
            cleaned = strip_sdh_line(line)
            if cleaned:
                lines.append(cleaned)
        if lines:
            result.append((idx, ts, "\n".join(lines)))
    return result


_STRUCTURAL_MARKUP_RE = re.compile(r"<[^>\n]+>|\{[^{}\n]*\}")
_STRUCTURAL_BRACKETS_RE = re.compile(r"^(?:\s*[\[(][^\[\]()]*[\])]\s*)+$")
# \u00b6 (\u00b6) KASITLI: EIA-608/SCC k\u00f6kenli altyaz\u0131larda nota karakteri \u00b6 olarak
# yaz\u0131l\u0131yor ('black market' S01E06: 34 \u00b6, hi\u00e7 \u266a yok). YALNIZ bu "ba\u015ftan sona
# nota" kal\u0131plar\u0131na eklenir \u2014 \u00b6 genel nota k\u00fcmesine (MUSIC_NOTE_RE) girerse
# mojibake dosyalarda ger\u00e7ek harf silinir: 'Gy\u00c3\u00b6rgy' i\u00e7indeki \u00b6, \u00f6'n\u00fcn ikinci
# bayt\u0131d\u0131r (ar\u015fivde \u00f6l\u00e7\u00fcld\u00fc: \u00b6 ge\u00e7en 80 cue'nun 12'si bu \u015fekilde).
_STRUCTURAL_NOTES_RE = re.compile(r"^[\s\u00b6\u266a\u266b\u266c\u2669]+$")


def is_structural_sdh_cue(text, allow_caps_heuristic: bool = True) -> bool:
    """Cue BÜTÜNÜYLE bir SDH etiketi mi — yani gramatik bir cümlenin üyesi olamaz mı?

    `[Prayer]`, `[Baby crying]`, `EXPLOSION`, `♪♪` gibi cue'lar noktayla
    kapanmadıkları için cümle parçası sanılıyor ve peşlerindeki gerçek
    konuşmayı aynı "cümle" grubuna çekiyorlardı; model o grubu tek cümle
    sanıp anlamı ID'ler arasında dağıtabiliyor, sonra SDH temizliği
    etiketi silince taşınan içerik de gidiyordu.

    `allow_caps_heuristic` kararını ÇAĞIRAN dosya düzeyinde verir: baştan
    sona büyük harfle yazılmış bir kaynakta caps sinyali hiçbir şeyi ayırt
    etmez ve gerçek replikleri etiket sanar.
    """
    flat = _STRUCTURAL_MARKUP_RE.sub("", str(text or ""))
    flat = re.sub(r"\s+", " ", flat).strip()
    if not flat:
        return False
    if _STRUCTURAL_BRACKETS_RE.match(flat) or _STRUCTURAL_NOTES_RE.match(flat):
        return True
    return bool(src_is_sfx_only(text, allow_caps_heuristic=allow_caps_heuristic))


def caps_heuristic_allowed(texts, threshold: float = 0.60) -> bool:
    """Bu dosyada 'tamamı büyük harf = SDH etiketi' sinyaline güvenilir mi?

    ABD kapalı-altyazı kaynakları baştan sona büyük harfle yazılır; orada
    caps hiçbir şeyi ayırt etmez ve her replik etiket sanılır. Karar dosya
    düzeyinde bir kez verilir ve etiket temizliği, ekran yazısı sezgisi ve
    cümle gruplaması AYNI yanıtı kullanmalıdır — üç yerde ayrı eşik olunca
    aradaki dosyalarda birbirine ters karar veriyorlardı (ölçülen bir vaka
    %78,3 oranla tam iki eşiğin arasına düşüyordu).

    Biçim etiketi harf sayılmaz: `<i>` bir küçük 'i' getirip tamamı büyük
    harfli bir cue'yu karışık harfli gösteriyordu.
    """
    total = 0
    caps = 0
    for text in texts:
        value = _STRUCTURAL_MARKUP_RE.sub("", str(text or "")).strip()
        letters = [char for char in value if char.isalpha()]
        if len(letters) < 4:
            continue
        total += 1
        if all(char.isupper() for char in letters):
            caps += 1
    if total < 8:
        return False
    return (caps / total) <= threshold
