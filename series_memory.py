"""
series_memory.py — Dizi (show) bazlı bölümler arası çeviri hafızası.

`project_memory.py` klasör bazlıdır (bir klasör = tek hafıza, tüm dosyalar karışır).
Bu modül SHOW bazlıdır: dosya adından dizi+sezon+bölüm çıkarır, her dizi için ayrı
hafıza tutar (aynı klasördeki iki farklı dizi birbirine karışmaz) ve hint'i HEM düz
HEM hybrid akışlara enjekte eder (hybrid'de proje hafızası enjeksiyonu yoktu).

Çakışma kuralı: ilk bölümde verilen karar KANON olur, sonraki bölümler ezemez —
tutarlılığın bütün amacı bu.

Saklama: <input_dir>/.series_memory/<show-slug>.json
"""

import json
import re
import threading
import unicodedata
from pathlib import Path

from app_state import _interprocess_lock, atomic_write_json

# 'Show.Name.S01E05.720p' → show + season + ep
_SXXEXX = re.compile(
    r'^(?P<show>.+?)[ ._\-]+[Ss](?P<season>\d{1,2})[ ._\-]?[Ee](?P<ep>\d{1,3})')
# 'Show Name 1x05' → show + season + ep (ayraç zorunlu: çözünürlük '1280x720' eşleşmez)
_NXNN = re.compile(
    r'^(?P<show>.+?)[ ._\-]+(?P<season>\d{1,2})x(?P<ep>\d{1,3})(?:\D|$)')
_TV_ROOT = re.compile(
    r'(?i)(?:^|[ ._\-])tv[ ._\-]*s(?P<season>\d{1,2})(?=$|[ ._\-])')
_TV_COMMON_ROOT = re.compile(r'(?i)(?:^|[ ._\-])tv(?=$|[ ._\-])')
_SEASON_DIR = re.compile(r'(?i)^(?:season[ ._\-]*|s)(?P<season>\d{1,2})$')
_EPISODE_DIR = re.compile(r'(?i)^episode[ ._\-]*(?P<ep>\d{1,3})$')
_PUNTATA = re.compile(
    r'(?i)(?:^|[ ._\-])puntata[ ._\-]*(?P<ep>\d{1,3})(?:\D|$)')
_N_OF_TOTAL = re.compile(
    r'(?i)(?:^|[ ._\-])(?P<ep>\d{1,3})[ ._\-]+of[ ._\-]+\d{1,3}(?:\D|$)')
# 'Show Name Episode 05' / 'Show Name Ep 05' / 'Show Name Bölüm 05' → show + ep
_EPISODE_WORD = re.compile(
    r'(?i)^(?P<show>.+?)[ ._\-]+(?:episode|bölüm|bolum|ep\.?)'
    r'[ ._\-]*'
    r'(?P<ep>\d{1,3})(?:\D|$)')
# Anime yayın biçimi: 'Show Name - 05 [1080p]'. Ayraç olarak boşluklu tire şart —
# 'Film - 2019' (4 hane) ve 'Show-05' gibi belirsiz adlar eşleşmez.
_ANIME_DASH = re.compile(
    r'^(?P<show>.+?) - (?P<ep>\d{1,3})(?:\s|$|[\[\(_])')


def _slugify(show: str) -> str:
    # NFC: Windows ve indirme araçları görsel olarak AYNI adı ayrışmış
    # (NFD) ya da birleşik (NFC) yazabiliyor. Normalize edilmeyince
    # 'Cafe' + combining accent 'cafe', birleşik 'Café' ise 'café' slug'ına
    # düşüyor ve aynı dizi iki ayrı hafızaya bölünüyordu (denetim
    # 2026-08-21, madde 36).
    show = unicodedata.normalize('NFC', str(show or ''))
    s = re.sub(r'[._]+', ' ', show.strip().lower())
    s = re.sub(r'[^\w\s-]', '', s)        # \w Türkçe harfleri de kapsar (py3 unicode)
    s = re.sub(r'\s+', '-', s.strip())
    return s or "dizi"


def _target_key(value: str) -> str:
    raw = str(value or "tr").strip().casefold()
    aliases = {
        "turkish": "tr",
        "türkçe": "tr",
        "german": "de",
        "deutsch": "de",
        "italian": "it",
        "spanish": "es",
        "french": "fr",
        "english": "en",
    }
    key = aliases.get(raw, raw)
    key = re.sub(r"[^a-z0-9_-]+", "-", key).strip("-")
    return key or "tr"


def _source_key(value: str) -> str:
    return _target_key(value or "en")


def _term_identity(value) -> str:
    # Terim kimliği de NFC'ye indirgenir (madde 36).
    text = unicodedata.normalize("NFC", str(value or "")).strip()
    if text.isupper() and any(ch.isalpha() for ch in text):
        return f"exact:{text}"
    return f"folded:{text.casefold()}"


