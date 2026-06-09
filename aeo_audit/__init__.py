"""AEO Audit CLI - Agent/Engine Optimization readiness scanner."""

from importlib.metadata import PackageNotFoundError, version

try:
    # Single source of truth: the installed distribution version (pyproject).
    __version__ = version("aeo-audit")
except PackageNotFoundError:  # pragma: no cover - running from a source tree
    __version__ = "0.0.0+dev"
