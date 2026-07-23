import json
import copy
import difflib
import math
import os
import re
import time
import hashlib
import queue
import threading
import traceback
import unicodedata
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import customtkinter as ctk
from tkinter import filedialog, messagebox
from openai import OpenAI
from helper_models import HELPER_MODEL_OPTIONS, resolve_helper_model, normalize_helper_model_label
from subtitle_formats import (parse_vtt, parse_ass, get_subtitle_files,
                              restore_format_tags, read_subtitle_text)
import credential_store
import series_memory
import sdh_cleaner
from app_state import atomic_write_json, mutate_batch_ids, state_dir, state_path
from prompt_constants import PROFANITY_RULES, JSON_INSTRUCTION
from folder_picker import pick_multiple_folders

# Tahmini 1M Token fiyatları (Input/Output $)
ESTIMATED_PRICES = {
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "gpt-4o": {"in": 2.50, "out": 10.00},
    "haiku": {"in": 1.00, "out": 5.00},
    "sonnet": {"in": 3.00, "out": 15.00},
    "flash": {"in": 0.075, "out": 0.30},
    "pro": {"in": 1.25, "out": 5.00},
    "deepseek-chat": {"in": 0.14, "out": 0.28},
    "deepseek-reasoner": {"in": 0.55, "out": 2.19},
    "qwen-plus": {"in": 0.40, "out": 1.20},
    "qwen-max": {"in": 1.20, "out": 4.80},
    "o1-mini": {"in": 3.00, "out": 12.00},
    "o1": {"in": 15.00, "out": 60.00},
}

MAX_PARALLEL = 3
CONTENT_TYPE_DETECT_MODEL = "gpt-5.4"
API_REQUEST_TIMEOUT_SECONDS = 300


def _safe_chat_create(client, **kwargs):
    model = kwargs.get("model", "")
    model_lower = (model or "").lower()
    base_url = str(getattr(client, "base_url", "")).lower().rstrip("/")

    # Bedrock and Anthropic provider check
    is_bedrock = False
    is_anthropic = False
    explicit_openai = False
    try:
        from helper_models import normalize_helper_model_label, resolve_helper_model, _CONFIGS, _ALIASES
        norm_label = normalize_helper_model_label(model)
        is_known_model = (model in _CONFIGS) or (model.lower() in _ALIASES) or (norm_label in _CONFIGS and norm_label != "gpt-5.4-mini")
        cfg = resolve_helper_model(norm_label)
        if cfg.provider == "bedrock":
            is_bedrock = True
        elif cfg.provider == "anthropic":
            is_anthropic = True
        elif cfg.provider == "openai" and is_known_model:
            explicit_openai = True
    except Exception:
        pass

    # Fallback/dynamic detection based on URL or model name
    if not is_bedrock and not is_anthropic and not explicit_openai:
        if "bedrock" in base_url or "bedrock" in model_lower:
            is_bedrock = True
        elif ("anthropic" in base_url or base_url.endswith("/messages")
              or ("claude" in model_lower and "/messages" in base_url)):
            if "bedrock" not in base_url and "bedrock" not in model_lower:
                is_anthropic = True

    if is_bedrock:
        api_key = getattr(client, "api_key", None)
        from helper_models import call_bedrock_converse
        return call_bedrock_converse(
            model_id=model,
            messages=kwargs.get("messages", []),
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens") or kwargs.get("max_completion_tokens"),
            api_key_str=api_key,
            base_url=base_url
        )

    if is_anthropic:
        api_key = getattr(client, "api_key", None)
        from helper_models import call_anthropic_messages
        return call_anthropic_messages(
            model_id=model,
            messages=kwargs.get("messages", []),
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens") or kwargs.get("max_completion_tokens"),
            api_key_str=api_key,
            base_url=base_url
        )

    try:
        import hybrid_translate as ht
        kwargs = ht._normalize_chat_create_kwargs(model, kwargs)
    except Exception:
        pass

    kwargs.setdefault("timeout", API_REQUEST_TIMEOUT_SECONDS)
    return client.chat.completions.create(**kwargs)


_SETTINGS_SECRET_KEY_RE = re.compile(
    r'("(?:[^"]*(?:api[_-]?key|secret|token|_key)[^"]*)"\s*:\s*")([^"]*)(")',
    re.I,
)
_SETTINGS_TOKEN_RE = re.compile(r"\b(?:sk|mk)-[A-Za-z0-9._\-]+\b")


def _sanitize_settings_backup_text(text: str) -> str:
    text = str(text or "")
    text = _SETTINGS_SECRET_KEY_RE.sub(r"\1[REDACTED]\3", text)
    text = _SETTINGS_TOKEN_RE.sub("[REDACTED]", text)
    return text


def _settings_backup_suffix(path: Path) -> int:
    """`.gui_settings.json.bak.<suffix>` adındaki sayısal kısmı döner, yoksa -1.
    Yeni/eski sıralaması için dosyanın kendi st_mtime'ı YERİNE bu kullanılmalı:
    art arda birden fazla yedek aynı saniye içinde yazılırsa (ör. testte 5 sahte
    + 1 gerçek yedek üst üste oluşturuluyor) bazı dosya sistemlerinde mtime
    çözünürlüğü bunları ayırt edemeyip aralarında rastgele bir dosyayı "en yeni"
    seçtiriyordu — dosya adındaki sayı (epoch saniye) zaten kesin ve çakışmasız
    bir sıralama sağlıyor."""
    try:
        return int(path.name.rsplit(".", 1)[-1])
    except (ValueError, IndexError):
        return -1


def _write_sanitized_settings_backup(src_path: Path, keep_last: int = 3) -> Path | None:
    if not src_path.exists():
        return None
    bak = src_path.with_name(f".gui_settings.json.bak.{int(time.time())}")
    raw = src_path.read_text(encoding="utf-8", errors="replace")
    bak.write_text(_sanitize_settings_backup_text(raw), encoding="utf-8")
    backups = sorted(src_path.parent.glob(".gui_settings.json.bak.*"), key=_settings_backup_suffix, reverse=True)
    for stale in backups[keep_last:]:
        try:
            stale.unlink()
        except Exception:
            pass
    return bak


def _normalize_api_base_url(value: str) -> str:
    """Normalize the optional main API base URL field."""
    url = (value or "").strip().rstrip("/")
    if url.lower() in {"", "none", "null", "default", "openai"}:
        return ""
    return url


def _get_usage_details(usage):
    if not usage:
        return 0, 0
    if isinstance(usage, dict):
        total = usage.get("total_tokens", 0) or 0
        prompt_details = usage.get("prompt_tokens_details") or {}
        cached = prompt_details.get("cached_tokens", 0) or 0
        return total, cached
    
    total = getattr(usage, "total_tokens", 0) or 0
    cached = 0
    try:
        p_details = getattr(usage, "prompt_tokens_details", None)
        if p_details:
            cached = getattr(p_details, "cached_tokens", 0) or 0
    except Exception:
        pass
    return total, cached


# ─────────────────────────────────────────────────────────────────────
# CustomTkinter ZeroDivisionError patch (scaling 0 olduğunda çöküyor)
# Bilinen bug: https://github.com/TomSchimansky/CustomTkinter/issues/2295
# Pencere boyutlandırma sırasında __window_scaling veya __widget_scaling
# bazen 0 oluyor ve _reverse_window_scaling / _reverse_widget_scaling
# bölme hatası veriyor. Aşağıdaki monkey-patch o iki metoda fallback ekler.
# ─────────────────────────────────────────────────────────────────────
try:
    from customtkinter.windows.widgets.scaling.scaling_base_class import ScalingBaseClass as _SBC

    def _safe_reverse_widget_scaling(self, value):
        s = getattr(self, "_ScalingBaseClass__widget_scaling", 1.0) or 1.0
        try:
            return value / s
        except ZeroDivisionError:
            return value

    def _safe_reverse_window_scaling(self, scaled_value):
        s = getattr(self, "_ScalingBaseClass__window_scaling", 1.0) or 1.0
        try:
            return int(scaled_value / s)
        except ZeroDivisionError:
            return int(scaled_value)

    _SBC._reverse_widget_scaling = _safe_reverse_widget_scaling
    _SBC._reverse_window_scaling = _safe_reverse_window_scaling
except Exception:
    pass

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
# Scaling değerlerini açıkça 1.0'a sabitle (bazı sürümlerde 0 ile başlar)
try:
    ctk.set_widget_scaling(1.0)
    ctk.set_window_scaling(1.0)
except Exception:
    pass

ACCENT  = "#7B68EE"
GREEN   = "#2ECC71"
RED     = "#E74C3C"
YELLOW  = "#F39C12"
BG      = "#1a1a2a"
PANEL   = "#242436"
CARD    = "#2e2e48"
BORDER  = "#3a3a55"
FG      = "#e8e8f0"
FG2     = "#8888aa"
WARN    = "#E74C3C"   # sil/iptal butonları

MODELS_250K = [
    "gpt-5.4", "gpt-5.2", "gpt-5.1", "gpt-5-chat-latest", "gpt-5",
    "o3", "o1", "gpt-4o", "gpt-4.1", "gpt-5.1-codex", "gpt-5-codex",
   
]
MODELS_2_5M = [
    "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.1-codex-mini",
    "gpt-5-mini", "gpt-5-nano", "gpt-4.1-mini", "gpt-4.1-nano",
    "gpt-4o-mini", "o1-mini", "o3-mini", "o4-mini", "codex-mini-latest",
    "claude-haiku-4-5-20251001",
]
MODELS = MODELS_250K + MODELS_2_5M
LANGUAGES = [
    "Turkish","English","German","French","Spanish","Italian",
    "Portuguese","Russian","Japanese","Korean","Chinese","Arabic",
    "Dutch","Polish","Swedish","Norwegian","Danish","Finnish",
]
# Naive `name.lower()[:2]` guesses the ISO 639-1 code from the English language
# name — wrong for over half of LANGUAGES (Turkish->"tu" not "tr", German->"ge"
# not "de", Spanish->"sp" not "es", Portuguese/Polish collide on "po", Chinese
# ->"ch" not "zh", Dutch->"du" not "nl", Swedish->"sw" not "sv"). Since
# sanitize_glossary_for_turkish's target-language guard only recognizes "tr"/
# "tur"/"turkish", the "tu" produced for Turkish silently disabled every
# glossary-poisoning guard (wqx/gloss-marker/verbose-meta-commentary) in
# production — the language name never matched, so the sanitizer always took
# its "unrecognized target, return unmodified" early exit.
_LANGUAGE_ISO639_1 = {
    "turkish": "tr", "türkçe": "tr", "turkce": "tr",
    "english": "en", "german": "de", "french": "fr",
    "spanish": "es", "italian": "it", "portuguese": "pt", "russian": "ru",
    "japanese": "ja", "korean": "ko", "chinese": "zh", "arabic": "ar",
    "dutch": "nl", "polish": "pl", "swedish": "sv", "norwegian": "no",
    "danish": "da", "finnish": "fi",
}


def _lang_iso639_1(name: str) -> str:
    """LANGUAGES display name -> correct ISO 639-1 code (falls back to a naive
    2-letter slice for anything not in the table above)."""
    key = str(name or "").strip().lower()
    return _LANGUAGE_ISO639_1.get(key) or key[:2]
CHUNK         = 30
SYNC_CHUNK    = 40
CONTEXT_LINES    = 20  # preceding lines sent as rolling context
LOOKAHEAD_LINES  = 10  # next-chunk lines sent as read-ahead

MODEL_PRICE = {  # USD per 1M tokens (blended estimate)
    # 250k token/gün kotası
    "gpt-5.4":           25.00,
    "gpt-5.2":           25.00,
    "gpt-5.1":           25.00,
    "gpt-5":             25.00,
    "gpt-5.1-codex":     25.00,
    "gpt-5-codex":       25.00,
    "gpt-5-chat-latest": 25.00,
    "gpt-4.1":            4.00,
    "gpt-4o":             5.00,
    "o1":                60.00,
    "o3":                60.00,
    # 2.5M token/gün kotası
    "gpt-5.4-mini":       5.00,
    "gpt-5.4-nano":       1.00,
    "gpt-5.1-codex-mini": 5.00,
    "gpt-5-mini":         5.00,
    "gpt-5-nano":         1.00,
    "codex-mini-latest":  5.00,
    "gpt-4.1-mini":       0.60,
    "gpt-4.1-nano":       0.15,
    "gpt-4o-mini":        0.23,
    "o4-mini":            5.00,
    "o3-mini":            5.00,
    "o1-mini":            5.00,
}

POLISH_MODEL = "gpt-4.1-mini"

CONTENT_SCHEMAS = {
    "auto": {
        "name": "Otomatik", "rules": [],
    },
    "reality": {
        "name": "Reality Show",
        "rules": [
            "- [CONTEXT & TONE] Keep insults, swearing, and yelling at full heat; 'What the hell is wrong with you?' must stay aggressive, not polite Turkish.",
            "- [TONE & REGISTER] Confrontational lines must stay sharp; 'Shut up', 'Back off', 'Don't test me' must not be softened or formal.",
            "- [TONE & REGISTER] Talking-head confessionals should sound spontaneous, gossipy, and slightly messy, not polished or literary.",
            "- [TONE & REGISTER] Jealousy, gossip, and petty shade must sound catty in Turkish; avoid dignified wording like a drama narrator.",
            "- [TERMINOLOGY] Replace slang with real Turkish spoken slang; never transliterate 'bro', 'literally', 'oh my God', 'seriously'.",
            "- [FLOW & TIMING] Interruptions, repeated words, and cut-off lines carry drama; keep them broken, do not merge into full sentences.",
            "- [TERMINOLOGY] Competition subtype (Survivor, MasterChef, etc.) needs competition jargon ('immunity'→dokunulmazlık, 'elimination'→eleme, 'challenge'→dokunulmazlık oyunu/düello, 'safe'→potada değil/güvende) in established Turkish TV vocabulary.",
            "- [TONE & REGISTER] Dating shows (The Bachelor, Love Island, etc.) carry their own crush-confession voice; do not let it slip into romantic drama register.",
            "- [CONTEXT & TONE] Reality narrator/voice-over should sound slightly arched, dramatic-but-knowing — not flat documentary, not melodrama.",
            "- [FLOW & TIMING] Group fight scenes overlap voices; preserve fragments and shouting, never tidy them into orderly exchanges.",
            "- [TR_ERROR] A major TR error here is over-formality: if the source sounds trashy, blunt, or chaotic, Turkish must too; do not sterilize female-vs-female confrontations.",
        ],
    },
    "reality_street": {
        "name": "Reality / Sokak Argosu",
        "rules": [
            "- [CONTEXT & TONE] For crude dating shows, mansion competitions, street interviews, and internet reality formats with heavy slang/AAVE; this is rougher than normal Reality Show.",
            "- [TONE & REGISTER] Keep speech chaotic, vulgar, and performative when the source is; do not clean it into standard TV Turkish.",
            "- [TERMINOLOGY] AAVE, Black American slang, Gen-Z slang, and sexual insults need real Turkish street/internet equivalents, not literal dictionary Turkish.",
            "- [FLOW & TIMING] Confessionals, group fights, and insults often come as fragments; preserve the broken rhythm and repeated words.",
            "- [TERMINOLOGY] Keep names, nicknames, brands, platform names, and meme labels exactly unless a Turkish meme equivalent is clearly established.",
            "- [TONE & REGISTER] Profanity and sexual slang translate at the same intensity; censorship changes the genre.",
            "- [DIALECT & CHARACTER] Differentiate host/announcer polish from contestant chaos; not everyone should sound equally rough.",
            "- [TR_ERROR] A common TR error here is translating AAVE as polite Turkish or as generic 'kanka' speech; preserve attitude, grammar roughness, and social texture.",
        ],
    },
    "documentary": {
        "name": "Belgesel",
        "rules": [
            "- [TONE & REGISTER] Narration must use clean, measured standard Turkish; no slang, no filler, no chatty YouTube phrasing.",
            "- [TERMINOLOGY] Dates, numbers, institutions, places, units, and names must be exact; never round, guess, or simplify ('about a thousand' ≠ 'around 1,000' — keep the source's precision).",
            "- [TERMINOLOGY] Technical, legal, scientific, and medical terms must use the established Turkish equivalent consistently.",
            "- [TONE & REGISTER] Preserve uncertainty markers exactly; 'may', 'appears to', 'is believed to', 'allegedly', 'reportedly' MUST NOT become certainty in Turkish.",
            "- [TONE & REGISTER] Interviewees keep their own speaking style; do not force every witness, expert, or survivor into narrator-level formality.",
            "- [FLOW & TIMING] Keep logical connectors explicit; 'however', 'therefore', 'meanwhile', 'in contrast', 'nevertheless' should not disappear into vague Turkish.",
            "- [CONTEXT & TONE] True-crime subtype: maintain forensic-investigative tone for narrator (cool, fact-driven), but let witness/family/victim voices carry real emotion.",
            "- [CONTEXT & TONE] Nature/wildlife subtype: the camera-narrator wonder tone exists but stays restrained; do not become a children's storybook.",
            "- [CONTEXT & TONE] Historical documentary: archive language tone for narrator, period-appropriate quotes inside interview/letter readings.",
            "- [TR_ERROR] A common TR error here is dramatization: neutral factual English must not become emotional or poetic Turkish.",
            "- [TR_ERROR] Another common TR error is collapsing scientific names into casual Turkish: 'Homo sapiens', 'COVID-19', 'mRNA', 'Permian extinction' stay technical.",
        ],
    },
    "society_politics_documentary": {
        "name": "Siyaset / Toplum Belgeseli",
        "rules": [
            "- [CONTEXT & TONE] Political, social history, censorship, civil rights, media, institutions, public intellectuals, and cultural conflict documentaries.",
            "- [TONE & REGISTER] Narration is analytical and clear; avoid sensational news tone and avoid academic stiffness unless the source is academic.",
            "- [TERMINOLOGY] Political institutions, laws, parties, movements, ideologies, and court/legal terms must use established Turkish equivalents.",
            "- [TERMINOLOGY] Preserve uncertainty and attribution: 'alleged', 'reportedly', 'critics argue', 'supporters say' must not become factual certainty.",
            "- [DIALECT & CHARACTER] Activists, politicians, journalists, academics, and ordinary witnesses each keep distinct registers.",
            "- [CONTEXT & TONE] Satirical or countercultural speakers may be sharp, profane, or ironic; do not turn political humor into bland commentary.",
            "- [FLOW & TIMING] Cause-effect chains and chronology must remain explicit so the viewer can follow the argument.",
            "- [TR_ERROR] A common TR error here is editorializing: the Turkish must not add a political stance that the source did not state.",
        ],
    },
    "history_documentary": {
        "name": "Tarih Belgeseli",
        "rules": [
            "- [CONTEXT & TONE] The tone is a serious, authoritative historical narrative. The narrator must sound like an archive historian, maintaining formal, factual, and respectful Turkish.",
            "- [TERMINOLOGY] Period-specific titles, institutions, geographic locations, and military ranks must be precise and accurate to the era (e.g., 'Ottoman Empire'→'Osmanlı İmparatorluğu', 'Byzantine'→'Bizans', 'Tsar'→'Çar'). Do not modernize historical terminology.",
            "- [TERMINOLOGY] For historical events and wars, use established Turkish historical nomenclature (e.g., 'The Crusades'→'Haçlı Seferleri', 'The Cold War'→'Soğuk Savaş', 'WWII'→'İkinci Dünya Savaşı').",
            "- [DIALECT & CHARACTER] Quotes from historical figures, letters, and diary entries should be translated with an archaic, literary register appropriate to the period, distinguishing them from the modern narrator's voice.",
            "- [FLOW & TIMING] Narrator's pacing is deliberate. Preserve rhetorical pauses, solemn pacing, and grand historical scope without turning it into an action movie trailer.",
            "- [TR_ERROR] A common TR error is translating period letters, declarations, or speeches into overly casual or modern conversational Turkish, thereby losing the historical distance and gravity.",
            "- [PRONOUNS] Pronoun register varies by period and rank: court, military, clergy, commoner, and modern interview voices should not collapse into one flat sen/siz level.",
        ],
    },
    "archaeology_ancient_history": {
        "name": "Arkeoloji / Antik Tarih Belgeseli",
        "rules": [
            "- [CONTEXT & TONE] Archaeology, Egyptology, ancient tombs, lost cities, artifacts, excavations, and ancient-civilization documentaries.",
            "- [TERMINOLOGY] Archaeological vocabulary must be precise: excavation, trench, layer, dating, burial chamber, sarcophagus, inscription, artifact, residue, site, stratigraphy.",
            "- [TERMINOLOGY] Ancient names, dynasties, rulers, sites, museums, and artifact catalogue terms stay consistent; use established Turkish forms where they exist.",
            "- [TONE & REGISTER] Keep the sense of discovery and mystery, but do not exaggerate into treasure-hunt melodrama unless the source does.",
            "- [CONTEXT & TONE] Expert interviews sound scholarly and cautious; narrator may be more cinematic but still factual.",
            "- [TERMINOLOGY] Preserve hedging around evidence: 'suggests', 'may indicate', 'possibly', 'is believed to' must not become proof.",
            "- [FLOW & TIMING] Spatial descriptions of tombs, chambers, maps, and dig sites must stay clear and concrete.",
            "- [TR_ERROR] A common TR error here is translating all ancient objects as generic 'kalıntı' or 'eser'; preserve object type and archaeological function.",
        ],
    },
    "series": {
        "name": "Dizi",
        "rules": [
            "- [TONE & REGISTER] Each recurring character must keep the same Turkish voice across scenes: same class level, same attitude, same rhythm.",
            "- [PRONOUNS] 'Sen/siz' and address words must stay consistent unless the relationship clearly changes in the story.",
            "- [TERMINOLOGY] Catchphrases, pet names, threats, and teasing formulas must repeat with the same Turkish wording every time.",
            "- [CONTEXT & TONE] Family, romance, workplace, and friendship dynamics must sound different; do not flatten everyone into one neutral register.",
            "- [FLOW & TIMING] Plot callbacks should echo earlier Turkish phrasing closely so continuity is audible to the viewer.",
            "- [FLOW & TIMING] Short reveal, reaction, and cliffhanger lines must stay short; do not expand them into explanatory prose.",
            "- [TERMINOLOGY] Show-specific lore, ranks, place names, and invented terms must remain fixed once chosen.",
            "- [CONTEXT & TONE] Recap intros always use the same fixed Turkish ('Önceki bölümlerde...'); recap lines reuse the original episode's Turkish phrasing where possible.",
            "- [TONE & REGISTER] Prestige drama (Breaking Bad, Succession) and soap/melodrama are different registers: prestige stays restrained and layered, soap is allowed open emotion.",
            "- [DIALECT & CHARACTER] Teen characters use current, natural Turkish teen speech — believable, not cringe adult-imitating-teen slang; adults around them stay adult.",
            "- [TR_ERROR] A common TR error here is voice drift across episodes: by episode 5 every character starts sounding the same — re-anchor each speaker's register at every scene.",
        ],
    },
    "film": {
        "name": "Film",
        "rules": [
            "- [TONE & REGISTER] Use controlled cinematic Turkish: natural and clean, but never sitcom-casual and never stage-play theatrical.",
            "- [CONTEXT & TONE] Translate subtext, not just meaning; a restrained threat, confession, or apology must still feel loaded.",
            "- [FLOW & TIMING] If a metaphor sounds dead when translated literally, replace it with a Turkish image that creates the same feeling.",
            "- [FLOW & TIMING] Big dramatic lines must land hard and clean; do not pad climactic moments with extra explanation.",
            "- [FLOW & TIMING] Silence, pauses, ellipses, and unfinished lines must keep tension; do not smooth them into fluent full sentences.",
            "- [TONE & REGISTER] If the source is simple, cold, or understated, keep it simple, cold, and understated in Turkish.",
            "- [CONTEXT & TONE] Voice-over narration is its own register, slightly more written than dialogue — keep narrator and character voices clearly distinct.",
            "- [CONTEXT & TONE] Read the film's genre blend and commit: noir narration, rom-com banter, biopic public-speech scenes, courtroom drama each pull the register differently.",
            "- [FLOW & TIMING] Iconic one-liners and quotable lines ('I'll be back') stay short and punchy — give them their Turkish equivalent weight in few words.",
            "- [TR_ERROR] A common TR error here is fake prestige: avoid archaic, bookish, or overwritten Turkish actors would never say.",
        ],
    },
    "horror_thriller": {
        "name": "Korku / Gerilim",
        "rules": [
            "- [FLOW & TIMING] Atmosphere is built from silence and short lines — never complete or expand half-finished sentences, the half-finished quality IS the dread.",
            "- [CONTEXT & TONE] Threat foreshadowing must stay subtextual; if the character knows something is wrong but isn't saying it, the Turkish keeps the same ambiguity.",
            "- [TONE & REGISTER] Warning lines ('Don't go in there', 'We shouldn't be here') get natural quiet Turkish, never theatrical or melodramatic.",
            "- [FLOW & TIMING] Screaming, panic, and breathless lines stay choppy and fragmented; fluent full Turkish sentences kill the panic.",
            "- [TONE & REGISTER] Villain monologues use cold, controlled register; psychopath lines should sound calmly disturbed, not operatic.",
            "- [FLOW & TIMING] Dialogue scarcity is intentional, never add filler to bridge silence.",
            "- [TERMINOLOGY] Scientist/expert exposition about the entity, disease, or curse must stay lore-precise and technical, not fantasy-flowery.",
            "- [TONE & REGISTER] Ritual, exorcism, occult-investigation scenes keep ceremonial gravity; do not let them slip into casual register.",
            "- [TERMINOLOGY] Body horror description keeps its somatic punch; do not euphemize wounds, transformations, or violence.",
            "- [TR_ERROR] A common TR error here is over-explaining the fear: if the source is vague, the Turkish must stay vague. Do not add dramatic exclamation like 'Tanrım! Olamaz!' unless present.",
        ],
    },
    "action_crime": {
        "name": "Aksiyon / Suç",
        "rules": [
            "- [FLOW & TIMING] Action lines are short, hard, and waste no time; suppress the urge to complete sentences or smooth out clipped exchanges.",
            "- [TERMINOLOGY] Use correct Turkish police/legal terminology: tanık, şüpheli, sanık, savcı, gözaltı, ihbar, suç ortağı, soruşturma — never generic 'kişi', 'olay', 'iş'.",
            "- [TONE & REGISTER] Military and SWAT commands are imperative and crisp: 'Yere yat', 'Çekil', 'Kıpırdama', 'Dağılın', 'Mevzilen' — not polite suggestions.",
            "- [TERMINOLOGY] Mafia/cartel hierarchy must show in voice: patron/babam, sağ kol, asker, kurye, haraç, koruma — terminology is power language.",
            "- [TERMINOLOGY] Underworld nicknames ('Joey the Hammer') may be naturalized cleverly in Turkish or kept literal — pick one strategy and stay consistent.",
            "- [FLOW & TIMING] Chase, shootout, and heist scenes use minimal natural Turkish: 'kahretsin', 'yürü, yürü', 'çık, çık', 'kapat', 'şimdi' — not flowery battle prose.",
            "- [TONE & REGISTER] Interrogation scenes keep cop hardness, suspect silence/denial, lawyer obstruction each in its own register.",
            "- [TERMINOLOGY] Legal drama subtype requires accurate Turkish court vocabulary (itiraz ediyorum, kabul, reddedildi, çapraz sorgu, suçunu kabul, savunma).",
            "- [TR_ERROR] A common TR error here is making action heroes sound polite: 'Wait' is 'DUR', not 'Bir saniye bekler misiniz' — keep the bark. Profanity and threats must use authentic Turkish street/criminal slang, never softened TV-Turkish.",
        ],
    },
    "romance_drama": {
        "name": "Romantik Drama",
        "rules": [
            "- [TONE & REGISTER] Intimate conversation tone dominates: short, halting lines with strong undertone — never pad them into flowing prose.",
            "- [TERMINOLOGY] Love confessions must avoid generic Turkish clichés; 'Seni seviyorum' is not auto-inserted everywhere — preserve the specific phrasing of the source.",
            "- [PRONOUNS] Class register matters: upper-middle, working-class, teen, mature relationship all sound different in Turkish (sen/siz choice, 'tatlım' vs 'sevgilim' vs 'aşkım').",
            "- [FLOW & TIMING] Confession scenes with cracked voice, swallowed words, and trailing-off must be preserved with '...' and broken phrasing.",
            "- [TONE & REGISTER] Jealousy, betrayal, and fight scenes stay sharp but realistic — never melodramatic stage-play Turkish, never wedding-soap-opera Turkish.",
            "- [TONE & REGISTER] Intimate/bedroom scenes use natural whispered Turkish with caught breath, not stiff dictionary translations of erotic vocabulary.",
            "- [CONTEXT & TONE] Family pressure, marriage expectation, cultural-conflict scenes ring familiar to Turkish viewers — let those rhythms exist naturally.",
            "- [TERMINOLOGY] Grief and loss scenes use authentic Turkish mourning vocabulary: 'başın sağ olsun', 'çok geçmiş olsun', 'Allah rahmet eylesin' (if religious), not flat 'üzgünüm'.",
            "- [CONTEXT & TONE] Romantic comedy subtype: keep sweet irony, do not over-egg it; bickering should sting like real bickering.",
            "- [TR_ERROR] A common TR error here is treating love dialogue like dictionary lookup, producing formal Turkish that strips all intimacy.",
        ],
    },
    "historical": {
        "name": "Tarihi / Dönem",
        "rules": [
            "- [TONE & REGISTER] Period-appropriate register MUST be selected: 1700s ('lütfederek bildirmek', 'arz etmek'), 1800-1900 ('muhterem', 'zat-ı âliniz'), early Cumhuriyet (öz-Türkçe), 1950-60 ('efendim', 'beyefendi', 'hanımefendi').",
            "- [TERMINOLOGY] Ottoman setting: layer in Arabic-Persian vocabulary that fits the era (selâm aleyküm, eyvallah, mübarek, hâlâ, vakıf, ferman) without mixing in modern Turkish.",
            "- [TERMINOLOGY] Court, military, legal, and religious terminology must be era-specific: paşa, vezir, kadı, ulema, sipahi, devşirme — never modernized.",
            "- [TERMINOLOGY] European/English historical drama: use established Turkish equivalents (lordum, sayın, leydim, vali, mareşal) where they exist; otherwise keep original title.",
            "- [TR_ERROR] ZERO modern slang or anglicisms in historical settings: 'literally', 'oh my God', 'dude', 'okay' are all anachronisms that destroy immersion.",
            "- [TONE & REGISTER] Religious texts, sermons, and ritual scenes preserve their period's formal liturgical register; never paraphrase into modern plain Turkish.",
            "- [TONE & REGISTER] Letter-reading scenes preserve epistolary tone: literary, formal, with archaic address forms.",
            "- [DIALECT & CHARACTER] Folk characters (peasants, soldiers) may use regional or folk Turkish, but do not exaggerate into cartoon dialect.",
            "- [TR_ERROR] A common TR error here is putting ALL historical characters into the same archaic Turkish; class, age, occupation, and faction must still differentiate voices.",
            "- [TR_ERROR] Another common TR error is mixing eras: early-Ottoman and late-Ottoman language are not the same, neither are Cumhuriyet and post-1980.",
        ],
    },
    "musical": {
        "name": "Müzikal / Şarkı",
        "rules": [
            "- [FLOW & TIMING] Song lyrics translation: meaning integrity ALWAYS outweighs rhyme — do not warp meaning to force a rhyme.",
            "- [FLOW & TIMING] Syllable/meter count should approximate the source line when sung; melodic flow must survive the translation.",
            "- [TERMINOLOGY] Refrains (nakarat) repeat with the SAME Turkish wording every time, never paraphrased variants.",
            "- [TONE & REGISTER] Solo vs duet vs chorus require different registers: solo intimate, duet conversational, chorus exclamatory and energetic.",
            "- [FLOW & TIMING] Fast rhythmic songs need tight syllable count; sustained 'ee', 'ay' vowels should map to suitable Turkish vowels for vocal performance.",
            "- [TONE & REGISTER] Sung-through musicals (Hamilton, Les Mis): translated lines must read as singable lyrics, literary but not novelistic.",
            "- [FLOW & TIMING] Spoken-to-sung transitions in the scene should glide smoothly in register, not jump.",
            "- [CONTEXT & TONE] Musical subgenre matters: Broadway, opera, hip-hop musical, jukebox, rock opera all need different Turkish — never translate Hamilton's rap into operatic Turkish.",
            "- [FLOW & TIMING] Song-internal metaphor and symbolism keep their semantic load while reading naturally in Turkish.",
            "- [TR_ERROR] A common TR error here is treating song lyrics as prose translation — losing rhythm, breath, and melodic singability.",
        ],
    },
    "comedy": {
        "name": "Komedi (Sitcom)",
        "rules": [
            "- [CONTEXT & TONE] This mode targets sitcoms and traditional ensemble comedies (Seinfeld, Friends, The Office, Brooklyn Nine-Nine, Modern Family, Yasak Elma, Avrupa Yakası).",
            "- [FLOW & TIMING] Keep the joke beat in the same place; if the laugh lands on the final word, the Turkish must also land there.",
            "- [TERMINOLOGY] Replace puns, idioms, and wordplay with a Turkish equivalent that gets a laugh, not a literal explanation.",
            "- [TR_ERROR] Never explain why something is funny; added explanation kills the joke instantly.",
            "- [FLOW & TIMING] Repetition, awkward pauses, false starts, and sudden cut-offs must be preserved because they carry timing.",
            "- [TERMINOLOGY] Running jokes and callbacks must reuse the same Turkish wording so the later payoff is recognizable.",
            "- [DIALECT & CHARACTER] Each ensemble character has a distinct voice (the nerd, the diva, the dad, the snarky one, the himbo) — keep them differentiated.",
            "- [TONE & REGISTER] Deadpan lines should stay flat and plain; do not make them more emotional, smarter, or more formal.",
            "- [TONE & REGISTER] Mockumentary subtype (The Office, Parks and Rec) needs talking-head confessional register slightly drier than scene dialogue.",
            "- [TR_ERROR] A common TR error here is cleanup: roast lines and banter should sting in everyday Turkish, not softened TV-speak.",
            "- [FLOW & TIMING] Do not over-translate canned filler ('Oh!', 'Wow!', 'Hmm?') into formal Turkish — these are reactions, keep them natural ('Aa!', 'Vay!', 'Hmm?').",
        ],
    },
    "sketch_comedy": {
        "name": "Sketch Komedi / Absürt",
        "rules": [
            "- [CONTEXT & TONE] Treat this as sketch/absurdist comedy translation mode (I Think You Should Leave, Key & Peele, SNL, Monty Python, Adult Swim shorts).",
            "- [DIALECT & CHARACTER] Each sketch character has an exaggerated one-note voice (clueless CEO, panicked guest, fake host); keep that exaggeration in Turkish — do not flatten.",
            "- [TONE & REGISTER] Mock-format parodies (fake news, fake corporate training) MUST use that format's authentic formal Turkish; the absurdity has to explode from inside the straight tone.",
            "- [TERMINOLOGY] Catchphrases and recurring lines ('Let's go!', 'I think you should leave') stay in the original language verbatim if key to the meme, or repeat identically in Turkish.",
            "- [FLOW & TIMING] The setup → punchline rhythm is sacred; the punch word must land on the final beat in Turkish too, never add explanatory clauses.",
            "- [TONE & REGISTER] Shock humor, crude jokes, uncensored profanity, and sexual material keep full force; this genre depends on full intensity.",
            "- [FLOW & TIMING] Absurd, surreal, or non-sequitur lines must be translated AS absurdly as the source; never 'correct' or 'rationalize' them.",
            "- [FLOW & TIMING] Improvised feel (half-finished sentences, 'şey', 'işte', 'yani' filler, self-corrections) must be preserved.",
            "- [TERMINOLOGY] Fictional proper names stay as-is; do NOT swap to Turkish names like Ahmet, Mehmet — preserve the foreign sketch-world.",
            "- [TONE & REGISTER] Mock-corporate, mock-academic, mock-clinical language must stay in their over-formal Turkish; the gag is the gap between formal register and deranged content.",
            "- [TR_ERROR] A common TR error here is making the character sound 'normal': the character IS supposed to sound absurd, off-key, weirdly intense, or robotically sincere.",
            "- [TR_ERROR] Another common TR error is overexplaining: if the source line is abrupt, broken, or nonsensical, the Turkish must be ALSO abrupt, broken, and nonsensical.",
        ],
    },
    "standup": {
        "name": "Stand-up Komedi",
        "rules": [
            "- [TONE & REGISTER] Single-performer voice addressed to a live audience — keep the rhythm of a person on stage thinking out loud, never write it like an essay.",
            "- [FLOW & TIMING] Personal story segments flow conversationally; do not literary-ize them, keep the 'I was at the airport last week and...' breath.",
            "- [TONE & REGISTER] Crowd work ('Where you from?') stays as direct natural Turkish ('Nerelisin?'); the comic's quick reaction to the answer must stay sharp.",
            "- [FLOW & TIMING] Setup → punch separation is sacred: setup neutral and clean, punch word stays in the punch position (end of line), never followed by explanation.",
            "- [TERMINOLOGY] Callbacks and running jokes must reuse identical Turkish wording from earlier in the set.",
            "- [DIALECT & CHARACTER] Comedian's signature register (deadpan, manic, observational, raunchy) must be preserved in Turkish — do not flatten everyone.",
            "- [TONE & REGISTER] Stand-up profanity, sexual material, race/politics/religion bits translate at FULL force — sanitized stand-up is broken stand-up.",
            "- [FLOW & TIMING] 'Tagging' (the small extra punch after the main punch) must stay in its own short beat, never merged.",
            "- [PRONOUNS] Crowd-friendly address ('y'all', 'guys') maps to natural Turkish equivalents ('millet', 'arkadaşlar', 'gençler') depending on the comic's persona.",
            "- [TR_ERROR] A common TR error here is translating stand-up as normal conversation, losing the precise word order and emphasis that makes the joke work.",
        ],
    },
    "comedy_biography_documentary": {
        "name": "Komedyen Biyografisi / Stand-up Belgeseli",
        "rules": [
            "- [CONTEXT & TONE] Biographical documentaries about comedians, comedy history, stand-up culture, censorship, clubs, writers' rooms, and performance careers.",
            "- [TONE & REGISTER] Distinguish documentary narration from quoted stage material: narration is reflective, stage clips keep joke timing and profanity.",
            "- [FLOW & TIMING] Setup, punchline, tag, callback, and crowd reaction language must be preserved when a routine is quoted.",
            "- [TERMINOLOGY] Comedy craft terms use natural Turkish: bit, set, punchline, callback, heckler, crowd work, open mic, club circuit, writer's room.",
            "- [DIALECT & CHARACTER] The comedian's persona is central; deadpan, ranting, observational, political, raunchy, or surreal voices must not flatten.",
            "- [CONTEXT & TONE] Social/political commentary in comedy keeps its bite; do not neutralize satire into polite analysis.",
            "- [TERMINOLOGY] Names of venues, albums, specials, TV shows, networks, and awards stay exact unless an established Turkish title exists.",
            "- [TR_ERROR] A common TR error here is translating biographical commentary well but ruining the actual jokes; when a joke is quoted, comedy rules override documentary smoothness.",
        ],
    },
    "cyberpunk_sci_fi": {
        "name": "Siberpunk / Distopya",
        "rules": [
            "- [CONTEXT & TONE] Keep the grim, technological, neon-noir tone. Corporations are oppressive, tech is ubiquitous, life is cheap.",
            "- [TERMINOLOGY] Tech jargon, implants, netrunning, corporate titles, AI, and hacking terms must sound like established sci-fi Turkish (e.g., 'Ağ' for net, 'Siber-implant' for cyberware).",
            "- [DIALECT & CHARACTER] Street characters speak with heavy slang/AAVE equivalents; corporate elites speak in sterile, formal, high-register Turkish.",
            "- [TONE & REGISTER] Nihilism and cynicism rule the dialogue. Do not soften cold or hopeless lines.",
            "- [FLOW & TIMING] Quick tactical jargon during combat/hacking must stay clipped and precise.",
            "- [PRONOUNS] Power dynamics are heavily reflected in pronouns; corporate bosses use 'sen' to underlings, street characters use casual 'sen' unless intimidated.",
            "- [TR_ERROR] A common TR error is translating cyberpunk concepts into fantasy/magic terms. Ensure it sounds like technology, not magic.",
        ],
    },
    "animation_kids": {
        "name": "Çocuk / Çizgi Dizi",
        "rules": [
            "- [TONE & REGISTER] Keep the tone bright, energetic, and accessible for children. Use natural, modern Turkish without overly archaic words.",
            "- [TERMINOLOGY] Catchphrases, magic spells, animal sounds, and character nicknames must be localized to fun, memorable Turkish equivalents.",
            "- [FLOW & TIMING] Action lines, gasps, and reactions should be slightly exaggerated. 'Yay!', 'Whoa!', 'Oh no!' become 'Yaşasın!', 'Vay canına!', 'Olamaz!'.",
            "- [PRONOUNS] Characters usually use 'sen' with each other; adults might use 'siz' depending on respect level.",
            "- [TR_ERROR] A common TR error is translating literal English idioms that make no sense to kids. Find a culturally equivalent Turkish idiom or phrase.",
            "- [DIALECT & CHARACTER] Ensure villain characters sound theatrically evil but not genuinely terrifying or profane.",
            "- [CONTEXT & TONE] Educational or moral lessons should be stated clearly and simply, matching the pedagogical tone of kids' shows.",
        ],
    },
    "anime": {
        "name": "Anime",
        "rules": [
            "- [TERMINOLOGY] Honorifics ('senpai', 'kun', 'chan', 'sama', 'sensei') need ONE consistent strategy: either keep all, drop all, or keep only relationally-significant ones.",
            "- [TERMINOLOGY] Attack names, special-move incantations, titles, and transformation phrases need ONE fixed Turkish (or kept-original) treatment.",
            "- [FLOW & TIMING] Battle cries, vows, oaths, and power-up lines stay short, explosive, exclamatory — never calm explanatory Turkish.",
            "- [DIALECT & CHARACTER] Character archetypes must stay distinct: tsundere bratty, ojou-sama noble, kuudere cold, yandere obsessive, genki energetic.",
            "- [PRONOUNS] Hierarchy is encoded in speech: senpai-kohai, master-disciple, sibling order — these show in Turkish word choice and sen/siz.",
            "- [TERMINOLOGY] Iconic Japanese reactions ('itadakimasu', 'arigatou', 'sumimasen') may stay original if globally recognizable, or take natural Turkish equivalent.",
            "- [CONTEXT & TONE] Subgenre register matters: shounen battle (loud, motivational), seinen mature (cool, restrained), slice-of-life (warm, easy) — pick by show.",
            "- [FLOW & TIMING] Internal monologue is huge in anime ('Naze... naze koko ni...?'): keep its dramatic internal quality.",
            "- [TERMINOLOGY] Sound effect tags ([gasp], [chuckle], [smirk]) translate to natural Turkish equivalents — never leave English.",
            "- [TR_ERROR] A common TR error here is flattening intensity: panic, devotion, awe, and rage must not become formal neutral speech.",
            "- [TR_ERROR] Another common TR error is romanticizing the Japaneseness — translate the meaning, do not over-decorate with 'oriental' Turkish flourishes.",
        ],
    },
    "kids_animation": {
        "name": "Çocuk Animasyonu",
        "rules": [
            "- [TONE & REGISTER] Target audience 4-12: clear vocabulary, short rhythmic sentences, no abstract or literary phrasing.",
            "- [CONTEXT & TONE] Educational-entertainment balance: deliver moral lessons through story, never as didactic statements.",
            "- [DIALECT & CHARACTER] Each animal/robot/magical creature character keeps a consistent fun Turkish voice across scenes.",
            "- [TONE & REGISTER] Child-appropriate slang only: no adult profanity, no double-meanings, no sexual references — but still let kids sound like kids.",
            "- [TERMINOLOGY] Catchphrases and theme songs translate identically every time (e.g. Bob the Builder: 'Yes we can!' always becomes the same Turkish phrase).",
            "- [CONTEXT & TONE] Pixar/Studio Ghibli depth: emotional themes (loss, fear, growing up, grief) must NOT be sanitized — these are made for adults too.",
            "- [TONE & REGISTER] Negative emotions (fear, sadness, anger) are translated honestly at child-appropriate intensity, never glossed over.",
            "- [FLOW & TIMING] Counting, alphabet, color, and animal-naming songs translate as functional teaching content in Turkish, not literal word matches.",
            "- [TERMINOLOGY] Onomatopoeia (booom, waaa, splat) maps to natural Turkish exclamations (bumm, waaa, şap, çat) — not left as English.",
            "- [FLOW & TIMING] 'Look! A butterfly!' enthusiasm tone must survive translation; flat 'Bir kelebek var.' kills the energy.",
            "- [TR_ERROR] A common TR error here is over-simplifying to baby-talk and losing character distinctness.",
            "- [TR_ERROR] Another common TR error is letting villain-character menace slip into adult-horror register; villain stays scary in a child-show way (Skeletor, Maleficent intensity, not Hannibal Lecter).",
        ],
    },
    "adult_animation": {
        "name": "Yetişkin Animasyonu",
        "rules": [
            "- [CONTEXT & TONE] Target: Rick and Morty, BoJack Horseman, Family Guy, South Park, Bob's Burgers — not anime, not sketch comedy, not regular sitcom.",
            "- [TONE & REGISTER] Adult irony tone preserved: sexual, political, existential, nihilist, and disturbing themes are normal here, never softened.",
            "- [TERMINOLOGY] Sci-fi/fantasy elements (alternate dimensions, sentient AI) get lore-consistent Turkish — not flowery, not childish.",
            "- [TERMINOLOGY] Pop culture references (Family Guy cutaways, Simpsons callbacks): keep proper names verbatim, never translate them away.",
            "- [TONE & REGISTER] Dark humor (suicide jokes, drug jokes, nihilism) translate at FULL strength — softening kills the genre's identity.",
            "- [FLOW & TIMING] Absurd situational comedy: preserve the absurdity, never make it 'make sense' in standard logic.",
            "- [FLOW & TIMING] Rapid-fire dialogue: keep short, punchy Turkish sentences, never expand for clarity.",
            "- [FLOW & TIMING] Long character monologues (BoJack's depressive internal voice, Rick's drunken rants) keep literary quality; do not flatten.",
            "- [TONE & REGISTER] Meta-humor and fourth-wall breaks ('this show', 'the writers'): preserve the layer of irony exactly.",
            "- [TONE & REGISTER] Sexual and crude humor stays uncensored; this is the genre's character.",
            "- [TR_ERROR] A common TR error here is treating adult animation like regular animation and sanitizing language — that destroys the show.",
        ],
    },
    "frp": {
        "name": "FRP / Masaustu Rol Yapma",
        "rules": [
            "- [CONTEXT & TONE] Specialist FRP / tabletop / grimdark translation mode for Warhammer 40K, Trench Crusade, D&D Dark Sun, Forgotten Realms, and similar settings.",
            "- [TERMINOLOGY] Preserve lore continuity like a setting bible: faction names, orders, legions, chapters, realms, deities, classes, and campaign-specific terminology must stay consistent.",
            "- [CONTEXT & TONE] Warhammer 40K tone: keep gothic militarism, Imperial bureaucracy, sacred technology, xenos/Chaos dread, Warp metaphysics, and codex-style faction language precise.",
            "- [CONTEXT & TONE] Trench Crusade tone: keep apocalyptic trench warfare, heresy, martyrdom, relics, infernal corruption, crusader theology, and brutal religious imagery solemn and severe.",
            "- [CONTEXT & TONE] D&D Dark Sun tone: keep Athas, sorcerer-kings, defilers, preservers, templars, gladiators, psionics, survival scarcity, desert brutality, and slave-city politics distinct.",
            "- [TERMINOLOGY] Translate rules text, mechanics, dice expressions, checks, saves, feats, abilities, spell effects, item properties, stat blocks, and sourcebook language with clear Turkish tabletop terminology.",
            "- [TERMINOLOGY] D&D-style terms must be stable: spell→büyü, cantrip→yönelim büyü/cantrip, feat→yetenek/feat, saving throw→kurtarma zarı, ability check→yetenek kontrolü, advantage→avantaj, AC→zırh sınıfı, HP→can puanı, dungeon→zindan, campaign→kampanya, subclass→alt sınıf, alignment→yönelim.",
            "- [TERMINOLOGY] Keep proper names such as characters, realms, planets, hive cities, chapters, warbands, gods, organizations, artifacts, spell names, books, codex names, and sourcebook titles unchanged unless established.",
            "- [TONE & REGISTER] Separate narrator/rules voice from character dialogue: mechanics should sound precise and readable, while character dialogue should keep rank, faith, threat, trauma, humor, class, and battlefield personality.",
            "- [CONTEXT & TONE] For YouTube videos, keep explanatory flow and creator energy natural, but do not sacrifice lore accuracy for casualness; jokes may be naturalized, names and taxonomy may not.",
            "- [TR_ERROR] A common TR error here is flattening taxonomy: do not translate all powers as generic 'yetenek', all realms as generic 'krallik', all orders as generic 'tarikat', or all wargear as generic 'silah'; keep the game/lore category precise.",
        ],
    },
    "warhammer40k": {
        "name": "Warhammer 40K / Grimdark",
        "rules": [
            "- [CONTEXT & TONE] Treat this as Warhammer 40,000 (40K) grimdark science-fantasy: gothic militarism, Imperial bureaucracy, religious-zealot fervor, sacred machine-cult technology, and the constant dread of Chaos, the Warp, and xenos.",
            "- [TERMINOLOGY] Keep iconic 40K terminology STABLE and recognizable; do NOT invent Turkish words for established lore. Leave proper-noun terminology unchanged: Astartes, Space Marine, Adeptus Mechanicus, Adeptus Astartes, Astra Militarum, Inquisition, Primarch, Commissar, psyker, servitor, servo-skull, gene-seed, bolter, chainsword, lasgun, power armour, the Warp, daemon, xenos, Ork, Aeldari/Eldar, Tyranid, Necron, T'au.",
            "- [TERMINOLOGY] Some terms have an ESTABLISHED Turkish form in the TR 40K community — prefer these: 'the Emperor'→'İmparator', 'the Imperium'→'İmparatorluk' (or keep 'Imperium' if the glossary does), 'heresy'→'sapkınlık', 'heretic'→'sapkın', 'the faithful'→'sadıklar'.",
            "- [FLOW & TIMING] Battle-cries, litanies, oaths and prayers must stay IMPACTFUL and liturgical, not literal-flat: 'For the Emperor!'→'İmparator için!', 'The Emperor protects.'→'İmparator korur.', 'Blood for the Blood God!'→'Kan Tanrısı için kan!', 'Death to the xenos!'→'Ölüm xenoslara!'",
            "- [PRONOUNS] Ranks/honorifics follow 40K usage, not civilian convention: 'Brother'→'Birader' (Astartes address), 'Brother-Captain'→'Birader-Yüzbaşı', 'my Lord'→'Lordum', 'Lord Commander'→'Lord Kumandan', 'Tech-Priest'→'Tekno-Rahip', 'Sergeant'→'Çavuş'.",
            "- [TERMINOLOGY] Preserve the Mechanicus / machine-cult register: 'Machine Spirit'→'Makine Ruhu', 'the Omnissiah', rites of activation, binary cant, and '++…++' vox/data formatting stay as-is; technology is SACRED, not casual.",
            "- [TONE & REGISTER] Keep a gothic, archaic-but-readable Turkish register for narration and lore: solemn, severe, weighty — avoid modern slang, memes and over-casual phrasing, but do NOT fake broken Ottoman Turkish.",
            "- [DIALECT & CHARACTER] Differentiate voices: a zealous Commissar, a cold Inquisitor, a stoic Astartes, a terrified Guardsman, and a cackling Chaos cultist must each keep their fear, faith, arrogance or madness.",
            "- [TR_ERROR] Do NOT flatten 40K taxonomy: a 'bolter' is not a generic 'silah', an 'Astartes' is not a generic 'asker', a 'Chapter' is not a generic 'birlik', the 'Warp' is not generic 'uzay'.",
        ],
        "glossary": {
            "Black Templars": "Black Templars",
            "Space Marine": "Space Marine",
            "Astartes": "Astartes",
            "Adeptus Astartes": "Adeptus Astartes",
            "Adeptus Mechanicus": "Adeptus Mechanicus",
            "Mechanicus": "Mechanicus",
            "Astra Militarum": "Astra Militarum",
            "Imperial Guard": "Imperial Guard",
            "Salamanders": "Salamanders",
            "Imperial Fists": "Imperial Fists",
            "Ultramarines": "Ultramarines",
            "Grey Knights": "Grey Knights",
            "Blood Angels": "Blood Angels",
            "Dark Angels": "Dark Angels",
            "Space Wolves": "Space Wolves",
            "Adepta Sororitas": "Adepta Sororitas",
            "Sisters of Battle": "Sisters of Battle",
            "Inquisition": "Inquisition",
            "Inquisitor": "Inquisitor",
            "Ordo Malleus": "Ordo Malleus",
            "High Marshal": "Yüksek Mareşal",
            "High Marshall": "Yüksek Mareşal",
            "Marshal": "Mareşal",
            "Chaplain": "Vaiz",
            "Reclusiarch": "Reclusiarch",
            "Brother-Captain": "Birader-Yüzbaşı",
            "Brother-Sergeant": "Birader-Çavuş",
            "Sergeant": "Çavuş",
            "Commissar": "Komiser",
            "Tech-Priest": "Tekno-Rahip",
            "Magos": "Magos",
            "Canoness": "Canoness",
            "Primarch": "Primarch",
            "Brother": "Birader",
            "the Emperor": "İmparator",
            "Emperor": "İmparator",
            "God-Emperor": "Tanrı-İmparator",
            "Imperium": "İmparatorluk",
            "heresy": "sapkınlık",
            "heretic": "sapkın",
            "heretics": "sapkınlar",
            "crusade": "haçlı seferi",
            "arch-enemy": "baş düşman",
            "the faithful": "sadıklar",
            "relic": "kutsal emanet",
            "Chaos": "Kaos",
            "daemon": "iblis",
            "daemons": "iblisler",
            "the Warp": "Warp",
            "Warp": "Warp",
            "xenos": "xenos",
            "psyker": "psyker",
            "servitor": "servitor",
            "gene-seed": "gen-tohumu",
            "bolter": "bolter",
            "bolt pistol": "bolt tabancası",
            "chainsword": "chainsword",
            "power armour": "güç zırhı",
            "power armor": "güç zırhı",
            "Machine Spirit": "Makine Ruhu",
            "Omnissiah": "Omnissiah",
            "hive city": "kovan şehir",
            "forge world": "dövüm dünyası",
            "Chapter": "Chapter",
            "For the Emperor": "İmparator için",
            "The Emperor protects": "İmparator korur",
        },
    },
    "youtube_edu": {
        "name": "YouTube / Eğitim",
        "rules": [
            "- [TONE & REGISTER] The voice should sound like a smart friend explaining something cool, not a stiff teacher and not a formal documentary.",
            "- [PRONOUNS] Direct viewer address should default to 'sen', 'biz', and 'hadi'; formal 'siz' usually breaks the channel voice.",
            "- [FLOW & TIMING] Hook lines and rhetorical turns must stay hooky; 'But here's the weird part' should still feel like a click-worthy pivot in Turkish.",
            "- [TERMINOLOGY] Technical terms should be introduced inside flowing speech, not with glossary-style or textbook-style Turkish.",
            "- [FLOW & TIMING] Lists, step markers, recap lines, and signposts must stay obvious so the viewer can follow the structure by ear.",
            "- [FLOW & TIMING] ALL CAPS or italic emphasis should become natural Turkish emphasis like 'resmen', 'bildiğin', 'tam anlamıyla'.",
            "- [TONE & REGISTER] Sponsor or ad-read sections should sound lightly promotional and a bit awkward, not like corporate brochure copy.",
            "- [TR_ERROR] A common TR error here is line merging: short pivots like 'Now', 'So', 'Here's the thing' must stay separate.",
        ],
    },
    "youtube": {
        "name": "YouTube / Street",
        "rules": [
            "- [TONE & REGISTER] The voice must sound like spontaneous street/internet Turkish, not standard TV Turkish and not translationese.",
            "- [TERMINOLOGY] Never transliterate slang; map 'bro'→kanka/kardeşim, 'no cap'→harbi/yalansız, 'for real'→harbiden, 'lowkey'→içten içe/hafiften, 'y'all'→millet/sizler, 'ain't' to Turkish vibe-equivalents.",
            "- [FLOW & TIMING] Broken grammar, fragments, double negatives, and repeats must stay rough when the speaker sounds rough.",
            "- [TONE & REGISTER] Profanity, sexual slang, flexing, and taunts should keep full force.",
            "- [TERMINOLOGY] Ad-libs, reaction sounds, and filler noises should be rendered as Turkish speech sounds, not left in English.",
            "- [FLOW & TIMING] Fast stream-of-consciousness lines must stay chopped and breathless; do not combine short sentences into polished prose.",
            "- [TERMINOLOGY] Meme and platform slang should use the closest TR internet equivalent, or stay as the meme label if already known (e.g. clickbait, cringe, spam).",
            "- [TR_ERROR] A common TR error here is sterilization: confessionals should feel like a voice note to a friend, not an interview transcript.",
        ],
    },
    "podcast_interview": {
        "name": "Podcast / Mülakat",
        "rules": [
            "- [FLOW & TIMING] Long-form conversation tone: natural flow with breaks, restarts, and overlap — never tidy into perfect sentences.",
            "- [DIALECT & CHARACTER] Host vs guest voices stay differentiated: host probes and steers, guest opens up and shares — do not merge them.",
            "- [TONE & REGISTER] Contested or disagreement moments keep each speaker's own register, do not paper over the friction.",
            "- [FLOW & TIMING] Continuous-attention noises ('right', 'yeah', 'mm-hmm') map to natural Turkish ('evet', 'aynen', 'tabii', 'haklısın') without overdoing them.",
            "- [FLOW & TIMING] Storytelling segments by the guest keep half-finished clauses, self-corrections, and tangents — the messiness IS the authenticity.",
            "- [DIALECT & CHARACTER] The guest's jokes, dry humor, and ironic asides reflect their personality; do not flatten into neutral commentary.",
            "- [TONE & REGISTER] Sponsor reads are tonally distinct: lightly promotional, often slightly awkward — preserve that 'ad break' texture.",
            "- [DIALECT & CHARACTER] Two-host-banter podcasts need both hosts in distinct Turkish registers (the loud one, the dry one, the straight man).",
            "- [CONTEXT & TONE] Heavy/serious episode topics (death, addiction, abuse) keep gravity; never let casual Turkish slip in.",
            "- [TERMINOLOGY] Field-specific jargon (psychology, economics, AI, neuroscience) uses correct Turkish technical terminology, not amateur paraphrase.",
            "- [FLOW & TIMING] Recording-environment cues ('Can you hear me?', 'My mic is bad') stay as natural studio chatter.",
            "- [TR_ERROR] A common TR error here is treating podcast like a news anchor — strip the formality, restore the looseness.",
        ],
    },
    "news": {
        "name": "Haber / Aktüalite",
        "rules": [
            "- [TERMINOLOGY] Formal news register: muhabir, sunucu, kaynak, açıklama, iddia, taraf, görgü tanığı, çevre kaynakları — professional journalism terminology.",
            "- [TONE & REGISTER] Fact vs claim distinction MUST survive translation: 'X dedi' vs 'X olduğu iddia ediliyor' vs 'X olduğu bildirildi' — the certainty/uncertainty level is mandatory.",
            "- [TERMINOLOGY] Numbers, names, institutions, dates, units, places stay EXACT and complete — no rounding, no simplification.",
            "- [TONE & REGISTER] Anchor tone: professional, measured, no sensationalism, no rhetorical questions, no emotional coloring.",
            "- [TONE & REGISTER] Field reporter / live correspondent slightly more dynamic than studio anchor, but still professional Turkish broadcast register.",
            "- [TONE & REGISTER] Interview segments: reporter asks polite but pointed questions; do not soften interviewee's evasions.",
            "- [TERMINOLOGY] Weather, sports, finance, economy segments use their own technical Turkish (yağış olasılığı, basınç, devre arası, döviz kuru, endeks, faiz).",
            "- [CONTEXT & TONE] Disaster, war, and crisis coverage avoids dramatization: 'büyük hasar var' is enough, 'felaket boyutunda yıkım' is editorialization.",
            "- [CONTEXT & TONE] Political news stays neutral; partisan markers ('iddia eden taraf', 'muhalefete göre') must be carried through accurately.",
            "- [TONE & REGISTER] Tabloid/celebrity news uses lighter Turkish but still preserves epistemic hedging ('iddia edildi', 'kaynaklara göre').",
            "- [TR_ERROR] A common TR error here is dramatizing news copy and breaking the source's neutrality.",
        ],
    },
    "gaming": {
        "name": "Oyun Yayını / Streamer",
        "rules": [
            "- [TONE & REGISTER] Streamer voice: single performer talking to chat/audience, narrating gameplay while reacting to viewers.",
            "- [PRONOUNS] Twitch/YouTube chat interaction: 'chat, görüyor musunuz?', 'yorumlardan yazın', 'donate geldi' — keep second-person engagement.",
            "- [TERMINOLOGY] Gaming jargon stays in original form: boss, loot, build, meta, nerf, buff, gank, lane, ping, push, ult, cooldown, respawn, AFK, GG, lag, hitbox — DO NOT force Turkish equivalents.",
            "- [TERMINOLOGY] Game titles, character names, map names, item names DO NOT translate ('League of Legends', 'Faker', 'Dust 2', 'AK-47') — these are proper nouns.",
            "- [TERMINOLOGY] Reaction lines ('no way', 'holy shit', 'GG', 'EZ') map to authentic Turkish gamer reactions ('yok artık', 'yok daha neler', 'gg', 'ezzz').",
            "- [TONE & REGISTER] Humor, swearing, rage moments, salt translate full-force in natural Turkish gamer slang.",
            "- [TONE & REGISTER] Tutorial/walkthrough videos: calmer explanatory tone, but jargon still stays.",
            "- [TERMINOLOGY] Speedrun and challenge content: technical terms (glitch, frame perfect, RNG, optimal route, world record pace) must be accurate.",
            "- [CONTEXT & TONE] Game lore content (cutscenes, voice acting): use the game's own register — formal if formal, casual if casual.",
            "- [CONTEXT & TONE] Esports broadcast: caster/analyst tone, jargon-heavy, fast — match the energy of Turkish esports broadcasting.",
            "- [TR_ERROR] A common TR error here is forcing all gaming jargon into Turkish ('kontrol noktası' for 'checkpoint', 'sersemletme' for 'stun') — the community uses English terms, respect that.",
        ],
    },
    "academic_lecture": {
        "name": "Akademik Ders / Felsefe / Mitoloji",
        "rules": [
            "- [CONTEXT & TONE] Academic lecture translation mode for philosophy, mythology, classics, theology, and humanities seminars (university lectures, conference talks).",
            "- [TONE & REGISTER] Register is academic-formal but NOT theatrical: a real lecturer's voice — measured, precise, occasionally passionate.",
            "- [TERMINOLOGY] Philosophical terminology uses established Turkish academic equivalents: ousia→öz/cevher, eidos→idea/form, telos→erek/gaye, episteme→bilgi/episteme, doxa→sanı/doxa, logos→logos, arche→arkhe, dasein→dasein, phenomenon→fenomen, a priori→a priori, sui generis→kendine özgü.",
            "- [TERMINOLOGY] When a foreign term is introduced, BOTH the original (Greek/Latin/German) and the Turkish gloss stay together on first mention: 'aretê (erdem)', 'eudaimonia (mutluluk)'.",
            "- [TERMINOLOGY] Ancient Greek philosopher names follow Turkish academic transliteration: Platon (NOT Plato), Aristoteles (NOT Aristotle), Sokrates (NOT Socrates), Demokritos, Herakleitos, Pythagoras.",
            "- [TERMINOLOGY] Modern Western philosopher names stay in original spelling: Kant, Hegel, Nietzsche, Heidegger, Wittgenstein, Foucault, Derrida, Sartre.",
            "- [TERMINOLOGY] Work titles use established Turkish translations when they exist: 'Republic'→'Devlet', 'Symposium'→'Şölen', 'Nicomachean Ethics'→'Nikomakhos'a Etik', 'Being and Time'→'Varlık ve Zaman'.",
            "- [TERMINOLOGY] Greek/Roman mythology names use Turkish-Greek transliteration tradition: Zeus, Apollon (NOT Apollo), Athena, Herakles (NOT Hercules), Odysseus (NOT Ulysses), Aphrodite.",
            "- [TERMINOLOGY] Eastern mythology and philosophy keep each tradition's terminology intact: Hindu (dharma, karma, atman, brahman, moksha, samsara), Buddhist (nirvana, anatta, sangha, bodhicitta), Daoist (dao, wuwei, qi, yin-yang), Norse (Ragnarök, Yggdrasil).",
            "- [TERMINOLOGY] Comparative religion sections respect each tradition's native vocabulary: Sufi (cezbe, vecd, hâl, fenâ), Christian (Holy Trinity→Teslis, Eucharist→Efkaristiya), Jewish (Shabbat, Torah, Talmud, Kabbalah), Islamic (tevhid, kelam, fıkıh).",
            "- [TONE & REGISTER] Antique quotations and source texts keep literary register (a Homer fragment, a Vedic hymn, a Tao Te Ching verse) — NEVER over-modernize.",
            "- [FLOW & TIMING] The lecturer's rhetorical structure — long sentences, parenthetical asides — MUST be preserved; do not chop into short sentences because the logic LIVES in the syntax.",
            "- [CONTEXT & TONE] Tonal shift between mythos and logos: when RECOUNTING a myth, narration becomes mythic; when ANALYZING it, voice shifts to analytical.",
            "- [TR_ERROR] A common TR error here is treating philosophy as ordinary conversation and stripping the careful logical structure; Aristoteles'in ayrımları kıl payı değildir, koruyun.",
        ],
    },
    "mythology_ancient_world": {
        "name": "Mitoloji / Antik Dünya",
        "rules": [
            "- [CONTEXT & TONE] Myth retellings, ancient-world documentaries, Greek/Roman/Norse/Egyptian myths, legends, epics, gods, heroes, and oral-storytelling adaptations.",
            "- [TERMINOLOGY] Mythological names follow Turkish convention where established: Zeus, Hera, Athena, Apollon, Herakles, Odysseus, Ares, Afrodit, Hades.",
            "- [TERMINOLOGY] Do not modernize myth concepts too casually: oracle, prophecy, sacrifice, underworld, fate, hubris, nymph, muse, titan, demigod need stable Turkish choices.",
            "- [TONE & REGISTER] Retold myths may be story-like and vivid; analysis/interview sections become more scholarly. Keep the shift visible.",
            "- [FLOW & TIMING] Oral storyteller rhythm, repeated formulas, and ritual phrases should echo consistently across episodes.",
            "- [DIALECT & CHARACTER] Gods, heroes, narrators, and comic side characters may have different registers; do not make all mythical speech equally grand.",
            "- [TERMINOLOGY] Ancient place names and peoples use accepted Turkish forms where common: Antik Yunan, Troya, Girit, Mısır, Roma, Sparta, Atina.",
            "- [TR_ERROR] A common TR error here is either over-modernizing myth into slang or over-elevating it into fake archaic Turkish; keep it vivid but readable.",
        ],
    },
    "esoteric_occult": {
        "name": "Ezoterik / Okült",
        "rules": [
            "- [CONTEXT & TONE] Specialist esoteric, occult, hermetic, mystical, and spiritual translation mode covering tarot, astrology, kabbalah, alchemy, shamanism, demonology.",
            "- [TERMINOLOGY] Preserve tradition-specific terminology: sephirot, qliphoth, ain soph, gematria, Major/Minor Arcana, suits, decans, transits, retrograde, sigil, talisman, athame, athanor, prima materia, magnum opus.",
            "- [TERMINOLOGY] Names of spirits, deities, angels, demons, archons, egregores, and paths (Metatron, Sandalphon, Choronzon, Baphomet, Asmodeus, Lilith, Hekate, Thoth-Hermes, Sophia, Abraxas) stay unchanged unless established.",
            "- [TONE & REGISTER] Grimoire and ritual texts keep solemn, archival, ritualistic register; do not modernize or casualize incantations, invocations, or consecrations.",
            "- [TERMINOLOGY] Tarot readings must keep card names, reversed/upright distinctions, spread positions (Celtic Cross, Tree of Life spread), and elemental/planetary attributions precise.",
            "- [TERMINOLOGY] Astrology must keep signs, planets, houses, aspects (conjunction, opposition, square, trine, sextile), dignities (domicile, detriment, fall), lunar nodes, and chart-reading vocabulary technically accurate.",
            "- [CONTEXT & TONE] Hermetic and alchemical language must preserve the symbolic layer: a 'marriage of sulphur and mercury' is not a chemistry note; 'dissolve and coagulate' is solve et coagula, not a cooking instruction.",
            "- [TERMINOLOGY] Kabbalistic material must distinguish Hebrew transliterations (Keter, Chokmah, Binah) from their Turkish glosses.",
            "- [TONE & REGISTER] Channeled material, prophetic visions, and trance speech should keep their visionary, fragmented, or oracular quality.",
            "- [CONTEXT & TONE] For YouTube esoteric content, keep creator warmth and accessibility, but lock tradition terms.",
            "- [TR_ERROR] A common TR error here is debunking-tone leakage: even if the translator is skeptical, the Turkish output must read as the tradition presents itself; do not insert 'sözde' that mock the source.",
            "- [TR_ERROR] Another common TR error is new-age flattening: ceremonial magic, traditional witchcraft, hermetic alchemy, and Vedic astrology must each keep their own technical taxonomy.",
        ],
    },
    "scifi_fantasy": {
        "name": "Bilim Kurgu / Fantastik",
        "rules": [
            "- [TERMINOLOGY] World-building terminology (ships, planets, species, factions, magic systems, spells, orders, technologies) gets ONE fixed Turkish-or-original treatment.",
            "- [TERMINOLOGY] Follow established Turkish franchise conventions: 'the Force'→'Güç', 'lightsaber'→'ışın kılıcı', 'Middle-earth'→'Orta Dünya', 'White Walkers'→'Ak Gezenler', 'muggle'→'muggle'.",
            "- [TERMINOLOGY] Technobabble (warp drive, hyperspace, nanites, terraforming, FTL) uses Turkish sci-fi convention: established loanwords stay (warp, hiperuzay, nano-).",
            "- [TERMINOLOGY] Invented units, dates, currencies, and measurements (parsecs, credits, cycles, moons) stay as the source built them — never convert.",
            "- [TONE & REGISTER] Medieval-flavored fantasy dialogue gets measured, slightly elevated Turkish — but NEVER fake Ottoman pastiche; lords and peasants still need distinct registers.",
            "- [FLOW & TIMING] Prophecies, oracles, and ancient inscriptions keep poetic-elevated register and repeat with IDENTICAL Turkish wording at every callback.",
            "- [TONE & REGISTER] AI, robot, and synthetic voices keep a flat, precise, slightly inhuman register clearly distinct.",
            "- [DIALECT & CHARACTER] Alien/creature speech quirks (broken syntax, formal hyper-correctness, hive-mind plural) are character identity — mirror the quirk in Turkish.",
            "- [TERMINOLOGY] Magic incantations and ritual phrases: decide keep-original vs translate ONCE at first occurrence.",
            "- [TR_ERROR] A common TR error here is explaining the world to the viewer: if the source drops you into jargon without explaining, the Turkish trusts the viewer the same way.",
        ],
    },
    "medical": {
        "name": "Tıbbi Dram / Hastane",
        "rules": [
            "- [TERMINOLOGY] Use the vocabulary real Turkish doctors use: entübe et, taburcu, konsültasyon, sevk, nöbet, anamnez, vaka — never dictionary-translate medical jargon.",
            "- [TONE & REGISTER] Emergency commands are short and imperative: 'Tansiyon düşüyor', 'Adrenalin ver', 'Şok hazırla', '200'e şarj', 'Entübe ediyorum' — never polite full sentences in a code blue.",
            "- [TONE & REGISTER] Doctor-to-doctor jargon vs doctor-to-patient plain language are DIFFERENT registers; when the doctor explains to the patient, the Turkish must simplify too.",
            "- [TERMINOLOGY] Abbreviations map to Turkish hospital usage: BP→tansiyon, OR→ameliyathane, ICU→yoğun bakım, ER→acil, CBC→hemogram, MRI→MR, CT→BT.",
            "- [TERMINOLOGY] Disease, anatomy, and procedure names use established Turkish medical forms (miyokard enfarktüsü, apandisit, lomber ponksiyon); drug brand names stay as-is.",
            "- [TONE & REGISTER] Bad-news scenes ('I'm sorry, we did everything we could') use the measured, real phrasing Turkish doctors actually use.",
            "- [FLOW & TIMING] Patient and family panic stays broken, repetitive, and emotional; do not tidy.",
            "- [PRONOUNS] Hospital hierarchy shows in speech: intörn, asistan, uzman, doçent, başhekim, hemşire — junior-to-senior uses 'hocam' and siz.",
            "- [TERMINOLOGY] Ethics-committee, malpractice, and consent scenes need accurate Turkish medico-legal vocabulary (onam, endikasyon, komplikasyon, malpraktis).",
            "- [TR_ERROR] A common TR error here is softening or hardening prognosis hedges: 'might not make it through the night' has an exact certainty level — keep it.",
        ],
    },
    "war_military": {
        "name": "Savaş / Askeri",
        "rules": [
            "- [TERMINOLOGY] Ranks use Turkish military equivalents consistently: private→er, corporal→onbaşı, sergeant→çavuş, lieutenant→teğmen, captain→yüzbaşı, major→binbaşı, colonel→albay, general→general.",
            "- [TONE & REGISTER] Orders are crisp imperatives: 'Mevzilen', 'Ateş', 'Siper al', 'İlerle', 'Geri çekil', 'Ateşi kes'.",
            "- [TERMINOLOGY] Radio protocol keeps procedural texture: 'Anlaşıldı', 'Tamam', 'Tekrar et', 'Duyuyor musun' — call signs (Bravo Six, Eagle One) stay original.",
            "- [TERMINOLOGY] Weapon, vehicle, and equipment designations stay as-is (M16, AK-47, Humvee, F-16); only generic terms take natural Turkish (tüfek, helikopter, mermi).",
            "- [TONE & REGISTER] Soldier banter is crude, dark, and fatalistic — gallows humor and profanity at full force; sanitized soldiers are fake.",
            "- [FLOW & TIMING] Combat chaos lines stay fragmented and overlapping ('Contact left!', 'Man down!', 'Cover me!') → ('Sol tarafta temas!', 'Adam vuruldu!', 'Koru beni!').",
            "- [TONE & REGISTER] Briefing scenes use formal operational register: harita, hedef, koordinat, intikal, keşif, takviye — precise and unemotional.",
            "- [CONTEXT & TONE] PTSD, grief, and aftermath scenes are restrained and numb when the source is — do not inject emotion.",
            "- [CONTEXT & TONE] Era matters: WW2, Vietnam, modern, and future warfare each have their own vocabulary and discipline texture.",
            "- [TR_ERROR] A common TR error here is heroic-epic Turkish where the source is procedural and numb — match the source's temperature.",
        ],
    },
    "sports": {
        "name": "Spor / Maç Yayını",
        "rules": [
            "- [TONE & REGISTER] Turkish sports broadcasting register: energetic but professional spiker voice — excitement is real but vocabulary is precise.",
            "- [TERMINOLOGY] Use the Turkish sports community's actual terminology: ofsayt, korner, penaltı, faul, ribaund, smaç, blok, ace, tie-break, brek, grid, pole pozisyonu, pit.",
            "- [TERMINOLOGY] Scores, statistics, times, distances, and records stay EXACT — never round, never approximate.",
            "- [TERMINOLOGY] Player, team, stadium, and tournament names stay unchanged; established Turkish forms only where tradition exists (Şampiyonlar Ligi).",
            "- [FLOW & TIMING] Play-by-play excitement crescendos are preserved — rising repetition, exclamation, the long 'GOOOL' energy.",
            "- [TONE & REGISTER] Analyst/studio segments use a calmer tactical register (pres, blok düzeni, oyun kurulumu) clearly distinct.",
            "- [TONE & REGISTER] Post-match athlete interviews keep their honest cliché register ('takım olarak iyi mücadele ettik', 'üç puan önemliydi').",
            "- [CONTEXT & TONE] Each sport has its own Turkish jargon: football, basketball, volleyball, tennis, F1, boxing/MMA, athletics — never mix them.",
            "- [TR_ERROR] A common TR error here is neutralizing the spiker: excited play-by-play must NOT become flat narration; match the energy curve.",
        ],
    },
    "food_travel": {
        "name": "Yemek / Seyahat",
        "rules": [
            "- [TERMINOLOGY] Dish names keep their original form with an optional Turkish gloss on first mention: 'coq au vin (şarapta tavuk)', 'pad thai', 'ceviche' — NEVER invent literal translations.",
            "- [TERMINOLOGY] Cooking techniques use real Turkish kitchen vocabulary: soteleme, karamelize etme, mühürleme, benmari, marine etme, kısık ateşte pişirme.",
            "- [FLOW & TIMING] Taste and texture language stays vivid and sensory in natural Turkish (çıtır çıtır, ağızda dağılıyor, dumanı üstünde).",
            "- [TONE & REGISTER] Host wonder and curiosity stays warm and personal ('şuna bakın', 'inanılmaz kokuyor') — not documentary-stiff.",
            "- [TONE & REGISTER] Local people and street vendors keep their warmth and simple directness; their hospitality lines ring natural.",
            "- [TERMINOLOGY] Spoken measurements convert naturally (a cup of flour → bir su bardağı un, an ounce → ~30 gram) but on-screen recipe text stays exact.",
            "- [TERMINOLOGY] Place names use established Turkish exonyms where they exist: Münih, Köln, Kudüs, Atina, Pekin — otherwise original spelling.",
            "- [TONE & REGISTER] Fine-dining vs street-food registers differ: Michelin tasting-menu language is composed, street food is loud and immediate.",
            "- [TR_ERROR] A common TR error here is translating dish names literally into absurd Turkish ('toad in the hole' is NOT 'delikteki kurbağa').",
        ],
    },
    "true_crime": {
        "name": "Suç Belgeseli / True Crime",
        "rules": [
            "- [CONTEXT & TONE] True-crime documentary about REAL cases (not fiction): real victims, perpetrators and investigators — translate with gravity.",
            "- [TERMINOLOGY] Keep legal/forensic/police terminology accurate: 'suspect'→'şüpheli', 'defendant'→'sanık', 'prosecutor'→'savcı', 'indictment'→'iddianame', 'verdict'→'karar', 'conviction'→'mahkumiyet', 'parole'→'şartlı tahliye', 'autopsy'→'otopsi', 'coroner'→'adli tabip', 'first-degree murder'→'birinci derece cinayet'.",
            "- [TERMINOLOGY] Real names of people, places, case names, dates and case numbers stay EXACTLY as in the source.",
            "- [DIALECT & CHARACTER] Distinguish three voices: measured documentary narrator, emotional first-person interview testimony, and clinical expert commentary.",
            "- [FLOW & TIMING] Interview and testimony speech keeps its raw, broken, emotional quality (grief, fear, hesitation) — do NOT tidy.",
            "- [TONE & REGISTER] Keep the somber, restrained tone; avoid jokey or melodramatic Turkish. The horror is in the facts.",
            "- [TERMINOLOGY] Police/legal procedure phrasing must be correct Turkish: 'read his rights'→'haklarını okudu', 'taken into custody'→'gözaltına alındı', 'cold case'→'faili meçhul dosya'.",
            "- [TR_ERROR] A common TR error here is dramatizing news/case copy and breaking the source's neutrality or factual gravity.",
        ],
    },
    "cinema_film": {
        "name": "Sinema / Film Belgeseli",
        "rules": [
            "- [CONTEXT & TONE] Documentary or video-essay ABOUT cinema (film history, criticism, a director's work) — NOT fiction film dialogue; register is analytical.",
            "- [TERMINOLOGY] Film titles: use the ESTABLISHED Turkish release title if one exists ('The Godfather'→'Baba', 'Vertigo'→'Ölüm Korkusu'); otherwise keep original.",
            "- [TERMINOLOGY] Director, actor, screenwriter, studio and character names stay EXACTLY as written.",
            "- [TERMINOLOGY] Keep film-craft terminology precise and standard: 'shot'→'plan/çekim', 'cut'→'kesme', 'mise-en-scène'→'mizansen', 'montage'→'kurgu/montaj', 'framing'→'kadraj', 'close-up'→'yakın çekim', 'tracking shot'→'kaydırma çekim', 'depth of field'→'alan derinliği'.",
            "- [DIALECT & CHARACTER] Distinguish narrator/critic analysis from QUOTED film dialogue or interview clips.",
            "- [TERMINOLOGY] Movements, genres and eras use accepted Turkish/critical names: 'New Wave'→'Yeni Dalga', 'film noir'→'kara film/film noir', 'auteur'→'auteur', 'silent era'→'sessiz sinema dönemi'.",
            "- [TONE & REGISTER] Cinephile/critical register: keep the passion and precision of film writing — do not flatten.",
            "- [TR_ERROR] A common TR error here is translating film titles literally into absurd Turkish or inventing new titles for famous classics.",
        ],
    },
    "art_culture": {
        "name": "Sanat / Kültür Belgeseli",
        "rules": [
            "- [CONTEXT & TONE] Art / culture documentary (painting, sculpture, architecture, art history) — register is cultured, appreciative and precise, like a museum guide.",
            "- [TERMINOLOGY] Artist names, artwork titles, museums and places stay as written; use the established Turkish title of a famous work if one exists ('The Starry Night'→'Yıldızlı Gece').",
            "- [TERMINOLOGY] Keep art terminology accurate and standard: 'brushstroke'→'fırça darbesi', 'composition'→'kompozisyon', 'perspective'→'perspektif', 'chiaroscuro'→'ışık-gölge', 'fresco'→'fresk', 'still life'→'natürmort'.",
            "- [TERMINOLOGY] Movements and periods use accepted Turkish names: 'Renaissance'→'Rönesans', 'Impressionism'→'İzlenimcilik', 'Baroque'→'Barok', 'Cubism'→'Kübizm'.",
            "- [DIALECT & CHARACTER] Distinguish the narrator's flowing storytelling from QUOTED letters or diaries — quotations keep their period, literary register.",
            "- [TONE & REGISTER] Keep the sense of wonder and cultural weight; avoid dry encyclopedic Turkish AND over-casual slang.",
            "- [TR_ERROR] A common TR error here is new-age flattening or over-modernizing historical concepts; keep artistic taxonomy precise.",
        ],
    },
    "gonzo_science": {
        "name": "Gonzo Bilim / Kimya Belgeseli",
        "rules": [
            "- [CONTEXT & TONE] Gonzo science, chemistry, and drug-culture investigative documentary (Hamilton's Pharmacopeia, Vice investigative science, drug anthropology and ethnobotany).",
            "- [TERMINOLOGY] Scientific, chemical, and botanical terminology must be absolutely precise: keep chemical names (5-MeO-DMT, ketamine, psilocybin, xenon), plant/animal species (*Bufo alvarius*, *Lophophora williamsii*), and pharmacological terms (agonist, reuptake inhibitor, receptor) scientifically accurate.",
            "- [TONE & REGISTER] Gonzo/first-person narrator tone: the host is an active participant, curious, intellectual, and slightly informal — translate narrator's voice-over as engaging, conversational, yet intellectually rigorous.",
            "- [DIALECT & CHARACTER] Underground lab and chemist scenes: keep lab jargon (reflux condenser, synthesis, precursors, glassware) and underground chemist street/lab slang authentic; do not sanitize or over-formalize.",
            "- [CONTEXT & TONE] Shamanic and ritual contexts: when dealing with traditional medicine, shamans, or indigenous rituals (Ayahuasca, Peyote, Iboga), use respectful and accurate ethnographic/ritual vocabulary (ritüel, şaman, vizyon, trans, ruhsal rehber).",
            "- [TERMINOLOGY] Policy and harm-reduction terminology: use accurate terms for drug scheduling, legal status, and harm reduction (zarar azaltma, yasal sınıflandırma, dekriminalizasyon, tolerans).",
            "- [TONE & REGISTER] Altered states descriptions: translate descriptions of psychedelic trips, altered consciousness, physical sensations, bad trips, and withdrawals with raw, phenomenological accuracy.",
            "- [TR_ERROR] A common TR error here is converting precise chemical/slang names into generic drugs vocabulary (e.g., translating a specific compound as just 'uyuşturucu' or 'ilaç') — keep the specific compound name.",
        ],
    },
    "gonzo_subculture": {
        "name": "Gonzo / Katılımcı Belgesel",
        "rules": [
            "- [CONTEXT & TONE] Gonzo/Participatory investigative documentary (e.g., Louis Theroux, Vice). The host immerses themselves into bizarre, fringe, or extreme subcultures. Tone is curious, informal, sometimes ironic or slightly awkward.",
            "- [TONE & REGISTER] Host's voice-over and interactions should NOT sound like a formal, stiff nature documentary. Keep the host's personal, conversational, and slightly vulnerable or self-deprecating tone intact.",
            "- [DIALECT & CHARACTER] Interviewees belong to niche subcultures (survivalists, cults, UFO hunters, etc.). Preserve their authentic slang, eccentricities, and street language without sanitizing it into standard formal Turkish.",
            "- [FLOW & TIMING] The awkward pauses, hesitant questions, and conversational dead-ends are intentional comedic/dramatic devices. Keep them raw ('Hmm', 'Yani...', 'Şey...'). Do not smooth them over into perfect sentences.",
            "- [TR_ERROR] A common TR error is making the host sound like an authoritative expert. The host is an outsider asking naive/probing questions; keep that 'fish-out-of-water' dynamic.",
            "- [TERMINOLOGY] Subculture-specific jargon (prepper terms, cult terminology, scene slang) must be researched and kept consistent; a survivalists' \"intake\" or a groups' \"initiation\" should use the correct Turkish term, not flattened into generic vocabulary.",
            "- [TR_ERROR] Another common TR error is self-censoring: if the interviewee says something shocking, offensive, or tabloid, Turkish must keep it shocking — do not soften, normalize, or rephrase to protect the viewer."
        ],
    },
    "shockumentary": {
        "name": "Şok Belgeseli (Mondo)",
        "rules": [
            "- [CONTEXT & TONE] Shockumentary / Mondo film genre (e.g., Mondo Cane, Faces of Death). Exploitative, sensational, and often staged documentary focusing on taboo subjects, bizarre customs, and graphic violence.",
            "- [TONE & REGISTER] The narrator's tone must be pseudo-scientific, detached, overly dramatic, or cynically moralizing. Keep the sensationalist and slightly judgmental undertone.",
            "- [TERMINOLOGY] Use visceral, graphic terminology without softening or censoring it. If the source describes grotesque or morbid acts in clinical or theatrical terms, the Turkish must match this exact flavor.",
            "- [TR_ERROR] A common TR error is translating the narration as a respectful nature/anthropology documentary. It must retain its exploitative, voyeuristic, and sensational edge.",
            "- [FLOW & TIMING] Segments transition rapidly between shocking scenes, exotic rituals, and staged interviews. Maintain the disorienting and provocative pace — do not smooth scene breaks or fill gaps with neutral bridging narration.",
            "- [DIALECT & CHARACTER] Subjects and interviewees (often real people in exploitative situations, or actors playing along) must sound raw and unfiltered. Do not elevate casual, shocked, or crude remarks into formal or literary Turkish.",
            "- [TR_ERROR] A pervasive TR error is self-censorship: if the narrator describes or shows graphic, morbid, or taboo content, the Turkish must not soften, omit, or euphemize it; the subtitle viewer must receive the same visceral impact as the original audience."
        ],
    },
    "collector_reality": {
        "name": "Koleksiyoncu / Meraklı Eşya Reality",
        "rules": [
            "- [CONTEXT & TONE] Collector/dealer/appraisal reality: curiosity shops, pawn/antique dealers, pickers, and storage auctions (Oddities, Pawn Stars, American Pickers, Storage Wars, Antiques Roadshow). It blends casual banter, object-history exposition, and haggling.",
            "- [TONE & REGISTER] Dealer/host and shop-floor banter stays casual, quick, and playful — do NOT elevate everyday shop chatter into documentary formality.",
            "- [TERMINOLOGY] Object-history exposition (age, era, maker, provenance, function, materials) must be precise: dates, periods, prices, materials, and technical/anatomical/medical terms stay EXACT and use established Turkish forms.",
            "- [CONTEXT & TONE] Macabre/oddity content (taxidermy, medical antiques, death paraphernalia, bones, specimens) is treated with delighted curiosity and dark playfulness — NOT horror-documentary dread and NOT euphemism; keep the ghoulish charm.",
            "- [FLOW & TIMING] Haggling scenes keep their back-and-forth snap: offers, counteroffers, 'I can do X', 'meet me at Y' stay short and transactional, never padded into polite full sentences; prices and numbers stay EXACT.",
            "- [DIALECT & CHARACTER] Separate three voices — dealer/host banter, wide-eyed customer curiosity, and the cool precision of the visiting expert/appraiser; do not flatten them into one register.",
            "- [TONE & REGISTER] Talking-head confessional inserts (the dealer explaining their thinking to camera) sound spontaneous and personal, looser than the on-floor scene.",
            "- [FLOW & TIMING] Reveal/guessing beats ('Guess what this is', 'You'll never believe what this does') keep their teasing setup→payoff timing; the punch lands where the source lands.",
            "- [TERMINOLOGY] Keep shop, brand, maker, and object proper names as-is; add a brief Turkish gloss only when an obscure object type first appears — never a full parenthetical explanation.",
            "- [TR_ERROR] A common TR error here is over-formalizing playful shop banter into stiff documentary Turkish, OR sanitizing the morbid delight; the genre lives in the gap between casual banter and grim subject matter.",
            "- [TR_ERROR] Another common TR error is treating fast dealer patter as prose and letting lines run long — keep them tight, since this content runs high CPS and concision matters.",
        ],
    },
    "talk_show": {
        "name": "Talk Show / Gece Programı",
        "rules": [
            "- [CONTEXT & TONE] Late-night / daytime talk show: host monologue, desk bits, celebrity interviews, and audience interaction (Fallon, Kimmel, Graham Norton, and Turkish equivalents).",
            "- [FLOW & TIMING] Monologue jokes keep setup→punch timing; the punch word stays in the punch position, never followed by an explanatory clause.",
            "- [TONE & REGISTER] The host persona (warm, snarky, absurd, dry) stays consistent scene to scene; celebrity guests keep their own register and speech quirks.",
            "- [DIALECT & CHARACTER] Host vs guest voices stay distinct — the host steers and jokes, the guest tells anecdotes; do not merge them into one smooth conversation.",
            "- [FLOW & TIMING] Guest anecdotes keep their live, self-correcting, tangential flow ('şey', 'yani', 'neyse'); the looseness is the charm, do not tidy it.",
            "- [TERMINOLOGY] Celebrity names, show titles, brand names, and pop-culture references stay verbatim; never translate or localize them away.",
            "- [TONE & REGISTER] Audience-bait lines and bandleader/sidekick banter keep their performative, crowd-pleasing snap.",
            "- [FLOW & TIMING] Topical/political monologue jokes keep their bite; do not neutralize the satire into polite commentary.",
            "- [PRONOUNS] Host-to-guest address is usually friendly-informal ('sen'), but a first-time or very senior guest may warrant 'siz' — keep it consistent with the relationship shown.",
            "- [TR_ERROR] A common TR error here is flattening the host's comedic timing into news-anchor delivery, or translating monologue jokes literally so the punchline dies.",
        ],
    },
    "game_show": {
        "name": "Yarışma / Bilgi Yarışması",
        "rules": [
            "- [CONTEXT & TONE] Game/quiz show: host patter, quiz questions, contestant tension, and prize reveals (Jeopardy, Who Wants to Be a Millionaire, Wheel of Fortune, family game shows).",
            "- [TONE & REGISTER] Host register is upbeat, encouraging, and theatrical without being cheesy; keep the showman energy in natural Turkish.",
            "- [TERMINOLOGY] Quiz questions and answers are translated with EXACT factual accuracy — a mistranslated question breaks the game; numbers, names, and answer options stay precise.",
            "- [FLOW & TIMING] Suspense beats ('Is that your final answer?', 'For 1 million...') keep their tension and pause; do not rush or pad them. Prize amounts stay EXACT.",
            "- [TERMINOLOGY] Show catchphrases and format lines repeat with IDENTICAL Turkish wording every time ('Son kararınız bu mu?', 'Çarkı çevirin').",
            "- [DIALECT & CHARACTER] Host confidence vs contestant nervousness/excitement are different registers; keep the contestant's hesitation, hope, and relief audible.",
            "- [FLOW & TIMING] Rapid-fire / lightning rounds stay short and clipped; do not expand answers into full sentences.",
            "- [TONE & REGISTER] Win and loss moments keep their emotional swing — elation, disappointment — at real intensity, never flat.",
            "- [TR_ERROR] A common TR error here is mistranslating the actual quiz content for the sake of fluency; in this genre factual precision of questions and answers OUTWEIGHS smoothness.",
        ],
    },
    "nature_wildlife": {
        "name": "Doğa / Yaban Hayatı Belgeseli",
        "rules": [
            "- [CONTEXT & TONE] Nature/wildlife documentary (Attenborough-style, Planet Earth, National Geographic wildlife): the narrator's wonder is restrained and authoritative, never a children's storybook.",
            "- [TONE & REGISTER] Narration uses clean, measured, evocative standard Turkish; awe is conveyed through precision and rhythm, not exclamation marks.",
            "- [TERMINOLOGY] Species names, habitats, behaviors, and biological terms use established Turkish equivalents; keep scientific/Latin names as-is ('Panthera leo'; 'the savanna'→'savan').",
            "- [CONTEXT & TONE] Animal behavior is described factually — predation, mating, migration, survival — WITHOUT anthropomorphizing beyond what the source does; do not add human emotions the narration never states.",
            "- [FLOW & TIMING] Long observational sentences that build tension (the hunt, the storm, the birth) keep their pacing and suspense; do not chop them into flat short sentences.",
            "- [TERMINOLOGY] Preserve scientific hedging: 'may', 'is thought to', 'appears to', 'one of the few' must not become certainty.",
            "- [TONE & REGISTER] Conservation/threat segments carry quiet gravity; do not tip into either alarmist or preachy Turkish.",
            "- [DIALECT & CHARACTER] Field scientists/researchers in interview clips keep their own plainer register, clearly distinct from the polished narrator.",
            "- [TR_ERROR] A common TR error here is over-dramatizing into a storybook or an action-trailer, OR flattening the narrator's evocative restraint into dry encyclopedia Turkish.",
        ],
    },
    "religious_faith": {
        "name": "Dini İçerik / Vaaz",
        "rules": [
            "- [CONTEXT & TONE] Religious/faith content: sermons, homilies, televangelism, religious ceremony, scripture reading, and faith-based programming — the register is reverent and exhortative.",
            "- [TONE & REGISTER] The preaching/sermon voice keeps its rhetorical rise-and-fall, direct address, and moral exhortation; do not flatten it into neutral lecture Turkish.",
            "- [TERMINOLOGY] Scripture quotations use the ESTABLISHED Turkish translation of that tradition's text where one exists; never paraphrase holy text casually. Book/chapter/verse references stay exact.",
            "- [TERMINOLOGY] Theological and liturgical terms use each tradition's accepted Turkish vocabulary (e.g. Christian: kutsama, günah, kefaret, vaftiz, cemaat; Islamic: tevhid, takva, tövbe, ibadet, hutbe) — do not cross-contaminate traditions.",
            "- [TONE & REGISTER] Prayer, blessing, and invocation passages keep their solemn devotional register; never casualize them.",
            "- [DIALECT & CHARACTER] Distinguish the preacher/clergy voice from congregation responses and lay testimony; a personal faith testimony is warmer and plainer than the pulpit voice.",
            "- [PRONOUNS] Address to the congregation and to the divine follows the tradition's convention (collective 'siz'/'sizler', reverent forms for the sacred); keep it consistent.",
            "- [CONTEXT & TONE] Keep the source's stance as it presents itself: even when translating skeptically, the Turkish must read as the faith presents itself — do not insert mocking 'sözde' or editorial distance.",
            "- [TR_ERROR] A common TR error here is translating scripture and sermon in flat conversational Turkish, stripping the liturgical weight and rhetorical cadence that define the genre.",
        ],
    },
}

_BRACKET_TAG  = re.compile(r'\[.*?\]')
_SPEAKER_TAG  = re.compile(r'^\s*-?\s*\[[^\]]{1,40}\]\s*:\s*')  # [MAN]: , [SHERRY]:
_MUSIC_NOTE   = re.compile(r'[♪♫]')
_EMPTY_DASH   = re.compile(r'^-\s*$')
_HTML_TAG     = re.compile(r'</?(i|b|u|font)[^>]*>', re.IGNORECASE)

# Turkish-specific characters to detect translated SFX (vs untranslated English)
_TURKISH_CHARS = set("çÇğĞıİöÖşŞüÜ")

def _should_keep_bracket(content: str) -> bool:
    """A bracket tag like [KAHKAHA] is kept if it contains Turkish characters
    (i.e., it was translated). Pure-ASCII brackets like [LAUGHS] are dropped."""
    return any(ch in _TURKISH_CHARS for ch in content)

def _strip_sdh_line(line: str) -> str:
    return sdh_cleaner.strip_sdh_line(line)
    # Drop speaker prefixes first: "[SHERRY]: Hello" → "Hello"
    # Drop HTML-ish formatting tags (not semantically meaningful)
    # Drop musical notes / lyrics markers
    # Selectively strip bracketed content: keep Turkish SFX, drop English leftovers
    # Parentheses around any descriptor: (LAUGHS), (dramatic music), (quietly), etc.
    # Collapse any multiple spaces left behind

def clean_sdh(blocks, src_map=None, source_driven=False):
    return sdh_cleaner.clean_sdh_blocks(blocks, src_map=src_map, source_driven=source_driven)


# ── Satır kırma optimizasyonu ─────────────────────────────────────────────────
_LINE_THRESHOLD = 42   # Netflix/EBU standardı: satır başına max 42 karakter
_MAX_LINES      = 3    # Bir blokta en fazla bu kadar satır

_CONJ_RE = re.compile(
    r'\b(ve|ama|fakat|ya da|veya|ancak|çünkü|oysa|lakin|ki|ise|ile|üstelik)\b',
    re.IGNORECASE
)

def _find_best_split(text: str) -> int | None:
    """text içinde en iyi boşluk pozisyonunu döndürür (merkeze yakın, virgül/bağlaç bonusu).
    Bulunamazsa None."""
    if len(text) <= _LINE_THRESHOLD:
        return None
    mid        = len(text) // 2
    best_pos   = None
    best_score = float('inf')
    for i, ch in enumerate(text):
        if ch != ' ':
            continue
        # Çok kısa/uzun fragman oluşturma — ilk %15 ve son %15'i atla
        if i < len(text) * 0.15 or i > len(text) * 0.85:
            continue
        dist  = abs(i - mid)
        score = dist
        if i > 0 and text[i - 1] == ',':   score -= 12   # virgülden sonra
        if i > 0 and text[i - 1] == ';':   score -= 11   # noktalı virgül
        if text[max(0, i-2):i+3] in (' — ', ' - '):
            score -= 10                                    # em/en dash
        if _CONJ_RE.match(text[i + 1:]):   score -= 8    # bağlaçla başlıyor
        if score < best_score:
            best_score = score
            best_pos   = i
    return best_pos


def _break_to_line_budget(text: str, max_lines: int = _MAX_LINES, duration: float = None) -> str:
    """Bloğu en fazla max_lines satıra böler. Mevcut satırları korur ve kalan
    bütçe oldukça HER TUR en uzun satırı kırar — toplam satır sayısı ASLA
    max_lines'ı aşmaz (EBU). Zaten max_lines satıra ulaşmışsa dokunmaz
    (model'in kendi kırmasına saygı). duration verilirse, CPS sınırını aşan
    satırları da kırmaya çalışır."""
    if not text:
        return text
    cps_limit = CPS_WARN_LIMIT
    lines = text.split('\n')
    while len(lines) < max_lines:
        en_i = max(range(len(lines)), key=lambda i: len(lines[i]))
        needs_cps_break = False
        if duration and duration > 0 and len(lines) > 1:
            # En yüksek CPS'li satırı bul
            max_cps = 0
            max_cps_i = 0
            for i, l in enumerate(lines):
                lc = len(l.replace("\n", ""))
                if lc > 0 and duration > 0:
                    seg_cps = lc / duration
                    if seg_cps > max_cps:
                        max_cps = seg_cps
                        max_cps_i = i
            if max_cps > cps_limit and max_cps_i != en_i:
                en_i = max_cps_i
                needs_cps_break = True
        if not needs_cps_break and len(lines[en_i]) <= _LINE_THRESHOLD:
            break
        pos = _find_best_split(lines[en_i])
        if pos is None:
            if needs_cps_break:
                # CPS yüksek ama bölünecek yer yok — kalan son uygun yeri dene
                for attempt_pos in range(len(lines[en_i]) // 2, len(lines[en_i])):
                    if lines[en_i][attempt_pos] == ' ':
                        pos = attempt_pos
                        break
            if pos is None:
                break
        first  = lines[en_i][:pos].rstrip()
        second = lines[en_i][pos:].lstrip()
        if not first or not second:
            break
        lines = lines[:en_i] + [first, second] + lines[en_i + 1:]
    return '\n'.join(lines)


def apply_line_breaks(blocks: list) -> list:
    """Her bloğu en fazla _MAX_LINES satıra böler (EBU). Eğer blok CPS
    sınırını aşıyorsa daha kısa satırlara bölmeye çalışır."""
    result = []
    for idx, ts, text in blocks:
        dur = None
        try:
            dur = max(_ts_end_sec_gui(ts) - _ts_to_sec_gui(ts), 0.1)
        except Exception:
            pass
        result.append((idx, ts, _break_to_line_budget(text, _MAX_LINES, duration=dur)))
    return result


# ── Parçalı cue birleştirme (Amazon vb. kelime-kelime bölünmüş altyazılar) ─────
MERGE_MAX_CHARS  = 84    # birleştirilmiş cue'da görünür karakter üst sınırı (~2 satır)
MERGE_MAX_GAP_MS = 500   # iki cue arası boşluk <= bu(ms) ise birleştirilebilir

def _visible_len(text: str) -> int:
    """Etiket/parantez/newline hariç görünür karakter sayısı (okuma uzunluğu için)."""
    t = re.sub(r'</?[a-zA-Z][^>]*>', '', text)
    t = re.sub(r'\{[^}]+\}', '', t)
    return len(t.replace('\n', ' ').strip())

def _is_dialogue_cue(text: str) -> bool:
    """İki konuşmacılı blok mu? ('- ...\\n- ...' veya tire ile başlayan satır).
    Baştaki <i>/{\\an8} etiketlerini soyup bakar (etiket arkasındaki tire de sayılır)."""
    def _lead(l):
        return re.sub(r'^\s*(?:<[^>]+>|\{[^}]*\})+', '', l).lstrip()
    lines = [l for l in text.split('\n') if l.strip()]
    if not lines:
        return False
    dash = sum(1 for l in lines if _lead(l).startswith('-'))
    return dash >= 2 or _lead(lines[0]).startswith('-')

_SDH_ONLY_RE = re.compile(r'^(\[[^\]]*\]|\([^)]*\)|♪[^♪]*♪?|[_♪])$')
def _is_sdh_only(text: str) -> bool:
    """Sadece ses betimlemesi/efekt mi? ([Laughing], (sighs), ♪, _ gibi)."""
    return sdh_cleaner.is_sdh_only(text)

def merge_fragmented_cues(blocks: list, max_chars: int = MERGE_MAX_CHARS,
                          max_gap_ms: int = MERGE_MAX_GAP_MS,
                          only_continuation: bool = True) -> list:
    """Art arda gelen, aynı cümleye ait kısa cue'ları tek bloğa birleştirir
    (Amazon WEB-DL gibi kelime-kelime bölünmüş kaynaklar için).

    Birleşik cue ilk cue'nun BAŞLANGICI → son cue'nun BİTİŞİ aralığını kapsar:
    senkron KORUNUR, metin kelime kelime yanıp sönmek yerine tek seferde görünür.
    Birleşme koşulları (hepsi): boşluk 0..max_gap_ms, birleşik görünür uzunluk
    <= max_chars, önceki metin cümle bitirmiyor (only_continuation), iki taraf da
    diyalog/SDH değil. Birleştirilenler ≤2 satıra sarılır; bloklar yeniden numaralanır."""
    if not blocks or len(blocks) < 2:
        return list(blocks)
    groups = []
    for idx, ts, text in blocks:
        parts = str(ts).split('-->')
        start_str = parts[0].strip()
        end_str   = parts[1].strip() if len(parts) > 1 else ""
        try:
            cs, ce = _ts_to_sec_gui(ts), _ts_end_sec_gui(ts)
        except Exception:
            cs = ce = None
        if groups and cs is not None and groups[-1]["end_sec"] is not None:
            g = groups[-1]
            gap_ms   = (cs - g["end_sec"]) * 1000
            combined = _visible_len(g["text"]) + 1 + _visible_len(text)
            # Birleşik blok okunabilir hızda mı? (toplam görünür karakter / toplam süre)
            span_sec = (ce - g["start_sec"]) if (ce is not None and g["start_sec"] is not None) else 0
            cps_ok   = span_sec <= 0 or (combined / span_sec) <= CPS_WARN_LIMIT
            if (0 <= gap_ms <= max_gap_ms
                    and combined <= max_chars
                    and cps_ok
                    and (not only_continuation or not _ends_sentence_gui(_clean_src(g["text"])))
                    and not _is_dialogue_cue(g["text"]) and not _is_dialogue_cue(text)
                    and not _is_sdh_only(g["text"]) and not _is_sdh_only(text)):
                # İkinci parçanın baştaki konum/override etiketini ({\an8} vb.) at —
                # grup konumunu ilk cue belirler, ortada tekrarı bozuk çıktı yapar
                _piece = re.sub(r'^\s*(?:\{[^}]*\})+', '', text)
                joined = g["text"].rstrip() + ' ' + _piece.lstrip()
                joined = re.sub(r'\s*\n\s*', ' ', joined)                       # iç newline'ları boşluğa
                joined = re.sub(r'</(i|b|u|font)>\s*<\1\b[^>]*>', ' ', joined)  # </i> <i> vb. sınırı topla
                g["text"], g["end"], g["end_sec"] = joined.strip(), end_str, ce
                g["count"] += 1
                continue
        groups.append({"start": start_str, "end": end_str, "start_sec": cs,
                       "end_sec": ce, "text": text, "count": 1, "ts": ts})
    out = []
    for i, g in enumerate(groups, 1):
        txt = _break_to_line_budget(g["text"], 2) if g["count"] > 1 else g["text"]
        ts  = f"{g['start']} --> {g['end']}" if g["end"] else g["ts"]
        out.append((str(i), ts, txt))
    return out


# ── AI destekli akıllı segmentasyon ───────────────────────────────────────────
# Mantık: AI YALNIZCA hangi ardışık cue'ların tek görüntü birimi olduğunu ve satır
# kırmayı önerir; ZAMANLAMA ve OKUMA HIZI (CPS) deterministik (matematikle) zorlanır,
# birleşik metin orijinal parçalardan kurulur. AI önerir, çekirdek uygular.

def _norm_for_compare(text: str) -> str:
    """Sadakat karşılaştırması için metni indirger: SADECE ardışık boşlukları tek boşluğa
    indirger ve uçları kırpar. Kelimeler, noktalama, büyük/küçük harf, etiketler (<i>,
    {\\anN}) ve parantez içerikleri AYNEN korunur — AI bunlardan herhangi birini
    değiştirirse (kelime yapıştırma/bölme, etiket ekleme/çıkarma/değiştirme, konum
    etiketi, harf büyüklüğü) 'sadık değil' sayılır ve deterministik birleştirmeye düşülür.
    Yalnızca satır kırma / boşluk sayısı farkı kabul edilir (AI'nin tek meşru katkısı)."""
    return re.sub(r'\s+', ' ', text or '').strip()


def _sanitize_ai_text(text: str) -> str:
    """Kabul edilen AI metnini güvenli karakter kümesine indirger: satır sonlarını \\n'e
    çevirir, \\n DIŞINDAKİ tüm whitespace'i (TAB, NBSP \\xa0, ideografik boşluk \\u3000,
    FF/VT/NEL, CR) tek ASCII boşluğa indirir, sıfır-genişlik karakterleri atar, satır
    uçlarını kırpar. Böylece diske yazılan cue yalnızca orijinal kelime/etiket + ASCII
    boşluk + \\n içerir — AI 'görünmez' bir whitespace karakteriyle (ör. \\r) sadakat
    kapısını geçip diskte yapıyı bozamaz (yeniden okununca \\r → \\n olurdu)."""
    s = (text or '').replace('\r\n', '\n').replace('\r', '\n')
    s = re.sub('[​‌‍⁠﻿]', '', s)   # sıfır-genişlik karakterler
    s = re.sub(r'[^\S\n]+', ' ', s)                          # \n hariç tüm whitespace → ' '
    return '\n'.join(ln.strip() for ln in s.split('\n') if ln.strip())


def _join_cue_texts(texts: list) -> str:
    """Birden çok cue metnini tek parçaya birleştirir (merge_fragmented_cues ile aynı
    kurallar): sonraki parçaların baştaki konum override'ını ({\\an8} vb.) atar, iç
    newline'ları boşluğa çevirir, etiket sınırlarını (</i> <i>) toplar."""
    joined = ""
    for i, t in enumerate(texts):
        t = t or ""
        if i == 0:
            joined = t.rstrip()
        else:
            piece = re.sub(r'^\s*(?:\{[^}]*\})+', '', t)
            joined = joined.rstrip() + ' ' + piece.lstrip()
    joined = re.sub(r'\s*\n\s*', ' ', joined)
    joined = re.sub(r'</(i|b|u|font)>\s*<\1\b[^>]*>', ' ', joined)
    return joined.strip()


def _segmentation_candidates(blocks: list, max_gap_ms: int = MERGE_MAX_GAP_MS,
                             max_window: int = 6) -> list:
    """AI segmentasyonu için aday pencereleri bulur: ardışık, küçük boşluklu (0..max_gap_ms),
    diyalog/SDH olmayan ve en az bir 'devam' (önceki cue cümle bitmiyor) sınırı içeren cue
    dizileri. Tam cümle/bağımsız uzun cue'lar pencereye girmez (boşuna token harcanmaz).
    Dönüş: [(start_pos, end_pos), ...] kapsayıcı pozisyon aralıkları (örtüşmez, sıralı)."""
    n = len(blocks)
    windows = []
    i = 0
    while i < n:
        run = [i]
        j = i
        while j + 1 < n and len(run) < max_window:
            _, ts, text = blocks[j]
            _, nts, ntext = blocks[j + 1]
            if (_is_dialogue_cue(text) or _is_sdh_only(text)
                    or _is_dialogue_cue(ntext) or _is_sdh_only(ntext)):
                break
            if _ends_sentence_gui(_clean_src(text)):
                break   # mevcut cue cümle bitiriyor → sınır 'devam' değil, pencereyi burada kes
            try:
                gap_ms = (_ts_to_sec_gui(nts) - _ts_end_sec_gui(ts)) * 1000
            except Exception:
                break
            if not (0 <= gap_ms <= max_gap_ms):
                break
            run.append(j + 1)
            j += 1
        if len(run) >= 2:
            has_cont = any(
                not _ends_sentence_gui(_clean_src(blocks[run[k]][2]))
                for k in range(len(run) - 1))
            if has_cont:
                windows.append((run[0], run[-1]))
                i = run[-1] + 1
                continue
        i += 1
    return windows


def _enforce_segment_groups(window_blocks: list, groups: list,
                            max_chars: int = MERGE_MAX_CHARS,
                            cps_limit: int = None):
    """AI'nin bir penceredeki gruplama önerisini deterministik kurallarla uygular.
    AI yalnızca GRUPLAMA + satır kırma önerir; ZAMANLAMA (ilk başı→son sonu) ve CPS
    matematikle zorlanır. Metin orijinal parçalardan kurulur; AI metni yalnızca SADIK
    ise (kelime/noktalama birebir) onun satır kırması korunur, aksi halde deterministik.
    Dönüş: [(ts, text), ...]  ya da geçersiz/okunamaz ise None (çağıran deterministik
    birleştirmeye düşer)."""
    if cps_limit is None:
        cps_limit = CPS_WARN_LIMIT
    if not groups:
        return None
    win_ids = [str(b[0]) for b in window_blocks]
    # Tekrarlı index'ler (bozuk kaynak SRT) by_id'de çakışıp cue düşürür/çoğaltır —
    # benzersiz değilse hiç güvenme, deterministik birleştirmeye düş.
    if len(set(win_ids)) != len(win_ids):
        return None
    by_id = {str(b[0]): b for b in window_blocks}
    flat = []
    for g in groups:
        if not isinstance(g, dict):
            return None
        ids = [str(x) for x in (g.get("ids") or [])]
        if not ids:
            return None
        flat.extend(ids)
    # AI id'leri pencere id'lerinin SIRALI, BİTİŞİK, TAM bölüntüsü olmalı
    if flat != win_ids:
        return None
    out = []
    for g in groups:
        ids = [str(x) for x in g["ids"]]
        members = [by_id[i] for i in ids]
        # AI metnini güvenli karakter kümesine indir (CR/NBSP/sıfır-genişlik smuggle'ı kapat)
        ai_text = _sanitize_ai_text(g.get("text") or "")
        if len(members) == 1:
            base_text = members[0][2]
            if ai_text and _norm_for_compare(ai_text) == _norm_for_compare(base_text):
                text = (ai_text if ai_text.count('\n') + 1 <= 2
                        else _break_to_line_budget(re.sub(r'\s*\n\s*', ' ', ai_text), 2))
            else:
                text = base_text
        else:
            # AI tamamlanmış bir cümleyi sonrakine yapıştırmasın: son üye dışında hiçbir
            # üye cümle bitirmemeli (deterministik temel de pencere içi böyle davranır)
            if any(_ends_sentence_gui(_clean_src(m[2])) for m in members[:-1]):
                return None
            det_text = _join_cue_texts([m[2] for m in members])
            if ai_text and _norm_for_compare(ai_text) == _norm_for_compare(det_text):
                text = (ai_text if ai_text.count('\n') + 1 <= 2
                        else _break_to_line_budget(re.sub(r'\s*\n\s*', ' ', ai_text), 2))
            else:
                text = _break_to_line_budget(det_text, 2)
        # İlk üyenin konum override'ını ({\anN}) koru (AI düşürdüyse geri ekle)
        lead = re.match(r'^\s*(?:\{[^}]*\})+', members[0][2] or '')
        if lead and not text.lstrip().startswith('{'):
            text = lead.group(0).strip() + text
        # Zamanlama: ilk üyenin başı → son üyenin sonu (deterministik, senkron korunur)
        start = str(members[0][1]).split('-->')[0].strip()
        end_parts = str(members[-1][1]).split('-->')
        end = end_parts[1].strip() if len(end_parts) > 1 else ""
        ts = f"{start} --> {end}" if end else members[0][1]
        # Okuma hızı + genişlik koruması SADECE bu pass'in ÜRETTİĞİ birleşmelere uygulanır
        # (tek-üye grup dokunulmamış kaynak cue'dur; kendi CPS'i yüzünden pencere reddedilmez).
        if len(members) > 1:
            try:
                span = _ts_end_sec_gui(ts) - _ts_to_sec_gui(ts)
            except Exception:
                return None   # zaman çözülemiyorsa güvenli tarafa düş (deterministik birleştir)
            if span > 0 and (_visible_len(text) / span) > cps_limit:
                return None
            if _visible_len(text) > max_chars:   # deterministik temelle aynı sert tavan
                return None
        out.append((ts, text))
    return out


def ai_resegment_cues(blocks: list, api_key: str, url: str = "https://api.openai.com/v1",
                      model: str = "gpt-5.4-mini", log_fn=None,
                      max_chars: int = MERGE_MAX_CHARS, max_gap_ms: int = MERGE_MAX_GAP_MS,
                      cps_limit: int = None, max_window: int = 6,
                      token_callback=None) -> list:
    """AI destekli akıllı cue segmentasyonu. Yalnızca aday pencereler (kelime kelime
    bölünmüş olabilecek ardışık diziler) modele gönderilir; model gruplamayı + satır
    kırmayı önerir, zamanlama/CPS deterministik zorlanır, metin orijinalden kurulur.
    Aday yoksa veya hata olursa hızlı merge_fragmented_cues'e düşer (sync hep korunur)."""
    if cps_limit is None:
        cps_limit = CPS_WARN_LIMIT
    if not blocks or len(blocks) < 2:
        return list(blocks)
    try:
        windows = _segmentation_candidates(blocks, max_gap_ms, max_window)
    except Exception:
        windows = []
    if not windows:
        return merge_fragmented_cues(blocks, max_chars=max_chars, max_gap_ms=max_gap_ms)
    try:
        import hybrid_translate as ht
        client = OpenAI(api_key=api_key, base_url=url)
    except Exception as e:
        if log_fn:
            log_fn(f"AI segmentasyon bağlantı hatası, hızlı birleştirmeye düşülüyor: {e}", "warn")
        return merge_fragmented_cues(blocks, max_chars=max_chars, max_gap_ms=max_gap_ms)

    resolved = {}        # (start_pos, end_pos) -> [(ts, text), ...]
    BATCH = 20
    n_ai = n_fallback = 0
    for wi in range(0, len(windows), BATCH):
        batch = windows[wi:wi + BATCH]
        payload = []
        for w, (s, e) in enumerate(batch):
            cues = [{"id": str(blocks[p][0]), "text": blocks[p][2]} for p in range(s, e + 1)]
            payload.append({"window": w, "cues": cues})
        prompt = (
            "Aşağıda, kelime kelime bölünmüş OLABİLECEK ardışık altyazı cue grupları (pencereler) var.\n"
            "Her pencere için, AYNI cümleye/görüntü birimine ait ardışık cue'ları GRUPLA.\n"
            "Kurallar:\n"
            "- SADECE grupla; kelimeleri DEĞİŞTİRME, ekleme/çıkarma/çeviri YAPMA.\n"
            "- Bir grubun 'text'i, gruptaki cue metinlerinin BİREBİR birleşimidir; yalnızca\n"
            "  en fazla 2 satıra (satır başına ~42 karakter), öğe/yan cümle sınırından dengeli böl (\\n).\n"
            "- Anlamca tek cümleyi birleştir; ayrı cümleleri/ayrı konuşmacıları AYRI grupla.\n"
            "- Her pencerenin TÜM id'leri, gruplarda SIRASIYLA ve eksiksiz yer almalı.\n\n"
            f"Pencereler:\n{json.dumps(payload, ensure_ascii=False)}\n\n"
            'Yalnızca şu JSON: {"results":[{"window":0,"groups":[{"ids":["3","4"],"text":"...\\n..."}]}]}'
        )
        n_cues = sum(len(item["cues"]) for item in payload)
        try:
            resp = ht._safe_chat_create(
                client, model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=n_cues * 60 + 400,
                temperature=0.2,
            )
            if token_callback and getattr(resp, "usage", None):
                tot, cached = _get_usage_details(resp.usage)
                try:
                    token_callback(tot, cached=cached)
                except TypeError:
                    token_callback(tot)
            content = (resp.choices[0].message.content or "").strip() if resp.choices else ""
            data = ht._extract_json_object(content) if content else {}
        except Exception as e:
            if log_fn:
                log_fn(f"AI segmentasyon isteği hatası (pencere {wi}+), yedek: {e}", "warn")
            data = {}
        results = (data.get("results") or []) if isinstance(data, dict) else []
        res_by_win = {}
        for r in results:
            if isinstance(r, dict) and isinstance(r.get("window"), int):
                res_by_win[r["window"]] = r.get("groups") or []
        for w, (s, e) in enumerate(batch):
            window_blocks = [blocks[p] for p in range(s, e + 1)]
            applied = None
            groups = res_by_win.get(w)
            if groups:
                try:
                    applied = _enforce_segment_groups(window_blocks, groups, max_chars, cps_limit)
                except Exception:
                    applied = None
            if applied is not None:
                resolved[(s, e)] = applied
                n_ai += 1
            else:
                det = merge_fragmented_cues(window_blocks, max_chars=max_chars, max_gap_ms=max_gap_ms)
                resolved[(s, e)] = [(ts, txt) for (_idx, ts, txt) in det]
                n_fallback += 1

    win_by_start = {s: (s, e) for (s, e) in windows}
    out = []
    p, n = 0, len(blocks)
    while p < n:
        if p in win_by_start:
            s, e = win_by_start[p]
            out.extend(resolved[(s, e)])
            p = e + 1
        else:
            out.append((blocks[p][1], blocks[p][2]))
            p += 1
    final = [(str(i), ts, txt) for i, (ts, txt) in enumerate(out, 1)]
    if log_fn:
        log_fn(f"AI segmentasyon: {len(blocks)} → {len(final)} blok "
               f"({len(windows)} pencere; {n_ai} AI, {n_fallback} yedek)", "ok")
    return final


# ── SRT yardımcıları ──────────────────────────────────────────────────────────
def parse_srt(filepath):
    parsed = []
    content = read_subtitle_text(filepath).strip()
    for block in re.split(r"\n[ \t]*\n+", content):
        lines = block.strip().splitlines()
        # Numarasız SRT (ilk satır doğrudan zaman damgası) → sıralı index uydur
        if len(lines) >= 2 and "-->" in lines[0]:
            parsed.append((None, lines[0].strip(), "\n".join(lines[1:]).strip()))
            continue
        if len(lines) < 3:
            continue
        parsed.append((lines[0].strip(), lines[1].strip(), "\n".join(lines[2:]).strip()))
    raw_ids = [idx for idx, _ts, _text in parsed]
    valid_ids = bool(raw_ids) and all(idx is not None and re.fullmatch(r"\d+", idx)
                                      for idx in raw_ids)
    if valid_ids:
        numeric_ids = [int(idx) for idx in raw_ids]
        valid_ids = all(a < b for a, b in zip(numeric_ids, numeric_ids[1:]))
    if valid_ids:
        return [(idx, ts, text) for idx, ts, text in parsed]
    return [(str(i), ts, text) for i, (_idx, ts, text) in enumerate(parsed, 1)]

def parse_subtitle(filepath: str) -> list:
    """Uzantıya göre uygun parser'ı seçer: .srt, .vtt, .ass, .ssa"""
    ext = Path(filepath).suffix.lower()
    if ext == '.vtt':
        return parse_vtt(filepath)
    if ext in ('.ass', '.ssa'):
        return parse_ass(filepath)
    result = parse_srt(filepath)
    # .srt uzantili ama icerigi VTT olan dosyalar: SRT parse bos donerse VTT dene
    if not result:
        result = list(parse_vtt(filepath))
    return result

_SPEAKER_MAP = {
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

_SPEAKER_LABEL_ALTS = (
    "News Anchor|Film Crew|Voice-over|Voiceover|Narrator|Man|Woman|Male|Female|"
    "Boy|Girl|Child|Kid|Announcer|Speaker|Voice|Interviewer|Host|Reporter|"
    "Crowd|Audience|Anchor|Director|Producer|Crew|Police|"
    "Doctor|Nurse|Officer|Teacher|Judge|King|Queen|Soldier|Captain|Priest|Baby|Patient"
)

def _tr_upper(s: str) -> str:
    res = []
    for char in s:
        if char == 'i':
            res.append('İ')
        elif char == 'ı':
            res.append('I')
        elif char == 'ş':
            res.append('Ş')
        elif char == 'ç':
            res.append('Ç')
        elif char == 'ğ':
            res.append('Ğ')
        elif char == 'ö':
            res.append('Ö')
        elif char == 'ü':
            res.append('Ü')
        else:
            res.append(char.upper())
    return "".join(res)

def _translate_speaker_labels(text: str) -> str:
    if not text:
        return text
    
    # Pattern 1: With colon, optional VO/OS (e.g. "Narrator: " or "MAN (V.O.): ")
    pat1 = re.compile(
        rf'^(\s*-?\s*\[?\(?)({_SPEAKER_LABEL_ALTS})(?:\s+\(?(V\.?O\.?|O\.?S\.?|VO|OS)\)?)?(\]?\)?\s*:\s*)',
        re.IGNORECASE
    )
    # Pattern 2: Without colon, but in brackets/parentheses (e.g. "[NARRATOR] " or "(MAN) ")
    pat2 = re.compile(
        rf'^(\s*-?\s*[\[\(])({_SPEAKER_LABEL_ALTS})(?:\s+\(?(V\.?O\.?|O\.?S\.?|VO|OS)\)?)?([\]\)]\s*)',
        re.IGNORECASE
    )

    lines = text.split('\n')
    new_lines = []
    for line in lines:
        match = pat1.match(line) or pat2.match(line)
        if match:
            prefix = match.group(1)
            name = match.group(2)
            vo = match.group(3)
            suffix = match.group(4)
            
            # Translate name
            l_name = name.lower()
            tr_name = _SPEAKER_MAP.get(l_name, name)
            if name.isupper():
                tr_name = _tr_upper(tr_name)
            
            # Translate VO/OS suffix
            tr_vo = ""
            if vo:
                is_upper = vo.isupper()
                has_dots = "." in vo
                if has_dots:
                    val = "D.S." if is_upper else "d.s."
                else:
                    val = "DS" if is_upper else "ds"
                
                matched_all = match.group(0)
                vo_idx = matched_all.lower().find(vo.lower())
                has_paren_open = vo_idx > 0 and matched_all[vo_idx - 1] == '('
                if has_paren_open:
                    tr_vo = " (" + val + ")"
                else:
                    tr_vo = " " + val
            
            rest = line[match.end():]
            new_line = f"{prefix}{tr_name}{tr_vo}{suffix}{rest}"
            new_lines.append(new_line)
        else:
            new_lines.append(line)
            
    return "\n".join(new_lines)

def write_srt(filepath, blocks):
    # Çıktı HER ZAMAN SRT biçimindedir → uzantıyı .srt yap (.vtt/.ass girdiler için de),
    # yoksa SRT içeriği .vtt/.ass uzantısıyla yazılıp oynatıcıda açılmaz.
    out = Path(filepath).with_suffix(".srt")
    out.parent.mkdir(parents=True, exist_ok=True)
    # Atomik yazım: önce .tmp'ye yaz, çökme durumunda yarım SRT kalmasın
    _tmp = out.with_suffix(".srt.tmp")
    with open(_tmp, "w", encoding="utf-8") as f:
        for idx, ts, text in blocks:
            # Metindeki çift+ newline'lar SRT blok ayracını (\n\n) taklit edip yeniden
            # okumada satır düşürür/bozar — tek newline'a indir.
            try:
                import hybrid_translate as ht
                text = ht.normalize_latin_homoglyphs(str(text))
                text = ht._apply_local_fixes(str(text))[0]
            except Exception:
                text = str(text)
            text = unicodedata.normalize("NFC", str(text).strip()).replace("\t", " ")
            text = re.sub(r'\n{2,}', '\n', text)
            text = sdh_cleaner.normalize_sdh_descriptors(text)
            text = sdh_cleaner.normalize_speaker_labels(text)
            text = sdh_cleaner.normalize_turkish_artifacts(text)
            text = _translate_speaker_labels(text)
            if not text.strip():
                text = "[ÇEVİRİ EKSİK]"
            f.write(f"{idx}\n{ts}\n{text}\n\n")
    _tmp.replace(out)


def _paths_equal(a, b) -> bool:
    """İki klasör yolu aynı yeri mi gösteriyor? (Windows: büyük/küçük harf duyarsız)."""
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return False
    try:
        return Path(a).resolve() == Path(b).resolve()
    except Exception:
        return a.rstrip("\\/").lower() == b.rstrip("\\/").lower()


def _resolve_output_path(input_dir: str, output_dir: str, filepath: str,
                          same_folder: bool = False) -> Path:
    """Çıktı .srt yolunu çözer (bkz. plans/output-folder-rules-brief.md).

    same_folder=True — Giriş/Çıkış klasörü alanları YOK SAYILIR: çıktı, dosyanın
        KENDİ geldiği klasöre kaynak adıyla yazılır. Farklı klasörlerden eklenen
        dosyalar (tek seferde çevrilse bile) kendi klasörüne geri döner. Kaynak
        zaten .srt ise hesaplanan yol kaynakla BİREBİR çakışır — orijinali
        silmemek için bu tek durumda <isim>.tr.srt kullanılır.
    Kural 1 — çıktı klasörü girdiyle aynı (veya boş):
        <girdi>/ÇIKTI/<göreli-yol>.srt   (göreli substructure korunur, kaynağın yanına yazılmaz)
    Kural 2 — çıktı ayrı bir klasör:
        <çıktı>/<dosya-adı-uzantısız>/<dosya-adı>.srt   (her dosya kendi klasöründe)
        Girdi kökü dışından eklenen dosyalarda kaynak klasör adı + kararlı kısa
        yol özeti kullanılır; aynı adlı farklı klasörler birbirine çarpmaz.

    Yol her zaman .srt uzantılıdır (çıktı daima SRT)."""
    src = Path(filepath)
    if same_folder:
        candidate = src.with_suffix(".srt")
        if candidate.name.lower() == src.name.lower():
            candidate = src.with_name(f"{src.stem}.tr.srt")
        return candidate
    in_dir = (input_dir or "").strip()
    out_dir = (output_dir or "").strip()
    if not out_dir or _paths_equal(in_dir, out_dir):
        base = Path(in_dir) if in_dir else src.parent
        try:
            rel = src.relative_to(base)
        except Exception:
            rel = Path(src.name)
        return (base / "ÇIKTI" / rel).with_suffix(".srt")
    if in_dir:
        try:
            rel = src.relative_to(Path(in_dir))
            if len(rel.parts) > 1:
                return (Path(out_dir) / rel.parent / src.stem / src.name).with_suffix(".srt")
        except Exception:
            pass
    if src.parent and src.parent.name and not _paths_equal(str(src.parent), out_dir) and not (in_dir and _paths_equal(str(src.parent), in_dir)):
        parent_key = os.path.normcase(os.path.abspath(str(src.parent)))
        digest = hashlib.sha1(parent_key.encode("utf-8", errors="surrogatepass")).hexdigest()[:8]
        bucket = f"{src.parent.name}-{digest}"
        return (Path(out_dir) / bucket / src.stem / src.name).with_suffix(".srt")
    return (Path(out_dir) / src.stem / src.name).with_suffix(".srt")


def _resolve_report_dir(input_dir: str, output_dir: str) -> Path:
    """ceviri_raporu.txt'nin gideceği 'efektif çıktı tabanı'.

    Kural 1 (çıktı==girdi veya boş): <girdi>/ÇIKTI  (çıktı .srt'lerin yanı, kaynağı kirletmez)
    Kural 2 (ayrı çıktı klasörü):    <çıktı>        (dosya-adı alt-klasörlerinin üstünde, kök)."""
    in_dir = (input_dir or "").strip()
    out_dir = (output_dir or "").strip()
    if not out_dir or _paths_equal(in_dir, out_dir):
        base = Path(in_dir) if in_dir else Path(".")
        return base / "ÇIKTI"
    return Path(out_dir)


def estimate_tokens(srt_files, chunk_size=None):
    """Token tahmini. chunk_size belirtilmezse mevcut mod CHUNK değeri kullanılır."""
    if chunk_size is None:
        chunk_size = CHUNK
    total_chars, total_blocks = 0, 0
    for fp in srt_files:
        blocks = list(parse_subtitle(fp))
        total_blocks += len(blocks)
        for _, _, text in blocks:
            total_chars += len(text)
    n_req       = math.ceil(total_blocks / max(chunk_size, 1))
    # Sistem prompt'u HER isteğe ekleniyor; sabit 180 gerçekçi değildi (asıl prompt
    # ~1500-1800 token). Prompt'u bir kez ölç (char/3 ~ token), önemli ölçüde daha doğru.
    try:
        _sys_chars   = len(_build_sync_system_prompt("English", "Turkish", None, "Orta"))
        _sys_per_req = max(180, _sys_chars // 3)
    except Exception:
        _sys_per_req = 1500
    sys_tokens  = n_req * _sys_per_req
    # tiktoken kuruluysa daha iyi oran (chars/3), yoksa chars/4 tahmini.
    # Not: tam tokenizasyon çok yavaş; sadece kurulu olup olmadığına göre oran seçiyoruz.
    try:
        import tiktoken  # noqa: F401
        content_tok = total_chars // 3
    except ImportError:
        content_tok = total_chars // 4
    return sys_tokens + content_tok * 2, total_blocks

def _build_sync_system_prompt(src: str, tgt: str, schema: dict = None, profanity: str = "Orta") -> str:
    schema_block = ""
    if schema and schema.get("rules"):
        schema_block = (
            f"\n## CONTENT TYPE: {schema['name'].upper()}\n"
            + "\n".join(schema["rules"]) + "\n"
        )

    profanity_rule = "\n".join(PROFANITY_RULES.get(profanity, PROFANITY_RULES["Orta"]))

    # Colloquial markers: skip for documentary/narration/news content
    # (hybrid yolu bunu context.tone register'ından çıkarır — sync'te şema adıyla paritede tut)
    schema_name = (schema or {}).get("name", "").lower()
    is_doc = any(k in schema_name for k in
                 ("belgesel", "documentary", "haber", "news", "anlatı", "sunum", "narration"))
    colloquial_block = "" if is_doc else (
        "\nNatural Turkish speech markers — use only where they genuinely fit:\n"
        '- Emphasis/filler: "yani", "işte", "zaten", "ya"\n'
        '- Surprise/reaction: "aa", "of", "vay be"\n'
        '- Casual assent: "tamam", "anladım", "olur"\n'
        "- Never force into every line — only when a native speaker would say it there\n"
        '- Subtractive too: English discourse markers map selectively — "well"→şey/yani or nothing, '
        '"you know"→usually nothing or işte, "I mean"→yani, "like"→usually nothing. The yes/no question '
        'particle "mi/mı/mu/mü" is REQUIRED for evet/hayır questions but must NOT be added to wh-questions '
        "(kim/ne/nerede/niye/nasıl already mark them).\n"
    )

    return (
        f"You are a professional subtitle translator from {src} to {tgt}.\n"
        f"CRITICAL: Every translated line MUST be in {tgt} ONLY. "
        f"Never output German, French, Spanish, Dutch, or any language other than {tgt}. "
        f"TURKIC GUARD: when {tgt} is Turkish, write ONLY Türkiye (Anatolian) Turkish — NEVER drift into "
        f"sibling Turkic languages (Uzbek, Azerbaijani, Turkmen, Tatar, Kazakh). Avoid leaks like "
        f"'qora'→'kara/siyah', 'yuqori'→'yüksek', 'pichoq'→'bıçak', 'qilich'→'kılıç', 'jang'→'savaş', "
        f"'qon'→'kan'. Words containing q/w/x are almost always foreign — they are a strong signal of Turkic "
        f"drift, though established loanwords like 'web', 'wifi', 'fax' and proper nouns ('Warp', 'xenos', 'vox') may use them. "
        f"Never output Turkmen-like forms such as 'bäýram', 'holidaý', 'oturylyşyğı', 'ortadagy bezeg', "
        f"'geňlikleri', 'taksidermiya', or 'bäseke'; use real Turkish: 'yılbaşı/tatil partisi', "
        f"'masa süsü', 'taksidermi', 'yarışma parçası'. "
        f"If the source contains foreign words, still translate everything into {tgt}.\n"
        f"NEVER add parenthetical translator notes or glosses '(...)' that do not exist in the source "
        f"line. Translate the term; do not explain it.\n"
        f"SCRIPT GUARD: Turkish uses the Latin alphabet only. "
        f"NEVER output Arabic (ع،ح), Tamil (கோயில்), Devanagari (देव), Cyrillic (текст), "
        f"CJK (寺), or ANY non-Latin script characters. "
        f"If you see 'temple', 'mosque', 'shrine', translate to Turkish words: "
        f"tapınak, cami, türbe — NEVER use the word's form in another language's script.\n"
        + schema_block
        + "Rules:\n"
        f"- Natural, fluent {tgt} — never word-for-word literal\n"
        "- MEANING-FIRST / sense-for-sense: infer what the speaker or narrator means ONLY from the visible "
        "source words and surrounding context, then say that naturally in Turkish. Preserve the speech act, "
        "implication, subtext, emotion, and cause-effect; change word order and wording when Turkish needs it, "
        "but never add unstated ideas. Duration/CPS beats source length: keep Turkish concise for the cue "
        "duration; aim for <=21 CPS and stay <=24 CPS when possible. Never translate by matching source words "
        "one by one.\n"
        "- Preserve polarity exactly: not/never/no/n't must stay negative in Turkish; never flip a denial into "
        "an affirmation or an affirmation into a denial.\n"
        "- Before translating pronouns and deictics (this/that/it/he/she/him/her/there), resolve what they refer "
        "to. If the 'scene' key's 'referents' field names it explicitly, use that; otherwise resolve from "
        "ctx/next_ctx; if still unclear, keep the Turkish wording neutral rather than inventing a referent.\n"
        "- Match tone: casual stays casual, formal stays formal, humor stays humorous\n"
        "- Keep names, brands, proper nouns unchanged\n"
        "- Keep the same number of subtitle lines inside each cue; preserve the existing \\n structure unless a "
        "minimal rebalance is needed for readable Turkish.\n"
        "- Preserve ALL HTML-like inline tags exactly as-is: <i>...</i>, <b>...</b>, <u>...</u>, <font ...>\n"
        "- Translate ALL [SFX] / [ACTION] tags to natural Turkish equivalents "
        "(e.g. [LAUGHS]→[KAHKAHA], [SIGHS]→[İÇ ÇEKİŞ], [GASPS]→[NEFES KESİLİŞ], "
        "[GAGGING]→[ÖĞÜRME], [CRYING]→[AĞLAMA], [GROANS]→[İNLEME], [WHISPERING]→[FISILDAMA])\n"
        "- Never leave an [SFX] tag untranslated — always find a Turkish equivalent\n"
        "- CRITICAL: every numbered id in the payload MUST receive its own translation, even if its source "
        "is a single word, a short interjection ('Okay.', 'Yeah, yeah.', 'Oh.'), or a bracketed sound effect. "
        "NEVER merge a short cue's meaning into a neighboring id's translation, and NEVER leave a short cue's "
        "translation empty or skip it — doing so shifts every subsequent id's alignment and desyncs the subtitles.\n"
        "- For technical/scientific terms NOT in the glossary, prefer the internationally accepted "
        "loanword (e.g. 'detonatör', 'dinamit', 'robot', 'laser') — do NOT invent Turkish equivalents\n"
        "- Do NOT invent pseudo-Turkish or foreign-looking words. If a term is unknown, use established Turkish, "
        "an accepted loanword, or a concise natural paraphrase.\n"
        "- Possessive forms: 'my girlfriend'→'sevgilim' (NOT 'severim'), "
        "'my friend'→'arkadaşım', 'my name'→'adım'\n"
        "- Informal address (man, dude, buddy, bro): 'dostum', 'arkadaşım', 'kanka' "
        "(NEVER 'kimse')\n"
        "- Titles/honorifics use Turkish convention, NOT literal: 'Mr. Smith'→'Bay Smith' or naturally "
        "'Smith Bey'; 'Mrs./Ms. Smith'→'Smith Hanım'; 'Dr. Brown'→'Doktor Brown'; 'Professor X'→'Profesör X'; "
        "ranks use the Turkish rank ('Captain'→'Yüzbaşı', 'Sergeant'→'Çavuş', 'Officer Reed'→'Memur Reed'). "
        "Standalone vocative 'Sir'/'ma'am'→'efendim' (NEVER 'Bay'/'Bayan' alone); 'my lord/lady'→'lordum/leydim'. "
        "Bey/Hanım FOLLOW a first name ('Mr. John'→'John Bey'); Bay/Bayan/Doktor/Profesör/ranks stay BEFORE the "
        "name. Match the sen/siz register chosen for the pair.\n"
        "- Spoken times/numbers use natural Turkish SPEECH, not a literal digit reading: 'half past three'→"
        "'üç buçuk', 'quarter to nine'→'dokuza çeyrek var', 'a.m./p.m.'→drop or 'sabah/akşam'; spoken numbers "
        "stay words ('two thousand'→'iki bin'). Do NOT round or change any value; keep on-screen/written numbers, "
        "dates, scores and exact technical figures EXACTLY as the source. Decimal point in digits → comma "
        "(3.5→3,5).\n"
        "- On-screen TEXT (signs, captions, headlines, displayed messages/letters, location/date cards) is a "
        "label, not speech: render it in flat, neutral Turkish — no colloquial fillers (yani/işte/vay be). "
        "Still correct and natural; keep any source italics. E.g. sign 'EXIT'→'ÇIKIŞ'; text 'On my way'→'Yoldayım'.\n"
        "- False friends: actually→aslında/gerçekte (NOT aktüel), eventually→sonunda/eninde sonunda "
        "(NOT eventüel), sympathetic→anlayışlı/duyarlı (NOT automatically sempatik), sensible→mantıklı, "
        "ultimately→nihayetinde/sonuçta, fabric→kumaş, library→kütüphane, preservative→koruyucu madde.\n"
        f"{profanity_rule}\n"
        "## CONCRETE TRANSLATION EXAMPLES\n"
        "CORRECT vs WRONG — memorize these patterns:\n"
        "  'IT'S A DETONATOR.' → 'BU BİR DETONATÖR.' | NOT 'BU BİR DÜRTÜKLEYİCİ.' (invented)\n"
        "  'WE'LL TALK, MAN.' → 'KONUŞURUZ, DOSTUM.' | NOT 'KONUŞURUZ, KİMSE.'\n"
        "  'MY GIRLFRIEND' → 'SEVGİLİM' | NOT 'SEVERİM' (wrong grammar)\n"
        "  'BAT WINGS' → 'YARASA KANATLARI' | NOT 'YUSUFÇUK KANATLARI' (dragonfly)\n"
        "  'SHE HAS A LION'S BODY.' → 'ASLAN BEDENİ VAR.' | NOT hallucinated text\n"
        "  'KNOCK KNOCK.' (door sound) → 'TOK TOK.' | NOT 'KAPİ KİM?' (that is the reply)\n"
        "  'YES, SIR.' → 'EVET, EFENDİM.' | NOT 'EVET, BAY.'\n"
        + "## IDIOM & REGISTER TRAPS — translate the MEANING, never word-for-word\n"
        "  Archaic/poetic English MUST be translated, never left as-is:\n"
        "    'ye' → 'ey'/'siz'; 'thee/thou' → 'sen'; ''tis' → 'işte/bu'\n"
        "    'look upon my works, ye mighty' → 'eserlerime bakın, ey ulular' | NOT 'ye büyükler'\n"
        "  Exclamation idioms → a natural Turkish exclamation, NEVER a literal proper-noun:\n"
        "    'Great Scott!' → 'Vay canına!'/'Aman Tanrım!' | NOT 'Büyük Scott!'\n"
        "    'Holy smokes/cow!' → 'Vay be!'/'Hay aksi!'; 'Geez/Jeez' → 'Off ya'/'Tanrım'\n"
        "  '-ass' is an INTENSIFIER (kocaman/baya), NOT sexual:\n"
        "    'big-ass door' → 'koca mı koca kapı' | NOT 'koca sikli kapı' (wrong & vulgar)\n"
        "    'bad-ass' → 'baya sağlam/efsane'; 'dumb-ass' → 'koca salak'\n"
        "  Figurative business idioms → the meaning, not the literal words:\n"
        "    'bottom line' (= profit) → 'kâr hanesi'/'kâr' | NOT 'alt çizgi'\n"
        "  Well-known songs/rhymes use their familiar Turkish form, not word-by-word:\n"
        "    'Row, row, row your boat' → 'Kürek çek, kürek çek...' | NOT 'Küre küre' ('row' = kürek çekmek)\n"
        "  Lines marked with ♪/♫ (or clearly sung) are LYRICS: translate for MEANING with natural, "
        "rhythmic Turkish — never warp the meaning to force a rhyme; KEEP the ♪/♫ markers; do NOT inject "
        "colloquial markers (yani/işte/ya) into sung lines.\n"
        + colloquial_block
        + "## TURKISH SYNTAX & FLOW\n"
        "- Turkish is SOV — let the finite verb fall at the clause end; do NOT carry English S-V-O order when it yields stilted Turkish.\n"
        "- AVOID premature verb closure (erken yüklem kapanması) on cross-cue sentences. If a sentence continues in the next block, do NOT write a finished Turkish verb in the current block (e.g. do NOT translate 'Throughout history, humanity has struggled / with fears of Armageddon' as 'Tarih boyunca insanlık boğuştu, / Armageddon korkularıyla'). Instead, delay the verb to the end of the sentence or keep the sentence open using Turkish relative clauses, participles, or conjunctions.\n"
        "- Subtitle Sentence Splitting & Info Flow: When a single sentence spans across multiple contiguous subtitle blocks:\n"
        "  * If they are close in time (dialogue flows naturally), prioritize natural Turkish word order (SOV). It is preferred to shift information across boundaries (e.g. putting the dependent clause 'Yağmur yağdığı için' in the first subtitle, and the verb 'markete gittim' in the second) to keep the Turkish flow smooth and standard.\n"
        "  * If there is a noticeable time gap (> 1.5 seconds) between the subtitles, try to keep the meaning of each block self-contained. In this case, you may use natural-sounding inverted sentences (devrik cümle) or conjunctions ('çünkü', 'fakat') to prevent displaying translations of future speech too early.\n"
        "- English subordinate clauses ('when/because/after X, Y') usually collapse into ONE Turkish clause "
        "via a converb/participle: 'When he arrived, she left' → 'O gelince kadın gitti' (NOT two sentences).\n"
        "- Pro-drop: omit subject pronouns the verb ending already carries ('I'm going'→'Gidiyorum', not "
        "'Ben gidiyorum') unless the pronoun is contrastive/emphatic.\n"
        "- Dummy 'it' (weather/time/existential) has NO Turkish subject: 'It's raining'→'Yağmur yağıyor', "
        "'It's three o'clock'→'Saat üç' — never 'O yağıyor'.\n"
        + "## TRANSLITERATION GUARD — CRITICAL\n"
        f"NEVER leave English slang/profanity untranslated in {tgt}:\n"
        "  ass / ass- → göt, kıç  (NEVER write 'ass' or 'assını')\n"
        "  shit / shitting → bok, sıçmak  (NEVER write 'shit')\n"
        "  fuck / fucking → sik-, orospu çocuğu  (NEVER write 'fuck')\n"
        "  damn → kahretsin, lanet  (NEVER write 'damn')\n"
        "  hell → cehennem, kahretsin  (NEVER write 'hell')\n"
        "  bitch → orospu, kaltak, it  (NEVER write 'bitch')\n"
        "  crap → bok, saçmalık  (NEVER write 'crap')\n"
        f"Scan your output: an untranslated English SLANG word, profanity, or everyday word is an error. "
        f"(Proper nouns, brand/character names, and accepted loanwords/technical terms — 'detonatör', 'robot', "
        f"'laser', 'online' — are NOT errors.)"
        + JSON_INSTRUCTION
    )

SCENE_GAP_SEC    = 3.0   # seconds; larger gap = new scene → reset rolling context
# Bir "çok satırlı cümle" fragman grubu en fazla bu kadar cue sürebilir. Daha uzun
# kapanmayan bir dizi gerçek bir cümle değildir → dosyada noktalama yok demektir
# (ör. otomatik üretilmiş altyazı). O durumda frag mantığı güvenilmez; grubu bağımsız
# bırakırız ki chunk'lama serbestçe bölebilsin (model sürekliliği next_ctx'ten anlar).
MAX_FRAG_GROUP   = 10
CPS_WARN_LIMIT   = 24    # chars/sec; Turkish naturally longer than English (21→24)

def _ts_to_sec_gui(ts_str: str) -> float:
    """Parse 'HH:MM:SS,mmm' or 'HH:MM:SS,mmm --> HH:MM:SS,mmm' → start seconds."""
    ts = ts_str.split('-->')[0].strip().replace(',', '.')
    h, m, s = ts.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)

def _ts_end_sec_gui(ts_str: str) -> float:
    """Parse end time from 'HH:MM:SS,mmm --> HH:MM:SS,mmm' → seconds."""
    parts = ts_str.split('-->')
    ts = (parts[1] if len(parts) > 1 else parts[0]).strip().replace(',', '.')
    h, m, s = ts.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)

def _log_cps_warning(blocks: list, log_fn) -> int:
    """CPS_WARN_LIMIT'i aşan (çok hızlı okunması gereken) satırları sayıp tek bir
    uyarı satırı loglar. Tüm akışlar (sync-hybrid, hybrid-batch, düz-batch) TEK bu
    fonksiyonu paylaşır — böylece batch koşularında da sync'teki CPS görünürlüğü olur
    (scan_translation_quality yalnız rapora istatistik yazar, interaktif log basmaz).
    Aşan satır sayısını döner (0 = uyarı yok)."""
    cps_issues = []
    for idx, ts, text in blocks:
        try:
            dur = max(_ts_end_sec_gui(ts) - _ts_to_sec_gui(ts), 0.1)
            speed = len(str(text).replace('\n', '')) / dur
            if speed > CPS_WARN_LIMIT:
                cps_issues.append((idx, round(speed, 1)))
        except Exception:
            pass
    if cps_issues and log_fn:
        log_fn(f"CPS uyarısı: {len(cps_issues)} satır çok hızlı "
               f"(>{CPS_WARN_LIMIT} kar/sn) — örnek: #{cps_issues[0][0]} "
               f"({cps_issues[0][1]} kar/sn)", "warn")
    return len(cps_issues)

def _clean_src(text: str) -> str:
    """Strip HTML/ASS formatting tags from source text before translation."""
    text = re.sub(r'</?[a-zA-Z][^>]*>', '', text)   # <i>, <b>, <font ...>
    text = re.sub(r'\{[^}]+\}', '', text)             # {an8}, {\c&H...}
    text = re.sub(r'  +', ' ', text)
    return text.strip()


def _ends_sentence_gui(text: str) -> bool:
    """True if text ends with sentence-closing punctuation."""
    t = text.strip().rstrip('"\'»"\u201d')
    return bool(t) and t[-1] in '.!?…'


def _ellipsis_continues_gui(cur: str, nxt: str) -> bool:
    """'...' ile biten satır devam cümlesi mi? Sonraki satır elipsisle veya
    küçük harfle başlıyorsa cümle sarkıyor demektir ('Düşünüyordum...' / '...dün olanları')."""
    c = cur.rstrip('"\'»” ').rstrip()
    if not (c.endswith('...') or c.endswith('…')):
        return False
    n = nxt.lstrip('"\'«“ ').lstrip()
    return bool(n) and (n.startswith('...') or n.startswith('…') or n[0].islower())


def _tag_fragments_gui(blocks: list, scene_gap_sec: float = None) -> dict:
    """Detect multi-line sentence fragments among (idx, ts, text) blocks.
    Returns {idx: 'none'|'start'|'mid'|'end'}."""
    tags = {}
    n = len(blocks)
    gap_limit = SCENE_GAP_SEC if scene_gap_sec is None else float(scene_gap_sec)

    def _closes(k: int) -> bool:
        """blocks[k] cümleyi kapatıyor mu? (elipsis devamı kapatmaz)"""
        t = _clean_src(blocks[k][2])
        if not _ends_sentence_gui(t):
            return False
        nxt = _clean_src(blocks[k + 1][2]) if k + 1 < n else ""
        return not _ellipsis_continues_gui(t, nxt)

    def _scene_break_before(k: int) -> bool:
        if k <= 0 or gap_limit <= 0:
            return False
        try:
            return (_ts_to_sec_gui(blocks[k][1]) - _ts_end_sec_gui(blocks[k - 1][1])) >= gap_limit
        except Exception:
            return False

    i = 0
    while i < n:
        if _closes(i) or i == n - 1:
            tags[blocks[i][0]] = "none"
            i += 1
        else:
            group = [i]
            j = i + 1
            closed = False
            while j < n:
                if _scene_break_before(j):
                    break
                group.append(j)
                if _closes(j) or j == n - 1:
                    closed = True
                    break
                j += 1
            i = group[-1] + 1
            if not closed:
                for k in group:
                    tags[blocks[k][0]] = "none"
                continue
            # GÜVENLİK: aşırı uzun "kapanmayan" grup = noktalama yok (gerçek cümle değil).
            # Hepsini bağımsız (none) bırak → chunk'lama serbest böler, dev chunk oluşmaz.
            if len(group) > MAX_FRAG_GROUP:
                for k in group:
                    tags[blocks[k][0]] = "none"
                continue
            if len(group) == 1:
                tags[blocks[group[0]][0]] = "none"
            elif len(group) == 2:
                tags[blocks[group[0]][0]] = "start"
                tags[blocks[group[1]][0]] = "end"
            else:
                tags[blocks[group[0]][0]] = "start"
                for k in group[1:-1]:
                    tags[blocks[k][0]] = "mid"
                tags[blocks[group[-1]][0]] = "end"
    return tags





def _fragment_groups_gui(blocks: list, frag_tags: dict | None = None,
                         scene_gap_sec: float = None) -> tuple[dict, list]:
    """Return per-block fragment group ids and compact source sentence groups."""
    if frag_tags is None:
        frag_tags = _tag_fragments_gui(blocks, scene_gap_sec=scene_gap_sec)
    groups = []
    group_by_idx = {}
    current = []

    def _flush():
        nonlocal current
        if len(current) < 2:
            current = []
            return
        first = current[0][0]
        last = current[-1][0]
        group_id = f"fg_{first}_{last}"
        items = []
        for idx, _ts, text in current:
            group_by_idx[idx] = group_id
            items.append(str(idx))
        groups.append({
            "id": group_id,
            "items": items,
        })
        current = []

    for block in blocks:
        idx = block[0]
        tag = frag_tags.get(idx, "none")
        if tag == "start":
            _flush()
            current = [block]
        elif tag in {"mid", "end"} and current:
            current.append(block)
            if tag == "end":
                _flush()
        else:
            _flush()
    _flush()
    return group_by_idx, groups


def _scene_cut_near_gui(blocks: list, start_i: int, target_end: int, window: int = 5,
                        scene_gap_sec: float = None):
    """Chunk hedefinin ±window satır penceresinde sahne sınırı (≥SCENE_GAP_SEC boşluk) arar.
    Bulursa kesim index'ini döner (chunk o index'ten ÖNCE biter), yoksa None."""
    n = len(blocks)
    best = None
    gap_limit = SCENE_GAP_SEC if scene_gap_sec is None else float(scene_gap_sec)
    for cand in range(max(start_i + 1, target_end - window),
                      min(n, target_end + window + 1)):
        try:
            gap = _ts_to_sec_gui(blocks[cand][1]) - _ts_end_sec_gui(blocks[cand - 1][1])
        except Exception:
            continue
        if gap >= gap_limit and (best is None
                                 or abs(cand - target_end) < abs(best - target_end)):
            best = cand
    return best


def _make_smart_chunks_gui(blocks: list, chunk_size: int, frag_tags=None,
                           scene_gap_sec: float = None) -> list:
    """Split (idx, ts, text) blocks into chunks that avoid cutting mid-sentence.
    Prefers scene boundaries near the target size, then sentence boundaries,
    and never splits inside a fragment group.
    frag_tags: önceden hesaplanmış fragment tags; None ise dahili hesaplar."""
    chunk_size = max(int(chunk_size or 1), 1)
    if frag_tags is None:
        frag_tags = _tag_fragments_gui(blocks, scene_gap_sec=scene_gap_sec)
    chunks = []
    i = 0
    n = len(blocks)
    while i < n:
        end = min(i + chunk_size, n)
        if end < n:
            # 1) Tercih: sahne sınırına hizala (±5 satır penceresi)
            scene_cut = _scene_cut_near_gui(blocks, i, end, scene_gap_sec=scene_gap_sec)
            if scene_cut is not None:
                end = scene_cut
            else:
                # 2) Cümle sonuna hizala
                for extra in range(0, 6):
                    check_idx = end - 1 + extra
                    if check_idx >= n:
                        end = n
                        break
                    text = _clean_src(blocks[check_idx][2])
                    if _ends_sentence_gui(text):
                        end = min(check_idx + 1, n)
                        break
            # Never cut inside a fragment group — ama chunk'ı şişirme: sert tavan koy
            # (grup MAX_FRAG_GROUP ile sınırlı; yine de noktasız uç durumda güvence)
            _frag_ceiling = min(n, i + chunk_size + MAX_FRAG_GROUP)
            while (end < _frag_ceiling
                   and frag_tags.get(blocks[end - 1][0]) in ("start", "mid")):
                end += 1
        chunks.append(blocks[i:end])
        i = end
    return chunks


def build_requests(srt_files, src, tgt, model, chunk_size=CHUNK, schema=None,
                    profanity="Orta", glossary: dict = None, project_memory=None,
                    file_hints: dict = None, block_cache: dict = None,
                    context_lines: int = None, lookahead_lines: int = None,
                    scene_gap_sec: float = None, scene_emotions: list = None,
                    temperature: float = None):
    import hybrid_translate as ht   # modül seviyesinde değil; term_in_text için gerekli
    if context_lines is None:
        context_lines = CONTEXT_LINES
    if lookahead_lines is None:
        lookahead_lines = LOOKAHEAD_LINES
    scene_gap_sec = SCENE_GAP_SEC if scene_gap_sec is None else float(scene_gap_sec)
    temperature = 0.2 if temperature is None else float(temperature)
    sys_prompt = _build_sync_system_prompt(src, tgt, schema, profanity)
    # Proje hafızası varsa system prompt'a ekle
    if project_memory is not None:
        try:
            hint = project_memory.build_context_hint()
            if hint:
                sys_prompt = sys_prompt + hint
        except Exception:
            pass
    requests, file_map = [], {}
    # Şemaya gömülü sözlük (ör. Warhammer terimleri) — aktif sözlükle birleştir;
    # kullanıcının kendi sözlüğü öncelikli (şema değerini ezer).
    _schema_gloss = (schema or {}).get("glossary") or {}
    gloss = {**_schema_gloss, **(glossary or {})} if _schema_gloss else (glossary or {})
    _cache = block_cache or {}
    for fp in srt_files:
        # Çağıran zaten parse ettiyse cache'ten al (sync/batch _block_cache) — disk okumaz
        blocks = _cache.get(fp)
        if blocks is None:
            blocks = list(parse_subtitle(fp))
        if not blocks:
            continue
        # Dosya düzeyi ön-bağlam hint'i (özet, karakterler, sen/siz, terimler)
        _fhint = (file_hints or {}).get(fp)
        file_sys_prompt = sys_prompt + _fhint if _fhint else sys_prompt
        # Pre-split into smart chunks (avoids cutting mid-sentence)
        frag_tags     = _tag_fragments_gui(blocks, scene_gap_sec=scene_gap_sec)
        frag_group_ids, fragment_groups = _fragment_groups_gui(
            blocks, frag_tags, scene_gap_sec=scene_gap_sec)
        chunks        = _make_smart_chunks_gui(
            blocks, chunk_size, frag_tags=frag_tags, scene_gap_sec=scene_gap_sec)
        # Path hash dosya başına bir kez hesapla — chunk döngüsü içinde tekrar etme
        _phash        = hashlib.md5(fp.encode("utf-8", errors="replace")).hexdigest()[:12]
        _fp_stem      = Path(fp).stem[:40]
        prev_ctx       = []
        prev_scene_ctx = []   # kapanan sahnenin son satırları — köprü bağlamı
        prev_end_sec   = None
        for ci, chunk in enumerate(chunks):
            cs  = chunk[0][0]   # first block's SRT index
            cid = f"{_fp_stem}_{_phash}__g{cs}"
            file_map[cid] = [(idx, ts, fp) for (idx, ts, _) in chunk]

            # Scene break detection — bağlam sıfırlanır ama kim/ne köprüsü taşınır
            scene_broke = False
            try:
                first_start = _ts_to_sec_gui(chunk[0][1])
                if prev_end_sec is not None and (first_start - prev_end_sec) >= scene_gap_sec:
                    prev_scene_ctx = prev_ctx[-6:] if prev_ctx else []
                    prev_ctx = []
                    scene_broke = True
            except Exception:
                pass

            # Build tr_items with source cleanup + duration + fragment tag
            tr_items = []
            chunk_text_lower = ""
            for idx, ts, text in chunk:
                try:
                    start = _ts_to_sec_gui(ts)
                    end   = _ts_end_sec_gui(ts)
                    dur   = round(max(end - start, 0.5), 2)
                except Exception:
                    dur   = 2.0
                clean = _clean_src(text)
                item  = {"i": idx, "t": clean, "d": dur}
                if ht.looks_like_on_screen_text(text):
                    item["is_ost"] = True
                tag = frag_tags.get(idx, "none")
                if tag != "none":
                    item["frag"] = tag
                    if idx in frag_group_ids:
                        item["frag_group"] = frag_group_ids[idx]
                tr_items.append(item)
                chunk_text_lower += " " + clean.lower()

            payload  = {"tr": tr_items}
            scene_plan = ht._scene_context_for_chunk(scene_emotions, chunk[0][0], chunk[-1][0])
            if scene_plan:
                payload["scene"] = scene_plan
            chunk_ids = {idx for idx, _ts, _text in chunk}
            chunk_groups = [
                group for group in fragment_groups
                if any(group_item in chunk_ids for group_item in group["items"])
            ]
            if chunk_groups:
                payload["sentence_groups"] = chunk_groups
            if prev_ctx:
                payload["ctx"] = prev_ctx
            if scene_broke and prev_scene_ctx:
                payload["prev_scene"] = prev_scene_ctx
            if ci + 1 < len(chunks):
                nxt = [{"i": idx, "t": _clean_src(text)}
                       for (idx, ts, text) in chunks[ci + 1][:lookahead_lines]]
                if nxt:
                    payload["next_ctx"] = nxt
            # Active glossary: only terms that appear in this chunk
            quality_terms = ht.quality_glossary_for_source(chunk_text_lower)
            if gloss:
                active = {k: v for k, v in gloss.items()
                          if ht.term_in_text(k, chunk_text_lower)}
                active = {**quality_terms, **ht.sanitize_glossary_for_turkish(active, target_language=tgt)}
                if active:
                    payload["glossary"] = active
            elif quality_terms:
                payload["glossary"] = quality_terms

            try:
                prev_end_sec = _ts_end_sec_gui(chunk[-1][1])
            except Exception:
                prev_end_sec = None
            prev_ctx = [{"i": idx, "t": _clean_src(text)} for (idx, ts, text) in chunk[-context_lines:]]

            # gpt-5/reasoning model checks
            _model_lower = model.lower()
            _is_no_temp = (
                _model_lower.startswith("gpt-5")
                or _model_lower.startswith("codex-")
                or _model_lower.startswith("o1")
                or _model_lower.startswith("o3")
                or _model_lower.startswith("o4")
            )
            messages = [
                {"role": "system", "content": file_sys_prompt},
                {"role": "user",   "content": json.dumps(payload, ensure_ascii=False)},
            ]
            if _is_no_temp:
                for msg in messages:
                    if msg["role"] == "system":
                        msg["role"] = "developer"

            req_body = {
                "model": model,
                "messages": messages,
                # GERÇEK chunk uzunluğuna göre bütçe (nominal chunk_size değil) — akıllı
                # chunk'layıcı chunk_size'ı aşabiliyor; sabit bütçe büyük chunk'larda yanıtı
                # kesiyordu. +500 taban: reasoning token + JSON yapısı payı.
                "max_completion_tokens": max(chunk_size, len(chunk)) * 120 + 500,
            }
            if not _is_no_temp:
                req_body["temperature"] = temperature

            requests.append({
                "custom_id": cid,
                "method": "POST", "url": "/v1/chat/completions",
                "body": req_body
            })
    return requests, file_map

def _inject_prev_tr(user_content: str, prev_pairs: list, max_pairs: int = CONTEXT_LINES) -> str:
    """Zincirleme bağlam: önceki chunk'ın çevirilerini payload'a 'prev_tr' olarak ekler.

    Payload'da 'ctx' yoksa sahne sınırı demektir (build_requests sıfırlamıştır) —
    o durumda çeviri bağlamı da taşınmaz, içerik aynen döner."""
    if not prev_pairs:
        return user_content
    try:
        payload = json.loads(user_content)
    except Exception:
        return user_content
    if "ctx" not in payload:
        return user_content
    payload["prev_tr"] = prev_pairs[-max_pairs:]
    return json.dumps(payload, ensure_ascii=False)


def _chain_pairs_from_result(user_content: str, trans_map: dict) -> list:
    """Tamamlanan chunk'tan sonraki chunk'ın prev_tr'i için (src, tr) çiftleri üretir.

    [HATA] satırları atlanır; hiç geçerli çift yoksa boş liste döner."""
    try:
        payload = json.loads(user_content)
    except Exception:
        return []
    pairs = []
    for item in payload.get("tr", []):
        if not isinstance(item, dict) or "i" not in item:
            continue
        tr = trans_map.get(str(item["i"]))
        if not tr or tr == "[HATA]":
            continue
        pairs.append({"i": item["i"], "tr": tr})
    return pairs


# ── İki-dalgalı zincirli batch (B3) — saf yardımcılar ─────────────────────────
# Batch API "hepsini birden gönder" modelinde çalışır; tek batch içinde chunk N+1'e
# chunk N'in ÇEVİRİSİNİ enjekte etmek mümkün değil (hepsi paralel işlenir). B3 dosyayı
# İKİ dalgaya böler: A dalgası çevrilir, BİTER, sonra A'nın kuyruk çevirileri B'nin
# ilk chunk'ına prev_tr olarak verilir. Bu, sync'in N-1 zincir sınırından yalnız 1'ini
# (dosya ortasındaki tek sınır) verir — bilinçli, dar bir kazanç (bkz. B3 tasarım kararı).
# Latency 2×'e çıkar (iki sıralı dalga); opt-in, varsayılan KAPALI.

def _req_has_ctx(req) -> bool:
    """İstek payload'ında 'ctx' var mı? (yoksa chunk bir sahne BAŞLANGICIdır ve
    _inject_prev_tr no-op olur — enjeksiyonun işe yaraması için B'nin ilk chunk'ı
    ctx'li, yani bir devam-chunk'ı olmalı)."""
    try:
        payload = json.loads(req["body"]["messages"][1]["content"])
        return "ctx" in payload
    except Exception:
        return False


def _split_waves(requests: list, target_frac: float = 0.5, min_wave: int = 2) -> tuple:
    """İstek listesini (A dalgası, B dalgası) olarak böler.

    Bölme noktası dosya ortasına (target_frac) EN YAKIN, B dalgasının İLK chunk'ının
    ctx'li (devam-chunk'ı) olduğu chunk sınırıdır — böylece tek zincir sınırı bir sahne
    kesintisine değil, çevirinin gerçekten faydalanacağı bir devam noktasına düşer.
    Çok az chunk varsa (< 2*min_wave) bölme yapılmaz → ([], requests) döner (tek batch)."""
    n = len(requests)
    if n < min_wave * 2:
        return [], list(requests)
    target = max(min_wave, min(n - min_wave, round(n * target_frac)))
    best = None
    for delta in range(0, n):
        for cand in (target + delta, target - delta):
            if min_wave <= cand <= n - min_wave and _req_has_ctx(requests[cand]):
                best = cand
                break
        if best is not None:
            break
    if best is None:
        best = target   # ctx'li sınır bulunamadı (nadir) — ortadan böl, enjeksiyon no-op olsa da böl
    return list(requests[:best]), list(requests[best:])


def _chain_waves(wave_a: list, wave_b: list, wave_a_raw_map: dict,
                 fmap: dict, max_pairs: int) -> list:
    """A dalgasının KUYRUK çevirilerini B dalgasının İLK chunk'ına prev_tr enjekte eder.

    wave_a_raw_map: {custom_id: ham_yanıt_metni} (A dalgası sonuçları).
    Enjekte edilmiş B dalgasını döner. A'nın hiç geçerli çevirisi yoksa (ör. hepsi
    [HATA]) B DEĞİŞMEDEN döner — zarafetli düşüş."""
    if not wave_a or not wave_b:
        return wave_b
    prev_pairs = []
    for req in wave_a:  # ileri yürü, son boş-olmayan çiftleri tut = A'nın kuyruğu
        cid = req.get("custom_id")
        raw = wave_a_raw_map.get(cid)
        if not raw:
            continue
        tmap = parse_response(raw, fmap.get(cid, []))
        pairs = _chain_pairs_from_result(req["body"]["messages"][1]["content"], tmap)
        if pairs:
            prev_pairs = pairs
    if not prev_pairs:
        return wave_b
    first = wave_b[0]
    um = first["body"]["messages"][1]
    um["content"] = _inject_prev_tr(um["content"], prev_pairs, max_pairs=max_pairs)
    return wave_b


def _raw_map_from_batch_content(content: str) -> dict:
    """Batch çıktı JSONL içeriğinden {custom_id: ham_yanıt_metni} çıkarır (SALT-OKUMA,
    token SAYMAZ). İki-dalgalı B3, A dalgasının ham çevirisini zincirleme için buradan
    alır; nihai birleşik save_results tokenları A+B için bir kez sayar (çift sayım yok)."""
    raw_map = {}
    for line in (content or "").strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            res = json.loads(line)
            cid = res["custom_id"]
            if res.get("error"):
                continue
            body = (res.get("response") or {}).get("body") or {}
            choices = body.get("choices") or []
            if not choices:
                continue
            txt = ((choices[0].get("message") or {}).get("content") or "").strip()
            if txt:
                raw_map[cid] = txt
        except Exception:
            continue
    return raw_map


def _src_map_from_cues(cues) -> dict:
    """Cue listesi (obje veya (idx, ts, text) tuple) → {idx_str: temiz kaynak metin}.
    Polish Pass'in 'en' alanı için kullanılır."""
    out = {}
    for c in cues or []:
        try:
            # Dikkat: tuple'ın yerleşik .index METODU vardır — ayrımı .text ile yap
            if hasattr(c, "text"):
                out[str(c.index)] = _clean_src(c.text)
            else:
                out[str(c[0])] = _clean_src(c[2])
        except Exception:
            continue
    return out


def _raw_src_map_from_cues(cues) -> dict:
    """Cue listesi → {idx_str: HAM kaynak metin} (etiketler sökülmemiş).
    restore_format_tags için kullanılır — temizlenmiş metin işe yaramaz."""
    out = {}
    for c in cues or []:
        try:
            if hasattr(c, "text"):
                out[str(c.index)] = c.text
            else:
                out[str(c[0])] = c[2]
        except Exception:
            continue
    return out


def _restore_tags_blocks(blocks: list, raw_src_map: dict) -> list:
    """Çeviri bloklarına kaynaktaki biçim etiketlerini ({\\an8}, <i> vb.) geri uygular."""
    if not raw_src_map:
        return blocks
    return [(idx, ts, restore_format_tags(raw_src_map.get(str(idx), ""), text))
            for idx, ts, text in blocks]


def _fill_hata_with_source(blocks: list, raw_src_map: dict, log_fn=None):
    """[HATA*] satırlarını görünür eksik-çeviri işaretiyle bırakır.

    raw_src_map: {idx_str: ham kaynak metin} — _raw_src_map_from_cues üretir.
    Kaynak metni hedef dosyaya yazmak kalite açısından tehlikeli olduğu için artık
    kaynakla doldurmayız; satırı kullanıcıya ve kalite raporuna açıkça görünür
    olacak şekilde işaretleriz. Döner: (yeni_bloklar, işaretlenen_sayı)."""
    if not raw_src_map:
        return blocks, 0
    out, marked = [], 0
    for idx, ts, text in blocks:
        if str(text).startswith("[HATA"):
            src = raw_src_map.get(str(idx))
            if src:
                out.append((idx, ts, "[ÇEVİRİ EKSİK]"))
                marked += 1
                continue
        out.append((idx, ts, text))
    if marked and log_fn:
        log_fn(f"{marked} çevrilemeyen satır kaynak metne düşürülmedi; [ÇEVİRİ EKSİK] olarak işaretlendi", "warn")
    return out, marked



def _semantic_text_for_repair(text: str) -> str:
    s = re.sub(r'</?[a-zA-Z][^>]*>', '', str(text or ''))
    s = re.sub(r'\{[^}]*\}', '', s)
    s = re.sub(r'\([^)]*\)|\[[^\]]*\]|[\u266a_]+', '', s)
    return s.strip()


def _has_wordlike_text(text: str) -> bool:
    return bool(re.search(r'[^\W_]', text or '', re.UNICODE))


def _is_punct_only_translation(src_text: str, tr_text: str) -> bool:
    src_sem = _semantic_text_for_repair(src_text)
    if not _has_wordlike_text(src_sem):
        return False
    tr_sem = _semantic_text_for_repair(tr_text)
    return not _has_wordlike_text(tr_sem)


_NUMERIC_ONLY_SRC_RE = re.compile(r'^[\d\s.,;:!?…\-]+$')


def _src_is_numeric_only(src_text: str) -> bool:
    """Kaynak yalnızca sayı/noktalama mı (ör. '1, 2, 3, 4, 5...' bir sayma
    dizisi)? Böyle satırlarda kaynakla çeviri arasında hiçbir kelime farkı
    olamaz -- identity aynen doğru çeviridir, 'çevrilmemiş' değil. Gerçek olay
    (A Metamorfose dos Passaros, 2026-07-20): 8 sayma-cue'su ("1, 2, 3, 4,
    5...", "621, 622, 623, 624...") kaynakla birebir aynı kaldığı için
    yanlışlıkla çevrilmemiş sanıldı."""
    stripped = str(src_text or '').strip()
    return bool(stripped) and bool(_NUMERIC_ONLY_SRC_RE.match(stripped)) and any(c.isdigit() for c in stripped)


_MUSIC_ONLY_RE = re.compile(
    r'^[\s*♪♫\u266a\u266b]+$'
    r'|^(?=.*[*♪♫])[\*\s♪♫]*'
    r'(?:[A-Za-z]{2,4}(?:[-–][A-Za-z]{2,4})?(?:\s+[A-Za-z]{2,4}(?:[-–][A-Za-z]{2,4})?)*)'
    r'[\*\s♪♫]*$'
    r'|^\[MÜZİK\]$|^\[MUSIC\]$'
    r'|^♪[^♪]*♪$',
    re.I,
)


_SDH_ONLY_SRC_RE = re.compile(r'^(?:\([^)]*\)|\[[^\]]*\]|[♪_\s]+)+$')
_PARTIAL_ENGLISH_LEAK_RE = re.compile(r'\b(?:Egyptian|creation|mythology)\b', re.I)
_PARTIAL_ENGLISH_LEAK_PHRASE_RE = re.compile(
    r"\bIn\s+(?:18|19|20)\d{2}\b"
    r"|\bInstitute\s+for\s+Learning\s+and\s+Brain(?:\s+Sciences)?\b"
    r"|\bmedical\s+student(?:['’]s)?\s+disease\b",
    re.I,
)


def _src_is_sdh_only(src_text: str) -> bool:
    """Kaynak satır yalnızca SFX/SDH köşeli-parantez/parantez/nota içeriği mi
    (gerçek diyalog kelimesi yok). _is_untranslated'daki iki ayrı kontrolde
    (boş çeviri + source==target) aynı mantık kullanılıyor, tek yerden."""
    no_sdh = re.sub(r'\([^)]*\)|\[[^\]]*\]|[♪_]+', '', src_text).strip()
    return (not no_sdh) or bool(_SDH_ONLY_SRC_RE.match(src_text.strip()))


def _src_text_is_all_caps(src_text: str) -> bool:
    """Kaynak, köşeli parantez OLMADAN yazılmış BÜYÜK HARF bir SDH/SFX
    açıklaması gibi mi (ör. 'BANGING AND LAUGHTER')? Böyle satırlar Türkçeye
    çevrilirken çoğunlukla köşeli parantezle sarmalanıyor ('[VURMA SESLERİ VE
    KAHKAHA]') — bu bilinçli bir biçim tercihi, içerik kaybı değil."""
    toks = [w for w in (t.strip('.,!?;:\'"()[]…-«»“”') for t in str(src_text or '').split()) if w]
    return bool(toks) and all(w[:1].isupper() for w in toks)


def _is_untranslated(src_text: str, tr_text: str) -> bool:
    import re
    if not src_text:
        return False
    if not tr_text:
        # Boş çeviri: kaynak SFX/SDH-only İSE meşru olabilir (clean_sdh nasılsa
        # boşa indirir) — ama gerçek diyalog içeriyorsa bu SESSİZ bir çeviri
        # kaybıdır (bkz. plans/s04e12-cue-shift-without-repair-brief.md Görev 6 —
        # kısa/ünlem cue'lar modelce atlanıp komşu cue'ya birleştirilebiliyor).
        # True dönmesi _repair_untranslated_sync'in bunu yakalayıp doğru kaynakla
        # yeniden çevirmesini sağlar.
        return not _src_is_sdh_only(src_text)
    if _MUSIC_ONLY_RE.match(src_text.strip()) or _MUSIC_ONLY_RE.match(tr_text.strip()):
        return False
    if _src_is_numeric_only(src_text):
        return False
    leaked = {word.lower() for word in _PARTIAL_ENGLISH_LEAK_RE.findall(src_text)}
    if any(re.search(rf'\b{re.escape(word)}\b', tr_text, re.I) for word in leaked):
        return True
    if any(match.group(0).lower() in tr_text.lower()
           for match in _PARTIAL_ENGLISH_LEAK_PHRASE_RE.finditer(src_text)):
        return True
    _src_all_caps = _src_text_is_all_caps(src_text)
    # Gerçek olay (Louis Theroux Behind Bars, 2026-07-20): kaynak parantezsiz
    # BÜYÜK HARF bir SDH açıklaması ("BANGING AND LAUGHTER"), çeviri bunu doğru
    # şekilde köşeli parantezle sarmalayıp çevirmiş ("[VURMA SESLERİ VE
    # KAHKAHA]"). _is_punct_only_translation köşeli parantez içeriğini SDH-tag
    # sayıp tamamen söküyor -- çevrilmiş metin de köşeli parantez içinde
    # olduğu için "hiç içerik kalmadı" sanıp yanlışlıkla "çevrilmemiş" diye
    # işaretliyordu. Kaynak zaten çıplak BÜYÜK HARF ise bu kontrol atlanır.
    if _is_punct_only_translation(src_text, tr_text) and not _src_all_caps:
        return True
    _LOANWORDS = frozenset([
        "ok", "yes", "no", "hi", "hey", "wow", "oh", "ah",
        "robot", "laser", "internet", "pizza", "taxi",
    ])
    src_words = src_text.split()
    if len(src_words) <= 2:
        return False
    src_norm = re.sub(r'[^\w\s]', '', src_text.lower()).strip()
    tr_norm  = re.sub(r'[^\w\s]', '', tr_text.lower()).strip()
    if src_norm == tr_norm and src_norm not in _LOANWORDS:
        if not _src_is_sdh_only(src_text) and not _src_all_caps:
            return True
    return False


def _chunk_src_map_from_request(req: dict) -> dict:
    """Bir API isteğinin (build_requests/build_batch_requests çıktısı) user mesajından
    {id_str: kaynak_metin} çıkarır — chunk-içi kontrol (ör. _retry_hata'nın
    adjacent_duplicate tetikleyicisi) için. Herhangi bir ayrıştırma hatasında boş dict
    döner (sessizce atla, çökme — bu bir en-iyi-çaba yardımcı fonksiyondur)."""
    try:
        messages = req.get("body", {}).get("messages", [])
        user_msg = next((m for m in messages if m.get("role") == "user"), None)
        if not user_msg:
            return {}
        payload = json.loads(user_msg.get("content", ""))
        tr_items = payload.get("tr", [])
        return {str(it["i"]): str(it.get("t", ""))
                for it in tr_items if isinstance(it, dict) and "i" in it}
    except Exception:
        return {}


def _repair_untranslated_sync(blocks, raw_src_map, client, src_lang, tgt_lang,
                              model="gpt-5.4-mini", schema=None, profanity="Orta",
                              log_fn=None, token_cb=None, max_per_call=15):
    """[HATA*] satırlarını sync API çağrısıyla otomatik çevirir.

    _fill_hata_with_source'dan ÖNCE çağrılmalı. Başarılı çevirileri blocks'a
    geri yazar; başarısız olanlar [HATA] olarak kalır ve son adımda görünür
    eksik-çeviri işaretine çevrilir. Kaynağı SFX/müzik-only olan [HATA] cue'lar
    onarılmaya ÇALIŞILMAZ — bu fonksiyon clean_sdh'ten SONRA çalıştığı için,
    onları API'ye gönderip taze bir SDH çevirisi (ör. "[MÜZİK ÇALIYOR]") üretmek
    clean_sdh'in artık göremeyeceği, ekrana sızan bir SDH etiketiyle sonuçlanır
    (Explorer 1 #36/#636'da doğrulandı) — bunun yerine doğrudan düşürülürler,
    tıpkı clean_sdh'in ilk geçişte yapacağı gibi.
    Döner: (güncel_blocks, onarılan_sayı).
    """
    if not raw_src_map:
        return blocks, 0

    # [HATA] ve çevrilmemiş satırları topla; kaynağı SFX/müzik-only olanları
    # onarım kuyruğuna ALMA — düşürülecekler listesine ekle.
    hata_indices = []
    drop_positions = []
    for i, (idx, ts, text) in enumerate(blocks):
        src = raw_src_map.get(str(idx), "")
        if str(text).startswith("[HATA") or _is_untranslated(src, str(text)):
            if not (src and src.strip()):
                continue
            if _src_is_sdh_only(src):
                drop_positions.append(i)
            else:
                hata_indices.append((i, idx, ts, src))

    if not hata_indices and not drop_positions:
        return blocks, 0

    out = list(blocks)  # mutable kopya
    repaired = 0

    if hata_indices and client:
        if log_fn:
            log_fn(f"🔧  {len(hata_indices)} çevrilmemiş satır sync ile onarılıyor...", "info")

        sys_prompt = _build_sync_system_prompt(src_lang, tgt_lang, schema, profanity)

        # Küçük gruplar halinde çevir
        for batch_start in range(0, len(hata_indices), max_per_call):
            batch = hata_indices[batch_start:batch_start + max_per_call]
            tr_items = [{"i": idx, "t": _clean_src(src)} for (_, idx, _, src) in batch]
            payload = json.dumps({"tr": tr_items}, ensure_ascii=False)

            for attempt in range(2):
                try:
                    resp = _safe_chat_create(
                        client,
                        model=model,
                        messages=[
                            {"role": "system", "content": sys_prompt},
                            {"role": "user",   "content": payload},
                        ],
                        temperature=0.3,
                    )
                    if not resp.choices:
                        if attempt == 0:
                            time.sleep(2)
                            continue
                        break
                    raw_text = (resp.choices[0].message.content or "").strip()
                    if not raw_text:
                        if attempt == 0:
                            time.sleep(2)
                            continue
                        break
                    if token_cb and resp.usage:
                        tok, cached = _get_usage_details(resp.usage)
                        token_cb(tok, cached=cached)
                    arr_text = _extract_json_array(raw_text)
                    items = json.loads(arr_text)
                    if not isinstance(items, list):
                        if attempt == 0:
                            continue
                        break
                    result_map = {it["i"]: it["t"] for it in items
                                 if isinstance(it, dict) and "i" in it and "t" in it
                                 and not str(it["t"]).startswith("[HATA")}
                    for (block_pos, idx, ts, _src) in batch:
                        translated = result_map.get(idx)
                        if translated and translated.strip():
                            out[block_pos] = (idx, ts, translated)
                            repaired += 1
                    break  # success
                except Exception as e:
                    if log_fn:
                        log_fn(f"  ?? Onarim batch basarisiz: {e}", "warn")
                    if attempt == 0:
                        time.sleep(2)
                        continue
                    break

        if log_fn:
            if repaired:
                log_fn(f"✓  {repaired}/{len(hata_indices)} satır onarıldı", "ok")
            else:
                log_fn("⚠  Onarım başarısız — son çareye düşülecek", "warn")

    if drop_positions:
        drop_set = set(drop_positions)
        out = [b for pos, b in enumerate(out) if pos not in drop_set]
        if log_fn:
            log_fn(f"↺  {len(drop_positions)} SFX/müzik-only cue onarılmadı, düşürüldü", "info")

    return out, repaired


# ── Ön-Bağlam Analizi (hybrid kapalıyken dosya düzeyi bağlam) ────────────────
PRECONTEXT_SAMPLE_HEAD = 150   # baştan alınan satır sayısı
PRECONTEXT_SAMPLE_REST = 100   # kalanından eşit aralıkla örneklenen satır sayısı
PRECONTEXT_CACHE_VER   = 2   # +1: _sig alanı eklendi

def _precontext_cache_path(filepath: str) -> Path:
    p = Path(filepath)
    return p.parent / ".context_cache" / (p.stem + ".precontext.json")


def _precontext_cache_sig(filepath: str) -> str:
    try:
        st = Path(filepath).stat()
        return f"{st.st_size}:{int(st.st_mtime)}"
    except Exception:
        return ""


def build_precontext_hint(data: dict, target_language: str = "tr") -> str:
    """Ön-analiz JSON'ını system prompt'a eklenecek metin bloğuna çevirir.

    terms burada da (yeniden) sanitize edilir çünkü `data` eski/bayat bir
    .context_cache/*.precontext.json dosyasından gelmiş olabilir — bu durumda
    analyze_file_precontext hiç çalışmaz, onun sanitize'ı atlanır (bkz. Adım 3,
    plans/sozluk-hedef-dil-guard-brief.md)."""
    if not isinstance(data, dict):
        return ""
    data = _sanitize_precontext_data(dict(data), target_language)
    lines = ["\n## FILE PRE-ANALYSIS (translator notes — follow strictly)"]
    if data.get("summary"):
        lines.append(f"Story: {data['summary']}")
    if data.get("tone"):
        lines.append(f"Overall tone: {data['tone']}")
    char_rows = []
    any_gender = False
    for c in (data.get("characters") or [])[:12]:
        if not isinstance(c, dict) or not c.get("name"):
            continue
        seg = f"- {c['name']}"
        g = str(c.get("gender", "")).strip().lower()
        if g in ("m", "male", "erkek", "man", "boy"):
            seg += " [erkek]"; any_gender = True
        elif g in ("f", "female", "kadın", "kadin", "woman", "girl"):
            seg += " [kadın]"; any_gender = True
        if c.get("role"):
            seg += f" ({c['role']})"
        if c.get("style"):
            seg += f": speaks {c['style']}"
        char_rows.append(seg)
    if char_rows:
        lines.append("Characters:")
        lines.extend(char_rows)
        if any_gender:
            lines.append("(Turkish 'o' is genderless — use the [erkek]/[kadın] tags to pick correct "
                         "gendered words (kız/oğlan, adam/kadın, abi/abla) and keep referents clear.)")
    addr_rows = [f"- {a['a']} → {a['b']}: '{a['register']}'"
                 for a in (data.get("address_map") or [])[:12]
                 if isinstance(a, dict) and a.get("a") and a.get("b") and a.get("register")]
    if addr_rows:
        lines.append("Address register (Turkish sen/siz — apply consistently):")
        lines.extend(addr_rows)
    terms = data.get("terms") or {}
    if isinstance(terms, dict):
        pairs = [f"'{k}' → '{v}'" for k, v in list(terms.items())[:20] if k and v]
        if pairs:
            lines.append("Fixed term translations (use EXACTLY these):")
            lines.extend(f"- {p}" for p in pairs)
    return "\n".join(lines) + "\n" if len(lines) > 1 else ""


def _salvage_precontext_json(s: str) -> dict:
    """Kesik bir üst-düzey JSON nesnesinden ({...) tamamlanmış alanları kurtarır: son
    tamamlanan değer/eleman boundary'sinde açık parantezleri kapatır. Tek geçiş (O(n)).
    Kesik bir dizinin (ör. characters) tamamlanmış elemanlarını da geri getirir."""
    in_str = False
    esc = False
    after_colon = False   # bir ':' sonrası mıyız? (string KEY değil VALUE ise kapatılabilir)
    stack = []            # açık parantez kapanışları: '}' / ']'
    last_safe = -1        # son güvenli boundary konumu
    last_stack = []       # o boundary'deki açık parantez yığını
    for i, ch in enumerate(s):
        if esc:
            esc = False
            continue
        if in_str:
            if ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
                # üst-düzey skaler DEĞER (summary/tone gibi) tamamlandıysa burada kapatılabilir
                if stack == ['}'] and after_colon:
                    last_safe, last_stack = i + 1, list(stack)
                    after_colon = False
            continue
        if ch == '"':
            in_str = True
        elif ch == ':':
            after_colon = True
        elif ch == ',':
            after_colon = False
        elif ch in '{[':
            stack.append('}' if ch == '{' else ']')
            after_colon = False
        elif ch in '}]':
            if stack:
                stack.pop()
            after_colon = False
            if not stack:
                try:
                    return json.loads(s[:i + 1])   # nesne zaten tam
                except Exception:
                    pass
            else:
                last_safe, last_stack = i + 1, list(stack)   # eleman/dizi tamamlandı
    if last_safe > 0:
        frag = s[:last_safe].rstrip().rstrip(',')
        closer = ''.join(reversed(last_stack))   # kalan açık parantezleri kapat
        try:
            obj = json.loads(frag + closer)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            pass
    return {}


def _sanitize_precontext_data(data: dict, tgt: str, log_fn=None) -> dict:
    """terms alanını Türkçe hedef-dil guard'ından geçirir. Precontext yolu (Yardımcı
    Analiz KAPALIYKEN) daha önce HİÇ sanitize edilmiyordu — hybrid yolunun aksine
    (bkz. Adım 3, KRİTİK BOŞLUK, plans/sozluk-hedef-dil-guard-brief.md)."""
    if not isinstance(data, dict):
        return data
    terms = data.get("terms")
    if isinstance(terms, dict) and terms:
        import hybrid_translate as ht
        data["terms"] = ht.sanitize_glossary_for_turkish(terms, target_language=tgt, log_fn=log_fn)
    return data


def analyze_file_precontext(client, blocks, model, src, tgt,
                            log_fn=None, token_cb=None):
    """Tek API çağrısıyla dosya düzeyi bağlam çıkarır: özet, karakterler,
    sen/siz hitap haritası ve sabit terimler. Hata durumunda None döner."""
    texts = [_clean_src(t) for (_i, _ts, t) in blocks if _clean_src(t)]
    if not texts:
        return None
    if len(texts) <= PRECONTEXT_SAMPLE_HEAD + PRECONTEXT_SAMPLE_REST:
        sample_lines = texts
    else:
        head = texts[:PRECONTEXT_SAMPLE_HEAD]
        rest = texts[PRECONTEXT_SAMPLE_HEAD:]
        step = max(1, len(rest) // PRECONTEXT_SAMPLE_REST)
        sample_lines = head + rest[::step][:PRECONTEXT_SAMPLE_REST]
    sample = "\n".join(sample_lines)
    prompt = (
        f"You will translate these {src} subtitles into {tgt} later. First, study this sample "
        f"({len(sample_lines)} of {len(texts)} lines, in chronological order) and extract "
        "translation-critical context.\n\n"
        f"{sample}\n\n"
        "Return ONLY a JSON object with these keys:\n"
        '  "summary": 2-3 sentence plot/content summary\n'
        '  "tone": overall tone/register in a few words (e.g. "casual comedy", "formal documentary")\n'
        '  "characters": [{"name": str, "role": str, "gender": "m|f|unknown", '
        '"style": "how they speak"}] (max 10) — gender lets the translator keep the genderless '
        'Turkish "o" unambiguous and pick correct gendered words\n'
        '  "address_map": [{"a": str, "b": str, "register": "sen|siz"}] — for Turkish T-V distinction, '
        "how character a should address character b based on their relationship (max 10)\n"
        '  "terms": {"source term": "fixed ' + tgt + ' translation"} — recurring names/places/jargon '
        "that must be translated identically every time (max 15)\n"
        "Return ONLY the JSON object."
    )
    try:
        from hybrid_translate import _safe_chat_create
        resp = _safe_chat_create(
            client, model=model,
            messages=[
                {"role": "system",
                 "content": "You are a senior subtitle translation analyst. Output only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=4000, temperature=0.2,   # 1200 yetersizdi: çok karakter/terim olan
        )                                       # dosyalarda JSON kesilip parse çöküyordu
        if token_cb and resp.usage:
            tot, cached = _get_usage_details(resp.usage)
            try:
                token_cb(tot, cached=cached)
            except TypeError:
                token_cb(tot)
        rawtxt = _strip_md((resp.choices[0].message.content or "").strip())
        s, e = rawtxt.find("{"), rawtxt.rfind("}")
        if s == -1 or e <= s:
            raise ValueError("cevapta JSON nesnesi yok")
        try:
            parsed = json.loads(rawtxt[s:e + 1])
        except json.JSONDecodeError:
            # Yine de kesik/bozuksa: tamamlanmış üst-düzey alanları kurtarmayı dene
            salvaged = _salvage_precontext_json(rawtxt[s:e + 1])
            if salvaged:
                if log_fn:
                    log_fn("Ön-bağlam JSON kısmen kurtarıldı (yanıt kesilmişti)", "warn")
                parsed = salvaged
            else:
                raise
        return _sanitize_precontext_data(parsed, tgt, log_fn)
    except Exception as ex:
        if log_fn:
            log_fn(f"Ön-bağlam analizi başarısız: {ex}", "warn")
        return None


def _detect_categories() -> list:
    """Otomatik tespitin seçebileceği kategoriler — şema listesinden türetilir.
    Yeni bir şema eklemek tespiti otomatik genişletir; ad uyumsuzluğu yaşanmaz."""
    return [v["name"] for v in CONTENT_SCHEMAS.values() if v["name"] != "Otomatik"]


def _match_category(detected: str, categories: list):
    """Modelin döndürdüğü tür adını kategori listesine eşler.
    Sıra: tam eşleşme → kategori adı cevabın içinde geçiyor (en uzun/spesifik
    kazanır) → cevap bir kategori adının parçası (en kısa kazanır, örn.
    'Komedi' → 'Komedi (Sitcom)'). Eşleşme yoksa None."""
    d = (detected or "").strip().lower()
    if not d:
        return None
    for cat in categories:
        if cat.lower() == d:
            return cat
    contains = [c for c in categories if c.lower() in d]
    if contains:
        return max(contains, key=len)
    contained = [c for c in categories if d in c.lower()]
    if contained:
        return min(contained, key=len)
    return None


def normalize_schema_name(name: str) -> str:
    raw = str(name or "").strip()
    if raw.lower() in {"auto", "automatic", "otomatik"}:
        return "Otomatik"
    for schema in CONTENT_SCHEMAS.values():
        if schema["name"].lower() == raw.lower():
            return schema["name"]
    return raw or "Otomatik"


def detect_content_type_with_ai(client, cues, model, log_fn=None, token_callback=None,
                                 filename: str = "") -> str:
    """Detects content type from sampled subtitle cues using the selected OpenAI model.
    Baş+orta+son örnekleme: tür sinyali her zaman ilk sahnede olmaz (örn. aksiyonla
    açılan romantik dram)."""
    sample_texts = []
    for c in cues:
        if hasattr(c, 'text'):
            txt = c.text.strip()
        else:
            txt = c[2].strip() if len(c) > 2 else ""
        if txt:
            sample_texts.append(txt)

    if not sample_texts:
        return "Otomatik"
    if len(sample_texts) > 180:
        mid = len(sample_texts) // 2
        sample_lines = (sample_texts[:80]
                        + sample_texts[mid:mid + 60]
                        + sample_texts[-40:])
    else:
        sample_lines = sample_texts
    sample = "\n".join(sample_lines)

    categories = _detect_categories()
    cat_list = "\n".join("- " + c for c in categories)
    hint = f" (from file: {Path(filename).stem})" if filename else ""
    system_msg = (
        "You are a media genre classification assistant with expertise in television, film, "
        "and online content. Given a subtitle sample, determine the single most fitting "
        "content type from the provided category list.\n\n"
        "Examples:\n"
        "- Sample with scripted dialogue, laugh track, multiple episodes → 'Komedi (Sitcom)'\n"
        "- Sample with presenter, hidden-camera reactions, challenge segments → 'Reality Show'\n"
        "- Sample with narrative voiceover, archival footage, historical events → 'Belgesel'\n"
        "- Sample with gameplay footage, player commentary, no scripted dialogue → 'Gaming'\n"
        "- Sample with scientific demonstration, expert presenter, studio setting → 'Akademik Anlatım'\n"
        "- Sample with formal interview, talking heads, news-style editing → 'Söyleşi / Podcast'\n\n"
        "Return ONLY a JSON object: {\"category\": \"exact category name\"}. Nothing else."
    )
    prompt = (
        "Analyze the following subtitle sample (beginning, middle and end of the file)"
        f"{hint} "
        "and classify its media genre/content type.\n"
        f"You MUST choose exactly one of these categories:\n{cat_list}\n\n"
        "Subtitle Sample:\n"
        f"{sample}\n\n"
        "Return ONLY a JSON object: {\"category\": \"exact category name as written above\"}. "
        "Nothing else."
    )

    def _call(prompt_text: str) -> tuple[str | None, bool]:
        try:
            from hybrid_translate import _safe_chat_create
            resp = _safe_chat_create(
                client,
                model=model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt_text}
                ],
                max_tokens=80,
                temperature=0.0,
                response_format={"type": "json_object"},
                timeout=45.0,
            )
            if token_callback and getattr(resp, "usage", None):
                tot, cached = _get_usage_details(resp.usage)
                try:
                    token_callback(tot, cached=cached)
                except TypeError:
                    token_callback(tot)
            content = (resp.choices[0].message.content or "").strip()
            try:
                data = json.loads(content)
                cat = data.get("category", "").strip()
                if cat:
                    return cat, True
            except Exception:
                pass
            # fallback: try plain-text match
            return _match_category(content, categories), content != ""
        except Exception as e:
            if log_fn:
                log_fn(f"İçerik türü tespit hatası: {e}", "warn")
            return None, False

    for attempt in range(2):
        result, ok = _call(prompt)
        if result:
            if log_fn:
                log_fn(f"İçerik Türü Analizi: '{result}' olarak tespit edildi.", "ok")
            return result
        if not ok:
            break
        # Retry: remind model about format
        if log_fn:
            log_fn("İçerik türü eşleşmedi, yeniden deneniyor...", "warn")
        prompt = (
            "The previous response could not be matched to any category.\n"
            f"Pick EXACTLY one from the list below. Return {{\"category\": \"...\"}}.\n"
            f"{cat_list}\n\n"
            f"Subtitle Sample:\n{sample[:800]}..."
        )

    if log_fn:
        log_fn("İçerik türü otomatik tespit edilemedi — Otomatik kullanılacak", "warn")
    return "Otomatik"

def _strip_md(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:]).rsplit("```", 1)[0].strip()
    return raw

def _extract_json_array(raw):
    """Extracts a JSON array from raw text, even with preamble/postamble."""
    raw = _strip_md(raw)
    if not raw.strip():
        return ""

    # Direct parse — most common case
    try:
        json.loads(raw)
        return raw
    except Exception:
        pass
    # Model added preamble like "Here is the JSON:" — find first [...]
    start = raw.find('[')
    end   = raw.rfind(']')
    if start != -1 and end > start:
        candidate = raw[start:end + 1]
        try:
            json.loads(candidate)
            return candidate
        except Exception:
            pass
    return ""  # Give up, return empty string to indicate failure

def _salvage_json_objects(raw) -> list:
    """Kesilmiş/bozuk bir JSON dizisinden TAM objeleri kurtarır (yarım kalan son
    obje atılır). API yanıtı token sınırında kelime ortasında kesildiğinde
    tamamlanmış çevirileri korur — yoksa _extract_json_array '' döndürüp TÜM chunk
    [HATA] olur ve başarıyla çevrilmiş satırlar da kaybolurdu (gözlemlenen veri kaybı)."""
    raw = _strip_md(raw)
    start = raw.find('[')
    if start == -1:
        return []
    dec = json.JSONDecoder()
    i, n, out = start + 1, len(raw), []
    while i < n:
        while i < n and raw[i] in ' \t\r\n,':
            i += 1
        if i >= n or raw[i] == ']':
            break
        if raw[i] != '{':
            break  # beklenmeyen içerik — dur
        try:
            obj, end = dec.raw_decode(raw, i)
        except Exception:
            break  # yarım/bozuk obje — kurtarmayı burada sonlandır
        if isinstance(obj, dict):
            out.append(obj)
        i = end
    return out


def parse_response(raw, chunk_info):
    raw_extracted = _extract_json_array(raw)
    try:
        items = json.loads(raw_extracted)
        if isinstance(items, list):
            trans_map = {}
            for item in items:
                if isinstance(item, dict) and "i" in item and "t" in item:
                    trans_map[str(item["i"])] = item["t"]
            # Every expected index present? If not, mark missing as [HATA]
            for (idx, *_rest) in chunk_info:
                trans_map.setdefault(str(idx), "[HATA]")
            return trans_map
        # Dict shape: {"tr":[...]} — model returned the full envelope
        if isinstance(items, dict) and isinstance(items.get("tr"), list):
            trans_map = {}
            for item in items["tr"]:
                if isinstance(item, dict) and "i" in item and "t" in item:
                    trans_map[str(item["i"])] = item["t"]
            for (idx, *_rest) in chunk_info:
                trans_map.setdefault(str(idx), "[HATA]")
            return trans_map
    except Exception:
        pass
    # Tam parse başarısız (çoğunlukla kesilmiş yanıt) — tamamlanan objeleri kurtar,
    # böylece çevrilen satırlar korunur; yalnızca kesilen kuyruk [HATA] kalır
    # (retry_hata / _fill_hata_with_source devralır).
    salvaged = _salvage_json_objects(raw)
    if salvaged:
        trans_map = {}
        for item in salvaged:
            if isinstance(item, dict) and "i" in item and "t" in item:
                trans_map[str(item["i"])] = item["t"]
        if trans_map:
            for (idx, *_rest) in chunk_info:
                trans_map.setdefault(str(idx), "[HATA]")
            return trans_map
    # Hiçbir şey kurtarılamadı — hepsini [HATA] (ham metni bloklara bölme, çok-satırlı
    # altyazıyı bozardı).
    return {str(info[0]): "[HATA]" for info in chunk_info}


def _missing_block_items(all_items: list, current_raw: str) -> list:
    """Chunk'ın tüm 'tr' öğeleri içinden, current_raw'da BAŞARIYLA çevrilmemiş
    (yanıtta hiç yok ya da [HATA]) olanları döner. Kesilmiş yanıtlarda salvage ile
    kurtarılan kısmi sonuçları da hesaba katar — böylece yalnızca gerçekten eksik
    bloklar yeniden istenir."""
    ok = set()
    try:
        parsed = json.loads(_extract_json_array(current_raw) or "[]")
    except Exception:
        parsed = []
    for it in (parsed if isinstance(parsed, list) else []):
        if isinstance(it, dict) and "i" in it and str(it.get("t", "")).strip() not in ("", "[HATA]"):
            ok.add(str(it["i"]))
    for it in _salvage_json_objects(current_raw):
        if isinstance(it, dict) and "i" in it and str(it.get("t", "")).strip() not in ("", "[HATA]"):
            ok.add(str(it["i"]))
    return [it for it in all_items if str(it.get("i")) not in ok]


def _repaired_json_ids(items) -> list:
    """items (JSON onarım yanıtı) içindeki geçerli 'i' alanlarını sırayla döner."""
    return [str(it["i"]) for it in items if isinstance(it, dict) and "i" in it]


def _validate_repaired_chunk(items, expected_ids: set, min_coverage: float = 0.5) -> bool:
    """_json_repair_pass'in ürettiği onarılmış JSON'u kabul etmeden önce yapısal
    olarak doğrular (bkz. plans/s04e14-json-repair-shift-brief.md — kaynağı görmeden
    yapılan onarım id-kaymasına yol açabiliyor). Onarım isteğinde kaynak metin
    YOK; bu yüzden içerik değil yalnızca id kümesinin tutarlılığı kontrol edilir:
      - id'ler benzersiz olmalı (tekrar = modelin sayıyı şaşırdığının işareti)
      - id'ler expected_ids'in bir ALT KÜMESİ olmalı (yabancı/uydurma id yoksa)
      - kapsam oranı çok düşük olmamalı (tamamen anlamsız/boş onarımları ele)
    expected_ids boşsa (id çıkarılamadıysa) doğrulama YAPILAMAZ — güvenli tarafta
    kalınır (False); çağıran tam yeniden çeviriye düşer."""
    if not expected_ids:
        return False
    ids = _repaired_json_ids(items)
    if not ids:
        return False
    if len(ids) != len(set(ids)):
        return False
    if not (set(ids) <= expected_ids):
        return False
    if len(ids) < max(1, len(expected_ids) * min_coverage):
        return False
    return True


def _expected_ids_from_req(req) -> set:
    """Bir isteğin payload'ındaki 'tr' listesinden beklenen id kümesini çıkarır
    (App._chunk_src_hash'in aynı JSON yapısını okuma deseniyle aynı)."""
    try:
        pl = json.loads(req["body"]["messages"][1]["content"])
        return {str(it.get("i")) for it in pl.get("tr", [])
                if isinstance(it, dict) and "i" in it}
    except Exception:
        return set()


def collect_results(raw_map, file_map, log_fn=None):
    file_blocks = {}
    for cid, raw in raw_map.items():
        info      = file_map.get(cid, [])
        if not info:
            # cid raw_map'te var ama file_map'te yok (fmap uyuşmazlığı) → sessizce
            # düşmek yerine uyar (aksi halde o chunk'ın çevirisi kaybolur, fark edilmez)
            if log_fn:
                log_fn(f"[UYARI] {cid}: file_map eşleşmesi yok — chunk atlandı", "warn")
            continue
        trans_map = parse_response(raw, info)
        for (orig_idx, ts, fp) in info:
            text = trans_map.get(str(orig_idx), "[HATA]")
            file_blocks.setdefault(fp, {})[orig_idx] = (str(orig_idx), ts, text)
    # raw_map'e girmeyen chunk'lar (retry'da da başarısız olanlar) için [HATA] yaz
    for cid, info in file_map.items():
        if cid not in raw_map:
            for (orig_idx, ts, fp) in info:
                # setdefault: zaten başka bir yoldan dolmuşsa dokunma
                file_blocks.setdefault(fp, {}).setdefault(
                    orig_idx, (str(orig_idx), ts, "[HATA]"))
    return file_blocks


def _slice_file_map(file_map: dict, requests: list) -> dict:
    ids = {req.get("custom_id") for req in requests or []}
    return {cid: info for cid, info in (file_map or {}).items() if cid in ids}


def _regular_batch_groups_ready(groups: dict, recovery_safe: bool = True) -> bool:
    return bool(recovery_safe and groups and all(
        group.get("terminal")
        and set(group.get("seen") or ()) == set(range(int(group.get("expected", 0))))
        for group in groups.values()
    ))


_ALIGN_SDH_ONLY_RE = re.compile(r'^(?:\([^)]*\)|\[[^\]]*\]|[♪*_\s]+)+$')
_ALIGN_NUMBER_RE = re.compile(r'\d{2,}')
# Özel-isim anchor'ı: Baş harf büyük + ardından ≥3 küçük harf (Ptahshepses, Abusir, Giza).
# ALL-CAPS konuşmacı etiketleri (NARRATOR) eşleşmez (ikinci harf büyük). src(İngilizce) ∩
# tr(Türkçe) kesişimi ortak sözcükleri (But≠Ama) doğal eler → geriye özel isim + sayı kalır.
_ALIGN_PROPER_RE = re.compile(r'[A-ZÇĞİÖŞÜ][a-zçğıöşü]{3,}')


def _align_visible(text) -> str:
    return re.sub(r'\s+', ' ', str(text or '')).strip()


def _align_ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def _align_lcs_len(a: str, b: str) -> int:
    """En uzun bitişik ortak alt-dizi uzunluğu (kaynak-tekrarı guard'ı için)."""
    if not a or not b:
        return 0
    return difflib.SequenceMatcher(None, a, b).find_longest_match(0, len(a), 0, len(b)).size


_DUP_WIN, _DUP_TR, _DUP_SRC, _DUP_LCS = 8, 0.75, 0.60, 15


def _find_adjacent_duplicate_ids(seq: list, src_map: dict,
                                  window: int = _DUP_WIN, tr_thresh: float = _DUP_TR,
                                  src_thresh: float = _DUP_SRC, lcs_thresh: int = _DUP_LCS) -> list:
    """seq: [(id_str, visible_tr_text), ...]. Komşu (±window) çeviri çiftlerinden
    TR-benzerliği yüksek AMA kaynak-benzerliği düşük olanların id'lerini döner —
    içerik 'öne kaymış' ve yeniden hizalanırken tekrarlanmış izi (redistribution-
    desync). Guard: kaynak da benziyorsa (refrain) ya da uzun ortak ifade
    paylaşıyorsa ('within sight of Gobekli Tepe' gibi) döndürmez (yanlış-pozitif
    önler). Hem tam-dosya taraması (detect_alignment_issues) hem chunk-içi
    onarım tetikleyicisi (_retry_hata) TEK bu fonksiyonu paylaşır."""
    dup_ids = []
    for a in range(len(seq)):
        ta = seq[a][1]
        if len(ta) < 12:
            continue
        for b in range(a + 1, min(a + 1 + window, len(seq))):
            tb = seq[b][1]
            if len(tb) < 12:
                continue
            if _align_ratio(ta.lower(), tb.lower()) < tr_thresh:
                continue
            sa = _align_visible(src_map.get(seq[a][0], "")).lower()
            sb = _align_visible(src_map.get(seq[b][0], "")).lower()
            if sa and sb and _align_ratio(sa, sb) >= src_thresh:
                continue  # kaynak da tekrar → meşru
            if _align_lcs_len(sa, sb) >= lcs_thresh:
                continue  # kaynaklar uzun ortak ifade paylaşıyor → meşru
            dup_ids.append(seq[a][0])
            dup_ids.append(seq[b][0])
    return dup_ids


def _content_shift_regions(seq: list, src_map: dict, window: int = 6,
                            min_offset: int = 2, min_run: int = 4) -> list:
    """seq: [(id_str, visible_tr), ...]. Kaynağa göre SÜREKLİ içerik-ötelemesi (id↔içerik
    kayması) olan cue bölgelerinin id'lerini döner. number_shift/adjacent_duplicate'in
    GÖREMEDİĞİ sınıf: 'akıcı ama N cue kaymış' gövde (Sun Kings mini #480-510'un 26-cue'luk
    saf-kayma kısmı bu yüzden sessizdi — yalnız duplikasyon kuyruğu yakalanmıştı).

    Yöntem (sözlük/API yok): kaynak(İngilizce) ve çeviri(Türkçe)'de ORTAK kalan tek
    anchor'lar = sayılar + özel isimler (Ptahshepses/Niuserre/Giza…). Her çeviri cue'sunu
    aynı anchor'ı içeren EN YAKIN kaynak cue'suyla eşleştir → offset = src_pos - tr_pos.
    Temiz/SOV dosyada offset ~0 (±1) salınır; gerçek kaymada bir pencere boyunca sabit
    |offset|>=min_offset (aynı işaret) görünür. min_run ardışık-anchor'lı-cue şartı izole
    eşleşmeyi/±1 SOV'u eler (yanlış-pozitif önler)."""
    def _anchors(text) -> set:
        t = str(text or "")
        props = {m.casefold() for m in _ALIGN_PROPER_RE.findall(t)}
        return set(_ALIGN_NUMBER_RE.findall(t)) | props

    n = len(seq)
    src_anchors = [_anchors(src_map.get(seq[p][0], "")) for p in range(n)]
    tr_anchors = [_anchors(seq[p][1]) for p in range(n)]

    offsets = {}  # tr_pos -> signed offset (yalnız anchor eşleşen cue'lar)
    for i in range(n):
        if not tr_anchors[i]:
            continue
        best = None
        for j in range(max(0, i - window), min(n, i + window + 1)):
            if tr_anchors[i] & src_anchors[j]:
                if best is None or abs(j - i) < abs(best - i):
                    best = j
        if best is not None:
            offsets[i] = best - i

    flagged = set()
    run = []  # aynı-işaret, güçlü offset'li ardışık anchor pozisyonları
    for p in sorted(offsets):
        o = offsets[p]
        strong = abs(o) >= min_offset
        if strong and (not run or (o > 0) == (offsets[run[-1]] > 0)):
            run.append(p)
        else:
            if len(run) >= min_run:
                flagged.update(range(run[0], run[-1] + 1))
            run = [p] if strong else []
    if len(run) >= min_run:
        flagged.update(range(run[0], run[-1] + 1))

    return sorted({seq[p][0] for p in flagged},
                  key=lambda i: (0, int(i)) if str(i).isdigit() else (1, str(i)))


def _align_is_sfx_only(text: str) -> bool:
    """Kaynak satır yalnızca ses efekti / müzik etiketi mi ([...], (...), ♪).
    SDH temizliğiyle SİLİNMESİ meşru olan cue'ları, gerçek diyalogdan ayırır."""
    t = _align_visible(text)
    t = re.sub(r'^(?:(?:&gt;|>){1,2})\s*', '', t)
    return bool(t) and bool(_ALIGN_SDH_ONLY_RE.match(t))


def _align_is_empty_tr(tr: str) -> bool:
    t = _align_visible(tr)
    return (not t) or t.startswith("[HATA") or t == "[ÇEVİRİ EKSİK]"


def _fmt_align_ranges(ids: list) -> str:
    """[362, 368, 369, 400] -> '#362, #368-369, #400' (gap<=3 aynı aralık)."""
    nums = sorted({int(i) for i in ids if str(i).isdigit()})
    if not nums:
        return ", ".join(f"#{i}" for i in ids[:8])
    ranges, s, p = [], nums[0], nums[0]
    for n in nums[1:]:
        if n - p <= 3:
            p = n
        else:
            ranges.append((s, p)); s = p = n
    ranges.append((s, p))
    return ", ".join(f"#{a}" if a == b else f"#{a}-{b}" for a, b in ranges)


def detect_alignment_issues(blocks: list, src_map: dict, window: int = 6) -> list:
    """Deterministik cue-hizalama taraması (API yok, eşik-tabanlı ama dar).

    id<->içerik kaymasını (S04E12/14/15'te doğrulandı) DÖRT bağımsız ucuz sinyalle
    yakalar — her biri hatanın farklı tezahürünü kapsar:
      • number_shift  : kaynaktaki 2+ basamaklı sayı KENDİ cue çevirisinde yok ama
                        komşu (±2) cue çevirisinde VAR (temiz frame-shift'in izi;
                        S04E14 '$150' bir cue kaymıştı).
      • missing_dialogue : SFX-only OLMAYAN gerçek diyalog cue'su çıktıda hiç yok
                        ya da çevirisi tamamen boş (S04E15'teki SESSİZ veri kaybı —
                        SDH temizliğiyle karışıp silinen gerçek replikler).
      • outlier_cluster : bir pencerede hem çok-kısa (<0.4x) hem çok-uzun (>2.5x)
                        uzunluk oranı BİR ARADA, ya da 3+ aykırı (içerik komşu
                        cue'ya 'akmış' izi; S04E12'de #487-518 böyleydi).
      • adjacent_duplicate : bir cue çevirisi yakın (±8) başka bir cue çevirisine
                        neredeyse aynı AMA kaynakları benzemiyor (içerik öne kayıp
                        yeniden hizalanırken tekrarlanmış — number/length/missing
                        sinyallerinin GÖREMEDİĞİ sınıf; Explorer 1 & 2'de doğrulandı).

    Tek başına izole bir aykırılık TETİKLEMEZ (temiz bölümlerde yanlış alarmı önler)
    — küme/komşu-kanıtı ister. Döner: [{"type", "idx"|"ids", "detail"}] listesi."""
    seq = [(str(idx), _align_visible(tr)) for (idx, _ts, tr) in blocks]
    present_ids = {i for i, _ in seq}
    findings = []

    def _key(i):
        try:
            return (0, int(i))
        except Exception:
            return (1, str(i))

    def _same_continuous_sentence(pa: int, pb: int) -> bool:
        """seq[pa]..seq[pb] kaynak cue'ları TEK sürekli cümle mi (aradaki hiçbiri
        cümle sonu noktalamasıyla bitmiyor). Öyleyse sayının komşu cue'ya kayması
        Türkçe söz dizimi (SOV) yeniden dağıtımıdır — KAYMA DEĞİL, meşru."""
        lo, hi = sorted((pa, pb))
        for p in range(lo, hi):
            if _ends_sentence_gui(src_map.get(seq[p][0], "")):
                return False
        return True

    # 1) number_shift — sayı, kendi cümlesi DIŞINDAKİ bir komşu cue'ya kaymışsa
    for pos, (idx, tr) in enumerate(seq):
        src_nums = set(_ALIGN_NUMBER_RE.findall(src_map.get(idx, "")))
        if not src_nums or (src_nums & set(_ALIGN_NUMBER_RE.findall(tr))):
            continue
        displaced = set()
        for d in (-2, -1, 1, 2):
            j = pos + d
            if 0 <= j < len(seq) and not _same_continuous_sentence(pos, j):
                neighbor_tr_nums = set(_ALIGN_NUMBER_RE.findall(seq[j][1]))
                neighbor_sentence_nums = set()
                for k in range(max(0, j - window), min(len(seq), j + window + 1)):
                    if _same_continuous_sentence(j, k):
                        neighbor_sentence_nums |= set(_ALIGN_NUMBER_RE.findall(
                            src_map.get(seq[k][0], "")))
                displaced |= (src_nums & neighbor_tr_nums) - neighbor_sentence_nums
        if displaced:
            findings.append({"type": "number_shift", "idx": idx,
                             "detail": sorted(displaced)})

    # 2) missing_dialogue — gerçek replik çıktıda yok / boş (sessiz kayıp)
    for idx in sorted(src_map, key=_key):
        src = src_map.get(idx, "")
        if _align_is_sfx_only(src) or len(_align_visible(src)) < 3:
            continue  # SFX-only silme meşru; çok kısa artık gürültü
        if idx not in present_ids:
            findings.append({"type": "missing_dialogue", "idx": idx,
                             "detail": _align_visible(src)[:60]})
    for idx, tr in seq:  # çıktıda var ama tamamen boş (görünür [ÇEVİRİ EKSİK] değil)
        src = src_map.get(idx, "")
        if _align_is_sfx_only(src) or len(_align_visible(src)) < 3:
            continue
        if _align_visible(tr) == "":
            findings.append({"type": "missing_dialogue", "idx": idx,
                             "detail": _align_visible(src)[:60]})

    # 3) outlier_cluster — kısa+uzun aykırılıkların yakınlaşması.
    # Hafif oranlar (0.25-1.9) normal cümle dağıtımında sürekli oluşur; yalnızca
    # pencerede EN AZ BİR AŞIRI (boş cue, <0.15 veya >4.0 — gerçek içerik kaybı/
    # şişmesi izi) varsa tetikle. Aksi hâlde çok-cue'lu cümle yeniden dağıtımını
    # kaymayla karıştırırız (S04E07 gibi meşru bölümlerde yanlış alarm).
    marks = []  # (pos, 'low'|'high', is_extreme)
    for pos, (idx, tr) in enumerate(seq):
        src = src_map.get(idx, "")
        if len(src) < 8:
            continue
        core = 0 if _align_is_empty_tr(tr) else len(tr)
        ratio = core / len(src)
        if ratio < 0.4:
            marks.append((pos, "low", ratio < 0.15))
        elif ratio > 2.5:
            marks.append((pos, "high", ratio > 4.0))
    flagged_pos = set()
    for a in range(len(marks)):
        win = [m for m in marks if abs(m[0] - marks[a][0]) <= window]
        kinds = {m[1] for m in win}
        has_extreme = any(m[2] for m in win)
        if has_extreme and (("low" in kinds and "high" in kinds) or len(win) >= 3):
            flagged_pos.update(m[0] for m in win)
    remaining_pos = set(flagged_pos)
    for p in sorted(flagged_pos):
        same_sentence = {q for q in flagged_pos if _same_continuous_sentence(p, q)}
        if len(same_sentence) < 2:
            continue
        lo, hi = min(same_sentence), max(same_sentence)
        joined_src = " ".join(src_map.get(seq[q][0], "") for q in range(lo, hi + 1))
        joined_tr = " ".join(seq[q][1] for q in range(lo, hi + 1))
        joined_ratio = len(joined_tr) / max(1, len(joined_src))
        if 0.4 <= joined_ratio <= 2.5:
            remaining_pos.difference_update(same_sentence)
    flagged_pos = remaining_pos
    if flagged_pos:
        ids = sorted({seq[p][0] for p in flagged_pos}, key=_key)
        findings.append({"type": "outlier_cluster", "ids": ids,
                         "detail": f"{len(flagged_pos)} aykırı uzunluk oranı yakın"})

    # 4) adjacent_duplicate — bir cue çevirisi yakın (±win) başka bir cue çevirisine ÇOK
    # benziyor AMA kaynakları benzemiyorsa: içerik 'öne kaymış' ve yeniden hizalanırken
    # tekrarlanmış (redistribution-desync imzası). number/length/missing sinyallerinin
    # GÖREMEDİĞİ sınıf — Explorer 1'in 6 bölgesi + Göbekli 2'nin 3-4 bölgesi bu yüzden
    # sessizceydi. Aynı mantık _retry_hata'da chunk-içi onarım tetikleyicisi olarak
    # da paylaşılıyor (bkz. _find_adjacent_duplicate_ids).
    dup_ids = _find_adjacent_duplicate_ids(seq, src_map)
    if dup_ids:
        ids = sorted(set(dup_ids), key=_key)
        findings.append({"type": "adjacent_duplicate", "ids": ids,
                         "detail": f"{len(ids)} cue komşusuyla neredeyse aynı (içerik kayması/tekrar)"})

    # 5) content_shift — sayı+özel-isim anchor'larıyla, kaynağa göre SÜREKLİ içerik
    # ötelemesi olan bölge (akıcı-ama-kaymış gövde; adjacent_duplicate yalnız kuyruğu görür).
    shift_ids = _content_shift_regions(seq, src_map, window=window)
    if shift_ids:
        findings.append({"type": "content_shift", "ids": shift_ids,
                         "detail": f"{len(shift_ids)} cue kaynağa göre sürekli kaymış (id↔içerik ötelemesi)"})

    return findings


_MIXED_TERM_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

# ">>COLLINS:" / ">>NOORY:" gibi konuşmacı etiketlerini token'lamadan ÖNCE satırdan
# sil — aksi hâlde konuşmacı adı yanlışlıkla 'özel-isim adayı' sayılıp gerçek
# terimin (ör. Gobekli) karşılığını gölgeliyor (cand_words[0] yanlış seçilir).
_MIXED_TERM_SPEAKER_RE = re.compile(r'^\s*>{1,2}\s*[A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ\s]*:\s*', re.MULTILINE)


def _mixed_term_strip_speaker(text: str) -> str:
    return _MIXED_TERM_SPEAKER_RE.sub('', text)


# Çeviri-tarafı "aday özel-isim" toplarken cümle-başı bağlaç/zarfları elemek için
# — mevcut _CONTENT_DRIFT_STOPS ile TEK stop-word listesi paylaşılır (bakım kolaylığı).
_MIXED_TERM_EXTRA_STOPS = frozenset({
    "sonunda", "böylece", "boylece", "ayrıca", "ayrica", "çünkü", "cunku",
    "üstelik", "ustelik", "peki", "acaba", "işte", "iste", "yine",
    "belki", "burada", "bunu", "buna", "bunun", "bundan", "orada", "ondan",
    # English source function words: all-caps captions make these look like
    # proper-noun candidates, but they are not stable terms.
    "this", "that", "these", "those", "there", "where", "when", "what", "which",
    "with", "from", "into", "onto", "over", "under", "your", "their", "ours",
    "have", "has", "had", "want", "take", "look", "like", "sure", "think",
    "looks", "looking", "really", "actually", "little", "very", "just", "only",
    "more", "most",
    # Apostrophe-split contractions in all-caps captions (HAVEN'T -> HAVEN).
    "haven", "didn", "doesn", "don", "isn", "aren", "wasn", "weren",
    "couldn", "wouldn", "shouldn", "won", "cant",
})


def _mixed_term_clusters(blocks: list, src_map: dict) -> dict:
    """detect_mixed_term_renderings ve _mixed_term_autofix_plan'ın PAYLAŞTIĞI iç
    kümeleme motoru. detect_mixed_term_renderings'teki algoritmayla BİREBİR aynı
    (bkz. o fonksiyonun docstring'i) — tek fark: her kümede yalnızca token değil,
    (idx, token) çiftleri tutulur, böylece autofix planlayıcı HANGİ cue'nun
    düzeltileceğini bilir. Döner: {terim: [[(idx, token), ...], ...]} (küme listesi,
    her kümenin ilk elemanı = o kümenin İLK bulunduğu occurrence — geriye dönük
    uyumluluk için temsilci biçim budur)."""
    try:
        import hybrid_translate as ht
    except Exception:
        return {}

    seq = {str(idx): _mixed_term_strip_speaker(_align_visible(tr)) for (idx, _ts, tr) in blocks}
    ordered_ids = sorted(seq.keys(), key=lambda i: int(i) if i.isdigit() else 0)
    pos_of = {i: p for p, i in enumerate(ordered_ids)}

    def _is_stop(w: str) -> bool:
        wl = w.lower()
        return wl in ht._CONTENT_DRIFT_STOPS or wl in _MIXED_TERM_EXTRA_STOPS

    def _line_is_all_caps(text: str) -> bool:
        letters = [ch for ch in text if ch.isalpha()]
        return bool(letters) and all(ch.isupper() for ch in letters)

    _SENTENCE_BOUNDARY_CHARS = ".!?…\"'-–—:"

    def _is_sentence_initial(text: str, pos: int) -> bool:
        """pos'taki kelime kendi CÜMLESİNİN/replik başındaki ilk kelime mi?
        Gerçek olay (Indiana Jones belgeseli, 2026-07-20): 'Undskyld' (Danca
        'pardon' - tekrar eden bir espri) çoğu cue'da SADECE ham kelime-listesi
        pozisyonuna göre (wi>0) mid-sentence sayılıyordu -- oysa cue içindeki
        İKİNCİ cümlenin ('Kom nu, Harry. Undskyld mig.' -> 'Undskyld' ikinci
        cümlenin ilk kelimesi) BAŞI, önceki kelime konumu >0 olsa bile aslında
        cümle/replik-başı. Ham konum yerine gerçek noktalama sınırına bakar."""
        j = pos - 1
        while j >= 0 and text[j] in " \t\n\r":
            j -= 1
        if j < 0:
            return True
        return text[j] in _SENTENCE_BOUNDARY_CHARS

    total_count: dict = {}
    mid_sentence: dict = {}
    occurrences: dict = {}
    lowercase_seen: set = set()
    phrase_adjacent_count: dict = {}
    for idx in ordered_ids:
        src_text = _mixed_term_strip_speaker(src_map.get(idx, ""))
        if not src_text:
            continue
        # Gerçek olay (Oddities S05E06, 2026-07-20): kaynağın %99'u ALL-CAPS
        # closed-caption stiliydi ("YEAH", "RIGHT", "GOOD" gibi 27 sıradan
        # kelime "hep büyük harf, hiç küçük harf görülmedi" diye özel-isim
        # sanılıp bulguya girdi). ALL-CAPS bir satırda büyük/küçük harf hiçbir
        # şey söylemez -- bu satırlardaki kelimeler total_count/occurrences'a
        # HİÇ girmez, dolayısıyla asla aday olamaz. Gerçek özel isimler zaten
        # en az bir normal-case satırda da geçtiği için işaretlenmeye devam eder.
        if _line_is_all_caps(src_text):
            continue
        matches = list(_MIXED_TERM_WORD_RE.finditer(src_text))
        words = [m.group(0) for m in matches]
        seen_in_this_cue: set = set()
        for wi, w in enumerate(words):
            if w[0].islower():
                lowercase_seen.add(w.lower())
            if len(w) < 4 or not w[0].isupper() or _is_stop(w):
                continue
            total_count[w] = total_count.get(w, 0) + 1
            # Gerçek olay (Massacre in Rome, 2026-07-20): kaynak cue'da terim
            # AYNI CUE İÇİNDE iki kez geçince ("Radio Rome. ... Rome One
            # station.") occurrences aynı idx'i iki kez sayıyor, bu da tek bir
            # yanlış-eşleşmenin kendi kendini "2 örnekli küme" diye onaylamasına
            # yol açıyordu ("Burası"). Bir cue, bir terim için en fazla BİR
            # occurrence'a sayılır -- tekrar sayım gerçek tutarlılık sinyali
            # değil, gürültü.
            if w not in seen_in_this_cue:
                occurrences.setdefault(w, []).append(idx)
                seen_in_this_cue.add(w)
            if not _is_sentence_initial(src_text, matches[wi].start()):
                mid_sentence[w] = True
            # Gerçek olay (aynı dosya): "Command" hep "German High Command"/
            # "High Command" içinde, bitişik başka bir büyük-harfli adayla
            # ("High") birlikte geçiyordu -- hedefte "Komutanlığı" hiç ilk
            # sırada olmadığı için asla kendi kümesini kuramıyor, bunun yerine
            # yanındaki sıfatlar ("Alman"/"Yüksek") rastgele küme oluşturuyordu.
            # Bitişik-büyük-harfli-komşu oranı YÜKSEKSE bu kelime muhtemelen
            # çok-kelimeli bir unvanın PARÇASI, tek başına izlenebilir bir özel
            # isim değil.
            has_capital_neighbor = False
            for ni in (wi - 1, wi + 1):
                if 0 <= ni < len(words):
                    nw = words[ni]
                    if len(nw) >= 4 and nw[0].isupper() and not _is_stop(nw) and nw.lower() != w.lower():
                        has_capital_neighbor = True
                        break
            if has_capital_neighbor:
                phrase_adjacent_count[w] = phrase_adjacent_count.get(w, 0) + 1

    # Sadece HER ZAMAN büyük-harfle geçen kelimeler aday — kaynakta küçük-harfli
    # biçimi de görülmüşse (ör. 'well'/'they'/'what') bu sıradan bir İngilizce
    # kelimedir (cümle-başı/üslup kaynaklı büyük yazım), gerçek özel isim değil.
    # phrase_adjacent_count[w] çoğunluğu geçerse (ör. "Command" hep "High"
    # bitişiğinde) bu kelime muhtemelen çok-kelimeli bir unvanın parçasıdır,
    # aday listesinden çıkarılır.
    candidates = [w for w, n in total_count.items()
                 if n >= 3 and mid_sentence.get(w) and w.lower() not in lowercase_seen
                 and phrase_adjacent_count.get(w, 0) * 2 <= n]
    if not candidates:
        return {}

    result: dict = {}
    for term in candidates:
        clusters = []  # her eleman: [(idx, token), ...] — aynı gövdeye düşen occurrence'lar
        for idx in occurrences[term]:
            p = pos_of.get(idx)
            if p is None:
                continue
            candidate_ids = [idx]
            if p > 0:
                candidate_ids.append(ordered_ids[p - 1])
            if p + 1 < len(ordered_ids):
                candidate_ids.append(ordered_ids[p + 1])
            found_token = None
            found_idx = None
            for cid in candidate_ids:
                tr_text = seq.get(cid, "")
                if not tr_text:
                    continue
                cand_words = [w for w in _MIXED_TERM_WORD_RE.findall(tr_text)
                             if len(w) >= 4 and w[0].isupper() and not _is_stop(w)]
                if not cand_words:
                    continue
                exact = next((w for w in cand_words if w.lower() == term.lower()), None)
                if exact:
                    found_token, found_idx = exact, cid
                    break
                # o cue'da BİRDEN FAZLA özel-isim adayı olabilir (ör. hem 'Plato'
                # hem alakasız 'Sfenks') — MEVCUT bir kümeye ait olanı tercih et,
                # rastgele ilkini değil (yanlış-eşleştirme riskini azaltır).
                # Gerçek olay (Massacre in Rome, 2026-07-20): cümle sırasında
                # önce gelen bir söylem-sözcüğü ("Demek") küçük/yanlış bir
                # kümeyle eşleşince, aynı cümlede SONRA gelen doğru aday
                # ("Roma", devasa ve doğru bir kümeyle eşleşecekken) hiç
                # denenmiyordu -- ilk-eşleşen-kazanır sırası cümle pozisyonuna
                # göre değil, EN BÜYÜK/en yerleşik kümeye göre karar vermeli.
                matched = None
                matched_size = -1
                for w in cand_words:
                    for cluster in clusters:
                        if ht._share_stem(w, cluster[0][1]):
                            if len(cluster) > matched_size:
                                matched = w
                                matched_size = len(cluster)
                            break
                found_token, found_idx = (matched or cand_words[0]), cid
                break
            if not found_token:
                continue
            placed = False
            for cluster in clusters:
                if ht._share_stem(found_token, cluster[0][1]):
                    cluster.append((found_idx, found_token))
                    placed = True
                    break
            if not placed:
                clusters.append([(found_idx, found_token)])
        result[term] = clusters
    return result


def detect_mixed_term_renderings(blocks: list, src_map: dict) -> list:
    """Kaynakta tekrarlanan özel-isim adaylarının (ör. Incas, Ouija, Boy King)
    dosya içinde TUTARSIZ çevrildiğini (İnka* vs Incas*) tespit eder — helper-model
    consistency sweep'in AYNI-MODEL kör noktasına deterministik bir protez.

    Otomatik düzeltme burada YAPILMAZ, yalnızca raporlar. Güvenli-olduğu kanıtlanan
    alt-küme (kaynakla birebir aynı 'sızıntı' biçimi) için otomatik düzeltme
    _mixed_term_autofix_plan + _normalize_mixed_terms içindedir (bkz. oradaki
    docstring — YALNIZCA çevrilmeden kalmış İngilizce biçimi hedefler, iki geçerli
    Türkçe yazım arasındaki üslup tercihine KARIŞMAZ).

    Yöntem/kümeleme algoritması: bkz. _mixed_term_clusters. ≥2 farklı küme VE her
    kümede ≥2 örnek varsa bulgu. Döner: [{"term", "renderings": {gövde*: sayı, ...}}]."""
    clusters_by_term = _mixed_term_clusters(blocks, src_map)
    findings = []
    for term, clusters in clusters_by_term.items():
        real_clusters = [c for c in clusters if len(c) >= 2]
        if len(real_clusters) >= 2:
            renderings = {f"{c[0][1]}*": len(c) for c in real_clusters}
            findings.append({"term": term, "renderings": renderings})
    return findings


def _mixed_term_autofix_plan(blocks: list, src_map: dict) -> dict:
    """Karışık-terim kümelerinden GÜVENLİ otomatik-düzeltme planı çıkarır.

    Yalnızca 'çevrilmeden kalmış İngilizce sızıntısı' durumunu hedefler: bir terim
    için TAM OLARAK 2 gerçek küme varsa VE kümelerden BİRİNİN temsilcisi kaynak
    terimle (case-insensitive) BİREBİR aynıysa (= büyük olasılıkla hiç çevrilmemiş),
    o küme 'yanlış' sayılır, diğeri 'doğru'. SAYICA ÇOĞUNLUK ASLA tek başına karar
    vermez — çoğunluk YANLIŞ olabilir (ör. bir terim yardımcı geçişlerde tekrar
    tekrar çevrilemeyip İngilizce kalırsa sayıca daha fazla bile olabilir; gerçek
    vaka: Strangest Things S02E03'te kaynak-eşleşen 'Troy' 14 kez, doğru 'Truva'
    yalnızca 3 kez geçmişti — çoğunluk mantığı bunu TERSİNE çevirirdi).

    2'den fazla küme VARSA, ya da HİÇBİR küme kaynakla birebir aynı DEĞİLSE (iki
    geçerli Türkçe yazım arasında üslup tercihi, ör. İliada/İlyada) — otomatik
    düzeltme YAPILMAZ; bu durumlar yalnızca detect_mixed_term_renderings ile
    raporlanmaya devam eder (insan kararı gerekir).

    Döner: {idx_str: [(yanlış_literal, doğru_literal), ...]}"""
    clusters_by_term = _mixed_term_clusters(blocks, src_map)
    plan: dict = {}
    for term, clusters in clusters_by_term.items():
        real_clusters = [c for c in clusters if len(c) >= 2]
        if len(real_clusters) != 2:
            continue
        term_l = term.lower()
        leak_i = next((i for i, c in enumerate(real_clusters) if c[0][1].lower() == term_l), None)
        if leak_i is None:
            continue
        other_i = 1 - leak_i
        if real_clusters[other_i][0][1].lower() == term_l:
            continue  # her iki küme de kaynakla aynı — belirsiz, atla
        wrong_literal = real_clusters[leak_i][0][1]
        correct_literal = real_clusters[other_i][0][1]
        for idx, _tok in real_clusters[leak_i]:
            plan.setdefault(idx, []).append((wrong_literal, correct_literal))
    return plan


def _validate_term_normalize_candidate(old: str, new: str, fixes: list) -> tuple:
    """Terim-normalizasyon adayı için hafif güvenlik kapısı.

    validate_polish_candidate'ın genel-amaçlı ağır guard'ları burada UYGUNSUZ —
    kasıtlı içerik-kelime değişimini (Troy->Truva) content_word_drift/loss sayıp
    reddederler. Bunun yerine dar-kapsamlı kontrol: satır/yeni-satır sayısı
    korunmalı; her (yanlış,doğru) çifti için YANLIŞ biçim (eki/kesme işaretiyle
    birlikte) satırdan tamamen kaybolmalı, DOĞRU biçim belirmeli; ve terim(ler) +
    ekleri DIŞINDAKİ metin HARFİYEN aynı kalmalı (aşırı yeniden-yazımı reddet —
    yalnızca ad+ek düzeltmesine izin verilir, cümlenin başka hiçbir yeri değişemez)."""
    if not new or not new.strip():
        return False, "empty"
    if old.count("\n") != new.count("\n"):
        return False, "linebreak_count"
    old_rest, new_rest = old, new
    for wrong, correct in fixes:
        pat_wrong = re.compile(r"\b" + re.escape(wrong) + r"(?:['’]\w+)?", re.IGNORECASE)
        pat_correct = re.compile(r"\b" + re.escape(correct) + r"(?:['’]\w+)?", re.IGNORECASE)
        if pat_wrong.search(new):
            return False, "term_not_replaced"
        if not pat_correct.search(new):
            return False, "term_missing_after_fix"
        old_rest = pat_wrong.sub("\0", old_rest)
        new_rest = pat_correct.sub("\0", new_rest)
    old_norm = re.sub(r"\s+", " ", old_rest).strip()
    new_norm = re.sub(r"\s+", " ", new_rest).strip()
    if old_norm != new_norm:
        return False, "unrelated_text_changed"
    return True, ""


def _normalize_mixed_terms(sorted_blocks: list, src_map: dict, helper_key: str, helper_url: str,
                           helper_model: str, log_fn=None) -> tuple:
    """_mixed_term_autofix_plan'ın GÜVENLİ bulduğu (yalnızca çevrilmeden-kalmış-
    İngilizce-sızıntısı sınıfı) karışık-terim örneklerini yardımcı modelle düzeltir.
    Riskli/belirsiz durumlar (bkz. plan fonksiyonunun docstring'i) dokunulmadan
    yalnızca detect_mixed_term_renderings ile raporlanmaya devam eder.

    Saf modül fonksiyonu — App'e bağlı değil, çağıran helper_key/url/model'i
    kendi rolünden (ör. 'polish') çözüp geçirir. Döner: (yeni_blocks, düzeltilen_sayısı)."""
    plan = _mixed_term_autofix_plan(sorted_blocks, src_map)
    if not plan:
        return sorted_blocks, 0

    by_idx_text = {str(idx): text for idx, _ts, text in sorted_blocks}
    items = []
    for idx, fixes in plan.items():
        text = by_idx_text.get(idx)
        if text is None or str(text).startswith("[HATA"):
            continue
        uniq_fixes = list(dict.fromkeys(fixes))
        items.append({"id": idx, "tr": text,
                     "fixes": [{"wrong": w, "correct": c} for w, c in uniq_fixes]})
    if not items or not helper_key:
        return sorted_blocks, 0

    try:
        from openai import OpenAI as _OAI
    except Exception:
        return sorted_blocks, 0
    client = _OAI(api_key=helper_key, base_url=helper_url)

    sys_prompt = (
        "Sen bir altyazı terim-tutarlılık editörüsün. Her satırda 'fixes' listesindeki "
        "her çift için: 'wrong' teriminin o satırdaki HER geçtiği yeri (varsa eki/kesme "
        "işaretiyle birlikte, ör. Troy'un) 'correct' terimin DOĞRU Türkçe ekiyle çekimlenmiş "
        "haline çevir (ör. Troy'un -> Truva'nın, Greece'ten -> Yunanistan'dan, Homer'a -> "
        "Homeros'a). BAŞKA HİÇBİR KELİMEYİ DEĞİŞTİRME, satır sayısını/\\n karakterlerini KORU. "
        "Emin değilsen satırı AYNEN döndür.\n"
        'Input: JSON {"items": [{"id": N, "tr": "...", "fixes": [{"wrong":"X","correct":"Y"}]}]}\n'
        'Output: JSON array [{"id": N, "tr": "düzeltilmiş"}] — aynı id\'ler, aynı sayıda.\n'
        "Return ONLY the JSON array. No explanation."
    )

    result_map = {}
    CHUNK = 60
    for cs in range(0, len(items), CHUNK):
        chunk = items[cs:cs + CHUNK]
        try:
            resp = _safe_chat_create(
                client, model=helper_model,
                messages=[{"role": "system", "content": sys_prompt},
                         {"role": "user", "content": json.dumps({"items": chunk}, ensure_ascii=False)}],
                max_tokens=max(800, len(chunk) * 100),
                temperature=0.2,
            )
            if not resp.choices:
                continue
            content = resp.choices[0].message.content or ""
            raw = _extract_json_array(content)
            if not raw.strip():
                continue
            data = json.loads(raw)
        except Exception:
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            rid = str(item.get("id", ""))
            new_text = item.get("tr")
            if rid in by_idx_text and new_text is not None:
                result_map[rid] = new_text

    fixes_by_idx = {it["id"]: [(f["wrong"], f["correct"]) for f in it["fixes"]] for it in items}
    fixed_count = 0
    rejected = 0
    rejected_reasons: dict = {}
    per_term_fixed: dict = {}
    new_blocks = []
    for idx, ts, text in sorted_blocks:
        sidx = str(idx)
        if sidx in result_map:
            candidate = result_map[sidx]
            ok, reason = _validate_term_normalize_candidate(text, candidate, fixes_by_idx[sidx])
            if ok:
                new_blocks.append((idx, ts, candidate))
                fixed_count += 1
                for w, c in fixes_by_idx[sidx]:
                    key = f"{w}->{c}"
                    per_term_fixed[key] = per_term_fixed.get(key, 0) + 1
                continue
            else:
                rejected += 1
                rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1
        new_blocks.append((idx, ts, text))

    if log_fn:
        if fixed_count:
            detail = ", ".join(f"{k}:{v}" for k, v in per_term_fixed.items())
            log_fn(f"✓ Terim normalizasyonu: {fixed_count} satır düzeltildi ({detail})", "ok")
        if rejected:
            detail = ", ".join(f"{k}:{v}" for k, v in rejected_reasons.items())
            log_fn(f"⚠ Terim normalizasyonu: {rejected} öneri güvenlik filtresinden döndü ({detail})", "warn")
    return new_blocks, fixed_count


def scan_translation_quality(fp: str, blocks: list, log_fn=None,
                             src_clean_map: dict = None) -> int:
    """Çeviri sonrası kalite taraması.
    - Kaynak ile aynı kalan satırları (çevrilmemiş) tespit eder
    - Anormal uzunluk oranı olanları (< 0.12 veya > 5.0) tespit eder
    Returns: toplam uyarı sayısı

    src_clean_map: {idx_str: etiketsiz kaynak metin} — verilirse dosya yeniden
    parse edilmez (çağıran zaten parse etmişse disk okumasını atlar)."""
    if src_clean_map is not None:
        orig = src_clean_map
    else:
        orig = {}
        try:
            for idx, ts, text in parse_subtitle(fp):
                clean = re.sub(r'</?[a-zA-Z][^>]*>', '', text).strip()
                orig[str(idx)] = clean
        except Exception:
            return 0

    # Common short loanwords that look "same" but are valid translations
    _LOANWORDS = frozenset([
        "ok", "yes", "no", "hi", "hey", "wow", "oh", "ah",
        "robot", "laser", "internet", "pizza", "taxi",
    ])
    warnings = 0
    untranslated = []
    ratio_issues = []

    for (idx, ts, tr_text) in blocks:
        if tr_text == "[HATA]":
            continue
        src_text = orig.get(str(idx), "")
        if not src_text or not tr_text:
            continue

        if _is_untranslated(src_text, tr_text):
            untranslated.append(str(idx))
            warnings += 1

        # Length ratio check
        if len(src_text) > 4:  # skip trivially short
            ratio = len(tr_text) / len(src_text)
            if ratio < 0.12 or ratio > 5.0:
                ratio_issues.append((str(idx), round(ratio, 2)))
                warnings += 1

    if log_fn:
        fname = Path(fp).name
        if untranslated:
            sample = ", ".join(untranslated[:5])
            more   = f" …+{len(untranslated)-5}" if len(untranslated) > 5 else ""
            log_fn(f"  ⚠ {fname}: {len(untranslated)} satır çevrilmemiş görünüyor "
                   f"(idx: {sample}{more})", "warn")
        if ratio_issues:
            sample = ", ".join(f"#{i}({r}x)" for i, r in ratio_issues[:4])
            more   = f" …+{len(ratio_issues)-4}" if len(ratio_issues) > 4 else ""
            log_fn(f"  ⚠ {fname}: {len(ratio_issues)} satırda anormal uzunluk oranı "
                   f"({sample}{more})", "warn")

    # Non-Latin script detection (Arabic, Tamil, Devanagari, Cyrillic, CJK, etc.)
    _NON_LATIN = re.compile(
        r'[\u0600-\u06FF'   # Arabic
        r'\u0900-\u097F'    # Devanagari
        r'\u0B80-\u0BFF'    # Tamil
        r'\u0400-\u04FF'    # Cyrillic
        r'\u4E00-\u9FFF'    # CJK
        r'\u3040-\u30FF'    # Hiragana/Katakana
        r'\uAC00-\uD7AF]'   # Hangul
    )
    script_issues = []
    for (idx, ts, tr_text) in blocks:
        if tr_text and tr_text != "[HATA]":
            try:
                import hybrid_translate as ht
                tr_text = ht.normalize_latin_homoglyphs(str(tr_text))
            except Exception:
                tr_text = str(tr_text)
        if tr_text and tr_text != "[HATA]" and _NON_LATIN.search(tr_text):
            script_issues.append(str(idx))
            warnings += 1
    if log_fn and script_issues:
        sample = ", ".join(script_issues[:5])
        more   = f" …+{len(script_issues)-5}" if len(script_issues) > 5 else ""
        log_fn(f"  🚨 {fname}: {len(script_issues)} satırda Türkçe dışı alfabe var "
               f"(Arabic/Tamil/Kiril vb.) — idx: {sample}{more}", "err")

    # Cue hizalama/kayma taraması (deterministik) — çeviri satırlarının yanlış cue'ya
    # kaymış olabileceği bölümleri işaretler (id<->içerik uyuşmazlığı). Ayrı tutulur
    # çünkü satırlar tek tek geçerli/akıcı olabilir; sorun BAĞLAM değil KONUMdur.
    try:
        align_findings = detect_alignment_issues(blocks, orig)
    except Exception:
        align_findings = []
    if align_findings:
        warnings += len(align_findings)
        if log_fn:
            fname = Path(fp).name
            all_ids = []
            for f in align_findings:
                if "idx" in f:
                    all_ids.append(f["idx"])
                else:
                    all_ids.extend(f.get("ids", []))
            types = sorted({f["type"] for f in align_findings})
            log_fn(f"  🚨 {fname}: OLASI CUE HİZALAMA/KAYMA SORUNU ({', '.join(types)}) "
                   f"— çeviri satırları yanlış cue'ya kaymış olabilir. Şu cue'ları "
                   f"kaynakla ELLE KARŞILAŞTIRIN: {_fmt_align_ranges(all_ids)}", "err")

    # Bozuk/yabancı token taraması (deterministik, run_validators'la aynı kurallar) —
    # critic API'ye gitmeyen sync akışında veya critic'in kaçırdığı satırlarda son
    # güvenlik ağı.
    try:
        import hybrid_translate as ht
        garble_lines = []
        _untranslated_ids = set(untranslated)
        for (idx, ts, tr_text) in blocks:
            if not tr_text or str(tr_text).startswith("[HATA"):
                continue
            if str(idx) in _untranslated_ids:
                continue  # zaten 'çevrilmemiş' işaretli — ayrıca token-token garble sayma
            hits = ht.find_garble_tokens(tr_text)
            if hits:
                garble_lines.append((str(idx), hits[0][0]))
                warnings += 1
    except Exception:
        garble_lines = []
    if log_fn and garble_lines:
        sample = ", ".join(f"#{i} '{tok}'" for i, tok in garble_lines[:5])
        more   = f" …+{len(garble_lines)-5}" if len(garble_lines) > 5 else ""
        log_fn(f"  ⚠ {fname}: {len(garble_lines)} satırda bozuk/yabancı token — "
               f"örn: {sample}{more}", "warn")

    # Karışık-terim raporu (deterministik) — aynı özel ismin dosya içinde farklı
    # biçimlerde çevrildiğini işaretler; helper-model consistency sweep'in
    # kaçırdığı aynı-model kör noktasına protez. Otomatik düzeltme YOK.
    try:
        mixed_terms = detect_mixed_term_renderings(blocks, orig)
    except Exception:
        mixed_terms = []
    if log_fn and mixed_terms:
        for mt in mixed_terms:
            renderings_str = " / ".join(f"{k}×{v}" for k, v in mt["renderings"].items())
            log_fn(f"  ⚠ {fname}: '{mt['term']}' dosya içinde karışık çevrilmiş "
                   f"({renderings_str}) — tutarlılık kontrolü önerilir", "warn")
        warnings += len(mixed_terms)

    return warnings


def summarize_file_outcomes(
    completed_files: list,
    failed_files: list = None,
    skipped_files: list = None,
    total_files: int = 0,
    stop_flag: bool = False
) -> dict:
    """Accurately calculates file completion status, failure counts, skipped counts,
    and determines whether full success or partial completion occurred."""
    nc = len(completed_files)
    nf = len(failed_files or [])
    nk = len(skipped_files or [])
    total = max(total_files, nc + nf + nk)
    pending = max(0, total - nc - nf - nk)

    is_full_success = (nc == total) and (nf == 0) and (nk == 0) and (nc > 0) and not stop_flag
    is_partial_success = (nc > 0) and not is_full_success and not stop_flag
    is_failure = (nc == 0) and (nf > 0 or pending > 0) and not stop_flag
    is_recovery_complete = (pending == 0) and (nf == 0) and not stop_flag

    details = []
    if nf > 0:
        details.append(f"{nf} hata")
    if nk > 0:
        details.append(f"{nk} atlandı/silindi")
    if pending > 0:
        details.append(f"{pending} bekliyor")

    det_str = f" ({', '.join(details)})" if details else ""

    if is_full_success:
        summary_text = f"{nc} dosya çevrildi"
        title_text = "Çeviri Tamamlandı ✓"
    elif is_partial_success:
        summary_text = f"{nc}/{total} dosya çevrildi{det_str}"
        title_text = "Çeviri Kısmen Tamamlandı ⚠️"
    elif stop_flag:
        summary_text = f"Durduruldu — {nc}/{total} dosya yazıldı{det_str}"
        title_text = "İşlem Durduruldu"
    elif nk == total and total > 0:
        summary_text = f"0/{total} dosya çevrildi{det_str}"
        title_text = "İşlem Tamamlandı"
    else:
        summary_text = f"Çeviri başarısız ({total} dosya işlenemedi){det_str}"
        title_text = "Çeviri Başarısız ❌"

    return {
        "completed_count": nc,
        "failed_count": nf,
        "skipped_count": nk,
        "pending_count": pending,
        "total_count": total,
        "is_full_success": is_full_success,
        "is_partial_success": is_partial_success,
        "is_failure": is_failure,
        "is_recovery_complete": is_recovery_complete,
        "summary_text": summary_text,
        "title_text": title_text,
    }

# ── UI Dispatcher & Thread Safety Helper ────────────────────────────────────
def _post_ui(self, fn, *args, **kwargs):
    """Worker thread'lerden veya ana thread'den UI callback'lerini güvenli şekilde kuyruğa ekler.
    Worker thread'deyse Tcl/Tk çağrısı YAPMAZ; sadece Python queue.Queue'ya koyar.
    """
    if getattr(self, "_is_shutting_down", False):
        return
    if threading.current_thread() is threading.main_thread():
        try:
            fn(*args, **kwargs)
        except Exception as e:
            print(f"[UI Dispatcher Direct Error] {fn}: {e}")
        return
    ui_q = getattr(self, "_ui_queue", None)
    if ui_q is not None:
        ui_q.put((fn, args, kwargs))

def _count_hata_cps(blocks) -> tuple:
    """(idx, ts, text) bloklarında eksik çeviri ve CPS aşımı sayısını döner."""
    hata = cps_n = 0
    for _idx, _ts, _txt in blocks:
        if str(_txt).startswith("[HATA") or str(_txt).strip() == "[ÇEVİRİ EKSİK]":
            hata += 1
            continue
        try:
            dur = max(_ts_end_sec_gui(_ts) - _ts_to_sec_gui(_ts), 0.1)
            if len(str(_txt).replace("\n", "")) / dur > CPS_WARN_LIMIT:
                cps_n += 1
        except Exception:
            pass
    return hata, cps_n


def _cps_stats(blocks) -> tuple:
    """(cps_avg, cps_max) — CPS dağılım istatistiklerini döndürür."""
    values = []
    for _idx, _ts, _txt in blocks:
        txt = str(_txt or "").replace("\n", "")
        if not txt or txt.startswith("[HATA"):
            continue
        try:
            dur = max(_ts_end_sec_gui(_ts) - _ts_to_sec_gui(_ts), 0.1)
            values.append(len(txt) / dur)
        except Exception:
            pass
    if not values:
        return 0.0, 0.0
    return round(sum(values) / len(values), 1), round(max(values), 1)


def _iter_text_changes(before_blocks, after_blocks):
    """Yield text changes by subtitle id, ignoring restored formatting tags."""
    before = {str(idx): _clean_src(text) for idx, _ts, text in (before_blocks or [])}
    for idx, _ts, text in (after_blocks or []):
        sid = str(idx)
        old = before.get(sid)
        new = _clean_src(text)
        if old is not None and old != new:
            yield sid, old, new


def _count_text_changes(before_blocks, after_blocks) -> int:
    """Count text changes by subtitle id, ignoring restored formatting tags."""
    return sum(1 for _ in _iter_text_changes(before_blocks, after_blocks))


def _record_pass_change(trace: dict, label: str, before_blocks, after_blocks,
                        history: dict = None) -> int:
    """Record how many lines a quality pass changed and return that count."""
    changes = list(_iter_text_changes(before_blocks, after_blocks))
    n = len(changes)
    if n:
        trace[label] = trace.get(label, 0) + n
        if history is not None:
            for sid, old, new in changes:
                history.setdefault(sid, []).append({
                    "pass": label,
                    "before": old,
                    "after": new,
                })
    return n


def _format_pass_trace(trace: dict) -> str:
    if not trace:
        return ""
    return ", ".join(f"{name}: {count}" for name, count in trace.items() if count)


def _multi_pass_history(history: dict, max_items: int = 5) -> tuple[int, str]:
    multi = [(sid, steps) for sid, steps in (history or {}).items() if len(steps) > 1]
    if not multi:
        return 0, ""
    samples = []
    for sid, steps in multi[:max_items]:
        chain = " -> ".join(str(step.get("pass", "?")) for step in steps)
        samples.append(f"#{sid}: {chain}")
    more = f" (+{len(multi) - max_items})" if len(multi) > max_items else ""
    return len(multi), "; ".join(samples) + more


def _is_refinement_change(before: str, after: str) -> bool:
    """Best-effort marker for small polish changes, not suspicious overrides."""
    if before == after:
        return False
    before_terminal = before.rstrip()[-1:] if before.rstrip() else ""
    after_terminal = after.rstrip()[-1:] if after.rstrip() else ""
    expressive_punct = {"?", "!"}
    terminal_punct = {".", "?", "!", "…"}
    if before_terminal and after_terminal and before_terminal != after_terminal:
        if before_terminal in terminal_punct and (
                before_terminal in expressive_punct or after_terminal in expressive_punct):
            return False
    compact_before = re.sub(r"[\s\W_]+", "", before, flags=re.UNICODE).casefold()
    compact_after = re.sub(r"[\s\W_]+", "", after, flags=re.UNICODE).casefold()
    if compact_before and compact_before == compact_after:
        return True
    if before and after.startswith(before) and len(after) <= max(len(before) + 3, int(len(before) * 1.15)):
        suffix = after[len(before):].strip()
        return bool(suffix) and all(ch in ".,;:!?…" for ch in suffix)
    return False


def _pass_interaction_events(history: dict) -> list:
    """Return adjacent pass interactions as (sid, prev_step, cur_step, kind)."""
    events = []
    for sid, steps in (history or {}).items():
        if len(steps) < 2:
            continue
        for i in range(1, len(steps)):
            prev = steps[i - 1]
            cur = steps[i]
            prev_before = str(prev.get("before", ""))
            prev_after = str(prev.get("after", ""))
            cur_after = str(cur.get("after", ""))
            if not prev_after or not cur_after or prev_after == cur_after:
                continue
            if cur_after == prev_before:
                kind = "revert"
            elif _is_refinement_change(prev_after, cur_after):
                kind = "refinement"
            else:
                kind = "override"
            events.append((sid, prev, cur, kind))
    return events


def _pass_interaction_counts(history: dict) -> dict:
    counts = {}
    for _sid, _prev, _cur, kind in _pass_interaction_events(history):
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _format_interaction_counts(counts: dict) -> str:
    order = ("override", "revert", "refinement")
    return ", ".join(f"{name}: {counts[name]}" for name in order if counts.get(name))


def _detect_pass_overrides(history: dict, max_items: int = 5) -> tuple[int, str]:
    """Summarize adjacent pass changes: refinement, override, or revert."""
    events = _pass_interaction_events(history)
    if not events:
        return 0, ""
    samples = []
    for sid, prev, cur, kind in events[:max_items]:
        chain = f"{prev.get('pass', '?')} -> {cur.get('pass', '?')}"
        samples.append(f"#{sid}: {chain} ({kind})")
    more = f" (+{len(events) - max_items})" if len(events) > max_items else ""
    return len(events), "; ".join(samples) + more


def build_quality_report_text(rows: list, model_name: str, tgt: str, mode: str,
                              total_tokens: int) -> str:
    """ceviri_raporu.txt içeriğini üretir. Satırlardaki alanlar opsiyoneldir —
    yalnızca mevcut olanlar yazılır (düz mod 'rev', hybrid 'pass_fix'/'qc' taşır)."""
    import datetime as _dt
    fields = [
        ("hata",     "Eksik çeviri satırı"),
        ("cps",      f"CPS aşımı (>{CPS_WARN_LIMIT} k/sn)"),
        ("cps_avg",  "Ortalama CPS"),
        ("cps_max",  "Maksimum CPS"),
        ("tm_hits",  "TM önbellek kullanımı"),
        ("cons",     "Tutarlılık düzeltmesi"),
        ("rev",      "İnceleme düzeltmesi"),
        ("pass_fix", "Kalite geçişi düzeltmesi"),
        ("qc_auto",  "QC otomatik düzeltmesi"),
        ("qc",       "QC düzeltmesi"),
        ("warn",     "Kalite uyarısı (tarama)"),
    ]
    price = MODEL_PRICE.get(model_name, 0.60)
    lines = [
        "ÇEVİRİ KALİTE RAPORU",
        f"Tarih  : {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Model  : {model_name}  |  Hedef dil: {tgt}  |  Mod: {mode}",
        "=" * 72,
    ]
    hata_files = [r.get("name", "?") for r in rows if r.get("hata_indices")]
    if hata_files:
        lines.insert(0, "")
        lines.insert(0, "!!! UYARI: [ÇEVİRİ EKSİK] kalan satırlar var - aşağıdaki dosyalarda indeks listesini kontrol edin!")
        lines.insert(0, "=" * 72)
    width = max(len(lbl) for _, lbl in fields)
    for r in rows:
        lines.append(f"\n• {r['name']}  ({r.get('total', 0)} satır)")
        for key, lbl in fields:
            if key in r:
                lines.append(f"   {lbl.ljust(width)} : {r[key]}")
        hata_idxs = r.get("hata_indices")
        if hata_idxs:
            idx_str = ", ".join(str(i) for i in sorted(hata_idxs))
            lines.append(f"   >>> [ÇEVİRİ EKSİK] kalan satır indeksleri: {idx_str}")
        passes = r.get("pass_coverage", "")
        if passes:
            lines.append(f"   {'Uygulanan geçişler'.ljust(width)} : {passes}")
        trace_txt = _format_pass_trace(r.get("pass_trace") or {})
        if trace_txt:
            lines.append(f"   {'Kalite geçişi kırılımı'.ljust(width)} : {trace_txt}")
        multi_count, multi_txt = _multi_pass_history(r.get("pass_history") or {})
        if multi_count:
            lines.append(f"   {'Çoklu-pass satırı'.ljust(width)} : {multi_count} ({multi_txt})")
        override_count, override_txt = _detect_pass_overrides(r.get("pass_history") or {})
        if override_count:
            lines.append(f"   {'Pass etkileşimi'.ljust(width)} : {override_count} ({override_txt})")
    sums = {}
    for key, _lbl in fields:
        vals = [r[key] for r in rows if key in r]
        if vals:
            sums[key] = sum(vals)
    total_lines = sum(r.get("total", 0) for r in rows)
    parts = [f"{lbl}: {sums[key]}" for key, lbl in fields if key in sums]
    trace_sums = {}
    for r in rows:
        for name, count in (r.get("pass_trace") or {}).items():
            trace_sums[name] = trace_sums.get(name, 0) + count
    trace_total = _format_pass_trace(trace_sums)
    lines += [
        "\n" + "=" * 72,
        f"TOPLAM: {len(rows)} dosya, {total_lines} satır",
        "  |  ".join(parts),
    ]
    if trace_total:
        lines.append(f"Pass breakdown total: {trace_total}")
    total_multi = 0
    multi_samples = []
    total_overrides = 0
    override_samples = []
    interaction_counts = {}
    for r in rows:
        count, sample = _multi_pass_history(r.get("pass_history") or {}, max_items=2)
        total_multi += count
        if sample:
            multi_samples.append(f"{r.get('name', '?')}: {sample}")
        for name, count_value in _pass_interaction_counts(r.get("pass_history") or {}).items():
            interaction_counts[name] = interaction_counts.get(name, 0) + count_value
        override_count, override_sample = _detect_pass_overrides(
            r.get("pass_history") or {}, max_items=2)
        total_overrides += override_count
        if override_sample:
            override_samples.append(f"{r.get('name', '?')}: {override_sample}")
    if total_multi:
        joined = " | ".join(multi_samples[:5])
        if len(multi_samples) > 5:
            joined += f" | +{len(multi_samples) - 5} dosya"
        lines.append(f"Çoklu-pass değişen satırlar: {total_multi} ({joined})")
    if total_overrides:
        joined = " | ".join(override_samples[:5])
        if len(override_samples) > 5:
            joined += f" | +{len(override_samples) - 5} dosya"
        counts_txt = _format_interaction_counts(interaction_counts)
        suffix = f"; {counts_txt}" if counts_txt else ""
        lines.append(f"Pass etkileşimleri: {total_overrides}{suffix} ({joined})")
    lines.append(f"Oturum token toplamı: {total_tokens:,}  (~${total_tokens/1e6*price:.4f})")
    return "\n".join(lines)


_LOG_PID_RE = re.compile(r"\.pid(\d+)\.log$")


def rotate_logs(log_dir: Path, keep: int = 100) -> int:
    """En yeni `keep` log dosyasını tutar, eskileri siler. Silinen sayısını döner.

    CANLI bir sürecin log dosyası SAYIYA BAKILMAKSIZIN asla silinmez (bkz. dosya adına
    gömülü pid + _pid_alive). NEDEN (2026-07-16 gerçek olay): kullanıcı bir batch'i
    saatlerce beklerken (log dosyası sessiz — yeni satır yazılmıyor, mtime bayatlıyor)
    art arda çalıştırılan test App() örnekleri onlarca YENİ (küçük, taze mtime'lı) log
    oluşturdu; sayı-bazlı 'en yeni N' kuralı kullanıcının SESSİZ ama CANLI oturum logunu
    rotasyondan düşürüp SİLDİ — geri getirilemedi. pid kontrolü bunu artık imkânsız
    kılar: log ne kadar sessiz kalırsa kalsın, sahibi yaşadığı sürece silinmez."""
    try:
        logs = list(log_dir.glob("*.log"))
    except Exception:
        return 0

    protected, candidates = [], []
    for p in logs:
        m = _LOG_PID_RE.search(p.name)
        if m and _pid_alive(int(m.group(1))):
            protected.append(p)
        else:
            candidates.append(p)

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    removed = 0
    for p in candidates[keep:]:
        try:
            p.unlink()
            removed += 1
        except Exception:
            pass
    return removed





# ── Canlı batch sahipliği (yarım-batch penceresi için) ────────────────────────
# SORUN (2026-07-16 gerçek olay): `batch_id.txt` gönderim anında yazılır ve iş bitince
# temizlenir — yani UÇUŞTAKİ bir batch ile ÇÖKMÜŞ/sahipsiz kalmış bir batch dosyada
# BİREBİR aynı görünür. Bu yüzden bir batch beklenirken uygulamanın İKİNCİ bir örneği
# açılırsa (ya da kapatılıp yeniden açılırsa), açılış kontrolü canlı batch'leri "yarım
# kalmış" diye listeler. Oradaki "Seçilenleri Sil" düğmesi, parası ödenmiş ve hâlâ
# işlenen bir batch'in kurtarma verisini (fmap + id) siler.
# ÇÖZÜM: batch'leri işleyen süreç sahipliğini `batch_owner_<pid>.json`'a yazar; açılış
# kontrolü, sahibi HÂLÂ YAŞAYAN süreç olan id'leri pencerede göstermez. Süreç gerçekten
# çöktüyse pid ölüdür → kilit yok sayılır → pencere amaçlandığı gibi çıkar (kurtarma
# yine çalışır).
# NEDEN SÜREÇ-BAŞINA DOSYA (tek ortak dosya DEĞİL): tek dosya tek sahipli olurdu —
# ikinci bir süreç (ya da App kuran bir test) kendi kilidini yazarken canlı sahibin
# kaydını EZER, aktif batch'i kalmayınca da dosyayı SİLERDİ; yani korumanın kendisi
# çözmeye çalıştığı kirlenmeyi yeniden üretirdi. Her süreç yalnızca KENDİ dosyasını
# yazar/siler; okuyucu hepsini tarayıp ölü pid'lerinkini yok sayar.
_BATCH_OWNER_PREFIX = "batch_owner_"
_BATCH_OWNER_GLOB = "batch_owner_*.json"


def _batch_id_path() -> Path:
    """batch_id.txt'nin yolu. Tek nokta olması testlerin GERÇEK dosyaya dokunmadan
    (patch'leyerek) çalışabilmesi içindir — canlı bir batch sürerken testin gerçek
    kurtarma dosyasını geçici de olsa ezmesi kabul edilemez."""
    return state_path(__file__, "batch_id.txt")


def _pid_alive(pid: int) -> bool:
    """PID canlı mı?

    DİKKAT: Windows'ta `os.kill(pid, 0)` KULLANILMAZ — POSIX'te sinyal 0 zararsız bir
    varlık sorgusudur, ama Windows'ta os.kill TerminateProcess çağırır ve süreci
    GERÇEKTEN ÖLDÜRÜR. Bu yüzden Windows'ta ctypes/OpenProcess ile salt-okuma sorgu.

    BELİRSİZLİK YÖNÜ KASITLI: sorgulanamayan durumlarda True (canlı) döner. Yanlışlıkla
    "canlı" demek pencereyi bastırır (kullanıcıda '↺ Batch'i Devam Ettir' düğmesi zaten
    var — zararsız); yanlışlıkla "ölü" demek ise canlı bir batch için tehlikeli Sil/Devam
    penceresini açar. Şüphede güvenli taraf: bastırmak."""
    try:
        pid = int(pid)
    except Exception:
        return False
    if pid <= 0:
        return False
    import sys as _sys
    if _sys.platform == "win32":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h:
                return False   # açılamıyor → süreç yok (ya da erişim yok; yok say)
            try:
                code = ctypes.c_ulong()
                if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
                    return True   # sorgulanamadı → canlı say (güvenli yön)
                return code.value == STILL_ACTIVE
            finally:
                k32.CloseHandle(h)
        except Exception:
            return True   # belirsiz → canlı say (güvenli yön)
    import os as _os
    try:
        _os.kill(pid, 0)   # POSIX: sinyal 0 = varlık sorgusu, öldürmez
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True   # süreç var, bize ait değil
    except Exception:
        return True


def _live_owned_batch_ids() -> set:
    """BAŞKA canlı süreçlerin şu an üzerinde çalıştığı batch id'leri.

    Tüm `batch_owner_<pid>.json` dosyaları taranır; ölü pid'lerinki yok sayılır (ve
    fırsat buldukça temizlenir). Okuma başarısızsa boş küme döner = eski davranış."""
    import os as _os
    owned: set = set()
    try:
        base = state_dir(__file__)
        my_pid = _os.getpid()
        for p in base.glob(_BATCH_OWNER_GLOB):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                pid = int(d.get("pid", 0) or 0)
                ids = {str(b).strip() for b in (d.get("batch_ids") or []) if str(b).strip()}
                if pid <= 0 or pid == my_pid:
                    continue
                if _pid_alive(pid):
                    owned |= ids
                else:
                    p.unlink(missing_ok=True)   # ölü sürecin kalıntısı — temizle
            except Exception:
                continue   # bozuk/okunamayan kilit dosyası: yok say, diğerlerine bak
    except Exception:
        return set()
    return owned


# ── Yarım-kalan-batch penceresi: OpenAI durumu ────────────────────────────────
# NEDEN: kilit (batch_owner) yanlış pencereyi bastırıyor ama pencere HAKLI olarak
# çıktığında kullanıcı yine kördü — hangi batch'in gerçekten bitmiş/hâlâ işlendiğini
# bilmeden "Seçilenleri Sil" tıklıyordu. Bu, işlenmekte olan (parası ödenmiş) bir
# batch'in kurtarma verisini silme riskini taşır. Çözüm: pencere açılırken OpenAI'den
# gerçek durumu çek, göster; hâlâ işlenen bir batch seçiliyse Sil'de ekstra onay iste.
_BATCH_LIVE_STATUSES = frozenset({"validating", "in_progress", "finalizing", "cancelling"})
_BATCH_DONE_STATUSES = frozenset({"completed"})
_BATCH_DEAD_STATUSES = frozenset({"failed", "expired", "cancelled"})


def _fetch_batch_statuses(api_key: str, batch_ids: list, log_fn=None, base_url: str = "") -> dict:
    """Verilen batch id'lerin OpenAI'deki GÜNCEL durumunu çeker.

    Döner: {batch_id: status_str}. status_str bilinen OpenAI değerlerinden biri
    ('validating'/'in_progress'/'finalizing'/'completed'/'failed'/'expired'/
    'cancelling'/'cancelled') ya da sorgulanamazsa 'unknown'. Ağ/anahtar hatası TÜM
    fonksiyonu düşürmez — her id bağımsız denenir, tek tek 'unknown'a düşer (fail-safe:
    bilinmeyen durum çağıran tarafından CANLI OLABİLİR sayılmalı, silme onayını atlamaz)."""
    result = {bid: "unknown" for bid in batch_ids}
    if not api_key or not batch_ids:
        return result
    try:
        from openai import OpenAI as _OAI
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = _OAI(**kwargs)
    except Exception as e:
        if log_fn:
            log_fn("Batch durumu sorgulanamadı.", "warn")
        return result
    for bid in batch_ids:
        try:
            b = client.batches.retrieve(bid)
            result[bid] = getattr(b, "status", "unknown") or "unknown"
        except Exception:
            result[bid] = "unknown"
    return result


def _batch_status_label(status: str) -> tuple:
    """Durum kodunu (görünen_metin, renk_sınıfı) çiftine çevirir.
    renk_sınıfı: 'live' | 'done' | 'dead' | 'unknown' — çağıran gerçek renge eşler."""
    if status in _BATCH_LIVE_STATUSES:
        return f"● {status} — İŞLENİYOR", "live"
    if status in _BATCH_DONE_STATUSES:
        return "✓ completed — indirilebilir", "done"
    if status in _BATCH_DEAD_STATUSES:
        return f"✗ {status}", "dead"
    return "? durum bilinmiyor", "unknown"


# ── Ana uygulama ──────────────────────────────────────────────────────────────
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Subtitle Translator")
        self.minsize(900, 620)
        self.configure(fg_color=BG)
        self._restored_geometry = None  # kayıtlı pencere pozisyonu

        self._stop_flag      = False
        self._pause_btw_files = threading.Event()
        self._pause_btw_files.set()  # initially not paused
        self._token_total    = 0
        self._token_cached   = 0
        self._token_lock     = threading.Lock()   # _token_total multi-thread erişimi
        self._log_lock       = threading.Lock()   # log dosyası concurrent write
        self._selected_files = []   # manually picked files; empty = use input folder
        self._input_folder_explicitly_selected = False
        self._input_entry_focus_val = None
        self._removed_queue_files = set()
        self._content_type_preflight_done = False
        self._active_batches = {}   # {batch_id: api_key} — durdururken iptal için
        self._batch_lock     = threading.RLock()   # _active_batches eşzamanlı erişimi
        self._ckpt_lock      = threading.Lock()   # sync checkpoint dosyasına eşzamanlı yazım
        self.model_2_5m_combo = None
        self.model_250k_combo = None
        self._helper_keys_cache = {}
        self.api_url_var = ctk.StringVar()

        # ── Advanced Settings defaults ────────────────────────────────────────
        self._chunk_size        = CHUNK
        self._context_lines     = CONTEXT_LINES
        self._lookahead_lines   = LOOKAHEAD_LINES
        self._max_workers       = 4
        self._temperature       = 0.2
        self._max_retry         = 3
        self._scene_gap_seconds = SCENE_GAP_SEC
        self._merge_max_chars   = MERGE_MAX_CHARS    # parçalı cue birleştirme eşikleri
        self._merge_max_gap_ms  = MERGE_MAX_GAP_MS

        # ── Progress tracking ─────────────────────────────────────────────────
        self._start_time         = None
        self._elapsed_tick       = None
        self._is_running         = False
        self._ui_queue           = queue.Queue()
        self._is_shutting_down   = False
        self._active_snapshot    = None
        self._drain_ui_queue_id  = None

        # ── Statistics animation ──────────────────────────────────────────────
        self._token_sparkline_points = []

        # ── Log dosyası ───────────────────────────────────────────────────────
        import datetime
        import os as _os
        _log_dir = state_path(__file__, "logs")
        _log_dir.mkdir(exist_ok=True)
        rotate_logs(_log_dir)   # canlı oturumlar korunur; kalan en yeni 100 tutulur
        _stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        # Dosya adına pid gömülü — rotate_logs bunu canlı-süreç korumasında kullanır
        # (bkz. yukarıdaki fonksiyon docstring'i + _LOG_PID_RE).
        self._log_file = open(_log_dir / f"{_stamp}.pid{_os.getpid()}.log", "w", encoding="utf-8")

        # ── Translation Memory ────────────────────────────────────────────────
        from translation_memory import TranslationMemory
        self._tm = TranslationMemory(state_path(__file__, "translation_memory.db"))

        # ── Project Memory ────────────────────────────────────────────────────
        from project_memory import ProjectMemory
        self._pm: ProjectMemory | None = None  # input klasörü seçilince init edilir

        self._build_ui()
        self._load_settings()
        if self._restored_geometry:
            try:
                self.geometry(self._restored_geometry)
            except Exception:
                pass
        self._setup_drag_drop()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        try:
            self._drain_ui_queue_id = self.after(20, self._drain_ui_queue)
        except Exception:
            pass
        # Açılışta yarım kalan batch kontrolü (UI hazır olduktan sonra çalışsın)
        self.after(500, self._check_pending_batches)


    def _check_pending_batches(self):
        """Program açılışında batch_id.txt varsa seçim penceresi gösterir."""
        try:
            bid_path = _batch_id_path()
            if not bid_path.exists():
                return
            raw_ids = [ln.strip() for ln in bid_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            if not raw_ids:
                return
            # batch_id.txt'de bazen ID'ler birbirine yapışık olabiliyor — ayır
            batch_ids = []
            for raw in raw_ids:
                parts = re.findall(r'batch_[a-f0-9]+', raw)
                batch_ids.extend(parts if parts else [raw])
            batch_ids = list(dict.fromkeys(batch_ids))  # deduplicate, preserve order
            # Başka bir CANLI süreç bu batch'leri işliyorsa onları GÖSTERME — pencerenin
            # 'Sil' düğmesi uçuştaki (parası ödenmiş) bir batch'in kurtarma verisini
            # silerdi. Bkz. _live_owned_batch_ids.
            owned = _live_owned_batch_ids()
            if owned:
                batch_ids = [b for b in batch_ids if b not in owned]
            if not batch_ids:
                return
            self._show_pending_batches_dialog(batch_ids)
        except Exception:
            pass

    def _show_pending_batches_dialog(self, batch_ids):
        """Yarım kalan batch'leri seçtiren CustomTkinter penceresi."""
        import os as _os
        from datetime import datetime
        dlg = ctk.CTkToplevel(self)
        dlg.title("⏳ Yarım Kalan Batch'ler")
        dlg.geometry("620x480")
        dlg.grab_set()
        dlg.lift()
        dlg.focus_force()
        dlg.configure(fg_color=BG)
        dlg.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ctk.CTkFrame(dlg, fg_color=ACCENT, corner_radius=10, height=50)
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="⏳  Yarım Kalan Batch'ler Bulundu",
                     font=ctk.CTkFont("Segoe UI", 14, "bold"),
                     text_color="white").pack(pady=12)

        ctk.CTkLabel(dlg, text="İşaretli olanlar seçilen işlemi (Sil veya Devam Ettir) alır:",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=FG2).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 6))

        # Scrollable frame for batch list
        scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent",
                                         scrollbar_button_color=BORDER,
                                         height=280)
        scroll.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 8))
        scroll.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(2, weight=1)

        check_vars = {}
        status_labels = {}
        status_map = {}   # bid -> OpenAI status (arka plan sorgusu doldurur)
        base = state_dir(__file__)

        for i, bid in enumerate(batch_ids):
            fmap_path = base / f"batch_fmap_{bid}.json"
            # Bilgileri topla
            btype = "?"
            date_str = "?"
            file_hint = ""
            if fmap_path.exists():
                try:
                    mtime = _os.path.getmtime(fmap_path)
                    date_str = datetime.fromtimestamp(mtime).strftime("%d.%m.%Y %H:%M")
                    with open(fmap_path, encoding="utf-8") as f:
                        fmap_data = json.load(f)
                    btype = "Hybrid" if fmap_data.get("type") == "hybrid" else "Standart"
                    # Dosya adını bulmaya çalış
                    opath = fmap_data.get("output_path", "")
                    if opath:
                        file_hint = Path(opath).stem[:40]
                except Exception:
                    pass
            else:
                btype = "Standart"
                date_str = "?"

            row_fr = ctk.CTkFrame(scroll, fg_color=CARD, corner_radius=8)
            row_fr.grid(row=i, column=0, sticky="ew", padx=4, pady=3)
            row_fr.grid_columnconfigure(1, weight=1)

            var = ctk.BooleanVar(value=True)
            check_vars[bid] = var

            cb = ctk.CTkCheckBox(row_fr, text="", variable=var,
                                 width=24, height=24,
                                 fg_color=ACCENT, hover_color=GREEN,
                                 border_color=BORDER)
            cb.grid(row=0, column=0, rowspan=3, padx=(8, 4), pady=6)

            # Batch bilgi satırı
            info_text = f"{btype}  •  {date_str}"
            if file_hint:
                info_text += f"  •  {file_hint}"
            ctk.CTkLabel(row_fr, text=info_text,
                         font=ctk.CTkFont("Segoe UI", 11, "bold"),
                         text_color=FG, anchor="w").grid(row=0, column=1, sticky="w", padx=4, pady=(6, 0))

            # Batch ID (küçük font)
            ctk.CTkLabel(row_fr, text=bid,
                         font=ctk.CTkFont("Consolas", 9),
                         text_color=FG2, anchor="w").grid(row=1, column=1, sticky="w", padx=4, pady=0)

            # OpenAI durumu — arka planda sorgulanır, gelene kadar placeholder
            status_lbl = ctk.CTkLabel(row_fr, text="… durum sorgulanıyor",
                                      font=ctk.CTkFont("Segoe UI", 10),
                                      text_color=FG2, anchor="w")
            status_lbl.grid(row=2, column=1, sticky="w", padx=4, pady=(0, 6))
            status_labels[bid] = status_lbl

        # OpenAI'den GERÇEK durumu çek (arka plan — UI'yı bloklamaz). "Seçilenleri Sil"
        # bu bilgiye göre ekstra onay ister (bkz. _delete_selected) — kilit (batch_owner)
        # yanlış pencereyi bastırıyor ama pencere haklı çıktığında kullanıcı hâlâ
        # kördü; 2026-07-16 olayının doğrudan devamı.
        _STATUS_COLOR = {"live": "#F5A623", "done": GREEN, "dead": RED, "unknown": FG2}

        def _apply_statuses(fetched):
            status_map.update(fetched)
            for bid, status in fetched.items():
                lbl = status_labels.get(bid)
                if lbl is None:
                    continue
                try:
                    text, kind = _batch_status_label(status)
                    lbl.configure(text=text, text_color=_STATUS_COLOR.get(kind, FG2))
                except Exception:
                    pass

        api_key = self._main_api_key()
        base_url = self._main_api_base_url()

        def _fetch_in_bg():
            fetched = _fetch_batch_statuses(
                api_key=api_key,
                batch_ids=batch_ids,
                log_fn=self._log,
                base_url=base_url,
            )
            _post_ui(self, _apply_statuses, fetched)

        threading.Thread(target=_fetch_in_bg, daemon=True).start()

        # Alt butonlar
        btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_fr.grid(row=3, column=0, sticky="ew", padx=12, pady=(4, 12))
        btn_fr.grid_columnconfigure((0, 1, 2, 3), weight=1)

        def _select_all():
            for v in check_vars.values():
                v.set(True)

        def _deselect_all():
            for v in check_vars.values():
                v.set(False)

        def _resume_selected():
            selected = [bid for bid, v in check_vars.items() if v.get()]
            unselected = [bid for bid, v in check_vars.items() if not v.get()]
            dlg.destroy()
            if not selected:
                return
            # Seçilmeyenleri batch_id.txt'den çıkar ve fmap dosyalarını sil
            if unselected:
                self._clear_batch_recovery(unselected)
            # batch_id.txt'yi sadece seçilenlerle güncelle
            bid_path = _batch_id_path()
            try:
                mutate_batch_ids(bid_path, replace=selected)
            except Exception:
                pass
            self._resume()

        def _delete_selected():
            selected = [bid for bid, v in check_vars.items() if v.get()]
            if not selected:
                # Hiçbiri işaretli değilken 'Sil'e basmak sessizce hiçbir şey
                # yapmamalı — pencere yine de kapanırsa kullanıcı sildiğini
                # sanır, batch_id.txt değişmez ve pencere bir sonraki açılışta
                # AYNEN tekrar çıkar. Bunun yerine durumu açıkça bildir.
                messagebox.showwarning(
                    "Seçim yok",
                    "Silinecek batch işaretlenmedi. En az bir tanesini işaretleyin "
                    "(veya 'Tümünü Seç' ile hepsini işaretleyip tekrar deneyin).",
                    parent=dlg)
                return
            # Seçilenlerden biri hâlâ İŞLENİYOR (ya da durumu henüz/hiç öğrenilemedi —
            # bilinmeyen durum GÜVENLİ TARAF gereği canlı sayılır) ise ekstra onay iste.
            # Bu, 2026-07-16'daki olayın (canlı bir batch'in kurtarma verisinin
            # yanlışlıkla silinme riski) doğrudan devamıdır.
            _risky = [bid for bid in selected
                     if status_map.get(bid, "unknown") in _BATCH_LIVE_STATUSES
                     or status_map.get(bid, "unknown") == "unknown"]
            if _risky:
                _names = "\n".join(f"  • {bid}" for bid in _risky)
                if not messagebox.askyesno(
                        "⚠ Hâlâ işleniyor olabilir",
                        f"{len(_risky)} batch'in durumu 'işleniyor' ya da öğrenilemedi:\n\n"
                        f"{_names}\n\n"
                        "Bunlar GERÇEKTEN hâlâ OpenAI'de çalışıyorsa, kurtarma verisini "
                        "silmek parasını ödediğiniz sonucu kaybetmenize yol açar.\n\n"
                        "Yine de silmek istediğinize emin misiniz?",
                        icon="warning", parent=dlg):
                    return
            self._clear_batch_recovery(selected)
            # Kalan batch'ler
            remaining = [bid for bid, v in check_vars.items() if not v.get()]
            bid_path = _batch_id_path()
            try:
                mutate_batch_ids(bid_path, replace=remaining)
            except Exception:
                pass
            dlg.destroy()

        ctk.CTkButton(btn_fr, text="Tümünü Seç", width=100, height=32,
                       font=ctk.CTkFont("Segoe UI", 11),
                       fg_color=CARD, hover_color=BORDER,
                       command=_select_all).grid(row=0, column=0, padx=3, sticky="ew")

        ctk.CTkButton(btn_fr, text="Seçimi Kaldır", width=100, height=32,
                       font=ctk.CTkFont("Segoe UI", 11),
                       fg_color=CARD, hover_color=BORDER,
                       command=_deselect_all).grid(row=0, column=1, padx=3, sticky="ew")

        ctk.CTkButton(btn_fr, text="🗑  Seçilenleri Sil", width=120, height=32,
                       font=ctk.CTkFont("Segoe UI", 11),
                       fg_color=RED, hover_color="#C0392B",
                       command=_delete_selected).grid(row=0, column=2, padx=3, sticky="ew")

        ctk.CTkButton(btn_fr, text="▶  Seçilenleri Devam Ettir", width=160, height=32,
                       font=ctk.CTkFont("Segoe UI", 11, "bold"),
                       fg_color=GREEN, hover_color="#27AE60",
                       text_color="white",
                       command=_resume_selected).grid(row=0, column=3, padx=3, sticky="ew")

    def _on_close(self):
        """Pencere kapatılırken kaynakları temizce kapat."""
        running = getattr(self, "_is_running", False)
        if running:
            if not messagebox.askyesno(
                    "Çeviri devam ediyor",
                    "Çeviri devam ediyor. Kapatırsanız batch'ler "
                    "OpenAI'de koşmaya devam eder.\n\nKapatmak ister misiniz?"):
                return
        self._is_shutting_down = True
        try:
            if self._drain_ui_queue_id is not None:
                self.after_cancel(self._drain_ui_queue_id)
                self._drain_ui_queue_id = None
        except Exception:
            pass
        while True:
            try:
                self._ui_queue.get_nowait()
            except queue.Empty:
                break
        self._stop_flag = True
        self._stop_elapsed_timer()
        try:
            self._save_settings()
        except Exception:
            pass
        try:
            if hasattr(self, "_tm") and self._tm:
                self._tm.close()
        except Exception:
            pass
        try:
            if hasattr(self, "_log_file") and self._log_file:
                self._log_file.close()
        except Exception:
            pass
        self.destroy()

    # ── Project Memory Dialog ─────────────────────────────────────────────────
    def _show_project_memory(self):
        """Proje hafızasını görüntüle ve yönet."""
        if self._pm is None:
            messagebox.showinfo(
                "Proje Hafızası",
                "Proje hafızası henüz yüklenmedi.\n"
                "Önce bir giriş klasörü seçin.",
                parent=self)
            return

        pm_stats = self._pm.stats()
        dlg = ctk.CTkToplevel(self)
        dlg.title("🧠 Proje Hafızası")
        dlg.geometry("700x580")
        dlg.configure(fg_color=BG)
        dlg.grab_set()
        dlg.lift()
        dlg.focus_force()

        hdr = ctk.CTkFrame(dlg, fg_color=ACCENT, corner_radius=10, height=50)
        hdr.pack(fill="x", padx=12, pady=(12, 4))
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="🧠  Proje Hafızası",
                     font=ctk.CTkFont("Segoe UI", 13, "bold"),
                     text_color="white").pack(side="left", padx=14)
        ctk.CTkLabel(hdr,
                     text=f"{pm_stats['glossary']} terim  •  {pm_stats['characters']} karakter",
                     font=ctk.CTkFont("Segoe UI", 10), text_color="#dde").pack(side="right", padx=14)

        sf = ctk.CTkScrollableFrame(dlg, fg_color=PANEL, corner_radius=8)
        sf.pack(fill="both", expand=True, padx=12, pady=8)

        # Glossary
        glossary = self._pm.get_glossary()
        if glossary:
            ctk.CTkLabel(sf, text="PROJE GLOSSARYSİ",
                         font=ctk.CTkFont("Segoe UI", 11, "bold"),
                         text_color=ACCENT).pack(anchor="w", padx=8, pady=(8, 4))
            for src, tgt in list(glossary.items())[:50]:
                row = ctk.CTkFrame(sf, fg_color=CARD, corner_radius=4)
                row.pack(fill="x", padx=4, pady=1)
                ctk.CTkLabel(row, text=f"{src}  →  {tgt}",
                             font=ctk.CTkFont("Segoe UI", 11),
                             text_color=FG, anchor="w").pack(fill="x", padx=10, pady=4)

        # Characters
        chars = self._pm.get_characters()
        if chars:
            ctk.CTkLabel(sf, text="KARAKTERLER",
                         font=ctk.CTkFont("Segoe UI", 11, "bold"),
                         text_color=ACCENT).pack(anchor="w", padx=8, pady=(12, 4))
            char_text = ", ".join(list(chars.keys())[:40])
            ctk.CTkLabel(sf, text=char_text,
                         font=ctk.CTkFont("Segoe UI", 11), text_color=FG,
                         wraplength=620, justify="left").pack(anchor="w", padx=12, pady=(0, 8))

        # Notes
        notes = self._pm.get_notes()
        if notes:
            ctk.CTkLabel(sf, text="SERİ NOTLARI",
                         font=ctk.CTkFont("Segoe UI", 11, "bold"),
                         text_color=ACCENT).pack(anchor="w", padx=8, pady=(12, 4))
            for note in notes:
                ctk.CTkLabel(sf, text=f"• {note}",
                             font=ctk.CTkFont("Segoe UI", 11), text_color=FG2,
                             wraplength=620, justify="left").pack(anchor="w", padx=12, pady=2)

        if not glossary and not chars and not notes:
            ctk.CTkLabel(sf, text="Henüz proje hafızası yok.\nAnaliz tamamlandıktan sonra otomatik dolar.",
                         font=ctk.CTkFont("Segoe UI", 12), text_color=FG2).pack(pady=40)

        # Butonlar
        btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_fr.pack(fill="x", padx=12, pady=(0, 12))
        btn_fr.grid_columnconfigure((0, 1, 2), weight=1)

        def _clear_pm():
            if messagebox.askyesno("Sıfırla", "Tüm proje hafızası silinsin mi?", parent=dlg):
                self._pm.clear()
                dlg.destroy()
                self._log("Proje hafızası sıfırlandı.", "warn")

        ctk.CTkButton(btn_fr, text="🗑  Sıfırla",
                      fg_color="#3a1a1a", hover_color="#5a2020",
                      text_color=RED,
                      command=_clear_pm).grid(row=0, column=0, padx=4, sticky="ew")
        ctk.CTkButton(btn_fr, text="📋  Kopyala",
                      fg_color=CARD, hover_color=BORDER,
                      command=lambda: (self.clipboard_clear(),
                                       self.clipboard_append(self._pm.build_context_hint()))).grid(
            row=0, column=1, padx=4, sticky="ew")
        ctk.CTkButton(btn_fr, text="✕  Kapat",
                      fg_color=CARD, hover_color=BORDER,
                      command=dlg.destroy).grid(row=0, column=2, padx=4, sticky="ew")

    # ── Drag-and-Drop ─────────────────────────────────────────────────────────
    def _setup_drag_drop(self):
        """Windows TkinterDnD2 ile sürükle-bırak desteği.
        tkinterdnd2 kurulu değilse sessizce devre dışı kalır."""
        try:
            from tkinterdnd2 import DND_FILES
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self._on_drop)
            self._drag_drop_available = True
            self._log("Sürükle-bırak aktif (.srt/.vtt/.ass)", "ok")
        except Exception:
            self._drag_drop_available = False

    def _on_drop(self, event):
        """Sürüklenen dosya/klasörleri mevcut seçime ekle."""
        if getattr(self, "_is_running", False):
            self._log("Çeviri çalışırken sürükle-bırak yapılamaz.", "warn")
            return
        try:
            files = list(self.tk.splitlist(event.data))
        except Exception:
            import re as _re
            paths = _re.findall(r'\{([^}]+)\}|(\S+)', event.data)
            files = [p[0] or p[1] for p in paths]
        # Sadece altyazı dosyalarını al
        subtitle_exts = {'.srt', '.vtt', '.ass', '.ssa'}
        valid = []
        for f in files:
            p = Path(f)
            if p.is_dir():
                valid.extend(get_subtitle_files(str(p), recursive=True))
            elif p.suffix.lower() in subtitle_exts and p.exists():
                valid.append(str(p))
        if not valid:
            self._log("Sürüklenen dosyalarda geçerli altyazı yok.", "warn")
            return
        before = len(self._selected_files)
        self._content_type_preflight_done = False
        self._selected_files = self._dedupe_paths(list(self._selected_files) + valid)
        added = len(self._selected_files) - before
        total = len(self._selected_files)
        self._refresh_selected_files_ui(
            f"Sürükle-bırak: +{added} yeni, toplam {total} dosya — "
            + ", ".join(Path(f).name for f in valid[:5])
            + ("…" if len(valid) > 5 else ""))

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()

    # ── Sol panel ─────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = ctk.CTkScrollableFrame(self, width=290, fg_color=PANEL,
                                    scrollbar_button_color=BORDER,
                                    scrollbar_button_hover_color=ACCENT)
        sb.grid(row=0, column=0, sticky="nsew", padx=(12,6), pady=12)
        sb.grid_columnconfigure(0, weight=1)
        self._sb = sb

        # Başlık
        hdr = ctk.CTkFrame(sb, fg_color=ACCENT, corner_radius=10, height=56)
        hdr.grid(row=0, column=0, sticky="ew", pady=(0,16))
        hdr.grid_columnconfigure(0, weight=1)
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="🎬  Subtitle Translator",
                     font=ctk.CTkFont("Segoe UI", 15, "bold"),
                     text_color="white").grid(row=0, column=0, pady=14, padx=14, sticky="w")

        r = 1

        def section(txt):
            nonlocal r
            ctk.CTkLabel(sb, text=txt, font=ctk.CTkFont("Segoe UI", 11, "bold"),
                         text_color=ACCENT).grid(row=r, column=0, sticky="w",
                         padx=4, pady=(14,4)); r += 1

        def lbl(txt, info=None):
            nonlocal r
            if info:
                fr = ctk.CTkFrame(sb, fg_color="transparent")
                fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(6,2)); r += 1
                fr.grid_columnconfigure(0, weight=1)
                ctk.CTkLabel(fr, text=txt, font=ctk.CTkFont("Segoe UI", 12),
                             text_color=FG2).grid(row=0, column=0, sticky="w")
                ctk.CTkLabel(fr, text=f"ℹ {info}", font=ctk.CTkFont("Segoe UI", 10),
                             text_color=FG2, wraplength=240, justify="left"
                             ).grid(row=1, column=0, sticky="w")
            else:
                ctk.CTkLabel(sb, text=txt, font=ctk.CTkFont("Segoe UI", 12),
                             text_color=FG2).grid(row=r, column=0, sticky="w",
                             padx=4, pady=(6,2)); r += 1

        def entry(show=None):
            nonlocal r
            e = ctk.CTkEntry(sb, show=show or "", height=36,
                             font=ctk.CTkFont("Consolas" if show else "Segoe UI", 12),
                             fg_color=CARD, border_color=BORDER,
                             text_color=FG, placeholder_text_color=FG2)
            e.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,2)); r += 1
            return e

        def combo(var, values):
            nonlocal r
            c = ctk.CTkComboBox(sb, variable=var, values=values,
                                height=36, font=ctk.CTkFont("Segoe UI", 12),
                                fg_color=CARD, border_color=BORDER,
                                button_color=BORDER, button_hover_color=ACCENT,
                                dropdown_fg_color=CARD, text_color=FG,
                                state="readonly")
            c.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,2)); r += 1
            return c

        def sep():
            nonlocal r
            ctk.CTkFrame(sb, height=1, fg_color=BORDER).grid(
                row=r, column=0, sticky="ew", padx=4, pady=8); r += 1

        # ── API ──────────────────────────────────────────────────────────────
        section("API AYARLARI")
        lbl("OpenAI API Key")
        self.api_key_entry = entry(show="•")
        lbl("OpenAI API Base URL (opsiyonel)")
        self.api_url_entry = ctk.CTkEntry(sb, textvariable=self.api_url_var, height=36,
                                          fg_color=CARD, border_color=BORDER, text_color=FG,
                                          placeholder_text="Boş bırak: https://api.openai.com/v1")
        self.api_url_entry.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,2)); r += 1

        # ── Ana Model — Özel Sağlayıcı (OpenAI dışı, ör. shuaiapi/gpt-5.5) ──────
        # TASARIM KARARI (2026-07-18, kullanıcı isteği): yukarıdaki "OpenAI API Key"/
        # "OpenAI API Base URL" alanlarına ASLA yazılmaz/dokunulmaz — kullanıcının
        # "mevcut openai keyim gitmeden" endişesini en net karşılayan yol, o alanları
        # hiç değiştirmemek. Bunun yerine AYRI, kendi etiketli alanlar: açıkken ana
        # çeviri bu alanları kullanır, OpenAI alanları görünürde/bellekte AYNEN kalır.
        # Kapatınca anında eskisi gibi OpenAI'ye döner — hiçbir şey elle geri yazılmaz.
        self.main_custom_var = ctk.BooleanVar(value=False)
        mc_fr = ctk.CTkFrame(sb, fg_color="transparent")
        mc_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        mc_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(mc_fr, text="", variable=self.main_custom_var,
                      width=44, height=22, fg_color=BORDER, progress_color=ACCENT,
                      command=lambda: self._on_main_custom_changed()).grid(row=0, column=0)
        ctk.CTkLabel(mc_fr, text="Ana Model — Özel Sağlayıcı",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="Açıkken ANA ÇEVİRİ yukarıdaki OpenAI anahtarı yerine\naşağıdaki sağlayıcıyı kullanır (ör. shuaiapi/gpt-5.5).\nOpenAI alanlarına DOKUNULMAZ — kapatınca anında\neskisi gibi OpenAI'ye döner.",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,4)); r += 1

        self.main_custom_frame = ctk.CTkFrame(sb, fg_color="transparent")
        self.main_custom_frame.grid(row=r, column=0, sticky="ew", padx=0, pady=(0,4)); r += 1

        ctk.CTkLabel(self.main_custom_frame, text="Model Adı", font=ctk.CTkFont("Segoe UI", 11), text_color=FG2).pack(anchor="w", padx=4, pady=(2,1))
        self.main_custom_model_var = ctk.StringVar(value="gpt-5.4")
        self.main_custom_model_entry = ctk.CTkEntry(self.main_custom_frame, textvariable=self.main_custom_model_var, height=32,
                     font=ctk.CTkFont("Segoe UI", 11),
                     fg_color=CARD, border_color=BORDER, text_color=FG)
        self.main_custom_model_entry.pack(fill="x", padx=4, pady=(0,2))

        ctk.CTkLabel(self.main_custom_frame, text="API URL (taban adres, /chat/completions olmadan)", font=ctk.CTkFont("Segoe UI", 11), text_color=FG2).pack(anchor="w", padx=4, pady=(2,1))
        self.main_custom_url_var = ctk.StringVar(value="https://api.shuaiapi.com/v1")
        self.main_custom_url_entry = ctk.CTkEntry(self.main_custom_frame, textvariable=self.main_custom_url_var, height=32,
                     font=ctk.CTkFont("Segoe UI", 11),
                     fg_color=CARD, border_color=BORDER, text_color=FG,
                     placeholder_text="https://api.shuaiapi.com/v1")
        self.main_custom_url_entry.pack(fill="x", padx=4, pady=(0,2))

        ctk.CTkLabel(self.main_custom_frame, text="API Anahtarı", font=ctk.CTkFont("Segoe UI", 11), text_color=FG2).pack(anchor="w", padx=4, pady=(2,1))
        self.main_custom_key_entry = ctk.CTkEntry(self.main_custom_frame, show="•", height=32,
                     font=ctk.CTkFont("Consolas", 11),
                     fg_color=CARD, border_color=BORDER, text_color=FG)
        self.main_custom_key_entry.pack(fill="x", padx=4, pady=(0,4))
        self.main_custom_frame.grid_remove()   # başlangıçta kapalı (default OFF)

        # Bu 3 alan yalnızca _start()/_resume()/kapanışta değil, ALANDAN ÇIKINCA da
        # kaydedilir — kullanıcı doldurup çeviri başlatmadan/uygulamayı düzgün
        # kapatmadan ekranı değiştirse bile "hatırlasın" beklentisini karşılar
        # (diğer ayarlardan FARKLI, kasıtlı istisna — bu alanlar başka hiçbir tetikleyici
        # olmadan kolayca unutulabilir, örn. yalnızca deneme amaçlı doldurulup kapatılabilir).
        # DİKKAT: CTkEntry kompozit bir widget — kendi ÜZERİNDE .bind() hiçbir şey
        # yapmaz (sessizce yutulur). Gerçek olaylar iç ._entry (ham tkinter.Entry)
        # üzerinde işlenir; CTk kendi odak-stil davranışı için ZATEN <FocusOut>
        # bağlamış olduğundan add='+' ŞART — yoksa onu SESSİZCE EZER (kenarlık
        # rengi vb. bozulur). try/except: tests/customtkinter.py (saf-mantık
        # testleri için hafif stub) ._entry'yi sahte bir fonksiyona düşürür —
        # gerçek Tk yoksa bu bağ isteğe bağlıdır, sessizce atlanır.
        for _mc_w in (self.main_custom_model_entry, self.main_custom_url_entry, self.main_custom_key_entry):
            try:
                _mc_w._entry.bind("<FocusOut>", lambda _e: self._save_settings(), add="+")
            except Exception:
                pass

        # ── Model selection divided by token limits ──
        self.limit_class_var = ctk.StringVar(value="2.5M")
        self.model_2_5m_var = ctk.StringVar(value="gpt-5.4-mini")
        self.model_250k_var = ctk.StringVar(value="gpt-5.4")
        self.model_var = ctk.StringVar(value="gpt-5.4-mini")

        lbl("Model Limit Grubu")
        limit_fr = ctk.CTkFrame(sb, fg_color="transparent")
        limit_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(2,4)); r += 1
        limit_fr.grid_columnconfigure((0,1), weight=1)

        r1 = ctk.CTkRadioButton(limit_fr, text="2.5M / Gün", variable=self.limit_class_var, value="2.5M",
                                font=ctk.CTkFont("Segoe UI", 11, "bold"), fg_color=ACCENT, hover_color=ACCENT,
                                text_color=FG, command=lambda: self._update_active_model())
        r1.grid(row=0, column=0, sticky="w", padx=2, pady=2)

        r2 = ctk.CTkRadioButton(limit_fr, text="250K / Gün", variable=self.limit_class_var, value="250K",
                                font=ctk.CTkFont("Segoe UI", 11, "bold"), fg_color=ACCENT, hover_color=ACCENT,
                                text_color=FG, command=lambda: self._update_active_model())
        r2.grid(row=0, column=1, sticky="w", padx=2, pady=2)

        lbl("Hafif Modeller (2.5M Limit)")
        self.model_2_5m_combo = combo(self.model_2_5m_var, MODELS_2_5M)
        self.model_2_5m_combo.configure(command=lambda _: self._update_active_model("2.5M"))

        lbl("Zeki Modeller (250K Limit)")
        self.model_250k_combo = combo(self.model_250k_var, MODELS_250K)
        self.model_250k_combo.configure(command=lambda _: self._update_active_model("250K"))

        # Trace updates
        self.model_2_5m_var.trace_add("write", lambda *args: self._update_active_model())
        self.model_250k_var.trace_add("write", lambda *args: self._update_active_model())

        # ── Mod ──────────────────────────────────────────────────────────────
        sep()
        section("ÇEVİRİ MODU")
        self.mode_var = ctk.StringVar(value="batch")
        mode_fr = ctk.CTkFrame(sb, fg_color="transparent")
        mode_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        mode_fr.grid_columnconfigure((0,1), weight=1)
        for col, (txt, val, sub) in enumerate([
            ("📦 Batch", "batch", "Ucuz • Async"),
            ("⚡ Anında", "sync",  "Hızlı • Senkron"),
        ]):
            fr = ctk.CTkFrame(mode_fr, fg_color=CARD, corner_radius=8)
            fr.grid(row=0, column=col, sticky="ew",
                    padx=(0,4) if col == 0 else (4,0), pady=2, ipady=4)
            fr.grid_columnconfigure(0, weight=1)
            _mode_radio = ctk.CTkRadioButton(fr, text=txt, variable=self.mode_var, value=val,
                               font=ctk.CTkFont("Segoe UI", 12),
                               fg_color=ACCENT, hover_color=ACCENT,
                               text_color=FG,
                               command=self._on_mode_change)
            _mode_radio.grid(row=0, column=0, padx=10, pady=4)
            if val == "batch":
                self._mode_batch_radio = _mode_radio
            ctk.CTkLabel(fr, text=sub, font=ctk.CTkFont("Segoe UI", 10),
                         text_color=FG2).grid(row=1, column=0)

        # ── Dil ──────────────────────────────────────────────────────────────
        sep()
        section("DİL")
        lbl("Kaynak dil")
        self.src_var = ctk.StringVar(value="English")
        combo(self.src_var, LANGUAGES)
        lbl("Hedef dil")
        self.tgt_var = ctk.StringVar(value="Turkish")
        combo(self.tgt_var, LANGUAGES)

        lbl("İçerik türü")
        self.content_type_var = ctk.StringVar(value="Otomatik")
        schema_names = [v["name"] for v in CONTENT_SCHEMAS.values()]
        combo(self.content_type_var, schema_names)

        lbl("Argo / Küfür")
        self.profanity_var = ctk.StringVar(value="Orta")
        combo(self.profanity_var, ["Hafif", "Orta", "Sert"])

        # ── Klasörler ─────────────────────────────────────────────────────────
        sep()
        section("KLASÖRLER")
        for lbl_txt, attr, default in [
            ("Giriş klasörü (.srt)", "input_var",  ""),
            ("Çıkış klasörü",        "output_var", ""),
        ]:
            is_input = "input" in attr
            lbl(lbl_txt)
            var = ctk.StringVar(value=default)
            setattr(self, attr, var)
            row_fr = ctk.CTkFrame(sb, fg_color="transparent")
            row_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,2)); r += 1
            row_fr.grid_columnconfigure(0, weight=1)
            entry = ctk.CTkEntry(row_fr, textvariable=var, height=36,
                         font=ctk.CTkFont("Segoe UI", 11),
                         fg_color=CARD, border_color=BORDER,
                         text_color=FG)
            entry.grid(row=0, column=0, sticky="ew")
            if is_input:
                self.input_entry = entry
                entry.bind("<FocusIn>", lambda _e: self._on_input_entry_focus_in())
                entry.bind("<FocusOut>", lambda _e: self._on_input_entry_edited())
                entry.bind("<Return>", lambda _e: self._on_input_entry_edited())
            ctk.CTkButton(row_fr, text="…", width=36, height=36,
                          font=ctk.CTkFont("Segoe UI", 13),
                          fg_color=BORDER, hover_color=ACCENT,
                          command=lambda v=var, inp=is_input: self._pick_folder(v, inp)
                          ).grid(row=0, column=1, padx=(6,0))

        # Aynı Klasöre Kaydet: açıksa Çıkış klasörü alanı YOK SAYILIR, her dosyanın
        # çıktısı KENDİ geldiği klasöre kaydedilir — 3-4 ayrı klasörden dosya
        # eklenip tek seferde çevrildiğinde her biri kendi klasörüne geri döner.
        self.same_folder_var = ctk.BooleanVar(value=False)
        sf_fr = ctk.CTkFrame(sb, fg_color="transparent")
        sf_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        sf_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(sf_fr, text="", variable=self.same_folder_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT).grid(row=0, column=0)
        ctk.CTkLabel(sf_fr, text="Aynı Klasöre Kaydet",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="Açıksa Çıkış klasörü YOK SAYILIR — her dosyanın\nçıktısı KENDİ geldiği klasöre, kendi adıyla\nyazılır. Farklı klasörlerden eklenen dosyalar\nkendi klasörüne geri döner. (Kaynak zaten .srt\nise çakışmayı önlemek için <isim>.tr.srt kullanılır.)",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # Dosya seç butonu (klasör yerine tek/çoklu dosya)
        pick_fr = ctk.CTkFrame(sb, fg_color="transparent")
        pick_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(4,2)); r += 1
        pick_fr.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(pick_fr, text="📄  Dosya Seç (.srt/.vtt/.ass)", height=34,
                      font=ctk.CTkFont("Segoe UI", 12),
                      fg_color=BORDER, hover_color=ACCENT,
                      command=self._pick_files).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(pick_fr, text="📂  Klasörler Ekle", height=34,
                      font=ctk.CTkFont("Segoe UI", 12),
                      fg_color=BORDER, hover_color=ACCENT,
                      command=self._add_folder_files).grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.clear_files_btn = ctk.CTkButton(pick_fr, text="X", width=34, height=34,
                      font=ctk.CTkFont("Segoe UI", 13),
                      fg_color=CARD, hover_color="#c0392b",
                      command=self._clear_selected_files)
        # shown only when files are selected

        self.file_info_var = ctk.StringVar(value="")
        info_fr = ctk.CTkFrame(sb, fg_color="transparent")
        info_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(2,6)); r += 1
        info_fr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(info_fr, textvariable=self.file_info_var,
                     font=ctk.CTkFont("Segoe UI", 11), text_color=GREEN,
                     wraplength=220, justify="left").grid(row=0, column=0, sticky="w")
        self.clear_info_btn = ctk.CTkButton(info_fr, text="Temizle ✕", height=24,
                      font=ctk.CTkFont("Segoe UI", 10),
                      fg_color="transparent", hover_color=CARD,
                      text_color=GREEN, command=self._clear_selected_files)
        # shown only when files are selected

        self.clean_sdh_var = ctk.BooleanVar(value=False)
        sdh_fr = ctk.CTkFrame(sb, fg_color="transparent")
        sdh_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        sdh_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(sdh_fr, text="", variable=self.clean_sdh_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT).grid(row=0, column=0)
        ctk.CTkLabel(sdh_fr, text="SDH Temizle",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="[Steve sighs], [woman speaking] gibi\nses açıklama satırlarını çıktıdan siler.",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # ── Kalite özellikleri ────────────────────────────────────────────────
        sep()
        section("KALİTE")

        # Zincirleme Bağlam (sync modda önceki chunk çevirileri bağlam olur)
        self.chain_ctx_var = ctk.BooleanVar(value=True)
        chain_fr = ctk.CTkFrame(sb, fg_color="transparent")
        chain_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        chain_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(chain_fr, text="", variable=self.chain_ctx_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT).grid(row=0, column=0)
        ctk.CTkLabel(chain_fr, text="Zincirleme Bağlam",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="Anında modda model kendi önceki\nçevirilerini görür: terim, ton ve sen/siz\ntutarlılığı artar. (Dosya içi sıralı işler)",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # Ön-Bağlam Analizi (hybrid kapalıyken dosya özeti çıkarır)
        self.precontext_var = ctk.BooleanVar(value=True)
        pctx_fr = ctk.CTkFrame(sb, fg_color="transparent")
        pctx_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        pctx_fr.grid_columnconfigure(1, weight=1)
        self.precontext_switch = ctk.CTkSwitch(pctx_fr, text="", variable=self.precontext_var,
                                               width=44, height=22,
                                               fg_color=BORDER, progress_color=ACCENT,
                                               command=self._on_precontext_toggle)
        self.precontext_switch.grid(row=0, column=0)
        ctk.CTkLabel(pctx_fr, text="Ön-Bağlam Analizi",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="Çeviriden önce dosyayı hızlıca okur:\nözet, karakterler, hitap (sen/siz) haritası\nve sabit terimler çıkarılıp prompt'a eklenir.\n(Yardımcı Analiz kapalıyken devreye girer)",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # Dizi Hafızası (bölümler arası terim/karakter/sen-siz tutarlılığı)
        self.series_memory_var = ctk.BooleanVar(value=True)
        smem_fr = ctk.CTkFrame(sb, fg_color="transparent")
        smem_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        smem_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(smem_fr, text="", variable=self.series_memory_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT).grid(row=0, column=0)
        ctk.CTkLabel(smem_fr, text="Dizi Hafızası",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="Aynı dizinin bölümleri arasında terim,\nkarakter ve sen/siz kararlarını taşır.\nDosya adından S01E05 tespit edilir;\nilk bölümün kararları sabit kalır.",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # Bağlam İncelemesi (Batch sonrası ikinci geçiş)
        self.review_pass_var = ctk.BooleanVar(value=True)
        rev_fr = ctk.CTkFrame(sb, fg_color="transparent")
        rev_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        rev_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(rev_fr, text="", variable=self.review_pass_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT).grid(row=0, column=0)
        ctk.CTkLabel(rev_fr, text="Bağlam İncelemesi (Batch)",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="Batch çevirisi bitince ana model dosyayı\nkaynakla karşılaştırıp baştan sona okur:\nterim/hitap tutarsızlıklarını ve çeviri\nhatalarını düzeltir. (~%40-60 ek maliyet)",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # Terim Normalizasyonu (karışık-terim otomatik düzeltme — YALNIZCA sızıntı sınıfı)
        self.term_normalize_var = ctk.BooleanVar(value=False)
        tn_fr = ctk.CTkFrame(sb, fg_color="transparent")
        tn_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        tn_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(tn_fr, text="", variable=self.term_normalize_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT).grid(row=0, column=0)
        ctk.CTkLabel(tn_fr, text="Terim Normalizasyonu",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="Dosya içinde bir özel ismin (Troy/Truva gibi)\nİNGİLİZCE biçimde kalmış (sızıntı) örneklerini,\nyalnızca doğru Türkçe biçim başka yerde açıkça\nvarsa otomatik düzeltir. Belirsiz durumlara\ndokunmaz. (gpt-5.4-mini ile)",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # İki-Dalgalı Zincirli Batch (B3)
        self.twowave_var = ctk.BooleanVar(value=False)
        tw_fr = ctk.CTkFrame(sb, fg_color="transparent")
        tw_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        tw_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(tw_fr, text="", variable=self.twowave_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT).grid(row=0, column=0)
        ctk.CTkLabel(tw_fr, text="İki-Dalgalı Zincirli Batch",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="YALNIZCA Batch+Hybrid modda. Dosyayı iki dalgaya\nböler; ilk dalga bitince çevirilerini ikinci dalgaya\nbağlam verir (batch'in eksik olduğu zincirleme).\nKaliteyi artırır ama BEKLEME SÜRESİNİ ~2×'ler\n(iki sıralı batch). Uzun/önemli dosyalar için.",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # Critic Pass
        self.critic_var = ctk.BooleanVar(value=True)
        critic_fr = ctk.CTkFrame(sb, fg_color="transparent")
        critic_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        critic_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(critic_fr, text="", variable=self.critic_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT,
                      command=self._sync_helper_role_controls).grid(row=0, column=0)
        ctk.CTkLabel(critic_fr, text="Critic Pass",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="gpt-5.4-mini hataları otomatik düzeltir:\ntransliterasyon, yanlış register.",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # Polish Pass
        self.polish_var = ctk.BooleanVar(value=False)
        polish_fr = ctk.CTkFrame(sb, fg_color="transparent")
        polish_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        polish_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(polish_fr, text="", variable=self.polish_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT,
                      command=self._sync_helper_role_controls).grid(row=0, column=0)
        ctk.CTkLabel(polish_fr, text="Polish Pass",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="Çeviri bittikten sonra gpt-5.4-mini ile\nikinci geçiş — doğal Türkçeye çevirir.",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # QC Kontrolü
        self.qc_var = ctk.BooleanVar(value=False)
        qc_fr = ctk.CTkFrame(sb, fg_color="transparent")
        qc_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        qc_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(qc_fr, text="", variable=self.qc_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT,
                      command=self._sync_helper_role_controls).grid(row=0, column=0)
        ctk.CTkLabel(qc_fr, text="QC Kontrolü",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="gpt-5.4-mini çeviriyi inceler, şüpheli\nsatırları işaretler. Onayınla düzeltir.",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # Native Okuyucu Pass
        self.native_var = ctk.BooleanVar(value=False)
        native_fr = ctk.CTkFrame(sb, fg_color="transparent")
        native_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        native_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(native_fr, text="", variable=self.native_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT).grid(row=0, column=0)
        ctk.CTkLabel(native_fr, text="🇹🇷 Native Okuyucu",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="Türk izleyici gözüyle 'çevrilmiş gibi\nduran' satırları tespit edip doğallaştırır.",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # Geri Çeviri Anlam Kontrolü (Türkçe→İngilizce geri çeviri, anlam sapması)
        self.backtrans_var = ctk.BooleanVar(value=False)
        bt_fr = ctk.CTkFrame(sb, fg_color="transparent")
        bt_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        bt_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(bt_fr, text="", variable=self.backtrans_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT).grid(row=0, column=0)
        ctk.CTkLabel(bt_fr, text="Geri Çeviri Anlam Kontrolü",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="Türkçeyi tekrar İngilizceye çevirip anlamı\nkaynaktan SAPAN satırları yakalar; rapora ve\nlog'a yazar — çeviriye DOKUNMAZ. Gerçek\nyanlış çevirileri bulur. (Ek maliyet)",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # Ham Çeviri Yedeği (kalite geçişlerinden önceki çeviriyi .ham.srt'e kaydeder)
        self.backup_raw_var = ctk.BooleanVar(value=True)
        bk_fr = ctk.CTkFrame(sb, fg_color="transparent")
        bk_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        bk_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(bk_fr, text="", variable=self.backup_raw_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT).grid(row=0, column=0)
        ctk.CTkLabel(bk_fr, text="Ham Çeviri Yedeği (.ham.srt)",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="Kalite geçişleri (critic/polish/native/geri\nçeviri/QC) uygulanMADAN önceki ham çeviriyi\n<isim>.ham.srt olarak ayrıca kaydeder. Ana\nçıktıya dokunulmaz — bir geçiş bozarsa ham\nhali elinde kalır.",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # Auto-Glossary
        self.auto_glossary_var = ctk.BooleanVar(value=False)
        ag_fr = ctk.CTkFrame(sb, fg_color="transparent")
        ag_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        ag_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(ag_fr, text="", variable=self.auto_glossary_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT).grid(row=0, column=0)
        ctk.CTkLabel(ag_fr, text="Auto-Glossary",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="Çeviriden sözlüğe eklenecek terimleri\notomatik önerir. (gpt-5.4-mini ile)",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # Satır Kırma
        self.linebreak_var = ctk.BooleanVar(value=False)
        lb_fr = ctk.CTkFrame(sb, fg_color="transparent")
        lb_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        lb_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(lb_fr, text="", variable=self.linebreak_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT).grid(row=0, column=0)
        ctk.CTkLabel(lb_fr, text="Satır Kırma",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="42+ karakterlik satırları virgül/\nbağlaçtan böler. (EBU standardı)",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # Parçalı Cue Birleştir (Amazon vb. kelime-kelime bölünmüş altyazılar)
        self.merge_cues_var = ctk.BooleanVar(value=False)
        mc_fr = ctk.CTkFrame(sb, fg_color="transparent")
        mc_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        mc_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(mc_fr, text="", variable=self.merge_cues_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT).grid(row=0, column=0)
        ctk.CTkLabel(mc_fr, text="Parçalı Cue Birleştir",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="'Peki, ananla ne yapacaksın' / 'ki?' gibi\nkelime kelime bölünmüş ardışık cue'ları\ntek bloğa toplar. Senkron korunur; sadece\ndevam eden (cümle bitmeyen) satırlar birleşir.",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # AI Akıllı Segmentasyon (yardımcı model: anlamsal gruplama + öğe-bilinçli kırma)
        self.ai_segment_var = ctk.BooleanVar(value=False)
        ais_fr = ctk.CTkFrame(sb, fg_color="transparent")
        ais_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        ais_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(ais_fr, text="", variable=self.ai_segment_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT).grid(row=0, column=0)
        ctk.CTkLabel(ais_fr, text="AI Akıllı Segmentasyon",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="Üstteki birleştirmenin AI'lı sürümü: yardımcı\nmodel cue'ları ANLAMCA gruplar, satırları\nöğe sınırından kırar. Zamanlama/okuma hızı\ndeterministik korunur; kelimeler değişmez.\nAçıksa hızlı birleştirmenin yerine geçer\n(hata/anahtar yoksa ona düşer). (gpt-5.4-mini)",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # Okuma Hızı Kısaltma (reading-speed condensation)
        self.condense_var = ctk.BooleanVar(value=False)
        cd_fr = ctk.CTkFrame(sb, fg_color="transparent")
        cd_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        cd_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkSwitch(cd_fr, text="", variable=self.condense_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT).grid(row=0, column=0)
        ctk.CTkLabel(cd_fr, text="Okuma Hızı Kısaltma",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(sb, text="Ekrana sığmayan (çok hızlı) satırları\nanlamı koruyarak kısaltır. (gpt-5.4-mini ile)",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        # ── Yardımcı Analiz (gpt-5.4-mini) ────────────────────────────────────
        sep()
        self.hybrid_var = ctk.BooleanVar(value=False)
        mm_hdr = ctk.CTkFrame(sb, fg_color="transparent")
        mm_hdr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        mm_hdr.grid_columnconfigure(1, weight=1)
        self.hybrid_switch = ctk.CTkSwitch(mm_hdr, text="", variable=self.hybrid_var,
                                           width=44, height=22,
                                           fg_color=BORDER, progress_color=ACCENT,
                                           command=self._toggle_hybrid)
        self.hybrid_switch.grid(row=0, column=0)
        ctk.CTkLabel(mm_hdr, text="Yardimci Analiz",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=ACCENT).grid(row=0, column=1, sticky="w", padx=8)

        ctk.CTkLabel(sb, text="Çevirmeden önce filmi analiz eder:\nkarakter sesleri, ton, zorunlu terimler.\nBu bağlamla OpenAI çevirisi çok daha kaliteli.",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).grid(
                     row=r, column=0, sticky="w", padx=4, pady=(0,8)); r += 1

        self.hybrid_frame = ctk.CTkFrame(sb, fg_color="transparent")
        self.hybrid_frame.grid(row=r, column=0, sticky="ew"); r += 1
        self.hybrid_frame.grid_columnconfigure(0, weight=1)
        self.hybrid_frame.grid_remove()

        hfr = self.hybrid_frame

        def hf_lbl(txt):
            lbl = ctk.CTkLabel(hfr, text=txt, font=ctk.CTkFont("Segoe UI", 12),
                               text_color=FG2)
            lbl.pack(anchor="w", padx=4, pady=(6,2))
            return lbl

        def hf_entry(show=None):
            e = ctk.CTkEntry(hfr, show=show or "", height=36,
                             font=ctk.CTkFont("Segoe UI", 12),
                             fg_color=CARD, border_color=BORDER, text_color=FG)
            e.pack(fill="x", padx=4, pady=(0,2))
            return e

        self.helper_key_label = hf_lbl("Analiz / kalite API Key (boş = ana OpenAI anahtarı)")
        self.helper_key_entry = hf_entry(show="•")
        hf_lbl("External Project Path")
        path_fr = ctk.CTkFrame(hfr, fg_color="transparent")
        path_fr.pack(fill="x", padx=4)
        path_fr.grid_columnconfigure(0, weight=1)
        self.ext_project_path_var = ctk.StringVar(value=r"C:\Users\T\Desktop\PROJE\Altyazı Çevirisi")
        ctk.CTkEntry(path_fr, textvariable=self.ext_project_path_var, height=36,
                     font=ctk.CTkFont("Segoe UI", 11),
                     fg_color=CARD, border_color=BORDER,
                     text_color=FG).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(path_fr, text="…", width=36, height=36,
                      fg_color=BORDER, hover_color=ACCENT,
                      command=self._pick_project_path).grid(row=0, column=1, padx=(6,0))
        # ── 4 Bağımsız Yardımcı Model Seçimi ──────────────────────────────
        self.helper_roles = {
            "analysis": "Yardımcı Analiz Modeli",
            "critic": "Critic Pass Modeli",
            "polish": "Polish Pass Modeli",
            "qc": "Kalite Kontrol (QC) Modeli"
        }

        self.helper_model_vars = {}
        self.helper_role_key_vars = {}
        self.helper_custom_provider_vars = {}
        self.helper_custom_model_vars = {}
        self.helper_custom_url_vars = {}
        self.helper_custom_key_vars = {}
        self.helper_custom_frames = {}
        self.helper_role_labels = {}
        self.helper_role_combos = {}
        self.helper_role_containers = {}

        for role, label_text in self.helper_roles.items():
            role_label = hf_lbl(label_text)
            self.helper_role_labels[role] = role_label
            role_container = ctk.CTkFrame(hfr, fg_color="transparent")
            role_container.pack(fill="x", pady=(0,2))
            self.helper_role_containers[role] = role_container

            mvar = ctk.StringVar(value="gpt-5.4-mini")
            self.helper_model_vars[role] = mvar

            combo = ctk.CTkComboBox(role_container, variable=mvar,
                            values=HELPER_MODEL_OPTIONS,
                            height=36, font=ctk.CTkFont("Segoe UI", 12),
                            fg_color=CARD, border_color=BORDER,
                            button_color=BORDER, button_hover_color=ACCENT,
                            dropdown_fg_color=CARD, text_color=FG,
                            state="readonly",
                            command=lambda _choice, r=role: self._on_helper_model_change_role(r))
            combo.pack(fill="x", padx=4, pady=(0,2))
            self.helper_role_combos[role] = combo

            lbl_role_key = ctk.CTkLabel(role_container, text="API Anahtarı (boş = üstteki genel anahtar)", font=ctk.CTkFont("Segoe UI", 11), text_color=FG2)
            lbl_role_key.pack(anchor="w", padx=4, pady=(2,1))
            kvar_role = ctk.StringVar()
            self.helper_role_key_vars[role] = kvar_role
            ctk.CTkEntry(role_container, textvariable=kvar_role, show="•", height=32,
                         font=ctk.CTkFont("Segoe UI", 11),
                         fg_color=CARD, border_color=BORDER, text_color=FG).pack(fill="x", padx=4, pady=(0,2))

            # Özel Model Ayarları Çerçevesi (Gizli/Açık)
            c_frame = ctk.CTkFrame(role_container, fg_color="transparent")
            self.helper_custom_frames[role] = c_frame

            # Provider
            lbl_custom_prov = ctk.CTkLabel(c_frame, text="Özel Model Sağlayıcı", font=ctk.CTkFont("Segoe UI", 11), text_color=FG2)
            lbl_custom_prov.pack(anchor="w", padx=4, pady=(2,1))
            pvar = ctk.StringVar(value="anthropic")
            self.helper_custom_provider_vars[role] = pvar

            ctk.CTkComboBox(c_frame, variable=pvar,
                            values=["openai", "anthropic", "deepseek", "bedrock"],
                            height=32, font=ctk.CTkFont("Segoe UI", 11),
                            fg_color=CARD, border_color=BORDER,
                            button_color=BORDER, button_hover_color=ACCENT,
                            dropdown_fg_color=CARD, text_color=FG,
                            state="readonly").pack(fill="x", padx=4, pady=(0,1))

            # Model Name
            lbl_custom_name = ctk.CTkLabel(c_frame, text="Özel Model Adı", font=ctk.CTkFont("Segoe UI", 11), text_color=FG2)
            lbl_custom_name.pack(anchor="w", padx=4, pady=(2,1))
            nvar = ctk.StringVar(value="claude-haiku-4-5-20251001")
            self.helper_custom_model_vars[role] = nvar
            ctk.CTkEntry(c_frame, textvariable=nvar, height=32,
                         font=ctk.CTkFont("Segoe UI", 11),
                         fg_color=CARD, border_color=BORDER, text_color=FG).pack(fill="x", padx=4, pady=(0,1))

            # Base URL
            lbl_custom_url = ctk.CTkLabel(c_frame, text="Özel API URL", font=ctk.CTkFont("Segoe UI", 11), text_color=FG2)
            lbl_custom_url.pack(anchor="w", padx=4, pady=(2,1))
            uvar = ctk.StringVar(value="https://147ai.online/v1/messages")
            self.helper_custom_url_vars[role] = uvar
            ctk.CTkEntry(c_frame, textvariable=uvar, height=32,
                         font=ctk.CTkFont("Segoe UI", 11),
                         fg_color=CARD, border_color=BORDER, text_color=FG).pack(fill="x", padx=4, pady=(0,1))

            # API Key
            lbl_custom_key = ctk.CTkLabel(c_frame, text="Özel API Anahtarı (boş = genel yardımcı anahtar)", font=ctk.CTkFont("Segoe UI", 11), text_color=FG2)
            lbl_custom_key.pack(anchor="w", padx=4, pady=(2,1))
            kvar = ctk.StringVar()
            self.helper_custom_key_vars[role] = kvar
            ctk.CTkEntry(c_frame, textvariable=kvar, show="•", height=32,
                         font=ctk.CTkFont("Segoe UI", 11),
                         fg_color=CARD, border_color=BORDER, text_color=FG).pack(fill="x", padx=4, pady=(0,2))
        self._sync_helper_role_controls()
        hf_lbl("Analiz derinligi")
        self.analysis_depth_var = ctk.StringVar(value="Standart")
        ctk.CTkComboBox(hfr, variable=self.analysis_depth_var,
                        values=["Standart", "Gelismis", "Maksimum"],
                        height=36, font=ctk.CTkFont("Segoe UI", 12),
                        fg_color=CARD, border_color=BORDER,
                        button_color=BORDER, button_hover_color=ACCENT,
                        dropdown_fg_color=CARD, text_color=FG,
                        state="readonly").pack(fill="x", padx=4, pady=(0,2))
        ctk.CTkLabel(hfr,
                     text="Gelismis ve Maksimum daha fazla chunk/token kullanir; karakter, terim, argo, sahne ve risk notlarini daha derin cikarir.",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=FG2,
                     justify="left", wraplength=260).pack(fill="x", padx=4, pady=(0,6))
        hf_lbl("Çeviri stili")
        self.style_var = ctk.StringVar(value="natural")
        ctk.CTkComboBox(hfr, variable=self.style_var,
                        values=["natural", "formal", "neutral", "cinematic"],
                        height=36, font=ctk.CTkFont("Segoe UI", 12),
                        fg_color=CARD, border_color=BORDER,
                        button_color=BORDER, button_hover_color=ACCENT,
                        dropdown_fg_color=CARD, text_color=FG,
                        state="readonly").pack(fill="x", padx=4, pady=(0,2))
        hf_lbl("Glossary dosyası (opsiyonel)")
        gf = ctk.CTkFrame(hfr, fg_color="transparent")
        gf.pack(fill="x", padx=4)
        gf.grid_columnconfigure(0, weight=1)
        self.glossary_var = ctk.StringVar()
        ctk.CTkEntry(gf, textvariable=self.glossary_var, height=36,
                     font=ctk.CTkFont("Segoe UI", 11),
                     fg_color=CARD, border_color=BORDER,
                     text_color=FG).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(gf, text="…", width=36, height=36,
                      fg_color=BORDER, hover_color=ACCENT,
                      command=self._pick_glossary).grid(row=0, column=1, padx=(6,0))

        # ── Butonlar ──────────────────────────────────────────────────────────
        sep()
        # Başlat + Test yan yana
        btn_row = ctk.CTkFrame(sb, fg_color="transparent")
        btn_row.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,6)); r += 1
        btn_row.grid_columnconfigure(0, weight=3)
        btn_row.grid_columnconfigure(1, weight=0)
        btn_row.grid_columnconfigure(2, weight=0)
        self.start_btn = ctk.CTkButton(
            btn_row, text="▶  Çeviriyi Başlat", height=44,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color=ACCENT, hover_color="#5a4fd1",
            command=self._start)
        self.start_btn.grid(row=0, column=0, sticky="ew", padx=(0,4))
        ctk.CTkButton(
            btn_row, text="🧪", height=44, width=44,
            font=ctk.CTkFont("Segoe UI", 16),
            fg_color=CARD, hover_color=BORDER,
            command=self._test_translate).grid(row=0, column=1, padx=(0,4), sticky="ew")

        ctk.CTkButton(
            btn_row, text="💲 Maliyet", height=44, width=60,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color="#006400", hover_color="#008000",
            command=self._show_cost_estimate).grid(row=0, column=2, sticky="ew")

        # Bildirimler switch
        notif_fr = ctk.CTkFrame(sb, fg_color="transparent")
        notif_fr.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,4)); r += 1
        notif_fr.grid_columnconfigure(1, weight=1)
        self.notify_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(notif_fr, text="", variable=self.notify_var,
                      width=44, height=22,
                      fg_color=BORDER, progress_color=ACCENT).grid(row=0, column=0)
        ctk.CTkLabel(notif_fr, text="🔔  Masaüstü bildirimi",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=FG2).grid(row=0, column=1, sticky="w", padx=8)

        self.resume_btn = ctk.CTkButton(
            sb, text="↺  Batch'i Devam Ettir", height=38,
            font=ctk.CTkFont("Segoe UI", 12),
            fg_color=CARD, hover_color=BORDER,
            command=self._resume)
        self.resume_btn.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,6)); r += 1

        self.jsonl_btn = ctk.CTkButton(
            sb, text="📂  JSONL → SRT", height=38,
            font=ctk.CTkFont("Segoe UI", 12),
            fg_color=CARD, hover_color=BORDER,
            command=self._import_jsonl)
        self.jsonl_btn.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,6)); r += 1

        self.postprocess_btn = ctk.CTkButton(
            sb, text="✦  SRT Post-İşle", height=38,
            font=ctk.CTkFont("Segoe UI", 12),
            fg_color=CARD, hover_color=BORDER,
            command=self._post_process_existing)
        self.postprocess_btn.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,6)); r += 1

        self.report_btn = ctk.CTkButton(
            sb, text="📊  Kalite Raporu", height=38,
            font=ctk.CTkFont("Segoe UI", 12),
            fg_color=CARD, hover_color=BORDER,
            command=self._open_quality_report)
        self.report_btn.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,6)); r += 1

        # ── Advanced Settings ─────────────────────────────────────────────────
        self.adv_settings_btn = ctk.CTkButton(
            sb, text="⚙️  Gelişmiş Ayarlar", height=38,
            font=ctk.CTkFont("Segoe UI", 12),
            fg_color=CARD, hover_color=BORDER,
            command=self._show_advanced_settings)
        self.adv_settings_btn.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,6)); r += 1

        self.pm_btn = ctk.CTkButton(
            sb, text="🧠  Proje Hafızası", height=38,
            font=ctk.CTkFont("Segoe UI", 12),
            fg_color=CARD, hover_color=BORDER,
            command=self._show_project_memory)
        self.pm_btn.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,6)); r += 1

        self.pause_btn = ctk.CTkButton(
            sb, text="\u23f8  Duraklat", height=38,
            font=ctk.CTkFont("Segoe UI", 12),
            fg_color=CARD, hover_color=BORDER,
            state="disabled",
            command=self._toggle_pause_between_files)
        self.pause_btn.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,6)); r += 1

        self.stop_btn = ctk.CTkButton(
            sb, text="■  Durdur", height=38,
            font=ctk.CTkFont("Segoe UI", 12),
            fg_color="#3a1a1a", hover_color="#5a2020",
            text_color=RED, state="disabled",
            command=self._stop)
        self.stop_btn.grid(row=r, column=0, sticky="ew", padx=4, pady=(0,12)); r += 1

    # ── Sağ panel ─────────────────────────────────────────────────────────────
    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=(6,12), pady=12)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(4, weight=1)

        # ── Stats kartları ────────────────────────────────────────────────────
        sf = ctk.CTkFrame(main, fg_color=PANEL, corner_radius=12)
        sf.grid(row=0, column=0, sticky="ew", pady=(0,10))

        stats = [
            ("📄 Toplam Dosya", "stat_files",  FG),
            ("📊 Toplam Satır", "stat_blocks", FG),
            ("✓ Tamamlanan",   "stat_done",   GREEN),
            ("✗ Hatalı",       "stat_fail",   RED),
            ("💾 TM Vuruş",     "stat_tm",     "#3498DB"),
            ("💰 Token",        "stat_tokens", YELLOW),
        ]
        sf.grid_columnconfigure((0,1,2,3,4,5), weight=1)
        for i, (name, attr, color) in enumerate(stats):
            c = ctk.CTkFrame(sf, fg_color=CARD, border_color=BORDER, border_width=1,
                           corner_radius=8)
            c.grid(row=0, column=i, padx=8, pady=16, sticky="nsew")
            c.grid_columnconfigure(0, weight=1)

            # Store reference for hover effects
            setattr(self, f"{attr}_frame", c)

            # Hover effect bindings
            def on_hover_enter(e, frame=c, attr=attr):
                frame.configure(border_color=ACCENT, border_width=2)
            def on_hover_leave(e, frame=c):
                frame.configure(border_color=BORDER, border_width=1)

            c.bind("<Enter>", on_hover_enter)
            c.bind("<Leave>", on_hover_leave)

            var = ctk.StringVar(value="—")
            setattr(self, attr+"_var", var)

            lbl = ctk.CTkLabel(c, textvariable=var,
                             font=ctk.CTkFont("Segoe UI", 26, "bold"),
                             text_color=color)
            lbl.pack(pady=(12,4))

            # Store label ref for animation
            setattr(self, f"{attr}_lbl", lbl)

            if attr == "stat_tokens":
                self.stat_tokens_sub_var = ctk.StringVar(value=name)
                ctk.CTkLabel(c, textvariable=self.stat_tokens_sub_var,
                             font=ctk.CTkFont("Segoe UI", 10),
                             text_color=FG2).pack(pady=(0,4))
                # Canvas for sparkline under token card
                import tkinter as tk
                self.stat_tokens_canvas = tk.Canvas(c, width=200, height=30,
                                                   bg=CARD, highlightthickness=0,
                                                   relief="flat", bd=0)
                self.stat_tokens_canvas.pack(padx=8, pady=(0,8), fill="x")
                self._token_sparkline_points = []
            else:
                ctk.CTkLabel(c, text=name,
                             font=ctk.CTkFont("Segoe UI", 10),
                             text_color=FG2).pack(pady=(0,12))

            if i < 5:
                ctk.CTkFrame(sf, width=1, fg_color=BORDER).grid(
                    row=0, column=i, sticky="nse", pady=12)

        # ── Progress ──────────────────────────────────────────────────────────
        pb_fr = ctk.CTkFrame(main, fg_color=PANEL, corner_radius=12)
        pb_fr.grid(row=1, column=0, sticky="ew", pady=(0,10))
        pb_fr.grid_columnconfigure(0, weight=1)

        # Satır 0: faz adı (büyük + renkli) + hız + ETA + geçen zaman
        pb_top = ctk.CTkFrame(pb_fr, fg_color="transparent")
        pb_top.grid(row=0, column=0, sticky="ew", padx=16, pady=(12,2))
        pb_top.grid_columnconfigure(1, weight=1)
        self._phase_dot = ctk.CTkLabel(pb_top, text="●",
                                       font=ctk.CTkFont("Segoe UI", 11),
                                       text_color=FG2, width=16, anchor="w")
        self._phase_dot.grid(row=0, column=0, sticky="w")
        self._phase_lbl = ctk.CTkLabel(pb_top, text="Hazır",
                                       font=ctk.CTkFont("Segoe UI", 13, "bold"),
                                       text_color=FG2, anchor="w")
        self._phase_lbl.grid(row=0, column=1, sticky="w", padx=(4,0))

        # Speed and elapsed time display
        speed_elapsed_fr = ctk.CTkFrame(pb_top, fg_color="transparent")
        speed_elapsed_fr.grid(row=0, column=2, sticky="e", padx=(8,0))
        speed_elapsed_fr.grid_columnconfigure((0,1,2), weight=0)
        self.speed_lbl = ctk.CTkLabel(speed_elapsed_fr, text="",
                                      font=ctk.CTkFont("Segoe UI", 10),
                                      text_color=FG2)
        self.speed_lbl.grid(row=0, column=0, sticky="e", padx=(0,8))
        self.elapsed_lbl = ctk.CTkLabel(speed_elapsed_fr, text="",
                                        font=ctk.CTkFont("Segoe UI", 10),
                                        text_color=FG2)
        self.elapsed_lbl.grid(row=0, column=1, sticky="e", padx=(0,8))
        self.eta_lbl = ctk.CTkLabel(speed_elapsed_fr, text="",
                                    font=ctk.CTkFont("Segoe UI", 10),
                                    text_color=FG2)
        self.eta_lbl.grid(row=0, column=2, sticky="e")

        # Satır 1: detay (dosya adı, chunk ilerlemesi vb.)
        self.progress_lbl = ctk.CTkLabel(pb_fr, text="",
                                         font=ctk.CTkFont("Segoe UI", 11),
                                         text_color=FG2, anchor="w")
        self.progress_lbl.grid(row=1, column=0, sticky="ew", padx=20, pady=(0,4))

        # Overall progress bar
        self.progress = ctk.CTkProgressBar(pb_fr, height=8,
                                           progress_color=ACCENT,
                                           fg_color=BORDER)
        self.progress.grid(row=2, column=0, sticky="ew", padx=16, pady=(0,6))
        self.progress.set(0)

        # Per-file progress bar
        self.progress_file = ctk.CTkProgressBar(pb_fr, height=6,
                                                progress_color=GREEN,
                                                fg_color=BORDER)
        self.progress_file.grid(row=3, column=0, sticky="ew", padx=16, pady=(0,14))
        self.progress_file.set(0)
        self.progress_file.grid_remove()  # Hidden until processing starts

        # ── İş panosu (çalışma sırasında dosya başı ilerleme) ─────────────────
        self._job_board = ctk.CTkFrame(main, fg_color=PANEL, corner_radius=12)
        self._job_board.grid(row=2, column=0, sticky="ew", pady=(0,10))
        self._job_board.grid_columnconfigure(0, weight=1)
        self._job_board.grid_remove()

        jb_hdr = ctk.CTkFrame(self._job_board, fg_color="transparent", height=36)
        jb_hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(10,4))
        jb_hdr.grid_columnconfigure(0, weight=1)
        jb_hdr.grid_propagate(False)
        self._jb_title = ctk.CTkLabel(jb_hdr, text="DOSYALAR",
                                      font=ctk.CTkFont("Segoe UI", 11, "bold"),
                                      text_color=FG2)
        self._jb_title.grid(row=0, column=0, sticky="w")

        self._job_rows_frame = ctk.CTkScrollableFrame(
            self._job_board, fg_color="transparent", height=180,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=ACCENT)
        self._job_rows_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0,10))
        self._job_rows_frame.grid_columnconfigure(0, weight=1)
        self._job_rows: dict = {}   # filepath → {dot, phase, pb, frame}

        # ── Dosya listesi (per-file şema) ─────────────────────────────────────
        self._file_list_outer = ctk.CTkFrame(main, fg_color=PANEL, corner_radius=12)
        self._file_list_outer.grid(row=2, column=0, sticky="ew", pady=(0,10))
        self._file_list_outer.grid_columnconfigure(0, weight=1)
        self._file_list_outer.grid_remove()  # hidden until files loaded

        fl_hdr = ctk.CTkFrame(self._file_list_outer, fg_color="transparent", height=36)
        fl_hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(10,4))
        fl_hdr.grid_columnconfigure(0, weight=1)
        fl_hdr.grid_propagate(False)
        self._file_list_lbl = ctk.CTkLabel(fl_hdr, text="DOSYALAR",
                                            font=ctk.CTkFont("Segoe UI", 11, "bold"),
                                            text_color=FG2)
        self._file_list_lbl.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(fl_hdr, text="Tümüne Uygula", width=110, height=24,
                      font=ctk.CTkFont("Segoe UI", 10),
                      fg_color=CARD, hover_color=BORDER,
                      command=self._apply_schema_to_all).grid(row=0, column=1)

        self._file_rows_frame = ctk.CTkScrollableFrame(
            self._file_list_outer, fg_color="transparent", height=148,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=ACCENT)
        self._file_rows_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0,10))
        self._file_rows_frame.grid_columnconfigure(0, weight=1)
        self._file_schema_vars = {}

        # ── Log yeniden boyutlandırma tutamacı ──────────────────────────────────
        # Dosya listesi ile Log arasında sürüklenebilir ince bir çubuk: yukarı
        # çekince dosya listesi küçülür, Log büyür (Log zaten tek weight=1 satır
        # olduğu için pencereyi büyütünce otomatik genişliyordu — bu, kullanıcının
        # ELLE, pencereyi büyütmeden de ayarlayabilmesini sağlar).
        self._FILE_LIST_MIN_H = 40
        self._FILE_LIST_MAX_H = 500
        grip = ctk.CTkFrame(main, height=8, fg_color=BORDER, corner_radius=4,
                            cursor="sb_v_double_arrow")
        grip.grid(row=3, column=0, sticky="ew", pady=(0,6))
        grip.grid_propagate(False)

        def _grip_enter(_e):
            grip.configure(fg_color=ACCENT)

        def _grip_leave(_e):
            if not getattr(self, "_log_resize_dragging", False):
                grip.configure(fg_color=BORDER)

        def _grip_press(e):
            self._log_resize_dragging = True
            self._log_resize_start_y = e.y_root
            self._log_resize_start_h = self._file_rows_frame.cget("height")

        def _grip_drag(e):
            delta = e.y_root - self._log_resize_start_y
            new_h = max(self._FILE_LIST_MIN_H,
                       min(self._FILE_LIST_MAX_H, self._log_resize_start_h + delta))
            self._file_rows_frame.configure(height=new_h)

        def _grip_release(_e):
            self._log_resize_dragging = False
            grip.configure(fg_color=BORDER)
            try:
                self._save_settings()
            except Exception:
                pass

        grip.bind("<Enter>", _grip_enter)
        grip.bind("<Leave>", _grip_leave)
        grip.bind("<ButtonPress-1>", _grip_press)
        grip.bind("<B1-Motion>", _grip_drag)
        grip.bind("<ButtonRelease-1>", _grip_release)
        self._log_grip = grip

        # ── Log ───────────────────────────────────────────────────────────────
        log_fr = ctk.CTkFrame(main, fg_color=PANEL, corner_radius=12)
        log_fr.grid(row=4, column=0, sticky="nsew")
        log_fr.grid_columnconfigure(0, weight=1)
        log_fr.grid_rowconfigure(1, weight=1)

        log_hdr = ctk.CTkFrame(log_fr, fg_color="transparent", height=40)
        log_hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(10,0))
        log_hdr.grid_columnconfigure(0, weight=1)
        log_hdr.grid_propagate(False)
        log_hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(log_hdr, text="LOG",
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color=FG2).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(log_hdr, text="⬇ Alta git", width=82, height=26,
                      font=ctk.CTkFont("Segoe UI", 10),
                      fg_color=CARD, hover_color=BORDER,
                      command=self._pin_log_bottom).grid(row=0, column=1, padx=(0,4))
        ctk.CTkButton(log_hdr, text="Temizle", width=70, height=26,
                      font=ctk.CTkFont("Segoe UI", 10),
                      fg_color=CARD, hover_color=BORDER,
                      command=self._clear_log).grid(row=0, column=2)

        self.log_box = ctk.CTkTextbox(log_fr, font=ctk.CTkFont("Consolas", 11),
                                      fg_color=CARD, corner_radius=8,
                                      text_color=FG, wrap="word",
                                      activate_scrollbars=True)
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(6,12))
        self.log_box.configure(state="disabled")

        # Scroll kilidi: kullanıcı yukarı kaydırınca auto-scroll durur
        self._log_pinned = True
        self.log_box.bind("<MouseWheel>",
                          lambda e: self.after(80, self._check_log_pin))
        self.log_box.bind("<Button-4>",
                          lambda e: self.after(80, self._check_log_pin))
        self.log_box.bind("<Button-5>",
                          lambda e: self.after(80, self._check_log_pin))

    # ── Per-file şema ─────────────────────────────────────────────────────────
    def _populate_file_list(self, files: list):
        """Input klasörü seçilince her dosya için şema dropdown'u oluştur."""
        for w in self._file_rows_frame.winfo_children():
            w.destroy()
        self._file_schema_vars = {}
        schema_names = [v["name"] for v in CONTENT_SCHEMAS.values()]
        default = normalize_schema_name(self.content_type_var.get())
        for fp in sorted(files, key=lambda p: Path(p).name.lower()):
            row_fr = ctk.CTkFrame(self._file_rows_frame, fg_color=CARD, corner_radius=6)
            row_fr.pack(fill="x", padx=2, pady=(0, 3))
            row_fr.grid_columnconfigure(0, weight=1)
            name = Path(fp).name
            if len(name) > 40:
                name = "…" + name[-37:]
            ctk.CTkLabel(row_fr, text=name,
                         font=ctk.CTkFont("Segoe UI", 11),
                         text_color=FG, anchor="w").grid(
                         row=0, column=0, sticky="ew", padx=(10,4), pady=5)
            var = ctk.StringVar(value=default)
            self._file_schema_vars[fp] = var
            ctk.CTkOptionMenu(row_fr, variable=var, values=schema_names,
                              width=155, height=26,
                              font=ctk.CTkFont("Segoe UI", 10),
                              fg_color=BORDER, button_color=BORDER,
                              button_hover_color=ACCENT,
                              dropdown_fg_color=CARD, text_color=FG,
                              ).grid(row=0, column=1, padx=(4, 2), pady=4)
            # Dosya silme butonu
            ctk.CTkButton(row_fr, text="X", width=26, height=26,
                          font=ctk.CTkFont("Segoe UI", 11, "bold"),
                          fg_color="transparent", hover_color=BORDER,
                          text_color=WARN,
                          command=lambda p=fp: self._remove_file_from_list(p)
                          ).grid(row=0, column=2, padx=(0, 6), pady=4)
        self._file_list_lbl.configure(text=f"DOSYALAR ({len(files)})")
        self._job_board.grid_remove()   # iş panosu varsa gizle
        self._file_list_outer.grid()

    def _remove_file_from_list(self, filepath: str):
        """Seçili dosyayı listeden kaldır."""
        if filepath in self._selected_files:
            self._selected_files.remove(filepath)
        self._file_schema_vars.pop(filepath, None)
        remaining = list(self._selected_files)
        if remaining:
            self._refresh_selected_files_ui(f"Dosya listeden çıkarıldı: {Path(filepath).name}")
        else:
            self._clear_selected_files()

    def _dedupe_paths(self, paths: list) -> list:
        import os
        seen = set()
        out = []
        for p in paths:
            key = os.path.normcase(os.path.abspath(str(p)))
            if key in seen:
                continue
            seen.add(key)
            out.append(str(p))
        return out

    def _refresh_selected_files_ui(self, log_msg: str = ""):
        import os
        self._content_type_preflight_done = False
        files = self._dedupe_paths(self._selected_files)
        self._selected_files = files
        if not files:
            self._clear_selected_files()
            return
        try:
            common = os.path.commonpath(files)
            if not os.path.isdir(common):
                common = str(Path(common).parent)
            self.input_var.set(common)
        except Exception:
            self.input_var.set(str(Path(files[0]).parent))
        n = len(files)
        self._estimate_async(
            files,
            lambda tb, ek, n=n: f"📄  {n} dosya seçildi  •  {tb} satır  •  ~{ek} token")
        if log_msg:
            self._log(log_msg, "ok")
        self._populate_file_list(files)
        self.clear_files_btn.grid(row=0, column=1, padx=(6, 0))
        self.clear_info_btn.grid(row=0, column=1, sticky="e", padx=(4, 0))

    def _apply_schema_to_all(self):
        """Tüm dosyaları global şemaya sıfırla."""
        name = normalize_schema_name(self.content_type_var.get())
        self.content_type_var.set(name)
        for var in self._file_schema_vars.values():
            var.set(name)

    def _get_file_glossary(self, filepath: str) -> str:
        """Dosyanın şemasına göre glossary yolunu döndür.
        Glossary alanı klasör ise: <klasör>/<schema_key>.{json,txt,tsv,csv}
        Glossary alanı dosya ise: doğrudan o dosyayı kullan (tüm şemalar için)."""
        if threading.current_thread() is not threading.main_thread() and hasattr(self, "_active_snapshot") and self._active_snapshot:
            fg = self._active_snapshot.get("file_glossaries", {}).get(filepath)
            if fg is not None:
                return fg
            return self._active_snapshot.get("global_glossary_path", "")
        glossary_path = self.glossary_var.get().strip()
        if not glossary_path:
            return ""
        p = Path(glossary_path)
        if p.is_dir():
            schema_name = self._get_file_schema(filepath)["name"]
            schema_key  = next((k for k, v in CONTENT_SCHEMAS.items()
                                if v["name"] == schema_name), None)
            if schema_key:
                for ext in (".json", ".txt", ".tsv", ".csv"):
                    candidate = p / (schema_key + ext)
                    if candidate.exists():
                        return str(candidate)
            # Fallback: default glossary in the folder
            for fname in ("default.json", "default.txt", "glossary.json", "glossary.txt"):
                candidate = p / fname
                if candidate.exists():
                    return str(candidate)
            return ""
        return glossary_path  # regular single file — used for all schemas

    def _schema_by_name(self, name: str) -> dict:
        name = normalize_schema_name(name)
        for schema in CONTENT_SCHEMAS.values():
            if schema["name"] == name:
                return schema
        return CONTENT_SCHEMAS["auto"]

    def _merge_schema_glossary(self, glossary: dict, schema_dict: dict) -> dict:
        """Şemaya gömülü sözlüğü (ör. Warhammer terimleri) aktif sözlükle birleştirir.
        Dosya/kullanıcı sözlüğü öncelikli (şema değerini ezer). Hybrid akışlarda
        build_batch_requests şema almadığı için merge burada yapılır."""
        sg = (schema_dict or {}).get("glossary") or {}
        if not sg:
            return glossary or {}
        return {**sg, **(glossary or {})}

    def _get_file_schema(self, filepath: str) -> dict:
        """Dosyaya özgü şema varsa onu, yoksa global şemayı döndür."""
        if threading.current_thread() is not threading.main_thread() and hasattr(self, "_active_snapshot") and self._active_snapshot:
            fs = self._active_snapshot.get("file_schemas", {}).get(filepath)
            if fs:
                return fs
            return self._active_snapshot.get("schema") or self._schema_by_name("Otomatik")
        var = self._file_schema_vars.get(filepath)
        name = normalize_schema_name(var.get() if var else self.content_type_var.get())
        return self._schema_by_name(name)

    # ── UI Dispatcher & Thread Safety ─────────────────────────────────────────
    _post_ui = _post_ui

    def _drain_ui_queue(self):
        """Ana thread'de çalışır ve UI kuyruğundaki callback'leri FIFO sırasıyla tüketir.
        Kapanış durumunu kontrol eder, bir turda sınırlı sayıda callback çalıştırır.
        """
        if getattr(self, "_is_shutting_down", False):
            return

        max_per_tick = 50
        count = 0
        while count < max_per_tick:
            try:
                item = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            count += 1
            fn, args, kwargs = item
            try:
                if not getattr(self, "_is_shutting_down", False):
                    fn(*args, **kwargs)
            except Exception as e:
                try:
                    print(f"[UI Dispatcher Error] {fn}: {e}")
                except Exception:
                    pass

        if not getattr(self, "_is_shutting_down", False):
            try:
                self._drain_ui_queue_id = self.after(20, self._drain_ui_queue)
            except Exception:
                pass

    def _snap_get(self, key: str, default=None):
        """Snapshot'tan ayar değerini güvenli şekilde döndürür."""
        if hasattr(self, "_active_snapshot") and isinstance(self._active_snapshot, dict) and key in self._active_snapshot:
            return self._active_snapshot[key]
        return default

    def _take_run_snapshot(self) -> dict:
        """Ana thread'de çalışarak çeviri oturumu için gereken tüm UI ayarlarının
        saf Python nesnesi olarak kopyasını oluşturur. Worker thread'ler Tk variable .get()
        veya widget okumaları yapmak yerine bu snapshot'ı kullanır.
        """
        srt_files = self._get_srt_files()
        file_schemas = {}
        file_glossaries = {}
        for fp in srt_files:
            try:
                var_s = getattr(self, "_file_schema_vars", {}).get(fp)
                name_s = normalize_schema_name(var_s.get() if var_s else self.content_type_var.get())
                file_schemas[fp] = self._schema_by_name(name_s)
            except Exception:
                pass
            try:
                file_glossaries[fp] = self._get_file_glossary(fp)
            except Exception:
                pass

        helper_keys = {}
        helper_urls = {}
        helper_models = {}
        for role in ["analysis", "critic", "polish", "qc", "native", "condense", "review"]:
            try:
                helper_keys[role] = self._helper_api_key(role)
                helper_urls[role] = self._helper_api_base_url(role)
                helper_models[role] = self._helper_api_model(role)
            except Exception:
                pass

        return {
            "input_dir": self.input_var.get(),
            "output_dir": self.output_var.get(),
            "src_lang": self.src_var.get(),
            "tgt_lang": self.tgt_var.get(),
            "profanity": self.profanity_var.get(),
            "same_folder": self.same_folder_var.get(),
            "mode": self.mode_var.get(),
            "hybrid_mode": self.hybrid_var.get(),
            "auto_glossary": self.auto_glossary_var.get(),
            "analysis_depth": self.analysis_depth_var.get(),
            "ext_project_path": self.ext_project_path_var.get().strip(),
            "notify_desktop": self.notify_var.get(),
            "term_normalize": getattr(self, "term_normalize_var", None).get() if getattr(self, "term_normalize_var", None) else False,
            "critic": self.critic_var.get(),
            "polish": self.polish_var.get(),
            "native": self.native_var.get(),
            "qc": self.qc_var.get(),
            "condense": self.condense_var.get(),
            "review": self.review_pass_var.get(),
            "twowave": self.twowave_var.get(),
            "clean_sdh": self.clean_sdh_var.get(),
            "linebreak": self.linebreak_var.get(),
            "ai_segment": bool(getattr(self, "ai_segment_var", None) and self.ai_segment_var.get()),
            "merge_cues": bool(getattr(self, "merge_cues_var", None) and self.merge_cues_var.get()),
            "chain_ctx": bool(getattr(self, "chain_ctx_var", None) and self.chain_ctx_var.get()),
            "precontext": bool(getattr(self, "precontext_var", None) and self.precontext_var.get()),
            "series_memory": bool(getattr(self, "series_memory_var", None) and self.series_memory_var.get()),
            "main_api_key": self._main_api_key(),
            "main_api_base_url": self._main_api_base_url(),
            "main_model_name": self._main_model_name(),
            "schema": self._get_schema(),
            "global_glossary_path": self.glossary_var.get().strip(),
            "helper_keys": helper_keys,
            "helper_urls": helper_urls,
            "helper_models": helper_models,
            "file_schemas": file_schemas,
            "file_glossaries": file_glossaries,
        }

    # ── Log yardımcıları ──────────────────────────────────────────────────────
    def _log(self, msg, tag=""):
        import datetime
        icons = {"ok": "✓", "err": "✗", "warn": "⚠", "info": "›"}
        icon  = icons.get(tag, " ")
        if len(msg) > 500:
            msg = msg[:497] + "…"
        ts   = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"{icon}  {msg}\n"

        # Log dosyasına yaz (zaman damgası ile) — lock: concurrent worker thread'ler
        try:
            with self._log_lock:
                self._log_file.write(f"[{ts}] {icon}  {msg}\n")
                self._log_file.flush()
        except Exception:
            pass

        def _write():
            try:
                self.log_box.configure(state="normal")
                self.log_box.insert("end", line)
                if self._log_pinned:
                    self.log_box.see("end")
                self.log_box.configure(state="disabled")
            except Exception:
                pass

        _post_ui(self, _write)

    def _log_exc(self, label: str, exc: Exception):
        """Hata mesajını + kısa traceback'i loga yazar."""
        tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
        # Son 2 frame'i al (çok uzun olmasın)
        compact = "".join(tb_lines[-3:]).strip().replace("\n", " | ")
        self._log(f"{label}: {exc}", "err")
        self._log(f"  ↳ {compact}", "err")

    def _notify(self, title: str, msg: str):
        """Windows masaüstü bildirimi (ek bağımlılık gerektirmez)."""
        enabled = False
        if threading.current_thread() is threading.main_thread():
            try:
                enabled = bool(self.notify_var.get())
            except Exception:
                enabled = False
        elif hasattr(self, "_active_snapshot") and self._active_snapshot:
            enabled = bool(self._active_snapshot.get("notify_desktop"))
        if not enabled:
            return
        try:
            import subprocess
            safe_title = title.replace("'", "").replace('"', '')
            safe_msg   = msg.replace("'", "").replace('"', '')
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$n = [System.Windows.Forms.NotifyIcon]::new(); "
                "$n.Icon = [System.Drawing.SystemIcons]::Application; "
                "$n.Visible = $true; "
                f"$n.ShowBalloonTip(5000,'{safe_title}','{safe_msg}',"
                "[System.Windows.Forms.ToolTipIcon]::Info); "
                "Start-Sleep 6; $n.Dispose()"
            )
            subprocess.Popen(
                ["powershell", "-WindowStyle", "Hidden", "-Command", ps],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            pass

    def _test_translate(self):
        """İlk dosyanın ilk 3 chunk'ını sync çevirip önizleme dialog'u açar."""
        api_key = self._main_api_key()
        if not api_key:
            messagebox.showerror("API Key", "OpenAI API key girilmemiş!")
            return
        files = self._get_srt_files()
        if not files:
            messagebox.showwarning("Test", "Önce dosya veya klasör seç.")
            return

        fp   = files[0]
        src  = self.src_var.get()
        tgt  = self.tgt_var.get()
        model = self._main_model_name()

        self._log(f"🧪 Test çevirisi: {Path(fp).name} (ilk 3 chunk)", "info")
        self._set_running(True)

        def _run():
            try:
                import hybrid_translate as ht
                from openai import OpenAI as _OAI
                b_url = self._main_api_base_url()
                client = _OAI(api_key=api_key, base_url=b_url if b_url else None)
                if not list(parse_subtitle(fp)):
                    try:
                        _post_ui(self, messagebox.showwarning, "Test", "Dosyada geçerli SRT bloğu yok.")
                    except Exception:
                        pass
                    return

                # Gerçek çeviriyle birebir aynı istek hattını kullan:
                # ctx/next_ctx, süre, frag etiketleri, glossary, proje hafızası dahil.
                schema    = self._get_file_schema(fp)
                profanity = self.profanity_var.get()
                gloss     = ht.load_glossary(self._get_file_glossary(fp))
                reqs, fmap = build_requests([fp], src, tgt, model,
                                            chunk_size=self._chunk_size,
                                            schema=schema,
                                            profanity=profanity,
                                            glossary=gloss,
                                            project_memory=self._pm,
                                            context_lines=self._context_lines,
                                            lookahead_lines=self._lookahead_lines,
                                            scene_gap_sec=self._scene_gap_seconds,
                                            temperature=self._temperature)
                reqs = reqs[:2]   # ilk ~2 chunk (≈100 satır) yeterli önizleme

                results, prev_pairs = [], []
                for req in reqs:
                    if self._stop_flag:
                        break
                    cid      = req["custom_id"]
                    user_msg = req["body"]["messages"][1]
                    if self.chain_ctx_var.get():
                        user_msg["content"] = _inject_prev_tr(
                            user_msg["content"], prev_pairs, max_pairs=self._context_lines)
                    payload = json.loads(user_msg["content"])
                    try:
                        resp = _safe_chat_create(client, **req["body"])
                        if resp.usage:
                            tot, cached = _get_usage_details(resp.usage)
                            self._update_tokens(tot, cached=cached)
                        raw  = (resp.choices[0].message.content or "").strip()
                        tmap = parse_response(raw, fmap.get(cid, []))
                        pairs = _chain_pairs_from_result(user_msg["content"], tmap)
                        if pairs:
                            prev_pairs = pairs
                        for it in payload.get("tr", []):
                            results.append((it.get("t", ""),
                                            tmap.get(str(it["i"]), "[HATA]")))
                    except Exception as e:
                        for it in payload.get("tr", []):
                            results.append((it.get("t", ""), f"[HATA: {e}]"))

                try:
                    _post_ui(self, self._show_test_dialog, results, Path(fp).name)
                except Exception:
                    pass
            except Exception as e:
                self._log_exc("Test çevirisi hatası", e)
            finally:
                self._set_running(False)

        threading.Thread(target=_run, daemon=True).start()

    def _show_test_dialog(self, results: list, fname: str):
        """Kaynak / Çeviri yan yana önizleme dialog'u."""
        dlg = ctk.CTkToplevel(self)
        dlg.title(f"🧪 Test Çevirisi — {fname}")
        dlg.geometry("920x600")
        dlg.configure(fg_color=BG)
        dlg.grab_set()
        dlg.lift()
        dlg.focus_force()

        ctk.CTkLabel(dlg,
                     text=f"{fname} — ilk {len(results)} satır önizleme",
                     font=ctk.CTkFont("Segoe UI", 13, "bold"),
                     text_color=ACCENT).pack(pady=(14, 4))

        # İki sütunlu scrollable alan
        cols = ctk.CTkFrame(dlg, fg_color="transparent")
        cols.pack(fill="both", expand=True, padx=12, pady=4)
        cols.grid_columnconfigure((0, 1), weight=1)

        for col, header in enumerate(["KAYNAK", "ÇEVİRİ"]):
            ctk.CTkLabel(cols, text=header,
                         font=ctk.CTkFont("Segoe UI", 11, "bold"),
                         text_color=FG2).grid(row=0, column=col, sticky="w", padx=8, pady=(0, 4))

        sf = ctk.CTkScrollableFrame(cols, fg_color=PANEL, corner_radius=8)
        sf.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=4)
        cols.grid_rowconfigure(1, weight=1)
        sf.grid_columnconfigure((0, 1), weight=1)

        for i, (src_t, tr_t) in enumerate(results):
            bg = CARD if i % 2 == 0 else PANEL
            for col, text in enumerate([src_t, tr_t]):
                color = FG if col == 0 else (RED if text.startswith("[HATA") else GREEN)
                ctk.CTkLabel(sf, text=text,
                             font=ctk.CTkFont("Segoe UI", 11),
                             text_color=color,
                             fg_color=bg, corner_radius=4,
                             wraplength=400, justify="left",
                             anchor="w").grid(
                    row=i, column=col, sticky="ew", padx=6, pady=2, ipady=3)

        btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_fr.pack(fill="x", padx=12, pady=(4, 14))
        btn_fr.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(btn_fr, text="✕  Kapat",
                      fg_color=CARD, hover_color=BORDER,
                      command=dlg.destroy).grid(row=0, column=0, padx=4, sticky="ew")
        ctk.CTkButton(btn_fr, text="▶  Tam Çeviriyi Başlat",
                      fg_color=ACCENT, hover_color="#5a4fd1",
                      command=lambda: (dlg.destroy(), self._start())).grid(row=0, column=1, padx=4, sticky="ew")

    def _check_log_pin(self):
        """Kullanıcı scroll yaptıktan sonra alta yakın mı diye kontrol eder."""
        try:
            _, bottom = self.log_box.yview()
            self._log_pinned = (bottom >= 0.98)
        except Exception:
            pass

    def _pin_log_bottom(self):
        """'⬇ Alta git' butonuna basınca kilidi aç ve en alta git."""
        self._log_pinned = True
        try:
            self.log_box.see("end")
        except Exception:
            pass

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    _PHASE_COLORS = {
        "analiz":    "#5B9BD5",   # mavi
        "çeviri":    "#2ECC71",   # yeşil
        "critic":    "#F39C12",   # turuncu
        "polish":    "#9B59B6",   # mor
        "qc":        "#E74C3C",   # kırmızı
        "sweep":     "#1ABC9C",   # teal
        "yazıyor":   "#7B68EE",   # accent
        "tamam":     "#2ECC71",   # yeşil
        "hata":      "#E74C3C",   # kırmızı
        "hazır":     "#8888aa",   # gri
    }

    def _set_phase(self, phase: str, detail: str = ""):
        """Büyük faz etiketini günceller. phase = 'analiz'|'çeviri'|'critic'|..."""
        key   = phase.lower().split()[0]
        color = self._PHASE_COLORS.get(key, ACCENT)

        def _upd():
            try:
                self._phase_lbl.configure(text=phase, text_color=color)
                self._phase_dot.configure(text_color=color)
                if detail:
                    self.progress_lbl.configure(text=detail)
            except Exception:
                pass

        _post_ui(self, _upd)

    def _set_status(self, msg):
        def _upd():
            try:
                self.progress_lbl.configure(text=msg)
            except Exception:
                pass
        _post_ui(self, _upd)

    def _set_progress(self, pct):
        val = pct / 100
        def _upd(v=val):
            try:
                self.progress.set(v)
            except Exception:
                pass
        _post_ui(self, _upd)

    def _set_eta(self, text: str):
        """ETA etiketini thread-safe günceller."""
        def _upd(t=text):
            try:
                self.eta_lbl.configure(text=t)
            except Exception:
                pass
        _post_ui(self, _upd)

    def _set_stat(self, var, value):
        """Stat sayacı Tk değişkenini thread-safe ayarlar (worker thread'den de güvenli —
        Tcl değişken yazımı yalnız ana thread'de güvenlidir)."""
        def _upd(v=value):
            try:
                var.set(v)
            except Exception:
                pass
        _post_ui(self, _upd)

    def _set_running(self, running):
        # Worker thread'lerden çağrılabilir; Tk widget .configure()/after_cancel YALNIZCA
        # ana thread'de güvenli (Tcl thread-safe değil). Ana thread'de değilsek marshal et.
        if threading.current_thread() is not threading.main_thread():
            _post_ui(self, self._set_running, running)
            return
        s = "disabled" if running else "normal"
        self.start_btn.configure(state=s)
        self.resume_btn.configure(state=s)
        self.jsonl_btn.configure(state=s)
        self.postprocess_btn.configure(state=s)
        self.stop_btn.configure(state="normal" if running else "disabled")
        self.pause_btn.configure(state="normal" if running else "disabled")
        self._is_running = running
        if running:
            self._active_snapshot = self._take_run_snapshot()
            self._start_elapsed_timer()
        else:
            self._active_snapshot = None
            self._stop_elapsed_timer()
            if self._job_rows:
                self._set_phase("Hazır", "")

    # ── İş panosu yardımcıları ────────────────────────────────────────────────
    def _show_progress_board(self, files: list):
        """İşlem başlarken tüm dosyaları 'Bekliyor' olarak gösteren panoyu açar."""
        def _build():
            for w in self._job_rows_frame.winfo_children():
                w.destroy()
            self._job_rows.clear()
            self._removed_queue_files.clear()

            for fp in files:
                fname = Path(fp).name
                if len(fname) > 46:
                    fname = "…" + fname[-43:]

                row_fr = ctk.CTkFrame(self._job_rows_frame,
                                      fg_color=CARD, corner_radius=6)
                row_fr.pack(fill="x", padx=2, pady=(0, 3))
                row_fr.grid_columnconfigure(1, weight=1)

                dot = ctk.CTkLabel(row_fr, text="○", width=22,
                                   font=ctk.CTkFont("Segoe UI", 13, "bold"),
                                   text_color=FG2)
                dot.grid(row=0, column=0, padx=(8, 2), pady=7)

                name_lbl = ctk.CTkLabel(row_fr, text=fname, anchor="w",
                                        font=ctk.CTkFont("Segoe UI", 11),
                                        text_color=FG)
                name_lbl.grid(row=0, column=1, sticky="ew", padx=(4, 8))

                phase_lbl = ctk.CTkLabel(row_fr, text="Bekliyor", width=148,
                                         anchor="w",
                                         font=ctk.CTkFont("Segoe UI", 10),
                                         text_color=FG2)
                phase_lbl.grid(row=0, column=2, padx=4)

                pb = ctk.CTkProgressBar(row_fr, height=5, width=108,
                                        progress_color=FG2, fg_color=BORDER)
                pb.grid(row=0, column=3, padx=(2, 12), pady=9)
                pb.set(0)

                remove_btn = ctk.CTkButton(
                    row_fr, text="×", width=26, height=26,
                    font=ctk.CTkFont("Segoe UI", 15, "bold"),
                    fg_color="transparent", hover_color=BORDER, text_color=WARN,
                    command=lambda p=fp: self._remove_queued_file(p))
                remove_btn.grid(row=0, column=4, padx=(0, 6), pady=4)

                self._job_rows[fp] = {"dot": dot, "phase": phase_lbl,
                                      "pb": pb, "frame": row_fr,
                                      "remove": remove_btn, "state": "waiting"}

            n = len(files)
            self._jb_title.configure(text=f"DOSYALAR — 0 / {n}")
            self._file_list_outer.grid_remove()
            self._job_board.grid()

        if threading.current_thread() is threading.main_thread():
            _build()
        else:
            ready = threading.Event()
            def _build_ready():
                try:
                    _build()
                finally:
                    ready.set()
            try:
                _post_ui(self, _build_ready)
                ready.wait(timeout=5)
            except Exception:
                pass

    def _norm_path(self, filepath: str) -> str:
        import os
        return os.path.normcase(os.path.abspath(str(filepath)))

    def _is_queued_file_removed(self, filepath: str) -> bool:
        return self._norm_path(filepath) in self._removed_queue_files

    def _remove_queued_file(self, filepath: str):
        """Henüz başlamamış dosyayı iş panosundaki kuyruktan çıkar."""
        row = self._job_rows.get(filepath)
        if not row or row.get("state") != "waiting":
            return
        norm_fp = self._norm_path(filepath)
        self._removed_queue_files.add(norm_fp)
        self._selected_files = [p for p in self._selected_files if self._norm_path(p) != norm_fp]
        self._file_schema_vars.pop(filepath, None)
        try:
            row["frame"].destroy()
        except Exception:
            pass
        self._job_rows.pop(filepath, None)
        self._log(f"Kuyruktan çıkarıldı: {Path(filepath).name}", "info")
        self._refresh_job_board_title()
        self._set_stat(self.stat_files_var, str(len(self._job_rows)))

    def _refresh_job_board_title(self):
        done_n = sum(1 for r in self._job_rows.values()
                     if r["dot"].cget("text") in ("✓", "✗", "—"))
        self._jb_title.configure(text=f"DOSYALAR — {done_n} / {len(self._job_rows)}")

    def _update_file_progress(self, filepath: str, phase: str,
                               pct: float, status: str = "running"):
        """Tek dosya satırını günceller. Thread-safe.
        status: 'running' | 'done' | 'error' | 'skip'"""
        row = self._job_rows.get(filepath)
        if not row:
            return

        if status == "running":
            row["state"] = "running"

        if status == "done":
            color, dot_text = GREEN,  "✓"
        elif status == "error":
            color, dot_text = RED,    "✗"
        elif status == "skip":
            color, dot_text = FG2,    "—"
        else:
            key   = phase.lower().split()[0]
            color = self._PHASE_COLORS.get(key, ACCENT)
            dot_text = "●"

        def _upd():
            try:
                row["dot"].configure(text=dot_text, text_color=color)
                row["phase"].configure(text=phase,  text_color=color)
                row["pb"].configure(progress_color=color)
                row["pb"].set(max(0.0, min(1.0, pct / 100)))
                if status == "running":
                    row["state"] = "running"
                    row["remove"].configure(state="disabled")
                self._refresh_job_board_title()
            except Exception:
                pass

        _post_ui(self, _upd)

    def _maybe_condense(self, blocks, mm_k, mm_u, mm_m, tgt, src_map=None):
        """condense_var açıksa CPS sınırını aşan satırları kısaltır. Aksi halde blocks aynen döner."""
        if not getattr(self, "condense_var", None) or not self.condense_var.get():
            return blocks
        if not blocks or not mm_k:
            return blocks
        import hybrid_translate as ht
        try:
            self._set_status("Okuma hızı kısaltma...")
            new_blocks, _n = ht.condense_fast_lines(
                tr_blocks=blocks,
                helper_api_key=mm_k, helper_url=mm_u, helper_model=mm_m,
                tgt_lang=tgt, cps_limit=21.0,
                log_fn=self._log, token_callback=self._update_tokens,
                src_map=src_map)
            return new_blocks
        except Exception as e:
            self._log_exc("Kısaltma pass hatası", e)
            return blocks

    def _maybe_merge_cues(self, blocks):
        """ai_segment_var açıksa AI destekli akıllı segmentasyon, değilse merge_cues_var
        açıksa hızlı parçalı birleştirme uygular. ÇIKTI biçimlendirmesidir — TM/scan
        PRE-merge bloklarla çalıştığı için bu yalnızca write_srt'e giden son adımda uygulanır."""
        if threading.current_thread() is not threading.main_thread() and hasattr(self, "_active_snapshot") and self._active_snapshot:
            ai_on = bool(self._active_snapshot.get("ai_segment"))
            fast_on = bool(self._active_snapshot.get("merge_cues"))
        else:
            ai_on   = bool(getattr(self, "ai_segment_var", None) and self.ai_segment_var.get())
            fast_on = bool(getattr(self, "merge_cues_var", None) and self.merge_cues_var.get())
        if not (ai_on or fast_on):
            return blocks
        try:
            if ai_on:
                key = self._helper_api_key("analysis")
                if key:
                    return ai_resegment_cues(
                        blocks, key, self._helper_api_base_url("analysis"), self._helper_api_model("analysis"),
                        log_fn=self._log, max_chars=self._merge_max_chars,
                        max_gap_ms=self._merge_max_gap_ms,
                        token_callback=self._update_tokens)
                self._log("AI segmentasyon: API anahtarı yok, hızlı birleştirmeye düşülüyor", "warn")
            out = merge_fragmented_cues(blocks,
                                        max_chars=self._merge_max_chars,
                                        max_gap_ms=self._merge_max_gap_ms)
            if len(out) < len(blocks):
                self._log(f"Parçalı cue birleştirme: {len(blocks)} → {len(out)} blok", "ok")
            return out
        except Exception as e:
            self._log_exc("Cue birleştirme hatası", e)
            return blocks

    def _get_schema(self) -> dict:
        name = self.content_type_var.get()
        for schema in CONTENT_SCHEMAS.values():
            if schema["name"] == name:
                return schema
        return CONTENT_SCHEMAS["auto"]

    def _update_tokens(self, added: int, price: float = None, cached: int = 0):
        """Token sayacını + tahmini maliyeti günceller. Maliyet AYRI birikir (kümülatif
        token × tek fiyat DEĞİL) — böylece her kaynak kendi fiyatıyla eklenir. price
        verilmezse ana model fiyatı kullanılır; Batch API çağrıları %50 indirimli geçer.
        cached verilirse OpenAI Prompt Caching indirimi (%50) hesaba katılır."""
        if price is None:
            price = MODEL_PRICE.get(self._main_model_name(), 0.60)
        with self._token_lock:
            self._token_total += added
            self._token_cached = getattr(self, "_token_cached", 0) + cached
            
            # Compute cost: cached tokens are 50% cheaper
            uncached = max(0, added - cached)
            cost_added = (uncached * price + cached * price * 0.5) / 1_000_000
            self._cost_total = getattr(self, "_cost_total", 0.0) + cost_added
            
            total = self._token_total
            cached_total = self._token_cached
            cost  = self._cost_total
        def _upd(t=total, c=cost, ct=cached_total):
            try:
                self.stat_tokens_var.set(f"{t:,}")
                if ct > 0:
                    self.stat_tokens_sub_var.set(f"~${c:.4f} ({ct:,} önb.)")
                else:
                    self.stat_tokens_sub_var.set(f"Token  ~${c:.4f}")
                pts = self._token_sparkline_points
                if not pts or pts[-1] != t:
                    pts.append(t)
                    if len(pts) > 20:
                        del pts[:-20]
                    self._update_token_sparkline()
            except Exception:
                pass
        _post_ui(self, _upd)

    def _update_batch_tokens(self, added: int):
        """Batch API token/maliyeti — Batch API %50 daha ucuz (gösterilen maliyet de öyle)."""
        self._update_tokens(added, price=MODEL_PRICE.get(self._main_model_name(), 0.60) * 0.5)

    def _store_tm_pairs(self, blocks, src_clean_map, model, tgt):
        """Kaynak↔çeviri çiftlerini TM'ye yazar; eksik işaretler ve kaynak==çeviri
        (kimlik) çiftleri hariç tutulur. DÖRT akışın ortak TM-kayıt mantığı tek yerde — birebir aynıydı,
        burada toplandı ki bir daha 'şu akışta var bu akışta yok' sürüklenmesi olmasın.
        (tr_text etiket geri yüklemeden geçmiş olmalı — TM'e temiz hâliyle yazılır.)"""
        try:
            pairs = [
                (src_clean_map[str(idx)], _clean_src(tr_text))
                for idx, ts, tr_text in blocks
                if str(idx) in src_clean_map
                and not str(tr_text).startswith("[HATA")
                and str(tr_text).strip() != "[ÇEVİRİ EKSİK]"
                and _clean_src(tr_text).strip().lower() != src_clean_map[str(idx)].strip().lower()
            ]
            if pairs:
                profanity = self.profanity_var.get() if hasattr(self, "profanity_var") else ""
                self._tm.store_batch(pairs, model, tgt_lang=tgt, profanity=profanity)
            self._update_tm_stat()
        except Exception as _tm_e:
            self._log(f"TM kayıt hatası: {_tm_e}", "warn")

    def _update_tm_stat(self):
        """TM vuruş sayacını stats panelinde günceller."""
        hits = self._tm.hit_count_session()
        def _upd():
            try:
                self.stat_tm_var.set(str(hits))
            except Exception:
                pass
        _post_ui(self, _upd)

    def _json_repair_pass(self, client, raw_map: dict, requests_list: list):
        """Before full retry, try to repair malformed JSON responses.
        For chunks where JSON extraction failed, ask the model to fix its own output.
        This avoids a full re-translation (cheaper) and recovers most parse failures.
        """
        repaired = 0
        for req in requests_list:
            cid = req["custom_id"]
            raw = raw_map.get(cid)
            if raw is None:
                continue  # no response at all — handled by retry_hata
            # Only attempt repair if parse truly failed (no valid array found)
            try:
                items = json.loads(_extract_json_array(raw))
                if isinstance(items, list) and items:
                    continue  # already valid
            except Exception:
                pass
            # Build repair prompt
            repair_payload = {
                "task": "The previous response was supposed to be a valid JSON array but failed to parse. "
                        "Return ONLY the corrected JSON array with the same translations. "
                        "No commentary, no markdown fences, no extra text.",
                "rules": [
                    "Output must be a JSON array: [{\"i\": N, \"t\": \"...\"}]",
                    "Preserve all translation content — do not change meanings",
                    "Do not wrap in ```json``` or any other delimiter",
                ],
                "broken_response": raw[:2000],  # cap to avoid token waste
            }
            try:
                resp = _safe_chat_create(
                    client,
                    model=req.get("body", {}).get("model") or self._main_model_name(),
                    messages=[
                        {"role": "system", "content": "You are a JSON repair assistant. Return only valid JSON."},
                        {"role": "user",   "content": json.dumps(repair_payload, ensure_ascii=False)},
                    ],
                    max_completion_tokens=2048,
                    temperature=0.0,
                )
                fixed = (resp.choices[0].message.content or "").strip()
                tok, cached = 0, 0
                if resp.usage:
                    tok, cached = _get_usage_details(resp.usage)
                self._update_tokens(tok, cached=cached)
                # Validate the repaired response
                items2 = json.loads(_extract_json_array(fixed))
                if isinstance(items2, list) and items2:
                    expected_ids = _expected_ids_from_req(req)
                    if _validate_repaired_chunk(items2, expected_ids):
                        raw_map[cid] = fixed
                        repaired += 1
                        self._log(f"  🔧 {cid}: JSON onarıldı ({len(items2)} item)", "ok")
                    else:
                        # id kümesi beklenenle uyuşmuyor (kayma riski) — onarımı
                        # KABUL ETME, raw_map dokunulmadan kalsın ki chunk normal
                        # tam-yeniden-çeviri yoluna (_retry_hata) düşsün.
                        self._log(f"  ↺ {cid}: JSON onarımı id doğrulamasından geçemedi, "
                                  f"tam yeniden çeviriye bırakıldı", "warn")
            except Exception:
                pass  # repair failed — retry_hata will handle it
        if repaired:
            self._log(f"JSON onarımı: {repaired} chunk kurtarıldı", "ok")

    def _retry_hata(self, client, raw_map: dict, requests_list: list, max_rounds: int = 2):
        """Retry chunks that produced [HATA] or failed to parse.
        First attempts JSON repair (cheap), then full re-translation.
        Up to `max_rounds` passes with exponential backoff on 429/5xx.
        """
        import random
        import hybrid_translate as ht
        # Step 0: try cheap JSON repair before full re-translation
        self._json_repair_pass(client, raw_map, requests_list)
        req_by_id = {r["custom_id"]: r for r in requests_list}

        def _retry_reason(cid):
            raw = raw_map.get(cid)
            if raw is None:
                return "missing_response"
            try:
                items = json.loads(_extract_json_array(raw))
                if not isinstance(items, list):
                    return "invalid_json"
                if any(not isinstance(it, dict) for it in items):
                    return "invalid_items"
                if any(str(it.get("t", "")).strip() == "[HATA]" for it in items):
                    return "hata_line"
                if any(ht.has_non_turkish_target_leak(str(it.get("t", ""))) for it in items):
                    return "non_turkish_target"
                req = req_by_id.get(cid)
                chunk_src_map = _chunk_src_map_from_request(req) if req else {}
                if chunk_src_map:
                    expected_ids = list(chunk_src_map)
                    actual_ids = [str(it.get("i")) for it in items if "i" in it]
                    required_ids = [
                        idx for idx in expected_ids
                        if len(_align_visible(chunk_src_map.get(idx, ""))) >= 3
                        and not _align_is_sfx_only(chunk_src_map.get(idx, ""))
                    ]
                    required_set = set(required_ids)
                    if (len(actual_ids) != len(set(actual_ids))
                            or not set(actual_ids) <= set(expected_ids)
                            or [idx for idx in actual_ids if idx in required_set] != required_ids):
                        return "id_integrity"
                    for it in items:
                        idx = str(it.get("i"))
                        if not str(it.get("t", "")).strip() and idx in required_set:
                            return "empty_dialogue"
                # Chunk içi komşu-tekrar: mini içeriği öne kaydırıp aynı satırı iki
                # id'ye yazdıysa, dosya yazılmadan ÖNCE burada yakala (bkz.
                # detect_alignment_issues'in adjacent_duplicate sinyali — aynı
                # paylaşılan mantık, tek bir chunk'a daraltılmış).
                if req:
                    if chunk_src_map:
                        seq = [(str(it.get("i")), _align_visible(str(it.get("t", ""))))
                               for it in items if isinstance(it, dict) and "i" in it]
                        if _find_adjacent_duplicate_ids(seq, chunk_src_map):
                            return "adjacent_duplicate"
                return ""
            except Exception:
                return "parse_error"

        def _needs_retry(cid):
            return bool(_retry_reason(cid))

        def _leak_example_token(cid):
            """Log/teşhis amaçlı: bu chunk'ta hedef-dil kaçağını tetikleyen somut
            token'ı döndürür (yanlış alarm mı gerçek sızıntı mı ayırt edilebilsin)."""
            try:
                items = json.loads(_extract_json_array(raw_map.get(cid, "")))
                for it in items:
                    tok = ht.non_turkish_leak_token(str(it.get("t", "")))
                    if tok:
                        return tok
            except Exception:
                pass
            return None

        def _retry_body_for(req, reason: str):
            body = copy.deepcopy(req["body"])
            if reason in {"adjacent_duplicate", "id_integrity", "empty_dialogue"}:
                for msg in body.get("messages", []):
                    if msg.get("role") != "user":
                        continue
                    try:
                        payload = json.loads(msg.get("content", ""))
                        payload.pop("sentence_groups", None)
                        for it in payload.get("tr", []):
                            if isinstance(it, dict):
                                it.pop("frag", None)
                                it.pop("frag_group", None)
                        msg["content"] = json.dumps(payload, ensure_ascii=False)
                    except Exception:
                        pass
                    break
                guard_msg = (
                    "STRICT ID RETRY — ID INTEGRITY: Retry the whole chunk and output ONLY valid JSON. "
                    "Translate every tr item independently into its own id. Context may clarify meaning, "
                    "but NEVER move, borrow, merge, or redistribute words or clauses between ids. "
                    "Return every input id exactly once, in the same order. No id may be missing and no "
                    "dialogue translation may be empty."
                )
                role = "developer" if any(m.get("role") == "developer" for m in body.get("messages", [])) else "system"
                body.setdefault("messages", []).insert(1, {"role": role, "content": guard_msg})
            if reason == "non_turkish_target":
                guard_msg = (
                    "QUALITY RETRY: The previous JSON parsed, but at least one translation contained "
                    "non-Turkey-Turkish Latin/Turkic artifacts. Retry the whole chunk. Output ONLY valid "
                    "JSON. Use natural Turkey Turkish only. Do not output Turkmen/Uzbek/Azeri-looking "
                    "forms such as bäýram, holidaý, oturylyşyğı, ortadagy, geň, taksidermiya, bäseke, "
                    "qora, yuqori, pichoq, shaxs, xavf, daraj, haqli. Keep the same ids and line breaks."
                )
                role = "developer" if any(m.get("role") == "developer" for m in body.get("messages", [])) else "system"
                body.setdefault("messages", []).insert(1, {"role": role, "content": guard_msg})
            if "temperature" in body:
                body["temperature"] = min(float(body.get("temperature") or 0.2), 0.2)
            return body

        for round_idx in range(max_rounds):
            if self._stop_flag:
                break
            retry_reasons = {cid: _retry_reason(cid) for cid in req_by_id}
            to_retry = [cid for cid, reason in retry_reasons.items() if reason]
            if not to_retry:
                return
            leak_cids = [cid for cid in to_retry if retry_reasons.get(cid) == "non_turkish_target"]
            leak_count = len(leak_cids)
            extra = f", {leak_count} hedef-dil kaçağı" if leak_count else ""
            if leak_cids:
                example = _leak_example_token(leak_cids[0])
                if example:
                    extra += f" (örn: '{example}')"
            dup_count = sum(1 for reason in retry_reasons.values() if reason == "adjacent_duplicate")
            if dup_count:
                extra += f", {dup_count} chunk-içi tekrar"
            self._log(f"↺  {len(to_retry)} chunk yeniden deneniyor{extra} (tur {round_idx+1}/{max_rounds})...", "warn")
            for cid in to_retry:
                if self._stop_flag:
                    break
                req = req_by_id.get(cid)
                if not req:
                    continue
                for attempt in range(3):  # up to 3 attempts per round for transient errors
                    try:
                        resp = _safe_chat_create(client, **_retry_body_for(req, retry_reasons.get(cid, "")))
                        if not resp.choices:
                            raise RuntimeError("empty choices")
                        msg = resp.choices[0].message
                        text = (msg.content or "").strip()
                        if not text:
                            raise RuntimeError("empty content")
                        tok, cached = 0, 0
                        if resp.usage:
                            tok, cached = _get_usage_details(resp.usage)
                        raw_map[cid] = text
                        self._update_tokens(tok, cached=cached)
                        self._log(f"  ↺ {cid}: tamam", "ok")
                        break
                    except Exception as e:
                        estr = str(e)
                        estr_l = estr.lower()
                        transient = (
                            "429" in estr
                            or "rate limit" in estr_l
                            or "timeout" in estr_l
                            or "connection" in estr_l
                            or any(code in estr for code in ("500", "502", "503", "504"))
                        )
                        if transient and attempt < 2:
                            wait = (2 ** attempt) + random.random()
                            time.sleep(wait)
                            continue
                        self._log(f"  ↺ {cid}: başarısız — {e}", "err")
                        break

        # Kurtarma adımı
        if self._stop_flag:
            return
        strict_fallback = set()
        for cid, req in req_by_id.items():
            reason = _retry_reason(cid)
            if reason not in {"adjacent_duplicate", "id_integrity", "empty_dialogue"}:
                continue
            try:
                messages = req.get("body", {}).get("messages", [])
                user_msg = next(m for m in messages if m.get("role") == "user")
                payload = json.loads(user_msg.get("content", ""))
                tr_items = payload.get("tr", [])
                raw_map[cid] = json.dumps(
                    [{"i": it["i"], "t": "[HATA]"} for it in tr_items
                     if isinstance(it, dict) and "i" in it],
                    ensure_ascii=False,
                )
                strict_fallback.add(cid)
                self._log(
                    f"  ↪ {cid}: katı ID denemesi başarısız; tüm chunk satır bazlı onarıma bırakıldı",
                    "warn",
                )
            except Exception:
                pass
        for cid in [c for c in req_by_id if c not in strict_fallback and _needs_retry(c)]:
            if self._stop_flag:
                break
            try:
                merged = self._resend_missing_blocks(client, req_by_id[cid], raw_map.get(cid, ""))
            except Exception as e:
                self._log(f"  ↺ {cid}: alt-istek kurtarması hatası — {e}", "warn")
                merged = None
            if merged is not None:
                raw_map[cid] = merged

        for cid in req_by_id:
            if _retry_reason(cid) != "non_turkish_target":
                continue
            try:
                items = json.loads(_extract_json_array(raw_map.get(cid, "")))
                marked = 0
                example = None
                for item in items:
                    if isinstance(item, dict):
                        tok = ht.non_turkish_leak_token(str(item.get("t", "")))
                        if tok:
                            item["t"] = "[HATA_NON_TURKISH_TARGET]"
                            marked += 1
                            if example is None:
                                example = tok
                if marked:
                    raw_map[cid] = json.dumps(items, ensure_ascii=False)
                    tok_hint = f" (örn: '{example}')" if example else ""
                    self._log(f"  ↺ {cid}: {marked} hedef-dil kaçağı son çare için işaretlendi{tok_hint}", "warn")
            except Exception:
                pass

    def _resend_missing_blocks(self, client, req: dict, current_raw: str, max_sub: int = 20):
        """Bir chunk'ta hâlâ eksik/[HATA] olan blokları, yalnızca o blokları içeren
        daha küçük isteklerle yeniden çevirir (kesilme kurtarması). Birleştirilmiş
        JSON dizisi (string) döner; kurtarılacak bir şey yoksa None."""
        try:
            payload = json.loads(req["body"]["messages"][1]["content"])
        except Exception:
            return None
        all_items = payload.get("tr", [])
        if len(all_items) < 2:
            return None
        missing = _missing_block_items(all_items, current_raw)
        if not missing or len(missing) >= len(all_items):
            return None

        recovered = {}
        try:
            for it in json.loads(_extract_json_array(current_raw) or "[]"):
                if isinstance(it, dict) and "i" in it and str(it.get("t", "")).strip() not in ("", "[HATA]"):
                    recovered[str(it["i"])] = it["t"]
        except Exception:
            pass
        for it in _salvage_json_objects(current_raw):
            if isinstance(it, dict) and "i" in it:
                recovered.setdefault(str(it["i"]), it.get("t"))

        sys_msg = req["body"]["messages"][0]
        model   = req["body"]["model"]
        _ml     = model.lower()
        _no_temp = _ml.startswith(("gpt-5", "o1", "o3", "o4", "codex-"))
        n_groups = math.ceil(len(missing) / max_sub)
        self._log(f"  ↺ {req['custom_id']}: {len(missing)} eksik blok "
                  f"{n_groups} küçük istekle tamamlanıyor (kesilme kurtarması)", "warn")

        for s in range(0, len(missing), max_sub):
            if self._stop_flag:
                break
            sub = missing[s:s + max_sub]
            sub_payload = {"tr": sub}
            for key in ("ctx", "next_ctx", "prev_scene", "scene", "sentence_groups",
                        "idioms", "prev_tr", "glossary"):
                if payload.get(key):
                    sub_payload[key] = payload[key]
            body = {
                "model": model,
                "messages": [sys_msg,
                             {"role": "user", "content": json.dumps(sub_payload, ensure_ascii=False)}],
                "max_completion_tokens": max(len(sub) * 200, 800),
            }
            if not _no_temp:
                body["temperature"] = 0.2
            try:
                resp = _safe_chat_create(client, **body)
                if resp.usage:
                    tot, cached = _get_usage_details(resp.usage)
                    self._update_tokens(tot, cached=cached)
                txt  = (resp.choices[0].message.content or "").strip()
                info = [(str(it.get("i")), "", "") for it in sub]
                tmap = parse_response(txt, info)
                for k, v in tmap.items():
                    if str(v).strip() not in ("", "[HATA]"):
                        recovered[k] = v
            except Exception as e:
                self._log(f"  ↺ alt-grup hatası: {e}", "warn")

        merged = [{"i": it.get("i"), "t": recovered.get(str(it.get("i")), "[HATA]")}
                  for it in all_items]
        return json.dumps(merged, ensure_ascii=False)

    def _update_active_model(self, source=None):
        if source == "2.5M":
            self.limit_class_var.set("2.5M")
            self.model_var.set(self.model_2_5m_var.get())
        elif source == "250K":
            self.limit_class_var.set("250K")
            self.model_var.set(self.model_250k_var.get())
        else:
            limit_class = self.limit_class_var.get()
            if limit_class == "2.5M":
                self.model_var.set(self.model_2_5m_var.get())
            else:
                self.model_var.set(self.model_250k_var.get())

        # Aktif seçimi mor çerçeve ile vurgula
        active_class = self.limit_class_var.get()
        if active_class == "2.5M":
            if hasattr(self, "model_2_5m_combo") and self.model_2_5m_combo:
                self.model_2_5m_combo.configure(border_color=ACCENT)
            if hasattr(self, "model_250k_combo") and self.model_250k_combo:
                self.model_250k_combo.configure(border_color=BORDER)
        else:
            if hasattr(self, "model_2_5m_combo") and self.model_2_5m_combo:
                self.model_2_5m_combo.configure(border_color=BORDER)
            if hasattr(self, "model_250k_combo") and self.model_250k_combo:
                self.model_250k_combo.configure(border_color=ACCENT)

        try:
            self._save_settings()
        except Exception:
            pass

    def _on_mode_change(self):
        if self.mode_var.get() == "sync" and not self.hybrid_var.get():
            self.hybrid_var.set(True)
            self.hybrid_frame.grid()

    def _toggle_hybrid(self):
        if self.hybrid_var.get():
            self.hybrid_frame.grid()
            # Karşılıklı engelleme: Yardımcı Analiz açıkken Ön-Bağlam'ı kapat ve pasifleştir
            self.precontext_var.set(False)
            if hasattr(self, "precontext_switch") and self.precontext_switch:
                self.precontext_switch.configure(state="disabled")
        else:
            self.hybrid_frame.grid_remove()
            # Yardımcı Analiz kapandığında Ön-Bağlam switch'ini tekrar etkinleştir
            if hasattr(self, "precontext_switch") and self.precontext_switch:
                self.precontext_switch.configure(state="normal")
        self._sync_helper_role_controls()

    def _on_precontext_toggle(self):
        # Ön-Bağlam Analizi açıldığında Yardımcı Analiz'i kapat
        if self.precontext_var.get():
            self.hybrid_var.set(False)
            self._toggle_hybrid()

    def _on_input_entry_focus_in(self):
        """Kullanıcı girdi klasör kutusuna tıkladığında odak anındaki ilk değeri kaydeder."""
        if getattr(self, "_is_running", False):
            return
        self._input_entry_focus_val = self.input_var.get()

    def _on_input_entry_edited(self):
        """Kullanıcı odak kaybettiğinde veya Enter bastığında değer gerçekten değiştiyse açık seçim olarak işaretler."""
        if getattr(self, "_is_running", False):
            return
        cur_val = self.input_var.get()
        if getattr(self, "_input_entry_focus_val", None) is not None:
            if cur_val == self._input_entry_focus_val:
                return
        self._input_entry_focus_val = cur_val
        self._input_folder_explicitly_selected = True
        path = (cur_val or "").strip()
        if not self._selected_files and path and os.path.isdir(path):
            try:
                from project_memory import ProjectMemory
                self._pm = ProjectMemory(path)
            except Exception:
                self._pm = None

    def _pick_folder(self, var, is_input):
        if getattr(self, "_is_running", False):
            self._log("Çeviri çalışırken klasör değiştirilemez.", "warn")
            return
        self.attributes("-topmost", True)
        path = filedialog.askdirectory(parent=self, title="Klasör Seç")
        self.attributes("-topmost", False)
        if not path:
            return
        var.set(path)
        if is_input:
            # Clear any manually selected files when a folder is chosen
            self._selected_files = []
            self._input_folder_explicitly_selected = True
            self._content_type_preflight_done = False
            self.clear_files_btn.grid_remove()
            self.clear_info_btn.grid_remove()
            # ProjectMemory'yi bu klasör için başlat
            try:
                from project_memory import ProjectMemory
                self._pm = ProjectMemory(path)
                pm_stats = self._pm.stats()
                if pm_stats["glossary"] > 0 or pm_stats["characters"] > 0:
                    self._log(
                        f"Proje hafızası yüklendi: {pm_stats['glossary']} terim, "
                        f"{pm_stats['characters']} karakter", "ok")
            except Exception:
                self._pm = None
            files = get_subtitle_files(path, recursive=True)
            if files:
                self._estimate_async(
                    files,
                    lambda tb, ek, n=len(files): f"✓  {n} dosya  •  {tb} satır  •  ~{ek} token")
                self._log(f"Klasör: {path}  ({len(files)} dosya)", "ok")
                self._populate_file_list(files)
            else:
                self.file_info_var.set("⚠  .srt bulunamadı!")
                self._log(f"'{path}' içinde .srt yok.", "warn")
        else:
            self._log(f"Çıkış klasörü: {path}", "info")

    def _pick_files(self):
        if getattr(self, "_is_running", False):
            self._log("Çeviri çalışırken dosya seçilemez.", "warn")
            return
        self.attributes("-topmost", True)
        paths = filedialog.askopenfilenames(
            parent=self, title="Altyazı Dosyaları Seç",
            filetypes=[
                ("Altyazı dosyaları", "*.srt *.vtt *.ass *.ssa"),
                ("SubRip (.srt)", "*.srt"),
                ("WebVTT (.vtt)", "*.vtt"),
                ("ASS/SSA (.ass *.ssa)", "*.ass *.ssa"),
                ("Tümü", "*.*"),
            ])
        self.attributes("-topmost", False)
        if not paths:
            return
        self._content_type_preflight_done = False
        self._input_folder_explicitly_selected = False
        self._selected_files = self._dedupe_paths(list(paths))
        n = len(self._selected_files)
        self._refresh_selected_files_ui(
            f"{n} dosya seçildi: "
            + ", ".join(Path(p).name for p in self._selected_files[:5])
            + ("…" if n > 5 else ""))

    def _add_folder_files(self):
        if getattr(self, "_is_running", False):
            self._log("Çeviri çalışırken klasör eklenemez.", "warn")
            return
        try:
            paths = pick_multiple_folders(
                owner_hwnd=self.winfo_id(),
                title="Altyazı Klasörlerini Seç (Ctrl/Shift ile birden fazla klasör seçebilirsiniz)")
        except Exception:
            paths = None
        if paths is None:
            self._log("Native çoklu klasör seçici kullanılamadı, alternatif klasör seçimi açılıyor.", "warn")
            collected = []
            while True:
                self.attributes("-topmost", True)
                path = filedialog.askdirectory(parent=self, title="Altyazı Klasörü Ekle")
                self.attributes("-topmost", False)
                if not path:
                    break
                collected.append(path)
                try:
                    from tkinter import messagebox
                    ans = messagebox.askyesno(
                        "Klasör Ekle",
                        "Başka klasör eklemek ister misiniz?",
                        parent=self
                    )
                except Exception:
                    ans = False
                if not ans:
                    break
            paths = collected
        if not paths:
            return

        self._append_folder_files(paths)

    def _append_folder_files(self, paths: list[str]):
        """Bir veya daha fazla klasörün altyazılarını mevcut seçime ekle."""
        if getattr(self, "_is_running", False):
            self._log("Çeviri çalışırken klasör eklenemez.", "warn")
            return 0
        if (not self._selected_files
                and getattr(self, "_input_folder_explicitly_selected", False)
                and self.input_var.get()):
            self._selected_files = self._get_srt_files()
        files = []
        empty = []
        for path in self._dedupe_paths(paths):
            found = get_subtitle_files(path, recursive=True)
            if found:
                files.extend(found)
            else:
                empty.append(path)
        if not files:
            for path in empty:
                self._log(f"'{path}' içinde altyazı yok.", "warn")
            return 0
        before = len(self._selected_files)
        self._content_type_preflight_done = False
        self._selected_files = self._dedupe_paths(list(self._selected_files) + files)
        added = len(self._selected_files) - before
        total = len(self._selected_files)
        for path in empty:
            self._log(f"'{path}' içinde altyazı yok.", "warn")
        self._refresh_selected_files_ui(
            f"{len(paths)} klasör eklendi: +{added} yeni, toplam {total} dosya")
        return added

    def _helper_model_config(self, role: str):
        if role not in self.helper_model_vars:
            return resolve_helper_model("gpt-5.4-mini")
        lbl = self.helper_model_vars[role].get()
        if self._is_custom_helper_label(lbl):
            from helper_models import HelperModelConfig
            prov = self.helper_custom_provider_vars[role].get()
            model_name = self.helper_custom_model_vars[role].get().strip() or "custom-model"
            base_url = self.helper_custom_url_vars[role].get().strip() or "https://api.openai.com/v1"
            if prov == "openai" and "claude" in model_name.lower() and "/messages" in base_url.lower():
                prov = "anthropic"
            return HelperModelConfig(
                label="Özel (Custom)",
                provider=prov,
                model=model_name,
                base_url=base_url
            )
        return resolve_helper_model(lbl)

    def _helper_api_base_url(self, role: str):
        if threading.current_thread() is not threading.main_thread() and hasattr(self, "_active_snapshot") and self._active_snapshot:
            urls = self._active_snapshot.get("helper_urls") or {}
            if role in urls:
                return urls[role]
        cfg = self._helper_model_config(role)
        url = cfg.base_url
        if url:
            url = url.rstrip("/")
        return url

    def _helper_api_model(self, role: str):
        if threading.current_thread() is not threading.main_thread() and hasattr(self, "_active_snapshot") and self._active_snapshot:
            models = self._active_snapshot.get("helper_models") or {}
            if role in models:
                return models[role]
        return self._helper_model_config(role).model

    def _helper_api_key(self, role: str):
        if threading.current_thread() is not threading.main_thread() and hasattr(self, "_active_snapshot") and self._active_snapshot:
            keys = self._active_snapshot.get("helper_keys") or {}
            if role in keys:
                return keys[role]
        k = ""
        if role in self.helper_role_key_vars:
            k = self.helper_role_key_vars[role].get().strip()
        if role in self.helper_custom_key_vars:
            k = k or self.helper_custom_key_vars[role].get().strip()
        provider = self._get_current_helper_provider(role)
        if not k:
            cache_key = "openai_helper" if provider == "openai" else provider
            k = self._helper_keys_cache.get(cache_key, "").strip()
        if not k and hasattr(self, "helper_key_entry") and self.helper_key_entry:
            k = self.helper_key_entry.get().strip()
        if (not k and provider in {"openai", "openai_helper"}
                and hasattr(self, "api_key_entry") and self.api_key_entry):
            k = self.api_key_entry.get().strip()
        return k

    # ── Ana Model — Özel Sağlayıcı resolver'ları ────────────────────────────
    # "OpenAI API Key"/"OpenAI API Base URL"/model dropdown'ına ASLA yazmaz/okumaz
    # onların dışından — yalnızca AŞAĞIDAKİ ayrı alanları okur, açık VE doluysa
    # onu döner; kapalıysa ya da özel alan boşsa sessizce gerçek OpenAI alanına
    # düşer (fail-safe, helper-role resolver'larıyla aynı "boş=genel" felsefesi).
    def _main_custom_active(self) -> bool:
        return bool(getattr(self, "main_custom_var", None) and self.main_custom_var.get())

    def _main_api_key(self) -> str:
        if threading.current_thread() is not threading.main_thread() and hasattr(self, "_active_snapshot") and self._active_snapshot:
            return self._active_snapshot.get("main_api_key", "")
        if self._main_custom_active():
            k = self.main_custom_key_entry.get().strip()
            if k:
                return k
        return self.api_key_entry.get().strip()

    def _main_api_base_url(self):
        if threading.current_thread() is not threading.main_thread() and hasattr(self, "_active_snapshot") and self._active_snapshot:
            return self._active_snapshot.get("main_api_base_url", None)
        if self._main_custom_active():
            u = self.main_custom_url_var.get().strip()
            if u:
                return _normalize_api_base_url(u)
        return _normalize_api_base_url(self.api_url_var.get())

    def _main_model_name(self) -> str:
        if threading.current_thread() is not threading.main_thread() and hasattr(self, "_active_snapshot") and self._active_snapshot:
            return self._active_snapshot.get("main_model_name", "")
        if self._main_custom_active():
            m = self.main_custom_model_var.get().strip()
            if m:
                return m
        return self.model_var.get()

    def _sync_main_custom_visibility(self):
        """Özel sağlayıcı alanlarını switch durumuna göre göster/gizler.

        Özel sağlayıcı (reseller) açıkken Batch modu seçilemez — gerçek
        OpenAI Batch API'si resmi OpenAI dışında desteklenmiyor (kullanıcı
        2026-07-20: yanlışlıkla batch seçip nasıl çalıştığını sormuştu; aslında
        hiç batch çalışmamıştı, mode_var sadece açılışta yüklenen eski ayarı
        gösteriyordu). Açıkken zaten Anında'ya (sync) zorlanır ve Batch radio'su
        pasifleştirilir; kapanınca tekrar seçilebilir olur."""
        custom_active = bool(getattr(self, "main_custom_var", None) and self.main_custom_var.get())
        if custom_active:
            self.main_custom_frame.grid()
        else:
            self.main_custom_frame.grid_remove()
        batch_radio = getattr(self, "_mode_batch_radio", None)
        if batch_radio:
            if custom_active:
                if self.mode_var.get() == "batch":
                    self.mode_var.set("sync")
                    self._on_mode_change()
                batch_radio.configure(state="disabled")
            else:
                batch_radio.configure(state="normal")

    def _on_main_custom_changed(self):
        """Switch tıklanınca: görünürlüğü güncelle + AYARLARI HEMEN KAYDET.

        Diğer toggle'lardan farklı olarak burada anında kaydediyoruz — kullanıcı
        switch'i açıp alanları doldurduktan sonra çeviri hiç başlatmadan/uygulamayı
        düzgün kapatmadan ekranı değiştirebilir; _start()/_resume()/_on_close()'a
        kadar beklemek bu durumda dolduruşu sessizce kaybettirir."""
        self._sync_main_custom_visibility()
        try:
            self._save_settings()
        except Exception:
            pass

    def _on_helper_provider_change_role(self, role: str):
        pass

    def _helper_display_name(self, role: str):
        return self._helper_model_config(role).label

    def _save_settings(self):
        data = {
            "model": self.model_var.get(), "src_lang": self.src_var.get(),
            "tgt_lang": self.tgt_var.get(), "mode": self.mode_var.get(),
            "hybrid": self.hybrid_var.get(),
            "style": self.style_var.get(), "glossary": self.glossary_var.get(),
            "analysis_depth": self.analysis_depth_var.get(),
            "ext_project_path": self.ext_project_path_var.get(),
            "clean_sdh": self.clean_sdh_var.get(),
            "content_type": self.content_type_var.get(),
            "profanity": self.profanity_var.get(),
            "critic": self.critic_var.get(),
            "polish": self.polish_var.get(),
            "qc": self.qc_var.get(),
            "native": self.native_var.get(),
            "backtrans": self.backtrans_var.get(),
            "backup_raw": self.backup_raw_var.get(),
            "auto_glossary": self.auto_glossary_var.get(),
            "linebreak": self.linebreak_var.get(),
            "condense": self.condense_var.get(),
            "chain_ctx": self.chain_ctx_var.get(),
            "precontext": self.precontext_var.get(),
            "series_memory": self.series_memory_var.get(),
            "review_pass": self.review_pass_var.get(),
            "term_normalize": self.term_normalize_var.get(),
            "twowave": self.twowave_var.get(),
            "same_folder": self.same_folder_var.get(),
            "file_list_height": int(self._file_rows_frame.cget("height")),
            "merge_cues": self.merge_cues_var.get(),
            "ai_segment": self.ai_segment_var.get(),
            "merge_max_chars": self._merge_max_chars,
            "merge_max_gap_ms": self._merge_max_gap_ms,
            "notify": self.notify_var.get(),
            "api_url": _normalize_api_base_url(self.api_url_var.get()),
            "main_custom": self.main_custom_var.get(),
            "main_custom_model": self.main_custom_model_var.get(),
            "main_custom_url": self.main_custom_url_var.get(),
            # Advanced settings
            "chunk_size": self._chunk_size,
            "context_lines": self._context_lines,
            "lookahead_lines": self._lookahead_lines,
            "max_workers": self._max_workers,
            "temperature": self._temperature,
            "max_retry": self._max_retry,
            "scene_gap_seconds": self._scene_gap_seconds,
            "window_geometry": self.geometry(),  # pencere pozisyon/boyut kaydet
        }

        # Bağımsız yardımcı model ayarlarını kaydet
        for role in self.helper_roles:
            cfg = self._helper_model_config(role)
            data[f"helper_model_{role}"] = cfg.label
            # NOT: role özel API anahtarları artık JSON'da saklanmıyor;
            # bunlar credential store'da güvenli şekilde tutuluyor.
            if role in self.helper_custom_provider_vars:
                data[f"helper_custom_provider_{role}"] = self.helper_custom_provider_vars[role].get()
                data[f"helper_custom_model_{role}"] = self.helper_custom_model_vars[role].get()
                data[f"helper_custom_url_{role}"] = self.helper_custom_url_vars[role].get()

        try:
            # Atomik yazım: önce .tmp'ye yaz, sonra rename
            _sp  = Path(self._settings_path())
            _tmp = _sp.with_suffix(".json.tmp")
            with open(_tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            _tmp.replace(_sp)
        except Exception:
            pass

        # API anahtarlarını güvenli depoya kaydet
        try:
            fallback_used = False
            _k = self.api_key_entry.get().strip()
            if _k:
                fallback_used = (not credential_store.save_key("openai", _k)) or fallback_used
            
            # Genel yardımcı anahtarı kaydet
            _mk = self.helper_key_entry.get().strip()
            if _mk:
                fallback_used = (not credential_store.save_key("openai_helper", _mk)) or fallback_used
                self._helper_keys_cache["openai_helper"] = _mk
            
            # Role özel API anahtarlarını kaydet / temizle
            for role in self.helper_roles:
                role_key = self.helper_role_key_vars[role].get().strip() if role in self.helper_role_key_vars else ""
                if role_key:
                    fallback_used = (not credential_store.save_key(f"helper_role_{role}_key", role_key)) or fallback_used
                else:
                    credential_store.delete_key(f"helper_role_{role}_key")
                k = self.helper_custom_key_vars[role].get().strip()
                if k:
                    fallback_used = (not credential_store.save_key(f"helper_{role}_key", k)) or fallback_used
                else:
                    credential_store.delete_key(f"helper_{role}_key")
            # Ana model — özel sağlayıcı anahtarı (ayrı slot; gerçek 'openai' anahtarını
            # ASLA ezmez/görmez — kendi credential_store rolü altında bağımsız saklanır).
            _mck = self.main_custom_key_entry.get().strip()
            if _mck:
                fallback_used = (not credential_store.save_key("main_custom", _mck)) or fallback_used
            else:
                credential_store.delete_key("main_custom")
            if fallback_used:
                self._log("keyring kullanılamıyor, anahtar obfuscated fallback dosyada saklandı", "warn")
        except Exception:
            pass

    def _get_current_helper_provider(self, role: str = "analysis", model_name: str = None) -> str:
        if role not in self.helper_model_vars:
            return "openai_helper"
        if model_name is None:
            model_name = self.helper_model_vars[role].get()
        if self._is_custom_helper_label(model_name):
            if role in self.helper_custom_provider_vars:
                provider = self.helper_custom_provider_vars[role].get()
                custom_model = self.helper_custom_model_vars.get(role).get() if role in self.helper_custom_model_vars else ""
                custom_url = self.helper_custom_url_vars.get(role).get() if role in self.helper_custom_url_vars else ""
                if provider == "openai" and "claude" in custom_model.lower() and "/messages" in custom_url.lower():
                    return "anthropic"
                return provider
            return "openai_helper"
        model_name_lower = model_name.lower()
        if "gemini" in model_name_lower:
            return "gemini"
        try:
            cfg = resolve_helper_model(normalize_helper_model_label(model_name))
            return "openai_helper" if cfg.provider == "openai" else cfg.provider
        except Exception:
            pass
        if "deepseek" in model_name_lower:
            return "deepseek"
        elif "bedrock" in model_name_lower:
            return "bedrock"
        elif "claude" in model_name_lower:
            return "anthropic"
        else:
            return "openai_helper"

    def _on_helper_model_change_role(self, role: str):
        if role not in self.helper_model_vars:
            return
        mvar = self.helper_model_vars[role]
        c_frame = self.helper_custom_frames.get(role)
        if not c_frame:
            return
        if not self._helper_role_is_enabled(role):
            c_frame.pack_forget()
            return

        if self._is_custom_helper_label(mvar.get()):
            c_frame.pack(fill="x", padx=4, pady=(2,4))
        else:
            c_frame.pack_forget()

    def _clear_selected_files(self):
        self._selected_files = []
        self._input_folder_explicitly_selected = True
        self._content_type_preflight_done = False
        self.file_info_var.set("")
        self.clear_files_btn.grid_remove()
        self.clear_info_btn.grid_remove()
        self._log("Dosya seçimi temizlendi — klasör modu aktif", "info")

    def _pick_glossary(self):
        self.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            parent=self, title="Glossary Seç",
            filetypes=[("Glossary", "*.json *.txt *.tsv *.csv"), ("Tümü", "*.*")])
        self.attributes("-topmost", False)
        if path:
            self.glossary_var.set(path)
            self._log(f"Glossary: {path}", "info")

    def _pick_project_path(self):
        self.attributes("-topmost", True)
        path = filedialog.askdirectory(parent=self, title="External Project Path Seç (subtitle_localizer)")
        self.attributes("-topmost", False)
        if path:
            self.ext_project_path_var.set(path)
            self._log(f"External project: {path}", "info")

    # ── Ayarlar ───────────────────────────────────────────────────────────────
    def _settings_path(self):
        return state_path(__file__, ".gui_settings.json")


    def _is_custom_helper_label(self, value: str) -> bool:
        return "custom" in (value or "").lower()

    def _helper_role_is_enabled(self, role: str) -> bool:
        if role == "analysis":
            return True
        role_var = {
            "critic": getattr(self, "critic_var", None),
            "polish": getattr(self, "polish_var", None),
            "qc": getattr(self, "qc_var", None),
        }.get(role)
        return bool(role_var and role_var.get())

    def _sync_helper_role_controls(self):
        if not hasattr(self, "helper_roles"):
            return
        labels = getattr(self, "helper_role_labels", {})
        combos = getattr(self, "helper_role_combos", {})
        custom_frames = getattr(self, "helper_custom_frames", {})
        for role, label_text in self.helper_roles.items():
            enabled = self._helper_role_is_enabled(role)
            label = labels.get(role)
            if label:
                label.configure(
                    text=label_text if enabled else f"{label_text} (kapali)",
                    text_color=FG2 if enabled else "#777190",
                )
            combo = combos.get(role)
            if combo:
                combo.configure(
                    state="readonly" if enabled else "disabled",
                    text_color=FG if enabled else "#8d88aa",
                    button_color=BORDER if enabled else CARD,
                )
            if enabled:
                self._on_helper_model_change_role(role)
            else:
                c_frame = custom_frames.get(role)
                if c_frame:
                    c_frame.pack_forget()


    def _log_startup_settings(self, note: str = ""):
        """Açılışta girdi/çıktı/mod'u TEK log satırında görünür kılar.

        Neden: 2026-07-17'de kullanıcının .gui_settings.json'ı fabrika varsayılanlarına
        dönmüş bulundu (input='./subtitles', output='./translated') ama hangi oturumun
        bunu kaydettiğini geriye dönük kanıtlayacak iz yoktu. Bu satır varsa bir
        dahaki sefere "hangi klasörle açıldı" anında loglarda görünür olur."""
        try:
            mode = self.mode_var.get()
            hyb = "hybrid" if self.hybrid_var.get() else "düz"
            msg = (f"Ayarlar yüklendi: girdi='{self.input_var.get()}', "
                  f"çıktı='{self.output_var.get()}', mod={mode}/{hyb}")
            if note:
                msg += f" {note}"
            self._log(msg, "info")
        except Exception:
            pass

    def _load_settings(self):
        p = self._settings_path()
        # Eski düz-metin anahtarları güvenli depoya taşı (JSON'dan siler)
        try:
            credential_store.migrate_from_settings(p)
        except Exception:
            pass
        # Anahtarları güvenli depodan yükle
        try:
            _k = credential_store.load_key("openai")
            if _k and not self.api_key_entry.get():
                self.api_key_entry.insert(0, _k)

            _mck = credential_store.load_key("main_custom")
            if _mck and not self.main_custom_key_entry.get():
                self.main_custom_key_entry.insert(0, _mck)

            # Tüm yardımcı model anahtarlarını önbelleğe al
            for prov in ("openai_helper", "gemini", "deepseek", "bedrock", "anthropic", "minimax"):
                val = credential_store.load_key(prov)
                if val:
                    self._helper_keys_cache[prov] = val

            # İlk gösterilecek anahtarı belirle ve yükle
            prov = self._get_current_helper_provider()
            _mk = self._helper_keys_cache.get(prov)
            if not _mk and prov == "openai_helper":
                _mk = self._helper_keys_cache.get("minimax")
            if _mk and not self.helper_key_entry.get():
                self.helper_key_entry.insert(0, _mk)
        except Exception:
            pass
        if not p.exists():
            self._log_startup_settings("(ayar dosyası yok, varsayılanlar)")
            return
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            # Eski format yedeği: depoda yoksa JSON'daki anahtarı kullan
            if d.get("api_key") and not self.api_key_entry.get():
                self.api_key_entry.insert(0, d["api_key"])
            if d.get("helper_key") and not self.helper_key_entry.get():
                self.helper_key_entry.insert(0, d["helper_key"])
            if d.get("model") in MODELS:
                loaded_model = d["model"]
                self.model_var.set(loaded_model)
                if loaded_model in MODELS_2_5M:
                    self.limit_class_var.set("2.5M")
                    self.model_2_5m_var.set(loaded_model)
                elif loaded_model in MODELS_250K:
                    self.limit_class_var.set("250K")
                    self.model_250k_var.set(loaded_model)
                self._update_active_model()
            if "api_url" in d:                     self.api_url_var.set(_normalize_api_base_url(d["api_url"]))
            if d.get("src_lang") in LANGUAGES:     self.src_var.set(d["src_lang"])
            if d.get("tgt_lang") in LANGUAGES:     self.tgt_var.set(d["tgt_lang"])
            if d.get("mode") in ("batch","sync"):  self.mode_var.set(d["mode"])
            if d.get("hybrid"):
                self.hybrid_var.set(True)
                self.hybrid_frame.grid()
            
            # Legacy single-helper settings, kept only for old settings files.
            if hasattr(self, "helper_custom_provider_var") and "helper_custom_provider" in d:
                self.helper_custom_provider_var.set(d["helper_custom_provider"])
            if hasattr(self, "helper_custom_model_var") and "helper_custom_model" in d:
                self.helper_custom_model_var.set(d["helper_custom_model"])
            if hasattr(self, "helper_custom_url_var") and "helper_custom_url" in d:
                self.helper_custom_url_var.set(d["helper_custom_url"])

            helper_model = d.get("helper_model")
            if helper_model and hasattr(self, "helper_model_var"):
                self.helper_model_var.set(normalize_helper_model_label(helper_model))

            for role in getattr(self, "helper_roles", {}):
                model_key = f"helper_model_{role}"
                saved_model = d.get(model_key)
                if saved_model and role in self.helper_model_vars:
                    if self._is_custom_helper_label(saved_model):
                        self.helper_model_vars[role].set(saved_model)
                    else:
                        self.helper_model_vars[role].set(normalize_helper_model_label(saved_model))
                if role in self.helper_custom_provider_vars:
                    provider_key = f"helper_custom_provider_{role}"
                    custom_model_key = f"helper_custom_model_{role}"
                    custom_url_key = f"helper_custom_url_{role}"
                    if provider_key in d:
                        self.helper_custom_provider_vars[role].set(d[provider_key])
                    if custom_model_key in d:
                        self.helper_custom_model_vars[role].set(d[custom_model_key])
                    if custom_url_key in d:
                        self.helper_custom_url_vars[role].set(d[custom_url_key])
                    role_key_key = f"helper_role_key_{role}"
                    if role_key_key in d and role in self.helper_role_key_vars:
                        self.helper_role_key_vars[role].set(d[role_key_key])
                    saved_role_key = credential_store.load_key(f"helper_role_{role}_key")
                    if saved_role_key and role in self.helper_role_key_vars and not self.helper_role_key_vars[role].get():
                        self.helper_role_key_vars[role].set(saved_role_key)
                    saved_role_key = credential_store.load_key(f"helper_{role}_key")
                    if saved_role_key and not self.helper_custom_key_vars[role].get():
                        self.helper_custom_key_vars[role].set(saved_role_key)
            if d.get("style"):          self.style_var.set(d["style"])
            if d.get("analysis_depth"):
                try:
                    import hybrid_translate as ht
                    self.analysis_depth_var.set(ht.analysis_depth_label(d["analysis_depth"]))
                except Exception:
                    if d["analysis_depth"] in ("Standart", "Gelismis", "Maksimum"):
                        self.analysis_depth_var.set(d["analysis_depth"])
            if d.get("glossary"):       self.glossary_var.set(d["glossary"])
            if d.get("ext_project_path"):
                self.ext_project_path_var.set(d["ext_project_path"])
            if "clean_sdh" in d:
                self.clean_sdh_var.set(bool(d["clean_sdh"]))
            if d.get("content_type"):
                self.content_type_var.set(normalize_schema_name(d["content_type"]))
            if d.get("profanity") in ("Hafif", "Orta", "Sert"):
                self.profanity_var.set(d["profanity"])
            if "critic" in d:
                self.critic_var.set(bool(d["critic"]))
            if "polish" in d:
                self.polish_var.set(bool(d["polish"]))
            if "qc" in d:
                self.qc_var.set(bool(d["qc"]))
            if "native" in d:
                self.native_var.set(bool(d["native"]))
            if "backtrans" in d:
                self.backtrans_var.set(bool(d["backtrans"]))
            if "auto_glossary" in d:
                self.auto_glossary_var.set(bool(d["auto_glossary"]))
            if "linebreak" in d:
                self.linebreak_var.set(bool(d["linebreak"]))
            if "condense" in d:
                self.condense_var.set(bool(d["condense"]))
            if "term_normalize" in d:
                self.term_normalize_var.set(bool(d["term_normalize"]))
            if "twowave" in d:
                self.twowave_var.set(bool(d["twowave"]))
            if "same_folder" in d:
                self.same_folder_var.set(bool(d["same_folder"]))
            if isinstance(d.get("file_list_height"), int):
                _flh = max(self._FILE_LIST_MIN_H, min(self._FILE_LIST_MAX_H, d["file_list_height"]))
                self._file_rows_frame.configure(height=_flh)
            if "main_custom_model" in d:
                self.main_custom_model_var.set(str(d["main_custom_model"]))
            if "main_custom_url" in d:
                self.main_custom_url_var.set(str(d["main_custom_url"]))
            if "main_custom" in d:
                self.main_custom_var.set(bool(d["main_custom"]))
                self._sync_main_custom_visibility()
            if "merge_cues" in d:
                self.merge_cues_var.set(bool(d["merge_cues"]))
            if "ai_segment" in d:
                self.ai_segment_var.set(bool(d["ai_segment"]))
            if isinstance(d.get("merge_max_chars"), int):
                self._merge_max_chars = d["merge_max_chars"]
            if isinstance(d.get("merge_max_gap_ms"), int):
                self._merge_max_gap_ms = d["merge_max_gap_ms"]
            # Varsayılanı True olan anahtarlar: yalnızca kayıtlı değer varsa uygula
            if "chain_ctx" in d:
                self.chain_ctx_var.set(bool(d["chain_ctx"]))
            if "precontext" in d:
                self.precontext_var.set(bool(d["precontext"]))
            if "series_memory" in d:
                self.series_memory_var.set(bool(d["series_memory"]))
            if "backup_raw" in d:                          # varsayılan AÇIK → kayıtlı false sabit kalsın
                self.backup_raw_var.set(bool(d["backup_raw"]))
            if "review_pass" in d:
                self.review_pass_var.set(bool(d["review_pass"]))
            if "notify" in d:
                self.notify_var.set(d["notify"])
            # Load advanced settings
            if isinstance(d.get("chunk_size"), int):
                self._chunk_size = d["chunk_size"]
            if isinstance(d.get("context_lines"), int):
                self._context_lines = max(1, d["context_lines"])
            if isinstance(d.get("lookahead_lines"), int):
                self._lookahead_lines = max(1, d["lookahead_lines"])
            if isinstance(d.get("max_workers"), int):
                self._max_workers = d["max_workers"]
            if isinstance(d.get("temperature"), (int, float)):
                self._temperature = float(d["temperature"])
            if isinstance(d.get("max_retry"), int):
                self._max_retry = d["max_retry"]
            if isinstance(d.get("scene_gap_seconds"), (int, float)):
                self._scene_gap_seconds = float(d["scene_gap_seconds"])
            if isinstance(d.get("window_geometry"), str):
                self._restored_geometry = d["window_geometry"]
            
            # Uygulama açılışında arayüz durumlarını senkronize et
            self._toggle_hybrid()
            self._log_startup_settings()
        except Exception as e:
            try:
                bak = _write_sanitized_settings_backup(p, keep_last=3)
                if bak is not None:
                    self._log(f"Ayarlar yüklenemedi, yedek alındı: {bak.name}", "warn")
                else:
                    self._log(f"Ayarlar yüklenemedi: {e}", "warn")
            except Exception:
                self._log(f"Ayarlar yüklenemedi ve yedek alınamadı: {e}", "err")
            return

    # ── Advanced Settings Dialog ──────────────────────────────────────────────
    def _show_advanced_settings(self):
        """Display advanced settings dialog with 7 sliders."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("Gelişmiş Ayarlar")
        dlg.geometry("500x600")
        dlg.grab_set()
        dlg.lift()
        dlg.focus_force()
        dlg.configure(fg_color=BG)

        # Slider'lar self.* alanlarına DOĞRUDAN yazıyor; İptal'de geri alabilmek için
        # mevcut değerleri sakla (eskiden İptal değişiklikleri geri almıyordu).
        _adv_attrs = ("_chunk_size", "_context_lines", "_lookahead_lines",
                      "_max_workers", "_temperature", "_max_retry", "_scene_gap_seconds")
        _adv_snapshot = {a: getattr(self, a, None) for a in _adv_attrs}

        dlg.grid_columnconfigure(0, weight=1)
        r = 0

        # Header
        hdr = ctk.CTkFrame(dlg, fg_color=ACCENT, corner_radius=10, height=50)
        hdr.grid(row=r, column=0, sticky="ew", padx=12, pady=(12,12))
        hdr.grid_propagate(False)
        r += 1
        ctk.CTkLabel(hdr, text="⚙️ Gelişmiş Ayarlar",
                     font=ctk.CTkFont("Segoe UI", 14, "bold"),
                     text_color="white").pack(pady=12)

        # Scrollable frame for sliders
        scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent",
                                        scrollbar_button_color=BORDER,
                                        scrollbar_button_hover_color=ACCENT)
        scroll.grid(row=r, column=0, sticky="nsew", padx=12, pady=(0,12))
        r += 1
        scroll.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(r-1, weight=1)

        def create_slider(label, var_name, min_val, max_val, current_val, step=1, is_float=False):
            """Create a labeled slider with value display."""
            fr = ctk.CTkFrame(scroll, fg_color="transparent")
            fr.pack(fill="x", padx=4, pady=(8,2))
            fr.grid_columnconfigure(0, weight=1)

            lbl_fr = ctk.CTkFrame(fr, fg_color="transparent")
            lbl_fr.grid(row=0, column=0, sticky="ew")
            lbl_fr.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(lbl_fr, text=label,
                         font=ctk.CTkFont("Segoe UI", 12),
                         text_color=FG).pack(side="left")

            val_lbl = ctk.CTkLabel(lbl_fr, text=str(current_val),
                                   font=ctk.CTkFont("Segoe UI", 11),
                                   text_color=ACCENT, width=50)
            val_lbl.pack(side="right")

            def on_slider_change(val):
                if is_float:
                    val = float(val)
                else:
                    val = int(val)
                setattr(self, var_name, val)
                val_lbl.configure(text=str(val))

            slider = ctk.CTkSlider(fr, from_=min_val, to=max_val,
                                   number_of_steps=int((max_val - min_val) / step),
                                   command=on_slider_change,
                                   fg_color=BORDER, progress_color=ACCENT)
            slider.set(current_val)
            slider.grid(row=1, column=0, sticky="ew", pady=(2,6))

        # Add sliders
        create_slider("CHUNK_SIZE (satır/batch)", "_chunk_size", 10, 100, self._chunk_size, 5)
        create_slider("CONTEXT_LINES (önceki)", "_context_lines", 1, 30, self._context_lines, 1)
        create_slider("LOOKAHEAD_LINES (sonraki)", "_lookahead_lines", 1, 20, self._lookahead_lines, 1)
        create_slider("Max Workers (thread)", "_max_workers", 1, 16, self._max_workers, 1)
        create_slider("Temperature (yaratıcılık, gpt-5.x/o-serisi modellerde etkisiz)",
                      "_temperature", 0.0, 1.0, self._temperature, 0.1, True)
        create_slider("Max Retry (yeniden deneme)", "_max_retry", 1, 10, self._max_retry, 1)
        create_slider("Scene Gap (saniye)", "_scene_gap_seconds", 0.5, 5.0, self._scene_gap_seconds, 0.5, True)

        # Buttons
        btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_fr.grid(row=r, column=0, sticky="ew", padx=12, pady=(0,12))
        r += 1
        btn_fr.grid_columnconfigure((0,1), weight=1)

        ctk.CTkButton(btn_fr, text="✓ Kaydet", height=36,
                      font=ctk.CTkFont("Segoe UI", 12),
                      fg_color=ACCENT, hover_color="#5a4fd1",
                      command=lambda: (self._save_settings(), dlg.destroy())
                      ).grid(row=0, column=0, sticky="ew", padx=(0,4))

        ctk.CTkButton(btn_fr, text="✕ İptal", height=36,
                      font=ctk.CTkFont("Segoe UI", 12),
                      fg_color=CARD, hover_color=BORDER,
                      command=lambda: ([setattr(self, k, v) for k, v in _adv_snapshot.items()
                                        if v is not None], dlg.destroy())
                      ).grid(row=0, column=1, sticky="ew", padx=(4,0))

    # ── Progress Tracking ─────────────────────────────────────────────────────
    def _start_elapsed_timer(self):
        """Start tracking elapsed time."""
        self._start_time = time.time()
        self._update_elapsed_display()

    def _stop_elapsed_timer(self):
        """Stop tracking elapsed time."""
        if self._elapsed_tick:
            self.after_cancel(self._elapsed_tick)
            self._elapsed_tick = None
        self._start_time = None

    def _update_elapsed_display(self):
        """Update elapsed time display every 1 second."""
        if self._start_time is None:
            return
        elapsed = time.time() - self._start_time
        mins, secs = divmod(int(elapsed), 60)
        hrs, mins = divmod(mins, 60)
        if hrs > 0:
            text = f"{hrs}h {mins}m"
        else:
            text = f"{mins}m {secs}s"

        def update():
            try:
                self.elapsed_lbl.configure(text=text)
            except Exception:
                pass

        _post_ui(self, update)

        self._elapsed_tick = self.after(1000, self._update_elapsed_display)

    def _update_progress_speed(self, total_processed: int, total_items: int):
        """Calculate and display processing speed (items/min)."""
        if self._start_time is None or total_processed == 0:
            return

        elapsed_secs = time.time() - self._start_time
        if elapsed_secs < 1:
            return

        # Calculate items per minute
        speed = (total_processed / elapsed_secs) * 60

        def update():
            try:
                if speed < 1:
                    self.speed_lbl.configure(text=f"{speed:.1f} item/m")
                else:
                    self.speed_lbl.configure(text=f"{speed:.0f} item/m")
            except Exception:
                pass

        _post_ui(self, update)

    def _calculate_eta(self, total_processed: int, total_items: int) -> str:
        """Calculate ETA based on current speed."""
        if self._start_time is None or total_processed == 0:
            return ""

        elapsed_secs = time.time() - self._start_time
        if elapsed_secs < 1:
            return ""

        remaining = total_items - total_processed
        if remaining <= 0:
            return "Tamamlanıyor..."

        avg_speed = total_processed / elapsed_secs  # items per second
        if avg_speed == 0:
            return ""

        eta_secs = remaining / avg_speed
        if eta_secs < 60:
            return f"ETA: {int(eta_secs)}s"
        elif eta_secs < 3600:
            mins = int(eta_secs / 60)
            secs = int(eta_secs % 60)
            return f"ETA: {mins}m {secs}s"
        else:
            hrs = int(eta_secs / 3600)
            mins = int((eta_secs % 3600) / 60)
            return f"ETA: {hrs}h {mins}m"

    # ── Stat Card Animations ──────────────────────────────────────────────────
    def _animate_stat(self, attr: str, target_value: int, duration_ms: int = 400):
        """Smoothly animate stat card number to target value."""
        lbl = getattr(self, f"{attr}_lbl", None)
        if not lbl:
            return

        start_value = 0
        try:
            current_text = getattr(self, f"{attr}_var").get()
            if current_text != "—":
                start_value = int(current_text)
        except (ValueError, AttributeError):
            pass

        if start_value == target_value:
            getattr(self, f"{attr}_var").set(str(target_value))
            return

        steps = max(10, int(duration_ms / 30))  # ~30ms per frame
        step_size = (target_value - start_value) / steps
        current_step = 0

        def animate_frame():
            nonlocal current_step
            if current_step >= steps:
                getattr(self, f"{attr}_var").set(str(target_value))
                return

            current_step += 1
            current_val = int(start_value + step_size * current_step)
            getattr(self, f"{attr}_var").set(str(current_val))
            self.after(30, animate_frame)

        animate_frame()

    def _update_token_sparkline(self):
        """Draw a mini sparkline graph in the token card canvas."""
        canvas = getattr(self, "stat_tokens_canvas", None)
        if not canvas:
            return

        canvas.delete("all")

        if not self._token_sparkline_points or len(self._token_sparkline_points) < 2:
            return

        # Get canvas dimensions
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w <= 1 or h <= 1:
            return

        points = self._token_sparkline_points[-20:]  # Last 20 samples
        if not points:
            return

        min_val = min(points)
        max_val = max(points)
        val_range = max_val - min_val if max_val > min_val else 1

        # Scale points to canvas
        scaled = []
        for i, val in enumerate(points):
            x = (i / (len(points) - 1)) * (w - 20) + 10 if len(points) > 1 else w / 2
            y = h - 8 - ((val - min_val) / val_range) * (h - 16)
            scaled.append((x, y))

        # Draw line
        if len(scaled) > 1:
            for i in range(len(scaled) - 1):
                x1, y1 = scaled[i]
                x2, y2 = scaled[i + 1]
                canvas.create_line(x1, y1, x2, y2, fill=YELLOW, width=2)

        # Draw points
        for x, y in scaled:
            canvas.create_oval(x-2, y-2, x+2, y+2, fill=YELLOW, outline=YELLOW)

    # ── Kontrol ───────────────────────────────────────────────────────────────
    def _validate(self):
        key = self._main_api_key()
        if len(key) < 10:
            messagebox.showerror("Hata", "API anahtarını girin.")
            return None
        hybrid = self.mode_var.get() == "batch" and self.hybrid_var.get()
        if hybrid or any((self.critic_var.get(), self.polish_var.get(),
                          self.native_var.get(), self.qc_var.get())):
            roles = []
            if hybrid:                                  roles.append("analysis")
            if self.critic_var.get():                  roles.append("critic")
            if self.polish_var.get():                  roles.append("polish")
            if self.native_var.get():                  roles.append("qc")
            if self.qc_var.get():                      roles.append("qc")
            for role in roles:
                hkey = self._helper_api_key(role)
                if not hkey or len(hkey) < 10:
                    messagebox.showerror(
                        "Hata",
                        f"Yardımcı API anahtarı gerekli: {role} ({self._helper_display_name(role)})")
                    return None
        return key


    def _show_cost_estimate(self):
        """Hesaplanan tokenlara ve seçili modellere göre yaklaşık maliyet dökümü göster."""
        paths = self._get_srt_files()
        if not paths:
            messagebox.showwarning("Uyarı", "Lütfen önce SRT dosyası ekleyin.")
            return

        total_chars = 0
        for p in paths:
            try:
                blocks = list(parse_subtitle(p))
                for b in blocks:
                    total_chars += len(b[2])
            except Exception as e:
                self._log(f"Maliyet tahmini atlandı: {p}: {e}", "warn")

        if total_chars == 0:
            messagebox.showwarning("Uyarı", "Seçili dosyalarda geçerli altyazı bulunamadı.")
            return

        # Çok kaba token tahmini (yaklaşık her 4 karakter 1 token)
        base_tokens = total_chars / 4.0

        def get_price(model_name):
            if not model_name: return {"in": 0.0, "out": 0.0}
            ml = model_name.lower().strip()
            if ml in MODEL_PRICE:
                p = MODEL_PRICE[ml]
                return {"in": p, "out": p}
            for k, v in ESTIMATED_PRICES.items():
                if k in ml: return v
            self._log(f"Bilinmeyen model fiyatı, fallback kullanıldı: {model_name}", "warn")
            return ESTIMATED_PRICES["gpt-4o-mini"]  # Fallback ucuz model

        main_model = self._main_model_name()
        main_price = get_price(main_model)
        main_cost = ((base_tokens * 1.5) / 1_000_000 * main_price["in"]) + ((base_tokens * 1.1) / 1_000_000 * main_price["out"])

        details = [f"Tahmini Toplam Dosya: {len(paths)}",
                   f"Tahmini Toplam Karakter: {total_chars:,}",
                   f"Tahmini Baz Token: {int(base_tokens):,}\n",
                   f"Ana Çeviri Modeli ({main_model}): ~${main_cost:.4f}"]

        total_cost = main_cost

        # Helper passes
        hybrid = self.hybrid_var.get()
        
        if hybrid:
            # Analysis
            an_m = self._helper_api_model("analysis")
            an_p = get_price(an_m)
            an_cost = (base_tokens / 1_000_000 * an_p["in"]) + (500 / 1_000_000 * an_p["out"])
            details.append(f"└ Ön Analiz ({an_m}): ~${an_cost:.4f}")
            total_cost += an_cost

        if self.critic_var.get():
            cr_m = self._helper_api_model("critic")
            cr_p = get_price(cr_m)
            cr_cost = ((base_tokens * 2.0) / 1_000_000 * cr_p["in"]) + ((base_tokens * 0.1) / 1_000_000 * cr_p["out"])
            details.append(f"└ Critic Pass ({cr_m}): ~${cr_cost:.4f}")
            total_cost += cr_cost

        if self.polish_var.get():
            pl_m = self._helper_api_model("polish")
            pl_p = get_price(pl_m)
            pl_cost = ((base_tokens * 1.2) / 1_000_000 * pl_p["in"]) + (base_tokens / 1_000_000 * pl_p["out"])
            details.append(f"└ Polish Pass ({pl_m}): ~${pl_cost:.4f}")
            total_cost += pl_cost

        if self.qc_var.get() or self.native_var.get():
            qc_m = self._helper_api_model("qc")
            qc_p = get_price(qc_m)
            qc_cost = ((base_tokens * 2.0) / 1_000_000 * qc_p["in"]) + ((base_tokens * 0.1) / 1_000_000 * qc_p["out"])
            details.append(f"└ QC / Native Pass ({qc_m}): ~${qc_cost:.4f}")
            total_cost += qc_cost

        details.append(f"\nGenel Toplam Maliyet: ~${total_cost:.4f}")

        # ── Model karşılaştırması: mevcut plan vs gpt-5.4 (Batch, %50 indirimli) ────
        # Neden: A/B testi (2026-07-10) desync sınıfının YALNIZCA gpt-5.4-full ana
        # model olduğunda ortadan kalktığını kanıtladı; mini+geçişler bazen gpt-5.4
        # batch'e YAKIN maliyete geliyor. Yardımcı geçiş maliyetleri ana modelden
        # bağımsız olduğu için (total_cost - main_cost) aynen taşınır; yalnızca ana
        # çeviri maliyeti gpt-5.4 fiyatıyla ve batch indirimiyle yeniden hesaplanır.
        _GPT54_KEY = "gpt-5.4"
        # TAM eşleşme (startswith DEĞİL) — "gpt-5.4-mini".startswith("gpt-5.4") True
        # döner, yani prefix kontrolü mini/nano varyantlarını YANLIŞLIKLA "zaten
        # gpt-5.4" sayıp karşılaştırmayı atlardı.
        if main_model.lower().strip() != _GPT54_KEY:
            _g54_price = get_price(_GPT54_KEY)
            _g54_main_sync = ((base_tokens * 1.5) / 1_000_000 * _g54_price["in"]) + \
                            ((base_tokens * 1.1) / 1_000_000 * _g54_price["out"])
            _g54_main_batch = _g54_main_sync * 0.5   # Batch API %50 indirimli
            _passes_cost = total_cost - main_cost
            _alt_total = _g54_main_batch + _passes_cost
            details.append(
                f"\n── Karşılaştırma ──\n"
                f"Mevcut plan ({main_model}): ~${total_cost:.4f}\n"
                f"Alternatif — gpt-5.4 (Batch, %50 indirimli) + aynı geçişler: ~${_alt_total:.4f}\n"
                f"(A/B testi: cue-kayma/desync sınıfı yalnızca gpt-5.4 ana modelde "
                f"tamamen ortadan kalkıyor — önemli dosyalarda değerlendirin.)")

        messagebox.showinfo("Tahmini Maliyet Hesabı", "\n".join(details))

    def _start(self):

        if self._is_running:          # double-click guard — ikinci tık state'i bozmasın
            return
        self._is_running = True       # TOCTOU: hemen set et — _validate boyunca ikinci tık блокlanır
        try:
            key = self._validate()
        except Exception:
            self._is_running = False
            raise
        if not key:
            self._is_running = False
            return
        # NOT: Burada eskiden "çıkış klasörü girişle aynı olamaz — kaynakların üzerine
        # yazılır" diye sert bir engel vardı. Çıktı-klasörü kuralları (2026-07-10) bunu
        # GEÇERSİZ kıldı: girdi==çıktı artık kaynağın yanına DEĞİL, <girdi>/ÇIKTI/ içine
        # yazar (Kural 1, bkz. _resolve_output_path) — üzerine yazma riski yok. Engel
        # dururken Kural 1'e hiç ulaşılamıyordu (kullanıcı isteği ölü koda dönüşmüştü).
        # Ayrıca get_subtitle_files ÇIKTI alt-klasörünü girdiden dışlar, yani yeniden
        # çalıştırmada program kendi çıktısını kaynak sanmaz.
        self._save_settings()
        self._stop_flag   = False
        self._pause_btw_files.set()  # start unpaused
        self._token_total = 0
        self._token_cached = 0
        self._cost_total  = 0.0
        with self._batch_lock:
            self._active_batches.clear()   # onceki durdurulan kosudan kalanlari temizle
        self._tm.reset_session_hits()
        for attr in ("stat_tokens_var", "stat_done_var", "stat_fail_var", "stat_tm_var"):
            getattr(self, attr).set("0")
        self._set_eta("")
        self._set_running(True)

        hybrid = self.hybrid_var.get()
        mode   = self.mode_var.get()

        if hybrid:
            mm = self._helper_api_key("analysis")
            if not mm:
                messagebox.showerror("Hata", "Analiz / kalite veya OpenAI API key girin veya Hybrid modu kapatın.")
                self._set_running(False)
                return
            ext_path = self.ext_project_path_var.get().strip()
            try:
                import hybrid_translate as ht
                ext_path = ht.resolve_subtitle_project_path(ext_path)
                self.ext_project_path_var.set(ext_path)
            except Exception as e:
                messagebox.showerror("Hata", f"External Project Path geçersiz:\n{e}")
                self._set_running(False)
                return

        srt_files = self._get_srt_files()
        if srt_files:
            import hybrid_translate as ht
            turkish_files = []
            for fp in srt_files:
                try:
                    sample = read_subtitle_text(fp)[:3000]
                except Exception:
                    sample = ""
                if ht.is_source_likely_turkish(filename=fp, text=sample):
                    turkish_files.append(Path(fp).name)
            if turkish_files:
                msg = (
                    "Bu dosya(lar) zaten Türkçe görünüyor:\n"
                    + "\n".join(f"  • {f}" for f in turkish_files)
                    + "\n\nİngilizce / orijinal altyazıyı seçin."
                )
                self._log(msg.replace("\n", " | "), tag="PREFLIGHT")
                messagebox.showerror("Preflight — Türkçe Kaynak", msg)
                self._set_running(False)
                return
        if (
            srt_files
            and not self._content_type_preflight_done
            and self._auto_content_type_files(srt_files)
        ):
            if self._start_content_type_preflight(key, srt_files):
                return
        self._content_type_preflight_done = False
        self._active_snapshot = self._take_run_snapshot()

        def _guarded_worker(target, *args):
            try:
                target(*args)
            except Exception as e:
                self._log_exc("Arka plan is parcacigi hatasi", e)
                self._set_status(f"Hata: {e}")
                self._set_eta("")
                self._set_running(False)

        if hybrid and mode == "batch":
            threading.Thread(target=_guarded_worker, args=(self._run_hybrid, key, mm, ext_path), daemon=True).start()
        elif mode == "sync":
            threading.Thread(target=_guarded_worker, args=(self._run_sync, key), daemon=True).start()
        else:
            threading.Thread(target=_guarded_worker, args=(self._run_batch, key), daemon=True).start()

    def _resume(self):
        if getattr(self, "_is_running", False):
            return
        key = self._validate()
        if not key:
            return
        bid_path = _batch_id_path()
        if not bid_path.exists():
            messagebox.showerror("Hata", "batch_id.txt bulunamadı.")
            return
        self._save_settings()
        self._stop_flag = False
        self._active_snapshot = self._take_run_snapshot()
        self._pause_btw_files.set()  # resume: start unpaused
        with self._batch_lock:
            self._active_batches.clear()
        raw = bid_path.read_text(encoding="utf-8")
        batch_ids = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = re.findall(r"batch_[A-Za-z0-9]+", line) or [line]
            batch_ids.extend(parts)
        batch_ids = list(dict.fromkeys(batch_ids))
        if not batch_ids:
            messagebox.showerror("Hata", "batch_id.txt boş veya bozuk.")
            self._set_running(False)
            return

        def _guarded_resume():
            try:
                self._resume_batches(key, batch_ids)
            except Exception as e:
                self._log(f"Resume hatası: {e}", "err")
                self._log_exc("Resume", e)
                try:
                    self._set_running(False)
                except Exception:
                    pass

        threading.Thread(target=_guarded_resume, daemon=True).start()

    def _import_jsonl(self):
        """Manuel indirilen batch JSONL → SRT dönüştürücü."""
        self.attributes("-topmost", True)
        jsonl_path = filedialog.askopenfilename(
            parent=self, title="Batch Output JSONL seç",
            filetypes=[("JSONL", "*.jsonl"), ("Tümü", "*.*")])
        self.attributes("-topmost", False)
        if not jsonl_path:
            return

        self.attributes("-topmost", True)
        orig_path = filedialog.askopenfilename(
            parent=self, title="Orijinal SRT dosyasını seç (timestamps için)",
            filetypes=[("SRT", "*.srt"), ("Tümü", "*.*")])
        self.attributes("-topmost", False)
        if not orig_path:
            return

        self.attributes("-topmost", True)
        out_path = filedialog.asksaveasfilename(
            parent=self, title="Çevrilmiş SRT olarak kaydet",
            defaultextension=".srt",
            filetypes=[("SRT", "*.srt")],
            initialfile=Path(orig_path).stem + "_tr.srt")
        self.attributes("-topmost", False)
        if not out_path:
            return

        self._set_running(True)
        src = self.src_var.get()
        tgt = self.tgt_var.get()
        clean_sdh_on = self.clean_sdh_var.get()
        polish_on = self.polish_var.get()
        profanity = self.profanity_var.get()
        schema = self._get_schema()

        def _do():
            api_key = self._main_api_key()
            b_url = self._main_api_base_url()
            self._set_status("JSONL → SRT dönüştürülüyor...")
            try:
                # Timestamps from original SRT
                ts_map = {}
                cues = list(parse_srt(orig_path))
                for block in cues:
                    ts_map[block[0].strip()] = block[1].strip()

                # Translations from JSONL
                trans = {}
                errors = 0
                total_tokens = 0
                with open(jsonl_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        # Tek bozuk satır TÜM dönüştürmeyi kaybetmesin — atla, gerisi işlensin
                        try:
                            obj = json.loads(line)
                            if obj.get("error"):
                                errors += 1
                                continue
                            body = obj["response"]["body"]
                            if body.get("usage"):
                                total_tokens += body["usage"].get("total_tokens", 0)
                            choices = body.get("choices") or []
                            raw = ((choices[0].get("message") or {}).get("content") or "").strip() if choices else ""
                        except Exception as e:
                            errors += 1
                            self._log(f"JSONL satırı atlanıyor (parse hatası): {e}", "warn")
                            continue
                        cid_pp = obj.get("custom_id", "?")
                        parsed = None
                        try:
                            parsed = json.loads(_extract_json_array(raw))
                        except Exception:
                            pass
                        if isinstance(parsed, list):
                            for it in parsed:
                                if isinstance(it, dict) and "i" in it and "t" in it:
                                    trans[str(it["i"])] = it["t"]
                        elif parsed is None:
                            self._log(f"Post-process {cid_pp}: JSON parse başarısız "
                                      f"(ham: {raw[:60]!r})", "err")

                self._update_tokens(total_tokens)
                self._log(f"JSONL: {len(trans)} satır çevrilmiş | {errors} hatalı chunk | "
                          f"{len(ts_map)} timestamp", "info")

                # Build blocks using original timestamps
                blocks = []
                missing = 0
                for idx_str in sorted(ts_map, key=lambda x: int(x) if x.isdigit() else 0):
                    ts  = ts_map[idx_str]
                    txt = trans.get(idx_str, "[HATA]")
                    if txt == "[HATA]":
                        missing += 1
                    blocks.append((idx_str, ts, txt))

                # Apply SDH cleaning if enabled
                if clean_sdh_on:
                    blocks = clean_sdh(blocks)

                # Apply Polish Pass if enabled
                if polish_on and blocks:
                    self._set_status("Doğallaştırma...")
                    self._log(f"Polish Pass başlıyor ({len(blocks)} satır)...", "info")
                    _mm_key = self._helper_api_key("polish")
                    _mm_url = self._helper_api_base_url("polish")
                    _mm_mdl = self._helper_api_model("polish")
                    blocks = self._polish_pass(
                        blocks, tgt, _mm_key, _mm_url, _mm_mdl,
                        src_map=_src_map_from_cues(cues))
                    self._log("Polish Pass tamamlandı", "ok")
                    blocks, _ = ht.final_consistency_sweep(cues, blocks, log_fn=self._log)

                # Çevrilemeyen satırları sync ile onarma denemesi
                if missing:
                    try:
                        _raw_map_pre = _raw_src_map_from_cues(cues)
                        _repair_client = OpenAI(api_key=api_key, base_url=b_url if b_url else None)
                        blocks, _n_repaired = _repair_untranslated_sync(
                            blocks, _raw_map_pre, _repair_client,
                            src_lang=src, tgt_lang=tgt,
                            model="gpt-5.4-mini", # Kullanıcı isteği üzerine hep gpt-5.4-mini
                            schema=schema, profanity=profanity,
                            log_fn=self._log, token_cb=self._update_tokens)
                    except Exception:
                        pass
                    
                    # [HATA] satırlarını görünür işaretle bırak + etiketleri geri uygula
                    try:
                        _raw_map = _raw_src_map_from_cues(cues)
                        blocks, _n_filled_save = _fill_hata_with_source(blocks, _raw_map, log_fn=self._log)
                        blocks = _restore_tags_blocks(blocks, _raw_map)
                    except Exception:
                        pass
                else:
                    try:
                        blocks = _restore_tags_blocks(blocks, _raw_src_map_from_cues(cues))
                    except Exception:
                        pass

                write_srt(out_path, self._maybe_merge_cues(blocks))
                self._log(f"Kaydedildi: {out_path}  ({len(blocks)} satır, {missing} eksik)", "ok")
                _post_ui(self, messagebox.showinfo, "Tamamlandı",
                              f"{len(blocks)} satır SRT'ye dönüştürüldü!\n"
                              f"{missing} satır eksik (orijinalde vardı ama çeviri yok)\n\n"
                              f"Konum:\n{out_path}")
            except Exception as e:
                self._log(f"Dönüştürme hatası: {e}", "err")
                # 'e' except bloğu bitince silinir; after() lambda'yı SONRA çalıştırır —
                # mesajı default argümana bağla, yoksa lambda NameError verir
                _post_ui(self, messagebox.showerror, "Hata", str(e))
            finally:
                self._set_running(False)
                self._set_status("Hazır.")

        threading.Thread(target=_do, daemon=True).start()

    # ── Aktif batch muhasebesi (durdururken uzak iptal için) ──────────────────
    def _register_batch(self, batch_id: str, api_key: str, base_url: str = ""):
        if not batch_id:
            return
        with self._batch_lock:
            self._active_batches[batch_id] = (api_key, base_url or "")
            self._write_batch_owner()

    def _unregister_batch(self, batch_id: str):
        with self._batch_lock:
            self._active_batches.pop(batch_id, None)
            self._write_batch_owner()

    def _write_batch_owner(self):
        """Bu sürecin ÜZERİNDE ÇALIŞTIĞI batch'leri işaretler (batch_owner_<pid>.json).

        Başka bir uygulama örneği açılış kontrolünde bunu okur ve canlı sahibi olan
        batch'ler için 'Yarım Kalan Batch'ler' penceresini AÇMAZ — bkz.
        _live_owned_batch_ids. YALNIZCA kendi pid dosyamıza dokunulur; başka bir sürecin
        kilidi asla ezilmez/silinmez. Aktif batch kalmayınca kendi dosyamız silinir."""
        import os as _os
        with self._batch_lock:
            try:
                p = state_path(__file__, f"{_BATCH_OWNER_PREFIX}{_os.getpid()}.json")
                ids = sorted(self._active_batches.keys())
                if not ids:
                    p.unlink(missing_ok=True)
                    return
                atomic_write_json(p, {"pid": _os.getpid(), "ts": time.time(),
                                      "batch_ids": ids})
            except Exception:
                pass   # kilit yazılamazsa eski davranışa düşülür (fail-open)

    def _clear_batch_recovery(self, batch_ids):
        """Verilen batch'lerin kurtarma dosyalarını (batch_fmap_<id>.json) siler ve
        bu id'leri batch_id.txt'den çıkarır (dosya boşalırsa siler).

        Tamamlanan işten sonra çağrılır — yoksa '↺ Batch'i Devam Ettir' zaten biten
        işi yeniden indirip (hybrid'de) işlenmiş çıktının üzerine yazardı."""
        base = state_dir(__file__)
        done = {str(b).strip() for b in (batch_ids or []) if str(b).strip()}
        if not done:
            return
        for bid in done:
            try:
                (base / f"batch_fmap_{bid}.json").unlink(missing_ok=True)
            except Exception:
                pass
        try:
            mutate_batch_ids(_batch_id_path(), remove=done)
        except Exception:
            pass

    def _cancel_active_batches(self):
        """Açık OpenAI batch'lerini iptal eder + kurtarma dosyalarını temizler.
        UI'ı bloklamamak için arka plan thread'inde çağrılmalı."""
        with self._batch_lock:
            items = list(self._active_batches.items())
            self._active_batches.clear()
        cancelled = []
        for bid, auth in items:
            if isinstance(auth, (tuple, list)):
                key, base_url = auth[0], auth[1] if len(auth) > 1 else ""
            else:
                key, base_url = auth, ""
            try:
                OpenAI(api_key=key, base_url=base_url or None).batches.cancel(bid)
                self._log(f"Batch iptal edildi: {bid}", "ok")
                cancelled.append(bid)
            except Exception as e:
                self._log(f"Batch iptal edilemedi ({bid}): {e}", "warn")
        self._clear_batch_recovery(cancelled)
    def _toggle_pause_between_files(self):
        if self._pause_btw_files.is_set():
            self._pause_btw_files.clear()
            self.pause_btn.configure(fg_color="#4a3510", text="\u25b6  Devam", hover_color="#6a4520")
            self._log("Duraklat\u0131ld\u0131 \u2014 mevcut dosya bitince duracak", "warn")
        else:
            self._pause_btw_files.set()
            self.pause_btn.configure(fg_color=CARD, text="\u23f8  Duraklat", hover_color=BORDER)
            self._log("Devam ediliyor...", "ok")


    def _wait_between_files(self, file_index: int, total_files: int, current_filename: str = "") -> str:
        """Dosya tamamlandıktan sonra, eğer sonraki dosya varsa ve 'Duraklat' düğmesine basılmışsa
        worker iş parçacığını duraklatır.

        Returns:
            "continue": Bir sonraki dosyaya geçilebilir (duraklatılmamış veya kullanıcı Devam'a bastı).
            "stopped":  Kullanıcı 'Durdur' düğmesine bastı (self._stop_flag True oldu).
        """
        import time
        if getattr(self, "_stop_flag", False) or file_index >= total_files - 1:
            return "stopped" if getattr(self, "_stop_flag", False) else "continue"

        if not self._pause_btw_files.is_set():
            fn_label = f" — '{current_filename}' tamamlandı." if current_filename else "."
            self._log(f"Duraklatıldı{fn_label} Devam bekleniyor...", "warn")
            self._set_status("Duraklatıldı — Devam bekleniyor...")

            while not self._pause_btw_files.is_set():
                if getattr(self, "_stop_flag", False):
                    return "stopped"
                self._pause_btw_files.wait(timeout=0.2)

            if getattr(self, "_stop_flag", False):
                return "stopped"

            self._log("Devam ediliyor...", "ok")
            self._set_status("Çeviriliyor...")

        return "continue"

    def _stop(self):
        self._stop_flag = True
        self._pause_btw_files.set()
        self._log("Durduruluyor...", "warn")
        self._set_status("Durduruluyor...")
        with self._batch_lock:
            n_active = len(self._active_batches)
        if n_active:
            ans = messagebox.askyesno(
                "Durdur",
                f"OpenAI'da bekleyen {n_active} batch de iptal edilsin mi?\n\n"
                "Hayır derseniz batch'ler sunucuda tamamlanır; daha sonra "
                "'↺ Batch'i Devam Ettir' ile sonuçları alabilirsiniz.\n"
                "Evet derseniz iptal edilir (faturalanmayı durdurur).")
            if ans:
                threading.Thread(target=self._cancel_active_batches, daemon=True).start()

    def _get_srt_files(self):
        if self._selected_files:
            files = list(self._selected_files)
        elif getattr(self, "_input_folder_explicitly_selected", False):
            root = (self.input_var.get() or "").strip()
            if not root:
                return []
            files = get_subtitle_files(root, recursive=True)
        else:
            files = []
        files = self._dedupe_paths(files)
        # Dizi hafızası açıkken bölüm sırasına diz (E01 kararları E02'ye aksın)
        if getattr(self, "series_memory_var", None) and self.series_memory_var.get():
            files = series_memory.sort_files_by_episode(files)
        return files

    def _series_mem_for(self, fp: str):
        """Dosya için (SeriesMemory, sezon, bölüm) döner; dizi değilse/kapalıysa (None,None,None)."""
        if not (getattr(self, "series_memory_var", None) and self.series_memory_var.get()):
            return None, None, None
        key = series_memory.parse_series_key(fp)
        if key is None:
            return None, None, None
        slug, season, ep = key
        input_dir = self.input_var.get() or str(Path(fp).parent)
        try:
            return series_memory.SeriesMemory.load(input_dir, slug), season, ep
        except Exception:
            return None, None, None

    def _series_hint_for(self, fp: str) -> str:
        sm_obj, _, _ = self._series_mem_for(fp)
        return sm_obj.build_hint() if sm_obj else ""

    def _estimate_async(self, files, label_fn):
        """estimate_tokens'i arka planda çalıştırır — klasör/dosya seçince UI donmaz.
        label_fn(total_blocks, est_k) → file_info_var'a yazılacak metni döner."""
        files = list(files)
        n = len(files)
        self._set_stat(self.stat_files_var, str(n))
        self.file_info_var.set(f"⏳  {n} dosya  •  token hesaplanıyor…")
        _cs = self._chunk_size
        def _work():
            try:
                est, total_blocks = estimate_tokens(files, chunk_size=_cs)
            except Exception:
                return
            est_k = f"{est/1000:.0f}k"
            def _upd():
                try:
                    self.file_info_var.set(label_fn(total_blocks, est_k))
                    self._set_stat(self.stat_blocks_var, str(total_blocks))
                except Exception:
                    pass
            _post_ui(self, _upd)
        threading.Thread(target=_work, daemon=True).start()

    # ── Bağlam İncelemesi (Batch sonrası ikinci geçiş) ────────────────────────
    def _save_raw_backup(self, out_path, raw_blocks, raw_map):
        """Kalite geçişlerinden ÖNCEKİ ham çeviriyi <stem>.ham.srt olarak yedekler.

        critic/polish/native/geri-çeviri/QC ham çeviriyi değiştirebilir; bu yedek
        onlardan ETKİLENMEZ — kullanıcı 'orijinal çeviri dosyasına dokunulmasın' istedi.
        Geçerli/oynatılabilir olsun diye yalnız [HATA] işaretleme + etiket geri yükleme
        uygulanır (kalite geçişi değil, sonlandırma adımı). Cue birleştirme de YOK —
        orijinal satır sınırları korunur."""
        try:
            if not self.backup_raw_var.get():
                return
        except Exception:
            return
        try:
            blk = list(raw_blocks)
            if raw_map:
                try:
                    blk, _ = _fill_hata_with_source(blk, raw_map)
                    blk = _restore_tags_blocks(blk, raw_map)
                except Exception:
                    pass
            bpath = str(Path(out_path).with_suffix(".ham.srt"))
            write_srt(bpath, blk)
            self._log(f"Ham çeviri yedeği: {Path(bpath).name}", "info")
        except Exception as e:
            self._log(f"Ham yedek yazılamadı: {e}", "warn")

    def _maybe_backtranslation_check(self, out_path, src_clean_map, blocks):
        """Geri çeviri anlam kontrolü. Açıksa çalışır: Türkçeyi tekrar
        kaynağa çevirip anlamca sapan satırları bulur, <stem>.geri_ceviri.txt'e +
        log'a yazar. Flag'lenen satırları helper model ile düzeltir."""
        try:
            if not self.backtrans_var.get():
                return
        except Exception:
            return
        if not src_clean_map or not blocks:
            return
        try:
            import hybrid_translate as ht
            flags = ht.back_translation_check(
                src_map=src_clean_map, tr_blocks=blocks,
                api_key=self._helper_api_key("qc"),
                base_url=self._helper_api_base_url("qc"),
                model=self._helper_api_model("qc"),
                src_lang=self.src_var.get() or "English",
                tgt_lang=self.tgt_var.get() or "Turkish",
                log_fn=self._log, token_callback=self._update_tokens)
            if not flags:
                return
            # Fix mode: flagged satırları helper ile düzelt
            fix_client = None
            fix_key = self._helper_api_key("qc")
            fix_url = self._helper_api_base_url("qc")
            fix_model = self._helper_api_model("qc")
            n_fixed = 0
            for f in flags:
                try:
                    src, tr, back, reason = f.get("src",""), f.get("tr",""), f.get("back",""), f.get("reason","")
                    idx = f["idx"]
                    if not tr or tr == "[HATA]":
                        continue
                    from hybrid_translate import _safe_chat_create, validate_polish_candidate
                    from openai import OpenAI
                    if fix_client is None:
                        fix_client = OpenAI(api_key=fix_key, base_url=fix_url)
                    fix_prompt = (
                        f"Fix the Turkish subtitle translation below. The original source is '{src}'.\n"
                        f"Current translation: '{tr}'.\n"
                        f"Back-translation of your current Turkish: '{back}'.\n"
                        f"Issue detected by back-translation comparison: {reason}.\n\n"
                        f"Translate the source '{src}' correctly into natural Turkish. "
                        f"Output ONLY the fixed Turkish text, nothing else."
                    )
                    resp = _safe_chat_create(
                        fix_client, model=fix_model,
                        messages=[{"role": "user", "content": fix_prompt}],
                        max_tokens=200, temperature=0.2,
                    )
                    fixed_text = (resp.choices[0].message.content or "").strip() if resp.choices else ""
                    if not fixed_text:
                        continue
                    fixed_text = fixed_text.strip("\"'")
                    ok, _reason = validate_polish_candidate(tr, fixed_text, source_text=src)
                    if ok:
                        for i, (b_idx, b_ts, b_text) in enumerate(blocks):
                            if str(b_idx) == idx:
                                blocks[i] = (b_idx, b_ts, fixed_text)
                                n_fixed += 1
                                break
                except Exception:
                    pass
            # Rapor yaz
            try:
                rpath = str(Path(out_path).with_suffix(".geri_ceviri.txt"))
                out = [f"# Geri Çeviri Anlam Kontrolü — {len(flags)} satır ({n_fixed} düzeltildi)",
                       f"# {n_fixed} satır otomatik düzeltildi, {len(flags) - n_fixed} rapor-only.", ""]
                for f in flags:
                    out.append(f"[{f['idx']}] sebep: {f['reason']}")
                    out.append(f"  kaynak     : {f['src']}")
                    out.append(f"  çeviri     : {f['tr']}")
                    out.append(f"  geri çeviri: {f['back']}")
                    out.append("")
                with open(rpath, "w", encoding="utf-8") as fh:
                    fh.write("\n".join(out))
                self._log(f"Geri çeviri raporu: {Path(rpath).name} ({len(flags)} satır)", "info")
            except Exception as _re:
                self._log(f"Geri çeviri raporu yazılamadı: {_re}", "warn")
        except Exception as e:
            self._log(f"Geri çeviri kontrolü hatası: {e}", "warn")

    def _locked_terms_hint(self, fp: str, tgt: str) -> str:
        """Batch inceleme için kilitli terim + isim bloğu.

        Dosya sözlüğü + proje hafızası sözlüğünü birleştirir (kimlik 'x -> x'
        çiftlerini eler), karakter isimlerini ayrı 'değiştirme' listesine koyar.
        Böylece review pass terim/isim tutarsızlığını yalnız sezgiyle değil,
        sabit referansla düzeltebilir. Boşsa '' döner."""
        try:
            import hybrid_translate as ht
            terms = {}
            try:
                terms.update(ht.load_glossary(self._get_file_glossary(fp)) or {})
            except Exception:
                pass
            if self._pm is not None:
                try:
                    terms.update(self._pm.get_glossary() or {})
                except Exception:
                    pass
            locked = [(s, t) for s, t in terms.items()
                      if s and t and str(s).strip().lower() != str(t).strip().lower()]
            names = []
            if self._pm is not None:
                try:
                    names = [n for n in (self._pm.get_characters() or {}).keys() if n]
                except Exception:
                    names = []
            if not locked and not names:
                return ""
            parts = []
            if locked:
                rows = "; ".join(f"{s} -> {t}" for s, t in locked[:60])
                parts.append(
                    f"\n## LOCKED TERMS (source term -> required {tgt} rendering; if a reviewed "
                    f"line renders that term differently, fix it to this):\n" + rows)
            if names:
                parts.append(
                    "\n## LOCKED NAMES (character/proper names — must appear verbatim, do NOT "
                    "translate or alter):\n" + ", ".join(names[:40]))
            return "".join(parts)
        except Exception:
            return ""

    def _review_pass(self, fp: str, sorted_blocks: list, model: str, tgt: str) -> tuple:
        """Batch çevirisi sonrası ana modelle tam-bağlam incelemesi. (bloklar, düzeltme_sayısı) döner.

        Batch modunda chunk'lar birbirinin çevirisini göremez (istekler önceden
        paketlenir); bu geçiş bütün dosyayı kaynakla karşılaştırarak sırayla okur,
        terim/hitap tutarsızlıklarını ve çeviri hatalarını düzeltir."""
        REVIEW_CHUNK = 80
        REVIEW_CTX   = 8   # önceki chunk'tan taşınan bağlam çifti sayısı
        try:
            b_url = self._main_api_base_url()
            client = OpenAI(api_key=self._main_api_key(), base_url=b_url if b_url else None)
        except Exception as e:
            self._log_exc("Bağlam incelemesi başlatılamadı", e)
            return sorted_blocks, 0

        src_cues = self._cached_blocks_for(fp)
        if src_cues is None:
            try:
                src_cues = list(parse_subtitle(fp))
            except Exception:
                src_cues = []
        src_map = _src_map_from_cues(src_cues)
        if not src_map:
            self._log("Bağlam incelemesi: kaynak metin bulunamadı, atlandı", "warn")
            return sorted_blocks, 0
        import hybrid_translate as ht

        sys_prompt = (
            f"You are a senior {tgt} subtitle QA reviewer. You receive source+translation pairs "
            f"from ONE film, in chronological order, with full context.\n"
            "Fix ONLY lines that have a real problem:\n"
            "- mistranslation (meaning differs from source)\n"
            "- inconsistent terminology or character names vs earlier lines\n"
            "- sen/siz (T-V) register breaks between the same speakers\n"
            "- unnatural literal phrasing a native speaker would never say\n"
            "- word-for-word rendering that misses intent, implication, joke, threat, sarcasm, or documentary logic\n"
            "- choppy line flow or wording too long for the available subtitle duration\n"
            "- untranslated source-language words left in the text\n"
            "Use sense-for-sense Turkish only when supported by the visible source words and surrounding context: "
            "preserve what the line is doing, not the source wording; do not add unstated ideas, and keep fixes concise. "
            "Duration/CPS beats source length: prefer <=21 CPS and avoid >24 CPS when possible.\n"
            "Preserve polarity, questions, and numbers exactly: negative stays negative, questions stay questions, "
            "and digits/dates/amounts keep the same value.\n"
            "Rules: preserve \\n line breaks exactly; keep similar length (subtitle reading "
            "speed matters); do NOT touch lines that are already correct.\n"
            "Input JSON keys:\n"
            '  "ctx"    — earlier reviewed pairs (do NOT output these, reference only)\n'
            '  "review" — pairs to review: [{"i":N,"src":"...","tr":"..."}]\n'
            'Output: JSON array of ONLY the corrected items [{"i":N,"t":"fixed translation"}]. '
            "Return [] if nothing needs fixing. Return ONLY the JSON array."
        )
        sys_prompt += self._locked_terms_hint(fp, tgt)   # kilitli sözlük/isim referansı (#7)

        # Fragment gruplarını hesapla (EARLY_VERB_CLOSURE tespiti için)
        review_frag_tags = {}
        review_frag_group_ids = {}
        review_fragment_groups = []
        try:
            if src_cues:
                review_frag_tags = ht._tag_fragments([
                    c for c in src_cues if hasattr(c, "text")])
                review_frag_group_ids, review_fragment_groups = ht._fragment_groups(src_cues, review_frag_tags)
        except Exception:
            pass

        result      = list(sorted_blocks)
        pos_by_idx  = {str(b[0]): k for k, b in enumerate(result)}
        total_chunks = math.ceil(len(result) / REVIEW_CHUNK)
        fixed_total = 0
        review_rejected = 0
        review_rejected_reasons = {}
        for cs in range(0, len(result), REVIEW_CHUNK):
            if self._stop_flag:
                break
            chunk = result[cs:cs + REVIEW_CHUNK]
            current_idxs = {str(idx) for idx, ts, text in chunk}   # yalnız bu chunk'ın id'leri
            items = [{"i": idx, "src": src_map.get(str(idx), ""), "tr": text}
                     for idx, ts, text in chunk
                     if not str(text).startswith("[HATA")]
            for it in items:
                tag = review_frag_tags.get(it["i"], "none")
                if tag != "none":
                    it["frag"] = tag
                    if it["i"] in review_frag_group_ids:
                        it["frag_group"] = review_frag_group_ids[it["i"]]
            if not items:
                continue
            payload = {"review": items}
            chunk_ids = {it["i"] for it in items}
            chunk_groups = [
                g for g in review_fragment_groups
                if any(str(g_item) in chunk_ids for g_item in g.get("items", []))
            ]
            if chunk_groups:
                payload["sentence_groups"] = chunk_groups
            if cs > 0:
                # Önceki chunk'ın (incelenmiş) son satırları — tutarlılık referansı
                ctx = [{"i": idx, "src": src_map.get(str(idx), ""), "tr": text}
                       for idx, ts, text in result[max(0, cs - REVIEW_CTX):cs]
                       if not str(text).startswith("[HATA")]
                if ctx:
                    payload["ctx"] = ctx
            chunk_no = cs // REVIEW_CHUNK + 1
            try:
                resp = _safe_chat_create(
                    client, model=model,
                    messages=[{"role": "system", "content": sys_prompt},
                              {"role": "user",
                               "content": json.dumps(payload, ensure_ascii=False)}],
                    max_tokens=REVIEW_CHUNK * 80,
                    temperature=0.2,
                )
                if resp.usage:
                    tot, cached = _get_usage_details(resp.usage)
                    self._update_tokens(tot, cached=cached)
                raw   = _extract_json_array((resp.choices[0].message.content or "").strip())
                fixes = json.loads(raw) if raw.strip() else []
                if not isinstance(fixes, list):
                    fixes = []
                for it in fixes:
                    if not (isinstance(it, dict) and "i" in it and "t" in it):
                        continue
                    if str(it["i"]) not in current_idxs:
                        continue   # model ctx satırının idx'ini döndürdü → önceki chunk'ı EZME
                    pos   = pos_by_idx.get(str(it["i"]))
                    new_t = str(it["t"]).strip()
                    if pos is None or not new_t:
                        continue
                    old_idx, old_ts, old_t = result[pos]
                    if new_t != old_t and not old_t.startswith("[HATA"):
                        neighbor_start = max(0, pos - 2)
                        neighbor_end = min(len(result), pos + 3)
                        neighbor_texts = [
                            result[n][2] for n in range(neighbor_start, neighbor_end)
                            if n != pos
                        ]
                        fragment_tag = (
                            review_frag_tags.get(old_idx)
                            or review_frag_tags.get(str(old_idx))
                            or review_frag_tags.get(it["i"])
                            or review_frag_tags.get(str(it["i"]))
                            or "none"
                        )
                        ok, reason = ht.validate_polish_candidate(
                            old_t,
                            new_t,
                            source_text=src_map.get(str(old_idx), ""),
                            neighbor_texts=neighbor_texts,
                            fragment_tag=fragment_tag,
                        )
                        if not ok:
                            review_rejected += 1
                            review_rejected_reasons[reason] = review_rejected_reasons.get(reason, 0) + 1
                            continue
                        result[pos] = (old_idx, old_ts, new_t)
                        fixed_total += 1
                        self._log(f"  ✏ İnceleme #{old_idx}: {old_t!r}", "warn")
                        self._log(f"       → {new_t!r}", "ok")
                self._set_status(f"Bağlam incelemesi {chunk_no}/{total_chunks} — {Path(fp).name}")
            except Exception as e:
                self._log_exc(f"Bağlam incelemesi chunk {chunk_no}/{total_chunks} hatası", e)
        if review_rejected:
            reason_bits = ", ".join(
                f"{reason}:{count}" for reason, count in sorted(review_rejected_reasons.items())
            )
            self._log(
                f"Bağlam incelemesi: {review_rejected} öneri güvenlik filtresinden döndü ({reason_bits})",
                "warn",
            )
        self._log(f"Bağlam incelemesi: {fixed_total} satır düzeltildi / {len(result)} toplam",
                  "ok" if fixed_total else "info")
        return result, fixed_total

    def _cached_blocks_for(self, fp: str):
        cache = getattr(self, "_block_cache", None)
        if isinstance(cache, dict):
            return cache.get(fp)
        return None

    # ── Polish Pass ───────────────────────────────────────────────────────────
    def _polish_pass(self, sorted_blocks: list, tgt: str,
                     helper_key: str, helper_url: str, helper_model: str,
                     src_map: dict = None, analysis_result=None) -> list:
        """Second-pass naturalisation using the helper model gpt-5.4-mini (cost-efficient).

        src_map: {idx_str: kaynak metin} — verilirse her satıra 'en' alanı eklenir;
        editör anlamı kaynaktan doğrular, anlam kayması engellenir."""
        POLISH_CHUNK = 150  # Balanced: large enough to be fast, small enough to avoid API limits
        POLISH_CTX   = 6    # önceki chunk'ın son N cilalı satırı — üslup sürekliliği
        from openai import OpenAI as _OAI
        import hybrid_translate as ht
        client = _OAI(api_key=helper_key, base_url=helper_url)
        src_map = src_map or {}
        
        # Reconstruct mock cues for fragment tagging
        frag_tags = {}
        frag_group_ids = {}
        fragment_groups = []
        if src_map:
            class MockCue:
                def __init__(self, index, text):
                    self.index = index
                    self.text = text
            mock_cues = []
            for idx, ts, text in sorted_blocks:
                src_t = src_map.get(str(idx), "")
                mock_cues.append(MockCue(idx, src_t))
            try:
                from hybrid_translate import _fragment_groups, _tag_fragments
                frag_tags = _tag_fragments(mock_cues)
                frag_group_ids, fragment_groups = _fragment_groups(mock_cues, frag_tags)
            except Exception:
                frag_tags = {}
                frag_group_ids = {}
                fragment_groups = []
                
        context_hint = ht.build_polish_context_hint(analysis_result, tgt_lang=tgt)
        sys_prompt = (
            f"Sen deneyimli bir {tgt} altyazı editörüsün. Sana makine tarafından çevrilmiş altyazılar gelecek.\n"
            f"Görevin: Anlam ve satır sayısını KORUYARAK dili insan çevirisi kalitesine yükselt.\n\n"
            f"{context_hint}"
            f"ANLAM ÖNCELİĞİ: Kaynak satırın sahnede ne demek istediğini, alt metnini ve konuşma eylemini yalnızca "
            f"görünen kaynak sözlerden ve çevre bağlamdan çıkar; keyfi yorum veya yeni bilgi ekleme. Türkçeyi buna "
            f"göre kur. Kelime kelime cilalama yapma. Anlam, bilgi ve ton değişmeyecekse Türkçe söz dizimini ve "
            f"ifadeyi doğallaştır. Süre/CPS kaynak uzunluğundan önceliklidir: hedef <=21 CPS, mümkünse 24 CPS'i "
            f"aşma; kısa ve okunabilir kal.\n\n"
            f"TEMEL KURALLAR:\n"
            f"1. Yeniden çevirme — orijinal anlamı değiştirme, sadece dil akışını düzelt. Emin değilsen satırı AYNEN döndür.\n"
            f"2. Satır sayısını ve \\n karakterlerini koru — ekstra satır ekleme, mevcut satırları birleştirme.\n"
            f"3. Orijinaldeki karakter sayısına yakın kal — Türkçe altyazı ekonomisi önemli, izleyici hızlı okur.\n\n"
            f"KORUMA RAYLARI:\n"
            f"- Sayıları, tarihleri, saatleri, ölçüleri, para birimlerini ve teknik kodları değiştirme.\n"
            f"- Olumsuzluğu, soru kipini ve sayısal değeri aynen koru: olumsuz olumluya dönmez, soru soru kalır, rakam/tarih/tutar değişmez.\n"
            f"- <i>, <b>, <u>, ASS biçim etiketleri ve konuşmacı tirelerini koru.\n"
            f"- [SFX]/[ACTION]/ekran yazısı etiketlerini silme; zaten Türkçeyse aynen bırak.\n"
            f"- Özel isim, marka, yer adı ve evren terimlerini bağlam/glossary gerektirmedikçe değiştirme.\n"
            f"- Kaynak anlamı ile mevcut çeviri çelişiyorsa yalnızca o çelişkiyi düzelt; yeni bilgi ekleme.\n"
            f"- MUHAFAZAKÂR CİLA: Yalnızca yazım hatası, noktalama, büyük-küçük harf, barok yapı (İngilizce söz dizimi → "
            f"doğal Türkçe SOV) ve doğallık sorunlarını düzelt. TÜMCE İÇERİĞİNİ YENİDEN YAZMA. Anlam, bilgi ve "
            f"içerik kelimeleri (isim, fiil, sıfat) aynı kalmalı. Emin değilsen satırı AYNEN bırak.\n"
            f"- AŞIRI DEĞİŞİM RİSKİ: Bir satırda tüm içerik kelimelerini değiştirme; bu anlam kaymasıdır. "
            f"Yüzey düzeltmeleri (imlâ/noktalama) yeterliyse, satırı olduğu gibi bırak.\n\n"
            f"DÜZELTİLECEKLER:\n"
            f"- Çoklu Satır Akışı & Söz Dizimi (Sondan Başa İlerleme): Eğer ardışık satırlarda 'frag' alanı varsa ('start', 'mid', 'end'), bu satırlar tek bir İngilizce cümlenin parçalarıdır. Türkçe çevirilerde İngilizce söz dizimi (SVO) sırası nedeniyle bilgi akışının 'sondan başa' gidiyor gibi durmasını (örn. erken yüklem kapanıp nesnelerin arkadan gelmesini) engelle. Bilgileri/kelimeleri bu satırlar arasında Türkçe kurallarına göre (SOV) yeniden dağıt. Cümle en son satırda ('end') yüklemle bitsin, önceki satırlar ('start', 'mid') Türkçe'de devam bekleyen yapıda olsun.\n"
            f"- Literalizm: 'benim için' → 'bence', 'sahip olmak' → 'var', 'gerçekleştirmek' → 'yapmak'\n"
            f"- Aşırı resmiyet: 'müzakere etmek' → 'konuşmak', 'istihdam' → 'iş', 'ikamet' → 'oturma'\n"
            f"- İngilizce kalıntılar: ass→göt, shit→bok, fuck→sik-, damn→kahretsin, bro→lan/abi\n"
            f"- Yapay Türkçe: 'Bu doğru değil mi?' → 'Değil mi?', 'Evet, biliyorum' → 'Biliyorum'\n"
            f"- Sen/Siz tutarsızlığı: Aynı karakterin bir cümlede 'sen' bir cümlede 'siz' demesi\n"
            f"- Okuma hızı: 42+ karakter satırlarında mümkünse kısalt, anlam kaybolmasın\n\n"
            f"DOKUNMA:\n"
            f"- Özel isimler, yer adları, marka adları\n"
            f"- Sayılar, tarihler, teknik terimler\n"
            f"- Zaten doğal olan satırlar\n\n"
            f"GİRDİ ALANLARI:\n"
            f"- 'en': satırın ORİJİNAL kaynak metni — anlam kontrolü için kullan; "
            f"düzeltmen kaynaktaki anlamdan SAPMAMALI. Çeviri kaynaktan zaten sapmışsa anlamı kaynağa göre düzelt.\n"
            f"- 'risk': bu satır için olası sorun ipuçlarıdır; yoksa satır muhtemelen daha az dokunulmalıdır.\n"
            f"- 'ctx': önceki bölümün son satırları (cilalanmış halleriyle) — üslup, terim ve sen/siz "
            f"tutarlılığı için referans; bunları ASLA çıktına ekleme.\n\n"
            f"- 'next_ctx': sonraki satırlar — devam eden cümle ve ton için referans; bunları ASLA çıktına ekleme.\n\n"
            f"- 'sentence_groups': start/mid/end satırlarının oluşturduğu tam kaynak cümlelerdir. "
            f"Önce bu bütün cümleyi anla, sonra Türkçeyi aynı id'lere doğal SOV akışla dağıt; "
            f"sentence_groups içeriğini ayrıca çıktılama.\n\n"
            f'Input: JSON {{"ctx": [...], "next_ctx": [...], "polish": [{{"id": N, "en": "source", "tr": "...", "risk": [...]}}]}}\n'
            f'Output: JSON array [{{"id": N, "tr": "polished"}}] — same IDs, same count.\n'
            f"Return ONLY the JSON array. No explanation, no preamble."
        )
        result_map = {}
        rejected = 0
        rejected_reasons = {}
        for cs in range(0, len(sorted_blocks), POLISH_CHUNK):
            if self._stop_flag:
                break
            chunk = sorted_blocks[cs:cs + POLISH_CHUNK]
            items = []
            original_by_id = {}
            neighbor_texts_by_id = {}
            for idx, ts, text in chunk:
                if str(text).startswith("[HATA"):
                    continue
                it = {"id": idx, "tr": text}
                src_t = src_map.get(str(idx))
                if src_t:
                    it["en"] = src_t
                tag = frag_tags.get(idx, "none")
                if tag != "none":
                    it["frag"] = tag
                    if idx in frag_group_ids:
                        it["frag_group"] = frag_group_ids[idx]
                risk = ht.polish_risk_hints(src_t or "", text)
                if risk:
                    it["risk"] = risk
                items.append(it)
                original_by_id[str(idx)] = text
            for pos, (idx, _ts, _text) in enumerate(chunk):
                start = max(0, pos - 2)
                end = min(len(chunk), pos + 3)
                neighbor_texts_by_id[str(idx)] = [chunk[i][2] for i in range(start, end) if i != pos]
            # Grubun BEKLENEN üyeleri (cue sırasında) — apply_polish_group_atomic'in
            # kısmi-yanıt ve birleşik-anlam kontrolleri için. [HATA] cue'ları original_by_id'de
            # olmadığından zaten dışarıda kalır.
            chunk_group_expected = {}
            for idx, _ts, _text in chunk:
                sid = str(idx)
                if sid not in original_by_id:
                    continue
                gid = frag_group_ids.get(idx, frag_group_ids.get(sid))
                if gid is not None:
                    chunk_group_expected.setdefault(gid, []).append(sid)
            if not items:
                continue
            payload = {"polish": items}
            chunk_ids = {idx for idx, _ts, _text in chunk}
            chunk_groups = [
                group for group in fragment_groups
                if any(group_item in chunk_ids for group_item in group["items"])
            ]
            if chunk_groups:
                payload["sentence_groups"] = chunk_groups
            if cs > 0:
                # Önceki chunk'ın son satırları — cilalanmış halleri öncelikli
                ctx_lines = []
                for p_idx, p_ts, p_text in sorted_blocks[max(0, cs - POLISH_CTX):cs]:
                    ctx_lines.append(result_map.get(str(p_idx), p_text))
                if ctx_lines:
                    payload["ctx"] = ctx_lines
            next_lines = []
            for n_idx, n_ts, n_text in sorted_blocks[cs + POLISH_CHUNK:cs + POLISH_CHUNK + POLISH_CTX]:
                next_lines.append(n_text)
            if next_lines:
                payload["next_ctx"] = next_lines
            chunk_num = cs // POLISH_CHUNK + 1
            total_chunks = math.ceil(len(sorted_blocks) / POLISH_CHUNK)

            for attempt in range(2):  # 1 retry on failure
                try:
                    resp = _safe_chat_create(
                        client,
                        model=helper_model,
                        messages=[
                            {"role": "system", "content": sys_prompt},
                            {"role": "user",   "content": json.dumps(payload, ensure_ascii=False)},
                        ],
                        max_tokens=max(1000, len(items) * 120),
                        temperature=0.4,
                    )
                    if not resp.choices:
                        raise RuntimeError("Polish: empty choices")
                    content = resp.choices[0].message.content or ""

                    if not content.strip():
                        raise RuntimeError("Polish: empty response from API")

                    raw = _extract_json_array(content)

                    if not raw.strip():
                        raise RuntimeError("Polish: invalid JSON response")

                    tok, cached = 0, 0
                    if resp.usage:
                        tok, cached = _get_usage_details(resp.usage)
                    self._update_tokens(tok, cached=cached)
                    polished = json.loads(raw)
                    if not isinstance(polished, list):
                        raise RuntimeError("Polish: expected JSON array")
                    chunk_proposals = {}
                    for item in polished:
                        if isinstance(item, dict) and "id" in item and "tr" in item:
                            sid = str(item["id"])
                            if sid not in original_by_id:
                                continue
                            new_text = str(item["tr"])
                            frag_key = int(sid) if sid.isdigit() else item["id"]
                            fragment_tag = frag_tags.get(item["id"], frag_tags.get(frag_key, "none"))
                            group_id = frag_group_ids.get(item["id"], frag_group_ids.get(frag_key))
                            ok, reason = ht.validate_polish_candidate(
                                original_by_id[sid],
                                new_text,
                                src_map.get(sid, ""),
                                neighbor_texts=neighbor_texts_by_id.get(sid, []),
                                fragment_tag=fragment_tag,
                            )
                            chunk_proposals[sid] = (new_text, ok, reason, group_id)
                    # Bir fragment grubunda değişen üyelerden biri reddedildiyse, model grubun
                    # yalnız bir kısmını döndürdüyse, ya da birleşik cümle anlamı bozulduysa
                    # grubun tamamı geri alınır — cümle bütünlüğü tek-tek kabulle bozulmasın.
                    chunk_result, chunk_rejected, chunk_reasons = ht.apply_polish_group_atomic(
                        chunk_proposals, original_by_id,
                        group_expected=chunk_group_expected, src_map=src_map)
                    result_map.update(chunk_result)
                    rejected += chunk_rejected
                    for _reason_key, _count in chunk_reasons.items():
                        rejected_reasons[_reason_key] = rejected_reasons.get(_reason_key, 0) + _count
                    break
                except Exception as e:
                    if attempt == 0:
                        self._log(f"Polish chunk {chunk_num}/{total_chunks} — retry...", "warn")
                        time.sleep(2)
                    else:
                        self._log_exc(f"Polish chunk {chunk_num}/{total_chunks} hatası", e)

        final = []
        changed = 0
        orig_by_id = {str(idx): text for idx, ts, text in sorted_blocks}
        for idx, ts, text in sorted_blocks:
            new_text = result_map.get(str(idx), text)
            if new_text != text:
                changed += 1
                self._log(f"  ✏ #{idx}  {text!r}", "warn")
                self._log(f"       → {new_text!r}", "ok")
            final.append((idx, ts, new_text))
        total = len(sorted_blocks)
        ratio = changed / total if total > 0 else 0
        if ratio > 0.25:
            revert_count = 0
            safe_final = []
            for idx, ts, text in sorted_blocks:
                sid = str(idx)
                new_text = result_map.get(sid, text)
                if new_text != text and not ht.is_safe_polish_edit(text, new_text):
                    safe_final.append((idx, ts, text))
                    revert_count += 1
                else:
                    safe_final.append((idx, ts, new_text))
            final = safe_final
            changed = sum(1 for idx, ts, text in final if text != orig_by_id.get(str(idx), text))
            self._log(f"Polish Pass: {changed} satır değişti / {total} toplam ({revert_count} riskli düzeltme geri alındı)", "warn")
        elif ratio > 0.15:
            self._log(f"Polish Pass: %{ratio*100:.0f} satır değişti — yüksek oran, gözden geçirilmeli", "warn")
        if rejected:
            reason_txt = ", ".join(f"{k}:{v}" for k, v in sorted(rejected_reasons.items()))
            self._log(f"Polish Pass: {rejected} öneri güvenlik filtresinden döndü ({reason_txt})", "warn")
        if ratio <= 0.25:
            self._log(f"Polish Pass: {changed} satır değişti / {total} toplam", "info")
        return final

    # ── Mevcut SRT post-işleme ────────────────────────────────────────────────
    def _post_process_existing(self):
        """Kullanıcının seçtiği SRT'ye pass seçimi dialoguyla işler."""
        paths = filedialog.askopenfilenames(
            title="Post-işlenecek SRT dosyalarını seç",
            filetypes=[("SRT dosyası", "*.srt"), ("Tüm dosyalar", "*.*")])
        if not paths:
            return

        # ── Pass seçim dialogu ────────────────────────────────────────────────
        dlg = ctk.CTkToplevel(self)
        dlg.title("✦  SRT Post-İşle")
        dlg.geometry("420x420")
        dlg.configure(fg_color=BG)
        dlg.grab_set()
        dlg.lift()
        dlg.focus_force()
        dlg.resizable(False, False)

        # Başlık
        ctk.CTkLabel(dlg, text="Hangi passları uygulayalım?",
                     font=ctk.CTkFont("Segoe UI", 14, "bold"),
                     text_color=FG).pack(pady=(20, 4))
        ctk.CTkLabel(dlg,
                     text=f"{len(paths)} dosya seçildi  •  Dosyalar ÜZERİNE yazılacak",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=FG2).pack(pady=(0, 16))

        # Checkbox'lar
        checks_fr = ctk.CTkFrame(dlg, fg_color=PANEL, corner_radius=10)
        checks_fr.pack(fill="x", padx=20, pady=(0, 16))

        passes = [
            ("🔍  Critic Pass",        "critic",        "gpt-5.4-mini ile hata tespiti"),
            ("✨  Polish Pass",        "polish",        "gpt-5.4-mini ile doğallaştırma"),
            ("🇹🇷  Native Okuyucu",   "native_reader", "Türk izleyici gözüyle doğallık"),
            ("✅  QC Kontrolü",       "qc",            "gpt-5.4-mini ile kalite kontrolü"),
            ("🧹  SDH Temizle",       "clean_sdh",     "İşitme engelli etiketleri kaldır"),
            ("↵   Satır Kırma",       "linebreak",     "42+ karakter satırları böl"),
            ("🔗  Parçalı Cue Birleştir", "merge_cues", "Kelime kelime bölünmüş cue'ları topla (dengeli 2 satır, senkron korunur)"),
            ("🤖  AI Akıllı Segmentasyon", "ai_merge", "Birleştirmenin AI'lı sürümü: anlamsal gruplama + öğe-bilinçli kırma (gpt-5.4-mini)"),
        ]

        check_vars = {}
        for i, (label, key, hint) in enumerate(passes):
            row = ctk.CTkFrame(checks_fr, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=(8 if i == 0 else 2, 8 if i == len(passes)-1 else 2))
            row.grid_columnconfigure(1, weight=1)

            var = ctk.BooleanVar(value=False)
            check_vars[key] = var

            ctk.CTkCheckBox(row, text="", variable=var,
                            width=24, height=24,
                            fg_color=ACCENT, hover_color="#5a4fd1",
                            border_color=BORDER).grid(row=0, column=0, padx=(0, 10))
            ctk.CTkLabel(row, text=label,
                         font=ctk.CTkFont("Segoe UI", 12, "bold"),
                         text_color=FG, anchor="w").grid(row=0, column=1, sticky="w")
            ctk.CTkLabel(row, text=hint,
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color=FG2, anchor="w").grid(row=1, column=1, sticky="w")

        # Butonlar
        btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_fr.pack(fill="x", padx=20, pady=(0, 20))
        btn_fr.grid_columnconfigure((0, 1), weight=1)

        result = [None]

        def confirm():
            selected = [k for k, v in check_vars.items() if v.get()]
            if not selected:
                messagebox.showwarning("Seçim yok", "En az bir pass seçin.", parent=dlg)
                return
            result[0] = selected
            dlg.destroy()

        def cancel():
            dlg.destroy()

        ctk.CTkButton(btn_fr, text="▶  Başlat", height=40,
                      font=ctk.CTkFont("Segoe UI", 13, "bold"),
                      fg_color=ACCENT, hover_color="#5a4fd1",
                      command=confirm).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(btn_fr, text="✕  İptal", height=40,
                      font=ctk.CTkFont("Segoe UI", 12),
                      fg_color=CARD, hover_color=BORDER,
                      command=cancel).grid(row=0, column=1, sticky="ew")

        dlg.protocol("WM_DELETE_WINDOW", cancel)
        self.wait_window(dlg)

        if result[0] is None:
            return  # kullanıcı iptal etti

        selected_passes = result[0]
        self._set_running(True)
        self._set_phase("Post-işlem", f"{len(paths)} dosya seçildi")
        threading.Thread(
            target=self._run_post_process,
            args=(list(paths), selected_passes),
            daemon=True).start()

    def _run_post_process(self, paths: list, selected_passes: list):
        import hybrid_translate as ht
        try:
            ht.set_project_path(self.ext_project_path_var.get().strip())
            tgt      = self.tgt_var.get()
        except Exception as e:
            # Kurulum hatası (ör. harici proje yolu) → thread sessizce ölmesin, UI'yi geri aç
            self._log_exc("Post-işlem başlatılamadı", e)
            self._set_running(False)
            self._set_eta("")
            return
        n        = len(paths)

        do_critic   = "critic"        in selected_passes
        do_polish   = "polish"        in selected_passes
        do_native   = "native_reader" in selected_passes
        do_qc       = "qc"            in selected_passes
        do_sdh      = "clean_sdh"     in selected_passes
        do_linebrk  = "linebreak"     in selected_passes
        do_merge    = "merge_cues"    in selected_passes
        do_ai_merge = "ai_merge"      in selected_passes
        mm_key = mm_url = mm_model = ""
        if do_ai_merge:
            mm_key = self._helper_api_key("analysis")
            mm_url = self._helper_api_base_url("analysis")
            mm_model = self._helper_api_model("analysis")

        self._show_progress_board(paths)

        for i, fp in enumerate(paths):
            if self._stop_flag:
                break
            if self._is_queued_file_removed(fp):
                continue
            fname = Path(fp).name
            self._log(f"\n── Post-işlem [{i+1}/{n}] {fname} ──", "info")
            self._update_file_progress(fp, "Yükleniyor", 5)

            try:
                blocks = list(parse_subtitle(fp))
                if not blocks:
                    self._log(f"{fname}: geçerli blok yok, atlandı", "warn")
                    self._update_file_progress(fp, "Atlandı", 0, "skip")
                    continue

                # Kaynağı + analiz önbelleğini DOSYA BAŞINA BİR KEZ yükle (critic/native/qc
                # paylaşır) — eskiden her geçiş dosyayı yeniden parse edip önbelleği tekrar okuyordu.
                orig_cues = None
                try:
                    orig_cues = ht.load_subtitle(fp)
                except Exception:
                    orig_cues = None
                analysis_result = (ht.load_context_cache(
                    fp,
                    expected_target=self.tgt_var.get(),
                    expected_analysis_depth=self.analysis_depth_var.get(),
                ) if (do_critic or do_polish or do_native or do_qc) else None)

                # Critic Pass
                if do_critic:
                    try:
                        self._update_file_progress(fp, "Critic Pass", 20)
                        self._set_phase("Critic Pass", f"{fname}  ({i+1}/{n})")
                        self._log(f"Critic Pass — {len(blocks)} satır...", "info")
                        _critic_change_log = []
                        blocks = ht.critic_pass_with_helper(
                            cues=orig_cues, tr_blocks=blocks,
                            helper_api_key=self._helper_api_key("critic"),
                            helper_url=self._helper_api_base_url("critic"),
                            helper_model=self._helper_api_model("critic"), tgt_lang=tgt,
                            log_fn=self._log,
                            glossary=ht.load_glossary(self._get_file_glossary(fp)),
                            analysis_result=analysis_result,
                            change_log=_critic_change_log)
                        self._write_critic_change_report(fp, _critic_change_log)
                    except Exception as e:
                        self._log(f"Critic Pass hatası: {e}", "warn")

                # Polish Pass
                if do_polish:
                    try:
                        self._update_file_progress(fp, "Polish Pass", 55)
                        self._set_phase("Polish Pass", f"{fname}  ({i+1}/{n})")
                        self._log(f"Polish Pass — {len(blocks)} satır...", "info")
                        blocks = self._polish_pass(
                            blocks, tgt,
                            self._helper_api_key("polish"), self._helper_api_base_url("polish"), self._helper_api_model("polish"),
                            src_map=_src_map_from_cues(orig_cues) if orig_cues else None,
                            analysis_result=analysis_result)
                    except Exception as e:
                        self._log(f"Polish Pass hatası: {e}", "warn")

                # Native Okuyucu Pass
                if do_native:
                    try:
                        self._update_file_progress(fp, "Native Okuyucu", 65)
                        self._set_phase("Native Okuyucu", f"{fname}  ({i+1}/{n})")
                        self._log(f"Native Okuyucu Pass — {len(blocks)} satır...", "info")
                        blocks = ht.native_reader_pass(
                            tr_blocks=blocks,
                            helper_api_key=self._helper_api_key("critic"), 
                            helper_url=self._helper_api_base_url("critic"),
                            helper_model=self._helper_api_model("critic"), tgt_lang=tgt,
                            log_fn=self._log, analysis_result=analysis_result,
                            token_callback=self._update_tokens,
                            src_map=_src_map_from_cues(orig_cues) if orig_cues else None)
                    except Exception as e:
                        self._log(f"Native Pass hatası: {e}", "warn")

                # SDH temizle
                if do_sdh:
                    try:
                        self._update_file_progress(fp, "SDH Temizle", 85)
                        blocks = clean_sdh(blocks, src_map=_src_map_from_cues(orig_cues) if orig_cues else None, source_driven=True)
                    except Exception as e:
                        self._log(f"SDH temizleme hatası: {e}", "warn")

                # Satır kırma
                if do_linebrk:
                    try:
                        self._update_file_progress(fp, "Satır Kırma", 92)
                        blocks = apply_line_breaks(blocks)
                    except Exception as e:
                        self._log(f"Satır kırma hatası: {e}", "warn")

                # QC Kontrolü
                if do_qc:
                    try:
                        self._update_file_progress(fp, "QC Kontrolü", 72)
                        self._set_phase("QC Kontrolü", f"{fname}  ({i+1}/{n})")
                        self._log(f"QC Kontrolü — {len(blocks)} satır...", "info")
                        blocks = self._run_quality_check_inline(
                            fp, orig_cues, blocks, 
                            self._helper_api_key("qc"), self._helper_api_base_url("qc"), self._helper_api_model("qc"), tgt, analysis_result=analysis_result)
                    except Exception as e:
                        self._log(f"QC hatası: {e}", "warn")

                # Parçalı cue birleştirme (en son — dengeli 2 satır, senkron korunur)
                # AI segmentasyon seçiliyse onun (anlamsal) sürümü, değilse hızlı algoritma.
                if do_ai_merge and mm_key:
                    try:
                        self._update_file_progress(fp, "AI Segmentasyon", 96)
                        _before = len(blocks)
                        blocks = ai_resegment_cues(
                            blocks, mm_key, mm_url, mm_model, log_fn=self._log,
                            max_chars=self._merge_max_chars, max_gap_ms=self._merge_max_gap_ms,
                            token_callback=self._update_tokens)
                        self._log(f"AI segmentasyon: {_before} → {len(blocks)} blok", "ok")
                    except Exception as e:
                        self._log(f"AI segmentasyon hatası: {e}", "warn")
                elif do_merge or (do_ai_merge and not mm_key):
                    try:
                        if do_ai_merge and not mm_key:
                            self._log("AI segmentasyon: API anahtarı yok, hızlı birleştirmeye düşülüyor", "warn")
                        self._update_file_progress(fp, "Cue Birleştirme", 96)
                        _before = len(blocks)
                        blocks = merge_fragmented_cues(
                            blocks, max_chars=self._merge_max_chars, max_gap_ms=self._merge_max_gap_ms)
                        self._log(f"Parçalı cue birleştirme: {_before} → {len(blocks)} blok", "ok")
                    except Exception as e:
                        self._log(f"Cue birleştirme hatası: {e}", "warn")

                if orig_cues:
                    _raw_map = _raw_src_map_from_cues(orig_cues)
                    blocks, _ = _fill_hata_with_source(blocks, _raw_map, log_fn=self._log)
                    blocks = _restore_tags_blocks(blocks, _raw_map)

                write_srt(fp, blocks)
                self._log(f"Kaydedildi: {fp}  ({len(blocks)} satır)", "ok")
                self._update_file_progress(fp,
                    f"Tamamlandı  {len(blocks)} satır", 100, "done")

            except Exception as e:
                self._log_exc(f"[{fname}] post-işlem hatası", e)
                self._update_file_progress(fp, "Hata", 0, "error")

        self._set_running(False)
        self._set_eta("")
        if not self._stop_flag:
            self._set_phase("Tamamlandı", f"{n} dosya post-işlendi")
            self._set_progress(100)
        else:
            self._set_phase("Hazır", "Durduruldu.")

    def _run_quality_check_inline(self, fp, orig_cues, blocks, mm_key, mm_url, mm_model, tgt, analysis_result=None):
        """QC kontrolü yap, dialog göster, onaylanan düzeltmeleri uygula. Güncel blocks döner.

        Uygulanan TÜM düzeltmeler (otomatik + dialogdan onaylı) <dosya>.qc_degisiklikler.txt'e
        öncesi/sonrasıyla yazılır. Neden: log sadece "X/Y satır yeniden çevrildi" özeti
        veriyor, hangi satırın neye dönüştüğünü göstermiyor — üstelik gerçekten uygulanan
        metin dialogdaki "Öneri" ile AYNI OLMAYABİLİR: onaylanan her satır qc_auto_fix
        içinde kaynak+hata+öneri eşliğinde YENİDEN çevriliyor, öneri sadece bir ipucu;
        yalnızca o yeniden-çeviri başarısız/güvenlik-filtresinden dönerse öneri metni
        aynen uygulanıyor. Kullanıcı gerçek sonucu görmeden onaylamış oluyordu."""
        import hybrid_translate as ht
        try:
            issues = ht.quality_check_with_helper(
                cues=orig_cues,
                tr_blocks=blocks,
                helper_api_key=mm_key,
                helper_url=mm_url,
                helper_model=mm_model,
                tgt_lang=tgt,
                log_fn=self._log,
                analysis_result=analysis_result,
            )
        except Exception as e:
            self._log_exc("QC hatası", e)
            return blocks

        if not issues:
            self._log("QC: sorun bulunamadı ✓", "ok")
            return blocks

        applied_records = []  # [{id, source, before, after, problem}]

        def _record(applied_issues, before_map, after_blocks):
            after_map = {str(b[0]): b[2] for b in after_blocks}
            for iss in applied_issues:
                iid = str(iss.get("id", ""))
                before = before_map.get(iid, iss.get("current", ""))
                after = after_map.get(iid, before)
                if after != before:
                    applied_records.append({
                        "id": iid, "source": iss.get("original", ""),
                        "before": before, "after": after,
                        "problem": iss.get("problem", ""),
                    })

        auto_issues, review_issues = ht.split_qc_issues_for_review(issues)
        if auto_issues:
            self._log(f"QC auto: {len(auto_issues)} düşük/orta severity düzeltme uygulanıyor", "info")
            before_map = {str(b[0]): b[2] for b in blocks}
            blocks = ht.qc_auto_fix(
                issues=auto_issues,
                tr_blocks=blocks,
                helper_api_key=self._helper_api_key("qc"),
                model=self._helper_api_model("qc"),
                tgt_lang=tgt,
                base_url=self._helper_api_base_url("qc"),
                log_fn=self._log,
            )
            _record(auto_issues, before_map, blocks)

        if not review_issues:
            self._write_qc_change_report(fp, applied_records)
            return blocks

        self._log(f"QC: {len(review_issues)} sorun insan onayı bekliyor — dialog açılıyor...", "warn")
        qc_event       = threading.Event()
        approved_fixes = []
        _post_ui(self, self._show_qc_dialog, review_issues, approved_fixes, qc_event)
        status = self._wait_for_dialog_event(qc_event, timeout=300)
        if status == "stopped":
            self._write_qc_change_report(fp, applied_records)
            return blocks
        if status == "timeout":
            self._set_status("QC: süre aşımı")

        if approved_fixes and status == "completed":
            before_map = {str(b[0]): b[2] for b in blocks}
            blocks = ht.qc_auto_fix(
                issues=approved_fixes,
                tr_blocks=blocks,
                helper_api_key=self._helper_api_key("qc"),
                model=self._helper_api_model("qc"),
                tgt_lang=tgt,
                base_url=self._helper_api_base_url("qc"),
                log_fn=self._log,
            )
            _record(approved_fixes, before_map, blocks)

        self._write_qc_change_report(fp, applied_records)
        return blocks

    def _write_qc_change_report(self, fp, applied_records: list):
        """QC tarafından fiilen değiştirilen satırları TEK bir txt dosyasına
        (kaynak/öncesi/sonrası) yazar — kullanıcı bunu paylaşıp kontrol ettirebilsin
        diye. Değişen satır yoksa dosya hiç yazılmaz (eski bir rapor varsa da
        silinmez — çağıran her zaman yeni bir liste ile çağırır)."""
        if not applied_records:
            return
        try:
            report_path = Path(fp).with_name(Path(fp).stem + ".qc_degisiklikler.txt")
            lines = [f"QC Değişiklikleri — {Path(fp).name}", f"Toplam: {len(applied_records)} satır", "=" * 60, ""]
            for rec in applied_records:
                lines.append(f"#{rec['id']}  [{rec['problem']}]")
                if rec["source"]:
                    lines.append(f"Kaynak : {rec['source']}")
                lines.append(f"Önce   : {rec['before']}")
                lines.append(f"Sonra  : {rec['after']}")
                lines.append("")
            report_path.write_text("\n".join(lines), encoding="utf-8")
            self._log(f"QC değişiklik raporu: {report_path.name}  ({len(applied_records)} satır)", "ok")
        except Exception as e:
            self._log_exc("QC değişiklik raporu yazılamadı", e)

    def _write_critic_change_report(self, fp, applied_records: list):
        """Critic Pass tarafından fiilen değiştirilen satırları TEK bir txt
        dosyasına (kaynak/öncesi/sonrası/sebep) yazar — QC değişiklik raporuyla
        aynı motivasyon (bkz. _write_qc_change_report yukarıda): Critic 150-200
        satır değiştirebiliyor ama hangi satırın NEDEN değiştiğini kimse
        göremiyordu."""
        if not applied_records:
            return
        try:
            report_path = Path(fp).with_name(Path(fp).stem + ".critic_degisiklikler.txt")
            report_path.parent.mkdir(parents=True, exist_ok=True)
            lines = [f"Critic Değişiklikleri — {Path(fp).name}", f"Toplam: {len(applied_records)} satır", "=" * 60, ""]
            for rec in applied_records:
                lines.append(f"#{rec['id']}  [{rec.get('reason', '')}]")
                if rec.get("source"):
                    lines.append(f"Kaynak : {rec['source']}")
                lines.append(f"Önce   : {rec['before']}")
                lines.append(f"Sonra  : {rec['after']}")
                lines.append("")
            report_path.write_text("\n".join(lines), encoding="utf-8")
            self._log(f"Critic değişiklik raporu: {report_path.name}  ({len(applied_records)} satır)", "ok")
        except Exception as e:
            self._log_exc("Critic değişiklik raporu yazılamadı", e)

    def _dismiss_modal_dialog(self, target_dlg=None, target_event=None):
        """Worker timeout/stop durumunda hâlâ açık olan modal inceleme dialog'unu (QC/Glossary) kapatır.
        Hedef dialog/event aktif modal ile eşleşmiyorsa no-op. Ana thread'de çağrılır."""
        dlg = getattr(self, "_active_modal_dlg", None)
        active_event = getattr(self, "_active_modal_event", None)
        if target_dlg is not None and dlg is not target_dlg:
            return
        if target_event is not None and active_event is not target_event:
            return
        self._active_modal_dlg = None
        self._active_modal_event = None
        try:
            if dlg is not None and dlg.winfo_exists():
                dlg.destroy()
        except Exception:
            pass

    def _wait_for_dialog_event(self, event: threading.Event, timeout: float = 300.0, poll_interval: float = 0.5) -> str:
        """Modal inceleme dialog event'ini self._stop_flag kontrolü ile güvenli şekilde bekler.

        Returns:
            "completed": Kullanıcı dialogu onayladı/kapattı (event set edildi).
            "stopped":   Kullanıcı 'Durdur' düğmesine bastı (self._stop_flag True oldu).
            "timeout":   Belirtilen süre (timeout) doldu.
        """
        start = time.monotonic()
        while not event.is_set():
            if getattr(self, "_stop_flag", False):
                event._dialog_cancelled = True
                _post_ui(self, self._dismiss_modal_dialog, target_event=event)
                return "stopped"
            if time.monotonic() - start >= timeout:
                event._dialog_cancelled = True
                _post_ui(self, self._dismiss_modal_dialog, target_event=event)
                return "timeout"
            event.wait(timeout=poll_interval)
        return "completed"

    # ── QC Dialog ────────────────────────────────────────────────────────────
    def _show_qc_dialog(self, issues: list, result_holder: list, done_event: threading.Event):
        """Show QC review dialog. Must be called on main thread."""
        if getattr(done_event, "_dialog_cancelled", False):
            return
        if not issues:
            done_event.set()
            return
        try:
            self._build_qc_dialog(issues, result_holder, done_event)
        except Exception as e:
            # Dialog kurulamazsa worker'ı 5 dk (qc_event.wait timeout) bekletme —
            # event'i hemen set et, fix uygulanmadan devam etsin
            self._log_exc("QC dialog açılamadı", e)
            done_event.set()

    def _build_qc_dialog(self, issues: list, result_holder: list, done_event: threading.Event):
        dlg = ctk.CTkToplevel(self)
        dlg.title(f"Kalite Kontrolü — {len(issues)} sorun bulundu")
        dlg.geometry("880x580")
        dlg.grab_set()
        dlg.configure(fg_color=BG)
        dlg.lift()
        dlg.focus_force()
        self._active_modal_dlg = dlg   # worker timeout'unda kapatabilmek için referans tut
        self._active_modal_event = done_event

        ctk.CTkLabel(dlg,
                     text=f"{len(issues)} potansiyel çeviri sorunu tespit edildi. "
                          f"Onayladıklarınız uygulanır:",
                     font=ctk.CTkFont("Segoe UI", 12), text_color=YELLOW,
                     wraplength=820).pack(padx=16, pady=(14,4))

        sf = ctk.CTkScrollableFrame(dlg, fg_color=PANEL, corner_radius=8)
        sf.pack(fill="both", expand=True, padx=12, pady=8)

        check_vars = []
        for issue in issues:
            row_fr = ctk.CTkFrame(sf, fg_color=CARD, corner_radius=8)
            row_fr.pack(fill="x", padx=4, pady=(0,6))
            info_fr = ctk.CTkFrame(row_fr, fg_color="transparent")
            info_fr.pack(fill="x", padx=10, pady=8)

            var = ctk.BooleanVar(value=True)
            check_vars.append(var)

            header_txt = f"#{issue.get('id','?')}  {issue.get('problem','')}"
            ctk.CTkCheckBox(info_fr, text=header_txt, variable=var,
                            fg_color=ACCENT, hover_color="#5a4fd1",
                            font=ctk.CTkFont("Segoe UI", 12, "bold"),
                            text_color=FG).pack(anchor="w")
            ctk.CTkLabel(info_fr,
                         text=f"Mevcut:  {issue.get('current', '')}",
                         font=ctk.CTkFont("Segoe UI", 11), text_color=FG2,
                         wraplength=800, justify="left").pack(anchor="w", pady=(3,0))
            ctk.CTkLabel(info_fr,
                         text=f"Öneri:    {issue.get('suggestion', '')}",
                         font=ctk.CTkFont("Segoe UI", 11), text_color=GREEN,
                         wraplength=800, justify="left").pack(anchor="w", pady=(2,0))

        btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_fr.pack(fill="x", padx=12, pady=(0,14))
        btn_fr.grid_columnconfigure((0,1,2), weight=1)

        def select_all():
            for v in check_vars:
                v.set(True)

        def apply_fixes():
            for i, v in enumerate(check_vars):
                if v.get():
                    result_holder.append(issues[i])
            self._active_modal_dlg = None
            self._active_modal_event = None
            dlg.destroy()
            done_event.set()

        def cancel():
            self._active_modal_dlg = None
            self._active_modal_event = None
            dlg.destroy()
            done_event.set()

        ctk.CTkButton(btn_fr, text="Tümünü Seç",
                      fg_color=BORDER, hover_color=ACCENT,
                      command=select_all).grid(row=0, column=0, padx=4, sticky="ew")
        ctk.CTkButton(btn_fr, text="✓ Uygula",
                      fg_color=ACCENT, hover_color="#5a4fd1",
                      command=apply_fixes).grid(row=0, column=1, padx=4, sticky="ew")
        ctk.CTkButton(btn_fr, text="Atla",
                      fg_color=CARD, hover_color=BORDER,
                      command=cancel).grid(row=0, column=2, padx=4, sticky="ew")

        dlg.protocol("WM_DELETE_WINDOW", cancel)

    # ── Auto-Glossary ─────────────────────────────────────────────────────────
    def _run_auto_glossary(self, cues: list, tr_blocks: list, filepath: str):
        """Build glossary suggestions from a completed translation and show review dialog."""
        import hybrid_translate as ht
        mm_key = self._helper_api_key("analysis")
        mm_url = self._helper_api_base_url("analysis")
        mm_mdl = self._helper_api_model("analysis")
        src    = self.src_var.get()
        tgt    = self.tgt_var.get()

        if not mm_key:
            self._log("Auto-Glossary: OpenAI API anahtarı gerekli", "warn")
            return

        glossary_path = self.glossary_var.get().strip()
        existing = ht.load_glossary(glossary_path) if glossary_path else {}

        self._log(f"Auto-Glossary: {Path(filepath).name} analiz ediliyor...", "info")
        suggestions = ht.build_glossary_suggestions(
            cues=cues,
            tr_blocks=tr_blocks,
            src_lang=src,
            tgt_lang=tgt,
            helper_api_key=mm_key,
            helper_url=mm_url,
            helper_model=mm_mdl,
            existing_glossary=existing,
            log_fn=self._log,
        )

        if not suggestions:
            self._log("Auto-Glossary: yeni terim önerisi yok", "ok")
            return

        done_event    = threading.Event()
        approved_list = []
        _post_ui(self, self._show_glossary_dialog, suggestions, approved_list, done_event, glossary_path)
        status = self._wait_for_dialog_event(done_event, timeout=300)

        if status == "completed" and approved_list and glossary_path:
            try:
                with open(glossary_path, "a", encoding="utf-8") as f:
                    f.write(f"\n# Auto-Glossary — {Path(filepath).name}\n")
                    for item in approved_list:
                        f.write(f"{item['src']} = {item['tgt']}\n")
                self._log(f"Auto-Glossary: {len(approved_list)} terim sözlüğe eklendi", "ok")
            except Exception as e:
                self._log(f"Auto-Glossary yazma hatası: {e}", "err")

    def _show_glossary_dialog(self, suggestions: list, result_holder: list,
                               done_event: threading.Event, glossary_path: str):
        """Show glossary suggestion review dialog. Must be called on main thread."""
        if getattr(done_event, "_dialog_cancelled", False):
            return
        if not suggestions:
            done_event.set()
            return

        _CATEGORY_COLORS = {
            "proper_noun": "#7B68EE",
            "technical":   "#2ECC71",
            "idiom":       "#F39C12",
            "recurring":   "#3498DB",
        }

        dlg = ctk.CTkToplevel(self)
        dlg.title(f"Auto-Glossary — {len(suggestions)} yeni terim önerisi")
        dlg.geometry("900x600")
        dlg.grab_set()
        dlg.configure(fg_color=BG)
        dlg.lift()
        dlg.focus_force()
        self._active_modal_dlg = dlg   # worker timeout'unda kapatabilmek için referans tut
        self._active_modal_event = done_event

        dest_label = Path(glossary_path).name if glossary_path else "sözlük seçilmedi"
        ctk.CTkLabel(dlg,
                     text=f"Çeviriden tespit edilen {len(suggestions)} terim. "
                          f"Onayladıklarınız '{dest_label}' dosyasına eklenir:",
                     font=ctk.CTkFont("Segoe UI", 12), text_color=YELLOW,
                     wraplength=840).pack(padx=16, pady=(14, 4))

        sf = ctk.CTkScrollableFrame(dlg, fg_color=PANEL, corner_radius=8)
        sf.pack(fill="both", expand=True, padx=12, pady=8)

        check_vars = []
        for sg in suggestions:
            row_fr = ctk.CTkFrame(sf, fg_color=CARD, corner_radius=8)
            row_fr.pack(fill="x", padx=4, pady=(0, 5))
            inner  = ctk.CTkFrame(row_fr, fg_color="transparent")
            inner.pack(fill="x", padx=10, pady=7)

            var = ctk.BooleanVar(value=True)
            check_vars.append(var)

            cat   = sg.get("category", "")
            color = _CATEGORY_COLORS.get(cat, FG2)
            ctk.CTkCheckBox(inner,
                            text=f"{sg.get('src','')}  →  {sg.get('tgt','')}",
                            variable=var,
                            fg_color=ACCENT, hover_color="#5a4fd1",
                            font=ctk.CTkFont("Segoe UI", 12, "bold"),
                            text_color=FG).pack(anchor="w")
            meta = f"[{cat}]  {sg.get('reason','')}"
            ctk.CTkLabel(inner, text=meta,
                         font=ctk.CTkFont("Segoe UI", 10), text_color=color,
                         wraplength=820, justify="left").pack(anchor="w", pady=(2, 0))

        btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_fr.pack(fill="x", padx=12, pady=(0, 14))
        btn_fr.grid_columnconfigure((0, 1, 2), weight=1)

        def select_all():
            for v in check_vars:
                v.set(True)

        def add_selected():
            for i, v in enumerate(check_vars):
                if v.get():
                    result_holder.append(suggestions[i])
            self._active_modal_dlg = None
            self._active_modal_event = None
            dlg.destroy()
            done_event.set()

        def cancel():
            self._active_modal_dlg = None
            self._active_modal_event = None
            dlg.destroy()
            done_event.set()

        ctk.CTkButton(btn_fr, text="Tümünü Seç",
                      fg_color=BORDER, hover_color=ACCENT,
                      command=select_all).grid(row=0, column=0, padx=4, sticky="ew")
        ctk.CTkButton(btn_fr, text="✓ Sözlüğe Ekle",
                      fg_color=ACCENT, hover_color="#5a4fd1",
                      command=add_selected).grid(row=0, column=1, padx=4, sticky="ew")
        ctk.CTkButton(btn_fr, text="Atla",
                      fg_color=CARD, hover_color=BORDER,
                      command=cancel).grid(row=0, column=2, padx=4, sticky="ew")

        dlg.protocol("WM_DELETE_WINDOW", cancel)

    # ── Senkron mod ───────────────────────────────────────────────────────────
    def _save_quality_report(self, rows: list, output_dir: str):
        """Kalite raporunu çıktı klasörüne ceviri_raporu.txt olarak yazar."""
        if not rows:
            return None
        try:
            with self._token_lock:
                tok = self._token_total
            txt = build_quality_report_text(rows, self._main_model_name(),
                                            self.tgt_var.get(),
                                            self.mode_var.get(), tok)
            # Rapor, çıktı .srt'lerle aynı 'efektif tabana' gider (Kural 1: <girdi>/ÇIKTI,
            # Kural 2: çıktı kökü) — bkz. plans/output-folder-rules-brief.md.
            rep_dir = _resolve_report_dir(self.input_var.get(), output_dir)
            rep_dir.mkdir(parents=True, exist_ok=True)
            p = rep_dir / "ceviri_raporu.txt"
            p.write_text(txt, encoding="utf-8")
            self._log(f"Kalite raporu: {p}", "ok")
            return p
        except Exception:
            return None

    def _open_quality_report(self):
        """Çıktı klasöründeki ceviri_raporu.txt'yi uygulama içi pencerede gösterir."""
        p = _resolve_report_dir(self.input_var.get(), self.output_var.get()) / "ceviri_raporu.txt"
        if not p.exists():
            messagebox.showinfo("Kalite Raporu",
                                "Henüz rapor yok.\nBir çeviri tamamlandığında çıktı "
                                "klasörüne 'ceviri_raporu.txt' yazılır.")
            return
        try:
            self._show_report_dialog(p.read_text(encoding="utf-8"), str(p))
        except Exception as e:
            messagebox.showerror("Hata", f"Rapor açılamadı:\n{e}")

    def _show_report_dialog(self, text: str, path: str):
        dlg = ctk.CTkToplevel(self)
        dlg.title("📊  Kalite Raporu")
        dlg.geometry("680x600")
        dlg.configure(fg_color=BG)
        dlg.lift(); dlg.focus_force()
        box = ctk.CTkTextbox(dlg, font=ctk.CTkFont("Consolas", 12),
                             fg_color=PANEL, text_color=FG, wrap="none")
        box.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        box.insert("1.0", text)
        box.configure(state="disabled")
        btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_fr.pack(fill="x", padx=12, pady=(0, 12))
        btn_fr.grid_columnconfigure((0, 1), weight=1)
        def _open_folder():
            import subprocess
            try:
                subprocess.Popen(["explorer", "/select,", str(Path(path))])
            except Exception:
                pass
        ctk.CTkButton(btn_fr, text="📂  Klasörde Göster", fg_color=CARD,
                      hover_color=BORDER, command=_open_folder).grid(
                      row=0, column=0, padx=4, sticky="ew")
        ctk.CTkButton(btn_fr, text="✕  Kapat", fg_color=CARD,
                      hover_color=BORDER, command=dlg.destroy).grid(
                      row=0, column=1, padx=4, sticky="ew")

    def _detect_content_types_parallel(self, client, files, model) -> dict:
        """'Otomatik' şemalı dosyaların içerik türünü paralel tespit eder.
        Dönen: {filepath: tespit edilen şema adı}."""
        results = {}
        if not files:
            return results
        def _one(fp):
            try:
                cues = self._cached_blocks_for(fp) or list(parse_subtitle(fp))
                return fp, detect_content_type_with_ai(client, cues, model, self._log, token_callback=self._update_tokens, filename=fp)
            except Exception as e:
                self._log(f"[{Path(fp).name}] Tür tespiti hatası: {e}", "warn")
                return fp, "Otomatik"
        with ThreadPoolExecutor(max_workers=min(4, len(files))) as ex:
            for fp, sname in ex.map(_one, files):
                results[fp] = sname
        return results

    def _auto_content_type_files(self, files: list) -> list:
        return [
            fp for fp in files
            if normalize_schema_name(self._get_file_schema(fp).get("name")) == "Otomatik"
        ]

    def _apply_detected_content_types(self, detected: dict):
        if not detected:
            return
        schema_names = [v["name"] for v in CONTENT_SCHEMAS.values()]
        for fp, raw_name in detected.items():
            name = normalize_schema_name(raw_name)
            if name not in schema_names:
                name = "Otomatik"
            var = self._file_schema_vars.get(fp)
            if var is None:
                var = ctk.StringVar(value=name)
                self._file_schema_vars[fp] = var
            else:
                var.set(name)
        resolved = {normalize_schema_name(v) for v in detected.values()}
        if len(resolved) == 1:
            only = next(iter(resolved))
            if only != "Otomatik":
                self.content_type_var.set(only)

    def _show_content_type_confirm_dialog(self, detected: dict) -> bool:
        """Show detected content types before translation. Returns True to continue."""
        schema_names = [v["name"] for v in CONTENT_SCHEMAS.values()]
        files = list(detected.keys())
        if not files:
            return True

        result = {"action": "cancel"}
        dlg = ctk.CTkToplevel(self)
        dlg.title("İçerik Türü Ön Analizi")
        dlg.geometry("760x520")
        dlg.configure(fg_color=BG)
        dlg.grab_set()
        dlg.lift()
        dlg.focus_force()
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(2, weight=1)

        hdr = ctk.CTkFrame(dlg, fg_color=ACCENT, corner_radius=10, height=52)
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        hdr.grid_propagate(False)
        ctk.CTkLabel(
            hdr,
            text=f"İçerik türü ön analizi tamamlandı ({CONTENT_TYPE_DETECT_MODEL})",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color="white",
        ).pack(side="left", padx=14, pady=14)

        ctk.CTkLabel(
            dlg,
            text="Seçilen türler doğruysa devam et. Gerekirse her dosyanın türünü burada değiştirebilirsin.",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=FG2,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 6))

        scroll = ctk.CTkScrollableFrame(
            dlg,
            fg_color="transparent",
            scrollbar_button_color=BORDER,
            height=330,
        )
        scroll.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 8))
        scroll.grid_columnconfigure(0, weight=1)
        row_vars = {}
        for i, fp in enumerate(files):
            row = ctk.CTkFrame(scroll, fg_color=CARD, corner_radius=7)
            row.grid(row=i, column=0, sticky="ew", padx=4, pady=3)
            row.grid_columnconfigure(0, weight=1)
            name = Path(fp).name
            ctk.CTkLabel(
                row,
                text=name if len(name) <= 70 else "..." + name[-67:],
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=FG,
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=(10, 8), pady=6)
            value = normalize_schema_name(detected.get(fp, "Otomatik"))
            if value not in schema_names:
                value = "Otomatik"
            var = ctk.StringVar(value=value)
            row_vars[fp] = var
            ctk.CTkOptionMenu(
                row,
                variable=var,
                values=schema_names,
                width=220,
                height=30,
                font=ctk.CTkFont("Segoe UI", 10),
                fg_color=BORDER,
                button_color=BORDER,
                button_hover_color=ACCENT,
                dropdown_fg_color=CARD,
                text_color=FG,
            ).grid(row=0, column=1, sticky="e", padx=(4, 10), pady=5)

        btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_fr.grid(row=3, column=0, sticky="ew", padx=12, pady=(4, 12))
        btn_fr.grid_columnconfigure((0, 1, 2), weight=1)

        def _collect():
            return {fp: normalize_schema_name(var.get()) for fp, var in row_vars.items()}

        def _continue():
            detected.clear()
            detected.update(_collect())
            result["action"] = "continue"
            dlg.destroy()

        def _edit_main():
            detected.clear()
            detected.update(_collect())
            result["action"] = "edit"
            dlg.destroy()

        def _cancel():
            result["action"] = "cancel"
            dlg.destroy()

        ctk.CTkButton(
            btn_fr,
            text="Bu Türlerle Devam Et",
            height=36,
            fg_color=GREEN,
            hover_color="#27AE60",
            text_color="white",
            command=_continue,
        ).grid(row=0, column=0, padx=4, sticky="ew")
        ctk.CTkButton(
            btn_fr,
            text="Ana Ekranda Düzenle",
            height=36,
            fg_color=CARD,
            hover_color=BORDER,
            command=_edit_main,
        ).grid(row=0, column=1, padx=4, sticky="ew")
        ctk.CTkButton(
            btn_fr,
            text="İptal",
            height=36,
            fg_color=CARD,
            hover_color=BORDER,
            command=_cancel,
        ).grid(row=0, column=2, padx=4, sticky="ew")
        dlg.protocol("WM_DELETE_WINDOW", _cancel)
        self.wait_window(dlg)
        self._apply_detected_content_types(detected)
        return result["action"] == "continue"

    def _start_content_type_preflight(self, api_key: str, files: list) -> bool:
        auto_files = self._auto_content_type_files(files)
        if not auto_files:
            return False

        self._set_running(True)
        self._set_phase("İçerik Türü", f"{len(auto_files)} dosya ön analiz ediliyor")
        detect_model = self._main_model_name() if self._main_custom_active() else CONTENT_TYPE_DETECT_MODEL
        self._set_status(f"İçerik türü ön analizi: {detect_model}")
        self._log(
            f"{len(auto_files)} dosya çeviri başlamadan önce içerik türü için analiz ediliyor "
            f"({detect_model})...",
            "info",
        )

        def _worker():
            try:
                b_url = self._main_api_base_url()
                client = OpenAI(api_key=api_key, base_url=b_url if b_url else None)
                detected = self._detect_content_types_parallel(
                    client,
                    auto_files,
                    detect_model,
                )
            except Exception as e:
                self._log(f"İçerik türü ön analizi başarısız: {e}", "warn")
                detected = {fp: "Otomatik" for fp in auto_files}

            def _finish():
                should_continue = self._show_content_type_confirm_dialog(detected)
                if should_continue:
                    self._content_type_preflight_done = True
                    self._set_running(False)
                    self.after(20, self._start)
                else:
                    self._content_type_preflight_done = False
                    self._set_running(False)
                    self._set_status("İçerik türü seçimi bekleniyor.")
                    self._log("İçerik türü ön analizi uygulandı; çeviri başlatılmadı.", "info")

            _post_ui(self, _finish)

        threading.Thread(target=_worker, daemon=True).start()
        return True

    def _get_precontext_hints(self, client, files, src, tgt, model) -> dict:
        """Hybrid (Yardımcı Analiz) kapalıyken dosya başına ön-bağlam hint'i üretir.
        Sonuçlar .context_cache/ altında önbelleklenir; önbellekte olmayan dosyalar
        paralel analiz edilir (4 worker)."""
        hints = {}
        if not self.precontext_var.get() or self.hybrid_var.get():
            return hints

        # 1) Önbellekten çöz, eksikleri topla
        data_by_fp, to_analyze = {}, []
        for fp in files:
            data  = None
            cpath = _precontext_cache_path(fp)
            try:
                if cpath.exists():
                    cached = json.loads(cpath.read_text(encoding="utf-8"))
                    if (cached.get("_ver") == PRECONTEXT_CACHE_VER
                            and cached.get("_tgt") == tgt
                            and cached.get("_sig", "") == _precontext_cache_sig(fp)):
                        data = cached.get("data")
            except Exception:
                data = None
            if data is not None:
                data_by_fp[fp] = data
            else:
                to_analyze.append(fp)

        # 2) Eksikleri paralel analiz et
        if to_analyze and not self._stop_flag:
            self._log(f"Ön-bağlam analizi: {len(to_analyze)} dosya "
                      f"(x{min(4, len(to_analyze))} paralel)...", "info")
            def _one(fp):
                if self._stop_flag:
                    return fp, None
                try:
                    blocks = self._cached_blocks_for(fp) or list(parse_subtitle(fp))
                    return fp, analyze_file_precontext(client, blocks, model, src, tgt,
                                                       log_fn=self._log,
                                                       token_cb=self._update_tokens)
                except Exception as e:
                    # Tek dosya parse/analiz hatası tüm koşuyu çökertmemeli
                    # (ex.map hatayı ana thread'e yeniden fırlatırdı → UI 'çalışıyor'da kalırdı)
                    self._log(f"[{Path(fp).name}] Ön-bağlam atlandı: {e}", "warn")
                    return fp, None
            with ThreadPoolExecutor(max_workers=min(4, len(to_analyze))) as ex:
                for fp, data in ex.map(_one, to_analyze):
                    if data is None:
                        continue
                    data_by_fp[fp] = data
                    try:
                        cpath = _precontext_cache_path(fp)
                        cpath.parent.mkdir(parents=True, exist_ok=True)
                        cpath.write_text(json.dumps(
                            {"_ver": PRECONTEXT_CACHE_VER, "_tgt": tgt, "data": data,
                             "_sig": _precontext_cache_sig(fp)},
                            ensure_ascii=False), encoding="utf-8")
                    except Exception as e:
                        # Önceden sessizce yutuluyordu (except: pass) — disk/izin hatası
                        # hiç görünmüyordu; artık en azından uyarı olarak loglanıyor
                        # (bkz. Adım 5, plans/sozluk-hedef-dil-guard-brief.md).
                        self._log(f"[{Path(fp).name}] Ön-bağlam önbelleği yazılamadı: {e}", "warn")

        # 3) Hint metinlerini üret (sıra önemsiz)
        for fp, data in data_by_fp.items():
            hint = build_precontext_hint(data, target_language=tgt)
            if hint:
                hints[fp] = hint
                n_char = len(data.get("characters") or [])
                n_term = len(data.get("terms") or {})
                self._log(f"[{Path(fp).name}] Ön-bağlam hazır — "
                          f"{n_char} karakter, {n_term} sabit terim", "ok")
                if n_term:
                    self._log(f"[{Path(fp).name}] Sabit terimler: {data.get('terms')}", "info")
        # Dizi hafızasını BÖLÜM SIRASINDA işle ('files' zaten _get_srt_files'ta
        # bölüme göre sıralı) — yoksa önbellekli E02 taze E01'den önce işlenip
        # "ilk karar kanon" kuralını bozardı
        for fp in files:
            data = data_by_fp.get(fp)
            if data is not None:
                self._update_series_memory_from_precontext(fp, data, target_language=tgt)
        return hints

    def _update_series_memory_from_precontext(self, fp: str, data: dict, target_language: str = "tr"):
        sm_obj, season, ep = self._series_mem_for(fp)
        if sm_obj is None or not isinstance(data, dict):
            return
        try:
            import hybrid_translate as ht
            safe_terms = ht.sanitize_glossary_for_turkish(
                data.get("terms") or {}, target_language=target_language, log_fn=self._log
            )
            sm_obj.merge_terms(safe_terms)
            sm_obj.merge_characters(data.get("characters") or [])
            sm_obj.merge_address_map(data.get("address_map") or [])
            sm_obj.mark_episode(season, ep)
            sm_obj.save()
        except Exception:
            pass

    def _update_series_memory_from_analysis(self, fp: str, context, pronoun_map):
        """Hybrid (Yardımcı Analiz) çıktısını dizi hafızasına işler (ilk karar kanon)."""
        sm_obj, season, ep = self._series_mem_for(fp)
        if sm_obj is None:
            return
        try:
            import hybrid_translate as ht
            sm_obj.merge_terms(ht.sanitize_glossary_for_turkish(
                dict(getattr(context, "recurring_terms", {}) or {}),
                target_language=self.tgt_var.get(),
            ))
            sm_obj.merge_characters(list(getattr(context, "characters", []) or []))
            if pronoun_map:
                sm_obj.merge_address_map(pronoun_map)
            sm_obj.mark_episode(season, ep)
            sm_obj.save()
        except Exception:
            pass

    # ── Sync mod çökme kurtarma (per-chunk checkpoint) ────────────────────────
    # Sync mod yarıda çökerse/durdurulursa, tamamlanan chunk'lar bu dosyaya yazılır;
    # aynı işi tekrar başlatınca o chunk'lar API'ye GÖNDERİLMEZ (token/para tasarrufu).
    # JSONL append (O(1)/chunk). Başarılı tam koşudan sonra silinir.
    def _sync_ckpt_path(self) -> Path:
        return state_path(__file__, ".sync_checkpoint.jsonl")

    def _ckpt_fingerprint(self) -> str:
        """Checkpoint imzasına giren ayar parmak izi. Model/hedef dil/üslup/küfür/tür
        değişince eski koşunun chunk'ları 'tamamlanmış' sayılmaz — aksi hâlde ayar
        değiştirip yeniden çeviren kullanıcıya bayat çeviri geri yazılır."""
        try:
            return "|".join([
                self._main_model_name(), self.tgt_var.get(), self.profanity_var.get(),
                self.style_var.get(), self.content_type_var.get(),
            ])
        except Exception:
            return ""

    @staticmethod
    def _chunk_src_hash(req, fingerprint: str = "", scope: str = "") -> str:
        """Chunk'ın çevrilecek KAYNAK satırları + ayar parmak izinin (fingerprint)
        imzası — kaynak içeriği YA DA model/ayarlar değişirse checkpoint eşleşmesin
        (bayat çeviri sunulmasın). 'tr' dışındaki alanlar (prev_tr enjeksiyonu vb.)
        imzayı değiştirmez."""
        try:
            pl = json.loads(req["body"]["messages"][1]["content"])
            srcs = "".join(str(it.get("t", "")) for it in pl.get("tr", []))
            scoped_fp = fingerprint
            if scope:
                scoped_fp += "\x1e" + str(scope)
            data = scoped_fp + "\x1f" + srcs
            return hashlib.md5(data.encode("utf-8", "replace")).hexdigest()[:10]
        except Exception:
            return ""

    def _load_sync_ckpt(self) -> dict:
        """{cid: (text, src_hash)} — bozuk/yarım satırlar atlanır."""
        d = {}
        p = self._sync_ckpt_path()
        if not p.exists():
            return d
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                    if o.get("cid"):
                        d[o["cid"]] = (o.get("t", ""), o.get("h", ""))
                except Exception:
                    continue
        except Exception:
            pass
        return d

    def _save_sync_ckpt_entry(self, cid, text, src_hash):
        with self._ckpt_lock:
            try:
                with open(self._sync_ckpt_path(), "a", encoding="utf-8") as f:
                    f.write(json.dumps({"cid": cid, "t": text, "h": src_hash},
                                       ensure_ascii=False) + "\n")
            except Exception:
                pass

    def _clear_sync_ckpt(self):
        try:
            self._sync_ckpt_path().unlink(missing_ok=True)
        except Exception:
            pass

    def _resume_from_sync_ckpt(self, api_requests, raw_map):
        """Checkpoint'teki (içerik imzası eşleşen) tamamlanmış chunk'ları raw_map'e koyar
        ve api_requests'ten çıkarır. Kalan api_requests'i döndürür."""
        ckpt = self._load_sync_ckpt()
        if not ckpt:
            return api_requests
        fp = self._ckpt_fingerprint()
        resumed, still = 0, []
        import hashlib
        for req in api_requests:
            cid = req["custom_id"]
            ent = ckpt.get(cid)
            # Yeni (ayarsız) hash veya eski (ayarlı) hash ile eşleşirse kabul et
            is_match = False
            if ent and ent[0]:
                h_new = self._chunk_src_hash(req, fp)
                if ent[1] == h_new:
                    is_match = True
                else:
                    try:
                        pl = json.loads(req["body"]["messages"][1]["content"])
                        srcs = " ".join(str(it.get("t", "")) for it in pl.get("tr", []))
                        h_old = hashlib.md5((fp + "\x1f" + srcs).encode("utf-8", "replace")).hexdigest()[:10]
                        if ent[1] == h_old:
                            is_match = True
                    except:
                        pass
            if is_match:
                raw_map[cid] = ent[0]
                resumed += 1
            else:
                still.append(req)
        if resumed:
            self._log(f"Çökme kurtarma: {resumed} tamamlanmış chunk önbellekten alındı — "
                      f"yeniden çevrilmeyecek (kalan {len(still)} istek API'ye)", "ok")
        return still

    def _prefill_sync_ckpt(self, reqs, raw_map, scope: str = "") -> int:
        """Checkpoint'teki (imzası eşleşen) tamamlanmış chunk'ları raw_map'e koyar; döngüler
        `cid in raw_map` ile atlar. (raw_map'i filtrelemez — chain prev_pairs için uygun.)"""
        ckpt = self._load_sync_ckpt()
        if not ckpt:
            return 0
        fp = self._ckpt_fingerprint()
        n = 0
        import hashlib
        for req in reqs:
            cid = req["custom_id"]
            ent = ckpt.get(cid)
            if ent and ent[0] and cid not in raw_map:
                h_new = self._chunk_src_hash(req, fp, scope)
                is_match = (ent[1] == h_new)
                if not is_match and not scope:
                    try:
                        pl = json.loads(req["body"]["messages"][1]["content"])
                        srcs = " ".join(str(it.get("t", "")) for it in pl.get("tr", []))
                        h_old = hashlib.md5((fp + "\x1f" + srcs).encode("utf-8", "replace")).hexdigest()[:10]
                        is_match = (ent[1] == h_old)
                    except:
                        pass
                if is_match:
                    raw_map[cid] = ent[0]
                    n += 1
        if n:
            self._log(f"Çökme kurtarma: {n} tamamlanmış chunk önbellekten alındı "
                      f"(yeniden çevrilmeyecek)", "ok")
        return n

    def _run_sync(self, api_key):
        import hybrid_translate as ht
        b_url = self._main_api_base_url()
        client = OpenAI(api_key=api_key, base_url=b_url if b_url else None)
        output_dir = self.output_var.get()
        src, tgt   = self.src_var.get(), self.tgt_var.get()
        model      = self._main_model_name()
        srt_files  = self._get_srt_files()

        if not srt_files:
            self._log("Giriş klasöründe .srt bulunamadı!", "err")
            self._set_running(False)
            return

        if self.hybrid_var.get():
            self._run_sync_hybrid(api_key, client, srt_files, src, tgt, model, output_dir)
            return

        # Parse her dosyayı bir kez yap — boş-filtre için cache'le
        self._block_cache: dict = {}
        valid_files = []
        for fp in srt_files:
            if self._is_queued_file_removed(fp):
                continue
            blocks = list(parse_subtitle(fp))
            if not blocks:
                self._log(f"{Path(fp).name}: geçerli altyazı bloğu yok, atlandı", "warn")
            else:
                self._block_cache[fp] = blocks
                valid_files.append(fp)
        if not valid_files:
            self._log("Geçerli altyazı dosyası yok!", "err")
            self._set_running(False)
            return

        _profanity = self.profanity_var.get()
        # Load global glossary once (schema-based glossary lookup uses first file as proxy)
        _global_glossary = ht.load_glossary(self._get_file_glossary(valid_files[0])) if valid_files else {}
        if _global_glossary:
            self._log(f"Glossary: {len(_global_glossary)} terim yüklendi", "info")
        _auto_files = [fp for fp in valid_files
                       if self._get_file_schema(fp)["name"] == "Otomatik"]
        if _auto_files:
            self._log(f"{len(_auto_files)} dosyanın içerik türü paralel analiz ediliyor...", "info")
        _detected = self._detect_content_types_parallel(client, _auto_files, model)
        _schema_groups: dict = {}
        for fp in valid_files:
            sname = self._get_file_schema(fp)["name"]
            if sname == "Otomatik":
                sname = _detected.get(fp, "Otomatik")
            _schema_groups.setdefault(sname, []).append(fp)
        # Ön-bağlam analizi (özet, karakterler, sen/siz haritası, sabit terimler)
        _file_hints = self._get_precontext_hints(client, valid_files, src, tgt, model)
        # Dizi hafızası: önceki bölümlerin terim/karakter/sen-siz kararlarını ekle
        _sm_used = 0
        for fp in valid_files:
            _sm_hint = self._series_hint_for(fp)
            if _sm_hint:
                _file_hints[fp] = _file_hints.get(fp, "") + _sm_hint
                _sm_used += 1
        if _sm_used:
            self._log(f"Dizi hafızası: {_sm_used} dosyaya önceki bölüm kararları eklendi", "info")
        all_requests, all_file_map = [], {}
        for sname, group in _schema_groups.items():
            reqs, fmap = build_requests(group, src, tgt, model,
                                        chunk_size=self._chunk_size,
                                        schema=self._schema_by_name(sname),
                                        profanity=_profanity,
                                        glossary=_global_glossary,
                                        project_memory=self._pm,
                                        file_hints=_file_hints,
                                        block_cache=self._block_cache,
                                        context_lines=self._context_lines,
                                        lookahead_lines=self._lookahead_lines,
                                        scene_gap_sec=self._scene_gap_seconds,
                                        temperature=self._temperature)
            all_requests.extend(reqs)
            all_file_map.update(fmap)
        requests, file_map = all_requests, all_file_map
        # ── TM ön taraması: tüm blokları tam eşleşen chunk'ları API'ye gönderme ──
        # Tüm chunk kaynaklarını TEK toplu sorguda çöz (satır-satır yerine)
        _all_srcs = []
        for req in requests:
            try:
                _pl = json.loads(req["body"]["messages"][1]["content"])
                _all_srcs.extend(it["t"] for it in _pl.get("tr", []) if "t" in it)
            except Exception:
                pass
        _tm_cache = self._tm.lookup_batch(_all_srcs, tgt_lang=tgt,
                                           model=self._main_model_name(),
                                           profanity=self.profanity_var.get()) if _all_srcs else {}

        def _tm_fill_chunk(req: dict) -> str | None:
            """Chunk'taki tüm bloklar TM'de tam eşleşiyorsa JSON cevabı döner, yoksa None."""
            try:
                payload = json.loads(req["body"]["messages"][1]["content"])
                items   = payload.get("tr", [])
                if not items:
                    return None
                results = []
                for item in items:
                    cached = _tm_cache.get(item["t"])
                    if cached is None:
                        fuzzy = self._tm.fuzzy_lookup(item["t"], threshold=0.95, tgt_lang=tgt,
                                                      model=self._main_model_name(),
                                                      profanity=self.profanity_var.get())
                        cached = fuzzy[0] if fuzzy else None
                    if cached is None:
                        return None  # eksik eşleşme — API'ye gönder
                    results.append({"i": item["i"], "t": cached})
                return json.dumps(results, ensure_ascii=False)
            except Exception:
                return None

        api_requests = []
        tm_hits_count = 0
        raw_map = {}
        for req in requests:
            hit = _tm_fill_chunk(req)
            if hit is not None:
                raw_map[req["custom_id"]] = hit
                tm_hits_count += 1
                self._tm.record_hit()
            else:
                api_requests.append(req)

        if tm_hits_count:
            self._log(f"TM önbellekten {tm_hits_count} chunk atlandı "
                      f"({len(api_requests)} istek API'ye gönderilecek)", "ok")
            self._update_tm_stat()

        # Çökme kurtarma: önceki yarıda kalan koşudan tamamlanmış chunk'ları geri al
        api_requests = self._resume_from_sync_ckpt(api_requests, raw_map)

        total = len(requests)
        api_total = len(api_requests)
        self._log(f"{total} istek ({api_total} API, {tm_hits_count} TM) — senkron gönderiliyor...", "info")
        self._set_status(f"Anında çeviri — 0/{api_total}")

        completed = [0]
        failed    = [0]
        start_ts  = time.time()
        lock      = threading.Lock()

        def send_one(req):
            body = {k: v for k, v in req["body"].items()}
            resp = _safe_chat_create(client, **body)
            if not resp.choices:
                raise RuntimeError("API returned empty choices")
            msg  = resp.choices[0].message
            text = (msg.content or "").strip()
            if not text:
                raise RuntimeError("API returned empty content")
            tok, cached = 0, 0
            if resp.usage:
                tok, cached = _get_usage_details(resp.usage)
            return req["custom_id"], text, tok, cached

        def _progress_tick():
            _denom = api_total or 1
            pct = int(completed[0] / _denom * 100)
            self._set_progress(pct)
            self._set_stat(self.stat_done_var, str(completed[0] + tm_hits_count))
            self._set_stat(self.stat_fail_var, str(failed[0]))
            elapsed = time.time() - start_ts
            if completed[0] > 0:
                eta_s = int(elapsed / completed[0] * (_denom - completed[0]))
                self._set_eta(f"ETA ~{eta_s//60}:{eta_s%60:02d}")
            self._set_status(f"Anında: {completed[0]}/{api_total} API  +{tm_hits_count} TM ({pct}%)")

        if self.chain_ctx_var.get():
            # ── Zincirleme bağlam: dosya içi chunk'lar sıralı, dosyalar paralel ──
            # Önceki chunk'ın ÇEVİRİLERİ sonraki isteğe prev_tr olarak verilir;
            # terim, ton ve sen/siz tutarlılığı için model kendi geçmişini görür.
            api_ids = {r["custom_id"] for r in api_requests}
            file_groups, file_order = {}, []
            for req in requests:
                fp = file_map[req["custom_id"]][0][2]
                if fp not in file_groups:
                    file_groups[fp] = []
                    file_order.append(fp)
                file_groups[fp].append(req)
            self._log(f"Zincirleme bağlam aktif — {len(file_order)} dosya paralel, "
                      f"dosya içi chunk'lar sıralı (önceki çeviriler bağlama eklenir)", "info")

            def chain_file(fp):
                if self._is_queued_file_removed(fp):
                    return
                prev_pairs = []
                for req in file_groups[fp]:
                    if self._stop_flag:
                        return
                    cid      = req["custom_id"]
                    user_msg = req["body"]["messages"][1]
                    if not _req_has_ctx(req):
                        prev_pairs = []
                    if cid not in api_ids:
                        # TM önbellekten doldu — API çağrısı yok, sadece zinciri besle
                        tmap  = parse_response(raw_map.get(cid, ""), file_map[cid])
                        pairs = _chain_pairs_from_result(user_msg["content"], tmap)
                        if pairs:
                            prev_pairs = pairs
                        continue
                    user_msg["content"] = _inject_prev_tr(
                        user_msg["content"], prev_pairs, max_pairs=self._context_lines)
                    try:
                        cid_r, text, tok, cached_tok = send_one(req)
                        with lock:
                            raw_map[cid_r] = text
                            completed[0] += 1
                        self._update_tokens(tok, cached=cached_tok)
                        self._save_sync_ckpt_entry(
                            cid_r, text, self._chunk_src_hash(req, self._ckpt_fingerprint()))
                        tmap  = parse_response(text, file_map[cid])
                        pairs = _chain_pairs_from_result(user_msg["content"], tmap)
                        if pairs:
                            prev_pairs = pairs
                    except Exception as e:
                        with lock:
                            failed[0] += 1
                        self._log_exc(f"Chunk hatası [{cid}]", e)
                    _progress_tick()

            with ThreadPoolExecutor(max_workers=self._max_workers) as ex:
                futures = [ex.submit(chain_file, fp) for fp in file_order]
                for fut in as_completed(futures):
                    if self._stop_flag:
                        ex.shutdown(wait=False, cancel_futures=True)
                        break
                    try:
                        fut.result()
                    except Exception as e:
                        self._log_exc("Dosya zinciri hatası", e)
        else:
            with ThreadPoolExecutor(max_workers=self._max_workers) as ex:
                futures = {ex.submit(send_one, req): req for req in api_requests}
                for fut in as_completed(futures):
                    if self._stop_flag:
                        ex.shutdown(wait=False, cancel_futures=True)
                        break
                    req = futures[fut]
                    cid_hint = req.get("custom_id", "?")
                    try:
                        cid, text, tok, cached_tok = fut.result()
                        with lock:
                            raw_map[cid] = text
                            completed[0] += 1
                        self._update_tokens(tok, cached=cached_tok)
                        self._save_sync_ckpt_entry(
                            cid, text, self._chunk_src_hash(req, self._ckpt_fingerprint()))
                    except Exception as e:
                        with lock:
                            failed[0] += 1
                        self._log_exc(f"Chunk hatası [{cid_hint}]", e)
                    _progress_tick()

        if not self._stop_flag:
            self._retry_hata(client, raw_map, requests, max_rounds=self._max_retry)
            _all_written = self._write_results(raw_map, file_map, output_dir,
                                               openai_key=api_key, src=src)
            if _all_written:
                self._clear_sync_ckpt()   # başarılı tam koşu — kurtarma kaydı silinir

        self._set_running(False)
        self._set_status("Tamamlandı." if not self._stop_flag else "Durduruldu.")
        self._set_eta("")

    def _run_sync_hybrid(self, api_key, client, srt_files, src, tgt, model, output_dir):
        self._block_cache = {}   # önceki çalışmadan kalan cache'i temizle
        import hybrid_translate as ht
        
        ext_path    = self.ext_project_path_var.get().strip()
        ht.set_project_path(ext_path)
        input_dir = self.input_var.get()
        profanity = self.profanity_var.get()
        self._show_progress_board(srt_files)

        self._set_stat(self.stat_files_var, str(len(srt_files)))
        n_files = len(srt_files)
        report_rows = []   # kalite raporu satırları (dosya başına)
        completed_files = []
        failed_files = []
        skipped_files = []

        def send_one(req):
            body = req["body"]
            resp = _safe_chat_create(client, **body)
            if not resp.choices:
                raise RuntimeError("API returned empty choices")
            msg  = resp.choices[0].message
            text = (msg.content or "").strip()
            if not text:
                raise RuntimeError("API returned empty content")
            tok, cached = 0, 0
            if resp.usage:
                tok, cached = _get_usage_details(resp.usage)
            return req["custom_id"], text, tok, cached

        for fi, filepath in enumerate(srt_files):
            if self._stop_flag:
                break
            if self._is_queued_file_removed(filepath):
                skipped_files.append(filepath)
                continue
            fname = Path(filepath).name
            self._log(f"\n── [{fi+1}/{n_files}] {fname} ──", "info")
            self._update_file_progress(filepath, "Hazırlanıyor", 2)

            try:
                cues = ht.load_subtitle(filepath)
                if not cues:
                    self._log(f"{fname}: geçerli SRT bloğu yok, atlandı", "warn")
                    self._update_file_progress(filepath, "Atlandı", 0, "skip")
                    skipped_files.append(filepath)
                    continue
                # ── Çıktı dosyası zaten varsa ve tamamsa atla ───────────────
                out_path = _resolve_output_path(input_dir, output_dir, filepath,
                                                 same_folder=self.same_folder_var.get())
                if out_path.exists():
                    try:
                        out_blocks = list(parse_subtitle(str(out_path)))
                        if out_blocks and len(out_blocks) == len(cues):
                            has_hata = any(
                                str(blk[2]).startswith("[HATA") or str(blk[2]).startswith("[ÇEVİRİ EKSİK]") for blk in out_blocks)
                            if not has_hata:
                                self._log(f"[{fi+1}/{n_files}] {fname} — ✓ tamamlanmış, atlanıyor", "ok")
                                self._update_file_progress(filepath, "Tamamlanmış (atlandı)", 100, "done")
                                completed_files.append(filepath)
                                file_pct = int((fi + 1) / n_files * 100)
                                self._set_progress(file_pct)
                                continue
                    except Exception:
                        pass  # parse edilemediyse yeniden çevir
                # ─────────────────────────────────────────────────────────────
                self._set_stat(self.stat_blocks_var, str(len(cues)))

                # ── Yardimci model analizi ───────────────────────────────────
                glossary = ht.load_glossary(self._get_file_glossary(filepath))

                schema_dict = self._get_file_schema(filepath)
                if schema_dict["name"] == "Otomatik":
                    self._log(f"[{fname}] İçerik türü otomatik analiz ediliyor...", "info")
                    try:
                        detected_name = detect_content_type_with_ai(client, cues, model, self._log, token_callback=self._update_tokens, filename=filepath)
                        schema_dict = self._schema_by_name(detected_name)
                    except Exception as e:
                        self._log(f"Otomatik şema tespiti başarısız: {e}", "warn")
                glossary = self._merge_schema_glossary(glossary, schema_dict)

                cached = ht.load_context_cache(
                    filepath,
                    expected_target=tgt,
                    expected_analysis_depth=self.analysis_depth_var.get(),
                )
                if cached:
                    context, char_examples, pronoun_map, character_styles, scene_emotions, idiom_map, cultural_refs = cached
                    self._log(f"Önbellek bulundu — analiz atlanıyor ({fname})", "ok")
                    self._update_file_progress(filepath, "Analiz (önbellek)", 38)
                else:
                    helper_name = self._helper_display_name("analysis")
                    self._set_phase(f"{helper_name} Analiz", f"{fname}  ({fi+1}/{n_files})")
                    self._update_file_progress(filepath, f"{helper_name} Analiz", 5)

                    def _ap(done, total_chunks, _fi=fi, _fp=filepath):
                        phase = done / total_chunks * 0.4 / n_files
                        self._set_progress(int((_fi / n_files + phase) * 100))
                        self._set_status(f"Analiz: {done}/{total_chunks} chunk — {fname}")
                        pct = int(done / total_chunks * 38)
                        self._update_file_progress(_fp, f"{helper_name} Analiz {done}/{total_chunks}", pct)

                    try:
                        result = ht.analyze_with_helper(
                            cues=cues, helper_api_key=self._helper_api_key("analysis"), helper_url=self._helper_api_base_url("analysis"), helper_model=self._helper_api_model("analysis"),
                            style=self.style_var.get(),
                            source_language=_lang_iso639_1(src),
                            target_language=_lang_iso639_1(tgt),
                            glossary=glossary, log_fn=self._log,
                            stop_flag_fn=lambda: self._stop_flag,
                            progress_fn=_ap,
                            schema=schema_dict,
                            analysis_depth=self.analysis_depth_var.get())
                    except Exception as e:
                        self._log(f"[{fname}] Analiz hatası: {e} — boş bağlamla devam", "warn")
                        result = None
                    if result is None:
                        if self._stop_flag:
                            break
                        else:
                            self._log(f"[{fname}] Analiz başarısız — boş bağlamla çeviri devam ediyor", "warn")
                            self._update_file_progress(filepath, "Analiz atlandı", 10, "warn")
                            result = ht.empty_analysis_result(_lang_iso639_1(src))
                    context, char_examples, pronoun_map, character_styles, scene_emotions, idiom_map, cultural_refs = result
                    ht.save_context_cache(context, filepath, char_examples, pronoun_map,
                                          character_styles=character_styles,
                                          scene_emotions=scene_emotions,
                                          idiom_map=idiom_map,
                                          cultural_refs=cultural_refs,
                                          target_language=tgt,
                                          analysis_depth=self.analysis_depth_var.get())
                    # Proje hafızasına kaydet
                    if self._pm is not None:
                        try:
                            self._pm.merge_glossary_from_analysis(
                                ht.sanitize_glossary_for_turkish(
                                    dict(context.recurring_terms), target_language=tgt
                                )
                            )
                            self._pm.update_characters([c.name for c in context.characters
                                                        if hasattr(c, 'name')])
                            if pronoun_map:
                                self._pm.update_pronoun_map(pronoun_map)
                        except Exception:
                            pass
                    self._log(f"Analiz tamam — {len(context.recurring_terms)} terim, "
                              f"{len(context.characters)} karakter, "
                              f"{len(char_examples)} örnek"
                              + (f", {len(idiom_map)} deyim" if idiom_map else "")
                              + (f", hitap: {pronoun_map}" if pronoun_map else ""), "ok")
                    if context.recurring_terms:
                        self._log(f"Sabit terimler: {context.recurring_terms}", "info")
                    self._update_file_progress(filepath, "Analiz tamam", 40)
            except Exception as e:
                self._log_exc(f"[{fname}] Yardimci analiz hatası — dosya atlanıyor", e)
                self._update_file_progress(filepath, "Analiz hatası", 10, "error")
                failed_files.append(filepath)
                continue

            # ── OpenAI sync ───────────────────────────────────────────────────
            # Dizi hafızasını bu bölümün analiziyle güncelle, sonra önceki
            # bölümlerin birikmiş kararlarını prompt'a ekle (ilk karar kanon)
            self._update_series_memory_from_analysis(filepath, context, pronoun_map)
            system_prompt = ht.build_system_prompt(
                context, src, tgt,
                schema=schema_dict,
                character_examples=char_examples,
                profanity=profanity,
                pronoun_map=pronoun_map,
                character_styles=character_styles,
                idiom_map=None,   # deyimler per-chunk 'idioms' payload'ında veriliyor — çift enjeksiyon olmasın
                cultural_refs=cultural_refs,
            )
            system_prompt += self._series_hint_for(filepath)
            if self._pm is not None:
                system_prompt += self._pm.build_context_hint()   # proje hafızası ipucu (sync/batch ile paritede)
            batch_reqs, fmap = ht.build_batch_requests(cues, system_prompt, model,
                                                        chunk_size=self._chunk_size, glossary=glossary,
                                                        scene_emotions=scene_emotions,
                                                        idiom_map=idiom_map,
                                                        tm=self._tm,
                                                        tgt_lang=tgt,
                                                        context_lines=self._context_lines,
                                                        lookahead_lines=self._lookahead_lines,
                                                        scene_gap_sec=self._scene_gap_seconds,
                                                        temperature=self._temperature)
            total     = len(batch_reqs)
            completed = [0]
            failed    = [0]
            raw_map   = {}
            _ckpt_scope = str(Path(filepath).resolve())
            self._prefill_sync_ckpt(batch_reqs, raw_map, scope=_ckpt_scope)
            start_ts  = time.time()
            lock      = threading.Lock()
            base_pct  = int((fi + 0.4) / n_files * 100)

            self._log(f"{total} istek gönderiliyor (sync+hybrid)...", "info")
            self._set_phase("Çeviri", f"{fname}  ({fi+1}/{n_files})  —  0/{total} chunk")
            self._update_file_progress(filepath, f"Çeviri 0/{total}", 40)

            def _hyb_tick(_fp=filepath, _fname=fname, _total=total, _base=base_pct):
                file_pct = int(completed[0] / _total * 0.5 / n_files * 100)
                self._set_progress(_base + file_pct)
                self._set_stat(self.stat_done_var, str(completed[0]))
                self._set_stat(self.stat_fail_var, str(failed[0]))
                elapsed = time.time() - start_ts
                if completed[0] > 0:
                    eta_s = int(elapsed / completed[0] * (_total - completed[0]))
                    self._set_eta(f"ETA ~{eta_s//60}:{eta_s%60:02d}")
                tr_pct = int(completed[0] / _total * 45) + 40
                self._set_status(f"{_fname}  —  {completed[0]}/{_total} chunk")
                self._update_file_progress(_fp, f"Çeviri {completed[0]}/{_total}", tr_pct)

            if self.chain_ctx_var.get():
                # ── Zincirleme bağlam: chunk'lar sıralı, önceki çeviriler prev_tr ──
                self._log("Zincirleme bağlam aktif — chunk'lar sıralı işlenir "
                          "(önceki çeviriler bağlama eklenir)", "info")
                prev_pairs = []
                for req in batch_reqs:
                    if self._stop_flag:
                        break
                    cid_hint = req.get("custom_id", "?")
                    if not _req_has_ctx(req):
                        prev_pairs = []
                    # Çökme kurtarma: bu chunk önceki koşuda tamamlanmış → API'ye gönderme,
                    # yalnızca zinciri (prev_pairs) besle.
                    if cid_hint in raw_map:
                        tmap  = parse_response(raw_map[cid_hint], fmap.get(cid_hint, []))
                        pairs = _chain_pairs_from_result(req["body"]["messages"][1]["content"], tmap)
                        if pairs:
                            prev_pairs = pairs
                        completed[0] += 1
                        _hyb_tick()
                        continue
                    user_msg = req["body"]["messages"][1]
                    user_msg["content"] = _inject_prev_tr(
                        user_msg["content"], prev_pairs, max_pairs=self._context_lines)
                    try:
                        cid, text, tok, cached_tok = send_one(req)
                        with lock:
                            raw_map[cid] = text
                            completed[0] += 1
                        self._update_tokens(tok, cached=cached_tok)
                        self._save_sync_ckpt_entry(
                            cid, text, self._chunk_src_hash(
                                req, self._ckpt_fingerprint(), _ckpt_scope))
                        tmap  = parse_response(text, fmap.get(cid, []))
                        pairs = _chain_pairs_from_result(user_msg["content"], tmap)
                        if pairs:
                            prev_pairs = pairs
                    except Exception as e:
                        with lock:
                            failed[0] += 1
                        self._log_exc(f"Chunk hatası [{cid_hint}] [{fname}]", e)
                    _hyb_tick()
            else:
                with ThreadPoolExecutor(max_workers=self._max_workers) as ex:
                    # Çökme kurtarma: zaten tamamlanmış (raw_map'te) chunk'ları gönderme
                    futures = {ex.submit(send_one, req): req
                               for req in batch_reqs if req["custom_id"] not in raw_map}
                    for fut in as_completed(futures):
                        if self._stop_flag:
                            ex.shutdown(wait=False, cancel_futures=True)
                            break
                        req = futures[fut]
                        cid_hint = req.get("custom_id", "?")
                        try:
                            cid, text, tok, cached_tok = fut.result()
                            with lock:
                                raw_map[cid] = text
                                completed[0] += 1
                            self._update_tokens(tok, cached=cached_tok)
                            self._save_sync_ckpt_entry(
                            cid, text, self._chunk_src_hash(
                                req, self._ckpt_fingerprint(), _ckpt_scope))
                        except Exception as e:
                            with lock:
                                failed[0] += 1
                            self._log_exc(f"Chunk hatası [{cid_hint}] [{fname}]", e)
                        _hyb_tick()

            if self._stop_flag:
                break

            # ── Retry + Birleştir ─────────────────────────────────────────────
            self._retry_hata(client, raw_map, batch_reqs, max_rounds=self._max_retry)
            srt_blocks = {}
            for cid, info in fmap.items():
                raw = raw_map.get(cid)
                if not raw:
                    for (idx, start, end) in info:
                        srt_blocks[idx] = (str(idx), f"{start} --> {end}", "[HATA]")
                    continue
                trans_map = parse_response(raw, info)
                for (idx, start, end) in info:
                    text = trans_map.get(str(idx), "[HATA]")
                    srt_blocks[idx] = (str(idx), f"{start} --> {end}", text)

            sorted_blocks = [srt_blocks[k] for k in sorted(
                srt_blocks, key=lambda k: (0, int(k)) if str(k).isdigit() else (1, str(k)))]
            _raw_backup_blocks = list(sorted_blocks)   # kalite geçişleri öncesi ham çeviri (yedek)

            # ── Consistency Sweep (dosya içi tekrar tutarsızlıklarını normalize et) ──
            self._update_file_progress(filepath, "Tutarlılık taraması", 87)
            sorted_blocks, _cons_fixes = ht.consistency_sweep(cues, sorted_blocks, log_fn=self._log)
            # Rapor için taban çizgisi: kalite geçişleri öncesi metinler
            _pre_pass = {str(b[0]): b[2] for b in sorted_blocks}
            _qc_fixes = 0
            _qc_auto_fixes = 0
            _pass_trace = {}
            _pass_history = {}

            # ── Critic Pass (otomatik düzeltme) ──────────────────────────────
            if self.critic_var.get() and sorted_blocks:
                self._set_phase("Critic Pass", f"{fname}  —  {len(sorted_blocks)} satır")
                self._update_file_progress(filepath, "Critic Pass", 89)
                self._log(f"Critic Pass başlıyor ({len(sorted_blocks)} satır)...", "info")
                _before_pass = list(sorted_blocks)
                _critic_change_log = []
                sorted_blocks = ht.critic_pass_with_helper(
                    cues=cues,
                    tr_blocks=sorted_blocks,
                    helper_api_key=self._helper_api_key("critic"), helper_url=self._helper_api_base_url("critic"), helper_model=self._helper_api_model("critic"),
                    tgt_lang=tgt,
                    log_fn=self._log,
                    glossary=glossary,
                    analysis_result=(context, char_examples, pronoun_map),
                    change_log=_critic_change_log,
                )
                _record_pass_change(_pass_trace, "Critic", _before_pass, sorted_blocks, _pass_history)
                self._write_critic_change_report(out_path, _critic_change_log)

            # ── Polish Pass (gpt-5.4-mini doğallaştırma) ─────────────────────
            if self.polish_var.get() and sorted_blocks:
                self._set_phase("Polish Pass", f"{fname}  —  doğallaştırma")
                self._update_file_progress(filepath, "Polish Pass", 92)
                self._log(f"Polish Pass başlıyor ({len(sorted_blocks)} satır)...", "info")
                _before_pass = list(sorted_blocks)
                sorted_blocks = self._polish_pass(
                    sorted_blocks, tgt,
                    self._helper_api_key("polish"),
                    self._helper_api_base_url("polish"),
                    self._helper_api_model("polish"),
                    src_map=_src_map_from_cues(cues),
                    analysis_result=(context, char_examples, pronoun_map,
                                     character_styles, scene_emotions, idiom_map, cultural_refs))
                _record_pass_change(_pass_trace, "Polish", _before_pass, sorted_blocks, _pass_history)
                self._log("Polish Pass tamamlandı", "ok")

            # ── Native Okuyucu Pass ───────────────────────────────────────────
            if self.native_var.get() and sorted_blocks:
                self._set_phase("Native Okuyucu", f"{fname}  —  doğallık taraması")
                self._update_file_progress(filepath, "Native Okuyucu", 94)
                self._log(f"Native Okuyucu Pass başlıyor ({len(sorted_blocks)} satır)...", "info")
                _before_pass = list(sorted_blocks)
                sorted_blocks = ht.native_reader_pass(
                    tr_blocks=sorted_blocks,
                    helper_api_key=self._helper_api_key("critic"), helper_url=self._helper_api_base_url("critic"), helper_model=self._helper_api_model("critic"),
                    tgt_lang=tgt,
                    log_fn=self._log,
                    analysis_result=(context, char_examples, pronoun_map,
                                     character_styles, scene_emotions, idiom_map, cultural_refs),
                    token_callback=self._update_tokens,
                    src_map=_src_map_from_cues(cues),
                )
                _record_pass_change(_pass_trace, "Native", _before_pass, sorted_blocks, _pass_history)

            if sorted_blocks and (self.critic_var.get() or self.polish_var.get() or self.native_var.get()):
                _before_pass = list(sorted_blocks)
                sorted_blocks, _final_cons_fixes = ht.final_consistency_sweep(cues, sorted_blocks, log_fn=self._log)
                if _final_cons_fixes:
                    _record_pass_change(_pass_trace, "Final-Consistency", _before_pass, sorted_blocks, _pass_history)

            # Kalite geçişi düzeltmeleri (critic + polish + native değişen satır)
            _pass_fix = sum(1 for b in sorted_blocks
                            if _pre_pass.get(str(b[0])) not in (None, b[2]))

            # ── CPS kontrolü (paylaşılan helper — tüm akışlarda aynı) ────────
            _log_cps_warning(sorted_blocks, self._log)

            # Okuma hızı kısaltma (satır kırmadan ÖNCE — kısaltılmış metni kırar)
            _before_pass = list(sorted_blocks)
            _src_map_for_condense = {str(c.index): _clean_src(c.text) for c in cues} if cues else {}
            sorted_blocks = self._maybe_condense(
                sorted_blocks,
                self._helper_api_key("analysis"),
                self._helper_api_base_url("analysis"),
                self._helper_api_model("analysis"),
                tgt, src_map=_src_map_for_condense)
            _record_pass_change(_pass_trace, "Condense", _before_pass, sorted_blocks, _pass_history)

            if self.clean_sdh_var.get():
                _before_pass = list(sorted_blocks)
                sorted_blocks = clean_sdh(sorted_blocks, src_map=_src_map_for_condense, source_driven=True)
                _record_pass_change(_pass_trace, "SDH", _before_pass, sorted_blocks, _pass_history)

            if self.linebreak_var.get() and sorted_blocks:
                _before_pass = list(sorted_blocks)
                sorted_blocks = apply_line_breaks(sorted_blocks)
                _record_pass_change(_pass_trace, "Line-break", _before_pass, sorted_blocks, _pass_history)

            # ── QC Kontrolü (kullanıcı onayı ile) ────────────────────────────
            if self.qc_var.get() and sorted_blocks:
                self._set_status(f"{self._helper_display_name('qc')} QC: {fname}")
                issues = ht.quality_check_with_helper(
                    cues=cues,
                    tr_blocks=sorted_blocks,
                    helper_api_key=self._helper_api_key("qc"), helper_url=self._helper_api_base_url("qc"), helper_model=self._helper_api_model("qc"),
                    tgt_lang=tgt,
                    log_fn=self._log,
                    analysis_result=(context, char_examples, pronoun_map),
                )
                if issues:
                    auto_issues, review_issues = ht.split_qc_issues_for_review(issues)
                    if auto_issues:
                        _before_pass = list(sorted_blocks)
                        self._log(f"QC auto: {len(auto_issues)} düşük/orta severity düzeltme uygulanıyor", "info")
                        sorted_blocks = ht.qc_auto_fix(
                            issues=auto_issues,
                            tr_blocks=sorted_blocks,
                            helper_api_key=self._helper_api_key("qc"),
                            model=self._helper_api_model("qc"),
                            tgt_lang=tgt,
                            base_url=self._helper_api_base_url("qc"),
                            log_fn=self._log,
                        )
                        _n_auto = _record_pass_change(_pass_trace, "QC auto", _before_pass, sorted_blocks, _pass_history)
                        _qc_fixes += _n_auto
                        _qc_auto_fixes += _n_auto
                    approved_fixes = []
                    status = "completed"
                    if review_issues:
                        qc_event      = threading.Event()
                        _post_ui(self, self._show_qc_dialog, review_issues, approved_fixes, qc_event)
                        status = self._wait_for_dialog_event(qc_event, timeout=300)
                        if status == "stopped":
                            break
                        if status == "timeout":
                            self._set_status("QC: süre aşımı")
                    if approved_fixes and status == "completed":
                        _before_pass = list(sorted_blocks)
                        sorted_blocks = ht.qc_auto_fix(
                            issues=approved_fixes,
                            tr_blocks=sorted_blocks,
                            helper_api_key=self._helper_api_key("qc"),
                            model=self._helper_api_model("qc"),
                            tgt_lang=tgt,
                            base_url=self._helper_api_base_url("qc"),
                            log_fn=self._log,
                        )
                        _n_approved = _record_pass_change(_pass_trace, "QC", _before_pass, sorted_blocks, _pass_history)
                        _qc_fixes += _n_approved

            # Çevrilemeyen satırları sync ile onarma denemesi
            try:
                _raw_map_pre = _raw_src_map_from_cues(cues)
                sorted_blocks, _n_repaired = _repair_untranslated_sync(
                    sorted_blocks, _raw_map_pre, client,
                    src_lang=src, tgt_lang=tgt,
                    model=model,
                    schema=self._get_schema(), profanity=self.profanity_var.get(),
                    log_fn=self._log, token_cb=self._update_tokens)
            except Exception:
                pass
            # [HATA] satırlarını görünür işaretle bırak + etiketleri geri uygula
            _n_filled = 0
            try:
                _raw_map = _raw_src_map_from_cues(cues)
                sorted_blocks, _n_filled = _fill_hata_with_source(sorted_blocks, _raw_map, log_fn=self._log)
                sorted_blocks = _restore_tags_blocks(sorted_blocks, _raw_map)
            except Exception:
                pass
            if getattr(self, "term_normalize_var", None) and self.term_normalize_var.get():
                try:
                    sorted_blocks, _ = _normalize_mixed_terms(
                        sorted_blocks, {str(c.index): _clean_src(c.text) for c in cues},
                        self._helper_api_key("polish"), self._helper_api_base_url("polish"),
                        self._helper_api_model("polish"), log_fn=self._log)
                except Exception:
                    pass
            out_path = _resolve_output_path(input_dir, output_dir, filepath,
                                             same_folder=self.same_folder_var.get())
            write_srt(out_path, self._maybe_merge_cues(sorted_blocks))
            completed_files.append(filepath)
            self._log(f"Kaydedildi: {out_path}", "ok")
            self._save_raw_backup(out_path, _raw_backup_blocks, _raw_map)
            # Kalite taraması (çeviri sonrası uyarılar) — diğer akışlarla paritede
            _w = 0
            try:
                _w = scan_translation_quality(
                    filepath, sorted_blocks, log_fn=self._log,
                    src_clean_map={str(c.index): _clean_src(c.text) for c in cues})
            except Exception:
                pass
            self._maybe_backtranslation_check(
                out_path, {str(c.index): _clean_src(c.text) for c in cues}, sorted_blocks)
            # Rapor satırı
            _hata_n, _cps_n = _count_hata_cps(sorted_blocks)
            _cps_avg, _cps_max = _cps_stats(sorted_blocks)
            _pc = "+".join(k for k, v in [("critic",self.critic_var.get()),("polish",self.polish_var.get()),("native",self.native_var.get()),("QC",self.qc_var.get()),("condense",self.condense_var.get()),("review",self.review_pass_var.get()),("termnorm",self.term_normalize_var.get()),("2wave",self.twowave_var.get()),("SDH",self.clean_sdh_var.get()),("linebreak",self.linebreak_var.get())] if v)
            report_rows.append({
                "name": fname, "total": len(sorted_blocks),
                "hata": _hata_n + _n_filled, "cps": _cps_n,
                "cps_avg": _cps_avg, "cps_max": _cps_max,
                "cons": _cons_fixes, "pass_fix": _pass_fix,
                "qc_auto": _qc_auto_fixes, "qc": _qc_fixes, "warn": _w,
                "pass_trace": _pass_trace,
                "pass_history": _pass_history,
                "pass_coverage": _pc,
                "tm_hits": self._tm.hit_count_session(),
            })
            # TM kaydı (ortak yardımcı)
            self._store_tm_pairs(sorted_blocks,
                                 {str(c.index): _clean_src(c.text) for c in cues},
                                 self._main_model_name(), tgt)
            if self.auto_glossary_var.get():
                self._run_auto_glossary(cues, sorted_blocks, filepath)
            ht.clear_context_cache(filepath)
            self._update_file_progress(filepath,
                f"Tamamlandı  {len(sorted_blocks)} satır", 100, "done")
            if self._wait_between_files(fi, n_files, fname) == "stopped":
                break

        summary = summarize_file_outcomes(
            completed_files, failed_files, skipped_files, total_files=n_files, stop_flag=self._stop_flag
        )
        if summary["is_recovery_complete"]:
            self._clear_sync_ckpt()   # tamamlanan veya bilinçli atlanan tüm dosyalar muhasebeleştirildi
        self._save_quality_report(report_rows, output_dir)
        self._set_running(False)
        self._set_eta("")
        if not self._stop_flag:
            self._set_progress(100)
            self._set_phase("Tamamlandı" if summary["is_full_success"] else "Kısmen Tamamlandı",
                            f"{summary['summary_text']} → {output_dir}")
            self._notify(summary["title_text"], f"{summary['summary_text']} → {output_dir}")
            if summary["completed_count"] > 0:
                try:
                    _post_ui(self, messagebox.showinfo, summary['title_text'], f"{summary['summary_text']}!\n\nKonum:\n{output_dir}")
                except Exception:
                    pass
        else:
            self._set_phase("Hazır", "Durduruldu.")

    # ── Batch mod ─────────────────────────────────────────────────────────────
    def _run_batch(self, api_key):
        import hybrid_translate as ht
        b_url = self._main_api_base_url()
        client = OpenAI(api_key=api_key, base_url=b_url if b_url else None)
        output_dir = self.output_var.get()
        src, tgt   = self.src_var.get(), self.tgt_var.get()
        model      = self._main_model_name()
        srt_files  = self._get_srt_files()

        if not srt_files:
            self._log("Giriş klasöründe .srt bulunamadı!", "err")
            self._set_running(False)
            return

        self._set_stat(self.stat_files_var, str(len(srt_files)))

        # Parse her dosyayı bir kez yap — hem boş-filtre hem blok sayımı için kullan
        self._block_cache: dict = {}
        valid_files = []
        for fp in srt_files:
            if self._is_queued_file_removed(fp):
                continue
            blocks = list(parse_subtitle(fp))
            if not blocks:
                self._log(f"{Path(fp).name}: geçerli altyazı bloğu yok, atlandı", "warn")
            else:
                self._block_cache[fp] = blocks
                valid_files.append(fp)
        if not valid_files:
            self._log("Geçerli altyazı dosyası yok!", "err")
            self._set_running(False)
            return

        _profanity = self.profanity_var.get()
        _global_glossary = ht.load_glossary(self._get_file_glossary(valid_files[0])) if valid_files else {}
        if _global_glossary:
            self._log(f"Glossary: {len(_global_glossary)} terim yüklendi", "info")
        _auto_files = [fp for fp in valid_files
                       if self._get_file_schema(fp)["name"] == "Otomatik"]
        if _auto_files:
            self._log(f"{len(_auto_files)} dosyanın içerik türü paralel analiz ediliyor...", "info")
        _detected = self._detect_content_types_parallel(client, _auto_files, model)
        _schema_groups: dict = {}
        for fp in valid_files:
            sname = self._get_file_schema(fp)["name"]
            if sname == "Otomatik":
                sname = _detected.get(fp, "Otomatik")
            _schema_groups.setdefault(sname, []).append(fp)
        # Ön-bağlam analizi (özet, karakterler, sen/siz haritası, sabit terimler)
        _file_hints = self._get_precontext_hints(client, valid_files, src, tgt, model)
        # Dizi hafızası: önceki bölümlerin terim/karakter/sen-siz kararlarını ekle
        _sm_used = 0
        for fp in valid_files:
            _sm_hint = self._series_hint_for(fp)
            if _sm_hint:
                _file_hints[fp] = _file_hints.get(fp, "") + _sm_hint
                _sm_used += 1
        if _sm_used:
            self._log(f"Dizi hafızası: {_sm_used} dosyaya önceki bölüm kararları eklendi", "info")
        all_requests, all_file_map = [], {}
        for sname, group in _schema_groups.items():
            reqs, fmap = build_requests(group, src, tgt, model,
                                        chunk_size=self._chunk_size,
                                        schema=self._schema_by_name(sname),
                                        profanity=_profanity,
                                        glossary=_global_glossary,
                                        project_memory=self._pm,
                                        file_hints=_file_hints,
                                        block_cache=self._block_cache,
                                        context_lines=self._context_lines,
                                        lookahead_lines=self._lookahead_lines,
                                        scene_gap_sec=self._scene_gap_seconds,
                                        temperature=self._temperature)
            all_requests.extend(reqs)
            all_file_map.update(fmap)
            if len(_schema_groups) > 1:
                self._log(f"Şema '{sname}': {len(group)} dosya, {len(reqs)} istek", "info")
        requests, file_map = all_requests, all_file_map
        # Cache'ten blok sayısını al — dosyaları tekrar parse etme
        total_blocks = sum(len(self._block_cache[fp]) for fp in valid_files)
        self._set_stat(self.stat_blocks_var, str(total_blocks))
        self._log(f"{total_blocks} satır → {len(requests)} istek "
                  f"(chunk {self._chunk_size}, ctx +{self._context_lines}, next +{self._lookahead_lines})", "info")

        LIMIT  = 50_000
        chunks = [requests[i:i+LIMIT] for i in range(0, len(requests), LIMIT)]
        if len(chunks) > 1:
            self._log(f"50.000 limit — {len(chunks)} batch'e bölünüyor.", "warn")

        import tempfile
        import uuid
        run_id = uuid.uuid4().hex
        input_dir = self.input_var.get()
        output_paths = {
            fp: str(_resolve_output_path(
                input_dir, output_dir, fp, same_folder=self.same_folder_var.get()))
            for fp in valid_files
        }
        batch_ids = []
        batch_runs = []
        for ci, chunk in enumerate(chunks):
            if self._stop_flag:
                break
            state_dir(__file__).mkdir(parents=True, exist_ok=True)
            tmp = tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", suffix=".jsonl", prefix="batch_input_",
                dir=state_dir(__file__), delete=False)
            jpath = Path(tmp.name)
            with tmp as f:
                for req in chunk:
                    f.write(json.dumps(req, ensure_ascii=False) + "\n")
            _upload_failed = False
            try:
                self._log(f"Yükleniyor ({ci+1}/{len(chunks)})...", "info")
                with open(jpath, "rb") as f:
                    up = client.files.create(file=f, purpose="batch")
                batch = client.batches.create(
                    input_file_id=up.id,
                    endpoint="/v1/chat/completions",
                    completion_window="24h")
                batch_ids.append(batch.id)
                mutate_batch_ids(_batch_id_path(), add=[batch.id])
                self._register_batch(batch.id, api_key, b_url)
                slice_fmap = _slice_file_map(file_map, chunk)
                batch_runs.append((batch.id, slice_fmap, chunk))
                fmap_path = state_path(__file__, f"batch_fmap_{batch.id}.json")
                fmap_data = {
                    "type": "regular",
                    "output_dir": output_dir,
                    "run_id": run_id,
                    "part_index": ci,
                    "part_count": len(chunks),
                    "output_paths": output_paths,
                    "requests": chunk,
                    "fmap": {cid: [list(x) for x in info] for cid, info in slice_fmap.items()},
                }
                atomic_write_json(fmap_path, fmap_data)
                self._log(f"Batch oluşturuldu: {batch.id}", "ok")
            except Exception as e:
                self._log_exc("Hata", e)
                self._set_running(False)
                _upload_failed = True
            finally:
                # Yükleme sonrası geçici JSONL dosyasını temizle
                try:
                    jpath.unlink(missing_ok=True)
                except Exception:
                    pass
            if _upload_failed:
                if batch_ids:
                    self._log(f"{len(batch_ids)} batch gönderilmişti — "
                              f"'↺ Batch'i Devam Ettir' ile alınabilir veya "
                              f"Durdur ile iptal edilebilir.", "warn")
                msg = (f"Batch yükleme hatası (chunk {ci+1}/{len(chunks)}).\n"
                       f"{len(batch_ids)} batch OpenAI'ye teslim edildi — ücretlendirilebilir.\n"
                       f"'↺ Batch'i Devam Ettir' ile tamamlayabilir veya Durdur ile iptal edebilirsiniz.")
                self._log(msg, "err")
                try:
                    _post_ui(self, messagebox.showerror, "Batch Upload Hatası", msg)
                except Exception:
                    pass
                return

        accumulated_raw_map = {}
        completed_bids = []   # YALNIZCA OpenAI'nin bitirdiği (terminal) batch'ler
        all_terminal = len(batch_runs) == len(chunks)
        for i, (bid, slice_fmap, _chunk) in enumerate(batch_runs):
            if self._stop_flag:
                break
            if len(batch_ids) > 1:
                self._log(f"\n── Batch {i+1}/{len(batch_ids)} ──", "info")
            batch_raw_map, terminal = self._wait_batch(client, bid, slice_fmap, output_dir,
                                                       requests_list=None,
                                                       is_last=(i == len(batch_ids)-1))
            if terminal:
                completed_bids.append(bid)
            else:
                all_terminal = False
            if batch_raw_map:
                accumulated_raw_map.update(batch_raw_map)

        final_written = False
        if not self._stop_flag and accumulated_raw_map and all_terminal:
            self._retry_hata(client, accumulated_raw_map, requests, max_rounds=self._max_retry)
            missing_ids = set(file_map) - set(accumulated_raw_map)
            if missing_ids:
                self._log(f"{len(missing_ids)} batch sonucu eksik; final dosya yazılmadı.", "warn")
            else:
                final_written = self._write_results(
                    accumulated_raw_map, file_map, output_dir,
                    openai_key=api_key, src=src, output_paths=output_paths)
        elif not self._stop_flag:
            self._log("Tüm batch parçaları terminal duruma gelmedi; eksik final dosya yazılmadı.", "warn")
        # Kurtarma kaydını YALNIZCA terminal (OpenAI'nin bitirdiği) batch'ler için temizle —
        # polling hatasıyla yarıda kalan ÖDENMİŞ batch'ler Resume için KORUNUR (kalıcı kayıp önlenir).
        if not self._stop_flag and completed_bids and final_written:
            self._clear_batch_recovery(completed_bids)
        self._set_running(False)   # #2: upload sonrası ilk poll'dan önce Stop'ta UI kilitlenmesin

    def _resume_batches(self, api_key, batch_ids):
        b_url = self._main_api_base_url()
        client = OpenAI(api_key=api_key, base_url=b_url if b_url else None)
        output_dir = self.output_var.get()
        src, tgt   = self.src_var.get(), self.tgt_var.get()
        model      = self._main_model_name()

        # Build default file_map for regular batches
        srt_files = self._get_srt_files()
        default_requests, default_file_map = build_requests(
            srt_files, src, tgt, model,
            schema=self._get_schema(),
            profanity=self.profanity_var.get(),
            chunk_size=self._chunk_size,
            context_lines=self._context_lines,
            lookahead_lines=self._lookahead_lines,
            scene_gap_sec=self._scene_gap_seconds,
            temperature=self._temperature) if srt_files else ([], {})

        accumulated_raw_map = {}
        accumulated_file_map = {}
        accumulated_requests = []
        accumulated_output_paths = {}
        regular_groups = {}
        regular_recovery_safe = True
        last_output_dir = output_dir
        _resume_report_rows = []   # hybrid resume kalite raporu
        hybrid_completed_bids = []
        regular_terminal_bids = []

        for i, bid in enumerate(batch_ids):
            if self._stop_flag:
                break
            bid = bid.strip()
            self._register_batch(bid, api_key, b_url)   # durdururken iptal edilebilsin
            fmap_path = state_path(__file__, f"batch_fmap_{bid}.json")

            if fmap_path.exists():
                try:
                    with open(fmap_path, encoding="utf-8") as f:
                        fmap_data = json.load(f)
                    batch_type = fmap_data.get("type", "regular")
                    saved_fmap = {cid: [tuple(x) for x in info]
                                  for cid, info in fmap_data["fmap"].items()}
                    if batch_type == "hybrid":
                        out_path = fmap_data.get("output_path", "")
                        # Gönderim anında saklananları kullan — UI'daki girdi/çıktı kutuları
                        # yeniden başlatma sonrası başka bir şeye dönmüş olabilir (düz-batch
                        # dalı zaten output_dir'i böyle saklıyordu; hybrid'de eksikti).
                        _saved_src = fmap_data.get("source_path", "")
                        _saved_out_dir = fmap_data.get("output_dir", "")
                        if _saved_out_dir:
                            last_output_dir = _saved_out_dir
                        _terminal = self._wait_batch_hybrid(client, bid, saved_fmap, out_path,
                                                openai_key=api_key,
                                                is_last=(i == len(batch_ids)-1),
                                                report_rows=_resume_report_rows,
                                                source_path=_saved_src)
                        if _terminal:
                            hybrid_completed_bids.append(bid)
                        if self._wait_between_files(i, len(batch_ids), Path(out_path).name) == "stopped":
                            break
                    else:
                        saved_out = fmap_data.get("output_dir", output_dir)
                        last_output_dir = saved_out
                        accumulated_file_map.update(saved_fmap)
                        accumulated_requests.extend(fmap_data.get("requests") or [])
                        accumulated_output_paths.update(fmap_data.get("output_paths") or {})
                        run_id = str(fmap_data.get("run_id") or bid)
                        part_index = int(fmap_data.get("part_index", 0))
                        part_count = max(1, int(fmap_data.get("part_count", 1)))
                        group = regular_groups.setdefault(
                            run_id, {"expected": part_count, "seen": set(), "terminal": True})
                        group["expected"] = max(group["expected"], part_count)
                        group["seen"].add(part_index)
                        batch_raw_map, _terminal = self._wait_batch(client, bid, saved_fmap, saved_out,
                                                         requests_list=None,
                                                         is_last=(i == len(batch_ids)-1))
                        if _terminal:
                            regular_terminal_bids.append(bid)
                        else:
                            group["terminal"] = False
                        if batch_raw_map:
                            accumulated_raw_map.update(batch_raw_map)
                    continue
                except Exception as e:
                    self._log(f"Kaydedilmiş file_map yüklenemedi ({bid}): {e} — yeniden oluşturuluyor", "warn")

            self._log(f"[HATA] {bid}: batch_fmap_{bid}.json yok; yanlış/boş final "
                      "yazmamak için resume durduruldu.", "err")
            regular_recovery_safe = False

        regular_ready = _regular_batch_groups_ready(
            regular_groups, recovery_safe=regular_recovery_safe)
        regular_written = False
        if not self._stop_flag and accumulated_raw_map and regular_ready:
            retry_source = accumulated_requests or default_requests
            retry_list = [r for r in retry_source if r["custom_id"] in accumulated_file_map]
            self._retry_hata(client, accumulated_raw_map, retry_list, max_rounds=self._max_retry)
            missing_ids = set(accumulated_file_map) - set(accumulated_raw_map)
            if missing_ids:
                self._log(f"{len(missing_ids)} kurtarılmış batch sonucu eksik; final yazılmadı.", "warn")
            else:
                regular_written = self._write_results(
                    accumulated_raw_map, accumulated_file_map, last_output_dir,
                    openai_key=api_key, src=src,
                    output_paths=accumulated_output_paths)
        elif not self._stop_flag and (accumulated_raw_map or regular_groups):
            self._log("Regular batch parçalarının tümü hazır değil; eksik final yazılmadı.", "warn")
        # Hybrid resume yolunda işlenen dosyalar için kalite raporu yaz
        if _resume_report_rows:
            self._save_quality_report(_resume_report_rows, last_output_dir)
        # Kurtarma kaydını YALNIZCA terminal (OpenAI'nin bitirdiği) batch'ler için temizle —
        # polling hatasıyla yarıda kalan ÖDENMİŞ batch'ler Resume için KORUNUR.
        clear_ids = list(hybrid_completed_bids)
        if regular_written:
            clear_ids.extend(regular_terminal_bids)
        if not self._stop_flag and clear_ids:
            self._clear_batch_recovery(clear_ids)
        self._set_running(False)   # erken-stop / hiç-poll-yok durumunda UI kilitlenmesin

    def _wait_batch_hybrid(self, client, batch_id, file_map, output_path,
                           openai_key, is_last=True, report_rows=None, source_path=""):
        """Hybrid batch tamamlanınca ht.save_results ile yazar.
        report_rows verilirse bu dosyanın kalite satırı eklenir (resume raporu için).
        source_path: gönderim anında saklanan KAYNAK dosya yolu (fmap'ten) — verilirse
        çıktı yolundan geriye hesaplama yapılmaz (bkz. aşağıdaki _orig_cues bloğu)."""
        import hybrid_translate as ht
        output_path = str(Path(output_path).with_suffix(".srt"))  # çıktı her zaman SRT (eski fmap'ler dahil)
        self._log(f"Hybrid batch bekleniyor: {batch_id}", "info")
        self._set_status("Hybrid batch işleniyor...")

        _consecutive_errors = 0
        _MAX_CONSECUTIVE_ERRORS = 10
        terminal = False   # OpenAI batch'i terminal duruma ulaştı mı (kurtarma silinebilir mi)
        while not self._stop_flag:
            try:
                b         = client.batches.retrieve(batch_id)
                counts    = b.request_counts
                total     = counts.total     or 1
                completed = counts.completed or 0
                failed    = counts.failed    or 0
                pct       = int(completed / total * 100)
                self._set_progress(pct)
                self._set_stat(self.stat_done_var, str(completed))
                self._set_stat(self.stat_fail_var, str(failed))
                self._set_status(f"{b.status}  {completed}/{total}  ({pct}%)")
                self._log(f"{b.status} — {completed}/{total}  hatalı:{failed}", "")

                if b.status == "completed":
                    self._unregister_batch(batch_id)
                    terminal = True
                    self._set_eta("")
                    self._log("Tamamlandı, indiriliyor...", "ok")
                    if b.output_file_id:
                        try:
                            ht.save_results(openai_key, b.output_file_id, file_map,
                                            output_path, self._log,
                                            token_callback=self._update_batch_tokens,
                                            base_url=str(getattr(client, "base_url", "")))
                        except Exception as e:
                            self._log(f"Sonuçlar kaydedilemedi: {e}", "err")
                    else:
                        self._log("Batch çıktısı boş (hiçbir istek başarılı olamadı).", "err")
                    if b.error_file_id:
                        self._show_errors(client, b.error_file_id)
                    # Post-processing: Consistency Sweep + Critic Pass + Polish Pass + SDH
                    if True:  # consistency sweep always runs; others are gated
                        try:
                            tgt   = self.tgt_var.get()
                            pp    = list(parse_srt(output_path))
                            _raw_backup_blocks = list(pp)   # kalite geçişleri öncesi ham çeviri (yedek)
                            
                            # Kaynak cue'ları yükle (consistency sweep + etiket geri yükleme +
                            # [HATA] işaretleme + TM/QC bunlara bağlı; bulunamazsa hepsi atlanır).
                            # ÖNCE fmap'te saklanan kaynak yolu kullanılır. Geriye-hesaplama
                            # (çıktı yolundan kaynağı türetme) ARTIK GEÇERLİ DEĞİL: çıktı-klasörü
                            # kuralları araya alt-klasör koyuyor (Kural 2: <çıktı>/<ad>/<ad>.srt,
                            # Kural 1: <girdi>/ÇIKTI/...) ve çıktı her zaman .srt iken kaynak
                            # .vtt/.ass olabilir. Yalnızca source_path'i OLMAYAN ESKİ fmap'ler
                            # için eski yönteme düşülür.
                            _orig_cues = None
                            _src_path = None
                            try:
                                if source_path and Path(source_path).exists():
                                    _src_path = Path(source_path)
                                else:
                                    _input_dir = self.input_var.get()
                                    _out_p     = Path(output_path)
                                    _out_dir   = self.output_var.get()
                                    _rel       = _out_p.relative_to(_out_dir) if _out_dir else _out_p.name
                                    _cand      = Path(_input_dir) / _rel
                                    if _cand.exists():
                                        _src_path = _cand
                                if _src_path is not None:
                                    _orig_cues = ht.load_subtitle(str(_src_path))
                            except Exception:
                                pass
                            if _orig_cues is None:
                                self._log("Resume: kaynak dosya bulunamadı — etiket geri yükleme / "
                                          "[HATA] işaretleme ve TM/QC bu dosyada atlanacak", "warn")
                            if pp:
                                self._set_status("Consistency sweep...")
                                pp, _cons_fixes = ht.consistency_sweep(_orig_cues, pp, log_fn=self._log)
                            else:
                                _cons_fixes = 0
                            _pre_pass = {str(b[0]): b[2] for b in pp}
                            _pass_trace = {}
                            _pass_history = {}
                            _qc_fixes = 0
                            _qc_auto_fixes = 0
                            # Bağlam incelemesi — resume/hybrid-batch de chained-context'ten yoksun.
                            # _orig_cues truthy ⟹ _src_path geçerli+mevcut (yukarıda öyle set edildi).
                            if (self.review_pass_var.get() and pp and _orig_cues
                                    and not self._stop_flag):
                                try:
                                    self._set_status("Bağlam incelemesi...")
                                    self._log(f"Bağlam incelemesi başlıyor ({len(pp)} satır)...", "info")
                                    _before_rev = list(pp)
                                    pp, _rev_fixes = self._review_pass(
                                        str(_src_path), pp, self._main_model_name(), tgt)
                                    _record_pass_change(_pass_trace, "Review", _before_rev, pp, _pass_history)
                                except Exception as e:
                                    self._log(f"Bağlam incelemesi hatası: {e}", "warn")
                            _analysis_result = None
                            if _orig_cues:
                                try:
                                    _analysis_result = ht.load_context_cache(
                                        str(_src_path),
                                        expected_target=tgt,
                                        expected_analysis_depth=self.analysis_depth_var.get(),
                                    )
                                except Exception:
                                    pass
                            if self.critic_var.get() and pp:
                                self._set_status("Critic Pass...")
                                self._log(f"Critic Pass başlıyor ({len(pp)} satır)...", "info")
                                _before_pass = list(pp)
                                _critic_change_log = []
                                pp = ht.critic_pass_with_helper(
                                    cues=_orig_cues, tr_blocks=pp,
                                    helper_api_key=self._helper_api_key("critic"),
                                    helper_url=self._helper_api_base_url("critic"),
                                    helper_model=self._helper_api_model("critic"),
                                    tgt_lang=tgt, log_fn=self._log,
                                    analysis_result=_analysis_result,
                                    change_log=_critic_change_log)
                                _record_pass_change(_pass_trace, "Critic", _before_pass, pp, _pass_history)
                                self._write_critic_change_report(output_path, _critic_change_log)
                            if self.polish_var.get() and pp:
                                self._set_status("Doğallaştırma...")
                                _before_pass = list(pp)
                                pp = self._polish_pass(pp, tgt, self._helper_api_key("polish"), self._helper_api_base_url("polish"), self._helper_api_model("polish"),
                                                       src_map=_src_map_from_cues(_orig_cues),
                                                       analysis_result=_analysis_result)
                                _record_pass_change(_pass_trace, "Polish", _before_pass, pp, _pass_history)
                            if self.native_var.get() and pp:
                                self._set_status("Native Okuyucu...")
                                _before_pass = list(pp)
                                pp = ht.native_reader_pass(
                                    tr_blocks=pp, helper_api_key=self._helper_api_key("critic"), helper_url=self._helper_api_base_url("critic"), helper_model=self._helper_api_model("critic"), tgt_lang=tgt, log_fn=self._log,
                                    token_callback=self._update_tokens,
                                    src_map=_src_map_from_cues(_orig_cues))
                                _record_pass_change(_pass_trace, "Native", _before_pass, pp, _pass_history)
                            if pp and (self.critic_var.get() or self.polish_var.get() or self.native_var.get()):
                                _before_pass = list(pp)
                                pp, _final_cons_fixes = ht.final_consistency_sweep(_orig_cues, pp, log_fn=self._log)
                                if _final_cons_fixes:
                                    _record_pass_change(_pass_trace, "Final-Consistency", _before_pass, pp, _pass_history)
                            _before_pass = list(pp)
                            pp = self._maybe_condense(
                                pp,
                                self._helper_api_key("analysis"),
                                self._helper_api_base_url("analysis"),
                                self._helper_api_model("analysis"),
                                tgt,
                                src_map=_src_map_from_cues(_orig_cues))
                            _record_pass_change(_pass_trace, "Condense", _before_pass, pp, _pass_history)
                            if self.clean_sdh_var.get():
                                _before_pass = list(pp)
                                pp = clean_sdh(pp, src_map=_src_map_from_cues(_orig_cues), source_driven=True)
                                _record_pass_change(_pass_trace, "SDH", _before_pass, pp, _pass_history)
                            if self.linebreak_var.get() and pp:
                                _before_pass = list(pp)
                                pp = apply_line_breaks(pp)
                                _record_pass_change(_pass_trace, "Line-break", _before_pass, pp, _pass_history)
                            if self.qc_var.get() and pp and _orig_cues:
                                self._set_status("QC kontrolü...")
                                _issues = ht.quality_check_with_helper(
                                    cues=_orig_cues, tr_blocks=pp,
                                    helper_api_key=self._helper_api_key("qc"), helper_url=self._helper_api_base_url("qc"), helper_model=self._helper_api_model("qc"), tgt_lang=tgt, log_fn=self._log)
                                if _issues:
                                    _auto_qc, _review_qc = ht.split_qc_issues_for_review(_issues)
                                    if _auto_qc:
                                        _before_pass = list(pp)
                                        self._log(f"QC auto: {len(_auto_qc)} düşük/orta severity düzeltme uygulanıyor", "info")
                                        pp = ht.qc_auto_fix(
                                            issues=_auto_qc, tr_blocks=pp,
                                            helper_api_key=self._helper_api_key("qc"),
                                            model=self._helper_api_model("qc"),
                                            tgt_lang=tgt, base_url=self._helper_api_base_url("qc"), log_fn=self._log)
                                        _n_auto = _record_pass_change(_pass_trace, "QC auto", _before_pass, pp, _pass_history)
                                        _qc_fixes += _n_auto
                                        _qc_auto_fixes += _n_auto
                                    _appr = []
                                    status = "completed"
                                    if _review_qc:
                                        _qcev = threading.Event()
                                        _post_ui(self, self._show_qc_dialog, _review_qc, _appr, _qcev)
                                        status = self._wait_for_dialog_event(_qcev, timeout=300)
                                        if status == "stopped":
                                            self._set_status("QC: durduruldu")
                                        elif status == "timeout":
                                            self._set_status("QC: süre aşımı")
                                    if _appr and status == "completed":
                                        _before_pass = list(pp)
                                        pp = ht.qc_auto_fix(
                                            issues=_appr, tr_blocks=pp,
                                            helper_api_key=self._helper_api_key("qc"),
                                            model=self._helper_api_model("qc"),
                                            tgt_lang=tgt, base_url=self._helper_api_base_url("qc"), log_fn=self._log)
                                        _n_approved = _record_pass_change(_pass_trace, "QC", _before_pass, pp, _pass_history)
                                        _qc_fixes += _n_approved
                            # CPS uyarısı — diğer akışlarla paritede
                            _log_cps_warning(pp, self._log)
                            # [HATA] satırlarını görünür işaretle bırak + etiketleri geri uygula
                            # (_orig_cues None olabilir — o durumda yardımcı dokunmaz)
                            try:
                                _raw_map = _raw_src_map_from_cues(_orig_cues)
                                pp, _ = _fill_hata_with_source(pp, _raw_map, log_fn=self._log)
                                pp = _restore_tags_blocks(pp, _raw_map)
                            except Exception:
                                pass
                            if (getattr(self, "term_normalize_var", None) and self.term_normalize_var.get()
                                    and _orig_cues):
                                try:
                                    pp, _ = _normalize_mixed_terms(
                                        pp, {str(c.index): _clean_src(c.text) for c in _orig_cues},
                                        self._helper_api_key("polish"), self._helper_api_base_url("polish"),
                                        self._helper_api_model("polish"), log_fn=self._log)
                                except Exception:
                                    pass
                            write_srt(output_path, self._maybe_merge_cues(pp))
                            self._save_raw_backup(output_path, _raw_backup_blocks, _raw_map)
                            # Kalite taraması + TM kaydı (diğer akışlarla paritede; kaynak gerekli)
                            if _orig_cues:
                                _src_map = {str(c.index): _clean_src(c.text) for c in _orig_cues}
                                try:
                                    scan_translation_quality(str(_src_path), pp,
                                                             log_fn=self._log, src_clean_map=_src_map)
                                except Exception:
                                    pass
                                self._store_tm_pairs(pp, _src_map, self._main_model_name(), tgt)
                                self._maybe_backtranslation_check(output_path, _src_map, pp)
                            if report_rows is not None:
                                _hn, _cn = _count_hata_cps(pp)
                                _cps_avg, _cps_max = _cps_stats(pp)
                                _pass_fix = sum(
                                    1 for b in pp
                                    if _pre_pass.get(str(b[0])) is not None
                                    and _clean_src(_pre_pass[str(b[0])]) != _clean_src(b[2]))
                                _pc = "+".join(k for k, v in [("critic",self.critic_var.get()),("polish",self.polish_var.get()),("native",self.native_var.get()),("QC",self.qc_var.get()),("condense",self.condense_var.get()),("review",self.review_pass_var.get()),("termnorm",self.term_normalize_var.get()),("2wave",self.twowave_var.get()),("SDH",self.clean_sdh_var.get()),("linebreak",self.linebreak_var.get())] if v)
                                report_rows.append({"name": Path(output_path).name,
                                                    "total": len(pp), "hata": _hn, "cps": _cn,
                                                    "cps_avg": _cps_avg, "cps_max": _cps_max,
                                                    "cons": _cons_fixes,
                                                    "pass_fix": _pass_fix,
                                                    "qc_auto": _qc_auto_fixes,
                                                    "qc": _qc_fixes,
                                                    "pass_trace": _pass_trace,
                                                    "pass_history": _pass_history,
                                                    "pass_coverage": _pc,
                                                    "tm_hits": self._tm.hit_count_session()})
                        except Exception as ppe:
                            self._log_exc(f"Post-processing [{Path(output_path).name}]", ppe)
                    break
                elif b.status in ("failed","expired","cancelled"):
                    self._unregister_batch(batch_id)
                    terminal = True
                    self._set_eta("")
                    self._log(f"Batch başarısız: {b.status}", "err")
                    if b.error_file_id:
                        self._show_errors(client, b.error_file_id)
                    break
                _consecutive_errors = 0  # başarılı sorgu — sıfırla
            except Exception as e:
                _consecutive_errors += 1
                self._log_exc("Hata", e)
                if _consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                    self._log(f"Arka arkaya {_MAX_CONSECUTIVE_ERRORS} hata — polling durduruldu "
                              f"(batch hâlâ sunucuda olabilir; kurtarma kaydı KORUNUR).", "err")
                    self._unregister_batch(batch_id)   # #7: bayat aktif-batch kaydını temizle
                    break   # terminal=False kalır → kurtarma korunur (Resume tekrar dener)

            for _ in range(30):
                if self._stop_flag:
                    break
                time.sleep(1)

        if is_last:
            self._set_running(False)
            self._set_status("Tamamlandı." if not self._stop_flag else "Durduruldu.")
        return terminal

    def _wait_batch(self, client, batch_id, file_map, output_dir, requests_list=None, is_last=True):
        self._log(f"Bekleniyor: {batch_id}", "info")
        self._set_status("Batch işleniyor...")
        start_ts = None
        _consecutive_errors = 0
        _MAX_CONSECUTIVE_ERRORS = 10
        batch_raw_map = {}
        terminal = False   # OpenAI batch'i TERMINAL duruma ulaştı mı (completed/failed/expired/
        #                    cancelled)? Yalnızca terminal ise kurtarma kaydı silinebilir.

        while not self._stop_flag:
            try:
                b         = client.batches.retrieve(batch_id)
                counts    = b.request_counts
                total     = counts.total     or 1
                completed = counts.completed or 0
                failed    = counts.failed    or 0
                pct       = int(completed / total * 100)
                self._set_progress(pct)
                self._set_stat(self.stat_done_var, str(completed))
                self._set_stat(self.stat_fail_var, str(failed))
                self._set_status(f"{b.status}  {completed}/{total}  ({pct}%)")
                self._log(f"{b.status} — {completed}/{total}  hatalı:{failed}", "")

                if b.status == "in_progress" and start_ts is None:
                    start_ts = time.time()
                if start_ts and completed > 0:
                    eta_s = int((time.time()-start_ts) / completed * (total-completed))
                    self._set_eta(f"ETA ~{eta_s//60}:{eta_s%60:02d}")

                if b.status == "completed":
                    self._unregister_batch(batch_id)
                    terminal = True
                    self._set_eta("")
                    if b.output_file_id:
                        self._log("Tamamlandı, indiriliyor...", "ok")
                        batch_raw_map = self._save_batch_results(client, b.output_file_id)
                    else:
                        self._log("Batch çıktısı boş (hiçbir istek başarılı olamadı).", "err")
                    if b.error_file_id:
                        self._show_errors(client, b.error_file_id)
                    break
                elif b.status in ("failed","expired","cancelled"):
                    self._unregister_batch(batch_id)
                    terminal = True
                    self._set_eta("")
                    self._log(f"Batch başarısız: {b.status}", "err")
                    if b.error_file_id:
                        self._show_errors(client, b.error_file_id)
                    break
                _consecutive_errors = 0  # başarılı sorgu — sıfırla
            except Exception as e:
                _consecutive_errors += 1
                self._log_exc("Hata", e)
                if _consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                    self._log(f"Arka arkaya {_MAX_CONSECUTIVE_ERRORS} hata — polling durduruldu "
                              f"(batch hâlâ sunucuda olabilir; kurtarma kaydı KORUNUR).", "err")
                    self._unregister_batch(batch_id)   # #7: bayat aktif-batch kaydını temizle
                    break   # terminal=False kalır → kurtarma kaydı silinmez (Resume tekrar dener)

            for _ in range(30):
                if self._stop_flag:
                    break
                time.sleep(1)

        if is_last:
            self._set_running(False)
            self._set_status("Tamamlandı." if not self._stop_flag else "Durduruldu.")

        return batch_raw_map, terminal

    def _save_batch_results(self, client, output_file_id):
        content   = client.files.content(output_file_id).text
        raw_map   = {}
        token_sum = 0
        for line in content.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            # Tek bozuk JSONL satırı TÜM batch'i kaybetmesin (parse hatası → o satırı atla,
            # düzgün satırlar korunur). None content / boş choices da güvenli ele alınır.
            try:
                res = json.loads(line)
                cid = res["custom_id"]
                if res.get("error"):
                    continue
                body    = res["response"]["body"]
                choices = body.get("choices") or []
                fr = choices[0].get("finish_reason", "") if choices else ""
                if fr == "content_filter":
                    self._log(f"{cid}: yanıt kesildi (finish_reason={fr})", "err")
                    continue
                raw     = ((choices[0].get("message") or {}).get("content") or "").strip() if choices else ""
                if fr == "length" and raw:
                    self._log(f"{cid}: yanıt kesildi; tamamlanan JSON öğeleri korunuyor", "warn")
                if not raw:
                    self._log(f"{cid}: boş yanıt", "err")
                else:
                    raw_map[cid] = raw
                if body.get("usage"):
                    token_sum += body["usage"].get("total_tokens", 0)
            except Exception as e:
                self._log(f"JSONL satırı atlanıyor (parse hatası): {e}", "warn")
                continue
        self._update_batch_tokens(token_sum)   # Batch API %50 indirimli
        return raw_map

    def _write_results(self, raw_map, file_map, output_dir, openai_key=None, src=None,
                       output_paths=None):
        import hybrid_translate as ht
        input_dir  = self.input_var.get()
        file_blocks = collect_results(raw_map, file_map, log_fn=self._log)
        total_warnings = 0
        model_name = self._main_model_name()
        _tgt_lang  = self.tgt_var.get()
        report_rows = []
        _last_src_cues = []   # diff penceresi için son dosyanın kaynak blokları
        _written_files = []
        _skipped_files = []
        _failed_files = []
        for fi, (fp, blocks_dict) in enumerate(file_blocks.items()):
            if self._is_queued_file_removed(fp):
                _skipped_files.append(fp)
                continue
            saved_out = (output_paths or {}).get(fp) or (output_paths or {}).get(str(fp))
            out_path = (Path(saved_out) if saved_out else
                        _resolve_output_path(input_dir, output_dir, fp,
                                             same_folder=self.same_folder_var.get()))
            sorted_blocks = [blocks_dict[k] for k in sorted(blocks_dict, key=lambda k: (0, int(k)) if str(k).isdigit() else (1, str(k)))]
            _raw_backup_blocks = list(sorted_blocks)   # kalite geçişleri öncesi ham çeviri (yedek)
            _cons_fixes, _rev_fixes = 0, 0
            _pass_trace = {}
            _pass_history = {}
            # Kaynağı DOSYA BAŞINA BİR KEZ parse et; tüm adımlar bunu paylaşır
            try:
                _src_cues = self._cached_blocks_for(fp) or list(parse_subtitle(fp))
            except Exception:
                _src_cues = []
            _last_src_cues = _src_cues
            _raw_map   = _raw_src_map_from_cues(_src_cues)   # ham (etiketli) kaynak
            src_blocks = {str(idx): _clean_src(text) for idx, ts, text in _src_cues}  # etiketsiz
            _analysis_result = None
            try:
                _analysis_result = ht.load_context_cache(
                    fp, expected_target=_tgt_lang,
                    expected_analysis_depth=self.analysis_depth_var.get())
            except Exception:
                _analysis_result = None
            # Tekrarlanan kaynak cümlelerin çevirilerini çoğunluğa göre normalize et
            try:
                sorted_blocks, _cons_fixes = ht.consistency_sweep(_src_cues, sorted_blocks, log_fn=self._log)
            except Exception:
                pass
            # Bağlam incelemesi — Batch'te zincirleme bağlam yoktur, bu geçiş telafi eder
            if (self.review_pass_var.get() and self.mode_var.get() == "batch"
                    and sorted_blocks and not self._stop_flag):
                self._set_status(f"Bağlam incelemesi: {Path(fp).name}")
                self._log(f"Bağlam incelemesi başlıyor ({len(sorted_blocks)} satır)...", "info")
                _before_pass = list(sorted_blocks)
                sorted_blocks, _rev_fixes = self._review_pass(fp, sorted_blocks, model_name, _tgt_lang)
                _record_pass_change(_pass_trace, "Review", _before_pass, sorted_blocks, _pass_history)
            # ── Kalite geçişleri (tüm modlarda, toggle açıksa) ──────────────
            if self.critic_var.get() and sorted_blocks and not self._stop_flag:
                try:
                    self._log(f"Critic Pass başlıyor ({len(sorted_blocks)} satır)...", "info")
                    _before_pass = list(sorted_blocks)
                    _critic_change_log = []
                    sorted_blocks = ht.critic_pass_with_helper(
                        cues=_src_cues, tr_blocks=sorted_blocks,
                        helper_api_key=self._helper_api_key("critic"),
                        helper_url=self._helper_api_base_url("critic"),
                        helper_model=self._helper_api_model("critic"),
                        tgt_lang=_tgt_lang, log_fn=self._log,
                        analysis_result=_analysis_result,
                        change_log=_critic_change_log)
                    _record_pass_change(_pass_trace, "Critic", _before_pass, sorted_blocks, _pass_history)
                    self._write_critic_change_report(out_path, _critic_change_log)
                except Exception as e:
                    self._log(f"Critic Pass hatası: {e}", "warn")
            if self.polish_var.get() and sorted_blocks and not self._stop_flag:
                try:
                    _before_pass = list(sorted_blocks)
                    sorted_blocks = self._polish_pass(
                        sorted_blocks, _tgt_lang,
                        self._helper_api_key("polish"), self._helper_api_base_url("polish"),
                        self._helper_api_model("polish"), src_map=src_blocks,
                        analysis_result=_analysis_result)
                    _record_pass_change(_pass_trace, "Polish", _before_pass, sorted_blocks, _pass_history)
                except Exception as e:
                    self._log(f"Polish Pass hatası: {e}", "warn")
            if self.native_var.get() and sorted_blocks and not self._stop_flag:
                try:
                    _before_pass = list(sorted_blocks)
                    sorted_blocks = ht.native_reader_pass(
                        tr_blocks=sorted_blocks,
                        helper_api_key=self._helper_api_key("critic"),
                        helper_url=self._helper_api_base_url("critic"),
                        helper_model=self._helper_api_model("critic"),
                        tgt_lang=_tgt_lang, log_fn=self._log,
                        analysis_result=_analysis_result,
                        src_map=src_blocks)
                    _record_pass_change(_pass_trace, "Native", _before_pass, sorted_blocks, _pass_history)
                except Exception as e:
                    self._log(f"Native Pass hatası: {e}", "warn")
            if sorted_blocks and not self._stop_flag and (self.critic_var.get() or self.polish_var.get() or self.native_var.get()):
                try:
                    _before_pass = list(sorted_blocks)
                    sorted_blocks, _final_cons_fixes = ht.final_consistency_sweep(_src_cues, sorted_blocks, log_fn=self._log)
                    if _final_cons_fixes:
                        _record_pass_change(_pass_trace, "Final-Consistency", _before_pass, sorted_blocks, _pass_history)
                except Exception as e:
                    self._log(f"Final consistency sweep hatası: {e}", "warn")
            if sorted_blocks and not self._stop_flag:
                _before_pass = list(sorted_blocks)
                sorted_blocks = self._maybe_condense(
                    sorted_blocks, self._helper_api_key("qc"),
                    self._helper_api_base_url("qc"), self._helper_api_model("qc"), _tgt_lang, src_map=src_blocks)
                _record_pass_change(_pass_trace, "Condense", _before_pass, sorted_blocks, _pass_history)
            if self.clean_sdh_var.get():
                _before_pass = list(sorted_blocks)
                # src_map=src_blocks: sync/batch akışları (bu fonksiyon) eskiden clean_sdh'ye
                # kaynak GEÇMİYORDU (bkz. plans/sdh-kaynak-gutlu-temizlik-brief.md Adım 3) —
                # hem kaynak-güdümlü tespiti hem de boş-cue güvenlik ağını (_src_is_real_dialogue)
                # etkinleştirmek için diğer akışlardaki gibi burada da geçiyoruz.
                sorted_blocks = clean_sdh(sorted_blocks, src_map=src_blocks, source_driven=True)
                _record_pass_change(_pass_trace, "SDH", _before_pass, sorted_blocks, _pass_history)
            if self.linebreak_var.get() and sorted_blocks:
                _before_pass = list(sorted_blocks)
                sorted_blocks = apply_line_breaks(sorted_blocks)
                _record_pass_change(_pass_trace, "Line-break", _before_pass, sorted_blocks, _pass_history)
            if self.qc_var.get() and sorted_blocks and not self._stop_flag:
                try:
                    _before_pass = list(sorted_blocks)
                    sorted_blocks = self._run_quality_check_inline(
                        str(out_path), _src_cues, sorted_blocks,
                        self._helper_api_key("qc"), self._helper_api_base_url("qc"),
                        self._helper_api_model("qc"), _tgt_lang,
                        analysis_result=_analysis_result)
                    _record_pass_change(_pass_trace, "QC", _before_pass, sorted_blocks, _pass_history)
                except Exception as e:
                    self._log(f"QC hatası: {e}", "warn")
            # Çevrilemeyen satırları sync ile onarma denemesi
            try:
                if openai_key:
                    _repair_client = OpenAI(api_key=openai_key, base_url=self._main_api_base_url() or None)
                    sorted_blocks, _n_repaired = _repair_untranslated_sync(
                        sorted_blocks, _raw_map, _repair_client,
                        src_lang=src or self.src_var.get(), tgt_lang=_tgt_lang,
                        model=self._main_model_name(),
                        schema=self._get_schema(), profanity=self.profanity_var.get(),
                        log_fn=self._log, token_cb=self._update_tokens)
            except Exception as e:
                self._log(f"Onarım geçişi atlandı: {e}", "warn")
            # CPS uyarısı — sync-hybrid ile paritede (düz-batch loglarında da görünsün)
            _log_cps_warning(sorted_blocks, self._log)
            # [HATA] satırlarını görünür işaretle bırak + etiketleri geri uygula
            _n_filled = 0
            try:
                sorted_blocks, _n_filled = _fill_hata_with_source(sorted_blocks, _raw_map, log_fn=self._log)
                sorted_blocks = _restore_tags_blocks(sorted_blocks, _raw_map)
            except Exception:
                pass
            if getattr(self, "term_normalize_var", None) and self.term_normalize_var.get():
                try:
                    sorted_blocks, _ = _normalize_mixed_terms(
                        sorted_blocks, src_blocks,
                        self._helper_api_key("polish"), self._helper_api_base_url("polish"),
                        self._helper_api_model("polish"), log_fn=self._log)
                except Exception:
                    pass
            write_srt(out_path, self._maybe_merge_cues(sorted_blocks))
            self._log(f"Kaydedildi: {out_path}", "ok")
            self._save_raw_backup(out_path, _raw_backup_blocks, _raw_map)
            # Post-write quality scan (önceden parse edilen kaynağı kullanır — disk okumaz)
            w = scan_translation_quality(fp, sorted_blocks, log_fn=self._log,
                                         src_clean_map=src_blocks)
            total_warnings += w
            self._maybe_backtranslation_check(out_path, src_blocks, sorted_blocks)
            # Rapor satırı: [HATA] (kalan + işaretlenen) ve CPS aşımı sayıları
            _hata_n, _cps_n = _count_hata_cps(sorted_blocks)
            _cps_avg, _cps_max = _cps_stats(sorted_blocks)
            _pc = "+".join(k for k, v in [("critic",self.critic_var.get()),("polish",self.polish_var.get()),("native",self.native_var.get()),("QC",self.qc_var.get()),("condense",self.condense_var.get()),("review",self.review_pass_var.get()),("termnorm",self.term_normalize_var.get()),("2wave",self.twowave_var.get()),("SDH",self.clean_sdh_var.get()),("linebreak",self.linebreak_var.get())] if v)
            report_rows.append({
                "name": Path(fp).name, "total": len(sorted_blocks),
                "hata": _hata_n + _n_filled, "cps": _cps_n,
                "cps_avg": _cps_avg, "cps_max": _cps_max,
                "cons": _cons_fixes, "rev": _rev_fixes, "warn": w,
                "pass_trace": _pass_trace,
                "pass_history": _pass_history,
                "pass_coverage": _pc,
                "tm_hits": self._tm.hit_count_session(),
            })
            # TM kaydı (ortak yardımcı)
            self._store_tm_pairs(sorted_blocks, src_blocks, model_name, _tgt_lang)
            # Auto-Glossary (düz sync/batch'te de) — Cue nesnesi gerektiğinden kaynağı
            # load_subtitle ile yükle (_src_cues tuple olabilir; build_glossary c.text ister)
            if self.auto_glossary_var.get():
                try:
                    self._run_auto_glossary(ht.load_subtitle(fp), sorted_blocks, fp)
                except Exception as _ag_e:
                    self._log(f"Auto-Glossary atlandı: {_ag_e}", "warn")
            _written_files.append(fp)
            if self._wait_between_files(fi, len(file_blocks), Path(fp).name) == "stopped":
                break
        # ── Kalite Raporu (ceviri_raporu.txt) ────────────────────────────────
        _report_path = self._save_quality_report(report_rows, output_dir)
        total_candidate = len(file_blocks)
        summary = summarize_file_outcomes(
            _written_files, _failed_files, _skipped_files, total_files=total_candidate, stop_flag=self._stop_flag
        )
        warn_txt = f"  ({total_warnings} kalite uyarısı)" if total_warnings else ""
        if not summary["is_full_success"]:
            self._log(f"\n{summary['summary_text']} → {output_dir}{warn_txt}", "warn")
            if not self._stop_flag and summary["completed_count"] > 0:
                self._notify(summary["title_text"], f"{summary['summary_text']} → {output_dir}")
            return summary["is_recovery_complete"]
        self._log(f"\n{summary['summary_text']} → {output_dir}{warn_txt}", "ok")
        self._notify(summary["title_text"], f"{summary['summary_text']} → {output_dir}")
        # Diff penceresi için son dosyanın sonuçlarını hazırla (döngüde parse edilen
        # kaynağı yeniden kullan — tekrar disk okuması yok)
        _last_fp    = _written_files[-1] if _written_files else None
        _last_orig  = _last_src_cues if _last_fp else []
        _last_trans = [file_blocks[_last_fp][k] for k in sorted(
            file_blocks[_last_fp],
            key=lambda k: (0, int(k)) if str(k).isdigit() else (1, str(k))
        )] if _last_fp else []
        def _show_done():
            _rapor_line = "\nRapor: ceviri_raporu.txt\n" if _report_path else "\n"
            ans = messagebox.askyesno(
                summary["title_text"],
                f"{summary['summary_text']}!\n\nKonum: {output_dir}{_rapor_line}\n"
                f"Çeviriyi incelemek ister misiniz?")
            if ans and _last_orig and _last_trans:
                fname = Path(_last_fp).name if _last_fp else ""
                orig_dict = {str(idx): text for idx, ts, text in _last_orig}
                pairs = []
                for idx, ts, tr_t in _last_trans[:120]:
                    src_t = orig_dict.get(str(idx), "")
                    pairs.append((_clean_src(src_t), tr_t))
                self._show_diff_dialog(pairs, fname, output_dir)
        try:
            _post_ui(self, _show_done)
        except Exception:
            pass
        return True

    # ── Post-translation Diff Dialog ──────────────────────────────────────────
    def _show_diff_dialog(self, pairs: list, fname: str, output_dir: str):
        """Kaynak / Çeviri yan yana diff penceresi. Çeviri sonrası inceleme içindir."""
        dlg = ctk.CTkToplevel(self)
        dlg.title(f"📋 Çeviri İnceleme — {fname}")
        dlg.geometry("1000x680")
        dlg.configure(fg_color=BG)
        dlg.lift()
        dlg.focus_force()

        # Üst başlık
        hdr = ctk.CTkFrame(dlg, fg_color=ACCENT, corner_radius=10, height=50)
        hdr.pack(fill="x", padx=12, pady=(12, 4))
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr,
                     text=f"📋  {fname}  —  {len(pairs)} satır önizleme",
                     font=ctk.CTkFont("Segoe UI", 13, "bold"),
                     text_color="white").pack(side="left", padx=14)
        ctk.CTkLabel(hdr,
                     text=f"Çıkış: {output_dir}",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color="#dde").pack(side="right", padx=14)

        # Sütun başlıkları
        col_hdr = ctk.CTkFrame(dlg, fg_color="transparent")
        col_hdr.pack(fill="x", padx=16, pady=(4, 0))
        col_hdr.grid_columnconfigure((0, 1), weight=1)
        for col_i, lbl_txt in enumerate(["KAYNAK", "ÇEVİRİ"]):
            ctk.CTkLabel(col_hdr, text=lbl_txt,
                         font=ctk.CTkFont("Segoe UI", 11, "bold"),
                         text_color=FG2).grid(row=0, column=col_i, sticky="w", padx=8)

        # İçerik
        sf = ctk.CTkScrollableFrame(dlg, fg_color=PANEL, corner_radius=8)
        sf.pack(fill="both", expand=True, padx=12, pady=4)
        sf.grid_columnconfigure((0, 1), weight=1)

        for i, (src_t, tr_t) in enumerate(pairs):
            bg = CARD if i % 2 == 0 else PANEL
            # Hata satırlarını kırmızıyla, normal çevirileri yeşille göster
            tr_color = RED if tr_t.startswith("[HATA") else GREEN
            # Uzun metin için truncate
            src_disp = src_t[:200] + "…" if len(src_t) > 200 else src_t
            tr_disp  = tr_t[:200] + "…" if len(tr_t) > 200 else tr_t
            for col_i, (text, color) in enumerate([(src_disp, FG), (tr_disp, tr_color)]):
                ctk.CTkLabel(sf, text=text,
                             font=ctk.CTkFont("Segoe UI", 11),
                             text_color=color,
                             fg_color=bg, corner_radius=4,
                             wraplength=440, justify="left",
                             anchor="w").grid(
                    row=i, column=col_i, sticky="ew", padx=6, pady=2, ipady=3)

        # Alt butonlar
        btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_fr.pack(fill="x", padx=12, pady=(4, 12))
        btn_fr.grid_columnconfigure((0, 1, 2), weight=1)

        def _open_folder():
            import subprocess
            try:
                subprocess.Popen(["explorer", output_dir])
            except Exception:
                pass

        ctk.CTkButton(btn_fr, text="📂  Klasörü Aç",
                      fg_color=CARD, hover_color=BORDER,
                      command=_open_folder).grid(row=0, column=0, padx=4, sticky="ew")
        ctk.CTkButton(btn_fr, text="▶  Yeni Çeviri Başlat",
                      fg_color=ACCENT, hover_color="#5a4fd1",
                      command=lambda: (dlg.destroy(), self._start())).grid(row=0, column=1, padx=4, sticky="ew")
        ctk.CTkButton(btn_fr, text="✕  Kapat",
                      fg_color=CARD, hover_color=BORDER,
                      command=dlg.destroy).grid(row=0, column=2, padx=4, sticky="ew")

    def _show_errors(self, client, error_file_id):
        try:
            for line in client.files.content(error_file_id).text.strip().splitlines()[:5]:
                r = json.loads(line)
                self._log(f"{r.get('custom_id','?')}: {r.get('error',{}).get('message','')}", "err")
        except Exception:
            pass

    def _run_twowave_batches(self, openai_key, requests, fmap, out_path,
                             source_path, output_dir, fname, progress_fn=None) -> bool:
        """İki-dalgalı zincirli batch (B3) — TEK dosya için sıralı submit-wait-submit-wait.

        A dalgasını gönderir, BEKLER, A'nın kuyruk çevirilerini B dalgasının ilk chunk'ına
        prev_tr enjekte eder, B'yi gönderir, bekler, iki çıktıyı out_path'e BİRLEŞİK yazar.
        Başarıda True; başarısızlık/durdurmada False (çağıran dosyayı 'failed' işaretler).

        GÜVENLİK/kurtarma: her dalga ayrı bir out_path (`.wave1of2.srt`/`.wave2of2.srt`) ile
        submit_batch üzerinden batch_id.txt'ye yazılır — çökme olursa standart resume onları
        BAĞIMSIZ batch olarak alır, AYRI dosyalara yazar (birbirini EZMEZ, sessiz bozulma yok;
        kullanıcı temiz sonuç için yeniden çalıştırır). Canlı akışta yazım out_path'e TEK
        seferde birleşik yapılır; başarıda iki dalga da recovery'den temizlenir.
        Chunk çok azsa (bkz. _split_waves) tek batch'e düşer — zincirsiz ama çalışır."""
        import hybrid_translate as ht
        from openai import OpenAI as _OAI
        b_url = self._main_api_base_url()

        wave_a, wave_b = _split_waves(requests)

        def _submit_wait(reqs, this_fmap, this_out):
            bid = ht.submit_batch(openai_key, reqs, self._log, this_fmap, this_out,
                                  source_path=source_path, output_dir=output_dir,
                                  base_url=b_url)
            if not bid:
                return None, None
            self._register_batch(bid, openai_key, b_url)
            oid = ht.wait_for_batch(openai_key, bid, self._log,
                                    stop_flag_fn=lambda: self._stop_flag,
                                    progress_fn=progress_fn, base_url=b_url)
            if not self._stop_flag:
                self._unregister_batch(bid)
            return bid, oid

        # Tek-batch fallback (bölünemeyecek kadar az chunk)
        if not wave_a:
            self._log(f"{fname}: iki-dalga için chunk yetersiz — tek batch (zincirsiz)", "info")
            bid, oid = _submit_wait(requests, fmap, out_path)
            if not bid or oid is None or self._stop_flag:
                return False
            ht.save_results(openai_key, oid, fmap, out_path, self._log,
                            token_callback=self._update_batch_tokens, src_cues=None,
                            base_url=b_url)
            self._clear_batch_recovery([bid])
            return True

        cids_a = {r.get("custom_id") for r in wave_a}
        fmap_a = {c: v for c, v in fmap.items() if c in cids_a}
        fmap_b = {c: v for c, v in fmap.items() if c not in cids_a}
        out_a = str(Path(out_path).with_suffix(".wave1of2.srt"))
        out_b = str(Path(out_path).with_suffix(".wave2of2.srt"))

        # ── A dalgası ─────────────────────────────────────────────────────────
        self._log(f"{fname}: iki-dalgalı — A dalgası ({len(wave_a)} chunk) gönderiliyor", "info")
        bid_a, oid_a = _submit_wait(wave_a, fmap_a, out_a)
        if not bid_a or oid_a is None or self._stop_flag:
            return False

        # A'nın ham çevirisini al → B'ye zincir enjekte et (başarısızsa zincirsiz devam)
        try:
            client = _OAI(api_key=openai_key, base_url=b_url or None)
            raw_a = _raw_map_from_batch_content(client.files.content(oid_a).text)
            wave_b = _chain_waves(wave_a, wave_b, raw_a, fmap_a, max_pairs=self._context_lines)
            self._log(f"{fname}: A tamamlandı → B'ye zincir bağlamı enjekte edildi", "ok")
        except Exception as e:
            self._log(f"{fname}: zincir enjeksiyonu atlandı ({e}) — B zincirsiz devam", "warn")

        # ── B dalgası ─────────────────────────────────────────────────────────
        self._log(f"{fname}: B dalgası ({len(wave_b)} chunk) gönderiliyor", "info")
        bid_b, oid_b = _submit_wait(wave_b, fmap_b, out_b)
        if not bid_b or oid_b is None or self._stop_flag:
            # A bitti ama B alınamadı: A recovery'de kalır (resume .wave1of2.srt'ye alır)
            return False

        # ── Birleşik yazım + recovery temizliği ───────────────────────────────
        ht.save_results(openai_key, [oid_a, oid_b], {**fmap_a, **fmap_b}, out_path,
                        self._log, token_callback=self._update_batch_tokens, src_cues=None,
                        base_url=b_url)
        self._clear_batch_recovery([bid_a, bid_b])
        return True

    # ── Hybrid mod (Batch + gpt-5.4-mini analiz) ──────────────────────────────
    def _run_hybrid(self, openai_key, helper_key, ext_project_path):
        self._block_cache = {}   # önceki çalışmadan kalan cache'i temizle
        self._twowave_pending = {}   # B3: iki-dalgalı dosyaların Faz1'de saklanan istekleri
        import hybrid_translate as ht
        ht.set_project_path(ext_project_path)
        b_url = self._main_api_base_url()
        output_dir  = self.output_var.get()
        src, tgt    = self.src_var.get(), self.tgt_var.get()
        model       = self._main_model_name()
        profanity   = self.profanity_var.get()
        srt_files   = self._get_srt_files()

        if not srt_files:
            self._log("Giriş klasöründe .srt bulunamadı!", "err")
            self._set_running(False)
            return

        n_files   = len(srt_files)
        input_dir = self.input_var.get()
        self._set_stat(self.stat_files_var, str(n_files))

        # ── Batch session: resume tracking ────────────────────────────────────
        session_fp = ht.batch_session_fingerprint(input_dir, output_dir, srt_files, {
            "target": tgt,
            "model": model,
            "style": self.style_var.get(),
            "profanity": profanity,
            "content_type": self.content_type_var.get(),
            "same_folder": bool(self.same_folder_var.get()),
            "chunk_size": self._chunk_size,
            "context_lines": self._context_lines,
            "lookahead_lines": self._lookahead_lines,
        })
        session = ht.create_batch_session(
            input_dir, output_dir, srt_files, fingerprint=session_fp)
        _summary = ht.batch_session_summary(session, srt_files)
        if _summary["completed"] > 0 or _summary["submitted"] > 0:
            self._log(
                f"▶ Oturum bulundu — "
                f"{_summary['completed']} tamamlandı (atlanıyor), "
                f"{_summary['submitted']} beklemede (yeniden bağlanıyor), "
                f"{_summary['pending']} yeni dosya.",
                "ok")
        # ── Oturum özeti ──────────────────────────────────────────────────────

        # ══════════════════════════════════════════════════════════════════════
        # FAZ 1 — Tüm dosyaları analiz et + batch'leri gönder (beklemeden)
        # Böylece program kapansa bile 'Devam Ettir' ile tüm dosyalar alınabilir
        # ══════════════════════════════════════════════════════════════════════
        self._log(f"Faz 1 — {n_files} dosya analiz ediliyor ve batch'ler gönderiliyor...", "info")
        # Each entry: (filepath, fname, out_path, fmap, batch_id, cues, analysis_tuple)
        submitted = []

        for fi, filepath in enumerate(srt_files):
            if self._stop_flag:
                break
            if self._is_queued_file_removed(filepath):
                continue
            fname = Path(filepath).name
            file_status = session["files"].get(str(filepath), {}).get("status", "pending")

            # ── Zaten tamamlanmış dosyaları atla ──────────────────────────────
            if file_status == "completed":
                self._log(f"[{fi+1}/{n_files}] {fname} — ✓ tamamlandı, atlanıyor", "ok")
                self._set_progress(int((fi + 1) / n_files * 40))
                continue

            self._log(f"\n── [{fi+1}/{n_files}] {fname} — Analiz ──", "info")

            try:
                cues = ht.load_subtitle(filepath)
                if not cues:
                    self._log(f"{fname}: geçerli SRT bloğu yok, atlandı", "warn")
                    continue
                self._set_stat(self.stat_blocks_var, str(len(cues)))

                schema_dict = self._get_file_schema(filepath)
                if schema_dict["name"] == "Otomatik":
                    self._log(f"[{fname}] İçerik türü otomatik analiz ediliyor...", "info")
                    try:
                        from openai import OpenAI
                        b_url = self._main_api_base_url()
                        client = OpenAI(api_key=openai_key, base_url=b_url if b_url else None)
                        detected_name = detect_content_type_with_ai(client, cues, model, self._log, token_callback=self._update_tokens, filename=filepath)
                        schema_dict = self._schema_by_name(detected_name)
                    except Exception as e:
                        self._log(f"Otomatik şema tespiti başarısız: {e}", "warn")

                glossary = ht.load_glossary(self._get_file_glossary(filepath))
                glossary = self._merge_schema_glossary(glossary, schema_dict)

                cached = ht.load_context_cache(
                    filepath,
                    expected_target=tgt,
                    expected_analysis_depth=self.analysis_depth_var.get(),
                )
                if cached:
                    context, char_examples, pronoun_map, character_styles, scene_emotions, idiom_map, cultural_refs = cached
                    self._log(f"Önbellek bulundu — analiz atlanıyor ({fname})", "ok")
                else:
                    helper_name = self._helper_display_name("analysis")
                    self._set_status(f"{helper_name} analizi: {fname}")
                    base = fi / n_files

                    def _ap(done, total_c, _b=base):
                        self._set_progress(int((_b + done / (total_c or 1) * 0.4 / n_files) * 100))
                        self._set_status(f"{helper_name} analiz: {done}/{total_c} — {fname}")

                    try:
                        result = ht.analyze_with_helper(
                            cues=cues, helper_api_key=self._helper_api_key("analysis"), helper_url=self._helper_api_base_url("analysis"), helper_model=self._helper_api_model("analysis"),
                            style=self.style_var.get(),
                            source_language=_lang_iso639_1(src),
                            target_language=_lang_iso639_1(tgt),
                            glossary=glossary, log_fn=self._log,
                            stop_flag_fn=lambda: self._stop_flag,
                            progress_fn=_ap,
                            schema=schema_dict,
                            analysis_depth=self.analysis_depth_var.get())
                    except Exception as e:
                        self._log(f"[{fname}] Analiz hatası: {e} — boş bağlamla devam", "warn")
                        result = None
                    if result is None:
                        if self._stop_flag:
                            break
                        else:
                            self._log(f"[{fname}] Analiz başarısız — boş bağlamla batch devam ediyor", "warn")
                            result = ht.empty_analysis_result(_lang_iso639_1(src))
                    context, char_examples, pronoun_map, character_styles, scene_emotions, idiom_map, cultural_refs = result
                    ht.save_context_cache(context, filepath, char_examples, pronoun_map,
                                          character_styles=character_styles,
                                          scene_emotions=scene_emotions,
                                          idiom_map=idiom_map,
                                          cultural_refs=cultural_refs,
                                          target_language=tgt,
                                          analysis_depth=self.analysis_depth_var.get())
                    # Proje hafızasına kaydet
                    if self._pm is not None:
                        try:
                            self._pm.merge_glossary_from_analysis(
                                ht.sanitize_glossary_for_turkish(
                                    dict(context.recurring_terms), target_language=tgt
                                )
                            )
                            self._pm.update_characters([c.name for c in context.characters
                                                        if hasattr(c, 'name')])
                            if pronoun_map:
                                self._pm.update_pronoun_map(pronoun_map)
                        except Exception:
                            pass
                    self._log(f"Analiz tamam — {len(context.recurring_terms)} terim, "
                              f"{len(context.characters)} karakter"
                              + (f", {len(idiom_map)} deyim" if idiom_map else "")
                              + (f", hitap: {pronoun_map}" if pronoun_map else ""), "ok")
                    if context.recurring_terms:
                        self._log(f"Sabit terimler: {context.recurring_terms}", "info")

                analysis_tuple = (context, char_examples, pronoun_map,
                                  character_styles, scene_emotions, idiom_map, cultural_refs)

                # ── Zaten gönderilmiş (submitted) dosyalar için batch yeniden gönderme ──
                if file_status == "submitted":
                    sess_entry = session["files"].get(str(filepath), {})
                    existing_bid = sess_entry.get("batch_id")
                    existing_out = sess_entry.get("out_path", "")
                    if existing_bid:
                        fmap = ht.load_fmap_for_batch(existing_bid)
                        if not fmap:
                            self._log(
                                f"{fname} — batch kurtarma eşlemesi yok/boş ({existing_bid}); "
                                "boş çıktı yazılmayacak.", "err")
                            ht.update_batch_session(session, filepath, "failed")
                            continue
                        self._log(
                            f"{fname} — zaten gönderildi ({existing_bid}), yeniden bağlanılıyor",
                            "info")
                        self._register_batch(existing_bid, openai_key, b_url)
                        submitted.append((filepath, fname, existing_out, fmap,
                                          existing_bid, cues, analysis_tuple))
                        self._set_progress(int((fi + 1) / n_files * 40))
                        continue
                    # batch_id yoksa yeniden gönder (aşağı düş)

                # Batch isteği oluştur + gönder
                # Dizi hafızasını bu bölümün analiziyle güncelle, sonra birikmiş
                # kararları prompt'a ekle (ilk karar kanon)
                self._update_series_memory_from_analysis(filepath, context, pronoun_map)
                system_prompt = ht.build_system_prompt(
                    context, src, tgt,
                    schema=schema_dict,
                    character_examples=char_examples,
                    profanity=profanity,
                    pronoun_map=pronoun_map,
                    character_styles=character_styles,
                    idiom_map=None,   # deyimler per-chunk 'idioms' payload'ında veriliyor — çift enjeksiyon olmasın
                    cultural_refs=cultural_refs,
                )
                system_prompt += self._series_hint_for(filepath)
                if self._pm is not None:
                    system_prompt += self._pm.build_context_hint()   # proje hafızası ipucu (sync/batch ile paritede)
                requests, fmap = ht.build_batch_requests(cues, system_prompt, model,
                                                          chunk_size=self._chunk_size,
                                                          glossary=glossary,
                                                          scene_emotions=scene_emotions,
                                                          idiom_map=idiom_map,
                                                          tm=self._tm,
                                                          tgt_lang=tgt,
                                                          context_lines=self._context_lines,
                                                          lookahead_lines=self._lookahead_lines,
                                                          scene_gap_sec=self._scene_gap_seconds,
                                                          temperature=self._temperature)
                self._log(f"{len(requests)} istek oluşturuldu", "info")

                out_path = str(_resolve_output_path(input_dir, output_dir, filepath,
                                                     same_folder=self.same_folder_var.get()))  # çıktı her zaman SRT

                # ── B3: İki-dalgalı zincirli batch ────────────────────────────
                # Doğası gereği "gönder-bekle-gönder-bekle" olduğundan Faz1'de GÖNDERİLMEZ;
                # istekler saklanıp Faz2'de sıralı işlenir (kapansa 'devam ettir'le kalınan
                # yerden alınamaz — bilinçli takas, bkz. _run_twowave_batches). Yalnız
                # hybrid-batch modunda anlamlı (sync'in zincir makinesi burada).
                if getattr(self, "twowave_var", None) and self.twowave_var.get():
                    self._twowave_pending[str(filepath)] = requests
                    ht.update_batch_session(session, filepath, "pending")
                    submitted.append((filepath, fname, out_path, fmap, "__twowave__", cues, analysis_tuple))
                    self._log(f"[{fname}] İki-dalgalı — Faz 2'de sıralı gönderilecek", "info")
                    self._set_progress(int((fi + 1) / n_files * 40))
                    continue

                self._set_status(f"Batch gönderiliyor: {fname}")
                batch_id = ht.submit_batch(
                    openai_key, requests, self._log, fmap, out_path,
                    source_path=str(filepath), output_dir=output_dir, base_url=b_url)
                if batch_id:
                    self._register_batch(batch_id, openai_key, b_url)
                    ht.update_batch_session(session, filepath, "submitted",
                                            batch_id=batch_id, out_path=out_path)
                    submitted.append((filepath, fname, out_path, fmap, batch_id, cues, analysis_tuple))
                    self._set_progress(int((fi + 1) / n_files * 40))
                else:
                    self._log(f"[{fname}] Batch gönderilemedi, atlanıyor", "err")
                    ht.update_batch_session(session, filepath, "failed")

            except Exception as e:
                self._log(f"[{fname}] Faz-1 hatası: {e} — atlanıyor", "err")
                ht.update_batch_session(session, filepath, "failed")
                continue

        if not submitted:
            self._log("Hiçbir dosya batch'e gönderilemedi.", "err")
            self._set_running(False)
            return

        self._log(f"\n✓ Faz 1 tamamlandı — {len(submitted)}/{n_files} batch gönderildi.", "ok")
        self._log("Program kapatılsa bile '↺ Batch'i Devam Ettir' ile sonuçları alabilirsiniz.", "info")

        # ══════════════════════════════════════════════════════════════════════
        # FAZ 2 — Batch'leri bekle + kaydet + post-process
        # ══════════════════════════════════════════════════════════════════════
        self._log(f"\nFaz 2 — {len(submitted)} batch bekleniyor...", "info")
        n_sub = len(submitted)
        report_rows = []   # kalite raporu satırları (dosya başına)

        for si, (filepath, fname, out_path, fmap, batch_id, cues, analysis_tuple) in enumerate(submitted):
            if self._stop_flag:
                break
            self._log(f"\n── [{si+1}/{n_sub}] {fname} — Batch bekleniyor ──", "info")
            self._set_status(f"Bekleniyor: {fname}")

            def _pfn(completed, total, failed, status, _si=si):
                base_pct = 40 + int(_si / n_sub * 60)
                file_pct = int(completed / (total or 1) * 60 / n_sub)
                self._set_progress(base_pct + file_pct)
                self._set_stat(self.stat_done_var, str(completed))
                self._set_stat(self.stat_fail_var, str(failed))
                self._set_status(f"{status}  {completed}/{total} — {fname}")

            try:
                if batch_id == "__twowave__":
                    # B3: iki-dalgalı sıralı submit-wait-submit-wait, out_path'e birleşik yazar.
                    _tw_reqs = self._twowave_pending.get(str(filepath), [])
                    _ok = self._run_twowave_batches(
                        openai_key, _tw_reqs, fmap, out_path,
                        str(filepath), output_dir, fname, progress_fn=_pfn)
                    if not _ok or self._stop_flag:
                        if not self._stop_flag:
                            self._log(f"[{fname}] İki-dalgalı batch tamamlanamadı.", "err")
                            ht.update_batch_session(session, filepath, "failed")
                        continue
                    # out_path yazıldı — normal post-processing'e aynen düş.
                else:
                    wait_result = ht.wait_for_batch(
                        openai_key, batch_id, self._log,
                        stop_flag_fn=lambda: self._stop_flag,
                        progress_fn=_pfn, base_url=b_url, detailed=True)
                    out_id = wait_result["output_file_id"]
                    # Batch polling sonuçlandı (terminal durum) — iptal listesinden çıkar
                    if not self._stop_flag:
                        self._unregister_batch(batch_id)
                    if out_id is None:
                        if not wait_result["terminal"]:
                            self._log(
                                f"[{fname}] Polling kesildi; batch sunucuda çalışıyor olabilir. "
                                "Oturum submitted bırakıldı.", "warn")
                        else:
                            self._log(f"[{fname}] Batch çıktısı alınamadı ({wait_result['status']}).", "err")
                            ht.update_batch_session(session, filepath, "failed")
                        continue

                    # save_results [HATA] satırlarını görünür eksik-çeviri işaretiyle bırakır;
                    # işaretlenen sayı raporun gerçeği yansıtması için yakalanır
                    # save_results'i src_cues=None vererek bu akışta işaretleme yapmadan bırakıyoruz.
                    _save_ret = ht.save_results(openai_key, out_id, fmap, out_path, self._log,
                                                token_callback=self._update_batch_tokens,
                                                src_cues=None, base_url=b_url)
                _final_blocks = list(parse_srt(out_path))
                if cues and not _final_blocks:
                    self._log(f"{fname}: kaynak dolu ama batch çıktısı boş; tamamlandı sayılmayacak.", "err")
                    ht.update_batch_session(session, filepath, "failed")
                    continue
                
                # Çevrilemeyen satırları sync ile onarma denemesi
                try:
                    _raw_map_pre = _raw_src_map_from_cues(cues)
                    _repair_client = OpenAI(api_key=openai_key, base_url=b_url if b_url else None)
                    _final_blocks, _n_repaired = _repair_untranslated_sync(
                        _final_blocks, _raw_map_pre, _repair_client,
                        src_lang=src, tgt_lang=tgt,
                        model="gpt-5.4-mini",
                        schema=self._get_schema(), profanity=self.profanity_var.get(),
                        log_fn=self._log, token_cb=self._update_tokens)
                except Exception:
                    pass
                
                _n_filled_save = 0
                _unresolved_missing = sum(
                    1 for _idx, _ts, _txt in _final_blocks
                    if str(_txt or "").startswith("[HATA") or "[ÇEVİRİ EKSİK]" in str(_txt or "")
                )
                if _unresolved_missing:
                    try:
                        _raw_map = _raw_src_map_from_cues(cues)
                        _interim_blocks, _n_filled_save = _fill_hata_with_source(list(_final_blocks), _raw_map, log_fn=self._log)
                        _interim_blocks = _restore_tags_blocks(_interim_blocks, _raw_map)
                        write_srt(out_path, self._maybe_merge_cues(_interim_blocks))
                    except Exception:
                        pass
                    self._log(
                        f"{fname}: {_unresolved_missing} eksik çeviri kaldı; "
                        "Critic/Polish atlandı, dosya tamamlandı sayılmayacak.",
                        "err",
                    )
                    _hata_n, _cps_n = _count_hata_cps(_final_blocks)
                    _cps_avg, _cps_max = _cps_stats(_final_blocks)
                    report_rows.append({
                        "name": fname, "total": len(_final_blocks),
                        "hata": max(_hata_n, _unresolved_missing), "cps": _cps_n,
                        "cps_avg": _cps_avg, "cps_max": _cps_max,
                        "cons": 0, "pass_fix": 0,
                        "qc_auto": 0, "qc": 0, "warn": _unresolved_missing,
                        "pass_trace": {}, "pass_history": {},
                        "pass_coverage": "skipped_missing",
                        "tm_hits": self._tm.hit_count_session(),
                    })
                    ht.update_batch_session(session, filepath, "failed")
                    continue
                _raw_backup_blocks = list(_final_blocks)   # kalite geçişleri öncesi ham çeviri (yedek)
                # Tutarlılık taraması (düz sync/batch + sync-hybrid ile paritede)
                _cons_fixes = 0
                try:
                    _final_blocks, _cons_fixes = ht.consistency_sweep(
                        cues, _final_blocks, log_fn=self._log)
                except Exception:
                    pass
                _pre_pass = {str(b[0]): b[2] for b in _final_blocks}
                _pass_fix, _qc_fixes, _qc_auto_fixes = 0, 0, 0
                _pass_trace = {}
                _pass_history = {}

                # Bağlam incelemesi — batch'te zincirleme bağlam yoktur (chunk'lar paralel),
                # bu geçiş telafi eder. Düz-batch _write_results'te zaten var; hybrid-batch de
                # aynı şekilde chained-context'ten yoksun olduğundan burada da çalışmalı.
                if self.review_pass_var.get() and _final_blocks and not self._stop_flag:
                    try:
                        self._set_status(f"Bağlam incelemesi: {fname}")
                        self._log(f"Bağlam incelemesi başlıyor ({len(_final_blocks)} satır)...", "info")
                        _before_rev = list(_final_blocks)
                        _final_blocks, _rev_fixes = self._review_pass(filepath, _final_blocks, model, tgt)
                        _record_pass_change(_pass_trace, "Review", _before_rev, _final_blocks, _pass_history)
                    except Exception as e:
                        self._log(f"Bağlam incelemesi hatası: {e}", "warn")

                # Post-processing: Critic Pass + Polish Pass + Native + SDH + Line Breaks + QC
                # Use per-file analysis_tuple (not a shared outer variable) to ensure
                # each file gets its own context even in multi-file batches.
                _full_analysis = analysis_tuple
                if (self.critic_var.get() or self.polish_var.get()
                        or self.native_var.get()
                        or self.clean_sdh_var.get() or self.linebreak_var.get()
                        or self.qc_var.get()):
                    try:
                        pp_blocks = list(_final_blocks)   # tutarlılık-taranmış bloklardan başla
                        
                        if self.critic_var.get() and pp_blocks:
                            self._set_status(f"Critic Pass: {fname}")
                            self._log(f"Critic Pass başlıyor ({len(pp_blocks)} satır)...", "info")
                            _before_pass = list(pp_blocks)
                            _critic_change_log = []
                            pp_blocks = ht.critic_pass_with_helper(
                                cues=cues, tr_blocks=pp_blocks,
                                helper_api_key=self._helper_api_key("critic"), helper_url=self._helper_api_base_url("critic"), helper_model=self._helper_api_model("critic"), tgt_lang=tgt,
                                log_fn=self._log, glossary=glossary,
                                analysis_result=_full_analysis,
                                change_log=_critic_change_log)
                            _record_pass_change(_pass_trace, "Critic", _before_pass, pp_blocks, _pass_history)
                            self._write_critic_change_report(out_path, _critic_change_log)
                        if self.polish_var.get() and pp_blocks:
                            self._set_status(f"Doğallaştırma: {fname}")
                            self._log(f"Polish Pass başlıyor ({len(pp_blocks)} satır)...", "info")
                            _before_pass = list(pp_blocks)
                            pp_blocks = self._polish_pass(pp_blocks, tgt, self._helper_api_key("polish"), self._helper_api_base_url("polish"), self._helper_api_model("polish"),
                                                          src_map=_src_map_from_cues(cues),
                                                          analysis_result=_full_analysis)
                            _record_pass_change(_pass_trace, "Polish", _before_pass, pp_blocks, _pass_history)
                            self._log("Polish Pass tamamlandı", "ok")
                        if self.native_var.get() and pp_blocks:
                            self._set_status(f"Native Okuyucu: {fname}")
                            self._log(f"Native Okuyucu Pass başlıyor ({len(pp_blocks)} satır)...", "info")
                            _before_pass = list(pp_blocks)
                            pp_blocks = ht.native_reader_pass(
                                tr_blocks=pp_blocks,
                                helper_api_key=self._helper_api_key("critic"), helper_url=self._helper_api_base_url("critic"), helper_model=self._helper_api_model("critic"), tgt_lang=tgt,
                                log_fn=self._log,
                                analysis_result=_full_analysis,
                                token_callback=self._update_tokens,
                                src_map=_src_map_from_cues(cues))
                            _record_pass_change(_pass_trace, "Native", _before_pass, pp_blocks, _pass_history)
                        if pp_blocks and (self.critic_var.get() or self.polish_var.get() or self.native_var.get()):
                            _before_pass = list(pp_blocks)
                            pp_blocks, _final_cons_fixes = ht.final_consistency_sweep(cues, pp_blocks, log_fn=self._log)
                            if _final_cons_fixes:
                                _record_pass_change(_pass_trace, "Final-Consistency", _before_pass, pp_blocks, _pass_history)
                        _before_pass = list(pp_blocks)
                        pp_blocks = self._maybe_condense(
                            pp_blocks,
                            self._helper_api_key("analysis"),
                            self._helper_api_base_url("analysis"),
                            self._helper_api_model("analysis"),
                            tgt, src_map=_src_map_from_cues(cues))
                        _record_pass_change(_pass_trace, "Condense", _before_pass, pp_blocks, _pass_history)
                        if self.clean_sdh_var.get():
                            _before_pass = list(pp_blocks)
                            pp_blocks = clean_sdh(pp_blocks, src_map=_src_map_from_cues(cues), source_driven=True)
                            _record_pass_change(_pass_trace, "SDH", _before_pass, pp_blocks, _pass_history)
                        if self.linebreak_var.get() and pp_blocks:
                            _before_pass = list(pp_blocks)
                            pp_blocks = apply_line_breaks(pp_blocks)
                            _record_pass_change(_pass_trace, "Line-break", _before_pass, pp_blocks, _pass_history)
                        if self.qc_var.get() and pp_blocks:
                            self._set_status(f"{self._helper_display_name('qc')} QC: {fname}")
                            issues = ht.quality_check_with_helper(
                                cues=cues, tr_blocks=pp_blocks,
                                helper_api_key=self._helper_api_key("qc"), helper_url=self._helper_api_base_url("qc"), helper_model=self._helper_api_model("qc"), tgt_lang=tgt,
                                log_fn=self._log,
                                analysis_result=_full_analysis)
                            if issues:
                                auto_issues, review_issues = ht.split_qc_issues_for_review(issues)
                                if auto_issues:
                                    _before_pass = list(pp_blocks)
                                    self._log(f"QC auto: {len(auto_issues)} düşük/orta severity düzeltme uygulanıyor", "info")
                                    pp_blocks = ht.qc_auto_fix(
                                        issues=auto_issues,
                                        tr_blocks=pp_blocks,
                                        helper_api_key=self._helper_api_key("qc"),
                                        model=self._helper_api_model("qc"),
                                        tgt_lang=tgt,
                                        base_url=self._helper_api_base_url("qc"),
                                        log_fn=self._log,
                                    )
                                    _n_auto = _record_pass_change(_pass_trace, "QC auto", _before_pass, pp_blocks, _pass_history)
                                    _qc_fixes += _n_auto
                                    _qc_auto_fixes += _n_auto
                                approved_fixes = []
                                status = "completed"
                                if review_issues:
                                    qc_event = threading.Event()
                                    _post_ui(self, self._show_qc_dialog, review_issues, approved_fixes, qc_event)
                                    status = self._wait_for_dialog_event(qc_event, timeout=300)
                                    if status == "stopped":
                                        break
                                    if status == "timeout":
                                        self._set_status("QC: süre aşımı")
                                if approved_fixes and status == "completed":
                                    _before_pass = list(pp_blocks)
                                    pp_blocks = ht.qc_auto_fix(
                                        issues=approved_fixes,
                                        tr_blocks=pp_blocks,
                                        helper_api_key=self._helper_api_key("qc"),
                                        model=self._helper_api_model("qc"),
                                        tgt_lang=tgt,
                                        base_url=self._helper_api_base_url("qc"),
                                        log_fn=self._log,
                                    )
                                    _n_approved = _record_pass_change(_pass_trace, "QC", _before_pass, pp_blocks, _pass_history)
                                    _qc_fixes += _n_approved
                        # Kalite geçişi düzeltmeleri (etiketten bağımsız karşılaştır)
                        _pass_fix = sum(
                            1 for b in pp_blocks
                            if _pre_pass.get(str(b[0])) is not None
                            and _clean_src(_pre_pass[str(b[0])]) != _clean_src(b[2]))
                        _final_blocks = pp_blocks
                    except Exception as pp_e:
                        self._log(f"Post-processing hatası: {pp_e}", "err")

                # CPS uyarısı — sync-hybrid ile paritede (batch loglarında da görünsün)
                _log_cps_warning(_final_blocks, self._log)
                # Etiket geri yükleme + birleştirme + yazım HER ZAMAN çalışır (kalite
                # toggle'ları kapalı olsa bile italik/konum etiketleri kaybolmasın) —
                # eskiden bu adımlar yalnızca bir kalite geçişi açıkken çalışıyordu.
                try:
                    _final_blocks = _restore_tags_blocks(_final_blocks, _raw_src_map_from_cues(cues))
                except Exception:
                    pass
                if getattr(self, "term_normalize_var", None) and self.term_normalize_var.get():
                    try:
                        _final_blocks, _ = _normalize_mixed_terms(
                            _final_blocks, {str(c.index): _clean_src(c.text) for c in cues},
                            self._helper_api_key("polish"), self._helper_api_base_url("polish"),
                            self._helper_api_model("polish"), log_fn=self._log)
                    except Exception:
                        pass
                write_srt(out_path, self._maybe_merge_cues(_final_blocks))
                self._save_raw_backup(out_path, _raw_backup_blocks, _raw_src_map_from_cues(cues))
                _src_map = {str(c.index): _clean_src(c.text) for c in cues}
                # Kalite taraması (çeviri sonrası uyarılar) — diğer akışlarla paritede
                _w = 0
                try:
                    _w = scan_translation_quality(filepath, _final_blocks,
                                                  log_fn=self._log, src_clean_map=_src_map)
                except Exception:
                    pass
                self._maybe_backtranslation_check(out_path, _src_map, _final_blocks)
                # TM kaydı (ortak yardımcı)
                self._store_tm_pairs(_final_blocks, _src_map, self._main_model_name(), tgt)
                if self.auto_glossary_var.get():
                    self._run_auto_glossary(cues, _final_blocks, filepath)

                # Rapor satırı ([HATA]: kalan + save_results'ın doldurduğu)
                _hata_n, _cps_n = _count_hata_cps(_final_blocks)
                _cps_avg, _cps_max = _cps_stats(_final_blocks)
                _pc = "+".join(k for k, v in [("critic",self.critic_var.get()),("polish",self.polish_var.get()),("native",self.native_var.get()),("QC",self.qc_var.get()),("condense",self.condense_var.get()),("review",self.review_pass_var.get()),("termnorm",self.term_normalize_var.get()),("2wave",self.twowave_var.get()),("SDH",self.clean_sdh_var.get()),("linebreak",self.linebreak_var.get())] if v)
                report_rows.append({
                    "name": fname, "total": len(_final_blocks),
                    "hata": _hata_n + _n_filled_save, "cps": _cps_n,
                    "cps_avg": _cps_avg, "cps_max": _cps_max,
                    "cons": _cons_fixes, "pass_fix": _pass_fix,
                    "qc_auto": _qc_auto_fixes, "qc": _qc_fixes, "warn": _w,
                    "pass_trace": _pass_trace,
                    "pass_history": _pass_history,
                    "pass_coverage": _pc,
                    "tm_hits": self._tm.hit_count_session(),
                })

                ht.clear_context_cache(filepath)
                ht.update_batch_session(session, filepath, "completed")

            except Exception as e:
                self._log(f"[{fname}] Faz-2 hatası: {e} — atlanıyor", "err")
                ht.update_batch_session(session, filepath, "failed")
                continue

        self._save_quality_report(report_rows, output_dir)
        self._set_running(False)
        if not self._stop_flag:
            self._set_progress(100)
            _completed_files = []
            _failed_files = []
            _skipped_files = []
            for _filepath in srt_files:
                _file_status = session["files"].get(str(_filepath), {}).get("status", "pending")
                if _file_status == "completed":
                    _completed_files.append(_filepath)
                elif self._is_queued_file_removed(_filepath):
                    _skipped_files.append(_filepath)
                elif _file_status == "failed":
                    _failed_files.append(_filepath)
            _outcome = summarize_file_outcomes(
                _completed_files, _failed_files, _skipped_files, n_files)
            if _outcome["is_full_success"]:
                self._set_status("Tamamlandı.")
            elif _outcome["is_partial_success"]:
                self._set_status("Kısmen tamamlandı.")
            elif _outcome["is_failure"]:
                self._set_status("Başarısız.")
            else:
                self._set_status("Tamamlandı.")
            if _outcome["is_recovery_complete"]:
                ht.clear_batch_session(input_dir)
                self._clear_batch_recovery([s[4] for s in submitted])
                self._log("Oturum dosyası temizlendi (tüm dosyalar tamamlandı).", "info")
            self._notify(_outcome["title_text"], f"{_outcome['summary_text']} → {output_dir}")
            if _outcome["completed_count"] > 0:
                _post_ui(self, messagebox.showinfo, _outcome["title_text"],
                              f"{_outcome['summary_text']}!\n\nKonum:\n{output_dir}")
        else:
            self._set_status("Durduruldu.")
            self._log(
                "İşlem durduruldu. Kaldığınız yerden devam etmek için "
                "'Hybrid Mod'u tekrar başlatın — tamamlanan dosyalar atlanacak.",
                "info")


if __name__ == "__main__":
    # tkinterdnd2 ile drag-and-drop desteği (opsiyonel)
    try:
        from tkinterdnd2 import TkinterDnD
        # CustomTkinter ile entegrasyon: CTk'nin altında TkinterDnD kullan
        import customtkinter.windows.ctk_tk as _ctk_tk
        _orig_ctk_base = _ctk_tk.CTk.__bases__
        if TkinterDnD.Tk not in _orig_ctk_base:
            _ctk_tk.CTk.__bases__ = (TkinterDnD.Tk,) + _orig_ctk_base[1:]
    except Exception:
        pass  # tkinterdnd2 kurulu değil — sürükle-bırak olmadan çalışır
    app = App()
    app.mainloop()
