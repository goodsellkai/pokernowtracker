"""Desktop interface, built on Qt."""

from __future__ import annotations

__all__ = ["run"]


def run(argv=None) -> int:
    """Start the desktop application."""
    from .app import run as _run

    return _run(argv)
