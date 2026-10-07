import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in ("tools", "skills/osm-network/scripts", "skills/vrp-solve/scripts", "skills/gh-datatree/scripts", "skills/opt-model/scripts"):
    sys.path.insert(0, str(ROOT / p))
GRID = str(ROOT / "grid_molde.osm")
