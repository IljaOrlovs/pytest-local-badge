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


@pytest.mark.parametrize("left_text", [None, "", "hello world"])
@pytest.mark.parametrize("right_text", [None, "", "hello world"])
@pytest.mark.parametrize("colour", [None, "", "#fff", "lightgreenm"])
def test_render_no_exceptions(mocker, left_text, right_text, colour):
    fobj = mocker.MagicMock(name="mock-fobj")
    svg_badge.render(fobj, left_text, right_text, colour)
    fobj.write.assert_called_once()
