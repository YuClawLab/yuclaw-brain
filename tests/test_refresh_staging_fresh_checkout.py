"""X01 (8.0.1): generation → the refresh's own staging block → commit → FRESH CLONE → coverage consistency.

The defect: cron/refresh_v3_pages.sh regenerated docs/coverage.json on every run and rendered the homepage, Explorer and
Why surfaces from it, but its `git add` list did not name the file. The nightly gates read the WORKING TREE (green);
every COMMIT carried surfaces bound to an artifact instance the committed /coverage.json did not have (public endpoint
as of 2026-09-15, surfaces as of 2026-09-18).

What is real here: v3.web.coverage_public.publish/read/identity_attrs (the generator and the binding the renderers
use), the staging block of the refresh script — extracted between its two markers and executed VERBATIM by bash — a
real `git commit`, a real `git clone`, and the unmodified tools/check_coverage_consistency.check on the clone, over the
real scoring universe. What stands in: the surface renderers (they need the research node); the stand-ins write the
fields the gate joins on, from coverage_public.read(), exactly as the renderers do. Disposable repository only."""
import json, os, pathlib, re, shutil, subprocess, sys, tempfile, unittest
from datetime import datetime, timezone

REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "tools"))
from v3.web import coverage_public as CP  # noqa: E402
from v3.universe_tiers import scoring_universe  # noqa: E402
import check_coverage_consistency as CC  # noqa: E402
import deploy_verify as DV  # noqa: E402

SCRIPT = REPO / "cron" / "refresh_v3_pages.sh"
BEGIN, END = "# >>> refresh staging block >>>", "# <<< refresh staging block <<<"
OMITTED = "docs/coverage.json"
GIT = "/usr/bin/git"                                   # the path the refresh script itself calls


def staging_block(text: str) -> str:
    assert text.count(BEGIN) == 1 and text.count(END) == 1, "the refresh script must carry exactly one marked staging block"
    return text.split(BEGIN, 1)[1].split(END, 1)[0]


def pathspecs(block: str) -> list:
    """Every path the block names (git add arguments and the guarded file)."""
    return sorted({t for t in re.split(r"[\s\\]+", block) if re.match(r"^(docs|registry)/|^README\.md$", t)})


def git_env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}       # never inherit a hook's GIT_DIR / index
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="refresh test", GIT_AUTHOR_EMAIL="refresh@test.invalid",
               GIT_COMMITTER_NAME="refresh test", GIT_COMMITTER_EMAIL="refresh@test.invalid")
    return env


def run(args, cwd) -> str:
    p = subprocess.run(args, cwd=cwd, env=git_env(), capture_output=True, text=True)
    assert p.returncode == 0, f"{args} rc={p.returncode}\n{p.stdout}\n{p.stderr}"
    return p.stdout


def generate(repo: pathlib.Path, as_of: str, shift: int) -> None:
    """One refresh run's coverage chain: private artifact → REAL public projection → surfaces bound through read()."""
    universe = sorted(scoring_universe())
    private = repo / "output" / "oie" / "evidence_coverage.json"; private.parent.mkdir(parents=True, exist_ok=True)
    private.write_text(json.dumps({"as_of": as_of, "caption": "coverage, not prediction", "method_hash": "m", "protocol_id": "e3d51f5b0ca3",
                                   "scores": {t: {"ecs": (i * 7 + shift) % 101, "events_90d": i, "recency_days": shift, "type_diversity": 1, "substrate_active": True}
                                              for i, t in enumerate(universe)}}))
    docs = repo / "docs"; (docs / "why").mkdir(parents=True, exist_ok=True)
    CP.publish(private=private, public=docs / "coverage.json", now=datetime.fromisoformat(as_of))
    cov = CP.read(docs / "coverage.json"); ident, scores = cov["identity"], cov["scores"]
    (docs / "explorer_data.json").write_text(json.dumps({"generated": as_of, "coverage_source": ident, "rows": [{"ticker": t, "ecs": scores[t]["ecs"]} for t in universe]}))
    rows = "".join(f"<tr><td>{t}</td><td>NEUTRAL</td><td>+0.0</td><td>{scores[t]['ecs']}</td></tr>" for t in universe)
    (docs / "index.html").write_text(f"<table {CP.identity_attrs(ident)}>{rows}</table>")
    for t in universe:
        (docs / "why" / f"{t}.json").write_text(json.dumps({"ticker": t, "evidence_coverage": {"ecs": scores[t]["ecs"], **ident}}))
        (docs / "why" / f"{t}.html").write_text(f'<div data-ecs="{scores[t]["ecs"]}">{scores[t]["ecs"]}</div>')


