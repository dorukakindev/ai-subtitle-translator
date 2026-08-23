import email.utils
import hashlib
import copy
import json
import re
import threading
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

from app_state import atomic_write_json


_RETRY_DELAY_RE = re.compile(
    r'(?i)(?:retry[_ -]?(?:after|delay)|retryDelay|try\s+again\s+in)["\']?'
    r'\s*[:=]?\s*["\']?'
    r'(\d+(?:\.\d+)?)\s*(ms|milliseconds?|s|sec(?:onds?)?)?'
)

TRANSIENT_RETRY_DELAYS = (5.0, 5.0, 5.0, 10.0, 30.0,
                          35.0, 40.0, 45.0, 45.0, 50.0)
PROVIDER_CIRCUIT_FAILURE_THRESHOLD = 3
PROVIDER_CIRCUIT_COOLDOWN_SECONDS = 60.0
RESPONSE_CHECKPOINT_VER = 1
_QUOTA_EXHAUSTED_MARKERS = (
    "insufficient_quota",
    "pre_consume_token_quota_failed",
    "token quota is not enough",
    "预扣费额度失败",
    "用户剩余额度",
    "余额不足",
)

_RESPONSE_CHECKPOINT_LOCK = threading.Lock()
_RESPONSE_CHECKPOINT = None
_RESPONSE_CHECKPOINT_GENERATION = 0
_REQUEST_CONTEXT = threading.local()

SHUAI_API_ROUTE_OPTIONS = (
    ("CF optimize", "https://api.shuaiapi.com/v1"),
    ("Global", "https://oai.sb/v1"),
    ("Asya Pasifik CDN 2", "https://api.oai.sb/v1"),
    ("Asya Pasifik CDN", "https://cdn.shuaiapi.com/v1"),
)
_SHUAI_ROUTE_HOSTS = frozenset(
    urlparse(url).hostname for _label, url in SHUAI_API_ROUTE_OPTIONS)
_SHUAI_FAILOVER_LOCK = threading.Lock()
_SHUAI_FAILOVER_ENABLED = False
_SHUAI_FAILOVER_PREFERRED_ROUTES = {
    "main": SHUAI_API_ROUTE_OPTIONS[0][1],
    "helper": SHUAI_API_ROUTE_OPTIONS[0][1],
}
_SHUAI_LAST_WORKING_ROUTES = {"main": "", "helper": ""}
# Aktif rota duyurusu SCOPE BASINA BIR KEZ loglanir: her istek basarili
# failover'da satir basmak oturum logunu ayni satirdan onlarcasiyla dolduruyor
# ve gercek ilerleme gorunmez oluyordu (2026-08-20 ekran goruntusu).
_SHUAI_ANNOUNCED_ROUTES = {"main": "", "helper": ""}
_SHUAI_ANNOUNCE_COUNTS = {"main": 0, "helper": 0}
_SHUAI_FAILOVER_LOG = None
_SHUAI_ROUTE_COOLDOWN_SECONDS = 300.0
_SHUAI_TRANSIENT_COOLDOWN_SECONDS = 30.0
_SHUAI_ROUTE_STATES = {
    url: {
        "health": "unknown", "cooldown_until": 0.0, "probing": False,
        "attempts": 0, "successes": 0, "failures": 0, "rate_limits": 0,
        "failovers": 0, "total_tokens": 0, "duration_seconds": 0.0,
        "last_error": "",
        # Koşu öncesi ölçüm (bkz. probe_shuai_routes): soğuk başlangıçta
        # sıralama artık liste sırasına değil gerçek gecikmeye dayanır.
        "probe_ok": False, "probe_latency_ms": None, "probe_detail": "",
        "probe_at": 0.0,
    }
    for _label, url in SHUAI_API_ROUTE_OPTIONS
}
_SHUAI_ROUTE_CONDITION = threading.Condition(_SHUAI_FAILOVER_LOCK)
_SHUAI_PROBE_DONE = False
SHUAI_ROUTE_PROBE_PATH = "/api/ping"
_SHUAI_PROBE_UNREACHABLE_RANK = 1_000_000.0


def normalize_shuai_api_route(value) -> str:
    raw = str(value or "").strip()
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").casefold()
    if host not in _SHUAI_ROUTE_HOSTS:
        return ""
    return f"https://{host}/v1"


def shuai_api_route_label(value) -> str:
    normalized = normalize_shuai_api_route(value)
    for label, url in SHUAI_API_ROUTE_OPTIONS:
        if url == normalized:
            return label
    return SHUAI_API_ROUTE_OPTIONS[0][0]


# ── Anahtar / grup yedeklemesi ───────────────────────────────────────────────
# Rota failover'i base_url'i degistirir, ANAHTARI degistirmez. Sorun rotada
# degil new-api GRUBUNDA ise (kota bitti, model gruba kapali, anahtar askiya
# alindi) dort rota da ayni hatayi verir. Bu katman ikinci bir gruba ait yedek
# anahtara gecer ve gecisi kosu boyunca yapisik tutar.
_API_KEY_FALLBACK_LOCK = threading.Lock()
_API_KEY_FALLBACKS = {}
_API_KEY_GROUP_MARKERS = (
    "no available channel",
    "no channel available",
    "current group",
    "无可用渠道",   # 无可用渠道
    "分组",                       # 分组
)


def configure_api_key_fallback(scope: str = "main", primary_key: str = "",
                               backup_key: str = "", log_fn=None) -> bool:
    """Bir kapsam icin yedek API anahtarini kaydeder.

    Yedek yoksa (ya da birincil ile ayniysa) kayit silinir ve davranis
    bugunku haliyle kalir. Her kosu basinda cagrilmalidir: aktif anahtar
    birincile geri doner.
    """
    scope = str(scope or "main")
    primary = str(primary_key or "").strip()
    backup = str(backup_key or "").strip()
    with _API_KEY_FALLBACK_LOCK:
        if not primary or not backup or primary == backup:
            _API_KEY_FALLBACKS.pop(scope, None)
            return False
        _API_KEY_FALLBACKS[scope] = {
            "primary": primary,
            "backup": backup,
            "active": "primary",
            "log": log_fn,
            "switched": False,
        }
        return True


def reset_api_key_fallback(scope: str = "") -> None:
    with _API_KEY_FALLBACK_LOCK:
        if scope:
            _API_KEY_FALLBACKS.pop(scope, None)
        else:
            _API_KEY_FALLBACKS.clear()


def api_key_fallback_state(scope: str = "main") -> dict:
    with _API_KEY_FALLBACK_LOCK:
        entry = _API_KEY_FALLBACKS.get(scope)
        if not entry:
            return {}
        return {"active": entry["active"], "switched": bool(entry["switched"])}


def _is_api_key_or_group_error(exc) -> bool:
    """Yedek anahtara gecmeyi hak eden hata mi?

    404 BURADA disarida: tek bir rotada yol/model bulunamadi olabilir ve
    zaten rota failover'ini tetikler. Rotalar tukendikten SONRA anlami
    degisir; bkz. _is_post_route_key_error.
    """
    status = _status_code(exc)
    if status in (401, 403):
        return True
    text = _provider_error_text(exc).casefold()
    if any(marker in text for marker in _QUOTA_EXHAUSTED_MARKERS):
        return True
    if any(marker in text for marker in _API_KEY_GROUP_MARKERS):
        return True
    return bool(status == 429 and "insufficient" in text)


def _is_post_route_key_error(exc) -> bool:
    """Rota failover'i tukendikten sonra: 404 de grup sorunudur.

    Dort rotanin dordu de 404 donduyse sorun rotada degil; new-api model
    grupta yoksa/kanal yoksa bu kodu doner (2026-08-23 kosu logu: gpt-5.4
    tum rotalarda 404, yedek anahtar hic denenmiyordu).

    ISTISNA: "channel is temporarily unavailable" metnini tasiyan 404 gecici
    bir bayi arizasidir; onu zaten 11 denemelik gecici-hata merdiveni
    kurtariyor (ayni gun 16:51 logunda kanal iki dakika sonra geri geldi).
    Tek atislik yedek gecisini boyle bir dalgalanmaya harcamayiz.
    """
    if _is_api_key_or_group_error(exc):
        return True
    return _status_code(exc) == 404 and not _is_transient_provider_error(exc)


def _client_api_key(client) -> str:
    api_key = getattr(client, "api_key", "")
    getter = getattr(api_key, "get_secret_value", None)
    if callable(getter):
        try:
            api_key = getter()
        except Exception:
            api_key = ""
    return str(api_key or "")


def _openai_client_for_key(client, api_key: str):
    try:
        return client.with_options(api_key=api_key, max_retries=0)
    except Exception:
        from openai import OpenAI
        base_url = str(getattr(client, "base_url", "") or "") or None
        return OpenAI(api_key=api_key, base_url=base_url, max_retries=0)


def _apply_active_api_key(client, scope: str):
    """Kosu icinde yedek anahtara gecildiyse yeni istekler de onu kullanir.

    Yalniz BIRINCIL anahtari tasiyan istemci degistirilir: bir yardimci role
    kendi anahtarini verdiyse (baska hesap) ona dokunulmaz.
    """
    with _API_KEY_FALLBACK_LOCK:
        entry = _API_KEY_FALLBACKS.get(scope)
        if not entry or entry["active"] != "backup":
            return client
        primary, backup = entry["primary"], entry["backup"]
    if _client_api_key(client) != primary:
        return client
    try:
        return _openai_client_for_key(client, backup)
    except Exception:
        return client


def _switch_to_backup_api_key(client, scope: str, exc):
    """Hata anahtar/grup kaynakliysa yedek anahtarli istemciyi dondurur.

    Buraya gelen hata rota failover'ini ZATEN gecmistir: her rota denenmis
    ve hepsi ayni hatayi vermistir. Bu yuzden 404'u de grup sorunu sayariz.
    """
    if not _is_post_route_key_error(exc):
        return None
    with _API_KEY_FALLBACK_LOCK:
        entry = _API_KEY_FALLBACKS.get(scope)
        if not entry:
            return None
        primary, backup = entry["primary"], entry["backup"]
        # Kendi anahtari olan bir rolu baska hesabin anahtarina cevirmeyiz.
        if _client_api_key(client) != primary:
            return None
        if entry["active"] == "backup":
            return None
        entry["active"] = "backup"
        entry["switched"] = True
        log_fn = entry.get("log")
    try:
        alternate = _openai_client_for_key(client, backup)
    except Exception:
        return None
    reason = _provider_error_context(exc).get("reason", "anahtar/grup hatasi")
    if _status_code(exc) == 404:
        reason += " — model bu grupta yok gibi görünüyor"
    message = (
        f"Ana API anahtarı başarısız ({reason}); tüm rotalarda aynı hata "
        "alındı, ikinci gruba ait yedek anahtara geçiliyor. Koşunun kalanı "
        "yedek anahtarla sürecek.")
    if log_fn is not None:
        try:
            log_fn(message, "warn")
        except Exception:
            pass
    else:
        _shuai_log(message, "warn")
    return alternate


