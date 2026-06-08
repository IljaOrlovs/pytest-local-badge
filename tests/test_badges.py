import argparse
import json
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


# ------------------------------------------------------------------------
# Tier-1 badges (skipped / xfailed / warnings / duration). They share a
# `terminalreporter` plugin lookup, so a common fixture builder helps.
# ------------------------------------------------------------------------


def _stub_terminalreporter(
    mocker,
    session,
    stats=None,
    legacy_starttime=None,
    modern_elapsed_seconds=None,
):
    """Wire a fake `terminalreporter` plugin onto `session`.

    Pytest exposes session start time differently across versions, so the
    stub can be told to populate either:
      - `_sessionstarttime` (legacy, pre-8.x): a `float` from `time.time()`.
      - `_session_start.elapsed().seconds` (modern): a `timing.Instant`.
    By default both attributes are absent, which models a reporter that
    doesn't expose timing at all (`Duration` should bail silently).
    """
    reporter = mocker.MagicMock(name="mock-terminalreporter")
    reporter.stats = stats or {}
    # MagicMock auto-creates any attribute access, which would defeat the
    # defensive `getattr(..., None)` checks. Force them missing by default.
    del reporter._sessionstarttime
    del reporter._session_start
    if legacy_starttime is not None:
        reporter._sessionstarttime = legacy_starttime
    if modern_elapsed_seconds is not None:
        instant = mocker.MagicMock(name="mock-timing-instant")
        instant.elapsed.return_value.seconds = modern_elapsed_seconds
        reporter._session_start = instant
    session.config.pluginmanager.getplugin.side_effect = lambda name: (
        reporter if name == "terminalreporter" else None
    )
    return reporter


class TestSkipped:
    @pytest.fixture
    def badge_obj(self, badge_output_dir, cli_options):
        return badges.Skipped(badge_output_dir, cli_options)

    def test_no_terminalreporter_is_silent(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        # `-p no:terminalreporter` runs — the badge should skip rendering
        # rather than crash.
        mock_session.config.pluginmanager.getplugin.return_value = None
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_not_called()

    @pytest.mark.parametrize(
        "total, skipped, exp_right, exp_color",
        [
            # No tests collected — "no data" → grey.
            (0, 0, "0", "lightgrey"),
            # No skips → brightgreen.
            (10, 0, "0", "brightgreen"),
            # Half the suite skipped → yellow (ratio 0.5).
            (10, 5, "5", "yellow"),
            # Everything skipped → red (ratio 0).
            (5, 5, "5", "red"),
        ],
    )
    def test_renders(
        self,
        mocker,
        mock_badge_render,
        badge_obj,
        mock_session,
        total,
        skipped,
        exp_right,
        exp_color,
    ):
        mock_session.testscollected = total
        _stub_terminalreporter(
            mocker, mock_session, stats={"skipped": [object()] * skipped}
        )
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY, left_txt="skipped", right_txt=exp_right, color=exp_color
        )


class TestXFailed:
    @pytest.fixture
    def badge_obj(self, badge_output_dir, cli_options):
        return badges.XFailed(badge_output_dir, cli_options)

    def test_no_terminalreporter_is_silent(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        mock_session.config.pluginmanager.getplugin.return_value = None
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_not_called()

    @pytest.mark.parametrize(
        "total, xfailed, exp_right, exp_color",
        [
            (0, 0, "0", "lightgrey"),
            (10, 0, "0", "brightgreen"),
            (10, 5, "5", "yellow"),
            (3, 3, "3", "red"),
        ],
    )
    def test_renders(
        self,
        mocker,
        mock_badge_render,
        badge_obj,
        mock_session,
        total,
        xfailed,
        exp_right,
        exp_color,
    ):
        mock_session.testscollected = total
        _stub_terminalreporter(
            mocker, mock_session, stats={"xfailed": [object()] * xfailed}
        )
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY, left_txt="xfailed", right_txt=exp_right, color=exp_color
        )


