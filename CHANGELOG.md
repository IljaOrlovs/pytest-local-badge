# Changelog

All notable changes to **pytest-local-badge** are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] — 2025-06-07

### Added
- **Four new badges** built on pytest's own session/terminalreporter
  state, no new runtime deps:
  - `skipped` — count of `@pytest.mark.skip` tests, colour-graded by the
    fraction of the suite that actually ran.
  - `xfailed` — count of expected-failure (`@pytest.mark.xfail`) tests,
    same colour model.
  - `warnings` — count of warnings raised during the session. 0 is
    brightgreen; anything above escalates through green / yellow / orange
    / red as it climbs.
  - `duration` — total wall-clock time formatted as `4.2s` / `1m 23s` /
    `1h 30m`, colour-graded against absolute thresholds (≤10s → bright
    green, >30min → red). Pass `--local-badge-duration-max=SECONDS` to
    switch to a proportional scale tied to your own budget — e.g.
    `-max=60` puts the red line at 60 s and scales the other colours
    accordingly.
- Per-badge `pytest_addoption` extensibility hook (previously a `pass`)
  is now actively used by `Duration` and available for downstream badge
  classes to register their own CLI flags.
- **100% test coverage** (branch + statement), enforced in CI via
  `coverage report --fail-under=100`. Required restructuring the CI test
  command around `coverage run -m pytest` so coverage starts before the
  plugin loads — `pytest --cov` alone misses module-level code in
  self-hosting pytest plugins.
- `[cov]` install extra so `pip install "pytest-local-badge[cov]"` pulls in
  `pytest-cov` automatically.
- Per-glyph Verdana-11 width table (from
  [anafanafo](https://github.com/metabolize/anafanafo)) — badges now size
  themselves the same way `shields.io` does and no longer mis-align on
  narrow (`iIl1`) or wide (`WMm`) text.
- `py.typed` marker so downstream type checkers consume the bundled
  annotations (PEP 561).
- Expanded test coverage for badge colour selection (regression tests for
  the `0 == False` bug, full coverage of every colour threshold).
- `NOTICE` file with attribution for bundled third-party data.

### Changed
- **Project modernised**: build backend switched from `setuptools` to
  [PDM](https://pdm-project.org/) (`pdm-backend`), SCM-driven versioning,
  dynamic `version`. `setup.py` and `tox.ini` removed.
- QA toolchain replaced: `black` + `flake8` → `ruff` (lint + format),
  added `pyright` for type checking.
- CI rewritten around PDM with a separate, OIDC-trusted release workflow
  (`sigstore` signing, GitHub Release notes from this changelog, Test PyPI
  + PyPI publish).
- Project metadata refreshed for PyPI discoverability: longer
  description, more classifiers (`Topic :: Software Development :: Testing`,
  `Typing :: Typed`, …), wider keyword list.
- README rewritten with a clearer value proposition, a comparison table
  versus hosted shield services, and a documented colour scale.

### Fixed
- **Badge width**: previously only the *right* half of a badge had
  horizontal text padding, so labels visibly crowded the left edge and
  badges came out ~10 px narrower than the shields.io equivalent. Both
  halves now get 5 px on each side of the text, so widths match shields
  within a pixel. Existing committed `*.svg` files will show a one-time
  diff the next time they're regenerated.
- **Colour bug**: `get_colour(0)` was returning `"lightgrey"` instead of
  `"red"` because `0 in (None, False)` evaluates true in Python
  (`False == 0`). All-failed test suites and 0% coverage now render red as
  intended. *Behaviour change for anyone whose badges relied on the old
  output.*
- `TestSuccess` no longer conflates "no tests collected" with "tests
  failed": empty suites render grey (no data), failures render red.
- `PytestCov` distinguishes "pytest-cov produced no report" (`cov_total is
  None` → grey) from a genuine 0% coverage (→ red).
- `open(...)` calls replaced with `pathlib.Path.open()` (ruff PTH rules).
- Removed a dead, never-asserted statement from the badge tests
  (`cli_options.__dict__`) and an unreachable `success_pct is True`
  branch in `get_colour`.
- Stripped redundant `assert output_dir.is_dir()` from `BadgeBase` — the
  same check already happens upstream in `LocalBadgePlugin` and the
  assertion was eliminated by `python -O`.
- README no longer advertises `--local-badge-status-file-name` and
  `--local-badge-cov-file-name`, which were never actually registered.

### Removed
- `setup.py`, `tox.ini`.
- The stale `# noqa: E501` line in `svg_badge.py` (replaced by a per-file
  ruff ignore).

## [1.0.3] — 2025-01-23
- Compatibility with Python 3.10 – 3.14 (community contribution: #1).

## [1.0.2] and earlier
- Tagged releases preceding this changelog. See the
  [git history](https://github.com/IljaOrlovs/pytest-local-badge/commits/main)
  for details.

[Unreleased]: https://github.com/IljaOrlovs/pytest-local-badge/compare/v1.0.3...HEAD
[1.0.3]: https://github.com/IljaOrlovs/pytest-local-badge/releases/tag/v1.0.3
