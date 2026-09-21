#!/usr/bin/env python3
"""8.0.1 — apply the version-surface change on the PATCH branch (owner order of 2026-09-21: local change and
validation-branch pushes only; this is not publication, a tag or a push to main).

Derived from the reviewed 8.0.0 tool (v8/V8-010/apply_version_surfaces_8.0.0.py, kept unchanged as history). Same
substitutions, re-derived on the current tree: pyproject, release manifest (release_kind = patch), capabilities,
evidence index, llms.txt, CITATION, README + generated PyPI README, the CHANGELOG entry, the badge on every
shared-header page, the README transcript (generated from a wheel of THIS tree, in the one transcript environment)
and the regenerated preview surfaces. New for 8.0.1:
  * the homepage's own identity strings (<title>, footer) and its static fragments are staged at the package version
    through tools/yuclaw_stage_static_surfaces.py — 8.0.0 re-badged the homepage and left its title at v7.0.1 (C06);
  * the DB-free consistency checks of the staged site must pass afterwards: derived Lab prose, Explorer template,
    homepage fragments, and the extended G2 version gate.
It refuses anywhere but branch codex/v8.0.1-quality-fixes with a clean working tree, and only with
YUCLAW_V8_0_1_APPLY=1; it makes NO commit and prints the touched paths (allow-list enforced, symlinks refused).

  YUCLAW_V8_0_1_APPLY=1 python3 v8/V8-018/apply_version_surfaces_8.0.1.py --changelog-entry v8/V8-018/changelog_entry_8.0.1.md --report <file outside the checkout>
"""
import argparse, fnmatch, json, os, pathlib, subprocess, sys, tempfile

repo = pathlib.Path(__file__).resolve().parents[2]
ap = argparse.ArgumentParser(); ap.add_argument("--changelog-entry", required=True); ap.add_argument("--report", required=True, help="where to write the touched-path report (outside the checkout)")
ap.add_argument("--old", default="8.0.0"); ap.add_argument("--new", default="8.0.1")
a = ap.parse_args(); OLD, NEW = a.old, a.new


def sh(*cmd, cwd=None, env=None):
    return subprocess.run(list(cmd), cwd=str(cwd or repo), capture_output=True, text=True, env=env, check=True).stdout


def porcelain():
    return [l for l in sh("git", "status", "--porcelain", "--untracked-files=all").splitlines() if l.strip()]      # never strip a line: the two-column code needs its leading space


if os.environ.get("YUCLAW_V8_0_1_APPLY") != "1":
    raise SystemExit("refused: set YUCLAW_V8_0_1_APPLY=1 (the owner's 8.0.1 order authorizes this local change on the patch branch only)")
if sh("git", "branch", "--show-current").strip() != "codex/v8.0.1-quality-fixes":
    raise SystemExit("refused: not on codex/v8.0.1-quality-fixes")
if porcelain():
    raise SystemExit(f"refused: working tree is not clean: {porcelain()[:10]}")
if pathlib.Path(a.changelog_entry).resolve().is_relative_to(repo) is False:
    raise SystemExit("refused: the CHANGELOG entry must be the tracked file of this tree")
entry = pathlib.Path(a.changelog_entry).read_text(encoding="utf-8").strip("\n")
if not entry.startswith(f"## [{NEW}]"):
    raise SystemExit(f"refused: the CHANGELOG entry must start with '## [{NEW}]'")


def sub(path: str, old: str, new: str, count: int | None = None):
    p = repo / path; t = p.read_text(encoding="utf-8"); n = t.count(old)
    assert n >= 1 and (count is None or n == count), (path, old[:60], n)
    p.write_text(t.replace(old, new), encoding="utf-8"); return n


changes = {}
changes["pyproject.toml"] = sub("pyproject.toml", f'version = "{OLD}"', f'version = "{NEW}"', 1)
rm = json.loads((repo / "release_manifest.json").read_text()); rm["version"] = NEW; rm["release_line"] = NEW.rsplit(".", 1)[0]; rm["release_kind"] = "patch"
(repo / "release_manifest.json").write_text(json.dumps(rm, indent=1, ensure_ascii=False) + "\n"); changes["release_manifest.json"] = 3
for f in ("docs/capabilities.json", "docs/evidence_index.json"):
    changes[f] = sub(f, f'"version": "v{OLD}"', f'"version": "v{NEW}"', 1)
changes["docs/llms.txt"] = sub("docs/llms.txt", f"- Version: yuclaw {OLD}", f"- Version: yuclaw {NEW}", 1)
changes["CITATION.cff"] = sub("CITATION.cff", f"version: {OLD}", f"version: {NEW}", 1)
changes["README.md"] = sub("README.md", f"Current package version: `{OLD}`", f"Current package version: `{NEW}`", 1) + sub("README.md", f"releases/tag/v{OLD})", f"releases/tag/v{NEW})", 1)
# NOT substituted (8.0.1 finding): the README's "v7 — check → reproduce …" output block was recorded on the 7.0.0 candidate and
# earlier version steps relabelled it 7.0.1 / 8.0.0 without re-recording it. The README now says where it was recorded.
cl = (repo / "CHANGELOG.md").read_text(encoding="utf-8"); i = cl.index("## [")
assert f"## [{NEW}]" not in cl, "CHANGELOG already carries this version"
(repo / "CHANGELOG.md").write_text(cl[:i] + entry + "\n\n" + cl[i:], encoding="utf-8"); changes["CHANGELOG.md"] = 1
pages = [p for p in list((repo / "docs").glob("*.html")) + list((repo / "docs" / "why").glob("*.html")) if "hdr-nav" in p.read_text(errors="replace")]
badge_n = 0
for p in pages:
    t = p.read_text(encoding="utf-8", errors="replace"); k = t.count(f">v{OLD}</span>"); assert k >= 1, p
    p.write_text(t.replace(f">v{OLD}</span>", f">v{NEW}</span>"), encoding="utf-8"); badge_n += k
changes["badge pages"] = f"{len(pages)} pages, {badge_n} badges"
print(sh(sys.executable, str(repo / "tools" / "yuclaw_stage_static_surfaces.py")).strip()); changes["docs/index.html identity + static fragments"] = "staged at the package version"
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
for tool in ("yuclaw_stage_static_surfaces.py", "yuclaw_lab_prose.py", "yuclaw_restage_explorer.py"):
    print(sh(sys.executable, str(repo / "tools" / tool), "--check").strip())                                   # check=True: a stale staged page stops here
print(sh(sys.executable, str(repo / "tools" / "check_release_manifest.py"), "--only", "g2").strip().splitlines()[-1])
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
