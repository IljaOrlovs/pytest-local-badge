import pathlib
import textwrap

import pytest


@pytest.fixture(autouse=True)
def tested_file(pytester):
    """The python file we are running pytest against."""
    sources_dir = pathlib.Path(pytester.path)
    fname = sources_dir / "mymodule.py"
    with open(fname, "w") as tested_module_f:
        tested_module_f.write(textwrap.dedent("""
                    def func1():
                        "This function will be covered."
                        return 42

                    def uncovered_func2():
                        "This function will not be covered"
                        return -1
                """))
    return fname


@pytest.fixture
def tests_dir(pytester):
    return pathlib.Path(pytester.mkdir("tests"))


@pytest.fixture(autouse=True)
def sample_pytest(tests_dir):
    test_fname = tests_dir / "test_me.py"
    with open(test_fname, "w") as test_f:
        test_f.write(textwrap.dedent("""
                    import mymodule

                    def test_simple():
                        assert mymodule.func1() == 42
                """))
    return test_fname


@pytest.mark.parametrize("no_cov", [True, False])
def test_default_behaviour(pytester, tests_dir, no_cov):
    badges_dir = pathlib.Path(pytester.mkdir("badges"))
    extra_args = []
    if no_cov:
        extra_args.append("--no-cov")
    result = pytester.runpytest(
        *extra_args,
        *["--cov", "mymodule", "--local-badge-output-dir", badges_dir, tests_dir]
    )
    assert result.ret == 0
    result.assert_outcomes(passed=1)
    # Check that the badge files were created
    assert (badges_dir / "tests.svg").is_file()
    if no_cov:
        assert not (badges_dir / "coverage.svg").exists()
    else:
        assert (badges_dir / "coverage.svg").is_file()
