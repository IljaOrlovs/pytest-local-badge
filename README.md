# Pytest local badge

[![PyPI version](https://badge.fury.io/py/pytest-local-badge.svg)](https://badge.fury.io/py/pytest-local-badge)
[![CI](https://github.com/VRGhost/pytest-local-badge/actions/workflows/main.yml/badge.svg)](https://github.com/VRGhost/pytest-local-badge/actions/workflows/main.yml)
![Tests](https://raw.githubusercontent.com/VRGhost/pytest-local-badge/main/badges/tests.svg)
![Coverage](https://raw.githubusercontent.com/VRGhost/pytest-local-badge/main/badges/coverage.svg)



Pytest extension to generate SVG badge files with pytest stats (number of tests passed, `pytest-cov` coverage statistics.)

# Motivation

Everyone likes pretty code status badges.  However, hosting them can get bit troublesome when working on private projects.

This pytest plugin sidesteps the problem by generating local badge files that you can simply add to the project repository and reference in the `README.md` directly.

Having a bit of extra noise in your change history is worthy cost of having pretty badges, right?

# Installation

    pip install pytest-local-badge

# Usage

The only thing you have to tell the plugin is where to store badges:

        pytest --local-badge-output-dir badges/

All supported badges will be stored that directory.  You can find the complete list of supported options by calling `pytest -h` and looking for all configuration parameters starting with ` --local-badge-*`.

Here are the options available at the moment:

    --no-local-badge      Disable the local badge plugin.
    --local-badge-output-dir=LOCAL_BADGE_OUTPUT_DIR
                            The directory to save local badges to.
    --local-badge-generate={cov,status} [{cov,status} ...]
                            List of local badges to generate.

# Supported badges:

1. `status` -- Number of tests (total & passed)
2. `cov` -- Coverage report as per `pytest-cov` plugin (the `pytest-cov` must be installed separately.)