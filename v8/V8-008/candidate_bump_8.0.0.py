#!/usr/bin/env python3
"""STAGING-ONLY version bump (V8-006 §2; V8-008: explicit path staging instead of `git add -A`). Applies the 8.0.0 identity to every surface the release gates read, inside a
DISPOSABLE clone, so the 8.0.0 publisher can be rehearsed end to end (real build, G2 over the built artifacts, exact
transcript comparison) without touching the candidate branch. The commit it makes is never a candidate: the real bump
is a freeze-day step in the production checkout (7.0.1 pattern: version + every page rendered at the badge).
Refuses to run outside a path containing 'rehearsal' or unless YUCLAW_REHEARSAL_BUMP=1.

  YUCLAW_REHEARSAL_BUMP=1 python3 rehearsal_bump_v800.py <clone> [<old-version> <new-version>]"""
import json, os, pathlib, subprocess, sys, tempfile

repo = pathlib.Path(sys.argv[1]).resolve(); OLD = sys.argv[2] if len(sys.argv) > 2 else "7.0.1"; NEW = sys.argv[3] if len(sys.argv) > 3 else "8.0.0"
if os.environ.get("YUCLAW_CANDIDATE_BUMP") != "1" or "staging" not in str(repo):
    raise SystemExit("refused: staging-only tool (set YUCLAW_CANDIDATE_BUMP=1 and use a private staging worktree whose path contains staging)")


def sub(path: str, old: str, new: str, count: int | None = None):
    p = repo / path; t = p.read_text(encoding="utf-8"); n = t.count(old)
    assert n >= 1 and (count is None or n == count), (path, old[:60], n)
    p.write_text(t.replace(old, new), encoding="utf-8"); return n


def sh(*a, cwd=None, env=None):
    return subprocess.run(list(a), cwd=str(cwd or repo), capture_output=True, text=True, env=env, check=True).stdout.strip()


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
(repo / "CHANGELOG.md").write_text(cl[:i] + f"## [{NEW}] — 2026-09-21\n\nResearch & education only. Not investment advice.\n\n### YUCLAW {NEW} — see the Tier-2 notes draft (v8/V8-006/release_notes_8.0.0_DRAFT.md); this CHANGELOG entry is composed from it at freeze\n\n" + cl[i:], encoding="utf-8")
changes["CHANGELOG.md"] = 1
pages = [p for p in list((repo / "docs").glob("*.html")) + list((repo / "docs" / "why").glob("*.html")) if "hdr-nav" in p.read_text(errors="replace")]
badge_n = 0
for p in pages:
    t = p.read_text(encoding="utf-8", errors="replace"); k = t.count(f">v{OLD}</span>"); assert k >= 1, p
    p.write_text(t.replace(f">v{OLD}</span>", f">v{NEW}</span>"), encoding="utf-8"); badge_n += k
changes["badge pages"] = f"{len(pages)} pages, {badge_n} badges"
# the README first-touch transcript is GENERATED from a wheel of THIS tree: throwaway build → venv install → transcript --write
with tempfile.TemporaryDirectory(prefix="yuclaw-rehearsal-transcript-") as td:
    td = pathlib.Path(td); env = dict(os.environ, SOURCE_DATE_EPOCH="1580601600"); env.pop("PYTHONPATH", None)
    sh(sys.executable, "-m", "build", "--wheel", "--outdir", str(td / "dist"), str(repo), env=env)
    whl = next((td / "dist").glob("*.whl")); sh(sys.executable, "-m", "venv", str(td / "venv")); sh(str(td / "venv" / "bin" / "python"), "-m", "pip", "install", "-q", str(whl))
    print(sh(sys.executable, str(repo / "tools" / "cli_transcript.py"), "--exe", str(td / "venv" / "bin" / "yuclaw"), "--wheel", whl.name, "--write"))
    changes["README transcript"] = whl.name
print(sh(sys.executable, str(repo / "tools" / "yuclaw_readme_pypi.py"), "--write"))
# staged preview surfaces (docs/preview/*, capabilities.vnext) are DERIVED from the tree by the staged renderer; regenerate them so gate 11
# (machine JSON == human page, byte-reproducible) holds at the new version — this needs no database and is not the production refresh chain
print(sh(sys.executable, "-c", "import sys; sys.path.insert(0, 'tools'); sys.path.insert(0, '.'); import yuclaw_science_trust_cards as C; r = C.write_all(); print('preview surfaces regenerated:', {k: v for k, v in r.items() if k != 'anchor'})", cwd=repo))
changes["docs/preview (staged renderer)"] = "regenerated"
# EXPLICIT staging (V8-008): every path this script touched is listed; anything else in the working tree (an untracked file, a
# symlink, unrelated owner work) is neither staged nor deleted, and any change outside the allow-list refuses the commit.
import fnmatch
allow = ("pyproject.toml", "release_manifest.json", "docs/capabilities.json", "docs/evidence_index.json", "docs/llms.txt", "CITATION.cff", "README.md", "README_PYPI.md", "CHANGELOG.md",
         "docs/*.html", "docs/why/*.html", "docs/why/*.json", "docs/preview/*", "docs/preview/*/*", "docs/preview/*/*/*")
status = [l for l in subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=str(repo), capture_output=True, text=True, check=True).stdout.splitlines() if l.strip()]   # no strip(): the two-column code needs its leading space
touched, refused = [], []
for l in status:
    code, path = l[:2], l[3:]
    if any(fnmatch.fnmatch(path, a) for a in allow) and code.strip() in ("M", "A", "??", "AM", "MM") and not (repo / path).is_symlink():
        touched.append(path)
    else:
        refused.append(l)
if refused:
    raise SystemExit(f"refused: working-tree entries outside the version-surface allow-list would not be staged: {refused[:20]} — resolve them first (nothing committed)")
sh("git", "add", "--", *touched)
staged = sh("git", "diff", "--cached", "--name-only").splitlines(); assert sorted(staged) == sorted(touched), (len(staged), len(touched))
changes["staged paths"] = len(touched)
sh("git", "-c", "user.name=YuClawLab", "-c", "user.email=vzhang2099@gmail.com", "commit", "-q", "-m", f"release(v{NEW}) candidate: version {NEW} on every gate-checked surface (badge re-pinned on the shared-header pages; README transcript from the release-candidate wheel; PyPI description regenerated) — PREPARED IN PRIVATE STAGING FOR OWNER REVIEW; not applied to the branch")
head = sh("git", "rev-parse", "HEAD")
g2 = subprocess.run([sys.executable, str(repo / "tools" / "check_release_manifest.py"), "--only", "g2"], cwd=str(repo), capture_output=True, text=True)
hl = subprocess.run([sys.executable, str(repo / "tools" / "check_header_layout.py")], cwd=str(repo), capture_output=True, text=True)
print(json.dumps({"rehearsal_head": head, "changes": changes, "g2_rc": g2.returncode, "g2_tail": (g2.stdout + g2.stderr).strip().splitlines()[-1:], "header_layout_rc": hl.returncode, "header_layout_tail": (hl.stdout + hl.stderr).strip().splitlines()[-1:]}, indent=1))
sys.exit(0 if g2.returncode == 0 and hl.returncode == 0 else 1)