def shuai_route_probe_url(route_url) -> str:
    """Rota tabanindan (…/v1) saglik ucunu (…/api/ping) turetir."""
    normalized = normalize_shuai_api_route(route_url)
    if not normalized:
        return ""
    parsed = urlparse(normalized)
    return f"{parsed.scheme}://{parsed.netloc}{SHUAI_ROUTE_PROBE_PATH}"


def _probe_one_shuai_route(route_url: str, attempts: int, timeout: float) -> dict:
    """Tek rotayi yoklar. API ANAHTARI GONDERMEZ, yalniz GET atar.

    Her istege rastgele bir nonce konur ve cevapta ayni nonce aranir: ara
    katman onbelleginden gelen bayat 200 'saglikli' sayilmaz.
    """
    probe_url = shuai_route_probe_url(route_url)
    if not probe_url:
        return {"ok": False, "successes": 0, "attempts": 0,
                "median_ms": None, "detail": "invalid-url"}
    latencies = []
    detail = ""
    for _ in range(max(1, int(attempts))):
        nonce = uuid.uuid4().hex
        request = urllib.request.Request(
            f"{probe_url}?nonce={nonce}",
            headers={
                "Accept": "application/json",
                "Cache-Control": "no-cache",
                "User-Agent": "SubtitleTranslator-RouteProbe/1.0",
            },
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read(65536).decode("utf-8", "replace")
            elapsed = int((time.perf_counter() - started) * 1000)
            payload = json.loads(body)
            data = payload.get("data") if isinstance(payload, dict) else None
            if (isinstance(payload, dict) and payload.get("success") is True
                    and isinstance(data, dict)
                    and data.get("service") == "new-api"
                    and data.get("nonce") == nonce):
                latencies.append(max(0, elapsed))
            elif not detail:
                detail = "gecersiz yanit"
        except urllib.error.HTTPError as exc:
            detail = f"HTTP {exc.code}"
        except Exception as exc:  # ag/TLS/zaman asimi
            if not detail:
                detail = f"{type(exc).__name__}: {exc}"[:120]
    median = None
    if latencies:
        ordered = sorted(latencies)
        middle = len(ordered) // 2
        median = (ordered[middle] if len(ordered) % 2
                  else int(round((ordered[middle - 1] + ordered[middle]) / 2)))
    return {
        "ok": bool(latencies),
        "successes": len(latencies),
        "attempts": max(1, int(attempts)),
        "median_ms": median,
        "detail": "" if latencies else (detail or "yanit yok"),
    }


def probe_shuai_routes(attempts: int = 2, timeout: float = 6.0,
                       log_fn=None) -> dict:
    """Dort rotayi paralel yoklar, sonucu sıralamaya tohum olarak yazar.

    Donen: {rota_url: {'ok', 'successes', 'attempts', 'median_ms', 'detail'}}
    Olcum SADECE siralamayi etkiler; cooldown/health gibi gercek API
    verisine dokunmaz — ping canli demek, model kanali saglikli demek degil.
    """
    global _SHUAI_PROBE_DONE
    routes = [url for _label, url in SHUAI_API_ROUTE_OPTIONS]
    results = {}
    with ThreadPoolExecutor(max_workers=len(routes)) as pool:
        futures = {
            pool.submit(_probe_one_shuai_route, url, attempts, timeout): url
            for url in routes
        }
        for future, url in futures.items():
            try:
                results[url] = future.result()
            except Exception as exc:
                results[url] = {
                    "ok": False, "successes": 0, "attempts": attempts,
                    "median_ms": None,
                    "detail": f"{type(exc).__name__}: {exc}"[:120],
                }
    now = time.monotonic()
    with _SHUAI_ROUTE_CONDITION:
        for url, result in results.items():
            state = _SHUAI_ROUTE_STATES.get(url)
            if state is None:
                continue
            state["probe_ok"] = bool(result.get("ok"))
            state["probe_latency_ms"] = result.get("median_ms")
            state["probe_detail"] = str(result.get("detail") or "")
            state["probe_at"] = now
        _SHUAI_PROBE_DONE = True
    if log_fn is not None:
        for label, url in SHUAI_API_ROUTE_OPTIONS:
            result = results.get(url) or {}
            host = urlparse(url).hostname or url
            if result.get("ok"):
                log_fn(
                    f"Rota testi: {label} ({host}) "
                    f"{result.get('successes')}/{result.get('attempts')} "
                    f"· medyan {result.get('median_ms')} ms", "info")
            else:
                log_fn(
                    f"Rota testi: {label} ({host}) yanit vermedi "
                    f"({result.get('detail')})", "warn")
    return results


def shuai_route_probe_report() -> list:
    """GUI tablosu icin satirlar; hizlidan yavasa siralidir."""
    rows = []
    with _SHUAI_ROUTE_CONDITION:
        for label, url in SHUAI_API_ROUTE_OPTIONS:
            state = dict(_SHUAI_ROUTE_STATES.get(url) or {})
            rows.append({
                "label": label,
                "url": url,
                "host": urlparse(url).hostname or url,
                "probe_ok": bool(state.get("probe_ok")),
                "median_ms": state.get("probe_latency_ms"),
                "detail": str(state.get("probe_detail") or ""),
                "health": str(state.get("health") or "unknown"),
                "cooldown_until": float(state.get("cooldown_until", 0.0) or 0.0),
                "successes": int(state.get("successes", 0) or 0),
                "failures": int(state.get("failures", 0) or 0),
            })
    rows.sort(key=lambda row: (
        0 if row["probe_ok"] else 1,
        row["median_ms"] if row["median_ms"] is not None else 10 ** 9,
    ))
    return rows


def shuai_probe_ran() -> bool:
    return _SHUAI_PROBE_DONE


def reset_shuai_route_probe() -> None:
    """Olcum sonuclarini siler (testler ve ayar degisikligi icin)."""
    global _SHUAI_PROBE_DONE
    with _SHUAI_ROUTE_CONDITION:
        for state in _SHUAI_ROUTE_STATES.values():
            state["probe_ok"] = False
            state["probe_latency_ms"] = None
            state["probe_detail"] = ""
            state["probe_at"] = 0.0
        _SHUAI_PROBE_DONE = False


API_KEY_CHECK_TIMEOUT = 20.0
_API_KEY_CHECK_PROMPT = "ping"
# Yanit icerigi onemsiz: HTTP 200 + gecerli 'choices' anahtarin ve grubun
# o modeli tasidigini kanitlar. gpt-5 ailesinde butce dusunme jetonlarini
# da kapsadigi icin bos metin donmesi NORMAL, basarisizlik degil.
_API_KEY_CHECK_BUDGET = 16

# GERCEKCI sinama: 16 jetonluk "ping" bayinin on kapisini olcuyor ama
# gercek isi olcmuyor. 2026-08-23 19:03'te anahtar testi ust uste UC KEZ
# ilk denemede yesil dedi, iki dakika sonra kosu dort rotadan da 502 aldi:
# kisa istek aninda doner, uzun uretimde ag gecidi zaman asimina duser.
# Bu yuzden kapi isteginin kosunun gonderdigine BENZEMESI gerekiyor.
_API_KEY_CHECK_REALISTIC_BUDGET = 600
_API_KEY_CHECK_REALISTIC_PROMPT = (
    "Translate these subtitle lines into Turkish. Return one line per input "
    "line and nothing else.\n"
    "1. We had been walking for hours before the rain finally stopped.\n"
    "2. Nobody told him the bridge had been closed since the spring floods.\n"
    "3. She kept the letter in a drawer for almost thirty years.\n"
    "4. The engine coughed twice, then settled into a steady rhythm.\n"
    "5. If you leave now you will still reach the harbour before dark.\n"
    "6. They argued about the price until the market began to empty.\n"
    "7. It was the last winter anyone remembered the river freezing over.\n"
    "8. He wrote the whole account down and then never spoke of it again."
)


def _api_key_check_payload(model: str, realistic: bool = False) -> dict:
    """Sinama istegi.

    realistic=False: bir kac jeton, yalniz anahtar/grup dogrulamasi.
    realistic=True : kosunun gonderdigine benzer boyutta gercek bir ceviri
    istegi — bayinin uzun uretimde 502 verip vermedigini de gorur.
    """
    model_lower = (model or "").lower()
    reasoning = (model_lower.startswith(("o1", "o3", "o4", "gpt-5", "codex-")))
    budget = (_API_KEY_CHECK_REALISTIC_BUDGET if realistic
              else _API_KEY_CHECK_BUDGET)
    prompt = (_API_KEY_CHECK_REALISTIC_PROMPT if realistic
              else _API_KEY_CHECK_PROMPT)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    if reasoning:
        payload["max_completion_tokens"] = budget
    else:
        payload["max_tokens"] = budget
        payload["temperature"] = 0
    return payload


def _api_key_check_request(url: str, api_key: str, timeout: float,
                           payload=None) -> tuple:
    """(status, govde, transport_hatasi) dondurur. Anahtar loglanmaz."""
    data = None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": "SubtitleTranslator-KeyCheck/1.0",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace"), ""
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        return exc.code, body, ""
    except Exception as exc:
        return None, "", f"{type(exc).__name__}: {exc}"[:120]


_TEMPORARY_CHANNEL_MARKERS = (
    "temporarily unavailable",
    "channel is temporarily",
    "渠道暂时不可用",
    "暂时不可用",
)


def _is_temporary_channel_text(folded: str) -> bool:
    """Bayinin ust kaynak kanali gecici kapali mi (model eksikligi DEGIL)?"""
    return any(marker in folded for marker in _TEMPORARY_CHANNEL_MARKERS)


def _api_key_check_is_flaky(status, body: str) -> bool:
    """Bu basarisizlik anahtarin degil, o anki hattin sorunu mu?

    Oyleyse hem siradaki rota denenir hem de tur bittiginde bir kez daha
    supurulur: bayi dalgalanirken kirmizi yakmak kullaniciyi yaniltir
    (2026-08-23 16:49'da kirmizi, 16:51'de ayni anahtar yesildi).
    """
    if status is None:
        return True
    if status >= 500:
        return True
    folded = (body or "").casefold()
    if _is_temporary_channel_text(folded):
        return True
    if status == 429:
        return not any(marker in folded for marker in _QUOTA_EXHAUSTED_MARKERS)
    return False


