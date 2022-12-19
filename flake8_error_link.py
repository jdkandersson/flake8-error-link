"""A linter that ensures all raised Exceptions include an error with a link to more information."""

import argparse
import ast
import builtins
import re
import tomllib
from pathlib import Path
from typing import Generator, Iterable, NamedTuple

from flake8.options.manager import OptionManager

ERROR_CODE_PREFIX = next(
    iter(
        tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["tool"]["poetry"][
            "plugins"
        ]["flake8.extension"].keys()
    )
)
BASE_MSG = (
    "exceptions should be raised with a link to more information: "
    "https://github.com/jdkandersson/flake8-error-link"
)
BUILTIN_CODE = f"{ERROR_CODE_PREFIX}001"
BUILTIN_MSG = f"{BUILTIN_CODE} builtin {BASE_MSG}#fix-eli001"
CUSTOM_CODE = f"{ERROR_CODE_PREFIX}002"
CUSTOM_MSG = f"{CUSTOM_CODE} custom {BASE_MSG}#fix-eli002"
VARIABLE_INCLUDED_CODE = f"{ERROR_CODE_PREFIX}003"
VARIABLE_INCLUDED_MSG = (
    f"{VARIABLE_INCLUDED_CODE} (detected variable in exception args) {BASE_MSG}#fix-eli003"
)
RE_RAISE_CODE = f"{ERROR_CODE_PREFIX}004"
RE_RAISE_MSG = f"{RE_RAISE_CODE} re-raised {BASE_MSG}#fix-eli004"
DEFAULT_REGEX = r"more information: (mailto\:|(news|(ht|f)tp(s?))\:\/\/){1}\S+"
BUILTIN_EXCEPTION_NAMES = frozenset(
    name
    for name, value in builtins.__dict__.items()
    if isinstance(value, type) and issubclass(value, BaseException)
)
ERROR_LINK_REGEX_ARG_NAME = "--error-link-regex"


class Problem(NamedTuple):
    """Represents a problem within the code.

    Attrs:
        lineno: The line number the problem occurred on
        col_offset: The column the problem occurred on
        msg: The message explaining the problem
    """

    lineno: int
    col_offset: int
    msg: str


