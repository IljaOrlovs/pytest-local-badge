import pathlib

import pytest

from . import svg_badge


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
