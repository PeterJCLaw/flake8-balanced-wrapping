import ast
import textwrap
import unittest

import flake8_balanced_wrapping


class TestFlake8BalancedWrapping(unittest.TestCase):
    def assertErrors(
        self,
        content: str,
        expected_errors: list[tuple[int, int]],
        *,
        message: str = "Wrong error locations",
    ) -> None:
        # Normalise from triple quoted strings
        content = textwrap.dedent(content[1:])

        tree = ast.parse(content)

        errors = [
            (x, y)
            for x, y, _, _ in flake8_balanced_wrapping.flake8_balanced_wrapping(tree)
        ]

        self.assertEqual(expected_errors, errors, message)

    def assertError(
        self,
        content: str,
        expected_error_position: tuple[int, int],
        *,
        message: str = "Wrong error locations",
    ) -> None:
        self.assertErrors(content, [expected_error_position], message=message)

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

    def test_hugging_wrapped_nested_call(self) -> None:
        self.assertOk('''
            call(nested(
                'inner',
                wrapped,
            ))
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
