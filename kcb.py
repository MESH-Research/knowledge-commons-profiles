# /// script
# requires-python = ">=3.12"
# dependencies = ["click>=8.1"]
# ///
"""Entry point: ``uv run kcb.py --help``."""

from kcbuild.cli import main

if __name__ == "__main__":
    main()
