"""Custom badges — user-supplied `LABEL | MESSAGE` pairs.

This module owns parsing and rendering only. The gather logic that
merges env vars → file → CLI lives in `pytest_local_badge.plugin` so
the option namespace stays one hop away from where the options are
declared.
"""

import dataclasses
import json
import pathlib
import re

from .. import svg_badge
from .base import BadgeBase

# Filenames the user must not clobber with a custom badge. Reserved at the
# `slug` level (post-canonicalisation), not the human label.
RESERVED_CUSTOM_SLUGS = frozenset(
    {
        "tests",
        "coverage",
        "skipped",
        "xfailed",
        "warnings",
        "duration",
        "last-run",
    }
)

_HEX_COLOUR_RE = re.compile(
    r"^#(?:[0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$",
    re.IGNORECASE,
)
_DEFAULT_CUSTOM_COLOUR = "blue"


def _is_colour_token(token: str) -> bool:
    """Palette-name or `#rgb` / `#rrggbb` / `#rrggbbaa` literal."""
    return token in svg_badge.COLORS or bool(_HEX_COLOUR_RE.match(token))


def _slugify_custom_label(label: str) -> str:
    """Filename slug for a custom-badge label.

    Lowercase, replace any non-`[a-z0-9-]` run with a single `-`, trim
    leading/trailing `-`. Distinct from `_normalize_package_name`, which
    only canonicalises the three PEP 503 separators — custom labels can
    contain spaces, slashes, etc. and need a stricter pass.
    """
    slug = re.sub(r"[^a-z0-9-]+", "-", label.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


@dataclasses.dataclass(frozen=True)
class CustomSpec:
    """One custom badge: left label, right message, colour, filename.

    `slug` is optional in user-facing inputs; when unset, `derived_slug`
    falls back to slugifying `label`. Stored separately so the file form
    can override the filename without affecting the displayed label.
    """

    label: str
    message: str
    colour: str = _DEFAULT_CUSTOM_COLOUR
    slug: str | None = None

    @property
    def derived_slug(self) -> str:
        if self.slug:
            return _slugify_custom_label(self.slug)
        return _slugify_custom_label(self.label)


class CustomSpecError(ValueError):
    """Raised when a user-supplied custom-badge spec can't be parsed.

    Distinct from `PytestLocalBadgeError` (a plugin-level config failure):
    spec errors carry the offending raw input so the gather layer can
    decide whether to abort or warn-and-skip.
    """


def parse_custom_value(raw: str) -> tuple[str, str]:
    """Split a `MESSAGE` or `MESSAGE:COLOR` tail into (message, colour).

    Splits on the **last** `:` and only treats the suffix as a colour if
    it's a known palette name or hex literal — otherwise the whole input
    is the message and the colour defaults to `blue`. Lets the common
    shell pattern survive embedded colons (timestamps, URLs).
    """
    if ":" in raw:
        head, _, tail = raw.rpartition(":")
        tail_stripped = tail.strip()
        if _is_colour_token(tail_stripped):
            return head.strip(), tail_stripped
    return raw.strip(), _DEFAULT_CUSTOM_COLOUR


def parse_custom_cli(raw: str) -> CustomSpec:
    """Parse a `--local-badge-custom` argument: `LABEL=MESSAGE[:COLOR]`.

    Splits on the *first* `=` — labels can't contain `=` but messages
    can (e.g. base64-ish values).
    """
    if "=" not in raw:
        raise CustomSpecError(
            f"--local-badge-custom value must be 'LABEL=MESSAGE[:COLOR]'; got {raw!r}"
        )
    label, _, rest = raw.partition("=")
    label = label.strip()
    if not label:
        raise CustomSpecError(f"--local-badge-custom value has an empty LABEL: {raw!r}")
    message, colour = parse_custom_value(rest)
    return CustomSpec(label=label, message=message, colour=colour)


def _spec_from_dict(row, source: str) -> CustomSpec:
    """Build a `CustomSpec` from a `{label, message, color?, slug?}` dict.

    `source` is included in error messages so the user can find the bad
    entry quickly when a file has dozens of rows.
    """
    if not isinstance(row, dict):
        raise CustomSpecError(
            f"{source}: each entry must be a JSON object, got {type(row).__name__}"
        )
    label = row.get("label")
    message = row.get("message")
    colour = row.get("color", _DEFAULT_CUSTOM_COLOUR)
    slug = row.get("slug")
    if not isinstance(label, str) or not label.strip():
        raise CustomSpecError(f"{source}: entry missing non-empty 'label': {row!r}")
    if not isinstance(message, str):
        raise CustomSpecError(f"{source}: entry missing string 'message': {row!r}")
    if not isinstance(colour, str):
        raise CustomSpecError(f"{source}: 'color' must be a string: {row!r}")
    if slug is not None and not isinstance(slug, str):
        raise CustomSpecError(f"{source}: 'slug' must be a string: {row!r}")
    return CustomSpec(
        label=label.strip(),
        message=message.strip(),
        colour=colour.strip(),
        slug=slug.strip() if slug else None,
    )


def parse_custom_file(path: pathlib.Path) -> list[CustomSpec]:
    """Parse a custom-badge file as JSON-list-first, JSONL-fallback.

    Try `json.loads(text)` over the whole file first. On success the
    top level must be a list of objects — anything else is an error.
    On `JSONDecodeError`, fall back to JSONL: each non-blank,
    non-`#`-prefixed line is decoded independently and bad lines abort
    (we report the line number so the user can fix it).
    """
    text = path.read_text(encoding="utf-8")
    source = str(path)
    # Distinguish "parsed successfully (even as None)" from "decode
    # failed → fall through to JSONL". A bare `null` is valid JSON
    # whose loads-result is `None`, so a `data is not None` check would
    # mis-route it into the JSONL branch.
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        json_ok = False
        data = None
    else:
        json_ok = True
    specs: list[CustomSpec] = []
    if json_ok:
        if not isinstance(data, list):
            raise CustomSpecError(
                f"{source}: top-level JSON must be a list of objects, "
                f"got {type(data).__name__}"
            )
        for idx, row in enumerate(data):
            specs.append(_spec_from_dict(row, source=f"{source}[{idx}]"))
        return specs
    # JSONL fallback.
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise CustomSpecError(
                f"{source}:{lineno}: malformed JSON line ({exc.msg})"
            ) from exc
        specs.append(_spec_from_dict(row, source=f"{source}:{lineno}"))
    return specs


class CustomBadge(BadgeBase):
    """Renders one user-supplied `CustomSpec` to `<slug>.svg`.

    Filename, label, message, and colour all come from the spec — this
    class is just the bridge from a `CustomSpec` to the existing
    `svg_badge.render` call so the gather layer doesn't need to know
    anything about file handles.
    """

    def __init__(self, output_dir: pathlib.Path, options, spec: CustomSpec):
        super().__init__(output_dir, options)
        self.spec = spec

    @property
    def full_output_file_name(self):
        return (self.output_dir / f"{self.spec.derived_slug}.svg").resolve()

    def on_sessionfinish(self, session, exitstatus):
        with self.full_output_file_name.open("w") as fout:
            svg_badge.render(
                fout,
                left_txt=self.spec.label,
                right_txt=self.spec.message,
                color=self.spec.colour,
            )
