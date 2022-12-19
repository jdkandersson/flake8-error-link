"""A linter that ensures all raised Exceptions include an error with a link to more information."""

import argparse
import ast
import builtins
import re
import tomllib
from pathlib import Path
from typing import Generator, NamedTuple

from flake8.options.manager import OptionManager

ERROR_CODE = next(
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
BUILTIN_MSG = f"{ERROR_CODE}001 builtin {BASE_MSG}"
CUSTOM_MSG = f"{ERROR_CODE}002 custom {BASE_MSG}"
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
        Valid nodes:
            raise <any exception>(*, <not constant>, *): exception is raised where any one of the
                arguments is not a constant (e.g., a variable, function call): valid because the
                variable could be message that includes a link.
            raise: Calling raise without exception, valid because this just re-raises an exception
                which could be any exception

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
            # Handle cases where at least one of the args is not a constant
            if next(filter(lambda arg: not isinstance(arg, ast.Constant), node.exc.args), None):
                return None

            # Handle args that are constant
            includes_link = (
                next(
                    filter(
                        None,
                        (
                            self._more_info_regex.match(arg.value)
                            for arg in node.exc.args
                            if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                        ),
                    ),
                    None,
                )
                is not None
            )
            if not includes_link:
                return BUILTIN_MSG if node.exc.func.id in BUILTIN_EXCEPTION_NAMES else CUSTOM_MSG

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
