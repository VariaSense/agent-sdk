"""Tests for Postgres storage adapter availability."""

import importlib.util
import pytest

from agent_sdk.storage.postgres import PostgresStorage


def test_postgres_storage_requires_driver():
    spec = importlib.util.find_spec("psycopg")
    if spec is not None:
        pytest.skip("psycopg installed; integration test not configured")
    with pytest.raises(RuntimeError):
        PostgresStorage("postgresql://localhost/agent_sdk")
