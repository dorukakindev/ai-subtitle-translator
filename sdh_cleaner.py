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


def _has_bracket_group(text: str) -> bool:
    return bool(_bracket_group_spans(text))

_SDH_KEYWORDS = {
    # English hearing-impaired captions
    "applause", "applauding", "cheering", "cheers", "booing",
    "laugh", "laughs", "laughing", "laughter", "chuckle", "chuckles",
    "chuckling", "giggle", "giggles", "giggling",
    "sigh", "sighs", "sighing", "gasp", "gasps", "gasping",
    "exhale", "exhales", "exhaling", "inhale", "inhales", "inhaling",
    "groan", "groans", "groaning", "moan", "moans", "moaning",
    "scream", "screams", "screaming", "crying", "cries", "sobbing",
    "sniffles", "cough", "coughs", "coughing", "sneeze", "sneezes",
    "breathing", "panting", "grunting", "whisper", "whispers",
    "whispering", "murmur", "murmurs", "murmuring", "chanting",
    "music", "song", "singing", "sings", "plays", "playing",
    "tense", "dramatic", "ominous", "somber", "upbeat", "soft",
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
    "rumbles", "heavily",
}

_SPEAKER_WORDS = {
    "man", "woman", "male", "female", "boy", "girl", "child", "kid",
    "narrator", "announcer", "speaker", "voice", "voiceover", "interviewer",
    "host", "reporter", "crowd", "sheriff", "deputy", "sergeant",
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
    "play", "tolling", "beating", "jingle", "blasts",
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


def is_sdh_descriptor(content: str, bare_text: bool = False) -> bool:
    key = _descriptor_key(content)
    if not key:
        return True
    if _is_heading_label(content):
        return False
    raw_words = str(content or "").strip().split()
    title_case = (2 <= len(raw_words) <= 6
                  and any(any(ch.islower() for ch in word) for word in raw_words)
                  and all(not word[:1].isalpha() or word[:1].isupper()
                          for word in raw_words))
    if title_case:
        first_key = _descriptor_key(raw_words[0])
        last_key = _descriptor_key(raw_words[-1])
        if (first_key not in _SPEAKER_WORDS
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
            "on tv", "on recording", "together", "clears throat"}:
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
        if colon_follows or is_sdh_descriptor(inner) or _is_speaker_name(inner, colon_follows):
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

    def replace_descriptor(raw):
        inner = raw[1:-1]
        return "" if is_sdh_descriptor(inner) else raw

    line = _replace_bracket_groups(line, replace_descriptor)
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
    if not text or EMPTY_DASH_RE.match(text):
        return True

    had_bracket_group = _has_bracket_group(text)
    stripped = _replace_bracket_groups(
        text, lambda raw: "" if is_sdh_descriptor(raw[1:-1]) else raw)
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
# subtitle_translator_gui._SDH_ONLY_SRC_RE ile aynı desen (bilinçli tekrar —
# sdh_cleaner.py, gui modülüne bağımlı olmamalı).
SFX_ONLY_STRUCTURAL_RE = re.compile(r'^(?:\([^)]*\)|\[[^\]]*\]|[♪_\s]+)+$')
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


def src_is_sfx_only(src_text: str) -> bool:
    """Kaynak cue'su tamamen parantez/köşeli parantez/nota mı (gerçek diyalog
    kelimesi YOK)? Boş kaynak SFX-only sayılmaz — bkz. _src_is_real_dialogue."""
    text = _strip_mojibake_music_ornament(
        re.sub(r'\{\\[^}]*\}', '', str(src_text or '')))
    text = _VTT_VOICE_TAG_RE.sub('', text)
    text = CHEVRON_SPEAKER_RE.sub("", text).strip()
    text = re.sub(r"(?m)^\s*[-–—]\s*(?=[\[(])", "", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    if not text:
        return False
    if _BARE_CYRILLIC_SDH_RE.fullmatch(text):
        return True
    if _src_is_bare_sdh_line(text):
        return True
    spans = _bracket_group_spans(text)
    residue = _replace_bracket_groups(text, lambda _raw: "")
    residue = MUSIC_NOTE_RE.sub("", residue).replace("_", "").strip()
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
    re.compile(r"^\s*(?:esteemed\s+sir|dear\s+sir|your\s+honou?r|superior\s+court)\s*$", re.IGNORECASE),
)


def _is_heading_label(label_text: str) -> bool:
    clean = str(label_text or "").strip()
    return any(p.match(clean) for p in _HEADING_LABEL_PATTERNS)


def _src_has_plain_speaker_label(src_line: str) -> bool:
    m = _SRC_PLAIN_SPEAKER_LABEL_RE.search(src_line)
    if not m:
        return False
    matched_text = m.group(0).rstrip(":\n\r\t ")
    label = re.sub(r"^\s*-\s*", "", matched_text).strip()
    if m.start() > 0 and src_line[:m.start()].strip() and label.casefold() == "listen":
        return False
    if label.casefold() in {"translation", "translator"}:
        return False
    return not _is_heading_label(label)


_SRC_PLAIN_SPEAKER_LABEL_RE = re.compile(
    r"(?m)(?:^|(?<=[.!?…]))\s*(?:-\s*)?"
    r"(?:[A-Z][A-Z0-9 .'\-]{1,30}(?:,\s*(?:VOICE[- ]OVER|V\.?O\.?))?|"
    r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}):\s*"
)
_TR_PLAIN_SPEAKER_LABEL_RE = re.compile(
    r"(?m)(^|(?<=[.!?…]))(\s*(?:-\s*)?)"
    r"(?:[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü0-9 .'\-]{1,30}"
    r"(?:,\s*(?:SES ÜSTÜ|DIŞ SES|V\.?O\.?))?:\s*(?=\S)|"
    r"[A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ0-9 .'\-]{1,30}"
    r"(?:,\s*(?:SES ÜSTÜ|DIŞ SES|V\.?O\.?))?:\s*$)"
)
_TR_LABEL_ONLY_RE = re.compile(
    r"^\s*(?:-\s*)?[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü0-9 .'\-]{1,30}"
    r"(?:,\s*(?:SES ÜSTÜ|DIŞ SES|V\.?O\.?))?:\s*$")