def _episode_order(tag):
    """'s01e002' / 's1e10' etiketini karşılaştırılabilir sayıya çevirir."""
    match = re.fullmatch(r"s(\d+)e(\d+)", str(tag or "").strip(), re.IGNORECASE)
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)))


def _term_origin_key(value) -> str:
    text = str(value or "").strip()
    if text.isupper() and any(ch.isalpha() for ch in text):
        return f"exact:{text}"
    return text.casefold()


def _character_identity(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    return "".join(char for char in text if not unicodedata.combining(char)).replace("ı", "i")


def _split_pair_key(key, known_names):
    """'Anlatıcı-Mark Gatiss' → ('Anlatıcı', 'Mark Gatiss'); değilse None.

    Hybrid analiz hitap kararlarını `{"A-B": "sen"}` biçiminde, yani ÇİFT
    anahtarlı bir sözlükle gönderiyor. `merge_address_map`'in sözlük dalı ise
    her anahtarı tek bir karakter adı sayıyordu; sonuçta 15 gerçek dizi
    hafızasındaki 147 kaydın 147'sinde `b` boş kalmış ve yönlü ilişki
    tamamen kaybolmuştu. Prompt'a `- Anlatıcı-Mark Gatiss: 'siz'` diye
    bozuk tek bir ad yazılıyordu.

    Ad İÇİNDE de tire olabildiği için ('Mary-Ann Ochota') körlemesine
    bölmüyoruz: yalnız İKİ YARISI DA bilinen karaktere denk gelen bir
    bölme kabul edilir, birden çok aday varsa hiçbiri seçilmez.
    """
    text = str(key or "").strip()
    if not text:
        return None
    lookup = {_character_identity(name): str(name)
              for name in (known_names or []) if str(name or "").strip()}
    if not lookup:
        return None
    matches = []
    for index, char in enumerate(text):
        if char != "-":
            continue
        left = text[:index].strip()
        right = text[index + 1:].strip()
        if not left or not right:
            continue
        left_id = _character_identity(left)
        right_id = _character_identity(right)
        if left_id in lookup and right_id in lookup and left_id != right_id:
            matches.append((lookup[left_id], lookup[right_id]))
    return matches[0] if len(matches) == 1 else None


def _repair_collapsed_address_pairs(data) -> int:
    """Diske yazılmış çökmüş çiftleri onarır; onarılan kayıt sayısını döner.

    Eski kayıtlarda `a` alanı çift anahtarını, `b` alanı boşu tutuyor.
    Köken anahtarı da eski çökmüş biçimde yazıldığı için birlikte taşınır;
    yoksa bölüm kesme filtresi onarılan kaydın kökenini bulamaz.
    """
    amap = data.get("address_map")
    if not isinstance(amap, list) or not amap:
        return 0
    known = list((data.get("characters") or {}).keys())
    if not known:
        return 0
    origins = data.get("address_origins")
    if not isinstance(origins, dict):
        origins = {}
        data["address_origins"] = origins
    repaired = 0
    for entry in amap:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("b") or "").strip():
            continue
        pair = _split_pair_key(entry.get("a"), known)
        if not pair:
            continue
        old_key = "\0".join((_character_identity(entry.get("a")), ""))
        entry["a"], entry["b"] = pair[0], pair[1]
        new_key = "\0".join((_character_identity(pair[0]),
                              _character_identity(pair[1])))
        if old_key in origins and new_key not in origins:
            origins[new_key] = origins.pop(old_key)
        repaired += 1
    return repaired


def _tv_root_info(filename: str):
    path = Path(filename)
    for parent in path.parents:
        match = _TV_ROOT.search(parent.name)
        if not match:
            continue
        show = parent.name[:match.start()]
        show = re.sub(
            r'[ ._\-]*[\(\[]?\d{4}[\)\]]?[ ._\-]*$', '', show)
        return parent, _slugify(show), int(match.group("season"))
    for parent in path.parents:
        match = _TV_COMMON_ROOT.search(parent.name)
        if not match:
            continue
        relative_parts = path.parent.relative_to(parent).parts
        season = None
        season_pos = None
        for pos, part in enumerate(relative_parts):
            season_match = _SEASON_DIR.match(part)
            if season_match:
                season = int(season_match.group("season"))
                season_pos = pos
                break
        if season is None:
            continue
        show = parent.name[:match.start()]
        show = re.sub(
            r'[ ._\-]*[\(\[]?\d{4}[\)\]]?[ ._\-]*$', '', show)
        if show.strip():
            return parent, _slugify(show), season
        if season_pos:
            show_root = parent.joinpath(*relative_parts[:season_pos])
            return show_root, _slugify(relative_parts[season_pos - 1]), season
    return None


