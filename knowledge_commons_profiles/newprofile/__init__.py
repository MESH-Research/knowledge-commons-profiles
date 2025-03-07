"""
Reads the version number from the pyproject.toml file
"""

import tomllib
from pathlib import Path

source_location = Path(__file__).parent.parent
if (source_location.parent / "pyproject.toml").exists():
    with Path.open(source_location.parent / "pyproject.toml", "rb") as f:
        __version__ = tomllib.load(f)["project"]["version"]
else:
    __version__ = "Unknown build"
