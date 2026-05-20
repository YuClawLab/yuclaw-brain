"""
Local profile + watchlist store at ~/.yuclaw/profile.json.

Why a JSON file (and not Postgres):
  - portable across machines via scp / dotfile manager
  - no DB dependency for read-only CLI usage on a fresh checkout
  - 600 perms keep it readable only by the owner

Schema (v1):
  {
    "watchlist":         [str, ...],   # subset of universe.json
    "alert_threshold":   0.0..1.0,     # min |Δ composite| to flag in alerts
    "channels":          {"telegram": bool, "email": bool, "slack": bool},
    "display":           {"top_n": int, "show_components": bool},
    "schema_version":    1,
    "created_at":        ISO-8601,
    "updated_at":        ISO-8601,
  }

Atomic writes: temp file in the same directory + os.replace so a crash
mid-write can never produce a half-written file. chmod 600 applied
after rename so the perms aren't lost if the temp had different perms.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UNIVERSE_PATH = Path(__file__).resolve().parent.parent / "universe.json"
PROFILE_DIR = Path(os.environ.get("YUCLAW_PROFILE_DIR",
                                  str(Path.home() / ".yuclaw")))
PROFILE_PATH = PROFILE_DIR / "profile.json"

SCHEMA_VERSION = 1

DEFAULT_PROFILE: dict[str, Any] = {
    "watchlist": [],
    "alert_threshold": 0.15,
    "channels": {"telegram": True, "email": False, "slack": False},
    "display": {"top_n": 10, "show_components": True},
    "schema_version": SCHEMA_VERSION,
}

# Public signal vocabulary — locked. Used to validate stored labels and
# to bound profile.set value parsing (alert_threshold must be a float, etc.).
PUBLIC_LABELS = {
    "STRONG_BUY", "BUY", "HOLD", "WATCH",
    "WEAKENING", "NEGATIVE_EVENT", "DOWNSIDE_WATCH",
    "RISK_ALERT",  # reserved — not currently emitted, but in the locked vocab
}


# ---------------------------------------------------------------------------
class ProfileError(ValueError):
    """User-facing validation error — CLI shows the message verbatim."""


# ---------------------------------------------------------------------------
def _universe() -> set[str]:
    u = json.loads(UNIVERSE_PATH.read_text())
    return set(u["equities"] + u["sector_etfs"] + u["broad_etfs"] + u["macro"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, content: str) -> None:
    """Write `content` to `path` atomically. Temp file lives in the same dir
    so os.replace is rename-on-same-filesystem (atomic on POSIX)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".profile.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    # Profile contains preference data that's only meaningful to its owner;
    # 600 prevents accidental readability by a shared service account.
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


# ---------------------------------------------------------------------------
def load_profile() -> dict[str, Any]:
    """Load the profile from disk; create + persist a default if missing.

    Migration is forward-only — a profile with an older schema_version is
    upgraded in place by filling in any missing keys from DEFAULT_PROFILE.
    """
    if not PROFILE_PATH.exists():
        prof = dict(DEFAULT_PROFILE)
        prof["created_at"] = _now_iso()
        prof["updated_at"] = prof["created_at"]
        save_profile(prof)
        return prof

    raw = PROFILE_PATH.read_text()
    try:
        prof = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProfileError(
            f"profile.json is not valid JSON ({e}). Move it aside (e.g. "
            f"`mv {PROFILE_PATH} {PROFILE_PATH}.broken`) and re-run to "
            "recreate defaults."
        )
    # Forward-fill any newly-added keys.
    for k, v in DEFAULT_PROFILE.items():
        if k not in prof:
            prof[k] = v
        elif isinstance(v, dict):
            for sk, sv in v.items():
                prof[k].setdefault(sk, sv)
    if "created_at" not in prof:
        prof["created_at"] = _now_iso()
    return prof


def save_profile(profile: dict[str, Any]) -> None:
    """Persist after validation. Re-validates so a caller can't write garbage."""
    validate_profile(profile)
    profile["updated_at"] = _now_iso()
    _atomic_write(PROFILE_PATH, json.dumps(profile, indent=2, sort_keys=True))


