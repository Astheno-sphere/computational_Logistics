"""Visual storytelling exports: SimWrapper dashboard, kepler.gl agent flows, Grasshopper pathway tree."""
import json

import yaml

import abm
import story


def test_trace_does_not_change_results_and_records_every_agent():
    a = abm.run(n=200, seed=3)
    b = abm.run(n=200, seed=3, trace_years=(2025, 2050))
    assert a["co2_2050_rel"] == b["co2_2050_rel"] and "trace" not in a
    t = b["trace"]
    assert sorted(t["years"]) == [2025, 2050] and len(t["zone"]) == 200
    assert set(t["years"][2050]["mode"]) <= {0, 1, 2}


def test_simwrapper_dashboard_references_existing_columns(tmp_path):
    pk = story.packages()
    df = story.run_pathways({k: pk[k] for k in list(pk)[:2]}, story.futures(4), n_agents=150)
    sw = story.simwrapper(df, story.futures(4), tmp_path)
    assert sw["best_package"] in pk
    for dash in tmp_path.glob("dashboard-*.yaml"):
        d = yaml.safe_load(dash.read_text())
        assert {"header", "layout"} <= set(d)
        for row in d["layout"].values():
            for card in row:
                cols = (tmp_path / card["dataset"]).read_text().splitlines()[0].split(",")
                for key in ("x", "groupBy"):
                    assert key not in card or card[key] in cols
                assert set(card.get("columns", [])) <= set(cols)


def test_agent_flows_place_arcs_near_the_towns(tmp_path):
    flows = story.agent_flows(story.packages()["no_policy"], {}, n_agents=150)
    assert len(flows) == 300 and set(flows["mode"]) <= {"car", "bus", "bike"}
    assert flows.home_lat.between(62.5, 63.3).all() and flows.home_lng.between(6.6, 8.3).all()
    html = story.kepler_html(flows, str(tmp_path / "map.html"), package="no_policy")
    page = open(html).read()
    assert "kepler.gl@%s" % story.KEPLER_VERSION in page and '"dataId": ["flows"]' in page
    data = json.loads(page.split("const DATA = ", 1)[1].split(";\n", 1)[0])
    assert len(data["rows"]) == 300 and [f["name"] for f in data["fields"]][:3] == ["agent", "year", "zone"]


def test_pathway_tree_and_polylines():
    pk = story.packages()
    df = story.run_pathways({"no_policy": pk["no_policy"]}, story.futures(3), n_agents=150)
    t = story.pathway_tree(df, "no_policy")
    assert sorted(t["tree"]) == ["{0}", "{1}", "{2}"] and len(t["success"]) == 3
    assert all(len(v) == len(t["years"]) == 26 for v in t["tree"].values())
    g = story.pathway_polylines(t["years"], list(t["tree"].values()), t["success"], index=1, sx=10, sy=100)
    assert len(g["ok"]) + len(g["fail"]) == 3 and g["focus"][0][0] == 0.0
    assert g["focus"][-1][0] == 250.0 and abs(g["focus"][0][1] - 100.0) < 1e-6


def test_hops_pathways_returns_one_branch_per_future():
    import hops_app
    from test_servers import hops_input, outputs
    body = {"pointer": "/cl/pathways", "values": [hops_input("Package", ["no_policy"]),
                                                  hops_input("Futures", [3], "System.Int32"),
                                                  hops_input("Target", [0.2], "System.Double")]}
    out = outputs(hops_app.hops.solve("/cl/pathways", json.dumps(body)))
    assert sorted(out["CO2"]) == ["{0}", "{1}", "{2}"] and len(out["Years"]["0"]) == 26
    assert len(out["Success"]["0"]) == 3
