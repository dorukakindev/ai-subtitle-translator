import email.utils
import hashlib
import copy
import json
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app_state import atomic_write_json


_RETRY_DELAY_RE = re.compile(
    r'(?i)(?:retry[_ -]?(?:after|delay)|retryDelay|try\s+again\s+in)["\']?'
    r'\s*[:=]?\s*["\']?'
    r'(\d+(?:\.\d+)?)\s*(ms|milliseconds?|s|sec(?:onds?)?)?'
)

TRANSIENT_RETRY_DELAYS = (10.0, 20.0, 30.0, 40.0, 120.0)
RESPONSE_CHECKPOINT_VER = 1

_RESPONSE_CHECKPOINT_LOCK = threading.Lock()
_RESPONSE_CHECKPOINT = None


def _response_checkpoint_namespace_dir(root: Path, namespace: str) -> Path:
    digest = hashlib.sha256(str(namespace).encode("utf-8", "replace")).hexdigest()
    return Path(root) / digest


def configure_response_checkpoint(path=None, namespace: str = "",
                                  allow_reads: bool = False,
                                  hit_callback=None) -> None:
    global _RESPONSE_CHECKPOINT
    with _RESPONSE_CHECKPOINT_LOCK:
        if path is None or not str(namespace).strip():
            _RESPONSE_CHECKPOINT = None
            return
        _RESPONSE_CHECKPOINT = {
            "path": Path(path),
            "namespace": str(namespace),
            "allow_reads": bool(allow_reads),
            "hit_callback": hit_callback,
            "hits": 0,
            "consumed": set(),
        }


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
                             requested_format=None) -> str:
    payload = {
        "base_url": str(getattr(client, "base_url", "") or "").rstrip("/").lower(),
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
    return SimpleNamespace(choices=[choice], usage=None)


def _response_checkpoint_lookup(client, model: str, kwargs: dict,
                                requested_format=None):
    with _RESPONSE_CHECKPOINT_LOCK:
        config = dict(_RESPONSE_CHECKPOINT or {})
    if not config or not config.get("allow_reads"):
        return None
    key = _response_checkpoint_key(client, model, kwargs, requested_format)
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
    with _RESPONSE_CHECKPOINT_LOCK:
        current = _RESPONSE_CHECKPOINT
        if (current and current.get("path") == root
                and current.get("namespace") == namespace):
            if key in current.setdefault("consumed", set()):
                return None
            current["consumed"].add(key)
            current["hits"] = int(current.get("hits", 0)) + 1
            hits = current["hits"]
            callback = current.get("hit_callback")
    if callback:
        try:
            callback(hits)
        except Exception:
            pass
    return _cached_chat_response(entry)


def _response_checkpoint_save(client, model: str, kwargs: dict, response,
                              requested_format=None) -> None:
    with _RESPONSE_CHECKPOINT_LOCK:
        config = dict(_RESPONSE_CHECKPOINT or {})
    if not config:
        return
    try:
        choice = response.choices[0]
        content = choice.message.content
    except Exception:
        return
    finish_reason = getattr(choice, "finish_reason", None)
    if finish_reason not in (None, "stop"):
        return
    key = _response_checkpoint_key(client, model, kwargs, requested_format)
    root = config["path"]
    namespace = config["namespace"]
    entry = {
        "version": RESPONSE_CHECKPOINT_VER,
        "content": content,
        "finish_reason": finish_reason,
        "updated_at": time.time(),
    }
    try:
        entry_path = _response_checkpoint_namespace_dir(
            root, namespace) / f"{key}.json"
        atomic_write_json(entry_path, entry)
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
            r"(?i)\b(?:http|status(?:\s+code)?|error\s+code)\s*[:=]?\s*(\d{3})\b",
            text,
        )
        return int(match.group(1)) if match else None


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


