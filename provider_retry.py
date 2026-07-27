import email.utils
import hashlib
import json
import re
import threading
import time
from datetime import datetime, timezone


_RETRY_DELAY_RE = re.compile(
    r'(?i)(?:retry[_ -]?(?:after|delay)|retryDelay|try\s+again\s+in)["\']?'
    r'\s*[:=]?\s*["\']?'
    r'(\d+(?:\.\d+)?)\s*(ms|milliseconds?|s|sec(?:onds?)?)?'
)


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
    def __init__(self, clock=None, sleeper=None, retry_spacing: float = 0.25):
        self._clock = clock or time.monotonic
        self._sleep = sleeper or time.sleep
        self._retry_spacing = max(0.0, float(retry_spacing))
        self._lock = threading.Lock()
        self._cooldown_until = {}
        self._next_slot = {}

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
            self._sleep(wait)
        return wait

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


def before_provider_request(client) -> float:
    return _REGISTRY.before_request(client)


def record_provider_failure(client, exc) -> float | None:
    return _REGISTRY.record_rate_limit(client, exc)
