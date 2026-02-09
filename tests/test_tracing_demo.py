"""Tests for tracing demo presence."""

from pathlib import Path


def test_tracing_demo_files_exist():
    assert Path("examples/tracing_demo/app.py").exists()
    assert Path("examples/tracing_demo/README.md").exists()
