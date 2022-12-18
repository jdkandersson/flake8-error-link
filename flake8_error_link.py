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
MSG = f"{ERROR_CODE} exceptions should be raised with a link to more information"
DEFAULT_REGEX = r"more information: (mailto\:|(news|(ht|f)tp(s?))\:\/\/){1}\S+"
BUILTIN_EXCEPTION_NAMES = frozenset(
    name
    for name, value in builtins.__dict__.items()
    if isinstance(value, type) and issubclass(value, BaseException)
)
ERROR_LINK_REGEX_ARG_NAME = "--error-link-regex"


class Location(NamedTuple):
    """Represents a location within the code.

    Attrs:
        lineno: The line number the problem occurred on
        col_offset: The column the problem occurred on
    """

    lineno: int
    col_offset: int


class Visitor(ast.NodeVisitor):
    """Visits AST nodes and check raise calls.

    Attrs:
        problems: All the problems that were encountered.
        _more_info_regex: The regular expression used to check whether the link with more
            information was included.
    """

    problems: list[Location]
    _more_info_regex: re.Pattern[str]

    def __init__(self, more_info_regex: str = DEFAULT_REGEX) -> None:
        """Construct.

        Args:
            more_info_regex: The value for the more_info_regex attribute.
        """
        self.problems = []
        self._more_info_regex = re.compile(rf".*{more_info_regex}.*")

    def _node_invalid(self, node: ast.Raise) -> bool:
        """Check whether a node is valid.

        Invalid nodes:
            raise <inbuilt exception>: raise inbuilt exception without any arguments, invalid
                because it does not provide a message at all.
            raise <inbuilt exception>(): raise inbuilt exception without any arguments, invalid
                because it does not provide a message at all.
            raise <inbuilt exception>('<constant>'+): any inbuilt exception raised with
                one or more constants that is either not a string or does not match the more
                information regular expression
        Valid nodes:
            raise <custom exception>: raise custom defined exception, not invalid because the
                custom definition could include a default message that includes the link.
            raise <any exception>(*, <not constant>, *): exception is raised where any one of the
                arguments is not a constant (e.g., a variable, function call): valid because the
                variable could be message that includes a link.
            raise: Calling raise without exception, valid because this just re-raises an exception
                which could be any exception

        Args:
            node: The node to check.

        Returns:
            Whether the node is valid.
        """
        # Handle case where the shortcut is used for exceptions
        if isinstance(node.exc, ast.Name):
            return node.exc.id in BUILTIN_EXCEPTION_NAMES

        # Handle exceptions that include a call
        if isinstance(node.exc, ast.Call):
            # Handle custom exceptions
            if hasattr(node.exc.func, "id") and node.exc.func.id not in BUILTIN_EXCEPTION_NAMES:
                return False

            # Handle cases where at least one of the args is not a constant
            if next(filter(lambda arg: not isinstance(arg, ast.Constant), node.exc.args), None):
                return False

            # Handle args that are constant
            return (
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
                is None
            )

        return False

    # The function must be called the same as the name of the node
    def visit_Raise(self, node: ast.Raise) -> None:  # pylint: disable=invalid-name
        """Visit all Raise nodes.

        Args:
            node: The Raise node.
        """
        if self._node_invalid(node):
            self.problems.append(Location(node.lineno, node.col_offset))

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
            (problem.lineno, problem.col_offset, MSG, type(self)) for problem in visitor.problems
        )
