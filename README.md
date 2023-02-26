# flake8-balanced-wrapping

[![CircleCI](https://circleci.com/gh/PeterJCLaw/flake8-balanced-wrapping/tree/main.svg?style=svg)](https://circleci.com/gh/PeterJCLaw/flake8-balanced-wrapping/tree/main)

A flake8 plugin that helps you wrap code with visual balance.

The aim of this linter is to complement the use of developer-assistance python
formatting tools, i.e: those where the developer remains in control of _when_ to
format code a particular way, while still enforcing a consistent style of _how_
the code is formatted.

## Style

The style which this linter checks for is one which aims for clarity and visual
balance while reducing diff noise, without concern for vertical space. This is
similar to the [`tuck`](https://pypi.org/project/tuck/) wrapping tool.

As much as possible this linter will not duplicate checks provided by other
plugins where they are are in agreement.

**Example**: Function definitions


``` python
# Unwrapped
def foo(bar: str, quox: int = 0) -> float:
    return 4.2

# Wrapped
def foo(
    bar: str,
    quox: int = 0,
) -> float:
    return 4.2
```

**Example**: List comprehension

``` python
# Unwrapped
[x for x in 'aBcD' if x.isupper()]

# Wrapped
[
    x
    for x in 'aBcD'
    if x.isupper()
]
```
