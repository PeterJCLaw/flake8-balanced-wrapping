from __future__ import annotations

import ast
import sys
import token
import tokenize
import itertools
import collections
import dataclasses
from typing import cast, Iterable, Iterator, Collection, NamedTuple
from typing_extensions import Protocol

from tuck.ast import Position, _last_token, _first_token
from asttokens import ASTTokens
from tuck.wrappers import get_node_bounds, expression_is_parenthesised


class Error(Protocol):
    @property
    def position(self) -> Position:
        ...

    def __str__(self) -> str:
        ...


@dataclasses.dataclass(frozen=True)
class UnderWrappedError:
    node: ast.AST
    conflicts: list[Position]

    @property
    def position(self) -> Position:
        return self.conflicts[0]

    def __str__(self) -> str:
        return (
            f"BWR001 {type(self.node).__name__} is wrapped badly - {len(self.conflicts)} "
            "elements on the same line"
        )


@dataclasses.dataclass(frozen=True)
class CallUnderWrappedError:
    node: ast.Call
    conflicts: list[Position]

    @property
    def position(self) -> Position:
        return self.conflicts[0]

    def __str__(self) -> str:
        return (
            "BWR002 Call is wrapped with separated positional and keyword args - "
            f"{len(self.conflicts)} elements on the same line"
        )


@dataclasses.dataclass(frozen=True)
class OverWrappedError:
    node: ast.AST
    positions: list[Position]

    @property
    def position(self) -> Position:
        return self.positions[0]

    def __str__(self) -> str:
        lines = set(x.line for x in self.positions)
        return (
            f"BWR010 {type(self.node).__name__} is wrapped unexpectedly over "
            f"{len(lines)} lines"
        )


class PositionsSummary(NamedTuple):
    is_single_line: bool
    is_single_column: bool
    most_common_line_number: int

    @property
    def is_single_line_or_column(self) -> bool:
        return self.is_single_line or self.is_single_column


def get_start_position(asttokens: ASTTokens, node: ast.AST) -> Position:
    if isinstance(node, ast.GeneratorExp):
        first_token, last_token = get_node_bounds(asttokens, node)
        if first_token.string == '(' and last_token.string == ')':
            return Position(*first_token.start)

    if (
        isinstance(node, (ast.BoolOp, ast.IfExp)) and
        expression_is_parenthesised(asttokens, node)
    ):
        open_paren = asttokens.prev_token(_first_token(node))
        return Position(*open_paren.start)

    return Position.from_node_start(node)


def get_start_positions(asttokens: ASTTokens, nodes: Iterable[ast.AST]) -> list[Position]:
    positions = []
    for node in nodes:
        start = get_start_position(asttokens, node)
        if start is not None:
            positions.append(start)
    return positions


def get_end_position(asttokens: ASTTokens, node: ast.AST) -> Position:
    if isinstance(node, ast.GeneratorExp):
        first_token, last_token = get_node_bounds(asttokens, node)
        if first_token.string == '(' and last_token.string == ')':
            return Position(*last_token.end)

    return Position(*_last_token(node).end)


def get_end_positions(asttokens: ASTTokens, nodes: Iterable[ast.AST]) -> list[Position]:
    positions = []
    for node in nodes:
        end = get_end_position(asttokens, node)
        if end is not None:
            positions.append(end)
    return positions


