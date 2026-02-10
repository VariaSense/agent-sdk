"""Run Alembic migrations for agent-sdk."""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    dsn = os.getenv("AGENT_SDK_ALEMBIC_DSN") or os.getenv("AGENT_SDK_POSTGRES_DSN")
    if dsn:
        os.environ["AGENT_SDK_ALEMBIC_DSN"] = dsn
    return subprocess.call([sys.executable, "-m", "alembic", "upgrade", "head"])


if __name__ == "__main__":
    raise SystemExit(main())
