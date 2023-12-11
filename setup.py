from pathlib import Path

from setuptools import setup

long_description = (Path(__file__).parent / 'README.md').read_text()

setup(
    name='flake8-balanced-wrapping',
    version='0.1.7',
    url='https://github.com/PeterJCLaw/flake8-balanced-wrapping',
    project_urls={
        'Issue tracker': 'https://github.com/PeterJCLaw/flake8-balanced-wrapping/issues',
    },
    description="A flake8 plugin that helps you wrap code with visual balance.",
    long_description=long_description,
    long_description_content_type='text/markdown',

    py_modules=['flake8_balanced_wrapping'],

    author="Peter Law",
    author_email="PeterJCLaw@gmail.com",

    license='Apache 2.0',

    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Software Development',
    ],

    entry_points={
        'flake8.extension': [
            'BWR001 = flake8_balanced_wrapping:flake8_balanced_wrapping',
        ],
    },

    install_requires=(
        'asttokens >=2.1.0, <3',
        # Don't really want to depend on tuck long-term, but for now it's an
        # easy thing to use.
        'tuck >=0.2, <0.3',
        'typing-extensions',
    ),
)
