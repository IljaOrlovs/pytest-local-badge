import pathlib

import pytest

from . import svg_badge


class BadgeBase:
    """Base class for badge generators."""

    output_file_name = "UNKNOWN.svg"
    output_dir: pathlib.Path

    def __init__(self, output_dir: pathlib.Path, options):
        self.options = options
        self.output_dir = output_dir
        assert self.output_dir.is_dir(), self.output_dir

    @property
    def full_output_file_name(self):
        return (self.output_dir / self.output_file_name).resolve()

    @classmethod
    def pytest_addoption(cls, option_group, my_prefix: str):
        pass

    def get_colour(self, success_pct: float | None):
        if success_pct in (None, False):
            out = "lightgrey"
        elif success_pct >= 0.99 or (success_pct is True):
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
        tests_success = exitstatus == 0
        total_tests = session.testscollected
        failed_tests = session.testsfailed
        succeeded_tests = max(total_tests - failed_tests, 0)
        if failed_tests == 0 or (succeeded_tests == total_tests):
            right_text = f"{total_tests}"
        else:
            right_text = f"{succeeded_tests}/{total_tests}"
        if (total_tests == 0) or not tests_success:
            coverage_percentage = 0
        else:
            coverage_percentage = (total_tests - failed_tests) / total_tests
        with open(self.full_output_file_name, "w") as fout:
            svg_badge.render(
                fout,
                left_txt="tests",
                right_txt=right_text,
                color=self.get_colour(coverage_percentage),
            )


class PytestCov(BadgeBase):
    output_file_name = "coverage.svg"

    def on_sessionfinish(self, session: pytest.Session, exitstatus: int):
        if session.config.pluginmanager.hasplugin("_cov"):
            plugin = session.config.pluginmanager.getplugin("_cov")
            if plugin and plugin.cov_controller:
                if plugin.cov_total:
                    coverage_percentage = (
                        plugin.cov_total / 100
                    )  # The plugin returns value as an int
                else:
                    coverage_percentage = 0
                with open(self.full_output_file_name, "w") as fout:
                    svg_badge.render(
                        fout,
                        left_txt="coverage",
                        right_txt=f"{int(coverage_percentage * 100)}%",
                        color=self.get_colour(coverage_percentage),
                    )
