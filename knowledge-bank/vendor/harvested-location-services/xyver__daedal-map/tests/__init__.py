from __future__ import annotations

import sys
from pathlib import Path


# Keep direct unittest runs stable from the shared workspace root. The tests
# import `mapmover.*`, so the public app root must be importable even when the
# caller does not set PYTHONPATH manually.
PUBLIC_ROOT = Path(__file__).resolve().parents[1]
public_root_str = str(PUBLIC_ROOT)
if public_root_str not in sys.path:
    sys.path.insert(0, public_root_str)
