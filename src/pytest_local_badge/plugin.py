"""Main plugin module"""

import pathlib

import pytest

from . import badges

BADGES = {
    "status": badges.TestSuccess,
    "cov": badges.PytestCov,
}


def pytest_addoption(parser):
    group = parser.getgroup("local_badge")
    group.addoption(
        "--no-local-badge",
        action="store_false",
        default=True,
        dest="pytest_local_badge_enabled",
        help="Disable the local badge plugin.",
    )
    group.addoption(
        "--local-badge-output-dir",
        action="store",
        default=None,
        help="The directory to save local badges to.",
    )
    all_badges = sorted(BADGES.keys())
    group.addoption(
        "--local-badge-generate",
        nargs="+",
        choices=all_badges,
        default=all_badges,
        help="List of local badges to generate.",
    )
    for badge_name, badge_cls in BADGES.items():
        badge_cls.pytest_addoption(group, badge_name)


@pytest.hookimpl(tryfirst=True)
def pytest_load_initial_conftests(early_config, parser, args):
    options = early_config.known_args_namespace
    if (
        early_config.known_args_namespace.pytest_local_badge_enabled
        and early_config.known_args_namespace.local_badge_output_dir
    ):
        plugin = LocalBadgePlugin(options)
        early_config.pluginmanager.register(plugin, "_local_badge")


class PytestLocalBadgeError(Exception):
    """A generic pytest_local_badge exception."""


class LocalBadgePlugin:
    """Generate local SVG badges."""

    options = None
    out_dir: pathlib.Path

    def __init__(self, options):
        self.options = options
        self.out_dir = pathlib.Path(options.local_badge_output_dir)
        if not self.out_dir.is_dir():
            raise PytestLocalBadgeError(
                f"Badge output dir {self.out_dir} ({self.out_dir.resolve()}) does not exist or is not a directory"
            )

    def pytest_sessionfinish(self, session, exitstatus):
        for enabled_badge_name in self.options.local_badge_generate:
            badge_cls = BADGES[enabled_badge_name]
            badge = badge_cls(self.out_dir, self.options)
            badge.on_sessionfinish(session, exitstatus)
