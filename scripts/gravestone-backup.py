#!/usr/bin/env python3
"""Dependency-free Gravestone notebook/map backup and new-directory recovery."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.backup import main

if __name__ == '__main__':
    raise SystemExit(main())