# Dizi adı TAŞIMAYAN, yalnız bölümü numaralayan klasör adları. Bunlar bir
# dizi kökü değildir; ayrı 'Episode 1' / 'Episode 2' klasörlerindeki iki
# bölüm ayrı bellek köküne düşüyor, dizi hafızası ve sezon kanonu hiç
# çalışmıyordu (denetim 2026-08-21, madde 29).
_EPISODE_CONTAINER_DIR = re.compile(
    r'^\s*(?:'
    r'(?:episode|ep|bölüm|bolum|part|kısım|kisim|chapter|disc|disk|cd)'
    r'[ ._\-]*\d{1,3}'
    r'|e\d{1,3}'
    r'|\d{1,3}'
    r')\s*$',
    re.IGNORECASE,
)


def series_memory_root(filename: str) -> Path:
    """Seçilmiş bölüm alt klasörlerini ortak dizi köküne bağlar.

    Tanınan TV/sezon kalıbı yoksa dosyanın hemen üst klasörü kullanılırdı.
    Dosya adı bir dizi kimliği taşıyorsa ve üst klasör yalnız bölümü
    numaralıyorsa ('Episode 1') bir üst ataya çıkılır; böylece kardeş bölüm
    klasörleri aynı belleği paylaşır. Farklı diziler birleşmez: bellek
    kimliği kökün YANINDA slug+sezon da taşır."""
    info = _tv_root_info(filename)
    if info:
        return info[0]
    path = Path(filename)
    root = path.parent
    if not parse_series_key(filename):
        return root
    # En çok iki kat yukarı: 'Show/Season 1/Episode 3' düzeni de kapsansın.
    for _step in range(2):
        if not _EPISODE_CONTAINER_DIR.match(root.name):
            break
        parent = root.parent
        if parent == root:
            break
        root = parent
    return root


# Dosya adı diziyi tek başına taşımadığında kullanılan klasör geri dönüşleri.
# 145 gerçek dizi kaynağının 30'u (%20,7) hiç tanınmıyordu: 'S01E01 New York'
# gibi dizi adı taşımayan adlar ve '02. Геракл и Иолай' gibi bölüm işareti
# yalnız KLASÖR adında olan yayınlar. Tanınmayan dosya dizi hafızasına hiç
# girmiyor; yani bölümler arası terim/ad kanonu o dizide çalışmıyor.
_BARE_SXXEXX = re.compile(
    r'^[Ss](?P<season>\d{1,2})[ ._\-]?[Ee](?P<ep>\d{1,3})(?=$|[ ._\-])')
_BARE_NXNN = re.compile(
    r'^(?P<season>\d{1,2})x(?P<ep>\d{1,3})(?=$|[ ._\-])')
# Program çıktısının kendi alt klasörleri dizi adı değildir.
_GENERIC_DIRS = frozenset({
    "raporlar", "kaynak", "kurtarma", "son denetim", "çıktı", "cikti",
    "yüklenecek", "yuklenecek", "yüklenecekler", "yuklenecekler",
    "yüklendi", "yuklendi",
})


# 'The.Question.Of.God.1of4' / 'BBC.Sacred.Music.Series1.1of4' — BBC tarzı
# çok bölümlü belgesel numaralandırması. Mevcut _N_OF_TOTAL yalnız ayrı bir
# 'tv' kök işareti varken çalışıyordu, bu yayınlarda ise yok. Bölünmüş FİLM
# dosyaları da 'CD1of2' biçimini kullandığı için o önekler dışlanır.
_SHOW_N_OF_TOTAL = re.compile(
    r'^(?P<show>.+?)[ ._\-]+(?P<ep>\d{1,3})of\d{1,3}(?=$|[ ._\-])',
    re.IGNORECASE)
_SPLIT_MEDIA_TAIL = re.compile(
    r'(?i)(?:^|[ ._\-])(?:cd|disc|disk|dvd|pt|part|vol)$')
# Sezonu 'Series1' / 'Series.2' diye yazan yayınlar: sezon numarası dizi
# adının içinde kalırsa her sezon ayrı bir diziymiş gibi hafızaya girer.
_TRAILING_SERIES_NO = re.compile(
    r'(?i)[ ._\-]*series[ ._\-]*(?P<season>\d{1,2})$')
# 'A History of Art in Three Colours S0103' — sezon ve bölüm ayraçsız bitişik.
_SXXEXX_COMPACT = re.compile(
    r'^(?P<show>.+?)[ ._\-]+[Ss](?P<season>\d{2})(?P<ep>\d{2})(?=$|[ ._\-])')
