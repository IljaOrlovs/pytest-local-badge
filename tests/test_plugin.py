import argparse
import json
import pathlib

import pytest

import pytest_local_badge.badges as badges
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

    def test_package_badge_filtering(self, mocker, badge_dir, mock_cli_options):
        # Covers the `if badge_name not in enabled: continue` branch for
        # package badges: pass a `--local-badge-package` but a generate
        # list that only mentions one of two package badges. The omitted
        # one must not be instantiated.
        mock_cli_options.local_badge_generate = ["pkg-yes"]
        mock_cli_options.local_badge_package = ["some-dist"]
        mock_pkg_badges = {
            "pkg-yes": mocker.MagicMock(name="pkg-yes-mock"),
            "pkg-no": mocker.MagicMock(name="pkg-no-mock"),
        }
        mocker.patch.object(plugin, "BADGES", {})
        mocker.patch.object(plugin, "PACKAGE_BADGES", mock_pkg_badges)
        obj = plugin.LocalBadgePlugin(mock_cli_options)
        obj.pytest_sessionfinish(mocker.MagicMock(name="session"), 0)
        mock_pkg_badges["pkg-yes"].assert_called_once_with(
            badge_dir, mock_cli_options, "some-dist"
        )
        mock_pkg_badges["pkg-no"].assert_not_called()


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


class TestGatherCustomSpecs:
    """`_gather_custom_specs` merges env vars → files → CLI flags."""

    @pytest.fixture
    def options(self):
        # The defaults the option parser would produce when nothing is
        # set, so each test can override only the fields it cares about.
        return argparse.Namespace(
            local_badge_custom=[],
            local_badge_custom_file=[],
            local_badge_custom_strict=False,
        )

    def test_empty_sources_returns_empty_list(self, options):
        assert plugin._gather_custom_specs(options, environ={}) == []

    def test_env_var_parsed(self, options):
        specs = plugin._gather_custom_specs(
            options, environ={"PYTEST_LOCAL_BADGE_CUSTOM_COMMIT": "abc1234"}
        )
        assert specs == [
            badges.CustomSpec(label="commit", message="abc1234", colour="blue")
        ]

    def test_env_var_underscore_becomes_dash(self, options):
        # `PYTEST_LOCAL_BADGE_CUSTOM_BUILD_SHA` → label `build-sha`,
        # slug `build-sha`. Mirrors what users naturally type in shells.
        specs = plugin._gather_custom_specs(
            options, environ={"PYTEST_LOCAL_BADGE_CUSTOM_BUILD_SHA": "abc:red"}
        )
        assert specs[0].label == "build-sha"
        assert specs[0].derived_slug == "build-sha"
        assert specs[0].colour == "red"

    def test_env_var_empty_label_suffix_skipped(self, options):
        # `PYTEST_LOCAL_BADGE_CUSTOM_` with no suffix at all is ignored
        # — handy if a CI templating system accidentally emits the bare
        # prefix.
        specs = plugin._gather_custom_specs(
            options, environ={"PYTEST_LOCAL_BADGE_CUSTOM_": "ignored"}
        )
        assert specs == []

    def test_non_matching_env_vars_ignored(self, options):
        # Sanity check: only the prefix-matched vars are read; PATH
        # and friends don't accidentally become badges.
        specs = plugin._gather_custom_specs(
            options,
            environ={
                "PATH": "/usr/bin",
                "HOME": "/home/user",
                "PYTEST_LOCAL_BADGE_CUSTOM_HIT": "yes",
            },
        )
        assert [s.label for s in specs] == ["hit"]

    def test_cli_overrides_file_overrides_env(self, tmp_path, options):
        # All three sources name the same slug; CLI must win, file
        # second, env last. We verify by inspecting the surviving
        # message.
        file_path = tmp_path / "badges.json"
        file_path.write_text(json.dumps([{"label": "commit", "message": "from-file"}]))
        options.local_badge_custom_file = [str(file_path)]
        options.local_badge_custom = ["commit=from-cli"]
        specs = plugin._gather_custom_specs(
            options, environ={"PYTEST_LOCAL_BADGE_CUSTOM_COMMIT": "from-env"}
        )
        assert len(specs) == 1
        assert specs[0].message == "from-cli"

    def test_file_overrides_env_when_no_cli(self, tmp_path, options):
        file_path = tmp_path / "badges.json"
        file_path.write_text(json.dumps([{"label": "commit", "message": "from-file"}]))
        options.local_badge_custom_file = [str(file_path)]
        specs = plugin._gather_custom_specs(
            options, environ={"PYTEST_LOCAL_BADGE_CUSTOM_COMMIT": "from-env"}
        )
        assert specs[0].message == "from-file"

    def test_reserved_slug_collision_raises(self, options):
        # "tests" is one of the built-in session badges; clobbering it
        # with a custom badge would be a footgun. Hard error.
        options.local_badge_custom = ["tests=42"]
        with pytest.raises(
            plugin.PytestLocalBadgeError, match="collides with a built-in"
        ):
            plugin._gather_custom_specs(options, environ={})

    def test_empty_slug_raises(self, options):
        # A label of "!!!" canonicalises to "" — would write to `.svg`,
        # which is nonsense. Error rather than guess.
        options.local_badge_custom = ["!!!=x"]
        with pytest.raises(plugin.PytestLocalBadgeError, match="empty slug"):
            plugin._gather_custom_specs(options, environ={})

    def test_empty_message_skipped_by_default(self, options):
        # Models `--local-badge-custom "commit=$(git rev-parse ... )"`
        # in a tarball checkout, where the subshell returns empty.
        # Without strict mode the badge silently drops, so the rest of
        # the run is unaffected.
        options.local_badge_custom = ["commit="]
        assert plugin._gather_custom_specs(options, environ={}) == []

    def test_empty_message_strict_mode_raises(self, options):
        options.local_badge_custom = ["commit="]
        options.local_badge_custom_strict = True
        with pytest.raises(
            plugin.PytestLocalBadgeError,
            match="strict.*empty MESSAGE.*commit",
        ):
            plugin._gather_custom_specs(options, environ={})

    def test_sessionfinish_renders_custom_badges(self, mocker, tmp_path):
        # End-to-end: a CLI-supplied custom badge survives the
        # `pytest_sessionfinish` path and writes its SVG. Patching the
        # built-in registries to empty isolates this to the custom path.
        mocker.patch.object(plugin, "BADGES", {})
        mocker.patch.object(plugin, "PACKAGE_BADGES", {})
        options = argparse.Namespace(
            local_badge_output_dir=str(tmp_path),
            local_badge_generate=[],
            local_badge_custom=["commit=abc1234:red"],
            local_badge_custom_file=[],
            local_badge_custom_strict=False,
            local_badge_package=[],
        )
        plug = plugin.LocalBadgePlugin(options)
        plug.pytest_sessionfinish(mocker.MagicMock(), 0)
        assert (tmp_path / "commit.svg").is_file()
        svg = (tmp_path / "commit.svg").read_text()
        # Red palette colour, plus our label and message text.
        assert "#e05d44" in svg
        assert "commit" in svg
        assert "abc1234" in svg
