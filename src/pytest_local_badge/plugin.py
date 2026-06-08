"""Main plugin module"""

import pathlib
import warnings

import pytest

from . import badges

BADGES = {
    "status": badges.TestSuccess,
    "cov": badges.PytestCov,
    "skipped": badges.Skipped,
    "xfailed": badges.XFailed,
    "warnings": badges.Warnings,
    "last-run": badges.LastRun,
    "duration": badges.Duration,
}

# Badges sourced from installed package metadata rather than the pytest
# session. Only emitted when the user passes `--local-badge-package=...`.
PACKAGE_BADGES = {
    "python": badges.PythonVersions,
    "license": badges.License,
    "private": badges.PrivatePackage,
    "version": badges.Version,
    "maturity": badges.DevelopmentStatus,
    "typed": badges.Typed,
    "implementation": badges.Implementation,
    "framework": badges.Framework,
    "requires-python": badges.RequiresPython,
    "os": badges.OperatingSystem,
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
    all_badges = sorted({**BADGES, **PACKAGE_BADGES}.keys())
    group.addoption(
        "--local-badge-generate",
        nargs="+",
        choices=all_badges,
        default=all_badges,
        help="List of local badges to generate.",
    )
    group.addoption(
        "--local-badge-package",
        action="append",
        default=[],
        metavar="PACKAGE",
        help=(
            "Installed distribution name to read metadata from for the "
            "package-classifier badges (python/license/private/...). Repeat "
            "for multiple packages — each gets its own set of badges, "
            "prefixed with the package's canonical name."
        ),
    )
    for badge_name, badge_cls in {**BADGES, **PACKAGE_BADGES}.items():
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

    out_dir: pathlib.Path

    def __init__(self, options):
        self.options = options
        self.out_dir = pathlib.Path(options.local_badge_output_dir)

    def pytest_sessionfinish(self, session, exitstatus):
        if not self.out_dir.is_dir():
            warnings.warn(
                f"Badge output dir {self.out_dir} ({self.out_dir.resolve()}) "
                "does not exist or is not a directory; skipping badge generation",
                stacklevel=1,
            )
            return
        enabled = set(self.options.local_badge_generate)
        for enabled_badge_name in self.options.local_badge_generate:
            badge_cls = BADGES.get(enabled_badge_name)
            if badge_cls is None:
                continue  # package badge — handled below
            badge = badge_cls(self.out_dir, self.options)
            badge.on_sessionfinish(session, exitstatus)
        packages = getattr(self.options, "local_badge_package", None) or []
        for package_name in packages:
            for badge_name, badge_cls in PACKAGE_BADGES.items():
                if badge_name not in enabled:
                    continue
                badge = badge_cls(self.out_dir, self.options, package_name)
                badge.on_sessionfinish(session, exitstatus)
