#!/usr/bin/env python3
"""V8-010 §4 — apply the reviewed 8.0.0 version-surface change ON the integration branch (authorized locally by order
V8-010; this is not publication, designation of a final release, a tag or a push).

The substitutions are the ones reviewed in the V8-006/V8-008 staging patch (108 files: pyproject, release manifest,
capabilities, evidence index, llms.txt, CITATION, README + generated PyPI README, CHANGELOG entry, the badge on every
shared-header page, the generated README transcript and the regenerated preview surfaces). They are RE-DERIVED on the
current tree — the old staging commit is never cherry-picked onto files that changed since. Differences from the
staging-only bump (v8/V8-008/candidate_bump_8.0.0.py, kept unchanged as the historical tool):
  * refuses anywhere but branch codex/v8-integration with a clean working tree, and only with YUCLAW_V8_010_APPLY=1;
  * writes a real CHANGELOG entry for the actual scope (passed in from a reviewed text file) instead of a pointer;
  * makes NO commit: it prints the exact touched paths (allow-list enforced, symlinks refused) for explicit staging.

  YUCLAW_V8_010_APPLY=1 python3 v8/V8-010/apply_version_surfaces_8.0.0.py --changelog-entry <file> --report <file outside the checkout>
"""
import argparse, fnmatch, json, os, pathlib, subprocess, sys, tempfile

repo = pathlib.Path(__file__).resolve().parents[2]
ap = argparse.ArgumentParser(); ap.add_argument("--changelog-entry", required=True); ap.add_argument("--report", required=True, help="where to write the touched-path report (outside the checkout)")
ap.add_argument("--old", default="7.0.1"); ap.add_argument("--new", default="8.0.0")
a = ap.parse_args(); OLD, NEW = a.old, a.new


def sh(*cmd, cwd=None, env=None):
    return subprocess.run(list(cmd), cwd=str(cwd or repo), capture_output=True, text=True, env=env, check=True).stdout


def porcelain():
    return [l for l in sh("git", "status", "--porcelain", "--untracked-files=all").splitlines() if l.strip()]      # never strip a line: the two-column code needs its leading space


if os.environ.get("YUCLAW_V8_010_APPLY") != "1":
    raise SystemExit("refused: set YUCLAW_V8_010_APPLY=1 (order V8-010 §4 authorizes this local change on the integration branch only)")
if sh("git", "branch", "--show-current").strip() != "codex/v8-integration":
    raise SystemExit("refused: not on codex/v8-integration")
if porcelain():
    raise SystemExit(f"refused: working tree is not clean: {porcelain()[:10]}")
entry = pathlib.Path(a.changelog_entry).read_text(encoding="utf-8").strip("\n")
if not entry.startswith(f"## [{NEW}]"):
    raise SystemExit(f"refused: the CHANGELOG entry must start with '## [{NEW}]'")


def sub(path: str, old: str, new: str, count: int | None = None):
    p = repo / path; t = p.read_text(encoding="utf-8"); n = t.count(old)
    assert n >= 1 and (count is None or n == count), (path, old[:60], n)
    p.write_text(t.replace(old, new), encoding="utf-8"); return n


changes = {}
changes["pyproject.toml"] = sub("pyproject.toml", f'version = "{OLD}"', f'version = "{NEW}"', 1)
rm = json.loads((repo / "release_manifest.json").read_text()); rm["version"] = NEW; rm["release_line"] = NEW.rsplit(".", 1)[0]; rm["release_kind"] = "major"
(repo / "release_manifest.json").write_text(json.dumps(rm, indent=1, ensure_ascii=False) + "\n"); changes["release_manifest.json"] = 3
for f in ("docs/capabilities.json", "docs/evidence_index.json"):
    changes[f] = sub(f, f'"version": "v{OLD}"', f'"version": "v{NEW}"', 1)
