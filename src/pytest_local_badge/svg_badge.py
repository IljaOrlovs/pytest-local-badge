import textwrap

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


def text_length(text):
    return 7.5 * len(text or "")


def render(fobj, left_txt, right_txt, color):
    # noqa: E501
    left_txt = str(left_txt)
    right_txt = str(right_txt)
    label_color = COLORS.get(color, color)
    title = f"{left_txt}: {right_txt}"
    left_width = text_length(left_txt)
    right_width = text_length(right_txt) + 10
    badge_height = 20
    fobj.write(textwrap.dedent(f"""
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    xmlns:xlink="http://www.w3.org/1999/xlink"
                    width="{left_width + right_width}"
                    height="{ badge_height }"
                    role="img"
                    aria-label="{xml_escape(title)}"
                >
                    <style>
                        rect {{
                            height: { badge_height }px;
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
            """))
