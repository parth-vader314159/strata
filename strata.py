#!/usr/bin/env python3
"""STRATA entry point.  `python strata.py <command>`  or  `make demo`."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from strata.app.cli import main

if __name__ == "__main__":
    sys.exit(main())
