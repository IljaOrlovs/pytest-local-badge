import pathlib
import textwrap

import pytest


@pytest.fixture(autouse=True)
def tested_file(pytester):
    """The python file we are running pytest against."""
    sources_dir = pathlib.Path(pytester.path)
    fname = sources_dir / "mymodule.py"
    fname.write_text(
        textwrap.dedent("""
                def func1():
                    "This function will be covered."
                    return 42

                def uncovered_func2():
                    "This function will not be covered"
                    return -1
            """)
    )
    return fname


@pytest.fixture
def tests_dir(pytester):
    return pathlib.Path(pytester.mkdir("tests"))


@pytest.fixture(autouse=True)
def sample_pytest(tests_dir):
    test_fname = tests_dir / "test_me.py"
    test_fname.write_text(
        textwrap.dedent("""
                import mymodule

                def test_simple():
                    assert mymodule.func1() == 42
            """)
    )
    return test_fname


@pytest.mark.parametrize("no_cov", [True, False])
def test_default_behaviour(pytester, tests_dir, no_cov):
    badges_dir = pathlib.Path(pytester.mkdir("badges"))
    extra_args = []
    if no_cov:
        extra_args.append("--no-cov")
    result = pytester.runpytest(
        *extra_args,
        *["--cov", "mymodule", "--local-badge-output-dir", badges_dir, tests_dir],
    )
    assert result.ret == 0
    result.assert_outcomes(passed=1)
    # Check that the badge files were created
    assert (badges_dir / "tests.svg").is_file()
    if no_cov:
        assert not (badges_dir / "coverage.svg").exists()
    else:
        assert (badges_dir / "coverage.svg").is_file()


def test_duration_max_flag_is_recognised(pytester, tests_dir):
    """End-to-end: `--local-badge-duration-max` must be a real flag that
    pytest accepts and pipes through into the duration badge."""
    badges_dir = pathlib.Path(pytester.mkdir("badges"))
    result = pytester.runpytest(
        "--no-cov",
        # An impossibly tight budget (1ms) — any non-trivial test run will
        # blow past it, so the duration badge must render red.
        "--local-badge-duration-max=0.001",
        "--local-badge-generate=duration",
        "--local-badge-output-dir",
        badges_dir,
        tests_dir,
    )
    assert result.ret == 0
    duration_svg = (badges_dir / "duration.svg").read_text()
    # Red is the colour shields uses for failed/over-budget.
    assert "#e05d44" in duration_svg, "expected red badge after blowing tiny budget"
