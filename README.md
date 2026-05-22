# pytest-local-badge

[![PyPI version](https://badge.fury.io/py/pytest-local-badge.svg)](https://pypi.org/project/pytest-local-badge/)
[![Python versions](https://img.shields.io/pypi/pyversions/pytest-local-badge.svg)](https://pypi.org/project/pytest-local-badge/)
[![CI](https://github.com/VRGhost/pytest-local-badge/actions/workflows/main.yml/badge.svg)](https://github.com/VRGhost/pytest-local-badge/actions/workflows/main.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

### Our badges:

![Tests](https://raw.githubusercontent.com/VRGhost/pytest-local-badge/main/badges/tests.svg)
![Coverage](https://raw.githubusercontent.com/VRGhost/pytest-local-badge/main/badges/coverage.svg)
![Skipped](https://raw.githubusercontent.com/VRGhost/pytest-local-badge/main/badges/skipped.svg)
![XFailed](https://raw.githubusercontent.com/VRGhost/pytest-local-badge/main/badges/xfailed.svg)
![Warnings](https://raw.githubusercontent.com/VRGhost/pytest-local-badge/main/badges/warnings.svg)
![Duration](https://raw.githubusercontent.com/VRGhost/pytest-local-badge/main/badges/duration.svg)

> **Self-hosted pytest status and coverage badges.** No shields.io, no Codecov, no third-party uptime to depend on — just SVG files committed alongside your code.

## Why?

Shiny badges in your README are great. But the usual recipe — a hosted shield service reading numbers from a hosted CI provider — falls apart the moment you:

- Work on a **private repo** the badge service can't see.
- Run on **internal CI** behind a VPN.
- Don't want a **third-party SVG endpoint** loading every time someone opens your README.
- Want badges that **work offline** (think air-gapped environments, local docs builds, PDFs).

`pytest-local-badge` skips the round-trip. Every test run regenerates plain SVG files next to your source. Commit them. Reference them with a normal relative path. Done.

## Install

Just the test-count badge:

```bash
pip install pytest-local-badge
```

With the coverage badge ([`pytest-cov`](https://pypi.org/project/pytest-cov/) pulled in automatically):

```bash
pip install "pytest-local-badge[cov]"
```

## Quick start

Tell pytest where to drop the SVGs:

```bash
pytest --cov=my_package --local-badge-output-dir badges/
```

You'll get:

```
badges/
├── tests.svg       # e.g. "tests | 142"  (or "139/142" if some fail)
└── coverage.svg    # e.g. "coverage | 87%"
```

Then in your `README.md`:

```markdown
![Tests](badges/tests.svg)
![Coverage](badges/coverage.svg)
```

### Make it permanent

Add it to your `pyproject.toml` so every `pytest` run keeps the badges in sync:

```toml
[tool.pytest.ini_options]
addopts = "--cov=my_package --local-badge-output-dir badges/"
```

…and commit the badge directory. The diff is tiny (an SVG only changes when the numbers change) and lives forever in your repo's history.

## Command-line options

```
--no-local-badge                 Disable the plugin for this run.
--local-badge-output-dir DIR     Where to write the SVGs. (Required to activate.)
--local-badge-generate {cov,duration,skipped,status,warnings,xfailed} [...]
                                 Which badges to generate. Defaults to all of them.
--local-badge-duration-max SECONDS
                                 Duration "budget" for the `duration` badge. When
                                 set, colour thresholds scale proportionally — e.g.
                                 `--local-badge-duration-max=60` gives brightgreen
                                 ≤ 6 s, orange ≤ 60 s, red > 60 s. Without it, the
                                 default absolute scale applies.
```

## Badge colour scale

Both badges colour-grade by ratio (pass rate or coverage):

| Range | Colour |
|------:|--------|
| ≥ 99% | brightgreen |
| ≥ 87% | green |
| ≥ 75% | yellowgreen |
| ≥ 50% | yellow |
| ≥ 30% | orange |
| < 30% | red |
| no data | lightgrey |

"No data" is reserved for genuinely missing input (no tests collected, `pytest-cov` produced no report) — a real 0% renders **red**, not grey.

## Supported badges

| Name | File | Shows |
|------|------|-------|
| `status` | `tests.svg` | Total tests collected, or `passed/total` when some failed. |
| `cov` | `coverage.svg` | `pytest-cov` line coverage as a percentage. Requires `pytest-cov`. |
| `skipped` | `skipped.svg` | Count of `@pytest.mark.skip` / `pytest.skip(...)` tests. Colours by the fraction of the suite that actually ran. |
| `xfailed` | `xfailed.svg` | Count of expected-failure (`@pytest.mark.xfail`) tests. |
| `warnings` | `warnings.svg` | Number of warnings raised during the run. Colour-graded by absolute count (0 → green, anything else escalates fast). |
| `duration` | `duration.svg` | Total test session wall-clock time (`4.2s`, `1m 23s`, `1h 30m`). Colours by absolute thresholds by default, or by `--local-badge-duration-max=SECONDS` when you set a budget. |

Pick which ones to render with `--local-badge-generate`, e.g.:

```bash
pytest --local-badge-output-dir badges/ --local-badge-generate status cov warnings
```

By default *all* badges are generated.

## How it compares

| | shields.io / Codecov / Coveralls | **pytest-local-badge** |
|---|---|---|
| Needs an external HTTP service | yes | no |
| Works on private repos out of the box | depends on plan | yes |
| Survives going offline | no | yes |
| Adds extra commits to history | no | yes (one per badge change) |
| Cost | free → paid tiers | free, forever |

If you're already happy with a hosted service, keep using it. If "another SaaS dependency for two SVGs" feels excessive — this plugin is for you.

## Contributing

Issues and PRs welcome: <https://github.com/VRGhost/pytest-local-badge>

```bash
git clone https://github.com/VRGhost/pytest-local-badge
cd pytest-local-badge
pdm install

# Measure coverage of the plugin itself, then regenerate the committed
# badges with that data. We need `coverage run` (not just `pytest --cov`)
# because the plugin is imported by pytest *before* pytest-cov starts
# measuring, which would otherwise leave module-level code uncounted.
# CI enforces 100% via `--fail-under=100`.
pdm run coverage erase
pdm run coverage run -m pytest
pdm run coverage combine
pdm run coverage report -m --fail-under=100
# Pipe the same data into pytest-cov so the coverage badge reflects the
# real 100%, not the partial number you'd get from `pytest --cov` alone.
pdm run pytest --cov=pytest_local_badge --cov-append

pdm run ruff check ./src ./test
pdm run pyright
```

## Acknowledgements

The bundled `verdana_11px_normal.json` character-width table comes from
[anafanafo](https://github.com/metabolize/anafanafo) (MIT). It's the same
table [shields.io](https://shields.io) uses to size their badges, so locally
generated badges line up visually with their hosted siblings. See
[NOTICE](NOTICE) for attribution details.

## License

MIT — see [LICENSE](LICENSE).
