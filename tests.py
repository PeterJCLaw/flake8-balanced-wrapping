import ast
import textwrap
import unittest
from unittest import mock

import asttokens

import flake8_balanced_wrapping


class TestFlake8BalancedWrapping(unittest.TestCase):
    def assertErrors(
        self,
        content: str,
        expected_errors: list[tuple[type[ast.AST], tuple[int, int]]],
        *,
        message: str = "Wrong error locations",
    ) -> None:
        # Normalise from triple quoted strings
        content = textwrap.dedent(content[1:])

        errors = flake8_balanced_wrapping.check(
            asttokens.ASTTokens(content, parse=True),
        )
        almost_errors = [
            (type(x.node), (x.position.line, x.position.col))
            for x in errors
        ]

        self.assertEqual(expected_errors, almost_errors, message)

    def assertError(
        self,
        content: str,
        expected_error_position: tuple[int, int],
        expected_error_type: type[ast.AST] = mock.ANY,
        *,
        message: str = "Wrong error locations",
    ) -> None:
        self.assertErrors(
            content,
            [(expected_error_type, expected_error_position)],
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
            (1, 13),
            ast.Call,
        )

    def test_misplaced_hugging_end_paren(self) -> None:
        # TODO: make this error position better
        self.assertError(
            '''
            foo('x', [
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
