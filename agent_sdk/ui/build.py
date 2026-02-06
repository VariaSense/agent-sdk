"""
Build step for the dev console UI.

Copies index.html to dist/index.html.
"""

from __future__ import annotations

import os
import shutil


def build_ui() -> str:
    base_dir = os.path.dirname(__file__)
    src = os.path.join(base_dir, "index.html")
    dist_dir = os.path.join(base_dir, "dist")
    dist = os.path.join(dist_dir, "index.html")

    os.makedirs(dist_dir, exist_ok=True)
    shutil.copyfile(src, dist)
    return dist


if __name__ == "__main__":
    path = build_ui()
    print(path)
