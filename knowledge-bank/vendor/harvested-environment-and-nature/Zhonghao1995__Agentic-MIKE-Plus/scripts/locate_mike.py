"""Verify the MIKE+ Python toolchain is usable on this machine.

Run:  .venv\\Scripts\\python.exe scripts\\locate_mike.py
"""
import importlib.metadata as md
import sys

print("python    :", sys.version.split()[0], sys.executable)
for pkg in ("mcp", "mikeplus", "mikeio", "mikeio1d", "pandas", "matplotlib"):
    try:
        print(f"{pkg:10}:", md.version(pkg))
    except Exception as exc:
        print(f"{pkg:10}: MISSING ({exc})")

# import mikeplus -> loads the .NET bridge and locates the local MIKE+ install
try:
    import mikeplus as mp  # noqa: F401
    print("mikeplus import + .NET load: OK (MIKE+ install found)")
except Exception as exc:
    print("mikeplus import FAILED:", exc)
    print("  -> install MIKE+ and ensure a valid license; running needs it (reading does not).")