# ---------------------------------------------------------------------------
def validate_profile(profile: dict[str, Any]) -> None:
    """Raise ProfileError on any structural / range violation. Never mutates."""
    if not isinstance(profile, dict):
        raise ProfileError("profile must be a dict")

    # Watchlist
    wl = profile.get("watchlist")
    if not isinstance(wl, list):
        raise ProfileError("watchlist must be a list")
    universe = _universe()
    seen: set[str] = set()
    for t in wl:
        if not isinstance(t, str):
            raise ProfileError(f"watchlist contains a non-string entry: {t!r}")
        if t.upper() != t:
            raise ProfileError(f"watchlist ticker {t!r} must be uppercase")
        if t in seen:
            raise ProfileError(f"watchlist has duplicate ticker {t}")
        seen.add(t)
        if t not in universe:
            raise ProfileError(
                f"watchlist ticker {t} is not in the v3.0 universe "
                f"(see v3/universe.json)"
            )

    # alert_threshold
    th = profile.get("alert_threshold")
    if not isinstance(th, (int, float)) or not (0.0 <= float(th) <= 1.0):
        raise ProfileError("alert_threshold must be a number in [0.0, 1.0]")

    # channels
    ch = profile.get("channels")
    if not isinstance(ch, dict):
        raise ProfileError("channels must be a dict")
    for k in ("telegram", "email", "slack"):
        if k not in ch:
            continue  # forward-fill handles defaults; missing is OK
        if not isinstance(ch[k], bool):
            raise ProfileError(f"channels.{k} must be a boolean")

    # display
    disp = profile.get("display")
    if not isinstance(disp, dict):
        raise ProfileError("display must be a dict")
    top_n = disp.get("top_n", 10)
    if not isinstance(top_n, int) or not (1 <= top_n <= 100):
        raise ProfileError("display.top_n must be an integer in [1, 100]")
    if "show_components" in disp and not isinstance(disp["show_components"], bool):
        raise ProfileError("display.show_components must be a boolean")


# ---------------------------------------------------------------------------
# Watchlist helpers
def add_watch(ticker: str) -> str:
    """Add `ticker` to the watchlist. Returns the normalized symbol.
    Raises ProfileError on unknown ticker or duplicate (case-insensitive)."""
    t = (ticker or "").strip().upper()
    if not t:
        raise ProfileError("ticker is empty")
    if t not in _universe():
        raise ProfileError(
            f"{t} is not in the v3.0 universe — `cat v3/universe.json` to see the list"
        )
    prof = load_profile()
    if t in prof["watchlist"]:
        raise ProfileError(f"{t} is already on your watchlist")
    prof["watchlist"].append(t)
    prof["watchlist"].sort()
    save_profile(prof)
    return t


def remove_watch(ticker: str) -> str:
    t = (ticker or "").strip().upper()
    prof = load_profile()
    if t not in prof["watchlist"]:
        raise ProfileError(f"{t} is not on your watchlist")
    prof["watchlist"].remove(t)
    save_profile(prof)
    return t


# ---------------------------------------------------------------------------
# Set via dotted-key path (e.g. "channels.telegram" → channels["telegram"]).
_VALUE_PARSERS = {
    "alert_threshold": float,
    "display.top_n":    int,
    "channels.telegram": lambda v: _parse_bool(v, "channels.telegram"),
    "channels.email":    lambda v: _parse_bool(v, "channels.email"),
    "channels.slack":    lambda v: _parse_bool(v, "channels.slack"),
    "display.show_components": lambda v: _parse_bool(v, "display.show_components"),
}


def _parse_bool(raw: str, key: str) -> bool:
    v = raw.strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    raise ProfileError(f"{key}: cannot parse {raw!r} as boolean")


def set_value(key: str, raw_value: str) -> tuple[str, Any]:
    """Set profile[key] (dotted) from a string. Returns (key, parsed_value)."""
    parser = _VALUE_PARSERS.get(key)
    if parser is None:
        raise ProfileError(
            f"unknown profile key {key!r}. "
            f"Settable keys: {sorted(_VALUE_PARSERS)}"
        )
    try:
        parsed = parser(raw_value)
    except ProfileError:
        raise
    except (ValueError, TypeError) as e:
        raise ProfileError(f"{key}: cannot parse {raw_value!r}: {e}")

    prof = load_profile()
    parts = key.split(".")
    cur: Any = prof
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = parsed
    save_profile(prof)
    return key, parsed
