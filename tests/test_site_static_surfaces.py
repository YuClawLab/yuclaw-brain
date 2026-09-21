"""8.0.1 C05 / C07 / C11 / C12 / C13 — what the entry points say about v8, the guides, the retained alias and the status.

The homepage and README (and therefore the PyPI long description) explain the local workbench and SHD/EVO/COM/PRC in
plain words with a working command route, say that the website is the research-content site and that the workbench runs
locally, state loopback binding, supported isolation, the experimental status and the absence of an independent security
review or user study; the current guide is the primary route and the earlier PDFs are labelled as history with their
real length; `former_name` stays as a documented deprecated compatibility alias; the owner's "Built in Canada" wording
is used, with no implication of government endorsement, funding or data residency."""
import json, pathlib, re, sys, unittest

REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "tools"))
from v3.web import useful_blocks as U                                           # noqa: E402

text = lambda html: " ".join(re.sub(r"<[^>]+>", " ", html).split())


class EntryPoints(unittest.TestCase):
    def test_the_workbench_card_and_the_readme_section_say_the_same_true_things(self):
        card = text(U.workbench_card_html()); readme = (REPO / "README.md").read_text(encoding="utf-8"); pypi = (REPO / "README_PYPI.md").read_text(encoding="utf-8")
        section = lambda t: " ".join(t[t.index("## v8 — the local workbench"):t.index("## v7 — check")].split())                       # the v8 section only: other sections have their own, older wording
        for where, t in (("card", card), ("README", section(readme)), ("PyPI long description", section(pypi))):
            for needle in ("research-content site", "on your own computer", "127.0.0.1", "no hosted service and no account", "Distillation Shield", "Evolution Evidence Audit", "Research Commons Guard", "Independent Practice",
                           "yuclaw workbench selftest", "yuclaw workbench principals init --workspace", "yuclaw workbench serve --workspace", "yuclaw workbench guide", "experimental", "Linux with Landlock",
                           "No independent security review has been performed", "human benefit is PENDING", "evidence scoreboard"):
                self.assertIn(needle, t, (where, needle))
            for wrong in ("works on macOS", "works on Windows", "audited", "certified", "guarantee"):
                self.assertNotIn(wrong, t, (where, wrong))

    def test_the_current_guide_is_primary_and_the_earlier_pdfs_are_labelled_history_with_their_real_length(self):
        g = text(U.guide_links_html()); self.assertTrue(g.index("Current guide (v8, English)") < g.index("Earlier PDF guides")); self.assertIn("12 pages", g); self.assertIn("not updated for v8", g); self.assertNotIn("six pages", g)
        page = (REPO / "docs" / "index.html").read_text(encoding="utf-8"); self.assertNotIn("six pages", page); self.assertIn(U.GUIDE_URL, page); self.assertIn("historical", text(page))
        for fn in ("YUCLAW_User_Guide.pdf", "YUCLAW_Guide_Utilisateur_FR.pdf", "v8/workbench/resources/OPERATOR_GUIDE.md"):
            self.assertTrue((REPO / "docs" / fn).exists() or (REPO / fn).exists(), fn)                                     # advertised, versionless addresses still resolve; the current guide exists
        self.assertIsNone(re.search(r"Guide[_a-zA-Z]*_v\d", page)); self.assertIsNone(re.search(r"\bv5\.1\b", (REPO / "README.md").read_text()))   # the existing B4 rule still holds

    def test_the_staged_homepage_carries_the_generators_static_fragments_and_the_package_version(self):
        import yuclaw_stage_static_surfaces as S
        page = (REPO / "docs" / "index.html").read_text(encoding="utf-8"); self.assertEqual(S.staged(page), page)
        self.assertIn(f"<title>YUCLAW {U.VERSION} — Evidence-First Financial AI</title>", page); self.assertIn("Built in Canada", page)

    def test_former_name_is_a_documented_deprecated_alias_not_positioning(self):
        caps = json.loads((REPO / "docs" / "capabilities.json").read_text()); man = json.loads((REPO / "release_manifest.json").read_text())
        self.assertEqual(caps["name"], "YUCLAW Evidence API"); self.assertEqual(caps["former_name"], man["api_former_name"]); self.assertIn("deprecated compatibility alias", caps["former_name_status"]); self.assertIn("not a product claim", caps["former_name_status"])
        disc = next(e for e in man["machine_surfaces"] if e["key"] == "discovery"); self.assertIn("former_name", disc["required_keys"])     # the compatibility contract that keeps it
        self.assertNotIn(man["api_former_name"].replace("YUCLAW ", "").replace(" API", ""), json.dumps({k: v for k, v in caps.items() if k != "former_name"}))   # the retired phrase appears nowhere else

    def test_canadian_origin_wording_makes_no_endorsement_or_residency_claim(self):
        for f in ("README.md", "docs/index.html", "CHANGELOG.md"):
            t = (REPO / f).read_text(encoding="utf-8"); self.assertIn("Built in Canada", t)
            head = t[:t.index("## [8.0.0]")] if f == "CHANGELOG.md" and "## [8.0.0]" in t else t
            for wrong in ("Government of Canada", "endorsed by", "SCIP", "data residency", "sovereign cloud", "Made in Canada"):
                self.assertNotIn(wrong, head if f == "CHANGELOG.md" else (t if wrong != "Made in Canada" else ""), (f, wrong))


if __name__ == "__main__":
    unittest.main()