def _api_key_check_reason(status, body: str) -> str:
    """HTTP kodunu kullanicinin anlayacagi tek satira cevirir."""
    text = ""
    try:
        parsed = json.loads(body or "{}")
        error = parsed.get("error")
        if isinstance(error, dict):
            text = str(error.get("message") or "")
        elif isinstance(error, str):
            text = error
        if not text:
            text = str(parsed.get("message") or "")
    except Exception:
        text = (body or "")[:120]
    text = " ".join(text.split())[:160]
    folded = (text or "").casefold()
    labels = {
        401: "anahtar gecersiz veya askida",
        403: "anahtarin bu modele/gruba izni yok",
        404: "model bu grupta yok",
        429: "kota bitti veya hiz siniri",
    }
    label = labels.get(status, f"HTTP {status}" if status else "baglanti yok")
    # new-api ayni 404'u iki bambaska durum icin doner: model gercekten
    # grupta yoksa VE ust kaynak kanali gecici kapaliysa. Ikincisi bir kac
    # dakikada kendi kendine duzelir; "model yok" demek yaniltici olur.
    if _is_temporary_channel_text(folded):
        label = "bayinin kanali gecici olarak kapali"
    elif any(marker in folded for marker in _QUOTA_EXHAUSTED_MARKERS):
        label = "kota bitti"
    return f"{label} — {text}" if text else label



def list_models_for_key(api_key: str, base_url: str,
                        timeout: float = 10.0) -> list:
    """Anahtarin grubundaki model adlari (new-api listeyi gruba gore filtreler)."""
    root = normalize_shuai_api_route(base_url) or str(base_url or "").rstrip("/")
    if not root:
        return []
    status, body, _err = _api_key_check_request(
        f"{root}/models", api_key, timeout)
    if status != 200:
        return []
    try:
        payload = json.loads(body or "{}")
    except Exception:
        return []
    names = []
    for item in payload.get("data") or []:
        if isinstance(item, dict) and item.get("id"):
            names.append(str(item["id"]))
        elif isinstance(item, str):
            names.append(item)
    return sorted(set(names))


def _model_missing_hint(api_key: str, base_url: str, model: str,
                        timeout: float) -> str:
    """404 sonrasi: model gercekten grupta yok mu, yoksa baska sorun mu?"""
    names = list_models_for_key(api_key, base_url, timeout=timeout)
    if not names:
        return ""
    if model in names:
        return ("model grubun listesinde var; sorun kanal atamasi "
                "veya kota olabilir")
    near = [name for name in names
            if name.split(":")[0].startswith((model or "")[:5])]
    if near:
        return "grupta bunlar var: " + ", ".join(near[:4])
    return f"grupta {len(names)} model var ama bu yok"


def _api_key_check_sweep(api_key: str, model: str, route_urls, payload: dict,
                         timeout: float, tally: dict) -> dict:
    """Rotalari sirayla dener; ilk KESIN cevap sonucu belirler.

    tally: {"attempts": n, "failures": n} — kac denemede basarildigini
    cagirana bildirir. Yesil isik tek basina yaniltici olabiliyor: bayi
    dalgalanirken sekiz denemenin biri 200 donse de kosunun ILK istegi
    502'ye denk gelebiliyor (2026-08-23 18:43 anahtar testi "calisiyor",
    18:44 kosusu dort rotadan da 502).
    """
    last = {"ok": False, "status": None, "latency_ms": None,
            "detail": "baglanti yok", "route": "", "hint": "", "flaky": True}
    for route in route_urls:
        if not route:
            continue
        started = time.monotonic()
        tally["attempts"] = tally.get("attempts", 0) + 1
        status, body, transport = _api_key_check_request(
            f"{route}/chat/completions", api_key, timeout, payload)
        elapsed = int((time.monotonic() - started) * 1000)
        if transport or status is None:
            tally["failures"] = tally.get("failures", 0) + 1
            last = {"ok": False, "status": None, "latency_ms": elapsed,
                    "detail": transport or "baglanti yok",
                    "route": route, "hint": "", "flaky": True}
            continue
        if status == 200:
            # Bu ucretli bir istek: `realistic=True` kosunun gonderdigine
            # BENZER boyutta gercek bir ceviri yolluyor. Yanit govdesindeki
            # `usage` okunmadan atiliyordu, yani harcama hicbir yerde
            # gorunmuyordu. Cagiran muhasebeye yazabilsin diye tasinir.
            usage = None
            try:
                usage = (json.loads(body) or {}).get("usage")
            except Exception:
                usage = None
            return {"ok": True, "status": 200, "latency_ms": elapsed,
                    "detail": "calisiyor", "route": route, "hint": "",
                    "flaky": False,
                    "usage": usage if isinstance(usage, dict) else None}
        tally["failures"] = tally.get("failures", 0) + 1
        flaky = _api_key_check_is_flaky(status, body)
        result = {"ok": False, "status": status, "latency_ms": elapsed,
                  "detail": _api_key_check_reason(status, body),
                  "route": route, "hint": "", "flaky": flaky}
        if flaky:
            # Yol veya kanal dalgalaniyor: bu rotayi anahtara yazmayiz.
            last = result
            continue
        if status == 404:
            result["hint"] = _model_missing_hint(
                api_key, route, model, min(timeout, 10.0))
        return result
    return last


def probe_api_key(api_key: str, base_url: str, model: str,
                  timeout: float = API_KEY_CHECK_TIMEOUT,
                  route_urls=None, attempts: int = 2,
                  retry_delay: float = 3.0, realistic: bool = False) -> dict:
    """Bir anahtari kucuk bir istekle sinar.

    Kesin cevaplar (401/403/gercek 404) ilk rotada isi bitirir. Gecici
    gorunen hatalar once siradaki rotaya, tur bitince de kisa bir bekleme
    sonrasi yeni bir tura devrolur; bayinin kanali dalgalanirken saglam bir
    anahtari kirmizi yakmamak icin.

    Donen sozlukte 'attempts'/'failures' de bulunur: yesil isik "anahtar ve
    grup dogru" demektir, "saglayici saglikli" DEMEZ. Kac denemede
    basarildigini gormeden yesil isik yaniltici olur.
    """
    api_key = str(api_key or "").strip()
    model = str(model or "").strip()
    if not api_key:
        return {"ok": False, "status": None, "latency_ms": None,
                "detail": "anahtar girilmemis", "route": "", "hint": "",
                "attempts": 0, "failures": 0}
    if not model:
        return {"ok": False, "status": None, "latency_ms": None,
                "detail": "model adi bos", "route": "", "hint": "",
                "attempts": 0, "failures": 0}
    if route_urls is None:
        normalized = normalize_shuai_api_route(base_url)
        if normalized and urlparse(normalized).hostname in _SHUAI_ROUTE_HOSTS:
            route_urls = [url for _label, url in SHUAI_API_ROUTE_OPTIONS]
            if normalized in route_urls:
                route_urls.remove(normalized)
            route_urls.insert(0, normalized)
        else:
            route_urls = [normalized or str(base_url or "").rstrip("/")]
    payload = _api_key_check_payload(model, realistic=realistic)
    tally = {"attempts": 0, "failures": 0}
    result = {}
    for turn in range(max(1, int(attempts))):
        if turn:
            time.sleep(max(0.0, retry_delay))
        result = _api_key_check_sweep(
            api_key, model, route_urls, payload, timeout, tally)
        if result["ok"] or not result.get("flaky"):
            break
    result.pop("flaky", None)
    result["attempts"] = tally["attempts"]
    result["failures"] = tally["failures"]
    return result


def api_key_check_stability_note(result: dict) -> str:
    """Yesil isigin yaninda gosterilecek kararsizlik uyarisi ('' ise temiz)."""
    if not isinstance(result, dict) or not result.get("ok"):
        return ""
    failures = int(result.get("failures", 0) or 0)
    attempts = int(result.get("attempts", 0) or 0)
    if failures <= 0:
        return ""
    return (f"anahtar ve grup dogru ama saglayici kararsiz: "
            f"{attempts} denemenin {failures} tanesi basarisiz")


def configure_shuai_route_failover(
        enabled=True, preferred_url="", log_fn=None,
        main_preferred_url=""):
    global _SHUAI_FAILOVER_ENABLED
    global _SHUAI_FAILOVER_LOG
    preferred = normalize_shuai_api_route(preferred_url)
    if not preferred:
        preferred = SHUAI_API_ROUTE_OPTIONS[0][1]
    main_preferred = normalize_shuai_api_route(main_preferred_url)
    if not main_preferred:
        main_preferred = _SHUAI_FAILOVER_PREFERRED_ROUTES["main"]
    with _SHUAI_FAILOVER_LOCK:
        if (not enabled
                or preferred != _SHUAI_FAILOVER_PREFERRED_ROUTES["helper"]):
            _SHUAI_LAST_WORKING_ROUTES["helper"] = ""
            _SHUAI_ANNOUNCED_ROUTES["helper"] = ""
        if (not enabled
                or main_preferred != _SHUAI_FAILOVER_PREFERRED_ROUTES["main"]):
            _SHUAI_LAST_WORKING_ROUTES["main"] = ""
            _SHUAI_ANNOUNCED_ROUTES["main"] = ""
        _SHUAI_FAILOVER_ENABLED = bool(enabled)
        _SHUAI_FAILOVER_PREFERRED_ROUTES.update({
            "main": main_preferred,
            "helper": preferred,
        })
        if log_fn is not None:
            _SHUAI_FAILOVER_LOG = log_fn


def _shuai_route_scope(checkpoint_label: str = "") -> str:
    label = str(checkpoint_label or "").strip().casefold()
    main_prefixes = (
        "main_translation", "translation_preview", "translation_repair",
        "translation_json_repair", "translation_subgroup_recovery",
        "ai_segmentation",
    )
    return "main" if label.startswith(main_prefixes) else "helper"


def _shuai_probe_rank(state) -> float:
    """Ölçüm sıralaması. Hiç ölçüm yapılmadıysa herkese 0 → nötr.

    Ölçüm yapıldıysa cevap vermeyen rota en sona düşer; cevap veren rotalar
    medyan gecikmeye göre sıralanır. Bu kriter BAŞARI ORANININ ALTINDA durur:
    ping ölçümü hangi kenarın canlı olduğunu söyler, yukarı akış kanalının
    sağlığını değil (2026-08-23 sağlayıcı kesintisi).
    """
    if not _SHUAI_PROBE_DONE:
        return 0.0
    if not state.get("probe_ok"):
        return _SHUAI_PROBE_UNREACHABLE_RANK
    latency = state.get("probe_latency_ms")
    if latency is None:
        return _SHUAI_PROBE_UNREACHABLE_RANK
    return float(latency)


