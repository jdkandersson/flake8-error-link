"""A linter that ensures all raised Exceptions include an error with a link to more information"""

import ast
import re
from pathlib import Path
from typing import Generator, NamedTuple

import tomllib
from astpretty import pprint

ERROR_CODE = next(
    iter(
        tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["tool"]["poetry"][
            "plugins"
        ]["flake8.extension"].keys()
    )
)
MSG = f"{ERROR_CODE} exceptions should be raised with a link to more information"
DEFAULT_REGEX = r"more information: (mailto\:|(news|(ht|f)tp(s?))\:\/\/){1}\S+"


class Problem(NamedTuple):
    """Represents a problem with the code.

    Attrs:
        line: The line number the problem occured on
        col: The column the problem occured on
    """

    line: int
    col: int


class Visitor(ast.NodeVisitor):
    """Visits AST nodes and check raise calls.

    Attrs:
        problems: All the problems that were encountered.
        more_info_regex: The regular expression used to check whether the link with more
            information was included.
    """

    problems: list[Problem]
    more_info_regex: re.Pattern[str]

    def __init__(self, more_info_regex: str = DEFAULT_REGEX) -> None:
        """Construct.

        Args:
            more_info_regex: The value for the more_info_regex attribute.
        """
        self.problems = []
        self.more_info_regex = re.compile(rf".*{more_info_regex}.*")

    @staticmethod
    def _node_invalid(node: ast.Raise) -> bool:
        """Check whether a node is valid.

        Invalid nodes:
            raise <inbuilt exception>: raise inbuilt exception without any arguments, invalid
                because it does not provide a message at all.
            raise <inbuilt exception>(): raise inbuilt exception without any arguments, invalid
                because it does not provide a message at all.
            raise <inbuilt exception>('<literal>'+): any inbuilt exception raised with
                one or literals that is either not a string or does not match the more information
                regular expression
        Valid nodes:
            raise <custom exception>: raise custom defined exception, not invalid because the
                custom definition could include a default message that includes the link.
            raise <any exception>(*, <variable>, *): exception is raised where any one of the
                arguments is a variable: valid because the variable could be message that includes
                a link.

        Args:
            node: The node to check.

        Returns:
            Whether the node is valid.
        """
        if not isinstance(node.exc, ast.Call):
            return True

    # The function must be called the same as the name of the node
    def visit_Raise(self, node: ast.Raise) -> None:  # pylint: disable=invalid-name
        """Visit all Raise nodes.

        Args:
            node: The Raise node.
        """
        pprint(node)
        if not isinstance(node.exc, ast.Call) or not next(
            filter(
                None,
                (
                    self.more_info_regex.match(arg.value)
                    for arg in node.exc.args
                    if isinstance(arg, ast.Constant)
                ),
            ),
            None,
        ):
            self.problems.append(Problem(node.lineno, node.col_offset))

        # Ensure recursion continues
        self.generic_visit(node)


class Plugin:
    """Ensures all raised Exceptions include an error with a link to more information"""

    name = __name__
    version = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["tool"]["poetry"][
        "version"
    ]

    def __init__(self, tree: ast.AST) -> None:
        """Construct."""
        self._tree = tree

    def run(self) -> Generator[tuple[int, int, str, type["Plugin"]], None, None]:
        """Lint a file.

        Returns:
            All the issues that were found.
        """
        visitor = Visitor()
        visitor.visit(self._tree)
        yield from ((line, col, MSG, type(self)) for line, col in visitor.problems)
