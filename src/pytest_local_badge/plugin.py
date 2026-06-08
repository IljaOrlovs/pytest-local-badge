"""Main plugin module"""

import os
import pathlib
import warnings

import pytest

from . import badges

_CUSTOM_ENV_PREFIX = "PYTEST_LOCAL_BADGE_CUSTOM_"

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
    group.addoption(
        "--local-badge-custom",
        action="append",
        default=[],
        metavar="LABEL=MESSAGE[:COLOR]",
        help=(
            "Render an arbitrary 'LABEL | MESSAGE' badge. Repeat the flag "
            "for more than one. Trailing ':COLOR' is parsed only when COLOR "
            "is a known palette name or `#hex` literal; otherwise the whole "
            "value is the message and the colour defaults to blue."
        ),
    )
    group.addoption(
        "--local-badge-custom-file",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "Read custom badges from a JSON list or JSONL file (auto-detected). "
            "Each entry: {label, message, color?, slug?}. Repeatable."
        ),
    )
    group.addoption(
        "--local-badge-custom-strict",
        action="store_true",
        default=False,
        help=(
            "Treat empty MESSAGE values in custom badges as errors rather "
            "than silently skipping them. Useful in CI when you'd rather "
            "fail loudly than produce a stale badge set."
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
        for spec in _gather_custom_specs(self.options, os.environ):
            badge = badges.CustomBadge(self.out_dir, self.options, spec)
            badge.on_sessionfinish(session, exitstatus)


def _merge_custom_sources(options, environ) -> dict[str, badges.CustomSpec]:
    """Build the slug-keyed map of specs from env → files → CLI.

    Each source overwrites the previous one's entry under the same slug,
    so the final dict reflects "last source wins". Kept separate from
    validation so the merge is trivially testable and the gather
    function stays under the complexity ceiling.
    """
    merged: dict[str, badges.CustomSpec] = {}
    for key in sorted(environ):
        if not key.startswith(_CUSTOM_ENV_PREFIX):
            continue
        label = key[len(_CUSTOM_ENV_PREFIX) :].lower().replace("_", "-")
        if not label:
            continue
        message, colour = badges.parse_custom_value(environ[key])
        spec = badges.CustomSpec(label=label, message=message, colour=colour)
        merged[spec.derived_slug] = spec
    for path_str in getattr(options, "local_badge_custom_file", None) or []:
        for spec in badges.parse_custom_file(pathlib.Path(path_str)):
            merged[spec.derived_slug] = spec
    for raw in getattr(options, "local_badge_custom", None) or []:
        spec = badges.parse_custom_cli(raw)
        merged[spec.derived_slug] = spec
    return merged


def _validate_custom_slug(slug: str, spec: badges.CustomSpec) -> None:
    """Raise if `slug` would produce a broken or built-in filename.

    Empty slugs come from labels like `"!!!"` that canonicalise away to
    nothing — silently producing `.svg` would be a worse failure mode
    than the explicit error.
    """
    if not slug:
        raise PytestLocalBadgeError(
            f"custom badge label {spec.label!r} canonicalises to an "
            "empty slug; pick a label with at least one alphanumeric "
            "character or set an explicit 'slug' in the file form."
        )
    if slug in badges.RESERVED_CUSTOM_SLUGS:
        raise PytestLocalBadgeError(
            f"custom badge slug {slug!r} (from label {spec.label!r}) "
            "collides with a built-in badge filename; rename the label "
            "or set an explicit non-reserved 'slug' in the file form."
        )


def _gather_custom_specs(options, environ) -> list[badges.CustomSpec]:
    """Merge env vars + files + CLI flags into a final list of custom specs.

    Precedence (last wins): env vars → files → CLI flags. Dedup is by
    the derived filename slug, not the raw label — so two labels that
    canonicalise to the same slug are treated as the same badge and the
    later source overrides the earlier one. Reserved-slug collisions
    raise `PytestLocalBadgeError`: the spec calls this a hard error
    because silently overwriting a built-in badge is worse than failing
    fast.
    """
    merged = _merge_custom_sources(options, environ)
    for slug, spec in merged.items():
        _validate_custom_slug(slug, spec)
    # Empty-message handling. Default is "skip silently" so shell
    # patterns like `--local-badge-custom "commit=$(git rev-parse ...)"`
    # don't blow up in tarball checkouts. `--local-badge-custom-strict`
    # flips it to a hard error.
    strict = getattr(options, "local_badge_custom_strict", False)
    final: list[badges.CustomSpec] = []
    for spec in merged.values():
        if not spec.message:
            if strict:
                raise PytestLocalBadgeError(
                    f"--local-badge-custom-strict: empty MESSAGE for "
                    f"label {spec.label!r}"
                )
            continue
        final.append(spec)
    return final
