# pytest-local-badge

[![PyPI version](https://badge.fury.io/py/pytest-local-badge.svg)](https://pypi.org/project/pytest-local-badge/)
[![Python versions](https://img.shields.io/pypi/pyversions/pytest-local-badge.svg)](https://pypi.org/project/pytest-local-badge/)
[![CI](https://github.com/VRGhost/pytest-local-badge/actions/workflows/main.yml/badge.svg)](https://github.com/VRGhost/pytest-local-badge/actions/workflows/main.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Tests](https://raw.githubusercontent.com/VRGhost/pytest-local-badge/main/badges/tests.svg)
![Coverage](https://raw.githubusercontent.com/VRGhost/pytest-local-badge/main/badges/coverage.svg)

> **Self-hosted pytest status and coverage badges.** No shields.io, no Codecov, no third-party uptime to depend on — just SVG files committed alongside your code.

## Why?

Shiny badges in your README are great. But the usual recipe — a hosted shield service reading numbers from a hosted CI provider — falls apart the moment you:

- Work on a **private repo** the badge service can't see.
- Run on **internal CI** behind a VPN.
- Don't want a **third-party SVG endpoint** loading every time someone opens your README.
- Want badges that **work offline** (think air-gapped environments, local docs builds, PDFs).

`pytest-local-badge` skips the round-trip. Every test run regenerates plain SVG files next to your source. Commit them. Reference them with a normal relative path. Done.

## Install

```bash
pip install pytest-local-badge
```

For the coverage badge you also need [`pytest-cov`](https://pypi.org/project/pytest-cov/):

```bash
pip install pytest-local-badge pytest-cov
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
--local-badge-generate {cov,status} [{cov,status} ...]
                                 Which badges to generate. Defaults to both.
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

Use `--local-badge-generate status` (or `cov`) to render just one.

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
pdm run pytest
pdm run ruff check ./src ./test
pdm run pyright
```

## License

MIT — see [LICENSE](LICENSE).
