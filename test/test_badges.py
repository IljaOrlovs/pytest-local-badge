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
        cli_options.__dict__
        assert badge_obj.full_output_file_name == (badge_output_dir / "UNKNOWN.svg")

    def test_get_colour(self, badge_obj):
        for pct, exp_out in [
            (None, "lightgrey"),
            (False, "lightgrey"),
            (True, "brightgreen"),
            (1, "brightgreen"),
            (0.9, "green"),
            (0.78, "yellowgreen"),
            (0.6, "yellow"),
            (0.4, "orange"),
            (0.1, "red"),
            (-1, "red"),
        ]:
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
        mock_badge_render.assert_called_once_with(
            mocker.ANY, color=mocker.ANY, left_txt=mocker.ANY, right_txt="0%"
        )

    def test_100_cov_total(self, mocker, mock_badge_render, badge_obj, mock_session):
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY, color=mocker.ANY, left_txt=mocker.ANY, right_txt="100%"
        )
