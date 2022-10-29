# flake8-balanced-wrapping

[![CircleCI](https://circleci.com/gh/PeterJCLaw/flake8-balanced-wrapping/tree/main.svg?style=svg)](https://circleci.com/gh/PeterJCLaw/flake8-balanced-wrapping/tree/main)

A flake8 plugin that helps you wrap code with visual balance.

The aim of this tool is to build up developer-assistance tooling for python
formatting. In general it will only format things when it needs to or when
directly instructed to.

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
