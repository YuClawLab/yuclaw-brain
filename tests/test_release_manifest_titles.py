"""8.0.1 C06 — the version gate reads page titles and "YUCLAW vX.Y.Z" identity strings of the current site.

8.0.0's homepage badge said v8.0.0 while its <title> and footer said v7.0.1; the gate compared badges and machine files
only. Archived guides and named earlier releases are not current (shared-header) pages and must stay untouched."""
import pathlib, sys, tempfile, unittest

REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "tools"))
import check_release_manifest as G                                              # noqa: E402


class Titles(unittest.TestCase):
    def page(self, d, name, html):
        p = pathlib.Path(d) / name; p.write_text(html); return p

    def test_a_stale_title_or_footer_identity_is_reported_and_matching_ones_pass(self):
        with tempfile.TemporaryDirectory() as d:
            good = self.page(d, "index.html", '<title>YUCLAW v9.9.9 — Evidence-First Financial AI</title><nav class="hdr-nav"></nav><span>v9.9.9</span><div class="footer">YUCLAW v9.9.9 · x</div>')
            bad = self.page(d, "lab.html", '<title>YUCLAW v7.0.1 — Lab</title><nav class="hdr-nav"></nav><div class="footer">YUCLAW v7.0.1 · x</div><p>introduced in v5.3.2</p>')
            plain = self.page(d, "plain.html", '<title>Explorer — YUCLAW</title><nav class="hdr-nav"></nav><p>since v5.3.2 the snapshot ships in the wheel</p>')
            self.assertEqual(G.stale_identity_strings([good, plain], "9.9.9"), [])
            out = G.stale_identity_strings([good, bad, plain], "9.9.9"); self.assertEqual(len(out), 2); self.assertTrue(all(x.startswith("lab.html: ") for x in out)); self.assertIn("<title>YUCLAW v7.0.1", out[0])

    def test_archived_guides_are_not_current_pages(self):
        archived = REPO / "docs" / "YUCLAW_User_Guide_v5.1_source.html"
        if archived.exists():
            self.assertNotIn("hdr-nav", archived.read_text(errors="replace"))           # g2 selects shared-header pages only: the archive is never rewritten to the current version


if __name__ == "__main__":
    unittest.main()
