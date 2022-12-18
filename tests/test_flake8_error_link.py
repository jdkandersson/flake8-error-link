"""Tests for plugin"""

import ast

import pytest

from flake8_error_link import MSG, Plugin


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
            "raise Exception", (f"1:0 {MSG}",), id="more information not provided shorthand"
        ),
        pytest.param(
            "raise ValueError()",
            (f"1:0 {MSG}",),
            id="more information not provided alternate exception",
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
            'raise Exception("more information: http://example.com")',
            (),
            id="more information provided",
        ),
        pytest.param(
            'raise ValueError("more information: http://example.com")',
            (),
            id="more information provided alternate exception",
        ),
        pytest.param(
            'raise Exception("first", "more information: http://example.com")',
            (),
            id="more information provided second args",
        ),
        pytest.param(
            'raise Exception("other text more information: http://example.com")',
            (),
            id="more information provided not at start",
        ),
        pytest.param(
            'raise Exception("more information: http://example.com other text")',
            (),
            id="more information provided not at end",
        ),
        pytest.param(
            'msg = "more information: http://example.com"\nraise Exception(msg)',
            (),
            id="more information provided using variable",
        ),
    ],
)
def test_plugin_trivial(code: str, expected_result: tuple[str, ...]):
    """
    given: code
    when: linting is run on the code
    then: the expected result is returned
    """
    assert _result(code) == expected_result
