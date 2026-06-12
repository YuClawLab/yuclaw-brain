"""YUCLAW Lab — self-contained inline-SVG chart design system.

No external libraries, no CDNs, no JS: every chart is a static <svg> string with
a consistent dark-terminal design language (gridlines, labeled axes with units,
tick formatting, legend, panel-tag + N in the title). Two primitives cover every
Lab chart:
  * bar_chart  — categorical/sequential bars over a zero baseline (decile
                 spectrum, IC time-series, turnover).
  * line_chart — one or more series over an integer x-axis, with optional shaded
                 ±band (event study) and right-hand legend (cumulative curves).

Charts render DERIVED STATISTICS only (returns, correlations, spreads). No raw
prices ever reach this layer.
"""

from __future__ import annotations

import math
from html import escape

# ---- design system ---------------------------------------------------------
BG = "#0B0E14"
PANEL = "#151A23"
BORDER = "#1E232D"
GRID = "#1E232D"
GRID_STRONG = "#2D3748"
ZERO = "#4A5568"
TEXT = "#E2E8F0"
MUTED = "#A0AEC0"
FAINT = "#718096"
GREEN = "#00E676"
RED = "#FF3366"
PURPLE = "#7C4DFF"
AMBER = "#FBA94B"
BLUE = "#4DD0E1"
GRAY = "#A0AEC0"
MONO = "JetBrains Mono,ui-monospace,monospace"


