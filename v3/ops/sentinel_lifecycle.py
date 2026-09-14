"""Sentinel lifecycle model (v7 P2 proposal; NOT a policy change). A pure, testable model of the rules the
launcher `services/sentinel_nightly.sh` enforces today — solo-session rule (supervised bypass), lock, prompt
pin, 25-minute bound, forbidden-path authority check with revert, push-after-verify — so that refusals and
outcomes can be classified and reported (e.g. by the nightly-status adapter) without inferring or changing the
policy. The model never terminates a session, never disables the guard and never runs anything."""
from __future__ import annotations

from dataclasses import dataclass, field

FORBIDDEN_PREFIXES = ("registry/protocols.jsonl", "v3/universe.json", "v3/signal/base.py", "v3/universe_tiers.py", "v3/u350/", "tools/check_", "tools/yuclaw_c6", "tools/yuclaw_reversal", "services/c6_")
WALL_CLOCK_BOUND_S = 1500
OUTCOMES = ("REFUSED_SOLO_SESSION", "REFUSED_LOCK_HELD", "REFUSED_PROMPT_TAMPER", "RAN_NO_COMMITS", "RAN_PUSHED", "RAN_PUSH_FAILED", "AUTHORITY_VIOLATION_REVERTED", "TIMED_OUT")


@dataclass
class Decision:
    outcome: str
    reason: str = ""
    exit_code: int = 0
    alert: str | None = None
    details: dict = field(default_factory=dict)


def preflight(*, live_sessions: int, supervised: bool, lock_held: bool, prompt_sha256: str, prompt_pin: str) -> Decision | None:
    """Mirror of the launcher's refusal order: solo-session (unless supervised) → lock → prompt pin. None = may run."""
    if not supervised and live_sessions > 0:
        return Decision("REFUSED_SOLO_SESSION", f"{live_sessions} live Claude session(s) — solo-session rule", 0)
    if lock_held:
        return Decision("REFUSED_LOCK_HELD", "another sentinel run is live", 0)
    if prompt_sha256 != prompt_pin:
        return Decision("REFUSED_PROMPT_TAMPER", "prompt hash != pin (tamper-evident)", 1, alert="SENTINEL refused: prompt hash mismatch")
    return None


def postflight(*, runtime_s: float, head_moved: bool, changed_paths: list[str], push_ok: bool | None) -> Decision:
    """Mirror of the post-run authority check: forbidden-path touch → hard reset + CRITICAL alert; else push-after-verify."""
    if runtime_s >= WALL_CLOCK_BOUND_S:
        base = Decision("TIMED_OUT", f"runtime {runtime_s:.0f}s reached the {WALL_CLOCK_BOUND_S}s bound", 124)
        if not head_moved:
            return base
    if not head_moved:
        return Decision("RAN_NO_COMMITS", "session made no commit", 0, details={"runtime_s": runtime_s})
    bad = [p for p in changed_paths if p.startswith(FORBIDDEN_PREFIXES)]
    if bad:
        return Decision("AUTHORITY_VIOLATION_REVERTED", "forbidden paths touched — hard reset to HEAD_BEFORE", 0, alert=f"SENTINEL CRITICAL: authority violation reverted ({', '.join(bad)})", details={"paths": bad})
    if push_ok:
        return Decision("RAN_PUSHED", "commit(s) pushed after the authority check", 0, details={"paths": changed_paths})
    return Decision("RAN_PUSH_FAILED", "push failed after retry", 0, alert="SENTINEL: push failed after retry", details={"paths": changed_paths})


def classify_log_entry(entry: dict) -> str:
    """Map a launcher log line to an OUTCOME without reading the session's content."""
    text = " ".join(str(v) for v in entry.values()).lower()
    if "solo-session" in text: return "REFUSED_SOLO_SESSION"
    if "lock held" in text: return "REFUSED_LOCK_HELD"
    if "prompt hash" in text: return "REFUSED_PROMPT_TAMPER"
    if "authority violation" in text: return "AUTHORITY_VIOLATION_REVERTED"
    if entry.get("pushed") in ("yes", True): return "RAN_PUSHED"
    if entry.get("commits") in (0, "0") or entry.get("n_commits") in (0, "0"): return "RAN_NO_COMMITS"
    return "RAN_PUSH_FAILED" if "push failed" in text else "UNCLASSIFIED"