class TestWarnings:
    @pytest.fixture
    def badge_obj(self, badge_output_dir, cli_options):
        return badges.Warnings(badge_output_dir, cli_options)

    def test_no_terminalreporter_is_silent(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        mock_session.config.pluginmanager.getplugin.return_value = None
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_not_called()

    @pytest.mark.parametrize(
        "count, exp_color",
        [
            (0, "brightgreen"),  # threshold edge: 0
            (1, "green"),  # transitions into green at 1
            (5, "green"),  # threshold edge: 5
            (6, "yellow"),  # transitions into yellow at 6
            (20, "yellow"),  # threshold edge: 20
            (21, "orange"),
            (50, "orange"),  # threshold edge: 50
            (51, "red"),
            (9999, "red"),
        ],
    )
    def test_colour_thresholds(
        self,
        mocker,
        mock_badge_render,
        badge_obj,
        mock_session,
        count,
        exp_color,
    ):
        _stub_terminalreporter(
            mocker, mock_session, stats={"warnings": [object()] * count}
        )
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY, left_txt="warnings", right_txt=str(count), color=exp_color
        )


class TestLastRun:
    @pytest.fixture
    def badge_obj(self, badge_output_dir, cli_options):
        return badges.LastRun(badge_output_dir, cli_options)

    def test_renders_utc_timestamp(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        # Freeze the clock so the right-hand text is deterministic.
        import datetime as _dt

        fixed = _dt.datetime(2026, 3, 14, 9, 26, tzinfo=_dt.timezone.utc)

        class _FixedDateTime(_dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed if tz is None else fixed.astimezone(tz)

        mocker.patch.object(badges.datetime, "datetime", _FixedDateTime)
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY,
            left_txt="last run",
            right_txt="2026-03-14 09:26 UTC",
            color="blue",
        )


class TestDuration:
    @pytest.fixture
    def badge_obj(self, badge_output_dir, cli_options):
        return badges.Duration(badge_output_dir, cli_options)

    def test_no_terminalreporter_is_silent(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        mock_session.config.pluginmanager.getplugin.return_value = None
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_not_called()

    def test_no_starttime_is_silent(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        # Terminalreporter present but with neither timing attribute — e.g.
        # an unusual pytest fork or a custom replacement. Render nothing.
        _stub_terminalreporter(mocker, mock_session)
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_not_called()

    def test_modern_instant_without_elapsed_method_is_silent(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        # `_session_start` exists but isn't a `timing.Instant` — defensive
        # fallback should return None rather than crash.
        _stub_terminalreporter(mocker, mock_session)
        # Inject a non-Instant object (no `elapsed` method).
        mocker.patch.object(
            mock_session.config.pluginmanager.getplugin("terminalreporter"),
            "_session_start",
            object(),
            create=True,
        )
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_not_called()

    # Two-axis parametrization: every elapsed value is rendered via both the
    # legacy `_sessionstarttime` path and the modern `_session_start.elapsed()`
    # path, proving both surfaces produce the same badge.
    @pytest.mark.parametrize("path", ["legacy", "modern"])
    @pytest.mark.parametrize(
        "elapsed, exp_right, exp_color",
        [
            (0.5, "0.5s", "brightgreen"),
            (10, "10.0s", "brightgreen"),  # edge
            (15, "15.0s", "green"),
            (30, "30.0s", "green"),  # edge
            (45, "45.0s", "yellowgreen"),
            (75, "1m 15s", "yellowgreen"),  # crosses the seconds→minutes formatter
            (120, "2m 0s", "yellowgreen"),  # edge
            (180, "3m 0s", "yellow"),
            (600, "10m 0s", "yellow"),  # edge
            (900, "15m 0s", "orange"),
            (1800, "30m 0s", "orange"),  # edge
            (5400, "1h 30m", "red"),  # crosses the minutes→hours formatter
        ],
    )
    def test_renders(
        self,
        mocker,
        mock_badge_render,
        badge_obj,
        mock_session,
        path,
        elapsed,
        exp_right,
        exp_color,
    ):
        if path == "legacy":
            starttime = 1_000_000.0
            mocker.patch(
                "pytest_local_badge.badges.time.time",
                return_value=starttime + elapsed,
            )
            _stub_terminalreporter(mocker, mock_session, legacy_starttime=starttime)
        else:
            _stub_terminalreporter(mocker, mock_session, modern_elapsed_seconds=elapsed)
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY, left_txt="duration", right_txt=exp_right, color=exp_color
        )

    @pytest.mark.parametrize(
        "elapsed, budget, exp_color",
        [
            # budget = 60s. Boundaries: brightgreen ≤6, green ≤18, yg ≤30,
            # yellow ≤48, orange ≤60, red > 60.
            (1, 60, "brightgreen"),
            (6, 60, "brightgreen"),  # edge
            (10, 60, "green"),
            (18, 60, "green"),  # edge
            (25, 60, "yellowgreen"),
            (30, 60, "yellowgreen"),  # edge
            (40, 60, "yellow"),
            (48, 60, "yellow"),  # edge
            (55, 60, "orange"),
            (60, 60, "orange"),  # exactly at budget = orange
            (61, 60, "red"),  # just over budget = red
            (120, 60, "red"),  # double budget = red
            # Same proportional model with a 10-minute budget.
            (10, 600, "brightgreen"),
            (60, 600, "brightgreen"),  # edge (10% of 600)
            (180, 600, "green"),
            (601, 600, "red"),
        ],
    )
    def test_proportional_thresholds(
        self,
        mocker,
        mock_badge_render,
        badge_obj,
        mock_session,
        cli_options,
        elapsed,
        budget,
        exp_color,
    ):
        # Inject the CLI option as it would appear after pytest parses
        # `--local-badge-duration-max=<budget>`.
        cli_options.local_badge_duration_max = budget
        _stub_terminalreporter(mocker, mock_session, modern_elapsed_seconds=elapsed)
        badge_obj.on_sessionfinish(mock_session, 0)
        actual_color = mock_badge_render.call_args.kwargs["color"]
        assert actual_color == exp_color

    @pytest.mark.parametrize("invalid_budget", [0, -1, -1000.0])
    def test_non_positive_budget_falls_back_to_absolute(
        self,
        mocker,
        mock_badge_render,
        badge_obj,
        mock_session,
        cli_options,
        invalid_budget,
    ):
        # A budget of zero would divide by zero; a negative budget is
        # nonsense. Either case should fall back to the absolute scale
        # rather than crashing.
        cli_options.local_badge_duration_max = invalid_budget
        _stub_terminalreporter(mocker, mock_session, modern_elapsed_seconds=5)
        badge_obj.on_sessionfinish(mock_session, 0)
        # 5s under absolute scale → brightgreen (≤10s).
        actual_color = mock_badge_render.call_args.kwargs["color"]
        assert actual_color == "brightgreen"

    def test_pytest_addoption_registers_max_flag(self, mocker):
        # `Duration.pytest_addoption` is supposed to wire up the
        # `--local-badge-duration-max` flag. Verify the call shape.
        group = mocker.MagicMock(name="option-group")
        badges.Duration.pytest_addoption(group, my_prefix="duration")
        group.addoption.assert_called_once()
        args, kwargs = group.addoption.call_args
        assert args == ("--local-badge-duration-max",)
        assert kwargs["type"] is float
        assert kwargs["default"] is None
        assert kwargs["metavar"] == "SECONDS"


def _stub_metadata(mocker, classifiers, extra=None):
    """Stub `importlib.metadata.metadata` to return a fake dist's metadata.

    `classifiers` becomes the `Classifier` multi-value field; `extra` is
    merged in as single-valued headers. Mirrors `email.message.Message`
    enough to satisfy the badge code under test.
    """
    md = mocker.MagicMock(name="metadata")
    md.get_all.side_effect = lambda key: classifiers if key == "Classifier" else None
    md.get.side_effect = lambda key, default=None: (extra or {}).get(key, default)
    md.__getitem__.side_effect = lambda key: (extra or {}).get(key)
    return mocker.patch(
        "pytest_local_badge.badges.importlib.metadata.metadata",
        return_value=md,
    )


class TestPackageBadgeBase:
    def test_filename_normalises_package_name(self, badge_output_dir, cli_options):
        # `Foo.Bar_baz` (legal-but-ugly distribution name) must canonicalise
        # to `foo-bar-baz` before being used as a filename component —
        # otherwise multiple installs of the same dist under different
        # case/separator spellings collide.
        class _Probe(badges.PackageBadgeBase):
            badge_name = "probe"

        obj = _Probe(badge_output_dir, cli_options, "Foo.Bar_baz")
        assert obj.full_output_file_name.name == "foo-bar-baz-probe.svg"

    def test_warns_on_missing_package(
        self, mocker, badge_output_dir, cli_options, mock_session
    ):
        # If the user asks for badges for a package that isn't installed,
        # warn and move on — don't crash the whole pytest run.
        mocker.patch(
            "pytest_local_badge.badges.importlib.metadata.metadata",
            side_effect=badges.importlib.metadata.PackageNotFoundError("nope"),
        )

        class _Probe(badges.PackageBadgeBase):
            badge_name = "probe"

            def render_from_metadata(self, md, classifiers):  # pragma: no cover
                raise AssertionError("should not be called when package missing")

        obj = _Probe(badge_output_dir, cli_options, "nope")
        with pytest.warns(UserWarning, match="is not installed"):
            obj.on_sessionfinish(mock_session, 0)


class TestPythonVersionsBadge:
    @pytest.fixture
    def badge_obj(self, badge_output_dir, cli_options):
        return badges.PythonVersions(badge_output_dir, cli_options, "demo-pkg")

    def test_extracts_versions_from_classifiers(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        # Mixed bag of `Programming Language :: Python ::` rows — the bare
        # "3", the "3 :: Only" header, and implementation tags must be
        # filtered out; only `X.Y` versions survive, in input order.
        _stub_metadata(
            mocker,
            classifiers=[
                "Programming Language :: Python :: 3",
                "Programming Language :: Python :: 3 :: Only",
                "Programming Language :: Python :: 3.10",
                "Programming Language :: Python :: 3.11",
                "Programming Language :: Python :: 3.12",
                "Programming Language :: Python :: Implementation :: CPython",
                "Topic :: Software Development",  # unrelated row
            ],
        )
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY,
            left_txt="python",
            right_txt="3.10 | 3.11 | 3.12",
            color="blue",
        )

    def test_no_render_when_no_version_classifiers(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        # A dist that doesn't advertise any specific Python version
        # produces no badge — silent skip, not an empty badge.
        _stub_metadata(mocker, classifiers=["Topic :: Software Development"])
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_not_called()


class TestLicenseBadge:
    @pytest.fixture
    def badge_obj(self, badge_output_dir, cli_options):
        return badges.License(badge_output_dir, cli_options, "demo-pkg")

    @pytest.mark.parametrize(
        "classifier, expected",
        [
            ("License :: OSI Approved :: MIT License", "MIT"),
            ("License :: OSI Approved :: Apache Software License", "Apache Software"),
            ("License :: OSI Approved :: BSD License", "BSD"),
            # No trailing " License" suffix → render as-is.
            ("License :: Public Domain", "Public Domain"),
        ],
    )
    def test_extracts_license(
        self,
        mocker,
        mock_badge_render,
        badge_obj,
        mock_session,
        classifier,
        expected,
    ):
        _stub_metadata(mocker, classifiers=[classifier])
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY,
            left_txt="License",
            right_txt=expected,
            color="yellow",
        )

    def test_no_render_without_license_classifier(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        _stub_metadata(mocker, classifiers=["Topic :: Software Development"])
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_not_called()


class TestPrivatePackageBadge:
    @pytest.fixture
    def badge_obj(self, badge_output_dir, cli_options):
        return badges.PrivatePackage(badge_output_dir, cli_options, "demo-pkg")

    def test_renders_when_marker_present(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        _stub_metadata(
            mocker,
            classifiers=[
                "Private :: Do Not Upload",
                "Programming Language :: Python :: 3.12",
            ],
        )
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY,
            left_txt="package",
            right_txt="private",
            color="red",
        )

    def test_no_render_when_marker_absent(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        # Public packages skip the badge entirely — it's only meaningful as
        # a "don't accidentally `twine upload` this" signal.
        _stub_metadata(
            mocker,
            classifiers=["License :: OSI Approved :: MIT License"],
        )
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_not_called()


class TestVersionBadge:
    @pytest.fixture
    def badge_obj(self, badge_output_dir, cli_options):
        return badges.Version(badge_output_dir, cli_options, "demo-pkg")

    def test_reads_version_field(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        _stub_metadata(mocker, classifiers=[], extra={"Version": "1.2.3"})
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY,
            left_txt="version",
            right_txt="1.2.3",
            color="blue",
        )

    def test_no_render_without_version(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        # No `Version` field → skip. Real `importlib.metadata` always
        # populates it, but defensive: don't render an empty badge.
        _stub_metadata(mocker, classifiers=[])
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_not_called()


class TestDevelopmentStatusBadge:
    @pytest.fixture
    def badge_obj(self, badge_output_dir, cli_options):
        return badges.DevelopmentStatus(badge_output_dir, cli_options, "demo-pkg")

    @pytest.mark.parametrize(
        "classifier, exp_text, exp_color",
        [
            ("Development Status :: 1 - Planning", "planning", "red"),
            ("Development Status :: 2 - Pre-Alpha", "pre-alpha", "red"),
            ("Development Status :: 3 - Alpha", "alpha", "orange"),
            ("Development Status :: 4 - Beta", "beta", "yellow"),
            (
                "Development Status :: 5 - Production/Stable",
                "production/stable",
                "brightgreen",
            ),
            ("Development Status :: 6 - Mature", "mature", "green"),
            ("Development Status :: 7 - Inactive", "inactive", "lightgrey"),
        ],
    )
    def test_grades_by_trove_digit(
        self,
        mocker,
        mock_badge_render,
        badge_obj,
        mock_session,
        classifier,
        exp_text,
        exp_color,
    ):
        _stub_metadata(mocker, classifiers=[classifier])
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY,
            left_txt="status",
            right_txt=exp_text,
            color=exp_color,
        )

    def test_no_render_without_classifier(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        _stub_metadata(mocker, classifiers=["Topic :: Software Development"])
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_not_called()

    def test_unknown_trove_digit_is_skipped(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        # A digit outside the canonical 1-7 table (e.g. a future "8" or a
        # malformed classifier) is skipped rather than crashing — the loop
        # moves on, and if nothing else matches, no badge is rendered.
        _stub_metadata(
            mocker,
            classifiers=["Development Status :: 99 - Speculative"],
        )
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_not_called()


class TestTypedBadge:
    @pytest.fixture
    def badge_obj(self, badge_output_dir, cli_options):
        return badges.Typed(badge_output_dir, cli_options, "demo-pkg")

    def test_renders_when_marker_present(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        _stub_metadata(mocker, classifiers=["Typing :: Typed"])
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY,
            left_txt="typed",
            right_txt="py.typed",
            color="blue",
        )

    def test_no_render_when_marker_absent(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        _stub_metadata(mocker, classifiers=["Typing :: Stubs Only"])
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_not_called()


class TestImplementationBadge:
    @pytest.fixture
    def badge_obj(self, badge_output_dir, cli_options):
        return badges.Implementation(badge_output_dir, cli_options, "demo-pkg")

    def test_extracts_and_dedupes_implementations(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        _stub_metadata(
            mocker,
            classifiers=[
                "Programming Language :: Python :: Implementation :: CPython",
                "Programming Language :: Python :: Implementation :: PyPy",
                # Duplicate — must collapse, not appear twice in the badge.
                "Programming Language :: Python :: Implementation :: CPython",
                "Programming Language :: Python :: 3.12",  # unrelated, ignored
            ],
        )
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY,
            left_txt="implementation",
            right_txt="CPython | PyPy",
            color="blue",
        )

    def test_no_render_without_implementation_classifier(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        _stub_metadata(
            mocker,
            classifiers=["Programming Language :: Python :: 3.12"],
        )
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_not_called()


class TestFrameworkBadge:
    @pytest.fixture
    def badge_obj(self, badge_output_dir, cli_options):
        return badges.Framework(badge_output_dir, cli_options, "demo-pkg")

    def test_keeps_top_level_and_dedupes(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        # `Framework :: Django` and `Framework :: Django :: 4.2` collapse
        # to a single `Django`. `Framework :: Pytest` adds a second entry.
        _stub_metadata(
            mocker,
            classifiers=[
                "Framework :: Django",
                "Framework :: Django :: 4.2",
                "Framework :: Pytest",
            ],
        )
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY,
            left_txt="framework",
            right_txt="Django | Pytest",
            color="blue",
        )

    def test_no_render_without_framework_classifier(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        _stub_metadata(mocker, classifiers=["Topic :: Software Development"])
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_not_called()


class TestRequiresPythonBadge:
    @pytest.fixture
    def badge_obj(self, badge_output_dir, cli_options):
        return badges.RequiresPython(badge_output_dir, cli_options, "demo-pkg")

    def test_reads_requires_python(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        _stub_metadata(
            mocker,
            classifiers=[],
            extra={"Requires-Python": ">=3.10"},
        )
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY,
            left_txt="python",
            right_txt=">=3.10",
            color="blue",
        )

    def test_no_render_when_absent(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        # Packages without a Requires-Python constraint skip the badge
        # rather than rendering an empty value.
        _stub_metadata(mocker, classifiers=[])
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_not_called()


class TestOperatingSystemBadge:
    @pytest.fixture
    def badge_obj(self, badge_output_dir, cli_options):
        return badges.OperatingSystem(badge_output_dir, cli_options, "demo-pkg")

    def test_keeps_final_segment_and_dedupes(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        _stub_metadata(
            mocker,
            classifiers=[
                "Operating System :: POSIX :: Linux",
                "Operating System :: MacOS",
                "Operating System :: Microsoft :: Windows",
                "Operating System :: POSIX :: Linux",  # dup
            ],
        )
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY,
            left_txt="OS",
            right_txt="Linux | MacOS | Windows",
            color="blue",
        )

    def test_os_independent_short_circuits(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        # A project that says "OS Independent" alongside specific OS rows
        # collapses to just "OS Independent" — the catch-all wins.
        _stub_metadata(
            mocker,
            classifiers=[
                "Operating System :: POSIX :: Linux",
                "Operating System :: OS Independent",
                "Operating System :: MacOS",
            ],
        )
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY,
            left_txt="OS",
            right_txt="OS Independent",
            color="blue",
        )

    def test_no_render_without_os_classifier(
        self, mocker, mock_badge_render, badge_obj, mock_session
    ):
        _stub_metadata(mocker, classifiers=["Topic :: Software Development"])
        badge_obj.on_sessionfinish(mock_session, 0)
        mock_badge_render.assert_not_called()


# ---------------------------------------------------------------------------
# Custom badges
# ---------------------------------------------------------------------------


class TestParseCustomValue:
    @pytest.mark.parametrize(
        "raw, exp_message, exp_colour",
        [
            ("abc123", "abc123", "blue"),
            # Trailing palette name is treated as a colour.
            ("abc123:red", "abc123", "red"),
            ("hello world:brightgreen", "hello world", "brightgreen"),
            # Hex literals (3/6/8 digits) also count as colours.
            ("v1.2.3:#ff8800", "v1.2.3", "#ff8800"),
            ("foo:#abc", "foo", "#abc"),
            ("bar:#abcdef12", "bar", "#abcdef12"),
            # Trailing `:NOT_A_COLOR` is part of the message — the
            # whole timestamp survives, colour defaults to blue.
            ("2026-06-08T14:32:00Z", "2026-06-08T14:32:00Z", "blue"),
            # URL with port and path — the trailing segment isn't a
            # palette name, so the entire URL stays the message.
            (
                "https://example.com:8080/ok",
                "https://example.com:8080/ok",
                "blue",
            ),
            # Whitespace around the value and the colour is trimmed.
            ("  padded  :  red  ", "padded", "red"),
        ],
    )
    def test_parses(self, raw, exp_message, exp_colour):
        assert badges.parse_custom_value(raw) == (exp_message, exp_colour)


class TestParseCustomCli:
    def test_label_message_only(self):
        assert badges.parse_custom_cli("commit=abc123") == badges.CustomSpec(
            label="commit", message="abc123", colour="blue"
        )

    def test_label_message_colour(self):
        assert badges.parse_custom_cli("commit=abc123:red") == badges.CustomSpec(
            label="commit", message="abc123", colour="red"
        )

    def test_message_with_equals_sign(self):
        # Only the first `=` separates label from message; later ones
        # belong to the value (e.g. base64-ish or query-string-y data).
        assert badges.parse_custom_cli("payload=k=v&x=y") == badges.CustomSpec(
            label="payload", message="k=v&x=y", colour="blue"
        )

    def test_missing_equals_errors(self):
        with pytest.raises(badges.CustomSpecError, match="must be 'LABEL=MESSAGE"):
            badges.parse_custom_cli("just-a-value")

    def test_empty_label_errors(self):
        with pytest.raises(badges.CustomSpecError, match="empty LABEL"):
            badges.parse_custom_cli("=value")


class TestCustomSpecSlug:
    @pytest.mark.parametrize(
        "label, exp_slug",
        [
            ("commit", "commit"),
            ("Build SHA", "build-sha"),
            ("My/Weird Label!", "my-weird-label"),
            # Runs of non-alphanumerics collapse to a single dash.
            ("a  b__c", "a-b-c"),
            # Leading/trailing separators are stripped.
            ("---trim---", "trim"),
        ],
    )
    def test_label_drives_slug_by_default(self, label, exp_slug):
        spec = badges.CustomSpec(label=label, message="x")
        assert spec.derived_slug == exp_slug

    def test_explicit_slug_overrides_label(self):
        spec = badges.CustomSpec(label="Build SHA", message="x", slug="sha")
        assert spec.derived_slug == "sha"

    def test_explicit_slug_is_also_canonicalised(self):
        # The file form lets users set `slug` directly, but it goes
        # through the same canonicalisation as a label-derived slug —
        # so users can't sneak `..` or capital letters into a filename.
        spec = badges.CustomSpec(label="x", message="y", slug="My Slug")
        assert spec.derived_slug == "my-slug"


class TestParseCustomFile:
    def test_json_array(self, tmp_path):
        path = tmp_path / "badges.json"
        path.write_text(
            json.dumps(
                [
                    {"label": "commit", "message": "abc1234"},
                    {
                        "label": "build SHA",
                        "message": "def5678",
                        "color": "#ff8800",
                        "slug": "sha",
                    },
                ]
            )
        )
        specs = badges.parse_custom_file(path)
        assert specs == [
            badges.CustomSpec(label="commit", message="abc1234", colour="blue"),
            badges.CustomSpec(
                label="build SHA",
                message="def5678",
                colour="#ff8800",
                slug="sha",
            ),
        ]

    def test_jsonl_with_comments_and_blank_lines(self, tmp_path):
        path = tmp_path / "badges.jsonl"
        path.write_text(
            "# comment line\n"
            "\n"
            '{"label": "commit", "message": "abc"}\n'
            "   # indented comment\n"
            '{"label": "deploy", "message": "yesterday", "color": "yellow"}\n'
        )
        specs = badges.parse_custom_file(path)
        assert [s.label for s in specs] == ["commit", "deploy"]
        assert specs[1].colour == "yellow"

    def test_top_level_dict_errors(self, tmp_path):
        # Valid JSON but wrong shape — fails immediately rather than
        # falling through to the JSONL parser, which would mis-report
        # the entire file as one bad JSONL line.
        path = tmp_path / "badges.json"
        path.write_text(json.dumps({"label": "x", "message": "y"}))
        with pytest.raises(
            badges.CustomSpecError, match="top-level JSON must be a list"
        ):
            badges.parse_custom_file(path)

    def test_jsonl_bad_line_reports_lineno(self, tmp_path):
        path = tmp_path / "badges.jsonl"
        path.write_text('{"label": "ok", "message": "x"}\nthis is not json at all\n')
        with pytest.raises(badges.CustomSpecError, match=r":2: malformed JSON"):
            badges.parse_custom_file(path)

    def test_row_missing_label(self, tmp_path):
        # Use the JSON-array form so field-level validation fires (a
        # single-line top-level object trips the "must be a list" check
        # first, which is its own test below).
        path = tmp_path / "badges.json"
        path.write_text(json.dumps([{"message": "x"}]))
        with pytest.raises(badges.CustomSpecError, match="non-empty 'label'"):
            badges.parse_custom_file(path)

    def test_row_message_not_string(self, tmp_path):
        path = tmp_path / "badges.json"
        path.write_text(json.dumps([{"label": "x", "message": 42}]))
        with pytest.raises(badges.CustomSpecError, match="string 'message'"):
            badges.parse_custom_file(path)

    def test_row_not_a_dict(self, tmp_path):
        path = tmp_path / "badges.json"
        path.write_text("[1, 2, 3]")
        with pytest.raises(badges.CustomSpecError, match="must be a JSON object"):
            badges.parse_custom_file(path)

    def test_row_color_wrong_type(self, tmp_path):
        path = tmp_path / "badges.json"
        path.write_text(json.dumps([{"label": "x", "message": "y", "color": 7}]))
        with pytest.raises(badges.CustomSpecError, match="'color' must be a string"):
            badges.parse_custom_file(path)

    def test_row_slug_wrong_type(self, tmp_path):
        path = tmp_path / "badges.json"
        path.write_text(json.dumps([{"label": "x", "message": "y", "slug": 7}]))
        with pytest.raises(badges.CustomSpecError, match="'slug' must be a string"):
            badges.parse_custom_file(path)

    def test_top_level_non_list_non_dict_errors(self, tmp_path):
        # E.g. `null` or `42` at the top level — valid JSON, wrong
        # shape. Same error path as the dict case.
        path = tmp_path / "badges.json"
        path.write_text("null")
        with pytest.raises(
            badges.CustomSpecError, match="top-level JSON must be a list"
        ):
            badges.parse_custom_file(path)


class TestCustomBadge:
    @pytest.fixture
    def spec(self):
        return badges.CustomSpec(label="commit", message="abc1234", colour="blue")

    def test_renders_to_slug_filename(
        self, mocker, mock_badge_render, badge_output_dir, cli_options, spec
    ):
        badge = badges.CustomBadge(badge_output_dir, cli_options, spec)
        assert badge.full_output_file_name == (badge_output_dir / "commit.svg")
        badge.on_sessionfinish(mocker.MagicMock(), 0)
        mock_badge_render.assert_called_once_with(
            mocker.ANY,
            left_txt="commit",
            right_txt="abc1234",
            color="blue",
        )

    def test_explicit_slug_changes_filename_only(
        self, mocker, mock_badge_render, badge_output_dir, cli_options
    ):
        spec = badges.CustomSpec(
            label="Build SHA", message="abc", colour="#ff8800", slug="sha"
        )
        badge = badges.CustomBadge(badge_output_dir, cli_options, spec)
        assert badge.full_output_file_name == (badge_output_dir / "sha.svg")
        badge.on_sessionfinish(mocker.MagicMock(), 0)
        # Label is shown as-is (case + space preserved), slug only
        # affects the file path.
        mock_badge_render.assert_called_once_with(
            mocker.ANY,
            left_txt="Build SHA",
            right_txt="abc",
            color="#ff8800",
        )
