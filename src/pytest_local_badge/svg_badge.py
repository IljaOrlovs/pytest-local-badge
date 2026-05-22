import bisect
import importlib.resources
import json
import textwrap
from functools import cache
from xml.sax.saxutils import escape as xml_escape

COLORS = {
    "brightgreen": "#4c1",
    "green": "#97ca00",
    "yellowgreen": "#a4a61d",
    "yellow": "#dfb317",
    "orange": "#fe7d37",
    "red": "#e05d44",
    "lightgrey": "#9f9f9f",
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
    if idx < 0:
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


def render(fobj, left_txt, right_txt, color):
    left_txt = str(left_txt)
    right_txt = str(right_txt)
    label_color = COLORS.get(color, color)
    title = f"{left_txt}: {right_txt}"
    left_width = text_length(left_txt)
    right_width = text_length(right_txt) + 10
    badge_height = 20
    fobj.write(
        textwrap.dedent(f"""
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    xmlns:xlink="http://www.w3.org/1999/xlink"
                    width="{left_width + right_width}"
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
                            font-size: 11.4px;
                            fill: #fff;
                        }}

                        .shadow {{
                            transform: translate(1px, 1px);
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
                            <rect width="{left_width}" fill="#555"/>
                            <text x="{left_width / 2}" y="{badge_height / 2}" class="shadow">{xml_escape(left_txt)}</text>
                            <text x="{left_width / 2}" y="{badge_height / 2}">{xml_escape(left_txt)}</text>
                        </g>
                        <g transform="translate({left_width} 0)">
                            <rect width="{right_width}" fill="{label_color}"/>
                            <text x="{right_width / 2}" y="{badge_height / 2}" class="shadow">{xml_escape(right_txt)}</text>
                            <text x="{right_width / 2}" y="{badge_height / 2}">{xml_escape(right_txt)}</text>
                        </g>
                        <rect width="100%" height="100%" fill="url(#s)"/>
                    </g>
                </svg>
            """)
    )
