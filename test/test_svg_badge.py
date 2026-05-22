import pytest

import pytest_local_badge.svg_badge as svg_badge


@pytest.mark.parametrize(
    "inp, exp_out",
    [
        ("", 0),
        (None, 0),
        # Digits are tabular in Verdana — each glyph = 6.99 px.
        ("123", pytest.approx(6.99 * 3)),
        # Narrow vs wide glyphs measure differently (the whole point of the
        # per-character table). 'i' is narrower than 'W'.
        ("iii", pytest.approx(3.02 * 3)),
        ("WWW", pytest.approx(10.88 * 3)),
    ],
)
def test_text_length(inp, exp_out):
    assert svg_badge.text_length(inp) == exp_out


def test_narrow_chars_render_narrower_than_wide():
    # Regression: previously `7.5 * len(text)` made all 3-char strings the
    # same width, leading to comically misaligned badges.
    assert svg_badge.text_length("iii") < svg_badge.text_length("WWW")


def test_unknown_codepoint_falls_back_to_em_width():
    # A high private-use code point that the table doesn't cover should
    # still produce a non-zero width (em-width fallback), not raise or
    # return zero.
    assert svg_badge.text_length("\U00100000") > 0


@pytest.mark.parametrize("control_char", ["\t", "\n", "\x00", "\x7f"])
def test_control_chars_have_zero_width(control_char):
    # Tabs / newlines / NUL / DEL — they don't render, so they shouldn't
    # contribute to the badge's pixel width.
    assert svg_badge.text_length(control_char) == 0.0


def test_both_halves_get_horizontal_padding(mocker):
    """Regression: shields.io adds ~10px of horizontal padding to *both*
    halves of a badge (5px on each side of the text). We used to pad only
    the right half, so badges looked visibly tighter than their hosted
    siblings around the label text. Locking the symmetry in here.
    """
    import re

    fobj = mocker.MagicMock(name="mock-fobj")
    svg_badge.render(fobj, "abc", "xyz", "brightgreen")
    written = fobj.write.call_args.args[0]
    # The two `<rect width="...">` declarations are left-half then right-half.
    rect_widths = [
        float(m) for m in re.findall(r'<rect width="([0-9.]+)"', written)
    ]
    text_abc = svg_badge.text_length("abc")
    text_xyz = svg_badge.text_length("xyz")
    # The clip-path and gradient-overlay rects use `width="100%"` and are
    # excluded by the numeric regex — so we get exactly the two coloured
    # halves, in document order: left then right.
    assert len(rect_widths) == 2
    left_rect, right_rect = rect_widths
    assert left_rect == pytest.approx(text_abc + 10)
    assert right_rect == pytest.approx(text_xyz + 10)


@pytest.mark.parametrize("left_text", [None, "", "hello world"])
@pytest.mark.parametrize("right_text", [None, "", "hello world"])
@pytest.mark.parametrize("colour", [None, "", "#fff", "lightgreenm"])
def test_render_no_exceptions(mocker, left_text, right_text, colour):
    fobj = mocker.MagicMock(name="mock-fobj")
    svg_badge.render(fobj, left_text, right_text, colour)
    fobj.write.assert_called_once()
