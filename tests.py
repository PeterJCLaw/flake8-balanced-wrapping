from __future__ import annotations

import ast
import textwrap
import unittest
from unittest import mock

import asttokens

import flake8_balanced_wrapping
from flake8_balanced_wrapping import Error, OverWrappedError, UnderWrappedError


class TestFlake8BalancedWrapping(unittest.TestCase):
    def assertErrors(
        self,
        content: str,
        expected_errors: list[tuple[type[Error], type[ast.AST], tuple[int, int]]],
        *,
        message: str = "Wrong error locations",
    ) -> None:
        # Normalise from triple quoted strings
        content = textwrap.dedent(content[1:])

        errors = flake8_balanced_wrapping.check(
            asttokens.ASTTokens(content, parse=True),
        )
        almost_errors = [
            (type(x), type(x.node), (x.position.line, x.position.col))
            for x in errors
        ]

        self.assertEqual(expected_errors, almost_errors, message)

    def assertError(
        self,
        content: str,
        expected_error_position: tuple[int, int],
        expected_error_node: type[ast.AST] = mock.ANY,
        expected_error_type: type[Error] = UnderWrappedError,
        *,
        message: str = "Wrong error locations",
    ) -> None:
        self.assertErrors(
            content,
            [(expected_error_type, expected_error_node, expected_error_position)],
            message=message,
        )

    def assertOk(
        self,
        content: str,
        *,
        message: str = "Unexpected error locations",
    ) -> None:
        self.assertErrors(content, [], message=message)

    def test_one_line_call(self) -> None:
        self.assertOk('''
            call('on', one, 'line')
        ''')

    def test_one_line_nested_call(self) -> None:
        self.assertOk('''
            call(nested('on', one, 'line'))
        ''')

    def test_wrapped_nested_call(self) -> None:
        self.assertOk('''
            call(
                nested('on', one, 'line'),
            )
        ''')

    def test_wrapped_nested_chained_call(self) -> None:
        self.assertOk('''
            call(
                Something.objects.filter(
                    property=True,
                ).values('a', 'b'),
            )
        ''')

    def test_hugging_wrapped_nested_call(self) -> None:
        self.assertOk('''
            call(nested(
                'inner',
                wrapped,
            ))
        ''')

    def test_call_arg_is_same_line_generator(self) -> None:
        self.assertOk('''
            call(x for x in 'abcd')
        ''')

    def test_call_arg_is_one_line_generator(self) -> None:
        self.assertOk('''
            call(
                x for x in 'abcd'
            )
        ''')

    def test_call_arg_is_two_line_generator(self) -> None:
        self.assertOk('''
            call(
                x
                for x in 'abcd'
            )
        ''')

    def test_call_arg_is_generator_with_call(self) -> None:
        self.assertOk('''
            call(
                nested(
                    'inner',
                    wrapped,
                )
                for x in 'abcd'
            )
        ''')

    def test_call_kwargs_wrapped(self) -> None:
        self.assertOk('''
            Item(42, 'slug',
                display="Thing",
                visible=False,
            )
        ''')

    def test_call_kwargs_badly_wrapped(self) -> None:
        self.assertError(
            '''
            Item(42, 'slug',
                display="Thing", visible=False,
            )
            ''',
            expected_error_position=(2, 4),
            expected_error_node=ast.Call,
        )

    def test_call_kwargs_badly_wrapped_with_misplaced_end_paren(self) -> None:
        self.assertError(
            '''
            Item(42, 'slug',
                display="Thing", visible=False)
            ''',
            expected_error_position=(2, 4),
            expected_error_node=ast.Call,
        )

    def test_one_line_function_def(self) -> None:
        self.assertOk('''
            def func(on, one, *, line):
                pass
        ''')

    def test_three_line_function_def(self) -> None:
        self.assertError(
            '''
            def func(
                on, three, *, lines
            ):
                pass
            ''',
            (2, 4),
        )

    def test_decorated_function_def(self) -> None:
        self.assertOk('''
            @foo
            def func(on, one, *, line):
                pass
        ''')

    def test_decorated_parens_function_def(self) -> None:
        self.assertOk('''
            @foo()
            def func(on, one, *, line):
                pass
        ''')

    def test_decorated_parens_class_def(self) -> None:
        self.assertOk('''
            @foo()
            class A:
                pass
        ''')

    def test_one_line_function_def_with_defaults(self) -> None:
        self.assertOk('''
            def func(on, one='default', *, line, kwarg='default'):
                pass
        ''')

    def test_multi_line_function_def_with_defaults(self) -> None:
        self.assertOk('''
            def func(
                on,
                many='default',
                *,
                lines,
                kwarg='default',
            ):
                pass
        ''')

    def test_pep8_style_call(self) -> None:
        self.assertError(
            '''
            connection = wrap_socket(connection,
                            server_hostname=self.host,
                            session=self.sock.session)
            ''',
            (3, 16),
            ast.Call,
        )

    def test_pep8_style_call_kwargs_only(self) -> None:
        self.assertError(
            '''
            connection = wrap_socket(conn=connection,
                            server_hostname=self.host,
                            session=self.sock.session)
            ''',
            (1, 13),
            ast.Call,
        )

    def test_pep8_style_call_positional_only(self) -> None:
        self.assertError(
            '''
            connection = wrap_socket(connection,
                            self.host,
                            self.sock.session)
            ''',
            (1, 13),
            ast.Call,
        )

    def test_dict_hugging_call(self) -> None:
        self.assertOk('''
            value = {'foo': Bar(
                42,
                'abcd',
            )}
        ''')

    def test_call_hugging_dict_literal(self) -> None:
        self.assertOk('''
            value = SomeTypedDict({'foo': Bar(
                42,
                'abcd',
            )})
        ''')

    def test_misplaced_hugging_end_paren_positional(self) -> None:
        # TODO: make this error position better
        self.assertError(
            '''
            foo([
                Bar,
            ],
            )
            ''',
            (1, 0),
            ast.Call,
        )

    def test_misplaced_hugging_end_paren_kwarg(self) -> None:
        # TODO: make this error position better
        self.assertError(
            '''
            foo(x=[
                Bar,
            ],
            )
            ''',
            (1, 0),
            ast.Call,
        )

    def test_imbalanced_tuple_wrap(self) -> None:
        # TODO: make this error position better
        self.assertError(
            '''
            ('FOO',
            Bar(
                ...,
            ))
            ''',
            (1, 0),
            ast.Tuple,
        )

    def test_imbalanced_tuple_wrap_within_list(self) -> None:
        self.assertError(
            '''
            [('FOO',
            Bar(
                ...,
            ))]
            ''',
            (1, 1),
            ast.Tuple,
        )

    def test_implicit_tuple_boundary_subscript(self) -> None:
        self.assertOk('''
            SomeAlias = Union[
                str,
                bool,
            ]
        ''')

    def test_if_expression_bad_wrap_body(self) -> None:
        # TODO: make this error position better
        self.assertError(
            '''
            x = ('foo'
                if False
                else 'bar'
            )
            ''',
            (1, 5),
            ast.IfExp,
        )

    def test_if_expression_bad_wrap_else(self) -> None:
        # TODO: make this error position better
        self.assertError(
            '''
            x = (
                'foo'
                if False else 'bar'
            )
            ''',
            (3, 7),
            ast.IfExp,
        )

    def test_if_expression_ok_one_line(self) -> None:
        self.assertOk('''
            x = 'foo' if False else 'bar'
        ''')

    def test_if_expression_ok_one_line_parens(self) -> None:
        self.assertOk('''
            x = ('foo' if False else 'bar')
        ''')

    def test_if_expression_ok_wrapped_parens(self) -> None:
        self.assertOk('''
            x = (
                'foo'
                if False
                else 'bar'
            )
        ''')

    def test_if_expression_ok_wrapped_implicit_boundary(self) -> None:
        self.assertOk('''
            x = {
                'y':
                    'foo'
                    if False
                    else 'bar'
            }
        ''')

    def test_comprehension_ok(self) -> None:
        self.assertOk('''
            ok = [
                x
                for x in valid_call(
                    foo='Bar',
                )
            ]
        ''')

    def test_comprehension_bad_wrap(self) -> None:
        self.assertError(
            '''
            bad = [
                x
                for x
                in "SOMETHING"
            ]
            ''',
            (3, 8),
            ast.comprehension,
            OverWrappedError,
        )

    def test_compare_ok(self) -> None:
        self.assertOk('''
            ok = 'foo' in 'foobar'
        ''')

    def test_compare_bad_wrap(self) -> None:
        self.assertError(
            '''
            ok = ('foo' in
                'foobar')
            ''',
            (1, 6),
            ast.Compare,
            OverWrappedError,
        )
