"""Packaged `yuclaw replay-lab` — reproduce the Validation Lab from the public bundle.

PACKAGED MIRROR of tools/replay_lab.py (the stdlib-only standalone script, which
stays working as-is for users who do not want to install anything). DUAL-COPY
RULE: any logic change must be applied to BOTH files identically.

Usage:
    yuclaw replay-lab                      # fetch the public bundle, verify
    yuclaw replay-lab bundle.json          # verify a local bundle
    yuclaw replay-lab --check              # alias for the default fetch+verify

Exit 0 = fully reproduced (statistics + ledger roots); non-zero with a diff
report otherwise. Stdlib only. Research/education only — not investment advice.
"""


from __future__ import annotations

import hashlib
import json
import math
import random
import sys

TOL = 1e-9


# ---------- stats (verbatim re-implementations of v3/lab/stats.py) ----------
def mean(xs): return sum(xs) / len(xs)


def stdev(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def _betacf(a, b, x):
    MAXIT, EPS, FPMIN = 200, 3e-12, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < FPMIN: d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN: d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN: c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN: d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN: c = FPMIN
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < EPS:
            break
    return h


def _betai(a, b, x):
    if x <= 0.0: return 0.0
    if x >= 1.0: return 1.0
    ln_bt = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
             + a * math.log(x) + b * math.log(1.0 - x))
    bt = math.exp(ln_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_pvalue_two_sided(t, df):
    """Two-sided p for Student-t (exact via regularized incomplete beta)."""
    t = abs(t)
    return min(1.0, _betai(df / 2.0, 0.5, df / (df + t * t)))


def one_sample_t(xs):
    n = len(xs)
    if n < 2: return {"mean": mean(xs) if n else None, "t": None, "p": None, "n": n}
    m, s = mean(xs), stdev(xs)
    if s == 0: return {"mean": m, "t": None, "p": None, "n": n}
    t = m / (s / math.sqrt(n))
    return {"mean": m, "t": t, "p": t_pvalue_two_sided(t, n - 1), "n": n}


def bootstrap_ci_mean(xs, iters=10_000, alpha=0.05, seed=20260518):
    n = len(xs)
    if n < 3: return None
    rng = random.Random(seed)
    means = []
    for _ in range(iters):
        means.append(sum(rng.choice(xs) for _ in range(n)) / n)
    means.sort()
    return (means[int((alpha / 2) * iters)],
            means[min(iters - 1, int((1 - alpha / 2) * iters))])


def newey_west_t(xs, lag):
    n = len(xs)
    if n < 3: return {"mean": mean(xs) if n else None, "t": None, "p": None, "n": n, "lag": lag}
    lag = max(0, min(lag, n - 2))
    m = mean(xs)
    e = [x - m for x in xs]
    s = sum(v * v for v in e) / n
    for l in range(1, lag + 1):
        gl = sum(e[i] * e[i - l] for i in range(l, n)) / n
        s += 2.0 * (1.0 - l / (lag + 1.0)) * gl
    if s <= 0: return {"mean": m, "t": None, "p": None, "n": n, "lag": lag}
    t = m / math.sqrt(s / n)
    return {"mean": m, "t": t, "p": t_pvalue_two_sided(abs(t), n - 1), "n": n, "lag": lag}


def _ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def pearson(xs, ys):
    n = len(xs)
    if n < 2: return None
    mx, my = mean(xs), mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0: return None
    return sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / math.sqrt(sxx * syy)


def spearman(xs, ys):
    if len(xs) != len(ys) or len(xs) < 2: return None
    return pearson(_ranks(xs), _ranks(ys))


def ols(y, x):
    n = len(y)
    if n < 3 or len(x) != n: return None
    mx, my = mean(x), mean(y)
    sxx = sum((xi - mx) ** 2 for xi in x)
    if sxx == 0: return None
    beta = sum((x[i] - mx) * (y[i] - my) for i in range(n)) / sxx
    alpha = my - beta * mx
    resid = [y[i] - alpha - beta * x[i] for i in range(n)]
    sse = sum(r * r for r in resid)
    sst = sum((yi - my) ** 2 for yi in y)
    df = n - 2
    s2 = sse / df
    se_alpha = math.sqrt(s2 * (1.0 / n + mx * mx / sxx))
    t_alpha = alpha / se_alpha if se_alpha > 0 else None
    return {"alpha": alpha, "beta": beta, "t_alpha": t_alpha,
            "p_alpha": t_pvalue_two_sided(abs(t_alpha), df) if t_alpha is not None else None,
            "r2": 1.0 - sse / sst if sst > 0 else None, "n": n}


# ---------- reproduction ----------
FAILURES: list[str] = []


def check(label, got, want, tol=1e-6):
    if want is None and got is None:
        return
    if want is None or got is None:
        FAILURES.append(f"{label}: got {got}, expected {want}")
        return
    if abs(float(got) - float(want)) > tol:
        FAILURES.append(f"{label}: got {got:.10f}, expected {float(want):.10f}")


def content_hash(snapshot_id, total_score, components):
    """Ledger leaf hash (must match v3/proof/_hash.py)."""
    parts = [snapshot_id, f"{float(total_score):.6f}"]
    for cid in sorted(components):
        parts.append(f"{cid}={float(components[cid]):.6f}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _run(path):
    bundle = json.load(open(path))
    meta = bundle["methodology"]
    print(f"Replay bundle built {bundle['built_utc']} from source commit "
          f"{(bundle.get('source_commit') or '?')[:12]}")
    print(f"Ledger repo: {bundle['ledger_repo']} @ {(bundle.get('ledger_commit') or '?')[:12]}\n")
    min_uni = meta["min_universe_for_deciles"]

    for panel in ("forward", "in_sample"):
        p = bundle["panels"][panel]
        exp = bundle["expected"].get(panel, {})
        if not exp.get("evaluable"):
            print(f"[{panel}] not evaluable in expected block — skipped")
            continue
        # 0. rebuild cohorts from scores; re-derive cohort period returns
        top, bot, uew, spy = [], [], [], []
        for rb in p["rebalances"]:
            scores, rets = rb["scores"], rb["period_returns"]
            if len(scores) < min_uni:
                continue  # inclusion rule
            ranked = sorted(scores, key=lambda tk: -scores[tk])  # ties: ticker order (stable)
            k = max(1, round(len(ranked) * meta["decile_fraction"]))

            def cret(tks):
                vals = [rets[t] for t in tks if t in rets]
                return sum(vals) / len(vals) if vals else 0.0

            top.append(cret(ranked[:k]))
            bot.append(cret(ranked[-k:]))
            uew.append(cret(list(scores)))
            spy.append(rb["spy_ret"])
        print(f"[{panel}] {len(top)} rebalance periods, window {p['window']}")

        # 1. spread tests
        for key, a, b in (("top_minus_bottom", top, bot), ("top_minus_universe", top, uew)):
            diffs = [a[i] - b[i] for i in range(len(a))]
            t = one_sample_t(diffs)
            ci = bootstrap_ci_mean(diffs, seed=meta["bootstrap"]["seed"])
            e = exp["spreads"][key]
            check(f"{panel}.{key}.mean", t["mean"], e["mean_per_period"], 1e-9)
            check(f"{panel}.{key}.t", t["t"], e["t_stat"], 1e-6)
            if ci and e.get("ci95"):
                check(f"{panel}.{key}.ci_lo", ci[0], e["ci95"][0], 1e-9)
                check(f"{panel}.{key}.ci_hi", ci[1], e["ci95"][1], 1e-9)
            print(f"  spread {key:18s} mean/period {t['mean']:+.5f}  t={t['t']:+.2f} "
                  f"p={t['p']:.3f}  n={t['n']}  CI95=({ci[0]:+.5f},{ci[1]:+.5f})")

        # 2. IC (Fama-MacBeth with NW t)
        by_date = {}
        for row in p["ic_rows"]:
            by_date.setdefault(row["date"], []).append(row)
        for h, rk in ((1, "r1"), (5, "r5"), (20, "r20")):
            ics, dts = [], []
            for d in sorted(by_date):
                rows = [r for r in by_date[d] if r[rk] is not None]
                if len(rows) < min_uni:
                    continue
                rho = spearman([r["score"] for r in rows], [r[rk] for r in rows])
                if rho is not None:
                    ics.append(rho)
                    dts.append(d)
            e = exp["ic"][str(h)] if str(h) in exp["ic"] else exp["ic"][h]
            if len(ics) >= 2:
                t = one_sample_t(ics)
                span_days = ((_d(dts[-1]) - _d(dts[0])).days or 1)
                avg_sp = max(1.0, span_days * (5.0 / 7.0) / max(1, len(ics) - 1))
                lag = max(0, math.ceil(h / avg_sp) - 1)
                nw = newey_west_t(ics, lag)
                check(f"{panel}.ic{h}.mean", t["mean"], e["mean_ic"], 1e-9)
                check(f"{panel}.ic{h}.nw_t", nw["t"], e["nw_t_stat"], 1e-6)
                rel = "" if e.get("t_reliable", True) else "  [T too small — descriptive only]"
                print(f"  IC {h:2d}d  mean {t['mean']:+.4f}  NW-t={nw['t']:+.2f} "
                      f"(lag {nw['lag']}) p={nw['p']:.3f}  T={t['n']} dates{rel}")

        # 3. market model
        for key, mkt in (("vs_universe", uew), ("vs_spy", spy)):
            r = ols(top, mkt)
            e = exp["market_model"][key]
            check(f"{panel}.mm.{key}.alpha", r["alpha"], e["alpha_per_period"], 1e-9)
            check(f"{panel}.mm.{key}.beta", r["beta"], e["beta"], 1e-9)
            print(f"  market-model {key:12s} alpha/period {r['alpha']:+.5f} "
                  f"beta {r['beta']:+.2f}  t(alpha)={r['t_alpha']:+.2f} "
                  f"p={r['p_alpha']:.3f}  R2={r['r2']:.3f}  n={r['n']}")
        print()

    # 4. ledger verification: recompute every leaf hash + daily root from the
    # bundled derived inputs; match against the public ledger roots. On days
    # with an intraday re-run the DB holds MORE rows than the ledger anchored
    # (the block is written once, at the first run); the check then verifies
    # that every ANCHORED hash still recomputes from today's data (subset
    # check) — the actual tamper-evidence property.
    blocks = {b["date"]: b for b in bundle.get("ledger_daily_roots", [])}
    n_ok = n_subset = n_missing = n_leaves = 0
    for d, leaves in sorted(bundle.get("ledger_leaves", {}).items()):
        hashes = [content_hash(l["snapshot_id"], l["total_score"], l["components"])
                  for l in leaves]
        n_leaves += len(hashes)
        root = hashlib.sha256("|".join(sorted(hashes)).encode()).hexdigest()
        b = blocks.get(d)
        if b is None:
            n_missing += 1
            continue
        if root == b["daily_root"]:
            n_ok += 1
        elif b.get("entry_hashes") and set(b["entry_hashes"]).issubset(hashes):
            n_subset += 1
            print(f"  note: {d} — ledger anchored {len(b['entry_hashes'])} of "
                  f"{len(hashes)} rows (intraday re-run after the anchor); all "
                  f"anchored hashes verified unmutated")
        else:
            FAILURES.append(f"ledger root mismatch on {d}")
    print(f"Ledger verification: {n_ok} daily roots exact"
          + (f" + {n_subset} anchored-subset days" if n_subset else "")
          + f" ({n_leaves} leaf hashes recomputed)"
          + (f"; {n_missing} dates have no public ledger block" if n_missing else ""))

    if FAILURES:
        print("\nREPRODUCTION FAILED:")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("\nREPRODUCED OK — every recomputed statistic matches the published page.")
    return 0


def _d(s):
    from datetime import date
    return date.fromisoformat(s)


BUNDLE_URL = "https://yuclawlab.github.io/yuclaw-brain/replay/lab_replay_bundle.json"


# Exit codes: 0 = reproduced, 1 = statistic/root mismatch, 2 = argparse,
# 3 = could not fetch the published bundle (network/proxy — not a data problem).
EXIT_FETCH_FAILED = 3


class _FetchError(Exception):
    pass


def _fetch(url: str) -> str:
    import tempfile
    import urllib.error
    import urllib.request
    print(f"fetching {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "yuclaw-replay-lab"})
    try:
        data = urllib.request.urlopen(req, timeout=120).read()
    except urllib.error.HTTPError as e:
        raise _FetchError(f"HTTP {e.code} fetching the replay bundle\n  URL: {url}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        reason = getattr(e, "reason", e)
        raise _FetchError(f"could not reach the replay-bundle host ({reason})\n  URL: {url}") from e
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.write(data)
    tmp.close()
    print(f"  {len(data):,} bytes -> {tmp.name}")
    return tmp.name


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="yuclaw replay-lab",
                                description="Reproduce the Validation Lab's statistics and "
                                            "ledger roots from the public replay bundle.")
    p.add_argument("bundle", nargs="?", help="path to lab_replay_bundle.json "
                                             "(default: fetch the published bundle)")
    p.add_argument("--check", action="store_true",
                   help="explicit check mode (same as the default behavior)")
    a = p.parse_args(argv)
    try:
        path = a.bundle or _fetch(BUNDLE_URL)
    except _FetchError as e:
        print(f"\n[replay-lab] bundle fetch failed: {e}\n"
              f"  Check connectivity/proxy and retry. The bundle is also downloadable\n"
              f"  manually at {BUNDLE_URL} — then run:\n"
              f"  yuclaw replay-lab /path/to/lab_replay_bundle.json", file=sys.stderr)
        return EXIT_FETCH_FAILED
    return _run(path)


if __name__ == "__main__":
    sys.exit(main())
