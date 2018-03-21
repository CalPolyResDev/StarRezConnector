#!/usr/bin/env python3

import ast
import os
import sys
from setuptools import setup


class MetadataFinder(ast.NodeVisitor):
    def __init__(self):
        self.version = None
        self.title = None
        self.summary = None
        self.author = None
        self.email = None
        self.uri = None
        self.licence = None

    def visit_Assign(self, node):
        if node.targets[0].id == '__version__':
            self.version = node.value.s
        elif node.targets[0].id == '__title__':
            self.title = node.value.s
        elif node.targets[0].id == '__summary__':
            self.summary = node.value.s
        elif node.targets[0].id == '__author__':
            self.author = node.value.s
        elif node.targets[0].id == '__email__':
            self.email = node.value.s
        elif node.targets[0].id == '__uri__':
            self.uri = node.value.s
        elif node.targets[0].id == '__license__':
            self.license = node.value.s


with open(os.path.join('starrezconnector', '__init__.py')) as open_file:
    finder = MetadataFinder()
    finder.visit(ast.parse(open_file.read()))

readme = open('README.rst').read()
changes = open('CHANGES.rst').read().replace('.. :changelog:', '')

INSTALL_REQUIRES = [starrez_client]

setup(
    name=finder.title,
    version=finder.version,
    description=finder.summary,
    long_description=readme + '\n\n\n' + changes,
    author=finder.author,
    author_email=finder.email,
    url=finder.uri,
    packages=[
        finder.title,
    ],
    package_dir={finder.title: finder.title},
    include_package_data=True,
    install_requires=INSTALL_REQUIRES,
    zip_safe=False,
    license=finder.license,
    keywords="starrez starrezconnector python django",
    classifiers=[
        "Development Status :: 1 - Planning",
        "Environment :: Console",
        "Environment :: Web Plugins",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
    ],
)