class Visitor(ast.NodeVisitor):
    """Visits AST nodes and check raise calls.

    Attrs:
        problems: All the problems that were encountered.
        _more_info_regex: The regular expression used to check whether the link with more
            information was included.
    """

    problems: list[Problem]
    _more_info_regex: re.Pattern[str]

    def __init__(self, more_info_regex: str = DEFAULT_REGEX) -> None:
        """Construct.

        Args:
            more_info_regex: The value for the more_info_regex attribute.
        """
        self.problems = []
        self._more_info_regex = re.compile(rf".*{more_info_regex}.*")

    @staticmethod
    def _iter_args(nodes: list[ast.expr]) -> Iterable[ast.expr]:
        """Iterate over the args whilst flatenning any JoinedStr.

        Args:
            nodes: The nodes to iterate over.

        Yields:
            All the args including any nested args in JoinedStr.
        """
        for node in nodes:
            match type(node):
                case ast.JoinedStr:
                    assert isinstance(node, ast.JoinedStr)
                    yield node
                    yield from node.values
                case ast.NamedExpr:
                    assert isinstance(node, ast.NamedExpr)
                    yield node
                    yield node.value
                case _:
                    yield node

    def _includes_variable(self, node: ast.Call) -> bool:
        """Check whether the node includes a variable in its arguments.

        Args:
            node: The node to check.

        Returns:
            Whether the node includes a variable in its arguments.
        """
        return (
            next(
                filter(
                    lambda arg: not isinstance(arg, ast.Constant),
                    self._iter_args(node.args),
                ),
                None,
            )
            is not None
        )

    def _includes_link(self, node: ast.Call) -> bool:
        """Check whether the node includes a constant with the more information link.

        Args:
            node: The node to check.

        Returns:
            Whether the node includes a constant with the more information link.
        """
        return (
            next(
                filter(
                    None,
                    (
                        self._more_info_regex.match(arg.value)
                        # pylint seems to think self._iter_args doesn't return an iterable
                        for arg in self._iter_args(node.args)  # pylint: disable=not-an-iterable
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                    ),
                ),
                None,
            )
            is not None
        )

    def _node_problem_message(self, node: ast.Raise) -> str | None:
        """Check whether a node has a problem.

        Invalid nodes:
            raise <exception>: raise exception without any arguments, invalid
                because it does not provide a message at all.
            raise <exception>(): raise exception without any arguments, invalid
                because it does not provide a message at all.
            raise <inbuilt exception>('<constant>'+): any inbuilt exception raised with
                one or more constants that is either not a string or does not match the more
                information regular expression
            raise <any exception>(<constant>*, <variable>+, <constant>*): exception is raised where
                any one of the arguments is not a constant (e.g., a variable, function call) and
                none of the constants are a string with a link to more information
        Valid nodes:
            raise: Calling raise without exception, valid because this just re-raises an exception
                which could be any exception
            raise <exception>('<constant>'+): any exception raised with one or more constants where
                one of the constants has the more information link

        Args:
            node: The node to check.

        Returns:
            The problem message if there is a problem or None.
        """
        # Handle case where the shortcut is used for exceptions
        if isinstance(node.exc, ast.Name):
            return BUILTIN_MSG if node.exc.id in BUILTIN_EXCEPTION_NAMES else CUSTOM_MSG

        # Handle exceptions that include a call
        if isinstance(node.exc, ast.Call):
            if not self._includes_link(node.exc):
                if self._includes_variable(node.exc):
                    return VARIABLE_INCLUDED_MSG
                if hasattr(node.exc.func, "id") and node.exc.func.id in BUILTIN_EXCEPTION_NAMES:
                    return BUILTIN_MSG
                return CUSTOM_MSG

        if node.exc is None:
            return RE_RAISE_MSG

        return None

    # The function must be called the same as the name of the node
    def visit_Raise(self, node: ast.Raise) -> None:  # pylint: disable=invalid-name
        """Visit all Raise nodes.

        Args:
            node: The Raise node.
        """
        if msg := self._node_problem_message(node):
            self.problems.append(Problem(node.lineno, node.col_offset, msg))

        # Ensure recursion continues
        self.generic_visit(node)


class Plugin:
    """Ensures all raised Exceptions include an error with a link to more information."""

    name = __name__
    version = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["tool"]["poetry"][
        "version"
    ]
    _error_link_regex: str = DEFAULT_REGEX

    def __init__(self, tree: ast.AST) -> None:
        """Construct."""
        self._tree = tree

    # No coverage since this only occurs from the command line
    @staticmethod
    def add_options(option_manager: OptionManager) -> None:  # pragma: nocover
        """Add additional options to flake8.

        Args:
            option_manager: The flake8 OptionManager.
        """
        option_manager.add_option(
            ERROR_LINK_REGEX_ARG_NAME,
            default=DEFAULT_REGEX,
            parse_from_config=True,
            help=(
                "The regular expression to use to verify that an exception was raised with a link "
                f"to more information. (Default: {DEFAULT_REGEX})"
            ),
        )

    # No coverage since this only occurs from the command line
    @classmethod
    def parse_options(cls, options: argparse.Namespace) -> None:  # pragma: nocover
        """Record the value of the options.

        Args:
            options: The options passed to flake8.
        """
        cls._error_link_regex = options.error_link_regex or cls._error_link_regex

    def run(self) -> Generator[tuple[int, int, str, type["Plugin"]], None, None]:
        """Lint a file.

        Yields:
            All the issues that were found.
        """
        visitor = Visitor(self._error_link_regex)
        visitor.visit(self._tree)
        yield from (
            (problem.lineno, problem.col_offset, problem.msg, type(self))
            for problem in visitor.problems
        )
