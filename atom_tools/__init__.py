"""
A cli, classes and functions for converting an atom slice to a different format
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("atom-tools")
except PackageNotFoundError:
    # Source checkout that was never installed: metadata does not exist yet.
    __version__ = "1.0.2"