# Eski TV arşivlerinde 'Show 104 Title' = sezon 1, bölüm 04. Yalnız yolun
# doğrulanmış bir `.tv.sNN` kökü varsa kullanılır; böylece film adlarındaki
# sıradan üç haneli sayılar dizi bölümü sanılmaz.
_LEGACY_COMPACT_EPISODE = re.compile(
    r'^(?P<show>.+?)[ ._\-]+(?P<season>[1-9])(?P<ep>\d{2})(?=$|[ ._\-])',
    re.IGNORECASE)


def _show_and_season(show: str, default_season: int):
    """'BBC.Sacred.Music.Series2' → ('bbc-sacred-music', 2)."""
    match = _TRAILING_SERIES_NO.search(show)
    if match:
        return _slugify(show[:match.start()]), int(match.group("season"))
    return _slugify(show), default_season


def _is_episode_marker_dir(name: str) -> bool:
    """Klasör adı dizi adı değil, bölüm/sezon işareti mi?"""
    return bool(_BARE_SXXEXX.match(name) or _BARE_NXNN.match(name)
                or _EPISODE_DIR.match(name) or _SEASON_DIR.match(name))


def _series_key_from_folders(path):
    """Dosya adı yetmediğinde klasör zincirinden dizi anahtarı çıkar."""
    parents = [p.name for p in path.parents
               if p.name and p.name.casefold() not in _GENERIC_DIRS]
    if not parents:
        return None
    bare = _BARE_SXXEXX.match(path.stem) or _BARE_NXNN.match(path.stem)
    if bare:
        # Sezon/bölüm dosyadan kesin; dizi adı bölüm işareti TAŞIMAYAN ilk
        # üst klasördür ('S01E01 New York' klasörü atlanır).
        for name in parents:
            if _is_episode_marker_dir(name):
                continue
            return (_slugify(name), int(bare.group("season")),
                    int(bare.group("ep")))
        return None
    # Dosya adı hiç ayrışmıyorsa yalnız en yakın iki klasöre bakılır; daha
    # yukarısı 'HAZIR DİZİLER' gibi toplu klasörlere kayar.
    for name in parents[:2]:
        for rx in (_SXXEXX, _NXNN):
            m = rx.match(name)
            if m:
                return (_slugify(m.group("show")), int(m.group("season")),
                        int(m.group("ep")))
    return None


def parse_series_key(filename: str):
    """'Show.Name.S01E05.720p.srt' → ('show-name', 1, 5). Dizi değilse None."""
    path = Path(filename)
    stem = path.stem
    root_info = _tv_root_info(filename)
    for rx in (_SXXEXX, _NXNN):
        m = rx.match(stem)
        if m:
            slug = root_info[1] if root_info else _slugify(m.group("show"))
            return slug, int(m.group("season")), int(m.group("ep"))
    if root_info:
        _root, slug, season = root_info
        compact = _LEGACY_COMPACT_EPISODE.match(stem)
        if compact and int(compact.group("season")) == season:
            episode = int(compact.group("ep"))
            if episode > 0:
                return slug, season, episode
        parent_match = _EPISODE_DIR.match(path.parent.name)
        if parent_match:
            return slug, season, int(parent_match.group("ep"))
        for rx in (_PUNTATA, _N_OF_TOTAL):
            match = rx.search(stem)
            if match:
                return slug, season, int(match.group("ep"))
    # Sezon bilgisi taşımayan biçimler (anime yayınları, 'Episode 05'): tek sezon
    # varsayılır. Bunlar olmadan anime dosyalarında dizi hafızası hiç çalışmıyordu.
    for rx in (_EPISODE_WORD, _ANIME_DASH):
        m = rx.match(stem)
        if m:
            slug = root_info[1] if root_info else _slugify(m.group("show"))
            season = root_info[2] if root_info else 1
            return slug, season, int(m.group("ep"))
    m = _SXXEXX_COMPACT.match(stem)
    if m:
        slug = root_info[1] if root_info else _slugify(m.group("show"))
        return slug, int(m.group("season")), int(m.group("ep"))
    m = _SHOW_N_OF_TOTAL.match(stem)
    if m and not _SPLIT_MEDIA_TAIL.search(m.group("show")):
        if root_info:
            return root_info[1], root_info[2], int(m.group("ep"))
        slug, season = _show_and_season(m.group("show"), 1)
        if slug:
            return slug, season, int(m.group("ep"))
    return _series_key_from_folders(path)


def sort_files_by_episode(files: list) -> list:
    """Dosyaları (dizi-slug, sezon, bölüm) sırasına dizer; dizi olmayanlar ada göre sona."""
    def key(fp):
        k = parse_series_key(fp)
        if k is None:
            return (1, Path(fp).name.lower(), 0, 0)
        slug, s, e = k
        return (0, slug, s, e)
    return sorted(files, key=key)


