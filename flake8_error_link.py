"""A linter that ensures all raised Exceptions include an error with a link to more information."""

import argparse
import ast
import builtins
import re
from itertools import chain
from typing import Generator, Iterable, List, NamedTuple, Optional, Tuple, Type

from flake8.options.manager import OptionManager

ERROR_CODE_PREFIX = "ELI"
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

    problems: List[Problem]
    _more_info_regex: re.Pattern

    def __init__(self, more_info_regex: str = DEFAULT_REGEX) -> None:
        """Construct.

        Args:
            more_info_regex: The value for the more_info_regex attribute.
        """
        self.problems = []
        self._more_info_regex = re.compile(rf".*{more_info_regex}.*")

    @staticmethod
    def _iter_arg_bin_op(node: ast.BinOp) -> Iterable[ast.expr]:
        """Flatenning binary operation.

        Args:
            node: The node to yield over.

        Yields:
            All the args including any relevant nested args.
        """
        # pylint seems to think self._iter_arg et al doesn't return an iterable
        # pylint: disable=not-an-iterable

        yield node

        # Handle add
        if isinstance(node.op, ast.Add):
            if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
                yield from Visitor._iter_arg(node.left)
            if isinstance(node.left, ast.BinOp):
                yield from Visitor._iter_arg_bin_op(node.left)
            if isinstance(node.right, ast.Constant) and isinstance(node.right.value, str):
                yield from Visitor._iter_arg(node.right)

        # Handle modulus
        if (
            isinstance(node.op, ast.Mod)
            and isinstance(node.left, ast.Constant)
            and isinstance(node.left.value, str)
        ):
            yield from Visitor._iter_arg(node.left)
            if isinstance(node.right, ast.Tuple):
                yield from Visitor._iter_args(node.right.elts)
            if isinstance(node.right, ast.Constant):
                yield from Visitor._iter_arg(node.right)

    @staticmethod
    def _iter_arg_call(node: ast.Call) -> Iterable[ast.expr]:
        """Flatenning call operation.

        Args:
            node: The node to yield over.

        Yields:
            All the args including any relevant nested args.
        """
        # pylint seems to think self._iter_arg et al doesn't return an iterable
        # pylint: disable=not-an-iterable

        yield node

        # Handle str.format, need it all to be in one expression so that mypy works
        if (
            hasattr(node, "func")  # pylint: disable=too-many-boolean-expressions
            and hasattr(node.func, "attr")
            and node.func.attr == "format"
            and hasattr(node.func, "value")
            and (
                (
                    isinstance(node.func.value, ast.Constant)
                    and isinstance(node.func.value.value, str)
                )
                or isinstance(node.func.value, ast.Name)
            )
            and hasattr(node, "args")
        ):
            yield from Visitor._iter_arg(node.func.value)
            yield from Visitor._iter_args(node.args)

        # Handle str.join, need it all to be in one expression so that mypy works
        if (
            hasattr(node, "func")  # pylint: disable=too-many-boolean-expressions
            and hasattr(node.func, "attr")
            and node.func.attr == "join"
            and hasattr(node.func, "value")
            and (
                (
                    isinstance(node.func.value, ast.Constant)
                    and isinstance(node.func.value.value, str)
                )
                or isinstance(node.func.value, ast.Name)
            )
            and hasattr(node, "args")
            and isinstance(node.args, list)
            and len(node.args) == 1
            and isinstance(node.args[0], (ast.List, ast.Set, ast.Tuple))
        ):
            yield from Visitor._iter_arg(node.func.value)
            yield from Visitor._iter_args(node.args[0].elts)

    @staticmethod
    def _iter_arg(node: ast.expr) -> Iterable[ast.expr]:
        """Flatenning certain argument types.

        Yields certain nested expressions for some kinds of expressions.

        Args:
            node: The node to yield over.

        Yields:
            All the args including any relevant nested args.
        """
        # pylint seems to think self._iter_arg et al doesn't return an iterable
        # pylint: disable=not-an-iterable

        yield node
        if isinstance(node, ast.JoinedStr):
            yield from Visitor._iter_args(node.values)
        elif isinstance(node, ast.NamedExpr):
            yield from Visitor._iter_arg(node.value)
        elif isinstance(node, ast.BinOp):
            yield from Visitor._iter_arg_bin_op(node)
        elif isinstance(node, ast.Call):
            yield from Visitor._iter_arg_call(node)

    @staticmethod
    def _iter_args(nodes: List[ast.expr]) -> Iterable[ast.expr]:
        """Iterate over the args whilst flatenning certain argument types.

        Args:
            nodes: The nodes to iterate over.

        Yields:
            All the args including any relevant nested args.
        """
        return chain.from_iterable(map(Visitor._iter_arg, nodes))

    @staticmethod
    def _includes_variable(node: ast.Call) -> bool:
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
                    Visitor._iter_args(node.args),
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
                        for arg in Visitor._iter_args(node.args)  # pylint: disable=not-an-iterable
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                    ),
                ),
                None,
            )
            is not None
        )

    def _node_problem_message(self, node: ast.Raise) -> Optional[str]:
        """Check whether a node has a problem.

        Invalid nodes:
            raise <exception>: raise exception without any arguments, invalid
                because it does not provide a message at all.
            raise <exception>(): raise exception without any arguments, invalid
                because it does not provide a message at all.
            raise <inbuilt exception>('<constant>'+): any inbuilt exception raised with
                one or more constants that is either not a string or does not match the more
                information regular expression, invalid because the more information link is not
                included.
            raise <any exception>(<constant>*, <variable>+, <constant>*): exception is raised where
                any one of the arguments is not a constant (e.g., a variable, function call) and
                none of the constants are a string with a link to more information, invalid because
                the more information link is not included.
            raise: Calling raise without exception, invalid because the more information link is
                not included.
        Valid nodes:
            raise <exception>('<constant>'+, <variable>?): any exception raised with one or more
                constants and zero or more variables where one of the constants has the more
                information link.

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

    def run(self) -> Generator[Tuple[int, int, str, Type["Plugin"]], None, None]:
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
