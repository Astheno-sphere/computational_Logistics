import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from kb_assemble import DOMAIN_RE, NOT_DOMAIN, frontmatter


def domains(text):
    return {d for d, rx in DOMAIN_RE if rx.search(text) and not (d in NOT_DOMAIN and NOT_DOMAIN[d].search(text))}


def test_real_domain_text_is_tagged():
    assert "logistics" in domains("Solve capacitated vehicle routing with time windows")
    assert "logistics" in domains("last-mile delivery routes from a depot")
    assert "urban" in domains("Design complete streets and zoning envelopes")
    assert "architecture-aec" in domains("Check egress widths against building codes")
    assert "computational-design" in domains("Grasshopper definitions for parametric design")
    assert "geospatial" in domains("Read GeoJSON and shapefiles in QGIS")


def test_software_senses_are_not_tagged():
    assert "logistics" not in domains("Configure Istio traffic routing and load balancing")
    assert "logistics" not in domains("Fit a logistic regression with statsmodels")
    assert "logistics" not in domains("Scan dependencies for software supply chain attacks")
    assert "logistics" not in domains("Build modern data warehouses and streaming pipelines")
    assert "architecture-aec" not in domains("Microservices architect for distributed systems")
    assert "architecture-aec" not in domains("Apply the facade pattern and other design patterns")
    assert "urban" not in domains("Analyse keyword density for SEO")


def test_frontmatter_parsing():
    fm, err = frontmatter("---\nname: x\ndescription: does y\n---\nbody")
    assert err is None and fm["name"] == "x"
    assert frontmatter("no frontmatter here")[1] == "no frontmatter"
    assert frontmatter("---\nname: [unclosed\n---\n")[1].startswith("bad YAML")
