"""Tests for plugin."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from flake8_error_link import ERROR_LINK_REGEX_ARG_NAME, MSG, Plugin

_VALID_RAISE_MSG = "more information: http://example.com"


def _result(code: str) -> tuple[str, ...]:
    """Generate linting results.

    Args:
        code: The code to convert.

    Returns:
        The linting result.
    """
    tree = ast.parse(code)
    plugin = Plugin(tree)
    return tuple(f"{line}:{col} {msg}" for line, col, msg, _ in plugin.run())


@pytest.mark.parametrize(
    "code, expected_result",
    [
        pytest.param("", (), id="trivial"),
        pytest.param("raise Exception()", (f"1:0 {MSG}",), id="more information not provided"),
        pytest.param(
            "raise Exception(1)",
            (f"1:0 {MSG}",),
            id="more information not provided non-string literal",
        ),
        pytest.param(
            "raise Exception", (f"1:0 {MSG}",), id="more information not provided shorthand"
        ),
        pytest.param(
            "raise ValueError()",
            (f"1:0 {MSG}",),
            id="more information not provided alternate inbuilt exception",
        ),
        pytest.param(
            "\nraise Exception()",
            (f"2:0 {MSG}",),
            id="more information not provided not first line",
        ),
        pytest.param(
            "if True: raise Exception()",
            (f"1:9 {MSG}",),
            id="more information not provided not first column",
        ),
        pytest.param(
            f'raise Exception("{_VALID_RAISE_MSG}")',
            (),
            id="more information provided",
        ),
        pytest.param(
            f'raise ValueError("{_VALID_RAISE_MSG}")',
            (),
            id="more information provided alternate exception",
        ),
        pytest.param(
            f'raise Exception("first", "{_VALID_RAISE_MSG}")',
            (),
            id="more information provided second args",
        ),
        pytest.param(
            f'raise Exception("other text {_VALID_RAISE_MSG}")',
            (),
            id="more information provided not at start",
        ),
        pytest.param(
            f'raise Exception("{_VALID_RAISE_MSG} other text")',
            (),
            id="more information provided not at end",
        ),
        pytest.param(
            f'raise Exception(msg := "{_VALID_RAISE_MSG}")',
            (),
            id="more information provided walrus",
        ),
        pytest.param('msg = ""\nraise Exception(msg)', (), id="variable"),
        pytest.param("raise CustomError", (), id="custom exception shorthand"),
        pytest.param("raise CustomError()", (), id="custom exception"),
        pytest.param("raise Exception(function_call())", (), id="argument is a function call"),
        pytest.param(
            "raise Exception((lambda: 1)())", (), id="argument is lambda definition and call"
        ),
        pytest.param("raise", (), id="no exception"),
    ],
)
def test_plugin(code: str, expected_result: tuple[str, ...]):
    """
    given: code
    when: linting is run on the code
    then: the expected result is returned
    """
    assert _result(code) == expected_result


def test_integration_help():
    """
    given:
    when: the flake8 help message is generated
    then: plugin is registered with flake8
    """
    with subprocess.Popen(
        f"{sys.executable} -m flake8 --help",
        stdout=subprocess.PIPE,
        shell=True,
    ) as proc:
        stdout = proc.communicate()[0].decode(encoding="utf-8")

        assert "flake8-error-link" in stdout
        assert ERROR_LINK_REGEX_ARG_NAME in stdout


def create_code_file(code: str, base_path: Path) -> Path:
    """Create the code file with the given code.

    Args:
        code: The code to write to the file.
        base_path: The path to create the file within

    Returns:
        The path to the code file.
    """
    (code_file := base_path / "code.py").write_text(f'"""Docstring."""\n\n{code}')
    return code_file


def test_integration_fail(tmp_path: Path):
    """
    given: file with Python code that fails the linting
    when: the flake8 is run against the code
    then: the process exits with non-zero code and includes the error message
    """
    code_file = create_code_file("raise Exception", tmp_path)

    with subprocess.Popen(
        f"{sys.executable} -m flake8 {code_file}",
        stdout=subprocess.PIPE,
        shell=True,
    ) as proc:
        stdout = proc.communicate()[0].decode(encoding="utf-8")

        assert MSG in stdout
        assert proc.returncode


@pytest.mark.parametrize(
    "code, extra_args",
    [
        pytest.param(f"raise Exception('{_VALID_RAISE_MSG}')\n", "", id="default regex"),
        pytest.param(
            "raise Exception('test')\n", f"{ERROR_LINK_REGEX_ARG_NAME} test", id="custom regex"
        ),
    ],
)
def test_integration_pass(code: str, extra_args: str, tmp_path: Path):
    """
    given: file with Python code that passes the linting
    when: the flake8 is run against the code
    then: the process exits with zero code and empty stdout
    """
    code_file = create_code_file(code, tmp_path)

    with subprocess.Popen(
        f"{sys.executable} -m flake8 {code_file} {extra_args}",
        stdout=subprocess.PIPE,
        shell=True,
    ) as proc:
        stdout = proc.communicate()[0].decode(encoding="utf-8")

        assert MSG not in stdout
        assert not proc.returncode, stdout