def refresh_and_clone(tmp: pathlib.Path, block: str):
    """baseline commit (run A) → run B → the given staging block, verbatim → commit → fresh clone. Returns (repo, clone)."""
    repo, clone = tmp / "production", tmp / "fresh_clone"; repo.mkdir()
    run([GIT, "init", "--quiet", "--initial-branch=main", "."], repo)
    for spec in pathspecs(staging_block(SCRIPT.read_text())):                     # every path the real block names exists and is tracked, as in production
        p = repo / spec
        if pathlib.PurePosixPath(spec).suffix:
            p.parent.mkdir(parents=True, exist_ok=True); p.write_text("placeholder\n")
        else:
            p.mkdir(parents=True, exist_ok=True); (p / ".keep").write_text("")
    generate(repo, "2026-01-05T23:00:00+00:00", shift=0)
    run([GIT, "add", "-A", "docs", "registry", "README.md"], repo); run([GIT, "commit", "--quiet", "-m", "baseline: run A"], repo)
    generate(repo, "2026-01-06T23:00:00+00:00", shift=13)
    run(["bash", "-c", "set -u\n" + block], repo)
    run([GIT, "commit", "--quiet", "-m", "auto: v3.0 page refresh (test run B)"], repo)
    run([GIT, "clone", "--quiet", str(repo), str(clone)], tmp)
    return repo, clone


@unittest.skipUnless(pathlib.Path(GIT).exists() and shutil.which("bash"), f"needs {GIT} and bash: the staging block is executed verbatim")
class RefreshStagingSurvivesAFreshCheckout(unittest.TestCase):
    def test_the_refresh_commit_is_coverage_consistent_in_a_fresh_clone(self):
        with tempfile.TemporaryDirectory() as d:
            repo, clone = refresh_and_clone(pathlib.Path(d), staging_block(SCRIPT.read_text()))
            self.assertEqual(CC.check(repo / "docs"), [])
            self.assertEqual(CC.check(clone / "docs"), [])                                                    # what a stranger checks out
            ident = CP.read(clone / "docs" / "coverage.json")["identity"]
            self.assertEqual(ident["as_of"], "2026-01-06T23:00:00+00:00")                                     # run B's artifact, not run A's
            self.assertEqual(json.loads((clone / "docs" / "explorer_data.json").read_text())["coverage_source"], ident)
            left = [l for l in run([GIT, "status", "--porcelain", "--untracked-files=no", "--", "docs", "registry", "README.md"], repo).splitlines() if l]
            self.assertEqual(left, [], "a tracked public file rewritten by the run was not selected for the commit")

    def test_the_original_omission_is_detected(self):
        block = staging_block(SCRIPT.read_text()); self.assertIn(OMITTED, pathspecs(block))
        original = "\n".join(l for l in block.splitlines() if l.strip().rstrip("\\").strip() != OMITTED)      # the list as it was before 8.0.1
        self.assertNotIn(OMITTED, pathspecs(original)); self.assertEqual(set(pathspecs(block)) - set(pathspecs(original)), {OMITTED})
        with tempfile.TemporaryDirectory() as d:
            repo, clone = refresh_and_clone(pathlib.Path(d), original)
            self.assertEqual(CC.check(repo / "docs"), [])                                                     # the blind spot: the working tree the nightly gates read is green
            f = CC.check(clone / "docs"); n = len(scoring_universe())
            self.assertEqual(sum("different artifact identity" in x for x in f), 2 + n, f[:5])                # Explorer + homepage + every Why JSON bound to an instance the clone does not have
            self.assertTrue(any(x.startswith("explorer_data.json:") and " ecs " in x for x in f))              # and same-metric values differ
            self.assertEqual(CP.read(clone / "docs" / "coverage.json")["identity"]["as_of"], "2026-01-05T23:00:00+00:00")   # the stale endpoint
            self.assertIn(" M docs/coverage.json", run([GIT, "status", "--porcelain", "--untracked-files=no"], repo).splitlines())   # the production "dirty" file


class EveryJoinedSurfaceIsStagedAndDeployVerified(unittest.TestCase):
    def test_staging_block_covers_every_file_the_gate_joins(self):
        specs = pathspecs(staging_block(SCRIPT.read_text()))
        for needed in ("docs/coverage.json", "docs/explorer_data.json", "docs/index.html", "docs/why"):
            self.assertIn(needed, specs)
        self.assertRegex(SCRIPT.read_text(), r"(?m)^/usr/bin/python3 -m v3\.web\.coverage_public \|\| exit 70$")   # still generated by the same run, before the renders

    def test_deploy_verify_watches_the_shared_artifact_with_its_surfaces(self):
        for rel in ("coverage.json", "explorer_data.json", "index.html", "why/AAPL.json"):
            self.assertIn(rel, DV.DEFAULT_PATHS)

    def test_this_checkout_is_coverage_consistent(self):
        """The committed site of this very checkout — in hosted CI, a fresh checkout of the exact commit."""
        self.assertEqual(CC.check(REPO / "docs"), [])


if __name__ == "__main__":
    unittest.main()
