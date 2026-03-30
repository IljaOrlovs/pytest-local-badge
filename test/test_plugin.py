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

    def test_no_badge_dir(self, mock_cli_options):
        mock_cli_options.local_badge_output_dir = "idontexist"
        with pytest.raises(plugin.PytestLocalBadgeError):
            plugin.LocalBadgePlugin(mock_cli_options)

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
