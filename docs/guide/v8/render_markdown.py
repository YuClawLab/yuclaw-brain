#!/usr/bin/env python3
"""Render the readable Markdown editions of the YUCLAW v8 user guide.

Reads guide_content.json — the SAME source build_guides.py reads for the DOCX (and, through LibreOffice, the PDF) — and
writes YUCLAW-v8-User-Guide-EN.md and YUCLAW-v8-User-Guide-FR.md next to it. Nothing is edited by hand in the output.
The only transformation beyond formatting: the PDF's "page N" cross-references become links to the numbered sections
(PDF page N is section N-1, because page 1 is the cover).
"""
from pathlib import Path
import json, re

HERE = Path(__file__).resolve().parent
DATA = HERE / 'guide_content.json'
STRINGS = {
    'EN': dict(file='YUCLAW-v8-User-Guide-EN.md', title='YUCLAW Version 8 — User Guide', contents='Contents',
               section='section', sections='sections', this_page='This page', this_section='This section',
               downloads='Downloads', other='Version française : [Guide utilisateur (FR)](YUCLAW-v8-User-Guide-FR.md)',
               pdf='PDF', docx='DOCX (editable)', index='Guide index (bilingual)',
               note='This Markdown edition is rendered from the same `guide_content.json` as the PDF and DOCX editions '
                    '(`render_markdown.py`). Page references in the PDF correspond to the numbered sections below.'),
    'FR': dict(file='YUCLAW-v8-User-Guide-FR.md', title='YUCLAW Version 8 — Guide utilisateur', contents='Table des matières',
               section='section', sections='sections', this_page='Cette page', this_section='Cette section',
               downloads='Téléchargements', other='English version: [User Guide (EN)](YUCLAW-v8-User-Guide-EN.md)',
               pdf='PDF', docx='DOCX (modifiable)', index='Index du guide (bilingue)',
               note='Cette édition Markdown est produite à partir du même fichier `guide_content.json` que les éditions PDF '
                    'et DOCX (`render_markdown.py`). Les renvois aux pages du PDF correspondent aux sections numérotées ci-dessous.'),
}


def anchor(title: str) -> str:
    """GitHub's heading anchor: lower-case, drop punctuation, spaces to hyphens (unicode letters are kept)."""
    t = re.sub(r'[^\w\- ]', '', title.lower())
    return t.replace(' ', '-')


def inline(text: str) -> str:
    """Escape Markdown-sensitive characters outside `code` spans; the source already uses `code` and **bold**."""
    out = []
    for part in re.split(r'(`[^`]+`)', text):
        if part.startswith('`'):
            out.append(part)
        else:
            out.append(part.replace('<', '\\<').replace('>', '\\>').replace('|', '\\|'))
    return ''.join(out)


def code_lang(block: str) -> str:
    return 'powershell' if re.search(r'^(py -3|& "|\$env:)', block, re.M) else 'bash'


def render(lang: str, pages: list, s: dict) -> str:
    chapters = pages[1:]                                       # pages[0] is the cover; PDF page N is pages[N-1]
    anchors = {i + 1: anchor(p['title']) for i, p in enumerate(chapters)}   # chapter number -> anchor

    def pageref(m):
        word, a, b = m.group(1), int(m.group(2)), m.group(3)
        if not (2 <= a <= len(pages)):
            return m.group(0)
        cap = word[0].isupper()
        if b:
            b = int(b)
            label = s['sections'].capitalize() if cap else s['sections']
            return f"{label} [{a-1}](#{anchors[a-1]})–[{b-1}](#{anchors[b-1]})"
        label = s['section'].capitalize() if cap else s['section']
        return f"{label} [{a-1}](#{anchors[a-1]})"

    def text(t: str) -> str:
        t = inline(t)
        t = re.sub(r'\b([Pp]ages?) (\d+)(?:–(\d+))?', pageref, t)
        return t.replace(s['this_page'], s['this_section'])

    L = []
    cover = pages[0]
    L.append(f"# {s['title']}")
    L.append('')
    L.append(f"*{inline(cover['subtitle'])}*")
    L.append('')
    L.append(f"{s['downloads']}: [{s['pdf']}](YUCLAW-v8-User-Guide-{lang}.pdf) · [{s['docx']}](YUCLAW-v8-User-Guide-{lang}.docx) · "
             f"[{s['index']}](README.md)  ")
    L.append(s['other'])
    L.append('')
    L.append(f"> {s['note']}")
    L.append('')
    L += blocks(cover['blocks'], text, s)
    L.append(f"## {s['contents']}")
    L.append('')
    for i, p in enumerate(chapters, 1):
        L.append(f"{i}. [{inline(p['title'])}](#{anchors[i]})")
    L.append('')
    for i, p in enumerate(chapters, 1):
        L.append(f"## {inline(p['title'])}")
        L.append('')
        L += blocks(p['blocks'], text, s)
    return '\n'.join(L).rstrip() + '\n'


def blocks(items, text, s):
    L, n = [], 0
    for b in items:
        k = b[0]
        if k != 'n':
            n = 0
        if k == 'p':
            for para in b[1].split('\n'):
                L.append(text(para)); L.append('')
        elif k == 'h':
            L.append(f"### {text(b[1])}"); L.append('')
        elif k == 'b':
            L.append(f"- {text(b[1])}")
            L.append('')
        elif k == 'n':
            n += 1; L.append(f"{n}. {text(b[1])}"); L.append('')
        elif k == 'code':
            L.append(f"```{code_lang(b[1])}"); L.append(b[1]); L.append('```'); L.append('')
        elif k == 'table':
            headers, rows = b[1], b[2]
            L.append('| ' + ' | '.join(text(h) for h in headers) + ' |')
            L.append('|' + '---|' * len(headers))
            for r in rows:
                L.append('| ' + ' | '.join(text(c) for c in r) + ' |')
            L.append('')
        elif k == 'link':
            L.append(f"- [{inline(b[1])}]({b[2]})" + (f" — {text(b[3])}" if len(b) > 3 and b[3] else ''))
            L.append('')
        elif k == 'gap':
            pass
        else:
            raise SystemExit(f"unknown block kind {k!r}")
    # merge consecutive bullets (remove blank lines between list items of the same kind)
    out = []
    for i, line in enumerate(L):
        if line == '' and i + 1 < len(L) and out and re.match(r'^(- |\d+\. )', out[-1]) and re.match(r'^(- |\d+\. )', L[i + 1]):
            continue
        out.append(line)
    return out


if __name__ == '__main__':
    data = json.loads(DATA.read_text(encoding='utf-8'))
    for lang, pages in data.items():
        s = STRINGS[lang]
        path = HERE / s['file']
        path.write_text(render(lang, pages, s), encoding='utf-8')
        print(path, len(pages) - 1, 'sections')
