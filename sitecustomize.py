from __future__ import annotations

import sys
from pathlib import Path


def _add_workspace_packages() -> None:
    workspace_root = Path(__file__).resolve().parent
    package_dir = workspace_root / ".python_packages"
    if not package_dir.exists():
        return

    package_dir_str = str(package_dir)
    if package_dir_str not in sys.path:
        sys.path.insert(0, package_dir_str)


_add_workspace_packages()
