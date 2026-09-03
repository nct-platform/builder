#!/usr/bin/env python3
"""mrjun — CLI toolkit for editing UNPACKED .mrjun exports (stdlib only, py3.9+).

Thin entrypoint. All logic lives in the mrjunkit package next to this file.

    python3 mrjun.py <command> ... --project <dir>
    python3 mrjun.py --help
"""

import os
import sys

# Make the sibling package importable regardless of cwd.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mrjunkit.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
