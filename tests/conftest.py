import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in ("tools", "skills/osm-network/scripts", "skills/vrp-solve/scripts", "skills/gh-datatree/scripts", "skills/opt-model/scripts", "servers", "skills/dcm-estimate/scripts", "skills/abm-transport/scripts", "skills/dmdu-explore/scripts", "skills/viz-story/scripts", "skills/visual-narrative/scripts"):
    sys.path.insert(0, str(ROOT / p))
GRID = str(ROOT / "data" / "synthetic" / "grid_molde.osm")
