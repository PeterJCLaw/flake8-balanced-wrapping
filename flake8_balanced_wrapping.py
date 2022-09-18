from __future__ import annotations

import ast
import sys
import tokenize
import collections
from typing import Iterator, NamedTuple


class CheckSpec(NamedTuple):
    include_own_start: bool
    include_own_end: bool


CHECK_EVERYTHING = CheckSpec(True, True)


class Visitor(ast.NodeVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.bad_nodes: dict[ast.AST, list[ast.AST]] = {}

    def _check_nodes(
        self,
        node: ast.AST,
        nodes: list[ast.AST],
        include_node_end: bool,
    ) -> None:
        by_line_no = collections.defaultdict(list)
        for x in nodes:
            if hasattr(x, 'lineno'):
                by_line_no[x.lineno].append(x)
        if include_node_end and sys.version_info >= (3, 8):
            assert node.end_lineno is not None
            by_line_no[node.end_lineno].append(node)

        counts = {x: len(y) for x, y in by_line_no.items()}
        (line_num, count), = collections.Counter(counts).most_common(1)

        # Everything should either be on one line or have its own line
        if len(counts) != 1 and count != 1:
            self.bad_nodes[node] = by_line_no[line_num]

    def _check_all(self, node: ast.AST) -> None:
        self._check_nodes(
            node,
            [*ast.iter_child_nodes(node), node],
            include_node_end=True,
        )

    visit_List = visit_Tuple = _check_all

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        nodes = [node, *node.bases, *node.keywords]
        self._check_nodes(node, nodes, include_node_end=False)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        nodes = [node, *ast.iter_child_nodes(node.args)]
        if node.returns:
            nodes.append(node.returns)
        self._check_nodes(node, nodes, include_node_end=False)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call) -> None:
        self._check_nodes(
            node,
            [node.func, *node.args, *node.keywords],
            include_node_end=True,
        )
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        self._check_nodes(
            node,
            [node, *(x for x in node.keys if x is not None)],
            include_node_end=True,
        )
        self.generic_visit(node)


def flake8_balanced_wrapping(
    tree: ast.AST,
    file_tokens: list[tokenize.TokenInfo],
) -> Iterator[tuple[int, int, str, None]]:
    visitor = Visitor()
    visitor.visit(tree)

    for node, conflicts in visitor.bad_nodes.items():
        yield (
            conflicts[0].lineno,
            conflicts[0].col_offset,
            f"BWR001 {type(node).__name__} is wrapped badly - {len(conflicts)} "
            "elements on the same line",
            None,
        )


flake8_balanced_wrapping.name = 'flake8-balanced-wrapping'  # type: ignore[attr-defined]
flake8_balanced_wrapping.version = '0.0.1'  # type: ignore[attr-defined]
