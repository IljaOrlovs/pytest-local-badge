import argparse
import pathlib

import pytest

import pytest_local_badge.plugin as plugin


class TestLocalBadgePlugin:
    @pytest.fixture
    def badge_dir(self, testdir):
        return pathlib.Path(testdir.mkdir("badges"))

    @pytest.fixture
    def mock_cli_options(self, badge_dir):
        return argparse.Namespace(
            local_badge_output_dir=str(badge_dir),
            local_badge_generate=["test-badge-1", "test-badge-2"],
        )

    def test_no_badge_dir(self, mocker, mock_cli_options):
        mock_cli_options.local_badge_output_dir = "idontexist"
        obj = plugin.LocalBadgePlugin(mock_cli_options)
        with pytest.warns(UserWarning, match="does not exist or is not a directory"):
            obj.pytest_sessionfinish(mocker.MagicMock(), 0)

    def test_badge_calls(self, mocker, badge_dir, mock_cli_options):
        mock_session = mocker.MagicMock(name="mock-session")
        exitstatus = 42
        mock_badges = {
            name: mocker.MagicMock(name=f"{name}-mock")
            for name in ["test-badge-1", "test-badge-2", "test-badge-42"]
        }
        mocker.patch.object(plugin, "BADGES", mock_badges)
        obj = plugin.LocalBadgePlugin(mock_cli_options)
        obj.pytest_sessionfinish(mock_session, exitstatus)
        for name, badge_cls_mock in mock_badges.items():
            if name in mock_cli_options.local_badge_generate:
                badge_cls_mock.assert_called_once_with(badge_dir, mock_cli_options)
                badge_obj = badge_cls_mock.return_value
                badge_obj.on_sessionfinish.assert_called_once_with(
                    mock_session, exitstatus
                )
            else:
                assert not badge_cls_mock.called


class TestLoadInitialConftests:
    """Direct unit tests for the `pytest_load_initial_conftests` hook.

    The pytester-driven tests in test_simple.py / test_cli_params.py cover
    the integrated path; these cover the branching directly so coverage
    measurement (which can't see into pytester subprocesses) catches it.
    """

    @pytest.fixture
    def early_config(self, mocker, tmp_path):
        cfg = mocker.MagicMock(name="early_config")
        cfg.known_args_namespace = argparse.Namespace(
            pytest_local_badge_enabled=True,
            local_badge_output_dir=str(tmp_path),
        )
        return cfg

    def test_registers_plugin_when_enabled_and_dir_set(self, early_config):
        plugin.pytest_load_initial_conftests(early_config, parser=None, args=[])
        early_config.pluginmanager.register.assert_called_once()
        registered, name = early_config.pluginmanager.register.call_args.args
        assert name == "_local_badge"
        assert isinstance(registered, plugin.LocalBadgePlugin)

    def test_no_register_when_disabled(self, early_config):
        # `--no-local-badge` clears the enabled flag — even with output_dir set,
        # the plugin must not register.
        early_config.known_args_namespace.pytest_local_badge_enabled = False
        plugin.pytest_load_initial_conftests(early_config, parser=None, args=[])
        early_config.pluginmanager.register.assert_not_called()

    def test_no_register_when_output_dir_missing(self, early_config):
        # The default — user never passed `--local-badge-output-dir`. The
        # plugin should stay dormant rather than write badges to nowhere.
        early_config.known_args_namespace.local_badge_output_dir = None
        plugin.pytest_load_initial_conftests(early_config, parser=None, args=[])
        early_config.pluginmanager.register.assert_not_called()