_SRC_BRACKET_SPEAKER_PREFIX_RE = re.compile(
    r"(?m)^\s*(?:-\s*)?\[[^\]\n]{1,40}\]\s*"
)
_SRC_QUOTED_SPEAKER_PREFIX_RE = re.compile(
    r"(?mi)^\s*(?:-\s*)?[A-Z][A-Za-z'\-]*"
    r"(?:\s+[A-Z][A-Za-z'\-]*){0,2},\s*[\"“]"
)


def _target_is_source_speaker_label_only(tr_line: str, src_line: str) -> bool:
    if not _TR_LABEL_ONLY_RE.fullmatch(str(tr_line or "")):
        return False
    source_match = _SRC_PLAIN_SPEAKER_LABEL_RE.search(str(src_line or ""))
    if not source_match:
        return False
    source_label = source_match.group(0).strip().lstrip("-").rstrip(":").strip()
    target_label = str(tr_line or "").strip().lstrip("-").rstrip(":").strip()
    source_key = _ascii_fold(source_label)
    target_key = _ascii_fold(target_label)
    mapped = _SPEAKER_LABEL_TRANSLATIONS.get(source_key, source_label)
    return target_key in {source_key, _ascii_fold(mapped)}


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
    if _SRC_NARRATOR_LABEL_RE.search(src_line):
        tr_line = _TR_NARRATOR_LABEL_RE.sub("", tr_line)
    if (_src_has_plain_speaker_label(src_line)
            or _SRC_BRACKET_SPEAKER_PREFIX_RE.search(src_line)
            or _SRC_QUOTED_SPEAKER_PREFIX_RE.search(src_line)):
        if (_src_has_plain_speaker_label(src_line)
                and _target_is_source_speaker_label_only(tr_line, src_line)):
            return ""
        tr_line = _TR_PLAIN_SPEAKER_LABEL_RE.sub(r"\1\2", tr_line)
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
        structural_speaker = (
            not src_line[:start].strip()
            and bool(re.match(r"\s*\r?\n", src_line[end:]))
            and not _is_heading_label(inner)
        )
        followed_by_dialogue = bool(
            src_line[end:].lstrip()
            and not src_line[end:].lstrip().startswith(("[", "(")))
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
    if _DASH_ONLY_LINE_RE.match(stripped):
        return ""
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
                result.append((idx, ts, "\n".join(lines)))
            continue
        lines = []
        for line in original.split("\n"):
            cleaned = strip_sdh_line(line)
            if cleaned:
                lines.append(cleaned)
        if lines:
            result.append((idx, ts, "\n".join(lines)))
    return result
