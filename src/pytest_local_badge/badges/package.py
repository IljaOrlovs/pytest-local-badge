"""Package-metadata badges — values pulled from an installed dist's `METADATA`.

Everything in here reads `importlib.metadata` rather than the pytest
session. One instance per (package, badge) pair so the user can run
`--local-badge-package=A --local-badge-package=B` and get two disjoint
sets of files prefixed with each canonical name.
"""

import importlib.metadata
import pathlib
import re
import warnings

from .. import svg_badge
from .base import BadgeBase


def _normalize_package_name(name: str) -> str:
    """PEP 503 canonical name — safe for use as a filename component."""
    return re.sub(r"[-_.]+", "-", name).lower()


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
    """License badge, preferring the `License-Expression` metadata field.

    Core metadata 2.4 deprecates the `License :: ...` trove classifiers in
    favour of a single SPDX `License-Expression` field, which is the form
    the packaging spec now recommends. We render that verbatim when
    present (e.g. `MIT`, `Apache-2.0 OR MIT`) and fall back to the legacy
    classifiers otherwise.

    For the classifier fallback, captures the final trove segment and
    strips a trailing " License" suffix so "MIT License" renders as "MIT".
    If multiple license classifiers are present (rare), the first match
    wins.
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
        expression = md.get("License-Expression")
        expression = str(expression).strip() if expression else ""

        classifier_value = ""
        for c in classifiers:
            match = self._RE.match(c)
            if match:
                classifier_value = match.group(1)
                break

        # A package should declare its license one way or the other, so if
        # both are set and they don't match verbatim, warn rather than
        # guess which spelling the maintainer meant. The comparison is a
        # naive case-insensitive one — `Apache-2.0` vs `Apache Software`
        # will trip it, but that pairing is itself the misconfiguration
        # worth flagging.
        if (
            expression
            and classifier_value
            and expression.casefold() != classifier_value.casefold()
        ):
            warnings.warn(
                f"Package {self.package_name!r} declares both "
                f"License-Expression ({expression!r}) and a License "
                f"classifier ({classifier_value!r}); using "
                f"License-Expression",
                stacklevel=1,
            )

        chosen = expression or classifier_value
        if chosen:
            self._render(chosen)

    def _render(self, right_txt: str):
        with self.full_output_file_name.open("w") as fout:
            svg_badge.render(
                fout,
                left_txt="License",
                right_txt=right_txt,
                color="yellow",
            )


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


class OperatingSystem(PackageBadgeBase):
    """Pipe-separated list of supported operating systems from classifiers.

    Reads `Operating System :: ...` trove rows and keeps the final
    segment (so `Operating System :: POSIX :: Linux` → "Linux",
    `Operating System :: MacOS` → "MacOS"). The catch-all
    `Operating System :: OS Independent` collapses to a single
    "OS Independent" badge value and short-circuits any other OS rows —
    a project that declares it has already said "anywhere".
    """

    badge_name = "os"
    _RE = re.compile(
        r"""^
            \s*
            Operating \s+ System \s+ :: \s+
            (?: .+ \s+ :: \s+ )?      # optional intermediate trove path
            (.+?)
            \s*
        $""",
        re.VERBOSE | re.IGNORECASE,
    )

    def render_from_metadata(self, md, classifiers):
        names = []
        for c in classifiers:
            match = self._RE.match(c)
            if not match:
                continue
            name = match.group(1)
            if name.lower() == "os independent":
                names = ["OS Independent"]
                break
            if name not in names:
                names.append(name)
        if not names:
            return
        with self.full_output_file_name.open("w") as fout:
            svg_badge.render(
                fout,
                left_txt="OS",
                right_txt=" | ".join(names),
                color="blue",
            )
