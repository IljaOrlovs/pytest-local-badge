import importlib.metadata
import pathlib
import re
import time
import warnings

import pytest

from . import svg_badge


def _normalize_package_name(name: str) -> str:
    """PEP 503 canonical name — safe for use as a filename component."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _terminal_stats(session: pytest.Session) -> dict | None:
    """Pull pytest's terminal-reporter stats dict, or `None` if unavailable.

    Used by the count-of-X badges (skipped / xfailed / warnings). The
    `terminalreporter` plugin is registered by pytest core in normal runs;
    only exotic configurations (e.g. `-p no:terminalreporter`) remove it.
    """
    reporter = session.config.pluginmanager.getplugin("terminalreporter")
    if reporter is None:
        return None
    return reporter.stats


class BadgeBase:
    """Base class for badge generators."""

    output_file_name = "UNKNOWN.svg"
    output_dir: pathlib.Path

    def __init__(self, output_dir: pathlib.Path, options):
        # `output_dir` existence is validated upstream in
        # `LocalBadgePlugin.__init__` (plugin.py) — no need to re-check here.
        self.options = options
        self.output_dir = output_dir

    @property
    def full_output_file_name(self):
        return (self.output_dir / self.output_file_name).resolve()

    @classmethod
    def pytest_addoption(cls, option_group, my_prefix: str):
        pass

    def get_colour(self, success_pct: float | None):
        # `success_pct is None` means "no data" — avoid `in (None, False)` because
        # `0 == False` would silently grey out a legitimate 0% / all-failed result.
        if success_pct is None:
            out = "lightgrey"
        elif success_pct >= 0.99:
            out = "brightgreen"
        elif success_pct >= 0.87:
            out = "green"
        elif success_pct >= 0.75:
            out = "yellowgreen"
        elif success_pct >= 0.5:
            out = "yellow"
        elif success_pct >= 0.3:
            out = "orange"
        else:
            out = "red"
        return out

    def on_sessionfinish(self, session, exitstatus):
        raise NotImplementedError(self.__class__.__name__)


class TestSuccess(BadgeBase):
    """Test success badge"""

    output_file_name = "tests.svg"

    def on_sessionfinish(self, session: pytest.Session, exitstatus: int):
        total_tests = session.testscollected
        failed_tests = session.testsfailed
        succeeded_tests = max(total_tests - failed_tests, 0)
        # `succeeded == total` covers both `failed == 0` and the degenerate
        # `total == 0, failed > 0` case (collection errors clamp succeeded to 0).
        if succeeded_tests == total_tests:
            right_text = f"{total_tests}"
        else:
            right_text = f"{succeeded_tests}/{total_tests}"
        # `None` → grey ("no data"), float ratio → coloured by pass rate.
        # A non-zero exit code with passing tests still goes red — the suite
        # failed even if individual cases didn't.
        if total_tests == 0:
            pass_ratio = None
        elif exitstatus != 0 and failed_tests == 0:
            pass_ratio = 0.0
        else:
            pass_ratio = succeeded_tests / total_tests
        with self.full_output_file_name.open("w") as fout:
            svg_badge.render(
                fout,
                left_txt="tests",
                right_txt=right_text,
                color=self.get_colour(pass_ratio),
            )


class PytestCov(BadgeBase):
    output_file_name = "coverage.svg"

    def on_sessionfinish(self, session: pytest.Session, exitstatus: int):
        if session.config.pluginmanager.hasplugin("_cov"):
            plugin = session.config.pluginmanager.getplugin("_cov")
            if plugin and plugin.cov_controller:
                # cov_total is None when pytest-cov hasn't produced a report
                # (e.g. tests errored out before collection). Treat that as
                # "no data" → grey, distinct from a real 0% → red.
                if plugin.cov_total is None:
                    coverage_ratio = None
                    right_text = "0%"
                else:
                    coverage_ratio = plugin.cov_total / 100
                    right_text = f"{int(plugin.cov_total)}%"
                with self.full_output_file_name.open("w") as fout:
                    svg_badge.render(
                        fout,
                        left_txt="coverage",
                        right_txt=right_text,
                        color=self.get_colour(coverage_ratio),
                    )


class Skipped(BadgeBase):
    """Number of `@pytest.mark.skip` / `pytest.skip()` tests in the run.

    Colour-grades by the *fraction of the suite that actually ran*: zero
    skips → brightgreen, half the suite skipped → yellow, everything
    skipped → red. A 0-test session renders grey ("no data").
    """

    output_file_name = "skipped.svg"

    def on_sessionfinish(self, session: pytest.Session, exitstatus: int):
        stats = _terminal_stats(session)
        if stats is None:
            return  # `-p no:terminalreporter` — nothing to read
        skipped = len(stats.get("skipped", []))
        total = session.testscollected
        ran_ratio = None if total == 0 else 1 - (skipped / total)
        with self.full_output_file_name.open("w") as fout:
            svg_badge.render(
                fout,
                left_txt="skipped",
                right_txt=str(skipped),
                color=self.get_colour(ran_ratio),
            )


class XFailed(BadgeBase):
    """Number of expected-failure tests (`@pytest.mark.xfail`).

    Same colour scale as `Skipped`: lots of known-broken tests is a
    legitimate signal that something is rotting.
    """

    output_file_name = "xfailed.svg"

    def on_sessionfinish(self, session: pytest.Session, exitstatus: int):
        stats = _terminal_stats(session)
        if stats is None:
            return
        xfailed = len(stats.get("xfailed", []))
        total = session.testscollected
        clean_ratio = None if total == 0 else 1 - (xfailed / total)
        with self.full_output_file_name.open("w") as fout:
            svg_badge.render(
                fout,
                left_txt="xfailed",
                right_txt=str(xfailed),
                color=self.get_colour(clean_ratio),
            )


class Warnings(BadgeBase):
    """Number of warnings raised during the test session.

    Colour grades by *absolute count* — most projects should be at zero
    and any warnings deserve attention regardless of test-suite size.
    """

    output_file_name = "warnings.svg"

    # (upper_bound_inclusive, colour). First match wins.
    _COLOUR_THRESHOLDS = (
        (0, "brightgreen"),
        (5, "green"),
        (20, "yellow"),
        (50, "orange"),
    )

    def on_sessionfinish(self, session: pytest.Session, exitstatus: int):
        stats = _terminal_stats(session)
        if stats is None:
            return
        count = len(stats.get("warnings", []))
        with self.full_output_file_name.open("w") as fout:
            svg_badge.render(
                fout,
                left_txt="warnings",
                right_txt=str(count),
                color=self._colour_for(count),
            )

    @classmethod
    def _colour_for(cls, count: int) -> str:
        for upper, colour in cls._COLOUR_THRESHOLDS:
            if count <= upper:
                return colour
        return "red"


class Duration(BadgeBase):
    """Total wall-clock time of the test session.

    Reads pytest's own session-start timestamp rather than measuring from
    the plugin, so the number matches what `pytest --durations` would say.

    Colour-grading has two modes:
      * **Absolute** (default): fixed thresholds (≤10s → brightgreen ...
        >30min → red). Sensible for "I have no opinion on what's slow."
      * **Proportional**: pass `--local-badge-duration-max=SECONDS` to set
        a budget; every colour threshold scales as a fraction of that
        budget. A 60s budget makes ≤6s brightgreen and >60s red.
    """

    output_file_name = "duration.svg"

    # (upper_bound_inclusive_seconds, colour). Used when no `-max` is set.
    _ABSOLUTE_THRESHOLDS = (
        (10, "brightgreen"),
        (30, "green"),
        (120, "yellowgreen"),
        (600, "yellow"),
        (1800, "orange"),
    )

    # (upper_bound_inclusive_fraction_of_max, colour). Used with `-max`.
    _PROPORTIONAL_THRESHOLDS = (
        (0.10, "brightgreen"),
        (0.30, "green"),
        (0.50, "yellowgreen"),
        (0.80, "yellow"),
        (1.00, "orange"),
    )

    @classmethod
    def pytest_addoption(cls, option_group, my_prefix: str):
        option_group.addoption(
            f"--local-badge-{my_prefix}-max",
            action="store",
            type=float,
            default=None,
            metavar="SECONDS",
            help=(
                "Duration budget in seconds for the `duration` badge. When "
                "set, colour thresholds scale proportionally — e.g. -max=60 "
                "→ brightgreen at ≤6s, orange at ≤60s, red beyond. When "
                "unset (default), absolute thresholds apply (≤10s → "
                "brightgreen ... >30min → red)."
            ),
        )

    def on_sessionfinish(self, session: pytest.Session, exitstatus: int):
        reporter = session.config.pluginmanager.getplugin("terminalreporter")
        if reporter is None:
            return
        elapsed = self._elapsed_seconds(reporter)
        if elapsed is None:
            return
        # `getattr` with a default so this badge still works when constructed
        # outside the plugin (unit tests, downstream code) without the option
        # being registered.
        budget = getattr(self.options, "local_badge_duration_max", None)
        with self.full_output_file_name.open("w") as fout:
            svg_badge.render(
                fout,
                left_txt="duration",
                right_txt=self._format(elapsed),
                color=self._colour_for(elapsed, budget),
            )

    @staticmethod
    def _elapsed_seconds(reporter) -> float | None:
        """Pull elapsed-session-time out of pytest's terminal reporter.

        Pytest renamed the attribute around 8.x: older versions exposed
        `_sessionstarttime` (a `float` from `time.time()`); newer ones
        expose `_session_start`, a `timing.Instant` whose `.elapsed()`
        returns a duration object with a `.seconds` attribute. Try both.
        """
        legacy = getattr(reporter, "_sessionstarttime", None)
        if legacy is not None:
            return time.time() - legacy
        modern = getattr(reporter, "_session_start", None)
        if modern is not None and hasattr(modern, "elapsed"):
            duration = modern.elapsed()
            return getattr(duration, "seconds", None)
        return None

    @staticmethod
    def _format(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.1f}s"
        if seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        return f"{int(seconds // 3600)}h {int((seconds % 3600) // 60)}m"

    @classmethod
    def _colour_for(cls, seconds: float, budget: float | None = None) -> str:
        # A positive budget enables proportional grading; otherwise fall back
        # to absolute seconds. A budget ≤ 0 is treated as "no budget" rather
        # than risking a division-by-zero.
        if budget is not None and budget > 0:
            ratio = seconds / budget
            for upper, colour in cls._PROPORTIONAL_THRESHOLDS:
                if ratio <= upper:
                    return colour
            return "red"
        for upper, colour in cls._ABSOLUTE_THRESHOLDS:
            if seconds <= upper:
                return colour
        return "red"


class PackageBadgeBase(BadgeBase):
    """Base for badges sourced from an installed distribution's metadata.

    Unlike the session badges, these don't read anything from the pytest
    run — they pull `Classifier` (and friends) from the installed
    distribution via `importlib.metadata`. One instance per
    (package, badge) pair; output filenames are prefixed with the
    package's PEP 503 canonical name so multiple packages don't collide.
    """

    badge_name = "UNKNOWN"

    def __init__(self, output_dir: pathlib.Path, options, package_name: str):
        super().__init__(output_dir, options)
        self.package_name = package_name

    @property
    def full_output_file_name(self):
        slug = _normalize_package_name(self.package_name)
        return (self.output_dir / f"{slug}-{self.badge_name}.svg").resolve()

    def on_sessionfinish(self, session, exitstatus):
        try:
            md = importlib.metadata.metadata(self.package_name)
        except importlib.metadata.PackageNotFoundError:
            warnings.warn(
                f"Package {self.package_name!r} is not installed; "
                f"skipping {self.badge_name} badge",
                stacklevel=1,
            )
            return
        classifiers = md.get_all("Classifier") or []
        self.render_from_metadata(md, classifiers)

    def render_from_metadata(self, md, classifiers: list[str]):
        raise NotImplementedError(self.__class__.__name__)


class PythonVersions(PackageBadgeBase):
    """Pipe-separated list of supported Python versions from classifiers.

    Reads `Programming Language :: Python :: X.Y` rows. The bare
    `Programming Language :: Python :: 3` / `:: 3 :: Only` headers and
    implementation tags (`:: CPython`, `:: PyPy`) are filtered out — they
    don't carry a concrete X.Y version.
    """

    badge_name = "python"
    _VERSION_RE = re.compile(
        r"""^
            \s*
            Programming \s+ Language \s+ :: \s+ Python \s+ :: \s+
            (\d+\.\d+)
            \s*
        $""",
        re.VERBOSE | re.IGNORECASE,
    )

    def render_from_metadata(self, md, classifiers):
        versions = []
        for _classifier in classifiers:
            match = self._VERSION_RE.match(_classifier)
            if match:
                versions.append(match.group(1))
        if not versions:
            return
        with self.full_output_file_name.open("w") as fout:
            svg_badge.render(
                fout,
                left_txt="python",
                right_txt=" | ".join(versions),
                color="blue",
            )


class License(PackageBadgeBase):
    """License badge from `License :: ...` classifiers.

    Captures the final trove segment and strips a trailing " License"
    suffix so "MIT License" renders as "MIT". If multiple license
    classifiers are present (rare), the first match wins.
    """

    badge_name = "license"
    _RE = re.compile(
        r"""^
            \s*
            License \s+ :: \s+
            (?: .+ \s+ :: \s+ )?      # optional intermediate trove path
            (.+?)                     # final segment
            (?: \s+ License )?        # optional " License" suffix
            \s*
        $""",
        re.VERBOSE | re.IGNORECASE,
    )

    def render_from_metadata(self, md, classifiers):
        for c in classifiers:
            match = self._RE.match(c)
            if not match:
                continue
            with self.full_output_file_name.open("w") as fout:
                svg_badge.render(
                    fout,
                    left_txt="License",
                    right_txt=match.group(1),
                    color="yellow",
                )
            return


class PrivatePackage(PackageBadgeBase):
    """Renders only when the `Private :: Do Not Upload` classifier is set.

    That classifier is the conventional way to mark a package as not
    intended for PyPI — if it's present, surface it loudly.
    """

    badge_name = "private"

    def render_from_metadata(self, md, classifiers):
        if "Private :: Do Not Upload" not in classifiers:
            return
        with self.full_output_file_name.open("w") as fout:
            svg_badge.render(
                fout,
                left_txt="package",
                right_txt="private",
                color="red",
            )


class Version(PackageBadgeBase):
    """Package version from the `Version` metadata field.

    Doesn't read classifiers — `md["Version"]` is always set on an
    installed distribution. Mirrors shields.io's `pypi/v/<pkg>` badge.
    """

    badge_name = "version"

    def render_from_metadata(self, md, classifiers):
        version = md["Version"]
        if not version:
            return
        with self.full_output_file_name.open("w") as fout:
            svg_badge.render(
                fout,
                left_txt="version",
                right_txt=str(version),
                color="blue",
            )


class DevelopmentStatus(PackageBadgeBase):
    """Project maturity from the `Development Status :: N - Name` classifier.

    Colour grades by the trove digit: planning/pre-alpha → red, alpha →
    orange, beta → yellow, stable → brightgreen, mature → green, inactive
    → grey. The right-hand text is the human-readable suffix lower-cased
    (e.g. "5 - Production/Stable" → "production/stable").
    """

    badge_name = "maturity"
    _RE = re.compile(
        r"""^
            \s*
            Development \s+ Status \s+ :: \s+
            (\d+)
            \s+ - \s+
            .+
            \s*
        $""",
        re.VERBOSE | re.IGNORECASE,
    )
    # Trove digit → (right-text, colour). Right text matches the
    # classifier's own wording rather than collapsing "Production/Stable"
    # to "stable"; the slash is fine in our 11px Verdana.
    _STATUS_TABLE = {
        "1": ("planning", "red"),
        "2": ("pre-alpha", "red"),
        "3": ("alpha", "orange"),
        "4": ("beta", "yellow"),
        "5": ("production/stable", "brightgreen"),
        "6": ("mature", "green"),
        "7": ("inactive", "lightgrey"),
    }

    def render_from_metadata(self, md, classifiers):
        for c in classifiers:
            match = self._RE.match(c)
            if not match:
                continue
            entry = self._STATUS_TABLE.get(match.group(1).lower())
            if entry is None:
                continue
            right_txt, colour = entry
            with self.full_output_file_name.open("w") as fout:
                svg_badge.render(
                    fout,
                    left_txt="status",
                    right_txt=right_txt,
                    color=colour,
                )
            return


class Typed(PackageBadgeBase):
    """Renders only when the `Typing :: Typed` classifier is set.

    Conventional marker that the package ships a `py.typed` marker file
    and is annotated end-to-end.
    """

    badge_name = "typed"

    def render_from_metadata(self, md, classifiers):
        if "Typing :: Typed" not in classifiers:
            return
        with self.full_output_file_name.open("w") as fout:
            svg_badge.render(
                fout,
                left_txt="typed",
                right_txt="py.typed",
                color="blue",
            )


class Implementation(PackageBadgeBase):
    """Pipe-separated list of supported Python implementations.

    Reads `Programming Language :: Python :: Implementation :: X`
    (CPython, PyPy, Jython, IronPython). Dedupes while preserving the
    classifier order.
    """

    badge_name = "implementation"
    _RE = re.compile(
        r"""^
            \s*
            Programming \s+ Language \s+ :: \s+ Python \s+ :: \s+
            Implementation \s+ :: \s+
            (.+?)
            \s*
        $""",
        re.VERBOSE | re.IGNORECASE,
    )

    def render_from_metadata(self, md, classifiers):
        impls = []
        for c in classifiers:
            match = self._RE.match(c)
            if not match:
                continue
            name = match.group(1)
            if name not in impls:
                impls.append(name)
        if not impls:
            return
        with self.full_output_file_name.open("w") as fout:
            svg_badge.render(
                fout,
                left_txt="implementation",
                right_txt=" | ".join(impls),
                color="blue",
            )


class Framework(PackageBadgeBase):
    """Pipe-separated list of frameworks the package targets.

    Reads `Framework :: X` (and ignores `Framework :: X :: Y` sub-version
    rows — keeps only the top-level framework name, deduplicated). A
    project tagged `Framework :: Django` and `Framework :: Django :: 4.2`
    surfaces as a single `Django`.
    """

    badge_name = "framework"
    # `[^:]+?` for the captured name keeps it inside one trove segment; the
    # optional ` :: rest` lets us swallow sub-version rows like
    # `Framework :: Django :: 4.2` and still capture just "Django".
    _RE = re.compile(
        r"""^
            \s*
            Framework \s+ :: \s+
            ([^:]+?)
            (?: \s+ :: \s+ .+ )?
            \s*
        $""",
        re.VERBOSE | re.IGNORECASE,
    )

    def render_from_metadata(self, md, classifiers):
        frameworks = []
        for c in classifiers:
            match = self._RE.match(c)
            if not match:
                continue
            name = match.group(1)
            if name not in frameworks:
                frameworks.append(name)
        if not frameworks:
            return
        with self.full_output_file_name.open("w") as fout:
            svg_badge.render(
                fout,
                left_txt="framework",
                right_txt=" | ".join(frameworks),
                color="blue",
            )


class RequiresPython(PackageBadgeBase):
    """Renders the `Requires-Python` constraint as-is (e.g. `>=3.10`).

    Distinct from `PythonVersions`: this one reads the version spec the
    package declared (one line, exact constraint), whereas
    `PythonVersions` enumerates trove classifiers. Some projects only
    set one or the other — the user can disable whichever doesn't apply
    via `--local-badge-generate`.
    """

    badge_name = "requires-python"

    def render_from_metadata(self, md, classifiers):
        spec = md["Requires-Python"]
        if not spec:
            return
        with self.full_output_file_name.open("w") as fout:
            svg_badge.render(
                fout,
                left_txt="python",
                right_txt=str(spec).strip(),
                color="blue",
            )
