"""Pathway explorer: a Rhino 8 Grasshopper Script component (Python 3).

Wire it to the Hops component pointed at http://localhost:5000/cl/pathways:
    Hops.Years   -> years     (list access, float)
    Hops.CO2     -> co2       (tree access, float; one branch per future)
    Hops.Success -> success   (list access, bool)
    Number Slider (0 .. futures-1, integer) -> index   (item access)
    sx, sy, target (item access, float); defaults 10, 100, 0.2
Outputs: ok (curves meeting the target), fail (curves missing it), focus (the future picked by the
slider), target_line, label. Colour ok green and fail red with Custom Preview; bake focus to tell its story.
The geometry logic mirrors story.pathway_polylines (tested in tests/test_story.py).
"""
import Rhino.Geometry as rg

sx = sx or 10.0          # model units per year
sy = sy or 100.0         # model units per 1.0 of CO2 relative to 2025
target = 0.2 if target is None else target
y0 = years[0]


def polyline(values):
    pts = [rg.Point3d((y - y0) * sx, v * sy, 0) for y, v in zip(years, values)]
    return rg.PolylineCurve(pts)


branches = [list(co2.Branch(p)) for p in co2.Paths]
ok = [polyline(b) for b, s in zip(branches, success) if s]
fail = [polyline(b) for b, s in zip(branches, success) if not s]
i = max(0, min(int(index or 0), len(branches) - 1))
focus = polyline(branches[i])
target_line = rg.LineCurve(rg.Point3d(0, target * sy, 0), rg.Point3d((years[-1] - y0) * sx, target * sy, 0))
label = "future %d: CO2 in %d = %.0f%% of %d (%s)" % (
    i, years[-1], 100 * branches[i][-1], y0, "meets target" if success[i] else "misses target")
