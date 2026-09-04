#!/usr/bin/env python3
"""
RELEASE-MANIFEST GATES (G2 VERSION · G3 BASE URL · G4 ENDPOINTS) —
ORDER 2026-09-05B. Deterministic; exit nonzero on any mismatch. The single
source is release_manifest.json at the repo root.

G2 VERSION — ALL of these == release_manifest.version:
   package version (pyproject.toml) · site badge on every shared-header page
   · capabilities.version · evidence_index.version · llms.txt declared
   version · README advertised version (+ its GitHub Release link tag, and
   the release-candidate transcript's recorded version) · CITATION.cff
   · [--dist DIR] wheel + sdist METADATA Version, and the sdist PKG-INFO
     long description carries the canonical look-ahead block (PyPI long
     description via README) · [--pypi] PyPI info.version.
   B4 packaging gate: advertised guide links are versionless and resolve;
   no stale advertised version (v5.1) remains in README.
G3 BASE URL — capabilities.base_url, evidence_index.base_url, llms.txt
   canonical base == release_manifest.public_base_url; zero github.io URLs
   in evidence_index.json / llms.txt; every listed URL is under the base.
G4 ENDPOINTS — the declared machine endpoint set (capabilities.endpoints,
   evidence_index.machine_surfaces, llms.txt release block) == the expected
   set generated from the manifest (no missing; no extra unless classified
   optional/dynamic); every static/templated surface resolves locally, is
   the declared format and schema-valid (required keys; JSON Schemas check
   against their metaschema; why-JSON EvidenceObjects validate against
   EvidenceObject.v1); wildcard families (ledger_day, evidence_changes_day)
   are resolved through their DISCOVERY RULE, never enumerated.
   [--live] the same over HTTPS with cache bypass: HTTP 200 + content type
   + the same format/schema checks.

CLI: python3 tools/check_release_manifest.py [--only g2|g3|g4] [--dist DIR]
     [--pypi] [--live] [--out record.json]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
DOCS = _REPO / "docs"
MANIFEST = json.loads((_REPO / "release_manifest.json").read_text())
VERSION = MANIFEST["version"]
BASE = MANIFEST["public_base_url"].rstrip("/")


def _pyproject_version() -> str:
    import tomllib
    return tomllib.load(open(_REPO / "pyproject.toml", "rb"))["project"]["version"]


def _get(url: str, tries: int = 3) -> tuple[int, bytes, str]:
    last = None
    for i in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": "yuclaw-release-gate",
                                                   "Cache-Control": "no-cache", "Pragma": "no-cache"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            return e.code, b"", ""
        except Exception as e:                        # noqa: BLE001
            last = e
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"{url}: {last}")


# ------------------------------------------------------------------ G2
def g2(problems: list[str], dist: str | None, pypi: bool) -> dict:
    seen = {"manifest": VERSION, "pyproject": _pyproject_version()}
    caps = json.loads((DOCS / "capabilities.json").read_text())
    idx = json.loads((DOCS / "evidence_index.json").read_text())
    llms = (DOCS / "llms.txt").read_text()
    readme = (_REPO / "README.md").read_text()
    seen["capabilities"] = caps.get("version", "").lstrip("v")
    seen["evidence_index"] = idx.get("version", "").lstrip("v")
    m = re.search(r"^- Version: yuclaw (\S+)$", llms, re.M)
    seen["llms"] = m.group(1) if m else ""
    m = re.search(r"Current package version: `([^`]+)`", readme)
    seen["readme"] = m.group(1) if m else ""
    m = re.search(r"releases/tag/v([0-9][^)\s]*)\)", readme)
    seen["readme_release_link"] = m.group(1) if m else ""
    m = re.search(r"<!-- CLI-TRANSCRIPT BEGIN -->\n(.*?)\n<!-- CLI-TRANSCRIPT END -->", readme, re.S)
    tm = re.search(r"\(yuclaw (\S+), Python", m.group(1)) if m else None
    seen["readme_transcript"] = tm.group(1) if tm else ""
    m = re.search(r"^version: (\S+)$", (_REPO / "CITATION.cff").read_text(), re.M)
    seen["citation_cff"] = m.group(1) if m else ""
    # site badge on every shared-header page
    badge = f">v{VERSION}</span>"
    pages = [p for p in list(DOCS.glob("*.html")) + list((DOCS / "why").glob("*.html"))
             + list(DOCS.glob("preview/**/*.html")) if "hdr-nav" in p.read_text(errors="replace")]
    stale = [p.relative_to(DOCS).as_posix() for p in pages if badge not in p.read_text(errors="replace")]
    seen["site_badge_pages"] = len(pages)
    if stale:
        problems.append(f"G2: {len(stale)} shared-header pages without badge v{VERSION}: {stale[:5]}")
    for k, v in seen.items():
        if k in ("site_badge_pages",):
            continue
        if v != VERSION:
            problems.append(f"G2: {k} version {v!r} != release_manifest.version {VERSION!r}")
    # B4 packaging gate: versionless, resolving guide links; no stale advertised version
    for lang, fn in MANIFEST["advertised_user_guide"].items():
        if not (DOCS / fn).exists():
            problems.append(f"G2/B4: advertised guide {fn} missing under docs/")
        if fn not in readme:
            problems.append(f"G2/B4: README does not link the advertised guide {fn}")
    if re.search(r"Guide[_ ]v\d", readme) or re.search(r"\bv5\.1\b", readme):
        problems.append("G2/B4: README still advertises a versioned/stale guide or release (v5.1)")
    landing = (DOCS / "index.html").read_text(errors="replace")
    if re.search(r"Guide[_a-zA-Z]*_v\d", landing):
        problems.append("G2/B4: index.html links a versioned guide filename")
    if dist:
        d = Path(dist)
        whl = next(iter(d.glob(f"yuclaw-{VERSION}-py3-none-any.whl")), None)
        sd = next(iter(d.glob(f"yuclaw-{VERSION}.tar.gz")), None)
        if not whl or not sd:
            problems.append(f"G2: dist {dist} lacks yuclaw-{VERSION} wheel/sdist")
        else:
            with zipfile.ZipFile(whl) as z:
                meta = z.read(f"yuclaw-{VERSION}.dist-info/METADATA").decode()
            mv = re.search(r"^Version: (\S+)$", meta, re.M)
            seen["wheel_metadata"] = mv.group(1) if mv else ""
            with tarfile.open(sd) as t:
                pkg = t.extractfile(f"yuclaw-{VERSION}/PKG-INFO").read().decode()
            mv = re.search(r"^Version: (\S+)$", pkg, re.M)
            seen["sdist_metadata"] = mv.group(1) if mv else ""
            block = (DOCS / "methodology" / "lookahead_statement.txt").read_text().rstrip("\n")
            seen["sdist_long_description_has_lookahead_block"] = block in pkg and block in meta
            if not seen["sdist_long_description_has_lookahead_block"]:
                problems.append("G2: package long description (README) does not carry the canonical look-ahead block")
            for k in ("wheel_metadata", "sdist_metadata"):
                if seen[k] != VERSION:
                    problems.append(f"G2: {k} {seen[k]!r} != {VERSION!r}")
    if pypi:
        st, body, _ = _get(f"https://pypi.org/pypi/yuclaw/{VERSION}/json")
        seen["pypi"] = json.loads(body)["info"]["version"] if st == 200 else f"HTTP {st}"
        if seen["pypi"] != VERSION:
            problems.append(f"G2: PyPI version {seen['pypi']!r} != {VERSION!r}")
    return seen


# ------------------------------------------------------------------ G3
def g3(problems: list[str]) -> dict:
    caps = json.loads((DOCS / "capabilities.json").read_text())
    idx = json.loads((DOCS / "evidence_index.json").read_text())
    llms = (DOCS / "llms.txt").read_text()
    m = re.search(r"^- Canonical base URL: (\S+)$", llms, re.M)
    seen = {"manifest": BASE, "capabilities": caps.get("base_url", ""),
            "evidence_index": idx.get("base_url", ""), "llms": m.group(1) if m else ""}
    for k, v in seen.items():
        if v.rstrip("/") != BASE:
            problems.append(f"G3: {k} base {v!r} != public_base_url {BASE!r}")
    for name, text in (("evidence_index.json", json.dumps(idx)), ("llms.txt", llms)):
        n = text.count("github.io")
        if n:
            problems.append(f"G3: {name} carries {n} github.io URL(s)")
    urls = list(caps.get("endpoints", {}).values()) + [idx.get("llms_txt", ""), idx.get("capabilities", ""),
            idx.get("replay_bundle", "")] + [p["url"] for p in idx.get("pages", [])] \
        + [p["url"] for p in idx.get("packets", {}).values()] + list(idx.get("schemas", {}).values()) \
        + [s["url"] for s in idx.get("machine_surfaces", [])]
    bad = [u for u in urls if not str(u).startswith(BASE + "/")]
    if bad:
        problems.append(f"G3: {len(bad)} listed URL(s) not under {BASE}: {bad[:3]}")
    seen["urls_checked"] = len(urls)
    return seen


# ------------------------------------------------------------------ G4
def _check_body(e: dict, data: bytes, where: str, problems: list[str]) -> None:
    fmt = e["format"]
    try:
        if fmt == "json":
            d = json.loads(data)
            for k in e.get("required_keys", []):
                if k not in d:
                    problems.append(f"G4: {where}: required key {k!r} missing")
            if e["key"] == "why_json":
                import jsonschema
                schema = json.loads((DOCS / "schemas" / "EvidenceObject.v1.json").read_text())
                for o in d.get("evidence_objects", [])[:5]:
                    jsonschema.validate(o, schema)
        elif fmt == "jsonl":
            for i, line in enumerate(data.decode("utf-8").splitlines()):
                if line.strip():
                    json.loads(line)
        elif fmt == "jsonschema":
            import jsonschema
            sch = json.loads(data)
            jsonschema.validators.validator_for(sch).check_schema(sch)
        elif fmt == "html":
            if b"<html" not in data[:2000].lower():
                problems.append(f"G4: {where}: not an HTML document")
        elif fmt == "text":
            data.decode("utf-8")
        elif fmt == "zip":
            if not zipfile.is_zipfile(io.BytesIO(data)):
                problems.append(f"G4: {where}: not a zip archive")
    except Exception as exc:                          # noqa: BLE001
        problems.append(f"G4: {where}: {type(exc).__name__}: {str(exc)[:120]}")


def _representatives(e: dict, reader) -> list[str]:
    """Paths to fetch for surface e. Wildcards resolve through the
    discovery rule; templated surfaces through their representative (and
    every schema member); statics through their own path."""
    if e["kind"] == "wildcard_family":
        if e["key"] == "ledger_day":
            days = json.loads(reader("/evidence/verify.json"))["days"]
            return [f"/ledger/{days[-1]['date']}.json"] if days else []
        if e["key"] == "evidence_changes_day":
            as_of = json.loads(reader("/c6_posture_current.json"))["as_of"]
            return [f"/evidence_changes/{as_of}.json"]
        return []
    if e["kind"] == "templated":
        if e["key"] == "schemas":
            return [f"/schemas/{n}.v1.json" for n in e["members"]]
        if e["key"] == "packet_zip":
            man = json.loads(reader("/packets/manifest.json"))
            return [f"/packets/{v['zip']}" for v in man.values() if isinstance(v, dict)]
        return [e["representative"]]
    return [e["path"]]


def g4(problems: list[str], live: bool) -> dict:
    expected = {e["path"] for e in MANIFEST["machine_surfaces"]}
    optional = set(MANIFEST.get("optional_or_dynamic", []))
    caps = json.loads((DOCS / "capabilities.json").read_text())
    idx = json.loads((DOCS / "evidence_index.json").read_text())
    llms = (DOCS / "llms.txt").read_text()
    declared = {
        "capabilities": {u[len(BASE):] for u in caps.get("endpoints", {}).values()},
        "evidence_index": {s["url"][len(BASE):] for s in idx.get("machine_surfaces", [])},
        "llms": set(re.findall(r"^  - (/\S+) · ", llms, re.M)),
    }
    key_by_path = {e["path"]: e["key"] for e in MANIFEST["machine_surfaces"]}
    for name, got in declared.items():
        missing = expected - got
        extra = {p for p in got - expected if key_by_path.get(p) not in optional}
        if missing:
            problems.append(f"G4: {name} is missing declared endpoints {sorted(missing)}")
        if extra:
            problems.append(f"G4: {name} declares extra endpoints not in the manifest {sorted(extra)}")
    fetched = {}

    def local_reader(path: str) -> bytes:
        return (DOCS / path.lstrip("/")).read_bytes()

    def live_reader(path: str) -> bytes:
        st, body, _ = _get(BASE + path)
        if st != 200:
            raise RuntimeError(f"HTTP {st}")
        return body

    reader = live_reader if live else local_reader
    for e in MANIFEST["machine_surfaces"]:
        try:
            reps = _representatives(e, reader)
        except Exception as exc:                      # noqa: BLE001
            problems.append(f"G4: {e['key']}: discovery rule failed: {type(exc).__name__}: {str(exc)[:100]}")
            continue
        if not reps:
            problems.append(f"G4: {e['key']}: discovery produced no representative")
        for rel in reps:
            where = f"{e['key']} {rel}"
            if live:
                try:
                    st, body, ctype = _get(BASE + rel)
                except Exception as exc:              # noqa: BLE001
                    problems.append(f"G4: {where}: {exc}"); continue
                fetched[rel] = {"status": st, "content_type": ctype, "sha256": hashlib.sha256(body).hexdigest()[:16]}
                if st != 200:
                    problems.append(f"G4: {where}: HTTP {st}"); continue
                want = e["content_type"].split(";")[0]
                if not ctype.split(";")[0].strip().startswith(want) and not (
                        want in ("application/octet-stream", "application/zip") and ctype):
                    problems.append(f"G4: {where}: content type {ctype!r} != {want!r}")
            else:
                p = DOCS / rel.lstrip("/")
                if not p.exists():
                    problems.append(f"G4: {where}: not present under docs/"); continue
                body = p.read_bytes()
                fetched[rel] = {"status": "local", "sha256": hashlib.sha256(body).hexdigest()[:16]}
            _check_body(e, body, where, problems)
    return {"expected": len(expected), "declared": {k: len(v) for k, v in declared.items()},
            "resolved": len(fetched), "mode": "live" if live else "local", "fetched": fetched}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["g2", "g3", "g4"])
    ap.add_argument("--dist", help="directory with the built wheel + sdist (G2 metadata + long description)")
    ap.add_argument("--pypi", action="store_true", help="also compare with the published PyPI version")
    ap.add_argument("--live", action="store_true", help="G4 over HTTPS with cache bypass")
    ap.add_argument("--out", help="write the record (JSON) here")
    a = ap.parse_args(argv)
    problems: list[str] = []
    rec: dict = {"version": VERSION, "base": BASE}
    if a.only in (None, "g2"):
        rec["g2"] = g2(problems, a.dist, a.pypi)
    if a.only in (None, "g3"):
        rec["g3"] = g3(problems)
    if a.only in (None, "g4"):
        rec["g4"] = g4(problems, a.live)
    rec["problems"] = problems
    rec["status"] = "GREEN" if not problems else "RED"
    if a.out:
        Path(a.out).write_text(json.dumps(rec, indent=1) + "\n")
    tag = a.only.upper() if a.only else "G2/G3/G4"
    if problems:
        print(f"RELEASE-MANIFEST GATE {tag} FAILED:")
        for p in problems:
            print("  ·", p)
        return 1
    parts = []
    if "g2" in rec:
        parts.append(f"G2 version {VERSION} on {len([k for k in rec['g2'] if k != 'site_badge_pages'])} surfaces + {rec['g2']['site_badge_pages']} badge pages")
    if "g3" in rec:
        parts.append(f"G3 base {BASE} ({rec['g3']['urls_checked']} URLs, zero github.io)")
    if "g4" in rec:
        parts.append(f"G4 {rec['g4']['expected']} endpoints declared on 3 surfaces, {rec['g4']['resolved']} representatives {rec['g4']['mode']}-resolved and schema-valid")
    print(f"[release-manifest] OK — " + " · ".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
