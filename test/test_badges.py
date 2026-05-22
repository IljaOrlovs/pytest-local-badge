import argparse
import pathlib

import pytest

import pytest_local_badge.badges as badges


@pytest.fixture(autouse=True)
def mock_badge_render(mocker):
    return mocker.patch("pytest_local_badge.svg_badge.render")


@pytest.fixture
def cli_options():
    return argparse.Namespace()


@pytest.fixture
def badge_output_dir(tmpdir):
    return pathlib.Path(tmpdir.mkdir("badges"))


@pytest.fixture
def mock_session(mocker):
    session = mocker.MagicMock(name="mock-pytest-session")
    session.config.pluginmanager.hasplugin.return_value = False
    return session


class TestBadgeBase:
    @pytest.fixture
    def badge_obj(self, badge_output_dir, cli_options):
        return badges.BadgeBase(badge_output_dir, cli_options)

    def test_on_sessionfinish(self, badge_obj, mock_session):
        with pytest.raises(NotImplementedError):
            badge_obj.on_sessionfinish(mock_session, 0)

    @pytest.mark.parametrize("cli_override", [None, "test_out.svg"])
    def test_out_fname(self, badge_obj, badge_output_dir, cli_override):
        assert badge_obj.full_output_file_name == (badge_output_dir / "UNKNOWN.svg")

    @pytest.mark.parametrize(
        "pct, exp_out",
        [
            (None, "lightgrey"),  # "no data" sentinel
            (1, "brightgreen"),
            (0.99, "brightgreen"),
            (0.9, "green"),
            (0.87, "green"),
            (0.78, "yellowgreen"),
            (0.75, "yellowgreen"),
            (0.6, "yellow"),
            (0.5, "yellow"),
            (0.4, "orange"),
            (0.3, "orange"),
            (0.1, "red"),
            # Regression: `0 in (None, False)` was True, so 0% silently
            # rendered grey instead of red. Both int and float forms.
            (0, "red"),
            (0.0, "red"),
            (-1, "red"),
        ],
    )
    def test_get_colour(self, badge_obj, pct, exp_out):
        assert badge_obj.get_colour(pct) == exp_out


class TestSuccessBadge:
    @pytest.fixture
    def badge_obj(self, badge_output_dir, cli_options):
        return badges.TestSuccess(badge_output_dir, cli_options)

    @pytest.mark.parametrize("rc", [0, 1, 42])
    @pytest.mark.parametrize("testscollected", [0, 1, 10])
    @pytest.mark.parametrize("testsfailed", [0, 1, 10])
    def test_badge_gen(
        self,
        mocker,
        mock_badge_render,
        badge_obj,
        mock_session,
        rc,
        testscollected,
        testsfailed,
    ):
        mock_session.testscollected = testscollected
        mock_session.testsfailed = testsfailed
        test_succeeded = max(testscollected - testsfailed, 0)
        if testscollected == 0:
            exp_right_txt = "0"
        elif testscollected == test_succeeded:
            exp_right_txt = str(testscollected)
        else:
            exp_right_txt = f"{test_succeeded}/{testscollected}"

        badge_obj.on_sessionfinish(mock_session, rc)
        mock_badge_render.assert_called_once_with(
            mocker.ANY,
            left_txt="tests",
            right_txt=exp_right_txt,
            color=mocker.ANY,
        )

    @pytest.mark.parametrize(
        "rc, testscollected, testsfailed, exp_color",
        [
            # No tests collected → "no data" → grey, regardless of rc.
            (0, 0, 0, "lightgrey"),
            (1, 0, 0, "lightgrey"),
            # All tests pass cleanly → brightgreen.
            (0, 10, 0, "brightgreen"),
            (0, 1, 0, "brightgreen"),
            # All tests fail → red (regression test for the `0 == False` bug).
            (1, 10, 10, "red"),
            # Partial failures → coloured by pass ratio.
            (1, 10, 1, "green"),  # 9/10 = 0.9
            (1, 10, 2, "yellowgreen"),  # 8/10 = 0.8
            (1, 4, 3, "red"),  # 1/4 = 0.25
            # Passing tests but non-zero rc (e.g. plugin error) → red.
            (1, 5, 0, "red"),
        ],
    )
    def test_badge_colour(
        self,
        mock_badge_render,
        badge_obj,
        mock_session,
        rc,
        testscollected,
        testsfailed,
        exp_color,
    ):
        mock_session.testscollected = testscollected
        mock_session.testsfailed = testsfailed
        badge_obj.on_sessionfinish(mock_session, rc)
        actual_color = mock_badge_render.call_args.kwargs["color"]
        assert actual_color == exp_color


class TestPytestCov:
    @pytest.fixture
    def badge_obj(self, badge_output_dir, cli_options):
        return badges.PytestCov(badge_output_dir, cli_options)

    @pytest.fixture
    def mock_plugin(self, mocker):
        out = mocker.MagicMock(name="mock-cov-plugin")
        out.cov_total = 100
        return out

    @pytest.fixture
    def mock_session(self, mock_session, mock_plugin):
        mock_session.config.pluginmanager.hasplugin.side_effect = lambda name: (
            name == "_cov"
        )
        mock_session.config.pluginmanager.getplugin.return_value = mock_plugin
        return mock_session

    @pytest.mark.parametrize("has_plugin", [True, False])
    @pytest.mark.parametrize("get_plugin", [True, False])
    def test_defensive_code(
        self, mock_badge_render, badge_obj, mock_session, has_plugin, get_plugin
    ):
        mock_session.config.pluginmanager.hasplugin.side_effect = lambda _: has_plugin
        if not get_plugin:
            mock_session.config.pluginmanager.getplugin.return_value = None

        badge_obj.on_sessionfinish(mock_session, 0)
        assert mock_badge_render.called == (has_plugin and get_plugin)

    def test_none_cov_total(
        self, mocker, mock_badge_render, badge_obj, mock_session, mock_plugin
    ):
        mock_plugin.cov_total = None

        badge_obj.on_sessionfinish(mock_session, 0)
        # `None` cov_total means pytest-cov produced no report — render grey,
        # not red. (Regression: previously conflated with 0% via `0 == False`.)
        mock_badge_render.assert_called_once_with(
            mocker.ANY, color="lightgrey", left_txt=mocker.ANY, right_txt="0%"
        )

    def test_100_cov_total(self, mocker, mock_badge_render, badge_obj, mock_session):
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY, color="brightgreen", left_txt=mocker.ANY, right_txt="100%"
        )

    @pytest.mark.parametrize(
        "cov_total, exp_right_txt, exp_color",
        [
            (None, "0%", "lightgrey"),
            (0, "0%", "red"),
            (10, "10%", "red"),
            (35, "35%", "orange"),
            (60, "60%", "yellow"),
            (80, "80%", "yellowgreen"),
            (90, "90%", "green"),
            (100, "100%", "brightgreen"),
        ],
    )
    def test_cov_total_colour(
        self,
        mocker,
        mock_badge_render,
        badge_obj,
        mock_session,
        mock_plugin,
        cov_total,
        exp_right_txt,
        exp_color,
    ):
        mock_plugin.cov_total = cov_total
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY, color=exp_color, left_txt="coverage", right_txt=exp_right_txt
        )
