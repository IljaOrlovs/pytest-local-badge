"""Quick and dirty test"""

import pathlib

import pytest


def test_import():
    import pytest_local_badge

    assert pytest_local_badge
    assert pytest_local_badge.plugin


@pytest.fixture
def simple_true_test(testdir):
    testdir.makepyfile("""
            def test_simple():
                assert (1 + 1) == 2
        """)


@pytest.mark.usefixtures("simple_true_test")
def test_no_output_dir(testdir):
    result = testdir.runpytest(
        "--local-badge-output-dir", pathlib.Path(str(testdir)) / "idontexist"
    )
    result.stderr.fnmatch_lines(
        [
            "* Badge output dir * does not exist or is not a directory*",
        ]
    )
    assert result.ret == 1


@pytest.mark.usefixtures("simple_true_test")
def test_disabled_and_no_output_dir(testdir):
    result = testdir.runpytest(
        "--no-cov",
        "--no-local-badge",
        "--local-badge-output-dir",
        pathlib.Path(str(testdir)) / "idontexist",
    )
    assert result.ret == 0
    result.assert_outcomes(passed=1)
