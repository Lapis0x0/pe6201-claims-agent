"""Alias for harness.py.

This repository's real evaluation entry point is harness.py (see README.md
and CLAUDE.md). This file exists only so that `python3 run_eval.py` - the
scaffold's own entry-point name - also works out of habit. It contains no
logic of its own: it imports harness.py and calls the exact same main().

    python3 run_eval.py                 same as python3 harness.py
    python3 run_eval.py --case CLM-8894 --verbose
    python3 run_eval.py --prompt        exactly what the model is told

See harness.py for every flag.
"""
from harness import main

if __name__ == "__main__":
    raise SystemExit(main())
