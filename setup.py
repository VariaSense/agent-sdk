#!/usr/bin/env python
"""Setup script for agent-sdk."""

from setuptools import setup, find_packages

# find_packages will discover agent_sdk and all subpackages
setup(
    packages=find_packages(exclude=["tests*", "documents*", "vector_store*", "htmlcov*", ".bin*"]),
)
