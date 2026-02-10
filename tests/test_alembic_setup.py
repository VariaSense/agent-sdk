"""Basic checks for Alembic migration setup."""

import os


def test_alembic_ini_exists():
    assert os.path.exists("alembic.ini")


def test_alembic_initial_revision_exists():
    path = os.path.join("alembic", "versions", "0001_initial_schema.py")
    assert os.path.exists(path)