changes["docs/llms.txt"] = sub("docs/llms.txt", f"- Version: yuclaw {OLD}", f"- Version: yuclaw {NEW}", 1)
changes["CITATION.cff"] = sub("CITATION.cff", f"version: {OLD}", f"version: {NEW}", 1)
changes["README.md"] = sub("README.md", f"Current package version: `{OLD}`", f"Current package version: `{NEW}`", 1) + sub("README.md", f"releases/tag/v{OLD})", f"releases/tag/v{NEW})", 1) \
    + sub("README.md", f"Outputs are from the {OLD} candidate checkout", f"Outputs are from the {NEW} candidate checkout", 1)
cl = (repo / "CHANGELOG.md").read_text(encoding="utf-8"); i = cl.index("## [")
assert f"## [{NEW}]" not in cl, "CHANGELOG already carries this version"
(repo / "CHANGELOG.md").write_text(cl[:i] + entry + "\n\n" + cl[i:], encoding="utf-8"); changes["CHANGELOG.md"] = 1
pages = [p for p in list((repo / "docs").glob("*.html")) + list((repo / "docs" / "why").glob("*.html")) if "hdr-nav" in p.read_text(errors="replace")]
badge_n = 0
for p in pages:
    t = p.read_text(encoding="utf-8", errors="replace"); k = t.count(f">v{OLD}</span>"); assert k >= 1, p
    p.write_text(t.replace(f">v{OLD}</span>", f">v{NEW}</span>"), encoding="utf-8"); badge_n += k
changes["badge pages"] = f"{len(pages)} pages, {badge_n} badges"
# the README first-touch transcript is GENERATED from a wheel of THIS tree: throwaway build → venv install → transcript --write
with tempfile.TemporaryDirectory(prefix="yuclaw-v8-010-transcript-") as td:
    td = pathlib.Path(td); env = dict(os.environ, SOURCE_DATE_EPOCH="1580601600"); env.pop("PYTHONPATH", None)
    src = td / "src"; src.mkdir()                                     # build from a copy of the tracked tree + these edits, never inside the checkout (no build/ or dist/ litter)
    files = sh("git", "ls-files", "-z").split("\0")
    for f in filter(None, files):
        s, d = repo / f, src / f
        if s.is_symlink() or not s.is_file():
            continue
        d.parent.mkdir(parents=True, exist_ok=True); d.write_bytes(s.read_bytes())
    sh(sys.executable, "-m", "build", "--wheel", "--outdir", str(td / "dist"), str(src), env=env)
    whl = next((td / "dist").glob("*.whl")); sh(sys.executable, "-m", "venv", str(td / "venv")); sh(str(td / "venv" / "bin" / "python"), "-m", "pip", "install", "-q", str(whl), env=env)
    print(sh(sys.executable, str(repo / "tools" / "cli_transcript.py"), "--exe", str(td / "venv" / "bin" / "yuclaw"), "--wheel", whl.name, "--write").strip())
    changes["README transcript"] = whl.name
print(sh(sys.executable, str(repo / "tools" / "yuclaw_readme_pypi.py"), "--write").strip())
print(sh(sys.executable, "-c", "import sys; sys.path.insert(0, 'tools'); sys.path.insert(0, '.'); import yuclaw_science_trust_cards as C; r = C.write_all(); print('preview surfaces regenerated:', {k: v for k, v in r.items() if k != 'anchor'})").strip())
changes["docs/preview (staged renderer)"] = "regenerated"
allow = ("pyproject.toml", "release_manifest.json", "docs/capabilities.json", "docs/evidence_index.json", "docs/llms.txt", "CITATION.cff", "README.md", "README_PYPI.md", "CHANGELOG.md",
         "docs/*.html", "docs/why/*.html", "docs/why/*.json", "docs/preview/*", "docs/preview/*/*", "docs/preview/*/*/*")
touched, refused = [], []
for l in porcelain():
    code, path = l[:2], l[3:]
    if any(fnmatch.fnmatch(path, x) for x in allow) and code.strip() in ("M", "A", "??", "AM", "MM") and not (repo / path).is_symlink():
        touched.append(path)
    else:
        refused.append(l)
out = {"changes": changes, "touched_paths": sorted(touched), "touched_count": len(touched), "outside_allow_list": refused, "committed": False}
pathlib.Path(a.report).write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps({k: v for k, v in out.items() if k != "touched_paths"}, indent=1))
sys.exit(1 if refused else 0)
