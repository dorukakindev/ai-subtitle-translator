"""
credential_store.py — Secure API key storage for Subtitle Translator.

Primary: OS credential manager via `keyring` library.
Fallback: Obfuscated local file (NOT cryptographically secure, but better
          than plain text in .gui_settings.json).
"""

import base64
import binascii
import hashlib
import json
import os
import platform
import re
import sys
import threading
import uuid
from pathlib import Path

from app_state import _interprocess_lock, atomic_write_json

SERVICE_NAME = "SubtitleTranslator"

# ── Fallback file path ──────────────────────────────────────────────────────
def _fallback_path() -> Path:
    return Path(__file__).parent / ".credentials"


def _machine_key() -> bytes:
    """Derive a machine-specific key from username + hostname + OS.

    This is NOT cryptographic-grade security. It merely obfuscates the
    stored keys so they are not readable at a glance. A determined attacker
    with source code access can reverse this. Use `keyring` for real security.
    """
    identity = f"{platform.node()}|{os.getenv('USERNAME','')}|{platform.system()}"
    return hashlib.sha256(identity.encode("utf-8")).digest()


def _obfuscate(text: str) -> str:
    key = _machine_key()
    raw = text.encode("utf-8")
    xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
    return base64.b64encode(xored).decode("ascii")


def _deobfuscate(token: str) -> str:
    key = _machine_key()
    try:
        raw = base64.b64decode(token)
        xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
        return xored.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as e:
        print(f"[cred] fallback anahtar okunamadı: {e}", file=sys.stderr)
        raise


# ── keyring helpers ──────────────────────────────────────────────────────────

_keyring_available = None
_fallback_lock = threading.Lock()

def _has_keyring() -> bool:
    global _keyring_available
    if _keyring_available is None:
        try:
            import keyring
            keyring.get_password("__subtitle_translator_probe__", "__probe__")
            _keyring_available = True
        except Exception as e:
            print(f"[cred] keyring kullanılamıyor, fallback aktif: {e}", file=sys.stderr)
            _keyring_available = False
    return _keyring_available


# ── Public API ───────────────────────────────────────────────────────────────

def save_key(service: str, key: str) -> bool:
    """Store an API key. Returns True if keyring was used (secure)."""
    if not key:
        return False

    if _has_keyring():
        try:
            import keyring
            keyring.set_password(SERVICE_NAME, service, key)
            _cleanup_fallback(service)  # remove legacy fallback if present
            return True
        except Exception:
            pass  # fall through to fallback

    # Fallback: obfuscated file
    _save_fallback(service, key)
    return False


def load_key(service: str) -> str | None:
    """Retrieve an API key. Returns None if not found."""
    if _has_keyring():
        try:
            import keyring
            val = keyring.get_password(SERVICE_NAME, service)
            if val is not None:
                return val
        except Exception:
            pass  # fall through to fallback

    return _load_fallback(service)


def delete_key(service: str) -> None:
    """Remove a stored API key from all stores."""
    if _has_keyring():
        try:
            import keyring
            keyring.delete_password(SERVICE_NAME, service)
        except Exception:
            pass

    _cleanup_fallback(service)


def is_secure() -> bool:
    """Return True if keyring is available (keys stored in OS credential manager)."""
    return _has_keyring()


# ── Fallback file I/O ───────────────────────────────────────────────────────

def _read_fallback_store() -> dict:
    p = _fallback_path()
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_fallback_store(data: dict) -> None:
    p = _fallback_path()
    atomic_write_json(p, data)
    # Obfuscation zayıf; en azından dosyayı diğer kullanıcılardan gizle (yalnız sahibine okunur).
    try:
        import os
        import subprocess
        user = os.environ.get("USERNAME") or ""
        domain = os.environ.get("USERDOMAIN") or ""
        principal = f"{domain}\\{user}" if domain and user else user
        if principal:
            subprocess.run(
                ["icacls", str(p), "/grant:r", f"{principal}:F"],
                check=False, capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        pass


def _save_fallback(service: str, key: str) -> None:
    with _fallback_lock:
        with _interprocess_lock(_fallback_path()):
            store = _read_fallback_store()
            store[service] = _obfuscate(key)
            _write_fallback_store(store)


def _load_fallback(service: str) -> str | None:
    with _interprocess_lock(_fallback_path()):
        store = _read_fallback_store()
    token = store.get(service)
    if token is None:
        return None
    try:
        return _deobfuscate(token)
    except Exception:
        return None


def _cleanup_fallback(service: str) -> None:
    with _fallback_lock:
        with _interprocess_lock(_fallback_path()):
            store = _read_fallback_store()
            if service in store:
                del store[service]
                _write_fallback_store(store)


def _atomic_write_settings_json(path: Path, data: dict) -> None:
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            try:
                os.chmod(tmp, path.stat().st_mode)
            except OSError:
                pass
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


# ── Migration helper ─────────────────────────────────────────────────────────

def migrate_from_settings(settings_path: str | Path) -> None:
    """Move API keys from .gui_settings.json into the credential store.

    After migration, the keys are removed from the JSON file so they are
    no longer stored in plain text.
    """
    p = Path(settings_path)
    if not p.exists():
        return

    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return

    service_names = {
        "api": "openai",
        "openai": "openai",
        "helper": "openai_helper",
        "minimax": "minimax",
        "deepseek": "deepseek",
        "gemini": "gemini",
        "anthropic": "anthropic",
        "claude": "anthropic",
        "bedrock": "bedrock",
        "groq": "groq",
        "mistral": "mistral",
        "main_custom": "main_custom",
        "openai_helper": "openai_helper",
    }
    key_pattern = re.compile(r"^(.+?)_(key|secret|token)$", re.IGNORECASE)

    changed = False
    # Rol özel yardımcı anahtarları: helper_role_key_<role> -> helper_role_<role>_key
    role_key_pattern = re.compile(r"^helper_role_key_(.+)$", re.IGNORECASE)
    custom_role_key_pattern = re.compile(r"^helper_custom_key_(.+)$", re.IGNORECASE)
    for key_name in list(data.keys()):
        # .get(.., "") yalnızca eksik anahtarı korur; JSON null (None) gelirse
        # .strip() patlar — `or ""` ile None/yanlış-tip güvenli
        raw_value = data.get(key_name)
        val = raw_value.strip() if isinstance(raw_value, str) else ""
        if not val or len(val) <= 5:
            continue

        rk_match = role_key_pattern.match(key_name)
        if rk_match:
            role = rk_match.group(1).lower()
            save_key(f"helper_role_{role}_key", val)
            del data[key_name]
            changed = True
            continue

        custom_match = custom_role_key_pattern.match(key_name)
        if custom_match:
            role = custom_match.group(1).lower()
            save_key(f"helper_role_{role}_key", val)
            del data[key_name]
            changed = True
            continue

        match = key_pattern.match(key_name)
        if not match:
            continue
        prefix = match.group(1).lower()
        service = service_names.get(prefix)
        if not service and prefix.startswith("helper_"):
            service = f"{prefix}_key"
        if not service:
            continue
        save_key(service, val)
        del data[key_name]
        changed = True

    if changed:
        _atomic_write_settings_json(p, data)
