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
from urllib.parse import urlparse

from app_state import atomic_write_json


_RETRY_DELAY_RE = re.compile(
    r'(?i)(?:retry[_ -]?(?:after|delay)|retryDelay|try\s+again\s+in)["\']?'
    r'\s*[:=]?\s*["\']?'
    r'(\d+(?:\.\d+)?)\s*(ms|milliseconds?|s|sec(?:onds?)?)?'
)

TRANSIENT_RETRY_DELAYS = (30.0, 60.0, 120.0)
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
    text = str(exc or "").casefold()
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
    text = str(exc or "").lower()
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


def _wait_for_transient_retry(exc, attempt: int, total: int, details=None) -> float:
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


def _provider_call_once(call, client, model: str, request_context=None,
                        cancel_check=None):
    total = len(TRANSIENT_RETRY_DELAYS)
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
                details["will_retry"] = bool(retryable)
                _REGISTRY.request_finished(
                    client, False, model, details, request_id=request_id)
                record_provider_failure(client, exc, model, details)
                if not retryable:
                    raise
                previous_context = getattr(_REQUEST_CONTEXT, "value", None)
                _REQUEST_CONTEXT.value = base_context
                try:
                    _wait_for_transient_retry(exc, attempt + 1, total)
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
                             cancel_check=None):
    return _provider_call_once(
        call, client, model, request_context, cancel_check=cancel_check)


def _chat_create_once(client, kwargs: dict, request_context=None):
    request_client = _without_sdk_retries(client)
    return _provider_call_once(
        lambda: request_client.chat.completions.create(**kwargs),
        client,
        kwargs.get("model", ""),
        request_context,
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
                                      requested_format=None, request_context=None):
    plain = copy.deepcopy(kwargs)
    if not _is_custom_gpt5(client, model):
        return _chat_create_once(client, plain, request_context)

    structured = copy.deepcopy(plain)
    if requested_format is not None:
        structured["response_format"] = copy.deepcopy(requested_format)
    else:
        structured = _translation_schema_kwargs(structured)
    if structured is None:
        return _chat_create_once(client, plain, request_context)

    key = _structured_key(client, model)
    with _STRUCTURED_LOCK:
        state = _STRUCTURED_STATES.get(key)
        probe_lock = _STRUCTURED_PROBE_LOCKS.setdefault(key, threading.Lock())
    if state is False:
        return _chat_create_once(client, plain, request_context)

    lock = probe_lock if state is None else threading.Lock()
    with lock:
        with _STRUCTURED_LOCK:
            state = _STRUCTURED_STATES.get(key)
        if state is False:
            return _chat_create_once(client, plain, request_context)
        try:
            result = _chat_create_once(client, structured, request_context)
        except Exception as exc:
            if not _structured_unsupported(exc):
                raise
            with _STRUCTURED_LOCK:
                _STRUCTURED_STATES[key] = False
            return _chat_create_once(client, plain, request_context)
        with _STRUCTURED_LOCK:
            _STRUCTURED_STATES[key] = True
        return result


def chat_create_with_compat(client, model: str, kwargs: dict, requested_format=None,
                            checkpoint_label=""):
    checkpoint_config = _response_checkpoint_snapshot()
    cached = _response_checkpoint_lookup(
        client, model, kwargs, requested_format=requested_format,
        checkpoint_label=checkpoint_label,
        checkpoint_config=checkpoint_config)
    if cached is not None:
        return cached
    request_context = _provider_request_context(
        client, model, checkpoint_label)
    request_context["request_fingerprint"] = _response_checkpoint_key(
        client, model, kwargs, requested_format, checkpoint_label)[:16]
    result = _chat_create_with_compat_uncached(
        client, model, kwargs, requested_format=requested_format,
        request_context=request_context)
    _response_checkpoint_save(
        client, model, kwargs, result, requested_format=requested_format,
        checkpoint_label=checkpoint_label,
        checkpoint_config=checkpoint_config)
    return result
