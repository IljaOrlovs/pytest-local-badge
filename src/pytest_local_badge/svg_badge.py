import bisect
import importlib.resources
import json
import textwrap
import typing
from functools import cache
from xml.sax.saxutils import escape as xml_escape

# Horizontal padding (in px) added to each half of the badge — 5px on
# either side of the text. Matches shields.io's badge geometry so locally
# generated badges visually line up with their hosted siblings.
_HORIZONTAL_PADDING = 10


COLORS = {
    "brightgreen": "#4c1",
    "green": "#97ca00",
    "yellowgreen": "#a4a61d",
    "yellow": "#dfb317",
    "orange": "#fe7d37",
    "red": "#e05d44",
    "lightgrey": "#9f9f9f",
    "blue": "#007ec6",
}


# Verdana 11px character widths, originally measured by the `anafanafo` project
# (https://github.com/metabolize/anafanafo, MIT). Format: a list of
# [lo, hi, width] triples, sorted by `lo`, covering ranges of Unicode code
# points. shields.io uses the same table for its badge layout, so widths
# computed here match shields' rendered output.
@cache
def _width_table() -> list[tuple[int, int, float]]:
    raw = (
        importlib.resources.files(__package__)
        .joinpath("verdana_11px_normal.json")
        .read_text(encoding="utf-8")
    )
    return [tuple(entry) for entry in json.loads(raw)]


@cache
def _width_table_lowers() -> list[int]:
    return [entry[0] for entry in _width_table()]


@cache
def _em_width() -> float:
    """Fallback glyph width — used for code points not in the table."""
    return _width_of_codepoint(ord("m")) or 7.0


def _width_of_codepoint(code_point: int) -> float:
    # Control characters render as zero width — matches anafanafo's behaviour.
    if code_point <= 31 or code_point == 127:
        return 0.0
    table = _width_table()
    lowers = _width_table_lowers()
    idx = bisect.bisect_right(lowers, code_point) - 1
    if idx < 0:  # pragma: no cover
        # Defensive: code points < 32 are caught by the control-char branch
        # above, and the table covers everything from 32 upward, so bisect
        # never actually returns -1 here. Keep the fallback in case the
        # bundled table is replaced with one that starts at a higher cp.
        return _em_width()
    lo, hi, width = table[idx]
    if lo <= code_point <= hi:
        return width
    return _em_width()


def text_length(text) -> float:
    """Pixel width of `text` rendered in 11px Verdana.

    Uses the same per-glyph width table shields.io uses, so badges look
    consistent with the rest of the ecosystem and don't mis-size on narrow
    (`iIl1`) or wide (`WMm`) characters the way a flat `7.5 * len(text)`
    estimate would.
    """
    if not text:
        return 0.0
    return sum(_width_of_codepoint(ord(ch)) for ch in str(text))


def _fmt(value: float) -> str:
    """Trim numeric attributes to 3 decimal places, dropping trailing zeros.

    `48.290` → `48.29`, `100.0` → `100`. Sub-pixel precision beyond 3
    decimals is invisible at 20px badge height; clipping it shaves a few
    bytes off every SVG without changing the rendered output.
    """
    return f"{value:.3f}".rstrip("0").rstrip(".")


def render(fobj: typing.TextIO, left_txt: str, right_txt: str, color: str):
    left_txt = str(left_txt)
    right_txt = str(right_txt)
    label_color = COLORS.get(color, color)
    title = f"{left_txt}: {right_txt}"
    left_text_w = text_length(left_txt)
    right_text_w = text_length(right_txt)
    left_width = left_text_w + _HORIZONTAL_PADDING
    right_width = right_text_w + _HORIZONTAL_PADDING
    badge_height = 20
    total_width = _fmt(left_width + right_width)
    left_width_s = _fmt(left_width)
    right_width_s = _fmt(right_width)
    left_text_len_s = _fmt(left_text_w * 10)
    right_text_len_s = _fmt(right_text_w * 10)
    left_text_x = _fmt(left_width * 5)
    right_text_x = _fmt(right_width * 5)
    text_y = _fmt(badge_height * 5)
    # Shields.io's glyph-positioning trick: render text inside
    # `<g transform="scale(.1)">` at 10× coordinates with an explicit
    # `textLength`. The 10× space lets us express sub-pixel glyph
    # positions as plain integers, and `textLength` forces the renderer
    # to fit the string to our anafanafo-measured width instead of
    # letting it pick its own letter spacing — so badges look identical
    # across browsers, librsvg, resvg, etc. Font size and shadow offset
    # are scaled up the same factor so the visible result is unchanged.
    fobj.write(
        textwrap.dedent(f"""
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    xmlns:xlink="http://www.w3.org/1999/xlink"
                    width="{total_width}"
                    height="{badge_height}"
                    role="img"
                    aria-label="{xml_escape(title)}"
                >
                    <style>
                        rect {{
                            height: {badge_height}px;
                        }}

                        text {{
                            text-rendering: geometricPrecision;
                            dominant-baseline: middle;
                            text-anchor: middle;
                            font-family: Verdana,Geneva,DejaVu Sans,sans-serif;
                            font-size: 110px;
                            fill: #fff;
                        }}

                        .shadow {{
                            transform: translate(10px, 10px);
                            fill: #010101;
                        }}
                    </style>
                    <title>{xml_escape(title)}</title>
                    <linearGradient id="s" x2="0" y2="100%">
                        <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
                        <stop offset="1" stop-opacity=".1"/>
                    </linearGradient>
                    <clipPath id="r">
                        <rect width="100%" rx="3" fill="#fff"/>
                    </clipPath>
                    <g clip-path="url(#r)" >
                        <g>
                            <rect width="{left_width_s}" fill="#555"/>
                            <g transform="scale(.1)">
                                <text x="{left_text_x}" y="{text_y}" textLength="{left_text_len_s}" class="shadow">{xml_escape(left_txt)}</text>
                                <text x="{left_text_x}" y="{text_y}" textLength="{left_text_len_s}">{xml_escape(left_txt)}</text>
                            </g>
                        </g>
                        <g transform="translate({left_width_s} 0)">
                            <rect width="{right_width_s}" fill="{label_color}"/>
                            <g transform="scale(.1)">
                                <text x="{right_text_x}" y="{text_y}" textLength="{right_text_len_s}" class="shadow">{xml_escape(right_txt)}</text>
                                <text x="{right_text_x}" y="{text_y}" textLength="{right_text_len_s}">{xml_escape(right_txt)}</text>
                            </g>
                        </g>
                        <rect width="100%" height="100%" fill="url(#s)"/>
                    </g>
                </svg>
            """)
    )
