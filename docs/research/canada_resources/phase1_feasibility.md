# YUCLAW Canada Resources — Phase 1 Feasibility & Coverage Study

**As of:** 2026-07-13 (study date). Research-only. Evidence dashboard groundwork. Not investment advice.
**Method:** read-only EDGAR queries + issuer holdings disclosures. Coverage is measured and scoped; missing data is excluded, not imputed.

## Verdict

An evidence-first Canada energy/resources section can stand on SEC filings. Every candidate lens measured above ~50% SEC-filer weight coverage; four of seven cleared 75%. Recommended Phase 2 scope: **XEG + ZEO (oil & gas), GDX (gold), URNM (uranium)**, with **EWC reference-only** and **GDXJ excluded** (52% coverage with a 68-name silent tail is below the honesty bar).

## Measured SEC-filer coverage by lens

| Lens | Theme | SEC-filer weight | Domestic (10-K/8-K) | MJDS (40-F/6-K) | Other FPI (20-F/6-K) | No EDGAR substrate | Names covered |
|---|---|---|---|---|---|---|---|
| EWC | Broad Canada (reference) | 82% | 10% | 72% | 0% | 18% | 53/83 |
| GDX | Gold miners | 79% | 17% | 51% | 11% | 21% | 28/51 |
| XEG | Cdn oil & gas (cap-wt) | 76% | 7% | 70% | 0% | 24% | 8/28 |
| ZEO | Cdn oil & gas (equal-wt) | 75% | 16% | 59% | 0% | 25% | 9/12 |
| URA | Uranium (Global X) | 59% | 21% | 34% | 4% | 41% | 18/52 |
| URNM | Uranium (Sprott) | 55% | 12% | 42% | 0% | 45% | 9/26 |
| GDXJ | Junior gold (excluded) | 52% | 13% | 36% | 3% | 48% | 46/114 |

Holdings sources (weights used only to derive coverage statistics; no licensed index data redistributed):
XEG — BlackRock Canada holdings CSV as of 2026-07-10; URA — Global X holdings CSV as of 2026-07-10;
ZEO — stockanalysis.com as of 2026-07-09 (issuer page unavailable at study time);
EWC — NPORT-P 0001410368-26-039462 (period 2026-02-28); GDX — NPORT-P 0001410368-26-054846 (2026-03-31);
GDXJ — NPORT-P 0001410368-26-054843 (2026-03-31); URNM — NPORT-P 0001049169-26-001608 (2026-03-31). All NPORT-P via SEC EDGAR.

## What the uncovered weight is (scope statements, not caveats)

- **Oil & gas:** TSX-only issuers with no current EDGAR reporting — Tourmaline (5.6% XEG), ARC Resources (9.0% ZEO), Keyera (8.5% ZEO), PrairieSky, Peyto, Athabasca, CES Energy. Several have 2026-era "/ADR" CIKs; these are F-6 depositary shells, not reporting companies, and are counted as uncovered.
- **Uranium:** Sprott Physical Uranium Trust (13.6% of URNM) does **not** file EDGAR (unlike PHYS/PSLV) and is a physical trust outside ordinary operating-company evidence scope by nature; Kazatomprom (LSE GDR), Yellow Cake plc (LSE), and the ASX cohort (Paladin, Boss, Deep Yellow, Bannerman) have no EDGAR substrate.
- **GDXJ:** a 68-name tail of ASX/LSE/TSXV juniors with no EDGAR substrate — the reason the lens is excluded.

## 6-K structural findings (12 filings sampled: SU, CNQ, CVE, CCJ, TRP, AEM)

- Every 6-K is an **envelope**: 1–3KB boilerplate cover + substance furnished as exhibits (EX-99.1…99.N; TC Energy variant uses EX-13.1/13.2 for MD&A/financials).
- All sampled exhibits were clean native HTML (no PDF/image-only). Earnings exhibits strip to 24K–158K chars of prose; thin news 6-Ks 1.7–4K chars. Suncor-class filings pad with zero-width spaces (needs stripping).
- **No item codes anywhere** (SGML header and submissions JSON `items` empty) — classification must come from exhibit text, with the cover page's one-line exhibit descriptions as hints.
- **Enbridge and Imperial Oil are US-domestic-form filers** (10-K/8-K) and ride the existing pipeline unchanged. Agnico Eagle, despite NYSE listing, is a standard MJDS filer.
- Cadence: 17–30 6-Ks/yr per major name.

## Insider channel (stated plainly)

MJDS insiders file on **SEDI in Canada, not Form 4**. Zero Form 4s since 2024 for all sampled MJDS names. Even domestic-form FPIs (Enbridge, Imperial Oil) have zero Form 4s (FPI Section 16 exemption is independent of form choice). A live Form 4 stream exists only for true US domestics in the add-list (NEM, CDE, HL, RGLD, SSRM, UEC, UUUU, URG). Insider-derived metrics for MJDS names are **outside current evidence scope** — excluded, not rendered as zero.

## Price-feed implication

48 of the 49 core-lens SEC filers have NYSE/Nasdaq-listed US lines servable by the existing feed with no `.TO` handling. The single exception is Whitecap Resources (OTC `WCPRF`) — a low-quality OTC proxy line, flagged as such.

## Add-list

See `addlist_final.json` (123 SEC filers across all 7 lenses, with CIKs, filer class, US lines, lens weights) and `addlist_table.md` (human-readable table). The Phase 2 evidence tier is the 49-name subset appearing in XEG/ZEO/GDX/URNM.

## EDGAR-matching traps recorded for reproducibility

1. The submissions-JSON "recent" window (last 1000 filings) hides 6-K/40-F for high-volume filers (Canadian banks flooded by 424B2/FWP) — verify via per-form browse-edgar queries.
2. EDGAR contains stale same-name CIKs (e.g. Bank of Montreal CIK 9622 is dead; the live filer is 927971 "/CAN/").
3. New 2026-era "/ADR" CIKs (Tourmaline, Keyera, ARC, Peyto, PrairieSky, Topaz, Tamarack, Dollarama) are F-6 shells, not evidence of SEC reporting.
4. Sprott Physical Uranium Trust and Yellow Cake plc are large uranium-lens holdings with plausible-but-wrong EDGAR name matches (Sprott Inc; the defunct Yellow Corp) — both verified uncovered.
