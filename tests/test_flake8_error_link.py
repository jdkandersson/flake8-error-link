"""Tests for plugin."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from flake8_error_link import (
    BUILTIN_CODE,
    BUILTIN_MSG,
    CUSTOM_CODE,
    CUSTOM_MSG,
    ERROR_LINK_REGEX_ARG_NAME,
    RE_RAISE_CODE,
    RE_RAISE_MSG,
    VARIABLE_INCLUDED_CODE,
    VARIABLE_INCLUDED_MSG,
    Plugin,
)

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
        pytest.param(
            "raise Exception()", (f"1:0 {BUILTIN_MSG}",), id="more information not provided"
        ),
        pytest.param(
            "raise Exception(1)",
            (f"1:0 {BUILTIN_MSG}",),
            id="more information not provided non-string literal",
        ),
        pytest.param(
            "raise Exception",
            (f"1:0 {BUILTIN_MSG}",),
            id="more information not provided shorthand",
        ),
        pytest.param(
            "raise ValueError()",
            (f"1:0 {BUILTIN_MSG}",),
            id="more information not provided alternate inbuilt exception",
        ),
        pytest.param(
            "\nraise Exception()",
            (f"2:0 {BUILTIN_MSG}",),
            id="more information not provided not first line",
        ),
        pytest.param(
            "if True: raise Exception()",
            (f"1:9 {BUILTIN_MSG}",),
            id="more information not provided not first column",
        ),
        pytest.param(
            "raise CustomError",
            (f"1:0 {CUSTOM_MSG}",),
            id="custom exception more information not provided shorthand",
        ),
        pytest.param(
            "raise CustomError()",
            (f"1:0 {CUSTOM_MSG}",),
            id="custom exception more information not provided",
        ),
        pytest.param(
            'msg = ""\nraise Exception(msg)',
            (f"2:0 {VARIABLE_INCLUDED_MSG}",),
            id="more information not provided variable",
        ),
        pytest.param(
            "raise Exception(function_call())",
            (f"1:0 {VARIABLE_INCLUDED_MSG}",),
            id="more information not provided argument is a function call",
        ),
        pytest.param(
            "raise Exception((lambda: 1)())",
            (f"1:0 {VARIABLE_INCLUDED_MSG}",),
            id="more information not provided argument is lambda definition and call",
        ),
        pytest.param(
            "raise", (f"1:0 {RE_RAISE_MSG}",), id="more information not provided no exception"
        ),
        pytest.param(
            "raise Exception() from exc",
            (f"1:0 {BUILTIN_MSG}",),
            id="more information not provided from",
        ),
        pytest.param(
            "raise Exception(1 + 1)",
            (f"1:0 {VARIABLE_INCLUDED_MSG}",),
            id="more information not provided +",
        ),
        pytest.param(
            "raise Exception(1 + 1 + 1)",
            (f"1:0 {VARIABLE_INCLUDED_MSG}",),
            id="more information not provided + multiple",
        ),
        pytest.param(
            "raise Exception(1 % 1)",
            (f"1:0 {VARIABLE_INCLUDED_MSG}",),
            id="more information not provided %",
        ),
        pytest.param(
            f'raise Exception(1 % "{_VALID_RAISE_MSG}")',
            (f"1:0 {VARIABLE_INCLUDED_MSG}",),
            id="more information not provided % right string",
        ),
        pytest.param(
            'raise Exception("%s" % 1)',
            (f"1:0 {VARIABLE_INCLUDED_MSG}",),
            id="more information not provided % left string",
        ),
        pytest.param(
            'raise Exception("%s" % [1])',
            (f"1:0 {VARIABLE_INCLUDED_MSG}",),
            id="more information not provided % right list",
        ),
        pytest.param(
            f'raise Exception([].join(["{_VALID_RAISE_MSG}"]))',
            (f"1:0 {VARIABLE_INCLUDED_MSG}",),
            id="more information not provided join not on string",
        ),
        pytest.param(
            f'raise Exception([].format("{_VALID_RAISE_MSG}"))',
            (f"1:0 {VARIABLE_INCLUDED_MSG}",),
            id="more information not provided format not on string",
        ),
        pytest.param(
            f'raise Exception("{_VALID_RAISE_MSG}")',
            (),
            id="more information provided",
        ),
        pytest.param(
            f'msg = ""\nraise Exception(msg, "{_VALID_RAISE_MSG}")',
            (),
            id="more information provided variable",
        ),
        pytest.param(
            f'raise CustomError("{_VALID_RAISE_MSG}")',
            (),
            id="more information provided custom exception",
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
            f'raise Exception("{_VALID_RAISE_MSG}", "second")',
            (),
            id="more information provided first args",
        ),
        pytest.param(
            f'raise Exception("{_VALID_RAISE_MSG}" + "trailing ")',
            (),
            id="more information provided string + first",
        ),
        pytest.param(
            f'raise Exception("leading " + "{_VALID_RAISE_MSG}")',
            (),
            id="more information provided string + second",
        ),
        pytest.param(
            f'raise Exception("leading " + "{_VALID_RAISE_MSG}" + "trailing")',
            (),
            id="more information provided string multiple +",
        ),
        pytest.param(
            f'raise Exception("{_VALID_RAISE_MSG}" + trailing)',
            (),
            id="more information provided string + first variable",
        ),
        pytest.param(
            f'raise Exception(leading + "{_VALID_RAISE_MSG}")',
            (),
            id="more information provided string + second variable",
        ),
        pytest.param(
            f'raise Exception("{_VALID_RAISE_MSG}" "trailing ")',
            (),
            id="more information provided string space first",
        ),
        pytest.param(
            f'raise Exception("leading " "{_VALID_RAISE_MSG}")',
            (),
            id="more information provided string space second",
        ),
        pytest.param(
            f'raise Exception("leading " "{_VALID_RAISE_MSG}" "trailing")',
            (),
            id="more information provided string multiple space",
        ),
        pytest.param(
            f'raise Exception("leading " "{_VALID_RAISE_MSG}" + "trailing")',
            (),
            id="more information provided string multiple space and +",
        ),
        pytest.param(
            f'raise Exception("%s".format("{_VALID_RAISE_MSG}"))',
            (),
            id="more information provided string format more info in argument",
        ),
        pytest.param(
            f'raise Exception("%s".format("{_VALID_RAISE_MSG}", variable))',
            (),
            id="more information provided string format more info in argument with variable",
        ),
        pytest.param(
            f'raise Exception(variable.format("{_VALID_RAISE_MSG}"))',
            (),
            id="more information provided string format variable",
        ),
        pytest.param(
            f'raise Exception("{_VALID_RAISE_MSG} %s".format(""))',
            (),
            id="more information provided string format more info in string",
        ),
        pytest.param(
            f'raise Exception("".join(["{_VALID_RAISE_MSG}"]))',
            (),
            id="more information provided string join more info in argument list",
        ),
        pytest.param(
            f'raise Exception(variable.join(["{_VALID_RAISE_MSG}"]))',
            (),
            id="more information provided string join variable",
        ),
        pytest.param(
            f'raise Exception("".join(["{_VALID_RAISE_MSG}", variable]))',
            (),
            id="more information provided string join more info in argument list with variable",
        ),
        pytest.param(
            f'raise Exception("".join(("{_VALID_RAISE_MSG}",)))',
            (),
            id="more information provided string join more info in argument tuple",
        ),
        pytest.param(
            f'raise Exception("".join({{"{_VALID_RAISE_MSG}"}}))',
            (),
            id="more information provided string join more info in argument set",
        ),
        pytest.param(
            f'raise Exception("".join(["{_VALID_RAISE_MSG}", "second"]))',
            (),
            id="more information provided string join more info in argument first",
        ),
        pytest.param(
            f'raise Exception("".join(["first", "{_VALID_RAISE_MSG}"]))',
            (),
            id="more information provided string join more info in argument second",
        ),
        pytest.param(
            f'raise Exception("{_VALID_RAISE_MSG}".join([""]))',
            (),
            id="more information provided string join more info in string",
        ),
        pytest.param(
            f'raise Exception("%s" % "{_VALID_RAISE_MSG}")',
            (),
            id="more information provided string %",
        ),
        pytest.param(
            f'raise Exception("%s" % ("{_VALID_RAISE_MSG}",))',
            (),
            id="more information provided string % tuple",
        ),
        pytest.param(
            f'raise Exception("%s" % ("{_VALID_RAISE_MSG}", "trailing "))',
            (),
            id="more information provided string % multiple first",
        ),
        pytest.param(
            f'raise Exception("%s" % ("leading ", "{_VALID_RAISE_MSG}"))',
            (),
            id="more information provided string % multiple second",
        ),
        pytest.param(
            f'raise Exception("%s" % ("leading ", "{_VALID_RAISE_MSG}", "trailing"))',
            (),
            id="more information provided string % multiple many",
        ),
        pytest.param(
            f'raise Exception("{_VALID_RAISE_MSG} %s" % "right")',
            (),
            id="more information provided string % in left",
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
        pytest.param(
            f'raise Exception(f"{_VALID_RAISE_MSG} {{variable}}")',
            (),
            id="more information provided f-string",
        ),
        pytest.param(
            f'raise Exception("{_VALID_RAISE_MSG}") from exc',
            (),
            id="more information provided from",
        ),
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

        assert BUILTIN_MSG in stdout
        assert proc.returncode


@pytest.mark.parametrize(
    "code, extra_args",
    [
        pytest.param(f'raise Exception("{_VALID_RAISE_MSG}")\n', "", id="default regex"),
        pytest.param(
            "raise Exception('test')\n", f"{ERROR_LINK_REGEX_ARG_NAME} test", id="custom regex"
        ),
        pytest.param(
            f"raise Exception  # noqa: {BUILTIN_CODE}\n", "", id=f"{BUILTIN_CODE} suppressed"
        ),
        pytest.param(
            (
                f'\nclass CustomError(Exception):\n    """Custom."""\n\n\nraise CustomError  '
                f"# noqa: {CUSTOM_CODE}\n"
            ),
            "",
            id=f"{CUSTOM_CODE} suppressed",
        ),
        pytest.param(
            f'test = "test"\nraise Exception(test)  # noqa: {VARIABLE_INCLUDED_CODE}\n',
            "",
            id=f"{VARIABLE_INCLUDED_CODE} suppressed",
        ),
        pytest.param(
            f'try:\n    raise Exception("{_VALID_RAISE_MSG}")\n'
            f"except Exception:\n    raise  # noqa: {RE_RAISE_CODE}\n",
            "",
            id=f"{RE_RAISE_CODE} suppressed",
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

        assert not stdout, stdout
        assert not proc.returncode
