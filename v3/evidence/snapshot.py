"""
Published-corpus snapshot (v5.3.2) — the offline fallback for the
Evidence Passport.

corpus_snapshot.json.gz is built at release time from docs/why/*.json —
the SAME published evidence_objects served at
https://yuclaw.ca/why/{TICKER}.json (up to the why-JSON per-name cap of
100 most-recent objects) — and ships inside the wheel, so a valid
structured claim resolves on a machine with no research node instead of
crashing. Loudly scoped, never silently authoritative: a negative
status offline means "not found in the bundled snapshot"; the passport
carries the snapshot date, the per-name cap, and the live URL to
confirm against.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

SNAPSHOT_PATH = Path(__file__).resolve().parent / "corpus_snapshot.json.gz"
# mirrors render_why_json's evidence_objects(limit=100) — the published cap
PER_NAME_CAP = 100


def load_snapshot() -> dict | None:
    """The bundled snapshot as {'source', 'generated', 'per_name_cap',
    'names': {TICKER: [EvidenceObject, ...]}} — or None when the file is
    missing or unreadable (callers then fail with the friendly
    research-node message, never a traceback)."""
    try:
        with gzip.open(SNAPSHOT_PATH, "rt", encoding="utf-8") as f:
            snap = json.load(f)
    except (OSError, ValueError):
        return None
    return snap if isinstance(snap, dict) and "names" in snap else None


def snapshot_corpus(ticker: str) -> tuple[list, dict] | None:
    """The bundled snapshot's objects for `ticker` plus the loud 'corpus'
    scope block every offline surface attaches (CLI passport since
    v5.3.2, MCP since v5.3.3 — ONE builder so they cannot diverge) — or
    None when no readable snapshot ships with this install."""
    snap = load_snapshot()
    if snap is None:
        return None
    t = ticker.upper()
    url = f"https://yuclaw.ca/why/{t}.json"
    return snap["names"].get(t, []), {
        "mode": "offline_snapshot",
        "snapshot_generated": snap.get("generated"),
        "scope": (f"published corpus snapshot bundled with this "
                  f"install — the same evidence_objects served at "
                  f"{url}, up to {snap.get('per_name_cap')} "
                  f"most-recent objects per name"),
        "confirm": (f"negative statuses here mean 'not found in the "
                    f"bundled snapshot' — confirm against {url} or a "
                    f"research node"),
    }


def build_snapshot(why_dir: str | Path,
                   out_path: str | Path = SNAPSHOT_PATH) -> dict:
    """Release-time builder: fold the published why-JSON evidence_objects
    for every scoring-universe name into one deterministic gzip (mtime=0,
    sorted keys — same inputs, byte-identical artifact)."""
    from v3.universe_tiers import scoring_universe
    names, gens = {}, []
    for t in sorted(scoring_universe()):
        p = Path(why_dir) / f"{t}.json"
        if not p.exists():
            raise FileNotFoundError(
                f"missing published why-JSON for {t}: {p} — refresh "
                f"docs/why before building the snapshot")
        d = json.loads(p.read_text())
        names[t] = d.get("evidence_objects", [])
        gens.append(d.get("generated") or "")
    snap = {
        "source": "published why-JSON evidence_objects "
                  "(https://yuclaw.ca/why/{TICKER}.json)",
        "generated": max(gens),
        "per_name_cap": PER_NAME_CAP,
        "names": names,
    }
    out_path = Path(out_path)
    out_path.write_bytes(gzip.compress(
        json.dumps(snap, sort_keys=True).encode(), mtime=0))
    return {"names": len(names),
            "objects": sum(len(v) for v in names.values()),
            "bytes": out_path.stat().st_size}


if __name__ == "__main__":
    import sys
    why = sys.argv[1] if len(sys.argv) > 1 else "docs/why"
    print(json.dumps(build_snapshot(why)))
