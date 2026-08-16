#!/usr/bin/env python3
"""Build the ElementZero visual element table from application artifacts."""

from __future__ import annotations

import sys

from elementzero.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["visual", "build", *sys.argv[1:]]))