def _shuai_route_score(route: str, preferred: str, last_working: str) -> tuple:
    state = _SHUAI_ROUTE_STATES.get(route) or {}
    attempts = int(state.get("attempts", 0) or 0)
    successes = int(state.get("successes", 0) or 0)
    failures = int(state.get("failures", 0) or 0)
    avg = (
        float(state.get("duration_seconds", 0.0) or 0.0) / successes
        if successes else 999999.0
    )
    success_rate = successes / max(1, successes + failures)
    probe_rank = _shuai_probe_rank(state)
    # Olcum yapildi ve bu rota cevap vermediyse 'tercih edilen'/'son calisan'
    # ayricaligi da dusurulur: olu rotaya bos yere ilk istegi harcamayalim.
    probe_dead = probe_rank >= _SHUAI_PROBE_UNREACHABLE_RANK
    return (
        0 if (route == last_working and not probe_dead) else 1,
        0 if (route == preferred and not probe_dead) else 1,
        -success_rate if attempts else 0.0,
        probe_rank,
        int(state.get("rate_limits", 0) or 0),
        avg,
    )


def _shuai_route_candidates(current_url, scope: str = "helper") -> tuple[str, ...]:
    current = normalize_shuai_api_route(current_url)
    if not current:
        return ()
    with _SHUAI_FAILOVER_LOCK:
        if not _SHUAI_FAILOVER_ENABLED:
            return (current,)
        preferred = _SHUAI_FAILOVER_PREFERRED_ROUTES.get(scope, current)
        last_working = _SHUAI_LAST_WORKING_ROUTES.get(scope, "")
        now = time.monotonic()
        available = [
            url for _label, url in SHUAI_API_ROUTE_OPTIONS
            if float(_SHUAI_ROUTE_STATES[url].get("cooldown_until", 0.0) or 0.0)
            <= now
        ]
        if not available:
            return ()
        return tuple(sorted(
            dict.fromkeys(available),
            key=lambda route: _shuai_route_score(route, preferred, last_working)))


def _shuai_claim_route(route: str) -> bool:
    with _SHUAI_ROUTE_CONDITION:
        state = _SHUAI_ROUTE_STATES[route]
        now = time.monotonic()
        if float(state.get("cooldown_until", 0.0) or 0.0) > now:
            return False
        needs_probe = state.get("health") != "healthy"
        if needs_probe and state.get("probing"):
            return False
        if needs_probe:
            state["probing"] = True
        return True


def _response_total_tokens(response) -> int:
    usage = response.get("usage") if isinstance(response, dict) else getattr(
        response, "usage", None)
    if isinstance(usage, dict):
        return int(usage.get("total_tokens", 0) or 0)
    return int(getattr(usage, "total_tokens", 0) or 0) if usage else 0


def _shuai_record_route_result(route: str, success: bool, duration: float,
                               response=None, exc=None) -> None:
    with _SHUAI_ROUTE_CONDITION:
        state = _SHUAI_ROUTE_STATES[route]
        state["attempts"] = int(state.get("attempts", 0) or 0) + 1
        state["duration_seconds"] = round(
            float(state.get("duration_seconds", 0.0) or 0.0)
            + max(0.0, float(duration or 0.0)), 3)
        state["probing"] = False
        if success:
            state["health"] = "healthy"
            state["cooldown_until"] = 0.0
            state["successes"] = int(state.get("successes", 0) or 0) + 1
            state["total_tokens"] = int(state.get("total_tokens", 0) or 0) + (
                _response_total_tokens(response))
            state["last_error"] = ""
        else:
            status = _status_code(exc)
            state["health"] = "cooldown"
            state["failures"] = int(state.get("failures", 0) or 0) + 1
            if status == 429:
                state["rate_limits"] = int(state.get("rate_limits", 0) or 0) + 1
            cooldown = (
                _SHUAI_ROUTE_COOLDOWN_SECONDS if status == 429
                else _SHUAI_TRANSIENT_COOLDOWN_SECONDS)
            state["cooldown_until"] = time.monotonic() + cooldown
            state["last_error"] = _provider_error_text(exc)
        _SHUAI_ROUTE_CONDITION.notify_all()


def _shuai_release_route_probe(route: str) -> None:
    with _SHUAI_ROUTE_CONDITION:
        state = _SHUAI_ROUTE_STATES[route]
        state["probing"] = False
        _SHUAI_ROUTE_CONDITION.notify_all()


def reset_shuai_route_metrics() -> None:
    with _SHUAI_ROUTE_CONDITION:
        for state in _SHUAI_ROUTE_STATES.values():
            state.update({
                "health": "unknown", "cooldown_until": 0.0,
                "probing": False, "attempts": 0, "successes": 0,
                "failures": 0, "rate_limits": 0, "failovers": 0,
                "total_tokens": 0, "duration_seconds": 0.0,
                "last_error": "",
            })
        _SHUAI_LAST_WORKING_ROUTES.update({"main": "", "helper": ""})
        _SHUAI_ANNOUNCED_ROUTES.update({"main": "", "helper": ""})
        _SHUAI_ANNOUNCE_COUNTS.update({"main": 0, "helper": 0})
        _SHUAI_ROUTE_CONDITION.notify_all()


def shuai_route_metrics_snapshot() -> list[dict]:
    with _SHUAI_FAILOVER_LOCK:
        now = time.monotonic()
        rows = []
        for label, route in SHUAI_API_ROUTE_OPTIONS:
            state = dict(_SHUAI_ROUTE_STATES[route])
            state.update({
                "label": label, "route": route,
                "host": urlparse(route).hostname or route,
                "cooldown_remaining": max(
                    0.0, float(state.get("cooldown_until", 0.0) or 0.0) - now),
            })
            state.pop("probing", None)
            rows.append(state)
        return rows


def format_shuai_route_metrics() -> list[str]:
    result = []
    for row in shuai_route_metrics_snapshot():
        attempts = int(row.get("attempts", 0) or 0)
        if not attempts:
            continue
        successes = int(row.get("successes", 0) or 0)
        avg = float(row.get("duration_seconds", 0.0) or 0.0) / max(1, attempts)
        result.append(
            f"{row['host']}: {successes}/{attempts} başarılı, "
            f"429={int(row.get('rate_limits', 0) or 0)}, "
            f"geçiş={int(row.get('failovers', 0) or 0)}, "
            f"ort. {avg:.1f} sn, token={int(row.get('total_tokens', 0) or 0)}")
    return result


def _shuai_failover_error(exc) -> bool:
    status = _status_code(exc)
    return bool(
        _is_transient_provider_error(exc)
        or status in {404, 405, 421, 520, 521, 522, 523}
    )


def _shuai_log(message: str, level: str = "info") -> None:
    with _SHUAI_FAILOVER_LOCK:
        callback = _SHUAI_FAILOVER_LOG
    if callback:
        try:
            callback(message, level)
        except TypeError:
            try:
                callback(message)
            except Exception:
                pass
        except Exception:
            pass


def _openai_client_for_route(client, route: str):
    try:
        return client.with_options(base_url=route, max_retries=0)
    except Exception:
        from openai import OpenAI
        api_key = getattr(client, "api_key", "")
        getter = getattr(api_key, "get_secret_value", None)
        if callable(getter):
            api_key = getter()
        return OpenAI(api_key=api_key, base_url=route, max_retries=0)


def _response_checkpoint_namespace_dir(root: Path, namespace: str) -> Path:
    digest = hashlib.sha256(str(namespace).encode("utf-8", "replace")).hexdigest()
    return Path(root) / digest


def _checkpoint_base_url(value) -> str:
    raw = str(value or "").rstrip("/")
    try:
        parsed = urlparse(raw)
        if not parsed.scheme or not parsed.netloc:
            return raw
        userinfo, separator, hostport = parsed.netloc.rpartition("@")
        netloc = ((userinfo + separator) if separator else "") + hostport.lower()
        return parsed._replace(
            scheme=parsed.scheme.lower(), netloc=netloc).geturl()
    except Exception:
        return raw


def configure_response_checkpoint(path=None, namespace: str = "",
                                   allow_reads: bool = False,
                                   hit_callback=None, error_callback=None) -> None:
    global _RESPONSE_CHECKPOINT, _RESPONSE_CHECKPOINT_GENERATION
    with _RESPONSE_CHECKPOINT_LOCK:
        _RESPONSE_CHECKPOINT_GENERATION += 1
        if path is None or not str(namespace).strip():
            _RESPONSE_CHECKPOINT = None
            return
        _RESPONSE_CHECKPOINT = {
            "path": Path(path),
            "namespace": str(namespace),
            "allow_reads": bool(allow_reads),
            "hit_callback": hit_callback,
            "error_callback": error_callback,
            "write_error_reported": False,
            "hits": 0,
            "consumed": set(),
            "generation": _RESPONSE_CHECKPOINT_GENERATION,
        }


def _response_checkpoint_snapshot() -> dict:
    with _RESPONSE_CHECKPOINT_LOCK:
        return dict(_RESPONSE_CHECKPOINT or {})


def clear_response_checkpoint_namespace(path, namespace: str) -> bool:
    root = Path(path)
    namespace_dir = _response_checkpoint_namespace_dir(root, namespace)
    try:
        for item in namespace_dir.iterdir():
            if item.is_file():
                item.unlink(missing_ok=True)
        namespace_dir.rmdir()
        try:
            root.rmdir()
        except OSError:
            pass
        return True
    except FileNotFoundError:
        return True
    except Exception:
        return False


def _response_checkpoint_key(client, model: str, kwargs: dict,
                             requested_format=None, checkpoint_label="") -> str:
    payload = {
        "base_url": _checkpoint_base_url(getattr(client, "base_url", "")),
        "model": str(model or ""),
        "kwargs": kwargs,
        "requested_format": requested_format,
    }
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()


def _cached_chat_response(entry: dict):
    message = SimpleNamespace(content=entry.get("content"))
    choice = SimpleNamespace(
        message=message,
        finish_reason=entry.get("finish_reason"),
    )
    usage = SimpleNamespace(
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        prompt_tokens_details=SimpleNamespace(cached_tokens=0),
    )
    return SimpleNamespace(
        choices=[choice], usage=usage, usage_available=True,
        response_checkpoint_hit=True)


