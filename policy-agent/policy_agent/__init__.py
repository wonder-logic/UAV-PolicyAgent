from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_local_packages() -> None:
    package_dir = Path(__file__).resolve().parents[1] / ".python_packages"
    if not package_dir.exists():
        return

    package_dir_str = str(package_dir)
    if package_dir_str not in sys.path:
        sys.path.insert(0, package_dir_str)


_bootstrap_local_packages()


def create_app(*args, **kwargs):
    from policy_agent.api.routes import create_app as _create_app

    return _create_app(*args, **kwargs)


__all__ = ["create_app"]
