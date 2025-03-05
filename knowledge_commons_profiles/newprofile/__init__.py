"""
Reads the version number from the pyproject.toml file
"""

import importlib.metadata
import pathlib
import tomllib

source_location = pathlib.Path(__file__).parent.parent
if (source_location.parent / "pyproject.toml").exists():
    with pathlib.Path.open(
        source_location.parent / "pyproject.toml", "rb"
    ) as f:
        __version__ = tomllib.load(f)["project"]["version"]
else:
    __version__ = importlib.metadata.version("package")
