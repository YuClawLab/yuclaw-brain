# YUCLAW v8 — User Guide · Guide utilisateur

| | English | Français |
|---|---|---|
| Read on GitHub · Lire sur GitHub | [User Guide (EN)](YUCLAW-v8-User-Guide-EN.md) | [Guide utilisateur (FR)](YUCLAW-v8-User-Guide-FR.md) |
| PDF | [YUCLAW-v8-User-Guide-EN.pdf](YUCLAW-v8-User-Guide-EN.pdf) | [YUCLAW-v8-User-Guide-FR.pdf](YUCLAW-v8-User-Guide-FR.pdf) |
| DOCX (editable · modifiable) | [YUCLAW-v8-User-Guide-EN.docx](YUCLAW-v8-User-Guide-EN.docx) | [YUCLAW-v8-User-Guide-FR.docx](YUCLAW-v8-User-Guide-FR.docx) |

- **Software covered · Logiciel couvert:** YUCLAW **8.0.1** — [PyPI](https://pypi.org/project/yuclaw/8.0.1/) · [release v8.0.1](https://github.com/YuClawLab/yuclaw-brain/releases/tag/v8.0.1)
- **Guide edition · Édition du guide:** **1.1** — 9 October 2026 · 9 octobre 2026 (21 pages per edition · 21 pages par édition)
- Research and education only; not investment advice. · Recherche et formation uniquement ; aucun conseil en placement.
- The guide describes 8.0.1 as released; later versions may change labels or behaviour. · Le guide décrit la version 8.0.1 publiée ; les versions ultérieures peuvent modifier libellés et comportements.
- Mission: Make financial AI accountable to evidence. · Vision: Become the Science Trust Layer for Financial AI.

The two editions cover the same release with the same workflow, numerical examples, limits and recovery steps; the executable
command examples are byte-identical. Interface labels stay in English in both editions because the product's interface is English.

## Source and build · Source et construction

| File | Role |
|---|---|
| `guide_content.json` | The single content source for both languages (one canonical text; the PDF, DOCX and Markdown editions are rendered from it). |
| `build_guides.py` | Renders the two DOCX editions (needs `python-docx`); asserts that the EN and FR command examples are identical. |
| `render_markdown.py` | Renders the two Markdown editions (standard library only). PDF "page N" references become links to section N−1. |
| `SHA256SUMS` | Digests of the published files, for `sha256sum -c`. |

```bash
python3 -m venv .venv && .venv/bin/pip install python-docx
.venv/bin/python build_guides.py        # -> YUCLAW-v8-User-Guide-EN.docx, YUCLAW-v8-User-Guide-FR.docx
soffice --headless --convert-to pdf --outdir . YUCLAW-v8-User-Guide-EN.docx YUCLAW-v8-User-Guide-FR.docx
python3 render_markdown.py              # -> YUCLAW-v8-User-Guide-EN.md, YUCLAW-v8-User-Guide-FR.md
sha256sum -c SHA256SUMS                 # checks the committed files
```

The builder names the fonts Calibri and Menlo; the published PDFs were rendered by LibreOffice 24.2 with the metric-compatible
Carlito and DejaVu Sans Mono. PDF and DOCX bytes vary with the build environment; the text and the page count (21) should not.
Edit `guide_content.json` only, then re-render every edition, so the three formats never diverge.

## Edition history · Historique des éditions

- **1.1 — 9 October 2026.** Corrections after a run against 8.0.1: the loaded fixture claim is `ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base`
  (the loader appends the fixture identifier; the first-run steps and the `build-export` example now use it); interface labels aligned
  (`/modx` is titled "Module evidence export and verification"; the COM task button is "Take (reserves the cost)"); the page footer states the software version and the guide edition; Markdown editions and
  this index added. No change to the workflow, examples, limits or recovery steps.
- **1.0 — 2 October 2026.** First edition for 8.0.1.

Related: the packaged operator guide for the same release ([OPERATOR_GUIDE.md at v8.0.1](https://github.com/YuClawLab/yuclaw-brain/blob/v8.0.1/v8/workbench/resources/OPERATOR_GUIDE.md), also `yuclaw workbench guide`).
The earlier PDF guides in `docs/` were written for the version 5 command line and are historical.