def retry_after_seconds(exc, default: float = 2.0, maximum: float = 600.0) -> float:
    headers = _headers(exc)
    retry_ms = _header_value(headers, "retry-after-ms")
    if retry_ms is not None:
        try:
            return min(maximum, max(0.0, float(retry_ms) / 1000.0))
        except (TypeError, ValueError):
            pass

    header_delay = _retry_after_header_seconds(_header_value(headers, "retry-after"))
    if header_delay is not None:
        return min(maximum, header_delay)

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
    base_url = str(getattr(client, "base_url", "") or "").lower().rstrip("/")
    api_key = getattr(client, "api_key", "")
    getter = getattr(api_key, "get_secret_value", None)
    if callable(getter):
        try:
            api_key = getter()
        except Exception:
            api_key = ""
    digest = hashlib.sha256(str(api_key or "").encode("utf-8")).hexdigest()[:12]
    return f"{base_url}|{digest}"


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
        self._cancel_check = cancel_check
        self._wait_callback = wait_callback
        self._lock = threading.Lock()
        self._cooldown_until = {}
        self._next_slot = {}
        self._waiting = 0

    def set_hooks(self, cancel_check=None, wait_callback=None):
        with self._lock:
            self._cancel_check = cancel_check
            self._wait_callback = wait_callback

    def _notify(self, event: str, remaining: float):
        callback = self._wait_callback
        if callback:
            try:
                callback(event, max(0, int(remaining + 0.999)), self._waiting)
            except Exception:
                pass

    def before_request(self, client) -> float:
        key = _client_key(client)
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
            self._notify("start", wait)
            deadline = self._clock() + wait
            last_second = None
            try:
                while True:
                    if self._cancel_check and self._cancel_check():
                        raise ProviderWaitCancelled("API kota beklemesi kullanıcı tarafından durduruldu")
                    remaining = deadline - self._clock()
                    if remaining <= 0:
                        break
                    second = int(remaining + 0.999)
                    if second != last_second:
                        last_second = second
                        self._notify("tick", remaining)
                    self._sleep(min(0.25, remaining))
            finally:
                with self._lock:
                    self._waiting = max(0, self._waiting - 1)
                self._notify("end", 0.0)
        return wait

    def wait_for_retry(self, delay: float, attempt: int, total: int) -> float:
        wait = max(0.0, float(delay))
        if wait <= 0.0:
            return 0.0
        with self._lock:
            self._waiting += 1
        prefix = f"retry_{{}}_{int(attempt)}_{int(total)}"
        self._notify(prefix.format("start"), wait)
        deadline = self._clock() + wait
        last_second = None
        try:
            while True:
                if self._cancel_check and self._cancel_check():
                    raise ProviderWaitCancelled(
                        "API yeniden deneme beklemesi kullanıcı tarafından durduruldu")
                remaining = deadline - self._clock()
                if remaining <= 0:
                    break
                second = int(remaining + 0.999)
                if second != last_second:
                    last_second = second
                    self._notify(prefix.format("tick"), remaining)
                self._sleep(min(0.25, remaining))
        finally:
            with self._lock:
                self._waiting = max(0, self._waiting - 1)
            self._notify(prefix.format("end"), 0.0)
        return wait

    def notify_retry_success(self, attempt: int, total: int) -> None:
        self._notify(f"retry_success_{int(attempt)}_{int(total)}", 0.0)

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


def before_provider_request(client) -> float:
    return _REGISTRY.before_request(client)


def record_provider_failure(client, exc) -> float | None:
    return _REGISTRY.record_rate_limit(client, exc)


def configure_provider_wait_hooks(cancel_check=None, wait_callback=None):
    _REGISTRY.set_hooks(cancel_check=cancel_check, wait_callback=wait_callback)


