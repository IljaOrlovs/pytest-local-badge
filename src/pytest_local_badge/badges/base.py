"""Shared base class for every badge generator.

Lives in its own module so the per-category files (session / package /
custom) can import `BadgeBase` without pulling each other's dependencies
along for the ride.
"""

import pathlib


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
