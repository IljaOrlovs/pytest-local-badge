"""Badge generators, grouped into four sibling modules.

* `base`    — `BadgeBase`, the parent of every badge class.
* `session` — badges sourced from the running pytest session
              (tests, coverage, skipped, xfailed, warnings, last-run,
              duration).
* `package` — badges sourced from an installed dist's `METADATA` via
              `importlib.metadata` (version, python, license, …).
* `custom`  — user-supplied `LABEL | MESSAGE` badges, with parsers for
              the CLI / file / env-var input channels.

This file re-exports the public surface so downstream code (plugin.py,
tests, anyone consuming the module) can keep using `pytest_local_badge.
badges.TestSuccess` etc. as before. The submodules are still importable
directly if you want the explicit path.
"""

# Stdlib re-imports: tests (and possibly downstream code) reach into
# `pytest_local_badge.badges.<stdlib>.X` to monkey-patch behaviour —
# e.g. freezing `datetime.datetime.now` for the `LastRun` badge, or
# stubbing `importlib.metadata.metadata` for the package-badge suite.
# Python modules are singletons, so binding the names here is enough to
# keep those patch paths working after the split.
import datetime  # noqa: F401  (re-exported)
import importlib.metadata  # noqa: F401  (re-exported)
import time  # noqa: F401  (re-exported)

from .base import BadgeBase
from .custom import (
    RESERVED_CUSTOM_SLUGS,
    CustomBadge,
    CustomSpec,
    CustomSpecError,
    parse_custom_cli,
    parse_custom_file,
    parse_custom_value,
)
from .package import (
    DevelopmentStatus,
    Framework,
    Implementation,
    License,
    OperatingSystem,
    PackageBadgeBase,
    PrivatePackage,
    PythonVersions,
    RequiresPython,
    Typed,
    Version,
)
from .session import (
    Duration,
    LastRun,
    PytestCov,
    Skipped,
    TestSuccess,
    Warnings,
    XFailed,
)

__all__ = [
    "RESERVED_CUSTOM_SLUGS",
    "BadgeBase",
    "CustomBadge",
    "CustomSpec",
    "CustomSpecError",
    "DevelopmentStatus",
    "Duration",
    "Framework",
    "Implementation",
    "LastRun",
    "License",
    "OperatingSystem",
    "PackageBadgeBase",
    "PrivatePackage",
    "PytestCov",
    "PythonVersions",
    "RequiresPython",
    "Skipped",
    "TestSuccess",
    "Typed",
    "Version",
    "Warnings",
    "XFailed",
    "parse_custom_cli",
    "parse_custom_file",
    "parse_custom_value",
]