def _is_transient_provider_error(exc) -> bool:
    text = str(exc or "").lower()
    status = _status_code(exc)
    if status in {400, 401, 403, 404, 409, 422}:
        return False
    if any(marker in text for marker in (
        "invalid api key",
        "insufficient_quota",
        "pre_consume_token_quota_failed",
        "token quota is not enough",
    )):
        return False
    if "model_not_found" in text and any(marker in text for marker in (
        "no available channel",
        "failed to get available channel",
        "auto groups is not enabled",
    )):
        return False
    return (
        status in {408, 429, 500, 502, 503, 504, 529}
        or "rate limit" in text
        or "temporarily unavailable" in text
        or "timeout" in text
        or "connection" in text
        or "server error" in text
        or "internal error" in text
    )


def _wait_for_transient_retry(exc, attempt: int, total: int) -> float:
    scheduled = TRANSIENT_RETRY_DELAYS[attempt - 1]
    return _REGISTRY.wait_for_retry(scheduled, attempt, total)


def _is_custom_gpt5(client, model: str) -> bool:
    base_url = str(getattr(client, "base_url", "") or "").lower().rstrip("/")
    return (
        (str(model or "").lower().startswith("gpt-5"))
        and "api.openai.com" not in base_url
        and bool(base_url)
    )


def _structured_key(client, model: str) -> str:
    base_url = str(getattr(client, "base_url", "") or "").lower().rstrip("/")
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
    instruction = {
        "role": "developer",
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
    ))
    unsupported = any(marker in text for marker in (
        "not support", "unsupported", "unknown parameter", "unrecognized",
        "extra_forbidden", "invalid parameter", "invalid schema",
        "schema for response_format", "invalid value", "supported values",
        "must be one of", "not permitted",
    ))
    return parameter and unsupported


def _chat_create_once(client, kwargs: dict):
    total = len(TRANSIENT_RETRY_DELAYS)
    for attempt in range(total + 1):
        before_provider_request(client)
        try:
            result = client.chat.completions.create(**kwargs)
            if attempt:
                _REGISTRY.notify_retry_success(attempt, total)
            return result
        except Exception as exc:
            record_provider_failure(client, exc)
            if attempt >= total or not _is_transient_provider_error(exc):
                raise
            _wait_for_transient_retry(exc, attempt + 1, total)


def _chat_create_with_compat_uncached(client, model: str, kwargs: dict,
                                      requested_format=None):
    plain = copy.deepcopy(kwargs)
    if not _is_custom_gpt5(client, model):
        return _chat_create_once(client, plain)

    structured = copy.deepcopy(plain)
    if requested_format is not None:
        structured["response_format"] = copy.deepcopy(requested_format)
    else:
        structured = _translation_schema_kwargs(structured)
    if structured is None:
        return _chat_create_once(client, plain)

    key = _structured_key(client, model)
    with _STRUCTURED_LOCK:
        state = _STRUCTURED_STATES.get(key)
        probe_lock = _STRUCTURED_PROBE_LOCKS.setdefault(key, threading.Lock())
    if state is False:
        return _chat_create_once(client, plain)

    lock = probe_lock if state is None else threading.Lock()
    with lock:
        with _STRUCTURED_LOCK:
            state = _STRUCTURED_STATES.get(key)
        if state is False:
            return _chat_create_once(client, plain)
        try:
            result = _chat_create_once(client, structured)
        except Exception as exc:
            if not _structured_unsupported(exc):
                raise
            with _STRUCTURED_LOCK:
                _STRUCTURED_STATES[key] = False
            return _chat_create_once(client, plain)
        with _STRUCTURED_LOCK:
            _STRUCTURED_STATES[key] = True
        return result


def chat_create_with_compat(client, model: str, kwargs: dict, requested_format=None):
    cached = _response_checkpoint_lookup(
        client, model, kwargs, requested_format=requested_format)
    if cached is not None:
        return cached
    result = _chat_create_with_compat_uncached(
        client, model, kwargs, requested_format=requested_format)
    _response_checkpoint_save(
        client, model, kwargs, result, requested_format=requested_format)
    return result