def _hex(c):
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def lerp_color(c1: str, c2: str, t: float) -> str:
    """Linear blend between two hex colors (t in 0..1)."""
    a, b = _hex(c1), _hex(c2)
    r, g, bl = (round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return f"#{r:02X}{g:02X}{bl:02X}"


def pct1(v):
    return "—" if v is None else f"{v*100:+.1f}%"


def pct2(v):
    return "—" if v is None else f"{v*100:+.2f}%"


def _nice_bounds(lo: float, hi: float, include_zero=True):
    """Return (ymin, ymax, [ticks]) padded to a clean range with ~5 ticks."""
    if include_zero:
        lo, hi = min(lo, 0.0), max(hi, 0.0)
    if hi == lo:
        hi = lo + 1.0
    span = hi - lo
    pad = span * 0.12
    ymin, ymax = lo - pad, hi + pad
    ticks = [ymin + (ymax - ymin) * k / 4 for k in range(5)]
    return ymin, ymax, ticks


def _title_block(parts, width, title, tag, tag_color, n_label, sub=""):
    """Standard chart header: title (left), panel tag (right), N/sub (2nd line)."""
    parts.append(f'<text x="14" y="22" fill="{TEXT}" font-size="13" font-weight="700" '
                 f'font-family="Inter,sans-serif">{escape(title)}</text>')
    if tag:
        parts.append(f'<text x="{width-14}" y="22" fill="{tag_color}" font-size="10" '
                     f'font-weight="700" text-anchor="end" font-family="{MONO}" '
                     f'letter-spacing="0.5">{escape(tag)}</text>')
    second = " · ".join(s for s in (n_label, sub) if s)
    if second:
        parts.append(f'<text x="14" y="38" fill="{FAINT}" font-size="10.5" '
                     f'font-family="{MONO}">{escape(second)}</text>')


def _svg_open(width, height, title):
    return [f'<svg viewBox="0 0 {width} {height}" width="100%" '
            f'style="background:{BG};border:1px solid {BORDER};border-radius:8px;margin:6px 0" '
            f'role="img" aria-label="{escape(title)}">']


def bar_chart(*, labels, values, colors=None, title, tag="", tag_color=GREEN,
              n_label="", y_axis_label="return", value_fmt=pct1, mean=None,
              mean_label="", x_axis_label="", width=860, height=340,
              rotate_x=False, show_values=True) -> str:
    """Vertical bars over a zero baseline. `values` may contain None (gap)."""
    pad_l, pad_r, pad_t, pad_b = 60, 20, 52, (60 if rotate_x else 44)
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    vals = [v for v in values if v is not None]
    extra = ([mean] if mean is not None else [])
    ymin, ymax, ticks = _nice_bounds(min(vals + extra, default=0.0),
                                     max(vals + extra, default=0.0))
    yr = ymax - ymin

    def Y(v): return pad_t + (ymax - v) / yr * plot_h

    n = len(labels)
    slot = plot_w / n
    bw = slot * 0.62
    parts = _svg_open(width, height, title)
    _title_block(parts, width, title, tag, tag_color, n_label)
    # y gridlines + tick labels (units)
    for tv in ticks:
        yy = Y(tv)
        parts.append(f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{pad_l+plot_w}" y2="{yy:.1f}" '
                     f'stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l-8}" y="{yy+3.5:.1f}" fill="{FAINT}" font-size="9.5" '
                     f'text-anchor="end" font-family="{MONO}">{tv*100:+.1f}%</text>')
    # zero baseline (strong)
    y0 = Y(0.0)
    parts.append(f'<line x1="{pad_l}" y1="{y0:.1f}" x2="{pad_l+plot_w}" y2="{y0:.1f}" '
                 f'stroke="{ZERO}" stroke-width="1.5"/>')
    # bars
    for i, v in enumerate(values):
        cx = pad_l + slot * i + slot / 2
        lx = cx - bw / 2
        col = (colors[i] if colors else GREEN)
        if v is not None:
            top = Y(max(v, 0.0))
            h = abs(Y(v) - y0)
            parts.append(f'<rect x="{lx:.1f}" y="{top:.1f}" width="{bw:.1f}" '
                         f'height="{max(h,0.5):.1f}" fill="{col}" rx="2" opacity="0.92"/>')
            if show_values:
                vy = (Y(v) - 5) if v >= 0 else (Y(v) + 12)
                parts.append(f'<text x="{cx:.1f}" y="{vy:.1f}" fill="{MUTED}" font-size="9" '
                             f'text-anchor="middle" font-family="{MONO}">{value_fmt(v)}</text>')
        # x label
        if rotate_x:
            parts.append(f'<text x="{cx:.1f}" y="{pad_t+plot_h+12:.1f}" fill="{FAINT}" '
                         f'font-size="8.5" text-anchor="end" font-family="{MONO}" '
                         f'transform="rotate(-45 {cx:.1f} {pad_t+plot_h+12:.1f})">{escape(str(labels[i]))}</text>')
        else:
            parts.append(f'<text x="{cx:.1f}" y="{pad_t+plot_h+14:.1f}" fill="{FAINT}" '
                         f'font-size="9.5" text-anchor="middle" font-family="{MONO}">{escape(str(labels[i]))}</text>')
    # mean line
    if mean is not None:
        my = Y(mean)
        parts.append(f'<line x1="{pad_l}" y1="{my:.1f}" x2="{pad_l+plot_w}" y2="{my:.1f}" '
                     f'stroke="{AMBER}" stroke-width="1.3" stroke-dasharray="5,3"/>')
        parts.append(f'<text x="{pad_l+plot_w}" y="{my-4:.1f}" fill="{AMBER}" font-size="9.5" '
                     f'text-anchor="end" font-family="{MONO}">{escape(mean_label)}</text>')
    # axis titles
    parts.append(f'<text x="13" y="{pad_t+plot_h/2:.1f}" fill="{FAINT}" font-size="9.5" '
                 f'text-anchor="middle" font-family="{MONO}" '
                 f'transform="rotate(-90 13 {pad_t+plot_h/2:.1f})">{escape(y_axis_label)}</text>')
    if x_axis_label:
        parts.append(f'<text x="{pad_l+plot_w/2:.1f}" y="{height-6}" fill="{FAINT}" '
                     f'font-size="9.5" text-anchor="middle" font-family="{MONO}">{escape(x_axis_label)}</text>')
    parts.append('</svg>')
    return "".join(parts)


def drawdown_chart(*, cum, title, tag="", tag_color=PURPLE, n_label="",
                   max_dd=None, color=PURPLE, width=900, height=320,
                   x_axis_label="rebalance period") -> str:
    """Cumulative curve (cum = multipliers, baseline 1.0) with underwater
    drawdown shading vs the running peak + max-drawdown annotation."""
    pad_l, pad_r, pad_t, pad_b = 60, 22, 52, 46
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    rets = [c - 1.0 for c in cum]
    series_v = [0.0] + rets
    ymin, ymax, ticks = _nice_bounds(min(series_v), max(series_v))
    yr = ymax - ymin
    n = len(series_v)
    xmax = max(n - 1, 1)

    def X(i): return pad_l + (i / xmax) * plot_w
    def Y(v): return pad_t + (ymax - v) / yr * plot_h

    # running peak + drawdown trough index
    peak, peaks, dd_idx, dd_min = -1e9, [], 0, 0.0
    for i, v in enumerate(series_v):
        peak = max(peak, v)
        peaks.append(peak)
        if v - peak < dd_min:
            dd_min, dd_idx = v - peak, i

    parts = _svg_open(width, height, title)
    _title_block(parts, width, title, tag, tag_color, n_label)
    for tv in ticks:
        yy = Y(tv)
        parts.append(f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{pad_l+plot_w}" y2="{yy:.1f}" '
                     f'stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l-8}" y="{yy+3.5:.1f}" fill="{FAINT}" font-size="9.5" '
                     f'text-anchor="end" font-family="{MONO}">{tv*100:+.1f}%</text>')
    parts.append(f'<line x1="{pad_l}" y1="{Y(0):.1f}" x2="{pad_l+plot_w}" y2="{Y(0):.1f}" '
                 f'stroke="{ZERO}" stroke-width="1.5"/>')
    # underwater shading: between curve and running peak
    up = [(X(i), Y(peaks[i])) for i in range(n)]
    dn = [(X(i), Y(series_v[i])) for i in range(n)]
    parts.append(f'<polygon points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in up+dn[::-1])}" '
                 f'fill="{RED}" opacity="0.13"/>')
    parts.append(f'<polyline points="{" ".join(f"{X(i):.1f},{Y(p):.1f}" for i,p in enumerate(peaks))}" '
                 f'fill="none" stroke="{FAINT}" stroke-width="1" stroke-dasharray="3,3"/>')
    parts.append(f'<polyline points="{" ".join(f"{X(i):.1f},{Y(v):.1f}" for i,v in enumerate(series_v))}" '
                 f'fill="none" stroke="{color}" stroke-width="2"/>')
    # max-drawdown annotation
    if max_dd is not None:
        mx, my = X(dd_idx), Y(series_v[dd_idx])
        parts.append(f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="3" fill="{RED}"/>')
        parts.append(f'<text x="{mx:.1f}" y="{my+16:.1f}" fill="{RED}" font-size="9.5" '
                     f'text-anchor="middle" font-family="{MONO}">max DD {max_dd*100:.1f}%</text>')
    parts.append(f'<text x="{pad_l+plot_w/2:.1f}" y="{height-6}" fill="{FAINT}" font-size="9.5" '
                 f'text-anchor="middle" font-family="{MONO}">{escape(x_axis_label)}</text>')
    parts.append(f'<text x="13" y="{pad_t+plot_h/2:.1f}" fill="{FAINT}" font-size="9.5" '
                 f'text-anchor="middle" font-family="{MONO}" '
                 f'transform="rotate(-90 13 {pad_t+plot_h/2:.1f})">cumulative spread</text>')
    parts.append('</svg>')
    return "".join(parts)


def line_chart(*, series, x_count, title, tag="", tag_color=GREEN, n_label="",
               y_axis_label="return", x_axis_label="", x_ticks=None,
               width=900, height=360, baseline=0.0, day0_marker=False,
               legend_right=True) -> str:
    """One or more line series over integer x 0..x_count-1.
    series: [{name, color, ys:[float], band:[float]|None}]. band shades ±band."""
    pad_l = 60
    pad_r = 168 if legend_right else 22
    pad_t, pad_b = 52, 46
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    allv = []
    for s in series:
        ys, band = s["ys"], s.get("band")
        allv += [y for y in ys if y is not None]
        if band:
            allv += [ys[i] + band[i] for i in range(len(ys)) if ys[i] is not None]
            allv += [ys[i] - band[i] for i in range(len(ys)) if ys[i] is not None]
    ymin, ymax, ticks = _nice_bounds(min(allv, default=0.0), max(allv, default=0.0))
    yr = ymax - ymin
    xmax = max(x_count - 1, 1)

    def X(i): return pad_l + (i / xmax) * plot_w
    def Y(v): return pad_t + (ymax - v) / yr * plot_h

    parts = _svg_open(width, height, title)
    _title_block(parts, width, title, tag, tag_color, n_label)
    for tv in ticks:
        yy = Y(tv)
        parts.append(f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{pad_l+plot_w}" y2="{yy:.1f}" '
                     f'stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l-8}" y="{yy+3.5:.1f}" fill="{FAINT}" font-size="9.5" '
                     f'text-anchor="end" font-family="{MONO}">{tv*100:+.1f}%</text>')
    # x ticks
    ticks_x = x_ticks if x_ticks is not None else [(i, str(i)) for i in range(0, x_count, max(1, x_count // 8))]
    for xi, lab in ticks_x:
        xx = X(xi)
        parts.append(f'<text x="{xx:.1f}" y="{pad_t+plot_h+14:.1f}" fill="{FAINT}" font-size="9" '
                     f'text-anchor="middle" font-family="{MONO}">{escape(str(lab))}</text>')
    # baseline
    yb = Y(baseline)
    parts.append(f'<line x1="{pad_l}" y1="{yb:.1f}" x2="{pad_l+plot_w}" y2="{yb:.1f}" '
                 f'stroke="{ZERO}" stroke-width="1.5"/>')
    if day0_marker:
        x0 = X(0)
        parts.append(f'<line x1="{x0:.1f}" y1="{pad_t}" x2="{x0:.1f}" y2="{pad_t+plot_h}" '
                     f'stroke="{GRID_STRONG}" stroke-width="1" stroke-dasharray="2,3"/>')
        parts.append(f'<text x="{x0+3:.1f}" y="{pad_t+10}" fill="{FAINT}" font-size="8.5" '
                     f'font-family="{MONO}">event day 0</text>')
    # bands then lines
    for s in series:
        ys, band, col = s["ys"], s.get("band"), s["color"]
        if band:
            up = [(X(i), Y(ys[i] + band[i])) for i in range(len(ys)) if ys[i] is not None]
            dn = [(X(i), Y(ys[i] - band[i])) for i in range(len(ys)) if ys[i] is not None]
            poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in up + dn[::-1])
            parts.append(f'<polygon points="{poly}" fill="{col}" opacity="0.12"/>')
    for k, s in enumerate(series):
        ys, col = s["ys"], s["color"]
        pts = " ".join(f"{X(i):.1f},{Y(y):.1f}" for i, y in enumerate(ys) if y is not None)
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2"/>')
        if legend_right:
            ly = pad_t + 6 + k * 19
            parts.append(f'<line x1="{pad_l+plot_w+14}" y1="{ly}" x2="{pad_l+plot_w+30}" '
                         f'y2="{ly}" stroke="{col}" stroke-width="3"/>')
            tail = next((y for y in reversed(ys) if y is not None), None)
            tail_s = f" {tail*100:+.1f}%" if tail is not None else ""
            parts.append(f'<text x="{pad_l+plot_w+34}" y="{ly+3.5}" fill="{TEXT}" font-size="10" '
                         f'font-family="{MONO}">{escape(s["name"])}{tail_s}</text>')
    parts.append(f'<text x="13" y="{pad_t+plot_h/2:.1f}" fill="{FAINT}" font-size="9.5" '
                 f'text-anchor="middle" font-family="{MONO}" '
                 f'transform="rotate(-90 13 {pad_t+plot_h/2:.1f})">{escape(y_axis_label)}</text>')
    if x_axis_label:
        parts.append(f'<text x="{pad_l+plot_w/2:.1f}" y="{height-6}" fill="{FAINT}" '
                     f'font-size="9.5" text-anchor="middle" font-family="{MONO}">{escape(x_axis_label)}</text>')
    parts.append('</svg>')
    return "".join(parts)