class SeriesMemory:
    VERSION   = 2
    MAX_TERMS = 80
    MAX_CHARS = 24
    MAX_ADDR  = 24

    def __init__(self, path: Path, data: dict):
        self._path = path
        self._data = data
        self._data.setdefault("term_origins", {})
        self._data.setdefault("character_origins", {})
        self._data.setdefault("address_origins", {})
        self._lock = threading.RLock()

    # ── Yükleme / kaydetme ────────────────────────────────────────────────────

    @staticmethod
    def memory_path(input_dir: str, show_slug: str,
                    target_language: str = "tr",
                    source_language: str = "en"):
        """Bu (kök, dizi, dil) dörtlüsünün diskteki dosya yolu."""
        target_key = _target_key(target_language)
        source_key = _source_key(source_language)
        base = Path(input_dir) / ".series_memory"
        if source_key == "en":
            return (
                base / f"{show_slug}.json"
                if target_key == "tr"
                else base / target_key / f"{show_slug}.json"
            )
        return base / f"src-{source_key}" / f"tgt-{target_key}" / f"{show_slug}.json"

    @classmethod
    def load(cls, input_dir: str, show_slug: str,
             target_language: str = "tr",
             source_language: str = "en") -> "SeriesMemory":
        show_slug = str(show_slug or "").strip()
        if not re.fullmatch(r"[\w-]+", show_slug, re.UNICODE):
            raise ValueError("gecersiz dizi hafizasi anahtari")
        target_key = _target_key(target_language)
        source_key = _source_key(source_language)
        path = cls.memory_path(
            input_dir, show_slug, target_language, source_language)
        data = None
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = None   # bozuk JSON'a dayanıklı — sıfırdan başla
        if (isinstance(data, dict) and data.get("target_language")
                and _target_key(data["target_language"]) != target_key):
            data = None
        if (isinstance(data, dict) and data.get("source_language")
                and _source_key(data["source_language"]) != source_key):
            data = None
        if not isinstance(data, dict):
            data = {}
        try:
            previous_version = int(data.get("version", 1))
        except Exception:
            previous_version = 1
        data["version"] = cls.VERSION
        data.setdefault("show", show_slug)
        data.setdefault("target_language", target_key)
        data.setdefault("source_language", source_key)
        data.setdefault("updated_eps", [])
        data.setdefault("terms", {})
        data.setdefault("characters", {})
        data.setdefault("address_map", [])
        data.setdefault("term_origins", {})
        data.setdefault("character_origins", {})
        data.setdefault("address_origins", {})
        if not isinstance(data.get("updated_eps"), list):
            data["updated_eps"] = []
        if not isinstance(data.get("terms"), dict):
            data["terms"] = {}
        if not isinstance(data.get("characters"), dict):
            data["characters"] = {}
        if not isinstance(data.get("address_map"), list):
            data["address_map"] = []
        for key in ("term_origins", "character_origins", "address_origins"):
            if not isinstance(data.get(key), dict):
                data[key] = {}
        # Diskte çökmüş çift kayıtları varsa yüklerken onarılır.
        _repair_collapsed_address_pairs(data)
        if previous_version < cls.VERSION:
            data.setdefault("legacy_unscoped", bool(data.get("updated_eps")))
        else:
            data.setdefault("legacy_unscoped", False)
        return cls(path, data)

    @staticmethod
    def _merge_saved_data(disk: dict, memory: dict) -> dict:
        if not isinstance(disk, dict):
            disk = {}
        memory_target = _target_key(memory.get("target_language", "tr"))
        memory_source = _source_key(memory.get("source_language", "en"))
        if ((disk.get("target_language")
             and _target_key(disk["target_language"]) != memory_target)
                or (disk.get("source_language")
                    and _source_key(disk["source_language"]) != memory_source)):
            disk = {}
        merged = {
            "version": memory.get("version", SeriesMemory.VERSION),
            "show": memory.get("show", disk.get("show", "")),
            "target_language": memory_target,
            "source_language": memory_source,
            "legacy_unscoped": bool(
                disk.get("legacy_unscoped") or memory.get("legacy_unscoped")),
        }
        for key in ("terms", "characters"):
            values = dict(disk.get(key) or {})
            # Karakterlerde `casefold()` yetmez: diskteki "Serif" ile yeni bölümdeki
            # "Şerif" eşleşmeyip aynı karakter iki ayrı anahtarla kaydoluyor ve model
            # sonraki bölümlerde çelişkili iki kural görüyordu (merge_characters
            # zaten `_character_identity` kullanıyor — burası da aynı olmalı).
            known = {
                (_term_identity(item) if key == "terms"
                 else _character_identity(item))
                for item in values
            }
            for item, value in dict(memory.get(key) or {}).items():
                identity = (_term_identity(item) if key == "terms"
                            else _character_identity(item))
                if identity not in known:
                    values[item] = value
                    known.add(identity)
                elif key == "characters":
                    # 'İlk karar kanon' terimler için doğru, KARAKTERLER
                    # için değil: merge_characters diskteki üslup BOŞsa
                    # bilerek zenginleştiriyor. Save sınırındaki 'kimlik
                    # diskte varsa bellek değerini yok say' kuralı tam o
                    # zenginleştirmeyi geri alıyordu — sonradan öğrenilen
                    # üslup hiç diske yazılmıyordu (dış denetim H3).
                    disk_entry = next(
                        (values[name] for name in values
                         if _character_identity(name) == identity), None)
                    if (isinstance(disk_entry, dict)
                            and isinstance(value, dict)
                            and not str(disk_entry.get("style") or "").strip()
                            and str(value.get("style") or "").strip()):
                        disk_entry["style"] = str(value["style"]).strip()
            merged[key] = values
        addresses = list(disk.get("address_map") or [])
        seen = {
            (_character_identity(item.get("a")), _character_identity(item.get("b")))
            for item in addresses if isinstance(item, dict)
        }
        for item in list(memory.get("address_map") or []):
            if not isinstance(item, dict):
                continue
            key = (_character_identity(item.get("a")),
                   _character_identity(item.get("b")))
            if key not in seen:
                addresses.append(item)
                seen.add(key)
        merged["address_map"] = addresses
        for key in ("term_origins", "character_origins", "address_origins"):
            origins = dict(disk.get(key) or {})
            for item, origin in dict(memory.get(key) or {}).items():
                origins.setdefault(str(item), str(origin))
            merged[key] = origins
        merged["updated_eps"] = list(dict.fromkeys(
            list(disk.get("updated_eps") or [])
            + list(memory.get("updated_eps") or [])))
        return merged

    def save(self):
        try:
            with self._lock:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with _interprocess_lock(self._path):
                    if self._path.exists():
                        try:
                            disk = json.loads(self._path.read_text(encoding="utf-8"))
                        except Exception as exc:
                            raise ValueError(
                                "mevcut dizi hafızası bozuk; veri kaybını önlemek "
                                "için üzerine yazılmadı"
                            ) from exc
                        if not isinstance(disk, dict):
                            raise ValueError(
                                "mevcut dizi hafızası nesne biçiminde değil; veri "
                                "kaybını önlemek için üzerine yazılmadı"
                            )
                    else:
                        disk = {}
                    self._data = self._merge_saved_data(disk, self._data)
                    atomic_write_json(self._path, self._data)
            return True
        except Exception as e:
            import sys
            print(f"[series_memory] kaydetme hatası {self._path}: {e}", file=sys.stderr)
            return False

    # ── Birleştirme (ilk karar kanon) ─────────────────────────────────────────

    @staticmethod
    def _episode_tag(season=None, ep=None) -> str:
        try:
            return f"s{int(season):02d}e{int(ep):03d}"
        except Exception:
            return ""

    def merge_terms(self, terms: dict, season=None, ep=None):
        if not isinstance(terms, dict):
            return
        t = self._data["terms"]
        known = {_term_identity(key) for key in t}
        for src, tgt in terms.items():
            if not (src and tgt):
                continue
            # Kaynak==hedef (küçük-harf sıradan kelime) İngilizce sızıntısı üretir;
            # özel ad/kısaltma (büyük harf içeren) korunur.
            s, v = str(src).strip(), str(tgt).strip()
            identity = _term_identity(s)
            if not s or identity in known:
                continue
            if s.lower() == v.lower() and s.islower():
                continue
            t[s] = v
            known.add(identity)
            tag = self._episode_tag(season, ep)
            if tag:
                self._data["term_origins"].setdefault(_term_origin_key(s), tag)

    def merge_characters(self, chars, season=None, ep=None):
        """chars: {name: style} | [{name, style|speaking_style}] | [CharacterVoice]."""
        c = self._data["characters"]
        items = []
        if isinstance(chars, dict):
            items = list(chars.items())
        elif isinstance(chars, (list, tuple)):
            for ch in chars:
                if isinstance(ch, dict) and ch.get("name"):
                    items.append((ch["name"], ch.get("style") or ch.get("speaking_style") or ""))
                elif hasattr(ch, "name"):
                    items.append((ch.name, getattr(ch, "speaking_style", "") or ""))
        known = {_character_identity(key): key for key in c}
        for name, style in items:
            clean_name = str(name or "").strip()
            if not clean_name:
                continue
            canonical = known.get(_character_identity(clean_name))
            if canonical is None:
                c[clean_name] = {"style": str(style or "").strip()}
                known[_character_identity(clean_name)] = clean_name
                tag = self._episode_tag(season, ep)
                if tag:
                    self._data["character_origins"].setdefault(
                        _character_identity(clean_name), tag)
            elif (isinstance(c.get(canonical), dict)
                  and not c[canonical].get("style") and str(style or "").strip()):
                c[canonical]["style"] = str(style).strip()

    def merge_address_map(self, pairs, season=None, ep=None):
        """pairs: [{a, b, register}] (pairwise) | {name: register} (per-character)."""
        amap = self._data["address_map"]
        seen = {
            (_character_identity(p.get("a")),
             _character_identity(p.get("b")))
            for p in amap if isinstance(p, dict)
        }
        entries = []
        if isinstance(pairs, dict):
            known = list((self._data.get("characters") or {}).keys())
            for name, reg in pairs.items():
                if not (name and reg):
                    continue
                # Anahtar bir ÇİFT ise ('A-B') yönlü kayda ayrıştır; değilse
                # eski karakter-başına davranış korunur (testle kilitli).
                pair = _split_pair_key(name, known)
                if pair:
                    entries.append({"a": pair[0], "b": pair[1],
                                    "register": str(reg)})
                else:
                    entries.append({"a": str(name), "b": "",
                                    "register": str(reg)})
        elif isinstance(pairs, (list, tuple)):
            for p in pairs:
                if isinstance(p, dict) and p.get("a") and p.get("register"):
                    entries.append({"a": str(p["a"]), "b": str(p.get("b") or ""),
                                    "register": str(p["register"])})
        for e in entries:
            key = (_character_identity(e["a"]), _character_identity(e["b"]))
            if key not in seen:
                seen.add(key)
                amap.append(e)
                tag = self._episode_tag(season, ep)
                if tag:
                    self._data["address_origins"].setdefault(
                        "\0".join(key), tag)

    def mark_episode(self, season, ep):
        # DİKKAT: `updated_eps` DİSK biçimi 2 hanelidir ('s01e01'), köken
        # etiketleri (`_episode_tag`) 3 hanelidir ('s01e001'). Bu ikisi
        # BİRBİRİYLE hiç karşılaştırılmaz: `updated_eps` yalnız legacy
        # bloklamada regex'le parse edilip SAYISAL karşılaştırılır, köken
        # etiketleri ise `_episode_order` ile. Dolguyu eşitlemek kayıtlı
        # .series_memory dosyalarının biçimini bozar (bug taraması madde 8:
        # tutarsızlık gerçek ama zararsız, düzeltmesi zararlı).
        try:
            tag = f"s{int(season):02d}e{int(ep):02d}"
        except Exception:
            return
        if tag not in self._data["updated_eps"]:
            self._data["updated_eps"].append(tag)

    # ── Prompt hint'i ─────────────────────────────────────────────────────────

    @staticmethod
    def _core_and_recent(items, limit):
        items = list(items)
        if len(items) <= limit:
            return items
        core_count = limit // 2
        return items[:core_count] + items[-(limit - core_count):]

    def _origin_allowed(self, origin, cutoff, cutoff_order,
                        legacy_blocked=False) -> bool:
        """Bu koken etiketi kesme noktasindan ONCE mi?

        `build_hint` ile `get_terms` AYNI kumeyi dondurmek zorunda
        (bkz. get_terms docstring'i): kilitli terim modele soylenmemis
        olmamali. Iki ayri kopya kacinilmaz olarak ayrisiyordu, tek
        kaynaga alindi."""
        if not cutoff:
            return True
        if not origin:
            return not legacy_blocked
        # Dize karsilastirmasi dolgusuz eski etiketlerde ('s1e10' < 's1e2')
        # yanlis sonuc verip kanon ipuclarini gereksiz eliyordu
        # (denetim Part 2, madde 19). Sayisal karsilastir, cozulemezse
        # eski davranisa dus.
        origin_order = _episode_order(origin)
        if origin_order is not None and cutoff_order is not None:
            return origin_order < cutoff_order
        return str(origin) < cutoff

    def build_hint(self, before_episode=None, term_filter=None) -> str:
        terms = self._data.get("terms") or {}
        chars = self._data.get("characters") or {}
        addr  = self._data.get("address_map") or []
        cutoff = self._episode_tag(*(before_episode or ())) if before_episode else ""
        legacy_blocked = False
        if cutoff and self._data.get("legacy_unscoped"):
            cutoff_match = re.fullmatch(r"s(\d+)e(\d+)", cutoff)
            if cutoff_match:
                cutoff_key = tuple(map(int, cutoff_match.groups()))
                for tag in self._data.get("updated_eps") or []:
                    match = re.fullmatch(r"s(\d+)e(\d+)", str(tag), re.IGNORECASE)
                    if match and tuple(map(int, match.groups())) >= cutoff_key:
                        legacy_blocked = True
                        break

        cutoff_order = _episode_order(cutoff)

        def allowed(origin):
            return self._origin_allowed(
                origin, cutoff, cutoff_order, legacy_blocked)

        term_origins = self._data.get("term_origins") or {}
        char_origins = self._data.get("character_origins") or {}
        addr_origins = self._data.get("address_origins") or {}
        terms = {
            source: target for source, target in terms.items()
            if allowed(term_origins.get(_term_origin_key(source)))
        }
        if callable(term_filter):
            try:
                filtered = term_filter(dict(terms))
                terms = dict(filtered) if isinstance(filtered, dict) else {}
            except Exception:
                terms = {}
        # Köken anahtarları `_character_identity` ile YAZILIYOR (bkz. merge_characters /
        # merge_address_map); burada `casefold()` ile aramak Türkçe ve aksanlı adlarda
        # (Şerif, İsmail, Hélène) hiç eşleşmiyor ve bölüm kesme mantığı bozuluyordu.
        chars = {
            name: meta for name, meta in chars.items()
            if allowed(char_origins.get(_character_identity(name)))
        }
        addr = [
            item for item in addr if isinstance(item, dict) and allowed(
                addr_origins.get("\0".join((
                    _character_identity(item.get("a")),
                    _character_identity(item.get("b")),
                )))
            )
        ]
        if not (terms or chars or addr):
            return ""
        lines = ["\n## SERIES MEMORY (decisions from earlier episodes — follow strictly)"]
        if terms:
            lines.append("Fixed term translations (use EXACTLY these, never re-decide):")
            lines.extend(
                f"- '{s}' → '{t}'"
                for s, t in self._core_and_recent(terms.items(), self.MAX_TERMS)
            )
        if chars:
            lines.append("Characters (keep each voice consistent across episodes):")
            for name, meta in self._core_and_recent(chars.items(), self.MAX_CHARS):
                style = meta.get("style") if isinstance(meta, dict) else ""
                lines.append(f"- {name}" + (f": {style}" if style else ""))
        if addr:
            lines.append("Address register (Turkish sen/siz — keep consistent):")
            for a in self._core_and_recent(addr, self.MAX_ADDR):
                if not isinstance(a, dict):
                    continue
                aa, bb, reg = a.get("a"), a.get("b"), a.get("register")
                if aa and reg:
                    lines.append(f"- {aa} → {bb}: '{reg}'" if bb else f"- {aa}: '{reg}'")
        return "\n".join(lines) + "\n"

    def get_terms(self, before_episode=None) -> dict:
        """Terim tablosu. before_episode verilirse 'ilk karar kanon'
        kesmesi UYGULANIR — build_hint ile aynı küme döner.

        Kesmesiz hâli, modele HİÇ söylenmemiş (hint'te olmayan) bir
        terimi doğrulayıcıya dayatıyordu: yanlış locked_term_violation
        redleri ve gereksiz terim-normalizasyonu adayları. Ayrıca bir
        sezonu ikinci kez çevirince kilitli küme büyüdüğü için aynı
        girdi farklı sonuç veriyordu (bug taraması madde 26)."""
        terms = dict(self._data.get("terms") or {})
        if not before_episode:
            return terms
        cutoff = self._episode_tag(*before_episode)
        cutoff_order = _episode_order(cutoff)
        if cutoff_order is None:
            return terms
        origins = self._data.get("term_origins") or {}
        allowed = {}
        for source, target in terms.items():
            origin = origins.get(_term_origin_key(source))
            if self._origin_allowed(origin, cutoff, cutoff_order):
                allowed[source] = target
        # `build_hint` terim listesini MAX_TERMS'te KIRPIYOR; burası
        # kırpmıyordu. Kırpılan terim modele hiç söylenmiyor ama kilitli
        # kümeye giriyor ve doğrulayıcı onu dayatıyordu — bu fonksiyonun
        # var oluş nedeni tam olarak bunu önlemekti. Gerçek dosyalarda
        # ölçüldü: 15 .series_memory dosyasının 2'sinde 12 ve 48 terim
        # yalnız kilitte vardı, hint'te yoktu.
        return dict(self._core_and_recent(allowed.items(), self.MAX_TERMS))

    def get_address_map(self) -> list:
        return [dict(item) for item in (self._data.get("address_map") or [])
                if isinstance(item, dict)]

    def counts(self) -> dict:
        return {"terms": len(self._data.get("terms", {})),
                "characters": len(self._data.get("characters", {})),
                "address": len(self._data.get("address_map", []))}