def _response_checkpoint_lookup(client, model: str, kwargs: dict,
                                requested_format=None, checkpoint_label="",
                                checkpoint_config=None):
    config = (dict(checkpoint_config)
              if checkpoint_config is not None
              else _response_checkpoint_snapshot())
    if not config or not config.get("allow_reads"):
        return None
    key = _response_checkpoint_key(
        client, model, kwargs, requested_format, checkpoint_label)
    root = config["path"]
    namespace = config["namespace"]
    if key in config.get("consumed", set()):
        return None
    entry_path = _response_checkpoint_namespace_dir(root, namespace) / f"{key}.json"
    try:
        entry = json.loads(entry_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if (not isinstance(entry, dict)
            or entry.get("version") != RESPONSE_CHECKPOINT_VER
            or "content" not in entry):
        return None
    callback = None
    hits = 0
    valid = False
    with _RESPONSE_CHECKPOINT_LOCK:
        current = _RESPONSE_CHECKPOINT
        if (current and current.get("path") == root
                and current.get("namespace") == namespace
                and current.get("generation") == config.get("generation")):
            if key in current.setdefault("consumed", set()):
                return None
            current["consumed"].add(key)
            current["hits"] = int(current.get("hits", 0)) + 1
            hits = current["hits"]
            callback = current.get("hit_callback")
            valid = True
    if not valid:
        return None
    if callback:
        try:
            callback(
                hits,
                str(entry.get("checkpoint_label") or checkpoint_label or ""),
                str(entry.get("request_fingerprint") or key[:16]),
            )
        except TypeError:
            try:
                callback(
                    hits,
                    str(entry.get("checkpoint_label") or checkpoint_label or ""))
            except TypeError:
                try:
                    callback(hits)
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            pass
    return _cached_chat_response(entry)


def _response_checkpoint_save(client, model: str, kwargs: dict, response,
                              requested_format=None, checkpoint_label="",
                              checkpoint_config=None) -> None:
    config = (dict(checkpoint_config)
              if checkpoint_config is not None
              else _response_checkpoint_snapshot())
    if not config:
        return
    try:
        choice = response.choices[0]
        content = choice.message.content
    except Exception:
        return
    if not isinstance(content, str) or not content.strip():
        return
    finish_reason = getattr(choice, "finish_reason", None)
    if finish_reason not in (None, "stop"):
        return
    key = _response_checkpoint_key(
        client, model, kwargs, requested_format, checkpoint_label)
    root = config["path"]
    namespace = config["namespace"]
    entry = {
        "version": RESPONSE_CHECKPOINT_VER,
        "content": content,
        "finish_reason": finish_reason,
        "updated_at": time.time(),
        "checkpoint_label": str(checkpoint_label or ""),
        "model": str(model or ""),
        "request_fingerprint": key[:16],
        "namespace": str(namespace or ""),
    }
    callback = None
    callback_error = None
    with _RESPONSE_CHECKPOINT_LOCK:
        current = _RESPONSE_CHECKPOINT
        if (not current
                or current.get("generation") != config.get("generation")
                or current.get("path") != root
                or current.get("namespace") != namespace):
            return
        try:
            entry_path = _response_checkpoint_namespace_dir(
                root, namespace) / f"{key}.json"
            atomic_write_json(entry_path, entry)
        except Exception as exc:
            if not current.get("write_error_reported"):
                current["write_error_reported"] = True
                callback = current.get("error_callback")
                callback_error = exc
    if callback:
        try:
            callback("write", callback_error)
        except Exception:
            pass


def _status_code(exc) -> int | None:
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    try:
        return int(status)
    except (TypeError, ValueError):
        text = str(exc or "")
        match = re.search(
            r"(?i)\b(?:http|status(?:[_ -]*code)?|error[_ -]*code)\s*[:=]?\s*(\d{3})\b",
            text,
        )
        return int(match.group(1)) if match else None


def _provider_error_text(exc) -> str:
    parts = [str(exc or "")]
    body = getattr(exc, "body", None)
    if body:
        try:
            parts.append(json.dumps(body, ensure_ascii=False))
        except TypeError:
            parts.append(str(body))
    response_text = getattr(getattr(exc, "response", None), "text", None)
    if response_text:
        parts.append(str(response_text))
    return " ".join(parts).casefold()


def _headers(exc):
    for owner in (exc, getattr(exc, "response", None)):
        headers = getattr(owner, "headers", None)
        if headers:
            return headers
    return {}


def _header_value(headers, name: str):
    try:
        value = headers.get(name)
        if value is None:
            value = headers.get(name.lower())
        if value is None:
            value = headers.get(name.upper())
        if value is None:
            wanted = str(name).casefold()
            for key, item in headers.items():
                if str(key).casefold() == wanted:
                    return item
        return value
    except Exception:
        return None


def _retry_after_header_seconds(value) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    try:
        return max(0.0, float(text))
    except ValueError:
        pass
    try:
        when = email.utils.parsedate_to_datetime(text)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


def _retry_after_hint_seconds(exc, maximum: float = 600.0) -> float | None:
    headers = _headers(exc)
    retry_ms = _header_value(headers, "retry-after-ms")
    if retry_ms is not None:
        try:
            return min(maximum, max(0.0, float(retry_ms) / 1000.0))
        except (TypeError, ValueError):
            pass
    header_delay = _retry_after_header_seconds(_header_value(headers, "retry-after"))
    return min(maximum, header_delay) if header_delay is not None else None


def _structured_retry_after_seconds(exc, maximum: float = 600.0) -> float | None:
    def _value_seconds(value):
        if isinstance(value, (int, float)):
            return min(maximum, max(0.0, float(value)))
        text = str(value or "").strip()
        match = re.fullmatch(
            r"(\d+(?:\.\d+)?)\s*(ms|milliseconds?|s|sec(?:onds?)?)?",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None
        delay = float(match.group(1))
        if (match.group(2) or "s").lower().startswith("m"):
            delay /= 1000.0
        return min(maximum, max(0.0, delay))

    def _walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                normalized = str(key).strip().casefold().replace("-", "_")
                if normalized in {
                    "retry_after", "retry_after_seconds", "retry_delay",
                    "retrydelay",
                }:
                    parsed = _value_seconds(item)
                    if parsed is not None:
                        return parsed
                parsed = _walk(item)
                if parsed is not None:
                    return parsed
        elif isinstance(value, (list, tuple)):
            for item in value:
                parsed = _walk(item)
                if parsed is not None:
                    return parsed
        return None

    body = getattr(exc, "body", None)
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except (TypeError, ValueError):
            pass
    parsed = _walk(body)
    if parsed is not None:
        return parsed
    response = getattr(exc, "response", None)
    json_fn = getattr(response, "json", None)
    if callable(json_fn):
        try:
            parsed = _walk(json_fn())
        except Exception:
            parsed = None
        if parsed is not None:
            return parsed
    text = getattr(response, "text", None)
    if text:
        try:
            return _walk(json.loads(str(text)))
        except (TypeError, ValueError):
            pass
    return None


def retry_after_seconds(exc, default: float = 2.0, maximum: float = 600.0) -> float:
    header_delay = _retry_after_hint_seconds(exc, maximum=maximum)
    if header_delay is not None:
        return header_delay

    structured_delay = _structured_retry_after_seconds(exc, maximum=maximum)
    if structured_delay is not None:
        return structured_delay

    candidates = [str(exc or "")]
    body = getattr(getattr(exc, "response", None), "text", None)
    if body:
        candidates.append(str(body))
    error_body = getattr(exc, "body", None)
    if error_body:
        try:
            candidates.append(json.dumps(error_body, ensure_ascii=False))
        except TypeError:
            candidates.append(str(error_body))

    for text in candidates:
        match = _RETRY_DELAY_RE.search(text)
        if not match:
            continue
        delay = float(match.group(1))
        unit = (match.group(2) or "s").lower()
        if unit.startswith("ms"):
            delay /= 1000.0
        return min(maximum, max(0.0, delay))
    return min(maximum, max(0.0, float(default)))


def _client_key(client) -> str:
    base_url = _checkpoint_base_url(getattr(client, "base_url", ""))
    api_key = getattr(client, "api_key", "")
    getter = getattr(api_key, "get_secret_value", None)
    if callable(getter):
        try:
            api_key = getter()
        except Exception:
            api_key = ""
    digest = hashlib.sha256(str(api_key or "").encode("utf-8")).hexdigest()[:12]
    return f"{base_url}|{digest}"


def _circuit_key(client, model: str = "") -> str:
    return f"{_client_key(client)}|{str(model or '').strip().casefold()}"


def _provider_request_context(client, model: str, checkpoint_label: str = "") -> dict:
    base_url = str(getattr(client, "base_url", "") or "")
    parsed = urlparse(base_url)
    return {
        "checkpoint_label": str(checkpoint_label or ""),
        "model": str(model or ""),
        "provider": str(parsed.hostname or parsed.netloc or "OpenAI"),
    }


def _upstream_request_id(value) -> str:
    direct = getattr(value, "request_id", None) or getattr(value, "_request_id", None)
    if direct:
        return str(direct)[:160]
    response = getattr(value, "response", None)
    headers = getattr(response, "headers", None) or getattr(value, "headers", None)
    for name in ("x-request-id", "request-id", "x-request_id"):
        header = _header_value(headers, name)
        if header:
            return str(header)[:160]
    candidates = [str(value or "")]
    body = getattr(value, "body", None)
    if body:
        try:
            candidates.append(json.dumps(body, ensure_ascii=False))
        except TypeError:
            candidates.append(str(body))
    for text in candidates:
        match = re.search(
            r"(?i)(?:request[_ -]?id)\s*[:=]\s*['\"]?([A-Za-z0-9._:-]{6,160})",
            text,
        )
        if match:
            return match.group(1).rstrip("')]}.,")
    return ""


def _provider_error_context(exc) -> dict:
    status = _status_code(exc)
    text = _provider_error_text(exc)
    if any(marker in text for marker in _QUOTA_EXHAUSTED_MARKERS):
        reason = "kota veya bakiye tükendi"
    elif status == 429 or "rate limit" in text:
        reason = "hız veya eşzamanlılık sınırı"
    elif "temporarily unavailable" in text:
        reason = "sağlayıcı kanalı geçici olarak kullanılamıyor"
    elif status == 401 or "invalid api key" in text:
        reason = "kimlik doğrulama"
    elif status == 403:
        reason = "anahtarın model, grup veya IP erişimi engelli"
    elif status == 404:
        reason = "model adı veya API yolu bulunamadı"
    elif status == 413 or "context_length_exceeded" in text:
        reason = "bağlam uzunluğu aşıldı"
    elif "model_not_found" in text or "available channel" in text:
        reason = "model veya kanal kullanılamıyor"
    elif status == 408 or "timeout" in text or "timed out" in text:
        reason = "zaman aşımı"
    elif status in {500, 502, 503, 504, 529}:
        reason = "sağlayıcı sunucu hatası"
    elif "connection" in text:
        reason = "bağlantı hatası"
    else:
        reason = "API hatası"
    result = {"status_code": status, "reason": reason}
    request_id = _upstream_request_id(exc)
    if request_id:
        result["request_id"] = request_id
    return result


def _auto_group_configuration_error(text: str) -> bool:
    lowered = str(text or "").casefold()
    return (
        "model_not_found" in lowered
        and "auto groups is not enabled" in lowered
    )


class ProviderCooldownRegistry:
    def __init__(
        self,
        clock=None,
        sleeper=None,
        retry_spacing: float = 0.25,
        cancel_check=None,
        wait_callback=None,
    ):
        self._clock = clock or time.monotonic
        self._sleep = sleeper or time.sleep
        self._retry_spacing = max(0.0, float(retry_spacing))
        self._heartbeat_enabled = clock is None and sleeper is None
        self._cancel_check = cancel_check
        self._wait_callback = wait_callback
        self._lock = threading.Lock()
        self._cooldown_until = {}
        self._next_slot = {}
        self._failure_counts = {}
        self._circuit_until = {}
        self._probe_locks = {}
        self._probe_owners = {}
        self._waiting = 0
        self._active_requests = 0
        self._request_seq = 0
        self._active_request_details = {}
        self._heartbeat_thread = None

    def set_hooks(self, cancel_check=None, wait_callback=None):
        with self._lock:
            self._cancel_check = cancel_check
            self._wait_callback = wait_callback

    def _notify(self, event: str, remaining: float, count=None, details=None):
        callback = self._wait_callback
        if callback:
            try:
                args = (
                    event,
                    max(0, int(remaining + 0.999)),
                    self._waiting if count is None else int(count),
                )
                try:
                    if details:
                        callback(*args, dict(details))
                    else:
                        callback(*args)
                except TypeError:
                    callback(*args)
            except Exception:
                pass

    def _cancelled(self):
        local_cancel = getattr(_REQUEST_CONTEXT, "cancel_check", None)
        return bool(
            (local_cancel and local_cancel())
            or (self._cancel_check and self._cancel_check())
        )

    def _wait_until(self, deadline: float, event_prefix: str, details=None) -> float:
        waited = max(0.0, deadline - self._clock())
        if waited <= 0.0:
            return 0.0
        with self._lock:
            self._waiting += 1
        self._notify(f"{event_prefix}_start", waited, details=details)
        last_second = None
        try:
            while True:
                if self._cancelled():
                    raise ProviderWaitCancelled(
                        "API sağlayıcı beklemesi kullanıcı tarafından durduruldu")
                remaining = deadline - self._clock()
                if remaining <= 0:
                    break
                second = int(remaining + 0.999)
                if second != last_second:
                    last_second = second
                    self._notify(f"{event_prefix}_tick", remaining, details=details)
                self._sleep(min(0.25, remaining))
        finally:
            with self._lock:
                self._waiting = max(0, self._waiting - 1)
            self._notify(f"{event_prefix}_end", 0.0, details=details)
        return waited

    def _before_circuit_request(self, key: str, details=None) -> float:
        waited = 0.0
        while True:
            with self._lock:
                until = self._circuit_until.get(key)
                if until is None:
                    return waited
                now = self._clock()
                if until > now:
                    deadline = until
                    probe_lock = None
                else:
                    probe_lock = self._probe_locks.setdefault(
                        key, threading.Lock())
                    if probe_lock.acquire(blocking=False):
                        self._probe_owners[key] = threading.get_ident()
                        self._notify("circuit_probe", 0.0, details=details)
                        return waited
                    deadline = now + 0.5
            waited += self._wait_until(deadline, "circuit", details)

    def before_request(self, client, model: str = "", details=None) -> float:
        key = _client_key(client)
        circuit_wait = self._before_circuit_request(
            _circuit_key(client, model), details)
        with self._lock:
            now = self._clock()
            cooldown = self._cooldown_until.get(key, 0.0)
            slot = self._next_slot.get(key, 0.0)
            ready = max(cooldown, slot)
            wait = max(0.0, ready - now)
            if wait > 0.0:
                self._next_slot[key] = ready + self._retry_spacing
            elif cooldown <= now:
                self._cooldown_until.pop(key, None)
                self._next_slot.pop(key, None)
        if wait > 0.0:
            with self._lock:
                self._waiting += 1
            self._notify("start", wait, details=details)
            deadline = self._clock() + wait
            last_second = None
            try:
                while True:
                    if self._cancelled():
                        raise ProviderWaitCancelled("API kota beklemesi kullanıcı tarafından durduruldu")
                    remaining = deadline - self._clock()
                    if remaining <= 0:
                        break
                    second = int(remaining + 0.999)
                    if second != last_second:
                        last_second = second
                        self._notify("tick", remaining, details=details)
                    self._sleep(min(0.25, remaining))
            finally:
                with self._lock:
                    self._waiting = max(0, self._waiting - 1)
                self._notify("end", 0.0, details=details)
        return circuit_wait + wait

    def request_started(self, details=None) -> int:
        with self._lock:
            self._request_seq += 1
            request_id = self._request_seq
            self._active_requests += 1
            active = self._active_requests
            self._active_request_details[request_id] = {
                "started": self._clock(), "details": dict(details or {})}
            heartbeat = self._heartbeat_thread
            if (self._heartbeat_enabled
                    and (heartbeat is None or not heartbeat.is_alive())):
                heartbeat = threading.Thread(
                    target=self._request_heartbeat,
                    name="provider-request-heartbeat",
                    daemon=True,
                )
                self._heartbeat_thread = heartbeat
                heartbeat.start()
        self._notify("request_start", 0.0, active, details)
        return request_id

    def _request_heartbeat(self) -> None:
        while True:
            time.sleep(1.0)
            with self._lock:
                active = self._active_requests
                active_items = list(self._active_request_details.values())
            if active <= 0 or not active_items:
                return
            current = min(active_items, key=lambda item: item["started"])
            started = current["started"]
            details = dict(current["details"])
            elapsed = max(0.0, self._clock() - started)
            self._notify("request_tick", elapsed, active, details)

    def request_finished(self, client, success: bool, model: str = "", details=None,
                         request_id=None) -> None:
        key = _circuit_key(client, model)
        recovered = False
        with self._lock:
            self._active_requests = max(0, self._active_requests - 1)
            active = self._active_requests
            if request_id is not None:
                self._active_request_details.pop(request_id, None)
            elif self._active_request_details:
                oldest = min(
                    self._active_request_details,
                    key=lambda rid: self._active_request_details[rid]["started"])
                self._active_request_details.pop(oldest, None)
            if success:
                recovered = key in self._circuit_until
                self._failure_counts.pop(key, None)
                self._circuit_until.pop(key, None)
                owner = self._probe_owners.pop(key, None)
                probe_lock = self._probe_locks.get(key)
                if (owner == threading.get_ident() and probe_lock
                        and probe_lock.locked()):
                    probe_lock.release()
        self._notify(
            "request_success" if success else "request_failure",
            0.0, active, details)
        if recovered:
            self._notify("circuit_recovered", 0.0)

    def _clear_circuit_state(self, key: str) -> None:
        with self._lock:
            self._failure_counts.pop(key, None)
            self._circuit_until.pop(key, None)
            owner = self._probe_owners.pop(key, None)
            probe_lock = self._probe_locks.get(key)
            if (owner == threading.get_ident() and probe_lock
                    and probe_lock.locked()):
                probe_lock.release()

    def record_transient_failure(self, client, exc, model: str = "", details=None) -> float | None:
        status = _status_code(exc)
        text = str(exc or "").lower()
        key = _circuit_key(client, model)
        temporary_unavailable = "temporarily unavailable" in text
        permanent = (
            (status in {400, 401, 403, 404, 409, 422}
             and not temporary_unavailable)
            or "invalid api key" in text
            or any(marker in text for marker in _QUOTA_EXHAUSTED_MARKERS)
            or _auto_group_configuration_error(text)
        )
        if status == 429 or permanent:
            self._clear_circuit_state(key)
            return None
        if not (
            status in {408, 500, 502, 503, 504, 529}
            or "temporarily unavailable" in text
            or "timeout" in text
            or "timed out" in text
            or "connection" in text
            or "server error" in text
            or "internal error" in text
        ):
            self._clear_circuit_state(key)
            return None
        opened = False
        reopened = False
        with self._lock:
            failures = int(self._failure_counts.get(key, 0)) + 1
            self._failure_counts[key] = failures
            already_open = key in self._circuit_until
            if failures >= PROVIDER_CIRCUIT_FAILURE_THRESHOLD or already_open:
                delay = PROVIDER_CIRCUIT_COOLDOWN_SECONDS
                self._circuit_until[key] = self._clock() + delay
                owner = self._probe_owners.pop(key, None)
                probe_lock = self._probe_locks.get(key)
                reopened = bool(already_open and owner == threading.get_ident())
                if (owner == threading.get_ident() and probe_lock
                        and probe_lock.locked()):
                    probe_lock.release()
                opened = not already_open
            else:
                delay = None
        if opened:
            self._notify("circuit_open", delay, details=details)
        elif reopened:
            self._notify("circuit_reopen", delay, details=details)
        return delay

    def wait_for_retry(self, delay: float, attempt: int, total: int, details=None) -> float:
        if details is None:
            details = getattr(_REQUEST_CONTEXT, "retry_details", None)
        wait = max(0.0, float(delay))
        if wait <= 0.0:
            return 0.0
        with self._lock:
            self._waiting += 1
        prefix = f"retry_{{}}_{int(attempt)}_{int(total)}"
        self._notify(prefix.format("start"), wait, details=details)
        deadline = self._clock() + wait
        last_second = None
        try:
            while True:
                if self._cancelled():
                    raise ProviderWaitCancelled(
                        "API yeniden deneme beklemesi kullanıcı tarafından durduruldu")
                remaining = deadline - self._clock()
                if remaining <= 0:
                    break
                second = int(remaining + 0.999)
                if second != last_second:
                    last_second = second
                    self._notify(prefix.format("tick"), remaining, details=details)
                self._sleep(min(0.25, remaining))
        finally:
            with self._lock:
                self._waiting = max(0, self._waiting - 1)
            self._notify(prefix.format("end"), 0.0, details=details)
        return wait

    def notify_retry_success(self, attempt: int, total: int, details=None) -> None:
        if details is None:
            details = getattr(_REQUEST_CONTEXT, "success_details", None)
        self._notify(
            f"retry_success_{int(attempt)}_{int(total)}", 0.0,
            details=details)

    def record_rate_limit(self, client, exc) -> float | None:
        if _status_code(exc) != 429 and "rate limit" not in str(exc or "").lower():
            return None
        delay = retry_after_seconds(exc)
        key = _client_key(client)
        with self._lock:
            until = self._clock() + delay
            self._cooldown_until[key] = max(
                self._cooldown_until.get(key, 0.0),
                until,
            )
            self._next_slot[key] = max(
                self._next_slot.get(key, 0.0),
                self._cooldown_until[key],
            )
        return delay


_REGISTRY = ProviderCooldownRegistry()
_STRUCTURED_LOCK = threading.Lock()
_STRUCTURED_STATES = {}
_STRUCTURED_PROBE_LOCKS = {}


class ProviderWaitCancelled(RuntimeError):
    pass


def before_provider_request(client, model: str = "", details=None) -> float:
    return _REGISTRY.before_request(client, model, details)


def record_provider_failure(client, exc, model: str = "", details=None) -> float | None:
    delay = _REGISTRY.record_rate_limit(client, exc)
    circuit_delay = _REGISTRY.record_transient_failure(
        client, exc, model, details)
    return delay if delay is not None else circuit_delay


def configure_provider_wait_hooks(cancel_check=None, wait_callback=None):
    _REGISTRY.set_hooks(cancel_check=cancel_check, wait_callback=wait_callback)


def _is_transient_provider_error(exc) -> bool:
    text = _provider_error_text(exc)
    status = _status_code(exc)
    temporary_unavailable = "temporarily unavailable" in text
    if (status in {400, 401, 403, 404, 409, 422}
            and not temporary_unavailable):
        return False
    if ("invalid api key" in text
            or any(marker in text for marker in _QUOTA_EXHAUSTED_MARKERS)):
        return False
    if _auto_group_configuration_error(text):
        return False
    return (
        status in {408, 429, 500, 502, 503, 504, 524, 529}
        or "rate limit" in text
        or "temporarily unavailable" in text
        or "timeout" in text
        or "timed out" in text
        or "connection" in text
        or "server error" in text
        or "internal error" in text
    )


def _wait_for_transient_retry(exc, attempt: int, total: int, details=None,
                              scheduled=None) -> float:
    if scheduled is None:
        scheduled = TRANSIENT_RETRY_DELAYS[attempt - 1]
    header_delay = _retry_after_hint_seconds(exc)
    structured_delay = _structured_retry_after_seconds(exc)
    if header_delay is not None:
        scheduled = header_delay
    elif structured_delay is not None:
        scheduled = max(scheduled, structured_delay)
    context = dict(
        details if details is not None
        else getattr(_REQUEST_CONTEXT, "value", {}) or {})
    context.update(_provider_error_context(exc))
    context["next_attempt"] = int(attempt) + 1
    context["max_attempts"] = int(total) + 1
    previous_details = getattr(_REQUEST_CONTEXT, "retry_details", None)
    _REQUEST_CONTEXT.retry_details = context
    try:
        return _REGISTRY.wait_for_retry(scheduled, attempt, total)
    finally:
        if previous_details is None:
            try:
                del _REQUEST_CONTEXT.retry_details
            except AttributeError:
                pass
        else:
            _REQUEST_CONTEXT.retry_details = previous_details


def _is_custom_gpt5(client, model: str) -> bool:
    base_url = str(getattr(client, "base_url", "") or "").lower().rstrip("/")
    return (
        (str(model or "").lower().startswith("gpt-5"))
        and "api.openai.com" not in base_url
        and bool(base_url)
    )


def _structured_key(client, model: str) -> str:
    base_url = _checkpoint_base_url(getattr(client, "base_url", ""))
    return f"{base_url}|{str(model or '').lower()}"


def _translation_schema_kwargs(kwargs: dict) -> dict | None:
    messages = kwargs.get("messages")
    if not isinstance(messages, list):
        return None
    payload = None
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        try:
            candidate = json.loads(message.get("content", ""))
        except Exception:
            continue
        if isinstance(candidate, dict) and isinstance(candidate.get("tr"), list):
            payload = candidate
            break
    if payload is None:
        return None
    ids = [
        str(item.get("i"))
        for item in payload["tr"]
        if isinstance(item, dict) and "i" in item
    ]
    if not ids:
        return None
    structured = copy.deepcopy(kwargs)
    # Rolü mesaj listesinden devral: birçok özel proxy (OneAPI, NewAPI) `developer`
    # rolünü tanımaz ve 400 döner. İstek zaten `developer` kullanıyorsa onu koru,
    # kullanmıyorsa yapılandırılmış çıktı uğruna YENİ bir rol tanıtma.
    instruction_role = (
        "developer"
        if any(message.get("role") == "developer" for message in messages)
        else "system"
    )
    instruction = {
        "role": instruction_role,
        "content": (
            'Return one JSON object {"tr":[{"i":"...","t":"..."}]}. '
            "Include every input id exactly once and no other ids."
        ),
    }
    insert_at = max(
        (index for index, message in enumerate(structured["messages"])
         if message.get("role") == "user"),
        default=len(structured["messages"]),
    )
    structured["messages"].insert(insert_at, instruction)
    structured["response_format"] = {
        "type": "json_schema",
        "json_schema": {
            "name": "subtitle_translations",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "tr": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "i": {"type": "string", "enum": ids},
                                "t": {"type": "string"},
                            },
                            "required": ["i", "t"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["tr"],
                "additionalProperties": False,
            },
        },
    }
    return structured


def _structured_unsupported(exc) -> bool:
    status = _status_code(exc)
    if status not in (400, 404, 422):
        return False
    text = str(exc or "").lower()
    body = getattr(exc, "body", None)
    if body:
        try:
            text += " " + json.dumps(body).lower()
        except TypeError:
            text += " " + str(body).lower()
    response_text = getattr(getattr(exc, "response", None), "text", None)
    if response_text:
        text += " " + str(response_text).lower()
    parameter = any(marker in text for marker in (
        "response_format", "json_schema", "structured output", "structured_output",
        # Bazı proxy'ler yapılandırılmış çıktıya eşlik eden rol/mesaj alanına takılır
        "'role'", '"role"', "messages[", "developer",
    ))
    unsupported = any(marker in text for marker in (
        "not support", "unsupported", "unknown parameter", "unrecognized",
        "extra_forbidden", "invalid parameter", "invalid schema",
        "schema for response_format", "invalid value", "supported values",
        "must be one of", "not permitted",
    ))
    return parameter and unsupported


def _provider_call_once(call, client, model: str, request_context=None,
                        cancel_check=None, retry_delays=None):
    use_default_delays = retry_delays is None
    retry_delays = (TRANSIENT_RETRY_DELAYS if use_default_delays
                    else tuple(retry_delays))
    total = len(retry_delays)
    model = str(model or "")
    base_context = dict(request_context or {})
    previous_cancel = getattr(_REQUEST_CONTEXT, "cancel_check", None)
    _REQUEST_CONTEXT.cancel_check = cancel_check
    try:
        for attempt in range(total + 1):
            if cancel_check and cancel_check():
                raise ProviderWaitCancelled(
                    "API isteği kullanıcı tarafından durduruldu")
            details = dict(base_context)
            details.update({"attempt": attempt + 1, "max_attempts": total + 1})
            before_provider_request(client, model, details)
            started = time.monotonic()
            request_id = _REGISTRY.request_started(details)
            try:
                result = call()
                upstream_request_id = _upstream_request_id(result)
                if upstream_request_id:
                    details["request_id"] = upstream_request_id
                details["duration_seconds"] = round(time.monotonic() - started, 3)
                _REGISTRY.request_finished(
                    client, True, model, details, request_id=request_id)
                if attempt:
                    previous_details = getattr(_REQUEST_CONTEXT, "success_details", None)
                    _REQUEST_CONTEXT.success_details = details
                    try:
                        _REGISTRY.notify_retry_success(attempt, total)
                    finally:
                        if previous_details is None:
                            try:
                                del _REQUEST_CONTEXT.success_details
                            except AttributeError:
                                pass
                        else:
                            _REQUEST_CONTEXT.success_details = previous_details
                return result
            except Exception as exc:
                retryable = attempt < total and _is_transient_provider_error(exc)
                details.update(_provider_error_context(exc))
                details["duration_seconds"] = round(time.monotonic() - started, 3)
                route_failover = bool(
                    base_context.get("shuai_route_failover_pending")
                    and _shuai_failover_error(exc))
                details["will_retry"] = bool(retryable or route_failover)
                details["shuai_route_failover"] = route_failover
                _REGISTRY.request_finished(
                    client, False, model, details, request_id=request_id)
                record_provider_failure(client, exc, model, details)
                if not retryable:
                    raise
                previous_context = getattr(_REQUEST_CONTEXT, "value", None)
                _REQUEST_CONTEXT.value = base_context
                try:
                    if use_default_delays:
                        _wait_for_transient_retry(exc, attempt + 1, total)
                    else:
                        _wait_for_transient_retry(
                            exc, attempt + 1, total,
                            scheduled=retry_delays[attempt])
                finally:
                    if previous_context is None:
                        try:
                            del _REQUEST_CONTEXT.value
                        except AttributeError:
                            pass
                    else:
                        _REQUEST_CONTEXT.value = previous_context
    finally:
        if previous_cancel is None:
            try:
                del _REQUEST_CONTEXT.cancel_check
            except AttributeError:
                pass
        else:
            _REQUEST_CONTEXT.cancel_check = previous_cancel


def provider_call_with_retry(call, client, model: str, request_context=None,
                             cancel_check=None, retry_delays=None):
    return _provider_call_once(
        call, client, model, request_context, cancel_check=cancel_check,
        retry_delays=retry_delays)


def _rotated_route_client(request_client, request_context=None):
    """Yeniden-deneme merdiveninin HER denemesinde rotayı yeniden seçer.

    Rota yarışı yalnız ilk saniyede bir kez yapılıyordu: dördü de düşünce
    hepsi soğumaya giriyor, `_shuai_route_candidates` boş dönüyor ve kalan
    ~10 dakikalık merdiven TEK adrese harcanıyordu. Gerçek koşuda
    (2026-08-22 22:36-22:46) 11 denemenin hepsi `api.shuaiapi.com`'a gitti;
    bağlantı hatasının soğuması 30 sn olduğu için diğer üç rota çoktan
    uygunken bir daha hiç sorulmadılar.

    Yalnız MEVCUT rota soğumadayken devreye girer; sağlıklı rotada çağrı
    olduğu gibi geçer ve Shuai dışı istemcilere hiç dokunmaz.
    """
    current = normalize_shuai_api_route(
        getattr(request_client, "base_url", ""))
    if not current:
        return request_client
    now = time.monotonic()
    with _SHUAI_FAILOVER_LOCK:
        if not _SHUAI_FAILOVER_ENABLED:
            return request_client
        cooling = float(
            _SHUAI_ROUTE_STATES[current].get("cooldown_until", 0.0) or 0.0)
    if cooling <= now:
        return request_client
    scope = _shuai_route_scope(
        (request_context or {}).get("checkpoint_label", ""))
    replacement = next(
        (route for route in _shuai_route_candidates(current, scope=scope)
         if route != current), "")
    if not replacement:
        return request_client
    _shuai_log(
        "Shuai rotası soğumada; yeniden deneme "
        f"{urlparse(replacement).hostname} üzerinden gönderiliyor.", "info")
    return _openai_client_for_route(request_client, replacement)


def _chat_create_once(client, kwargs: dict, request_context=None,
                      cancel_check=None, retry_delays=None):
    request_client = _without_sdk_retries(client)
    return _provider_call_once(
        lambda: _rotated_route_client(
            request_client, request_context).chat.completions.create(**kwargs),
        client,
        kwargs.get("model", ""),
        request_context,
        cancel_check=cancel_check,
        retry_delays=retry_delays,
    )


def _without_sdk_retries(client):
    try:
        from openai import OpenAI
        if isinstance(client, OpenAI) and getattr(client, "max_retries", 0):
            return client.with_options(max_retries=0)
    except (ImportError, TypeError, AttributeError):
        pass
    return client


def _chat_create_with_compat_uncached(client, model: str, kwargs: dict,
                                      requested_format=None, request_context=None,
                                      cancel_check=None, retry_delays=None):
    plain = copy.deepcopy(kwargs)
    if not _is_custom_gpt5(client, model):
        return _chat_create_once(
            client, plain, request_context, cancel_check, retry_delays)

    structured = copy.deepcopy(plain)
    if requested_format is not None:
        structured["response_format"] = copy.deepcopy(requested_format)
    else:
        structured = _translation_schema_kwargs(structured)
    if structured is None:
        return _chat_create_once(
            client, plain, request_context, cancel_check, retry_delays)

    key = _structured_key(client, model)
    with _STRUCTURED_LOCK:
        state = _STRUCTURED_STATES.get(key)
        probe_lock = _STRUCTURED_PROBE_LOCKS.setdefault(key, threading.Lock())
    if state is False:
        return _chat_create_once(
            client, plain, request_context, cancel_check, retry_delays)

    lock = probe_lock if state is None else threading.Lock()
    with lock:
        with _STRUCTURED_LOCK:
            state = _STRUCTURED_STATES.get(key)
        if state is False:
            return _chat_create_once(
                client, plain, request_context, cancel_check, retry_delays)
        try:
            result = _chat_create_once(
                client, structured, request_context, cancel_check, retry_delays)
        except Exception as exc:
            if not _structured_unsupported(exc):
                raise
            with _STRUCTURED_LOCK:
                _STRUCTURED_STATES[key] = False
            return _chat_create_once(
                client, plain, request_context, cancel_check, retry_delays)
        with _STRUCTURED_LOCK:
            _STRUCTURED_STATES[key] = True
        return result


def chat_create_with_compat(client, model: str, kwargs: dict, requested_format=None,
                            checkpoint_label="", cancel_check=None,
                            retry_delays=None, request_context_extra=None):
    checkpoint_config = _response_checkpoint_snapshot()
    cached = _response_checkpoint_lookup(
        client, model, kwargs, requested_format=requested_format,
        checkpoint_label=checkpoint_label,
        checkpoint_config=checkpoint_config)
    if cached is not None:
        return cached
    request_context = _provider_request_context(
        client, model, checkpoint_label)
    request_context.update(dict(request_context_extra or {}))
    request_context["request_fingerprint"] = _response_checkpoint_key(
        client, model, kwargs, requested_format, checkpoint_label)[:16]
    result = _chat_create_with_compat_uncached(
        client, model, kwargs, requested_format=requested_format,
        request_context=request_context, cancel_check=cancel_check,
        retry_delays=retry_delays)
    _response_checkpoint_save(
        client, model, kwargs, result, requested_format=requested_format,
        checkpoint_label=checkpoint_label,
        checkpoint_config=checkpoint_config)
    return result


def chat_create_with_shuai_failover(
        client, model: str, kwargs: dict, requested_format=None,
        checkpoint_label="", cancel_context=None):
    """Once rota failover'i, o da tukenirse yedek API anahtari (2. grup).

    Sira onemli: rota hatasi cok daha sik ve ucuz. Anahtar degistirmek ise
    faturayi baska bir gruba yazar, o yuzden yalnizca hata anahtarin/grubun
    kendisine isaret ediyorsa yapilir (bkz. _is_api_key_or_group_error).
    """
    scope = _shuai_route_scope(checkpoint_label)
    client = _apply_active_api_key(client, scope)
    try:
        return _chat_create_with_route_failover(
            client, model, kwargs, requested_format=requested_format,
            checkpoint_label=checkpoint_label, cancel_context=cancel_context)
    except Exception as exc:
        if cancel_context is not None and cancel_context.is_cancelled():
            raise
        alternate = _switch_to_backup_api_key(client, scope, exc)
        if alternate is None:
            raise
    return _chat_create_with_route_failover(
        alternate, model, kwargs, requested_format=requested_format,
        checkpoint_label=checkpoint_label, cancel_context=cancel_context)


def _chat_create_with_route_failover(
        client, model: str, kwargs: dict, requested_format=None,
        checkpoint_label="", cancel_context=None):
    scope = _shuai_route_scope(checkpoint_label)
    routes = _shuai_route_candidates(
        getattr(client, "base_url", ""), scope=scope)
    original = normalize_shuai_api_route(getattr(client, "base_url", ""))
    with _SHUAI_FAILOVER_LOCK:
        failover_enabled = bool(_SHUAI_FAILOVER_ENABLED)
    cancel_check = (
        cancel_context.is_cancelled if cancel_context is not None else None)
    if not original or not failover_enabled:
        if cancel_context is not None:
            cancel_context.raise_if_cancelled()
            cancel_context.register(client)
        try:
            return chat_create_with_compat(
                client, model, kwargs, requested_format=requested_format,
                checkpoint_label=checkpoint_label, cancel_check=cancel_check)
        finally:
            if cancel_context is not None:
                cancel_context.unregister(client)

    claimed_any = False
    for route in routes:
        if not _shuai_claim_route(route):
            continue
        claimed_any = True
        route_client = client if route == original else _openai_client_for_route(
            client, route)
        if cancel_context is not None:
            try:
                cancel_context.raise_if_cancelled()
            except BaseException:
                # İPTAL claim ile çağrı ARASINA düşerse `probing` bayrağı
                # süreç ömrü boyunca True kalıyordu; rota daha önce hiç
                # healthy olmadıysa bir daha claim edilemiyor ve
                # cancel_check'siz bir çağrı süresiz bekleyebiliyordu
                # (bug taraması madde 5). Diğer tüm raise yolları
                # bayrağı bırakıyor; bu yol da bıraksın.
                _shuai_release_route_probe(route)
                raise
            cancel_context.register(route_client)
        started = time.monotonic()
        try:
            result = chat_create_with_compat(
                route_client, model, kwargs, requested_format=requested_format,
                checkpoint_label=checkpoint_label, cancel_check=cancel_check,
                retry_delays=(), request_context_extra={
                    "shuai_route_failover_pending": True,
                    "shuai_route": urlparse(route).hostname or route,
                })
        except Exception as exc:
            if cancel_context is not None and cancel_context.is_cancelled():
                _shuai_release_route_probe(route)
                raise
            if not _shuai_failover_error(exc):
                _shuai_release_route_probe(route)
                raise
            _shuai_record_route_result(
                route, False, time.monotonic() - started, exc=exc)
            _shuai_log(
                f"Shuai rota yanıt vermedi: {urlparse(route).hostname}; "
                "sıradaki rota deneniyor.", "warn")
        else:
            _shuai_record_route_result(
                route, True, time.monotonic() - started, response=result)
            with _SHUAI_FAILOVER_LOCK:
                _SHUAI_LAST_WORKING_ROUTES[scope] = route
                if route != original:
                    state = _SHUAI_ROUTE_STATES[route]
                    state["failovers"] = int(state.get("failovers", 0) or 0) + 1
            try:
                setattr(result, "shuai_route_used", route)
                setattr(result, "shuai_route_requested", original)
            except Exception:
                pass
            if route != original:
                # Duyuru scope basina yalnizca rota DEGISTIGINDE. Ayni rotayla
                # devam eden istekler sessiz sayilir; sonraki degisiklikte kac
                # istegin o rotayi kullandigi tek satirda bildirilir.
                with _SHUAI_FAILOVER_LOCK:
                    announced = _SHUAI_ANNOUNCED_ROUTES.get(scope, "")
                    if announced == route:
                        _SHUAI_ANNOUNCE_COUNTS[scope] = int(
                            _SHUAI_ANNOUNCE_COUNTS.get(scope, 0) or 0) + 1
                        previous_count = None
                    else:
                        previous_count = int(
                            _SHUAI_ANNOUNCE_COUNTS.get(scope, 0) or 0)
                        _SHUAI_ANNOUNCED_ROUTES[scope] = route
                        _SHUAI_ANNOUNCE_COUNTS[scope] = 1
                if previous_count is not None:
                    tail = (f" (onceki rota {previous_count} istekte kullanildi)"
                            if previous_count else "")
                    _shuai_log(
                        f"Shuai otomatik rota gecisi basarili: "
                        f"{urlparse(route).hostname}{tail}; ayni rotayla devam "
                        "eden istekler tekrar loglanmaz.", "ok")
            return result
        finally:
            if cancel_context is not None:
                cancel_context.unregister(route_client)

    if not claimed_any and routes:
        _shuai_log(
            "Shuai rota sağlık denemesi başka bir iş parçacığında sürüyor; "
            "aynı hatalı rotaya yeni istek yollamadan sonuç bekleniyor.", "info")
        with _SHUAI_ROUTE_CONDITION:
            while any(
                    _SHUAI_ROUTE_STATES[route].get("probing")
                    for route in routes):
                if cancel_check and cancel_check():
                    raise ProviderWaitCancelled(
                        "API isteği kullanıcı tarafından durduruldu")
                _SHUAI_ROUTE_CONDITION.wait(timeout=0.25)
        return chat_create_with_shuai_failover(
            client, model, kwargs, requested_format=requested_format,
            checkpoint_label=checkpoint_label, cancel_context=cancel_context)

    if claimed_any:
        _shuai_log(
            "Kullanılabilir Shuai rotaları ilk denemede yanıt vermedi; "
            "normal 5/5/5/10/30/35/40/45/45/50 saniye yeniden deneme "
            "düzenine geçiliyor.", "warn")
    else:
        _shuai_log(
            "Shuai rotaları soğuma süresinde veya başka bir istekçe "
            "doğrulanıyor; normal yeniden deneme düzenine geçiliyor.", "warn")
    if cancel_context is not None:
        cancel_context.raise_if_cancelled()
        cancel_context.register(client)
    started = time.monotonic()
    try:
        result = chat_create_with_compat(
            client, model, kwargs, requested_format=requested_format,
            checkpoint_label=checkpoint_label, cancel_check=cancel_check)
        _shuai_record_route_result(
            original, True, time.monotonic() - started, response=result)
        return result
    except Exception as exc:
        if not (cancel_context is not None and cancel_context.is_cancelled()):
            _shuai_record_route_result(
                original, False, time.monotonic() - started, exc=exc)
        raise
    finally:
        if cancel_context is not None:
            cancel_context.unregister(client)