class Visitor(ast.NodeVisitor):
    def __init__(self, asttokens: ASTTokens) -> None:
        super().__init__()
        self.asttokens = asttokens
        self.errors: list[Error] = []

    def _get_nodes_by_line_number(
        self,
        node: ast.AST,
        reference: Position,
        nodes: Collection[ast.AST],
        include_node_end: bool,
        include_node_start: bool = True,
    ) -> dict[int, list[ast.AST]]:
        by_line_no = collections.defaultdict(list)

        if include_node_start:
            by_line_no[reference.line].append(node)

        for x in nodes:
            pos = get_start_position(self.asttokens, x)
            by_line_no[pos.line].append(x)

        if include_node_end:
            end_line, end_col = _last_token(node).end
            just_before_end_pos = Position(end_line, end_col - 1)
            end_positions = get_end_positions(self.asttokens, nodes)

            # Allow hugging, but otherwise add the containing node via its end
            # line too.
            if just_before_end_pos not in end_positions or end_line in by_line_no:
                by_line_no[end_line].append(node)

        return by_line_no

    def _summarise_lines(
        self,
        nodes_by_line_number: dict[int, list[ast.AST]],
    ) -> PositionsSummary:
        counts = {x: len(y) for x, y in nodes_by_line_number.items()}
        (line_num, max_nodes_per_line), = collections.Counter(counts).most_common(1)
        return PositionsSummary(
            is_single_line=len(counts) == 1,
            is_single_column=max_nodes_per_line == 1,
            most_common_line_number=line_num,
        )

    def _record_error(
        self,
        node: ast.AST,
        nodes: list[ast.AST],
        error_type: type[UnderWrappedError] | type[OverWrappedError] = UnderWrappedError,
    ) -> None:
        positions = get_start_positions(self.asttokens, nodes)
        assert positions
        self.errors.append(error_type(node, positions))

    def _check_under_wrapping(
        self,
        node: ast.AST,
        reference: Position,
        nodes: Collection[ast.AST],
        include_node_end: bool,
        include_node_start: bool = True,
    ) -> PositionsSummary:
        by_line_no = self._get_nodes_by_line_number(
            node,
            reference,
            nodes,
            include_node_end=include_node_end,
            include_node_start=include_node_start,
        )

        summary = self._summarise_lines(by_line_no)

        if not summary.is_single_line_or_column:
            self._record_error(node, by_line_no[summary.most_common_line_number])

        return summary

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        nodes = [*node.bases, *node.keywords]

        class_tok = self.asttokens.find_token(_first_token(node), token.NAME, 'class')
        open_paren = self.asttokens.find_token(class_tok, token.OP, '(')

        self._check_under_wrapping(
            node,
            Position(*open_paren.end),
            nodes,
            include_node_end=False,
        )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        # TODO: also check the positional/args/kwargs markers?
        # TODO: returns will have a different column if wrapped
        # TODO: check that argument defaults are on the same line as their arguments?
        nodes: list[ast.AST | None] = [
            *node.args.args,
            node.args.vararg,
            *node.args.kwonlyargs,
            node.args.kwarg,
            node.returns,
        ]

        if sys.version_info >= (3, 8):
            nodes = [*node.args.posonlyargs, *nodes]

        def_tok = self.asttokens.find_token(_first_token(node), token.NAME, 'def')
        open_paren = self.asttokens.find_token(def_tok, token.OP, '(')

        self._check_under_wrapping(
            node,
            Position(*open_paren.end),
            [x for x in nodes if x],
            include_node_end=False,
        )
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        open_paren = self.asttokens.find_token(_last_token(node.func), token.OP, '(')

        by_line_no = self._get_nodes_by_line_number(
            node,
            Position(*open_paren.end),
            [*node.args, *node.keywords],
            include_node_end=True,
        )

        has_error = False
        if len(by_line_no) > 1:
            kwargs_by_line_no = self._get_nodes_by_line_number(
                node,
                Position(*open_paren.end),
                node.keywords,
                include_node_end=True,
                include_node_start=not node.args,
            )

            kwargs_summary = self._summarise_lines(kwargs_by_line_no)

            if not kwargs_summary.is_single_column:
                has_error = True
                self._record_error(
                    node,
                    kwargs_by_line_no[kwargs_summary.most_common_line_number],
                )

            pos_args_by_line_no = self._get_nodes_by_line_number(
                node,
                Position(*open_paren.end),
                node.args,
                include_node_end=not node.keywords,
                include_node_start=True,
            )

            pos_args_summary = self._summarise_lines(pos_args_by_line_no)

            if not pos_args_summary.is_single_line_or_column:
                has_error = True
                self._record_error(
                    node,
                    pos_args_by_line_no[pos_args_summary.most_common_line_number],
                )

            if not has_error:
                # Check that overall there is no error. This allows us to emit
                # CallUnderWrappedError for cases such as:
                #
                #    call(42,
                #        kwarg='',
                #    )
                #
                # which we want to allow users to allow if they want.
                summary = self._summarise_lines(by_line_no)

                if not summary.is_single_line_or_column:
                    positions = get_start_positions(
                        self.asttokens,
                        by_line_no[summary.most_common_line_number],
                    )
                    assert positions
                    self.errors.append(CallUnderWrappedError(node, positions))

        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        by_line_no = self._get_nodes_by_line_number(
            node,
            Position.from_node_start(node),
            [x for x in node.keys if x is not None],
            include_node_end=True,
        )

        summary = self._summarise_lines(by_line_no)

        # Everything should either be on one line or have its own line, unless
        # we're hugging a single member in which case we require that that
        # member occupy the intervening lines:
        # ```
        # value = {'foo': Bar(
        #    42,
        # )}
        # ```
        def _check_single_entry_hugging() -> bool:
            if len(node.values) != 1:
                return False

            value, = node.values
            return (
                Position.from_node_start(value).line == Position.from_node_start(node).line and
                Position.from_node_end(value).line == Position.from_node_end(node).line
            )

        if not summary.is_single_line_or_column:
            if not _check_single_entry_hugging():
                self._record_error(node, by_line_no[summary.most_common_line_number])

        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        by_line_no = self._get_nodes_by_line_number(
            node,
            Position.from_node_start(node.body),
            # TODO: when we get to column validation we're going to need a way
            # to represent syntax here not just AST nodes.
            [node.body, node.test, node.orelse],
            include_node_end=False,
            include_node_start=False,
        )

        if expression_is_parenthesised(self.asttokens, node):
            # Also account for the parens
            open_paren = self.asttokens.prev_token(_first_token(node))
            close_paren = self.asttokens.next_token(_last_token(node))

            open_line = open_paren.start[0]
            close_line = close_paren.start[0]

            if open_line in by_line_no or close_line in by_line_no:
                by_line_no[open_line].append(node)
                by_line_no[close_line].append(node)

        summary = self._summarise_lines(by_line_no)

        if not summary.is_single_line_or_column:
            self._record_error(node, by_line_no[summary.most_common_line_number])

        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        # Position information in f-strings is a mess, so ASTTokens doesn't have
        # useful information, so we don't try either.
        return

    def visit_List(self, node: ast.List) -> None:
        self._check_under_wrapping(
            node,
            Position.from_node_start(node),
            node.elts,
            include_node_end=True,
        )
        self.generic_visit(node)

    def visit_Tuple(self, node: ast.Tuple) -> None:
        is_parenthesised = (
            _first_token(node).string == '(' and
            _last_token(node).string == ')'
        )

        self._check_under_wrapping(
            node,
            Position.from_node_start(node),
            node.elts,
            include_node_end=is_parenthesised,
            include_node_start=is_parenthesised,
        )

        self.generic_visit(node)

    def visit_comp(self, node: ast.ListComp | ast.SetComp) -> None:
        summary = self._check_under_wrapping(
            node,
            Position.from_node_start(node),
            [node.elt, *node.generators, *itertools.chain.from_iterable(x.ifs for x in node.generators)],
            include_node_start=False,
            include_node_end=False,
        )

        if not summary.is_single_line:
            # Ensure that the element from the comprehension is fully on its own
            # line and not overlapping with the generators.
            elt_end = Position.from_node_end(node.elt)
            generator = node.generators[0]
            generator_start = Position.from_node_start(generator)
            if elt_end.line == generator_start.line:
                self._record_error(node, [node.elt, generator])

        self.generic_visit(node)

    visit_ListComp = visit_comp
    visit_SetComp = visit_comp

    def visit_DictComp(self, node: ast.DictComp) -> None:
        summary = self._check_under_wrapping(
            node,
            Position.from_node_start(node),
            [node.key, *node.generators, *itertools.chain.from_iterable(x.ifs for x in node.generators)],
            include_node_start=False,
            include_node_end=False,
        )

        if not summary.is_single_line:
            # Ensure that the `key: value` from the comprehension is fully on
            # its own line and not overlapping with the generators.
            value_end = Position.from_node_end(node.value)
            generator = node.generators[0]
            generator_start = Position.from_node_start(generator)
            if value_end.line == generator_start.line:
                self._record_error(node, [node.value, generator])

        self.generic_visit(node)

    def _check_over_wrapping(
        self,
        node: ast.AST,
        reference: Position,
        nodes: Collection[ast.AST],
        include_node_end: bool,
        include_node_start: bool = True,
    ) -> None:
        by_line_no = self._get_nodes_by_line_number(
            node,
            reference,
            nodes,
            include_node_end=include_node_end,
            include_node_start=include_node_start,
        )

        if len(by_line_no) != 1:
            self._record_error(
                node,
                list(itertools.chain.from_iterable(by_line_no.values())),
                error_type=OverWrappedError,
            )

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        start_pos = Position.from_node_start(node)

        by_line_no = self._get_nodes_by_line_number(
            node,
            start_pos,
            node.values,
            include_node_end=False,
            include_node_start=False,
        )

        summary = self._summarise_lines(by_line_no)

        if not summary.is_single_line_or_column:
            self._record_error(
                node,
                [node, *node.values],
                error_type=OverWrappedError,
            )

        elif expression_is_parenthesised(self.asttokens, node):
            # Also account for the parens
            open_paren = self.asttokens.prev_token(_first_token(node))
            close_paren = self.asttokens.next_token(_last_token(node))

            open_line = open_paren.start[0]
            close_line = close_paren.start[0]

            if (
                open_line != close_line and
                (open_line in by_line_no or close_line in by_line_no)
            ):
                by_line_no[open_line].append(node)
                by_line_no[close_line].append(node)

                self._record_error(
                    node,
                    [node, *node.values],
                    error_type=OverWrappedError,
                )

        self.generic_visit(node)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        operand_start = get_start_position(self.asttokens, node.operand)

        if node.lineno != operand_start.line:
            self._record_error(
                node,
                [node, node.operand],
                error_type=OverWrappedError,
            )

        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self._check_over_wrapping(
            node,
            Position.from_node_start(node),
            [node.target, node.iter],
            include_node_end=False,
            include_node_start=False,
        )
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        self._check_over_wrapping(
            node,
            Position.from_node_start(node.left),
            [node.left, *node.comparators],
            include_node_end=False,
            include_node_start=True,
        )
        self.generic_visit(node)


def check(asttokens: ASTTokens) -> list[Error]:
    visitor = Visitor(asttokens)
    assert asttokens.tree  # placate mypy
    visitor.visit(asttokens.tree)
    return visitor.errors


def flake8_balanced_wrapping(
    tree: ast.AST,
    file_tokens: list[tokenize.TokenInfo],
    lines: list[str],
) -> Iterator[tuple[int, int, str, None]]:
    asttokens = ASTTokens(''.join(lines), tree=cast(ast.Module, tree), tokens=file_tokens)
    for error in check(asttokens):
        yield (
            error.position.line,
            error.position.col,
            str(error),
            None,
        )


flake8_balanced_wrapping.name = 'flake8-balanced-wrapping'  # type: ignore[attr-defined]
flake8_balanced_wrapping.version = '0.0.1'  # type: ignore[attr-defined]
