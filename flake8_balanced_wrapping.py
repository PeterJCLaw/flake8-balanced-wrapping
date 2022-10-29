from __future__ import annotations

import ast
import sys
import token
import tokenize
import collections
import dataclasses
from typing import cast, Iterator

from tuck.ast import Position, _last_token, _first_token
from asttokens import ASTTokens


@dataclasses.dataclass(frozen=True)
class Error:
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


def get_start_position(node: ast.AST) -> Position:
    return Position.from_node_start(node)


class Visitor(ast.NodeVisitor):
    def __init__(self, asttokens: ASTTokens) -> None:
        super().__init__()
        self.asttokens = asttokens
        self.bad_nodes: dict[ast.AST, list[Position]] = {}

    def _check_nodes(
        self,
        node: ast.AST,
        reference: Position,
        nodes: list[ast.AST],
        include_node_end: bool,
    ) -> None:
        by_line_no = collections.defaultdict(list)
        by_line_no[reference.line].append(node)
        for x in nodes:
            pos = get_start_position(x)
            by_line_no[pos.line].append(x)
        if include_node_end and sys.version_info >= (3, 8):
            assert node.end_lineno is not None
            assert node.end_col_offset is not None

            # Allow hugging
            if not any(
                x.end_lineno == node.end_lineno and
                x.end_col_offset == node.end_col_offset - 1
                for x in nodes
                if hasattr(x, 'end_lineno')
            ):
                by_line_no[node.end_lineno].append(node)

        counts = {x: len(y) for x, y in by_line_no.items()}
        (line_num, count), = collections.Counter(counts).most_common(1)

        # Everything should either be on one line or have its own line
        if len(counts) != 1 and count != 1:
            maybe_positions = [get_start_position(x) for x in by_line_no[line_num]]
            positions = [x for x in maybe_positions if x is not None]
            assert positions
            self.bad_nodes[node] = positions

    def _check_all(self, node: ast.AST) -> None:
        self._check_nodes(
            node,
            Position.from_node_start(node),
            [x for x in ast.iter_child_nodes(node) if hasattr(x, 'lineno')],
            include_node_end=True,
        )
        self.generic_visit(node)

    visit_List = visit_Tuple = _check_all

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        nodes = [*node.bases, *node.keywords]

        open_paren = self.asttokens.find_token(_first_token(node), token.OP, '(')

        self._check_nodes(
            node,
            Position(*open_paren.end),
            nodes,
            include_node_end=False,
        )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        # TODO: also check the positional/args/kwargs markers?
        # TODO: returns will have a different column if wrapped
        # TODO: check that argument defatuls are on the same line as their arguments?
        nodes: list[ast.AST | None] = [
            *node.args.posonlyargs,
            *node.args.args,
            node.args.vararg,
            *node.args.kwonlyargs,
            node.args.kwarg,
            node.returns,
        ]

        open_paren = self.asttokens.find_token(_first_token(node), token.OP, '(')

        self._check_nodes(
            node,
            Position(*open_paren.end),
            [x for x in nodes if x],
            include_node_end=False,
        )
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        open_paren = self.asttokens.find_token(_last_token(node.func), token.OP, '(')
        self._check_nodes(
            node,
            Position(*open_paren.end),
            [*node.args, *node.keywords],
            include_node_end=True,
        )
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        self._check_nodes(
            node,
            Position.from_node_start(node),
            [x for x in node.keys if x is not None],
            include_node_end=True,
        )
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        # Position information in f-strings is a mess, so ASTTokens doesn't have
        # useful information, so we don't try either.
        return


def check(asttokens: ASTTokens) -> list[Error]:
    visitor = Visitor(asttokens)
    assert asttokens.tree  # placate mypy
    visitor.visit(asttokens.tree)

    return [
        Error(node, conflicts)
        for node, conflicts in visitor.bad_nodes.items()
    ]


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
