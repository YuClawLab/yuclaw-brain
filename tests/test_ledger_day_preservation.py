"""Per-day public ledger files (docs/ledger/{DATE}.json) are externally pinned by file hash: the nightly rebuild must leave an
existing day whose root and entries are unchanged byte-for-byte untouched (a prose-only change to the verify sentence never
rewrites history); a new day, a day whose entries changed, and an unreadable file are written with the current sentence."""
import hashlib, json, pathlib, sys, tempfile, unittest

R = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))
from v3.web import render_why_json as W  # noqa: E402


def entries(n, salt=""):
    return [{"ticker": f"T{i}", "content_hash": hashlib.sha256(f"{i}{salt}".encode()).hexdigest()} for i in range(n)]


class LedgerDayPreservation(unittest.TestCase):
    def test_existing_unchanged_day_keeps_its_bytes_and_everything_else_is_written(self):
        tmp = pathlib.Path(tempfile.mkdtemp()); src = tmp / "ledger.jsonl"; out = tmp / "ledger"; out.mkdir()
        days = {"2026-05-20": entries(3), "2026-05-21": entries(2), "2026-05-22": entries(4), "2026-05-23": entries(1)}
        src.write_text("".join(json.dumps({"date": d, "snapshot_count": len(e), "entries": e}) + "\n" for d, e in days.items()))
        root = lambda e: hashlib.sha256(json.dumps(e, sort_keys=True).encode()).hexdigest()
        old_prose = "recompute sha256 over the sorted entries and compare; each entry's content_hash matches its snapshot object"
        (out / "2026-05-20.json").write_text(json.dumps({"date": "2026-05-20", "snapshot_count": 3, "root_sha256": root(days["2026-05-20"]), "entries": days["2026-05-20"], "verify": old_prose, "not_advice": "x"}, indent=1))
        pinned = hashlib.sha256((out / "2026-05-20.json").read_bytes()).hexdigest()                     # an outside party recorded this file hash earlier
        (out / "2026-05-21.json").write_text(json.dumps({"date": "2026-05-21", "snapshot_count": 2, "root_sha256": root(entries(2, "old")), "entries": entries(2, "old"), "verify": old_prose}, indent=1))   # entries changed upstream
        (out / "2026-05-22.json").write_text("{not json")                                                                                                          # unreadable
        roots = W.write_ledger_days(src, out)
        self.assertEqual([r["date"] for r in roots], list(days)); self.assertEqual(roots[0]["root_sha256"], root(days["2026-05-20"]))
        self.assertEqual(hashlib.sha256((out / "2026-05-20.json").read_bytes()).hexdigest(), pinned)   # preserved byte-for-byte, old prose and all
        self.assertIn(old_prose, (out / "2026-05-20.json").read_text())
        for d in ("2026-05-21", "2026-05-22", "2026-05-23"):
            got = json.loads((out / f"{d}.json").read_text()); self.assertEqual(got["verify"], W.LEDGER_DAY_VERIFY); self.assertEqual(got["root_sha256"], root(days[d])); self.assertEqual(got["entries"], days[d])
        again = W.write_ledger_days(src, out); self.assertEqual(again, roots)
        self.assertEqual(hashlib.sha256((out / "2026-05-20.json").read_bytes()).hexdigest(), pinned)   # idempotent

    def test_the_tree_s_own_day_files_match_their_roots(self):
        bad = []
        for p in sorted((R / "docs" / "ledger").glob("????-??-??.json")):
            d = json.loads(p.read_text())
            if hashlib.sha256(json.dumps(d["entries"], sort_keys=True).encode()).hexdigest() != d["root_sha256"] or d["date"] != p.stem:
                bad.append(p.name)
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
