"""Every path a caller can name has to be checked, and not by anyone remembering.

Path containment lived in two places that could disagree. The dedicated MCP tools
call `workspace.guard` on each argument by hand; `run_operation` and
`execute_plan` rely on the plan validator, which reads a per-binding tuple of
argument names. On 2026-08-29 those two disagreed on `merge_layers`: its
`input_paths` is a list, so it was invisible to the validator twice over — not in
`input_args`, and not a `str` — and a call the dedicated tool refused was executed
by `run_operation`, reading a file from outside `MAPSMITH_WORKSPACE` and writing
it inside, where the next `describe_dataset` hands it to the model.
`validate_plan` reported that step as `valid: true` with no errors.

The fix was one field. This file is why it does not come back: the failure was not
the missing tuple entry, it was that a hand-maintained enumeration of a growing
set is wrong somewhere between one addition and the next, and only a mechanical
check notices. Same shape as `test_no_new_driver_escapes_the_policy`.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mapsmith import catalog
from mapsmith.plans import models, validator
from mapsmith.plans.registry import BINDINGS


def _declared_paths(entry: dict) -> list[str]:
    """Parameter names that carry a path, by the only signal the catalog gives.

    Naming, because the parameter vocabulary (`str`, `float`, `list[str]`, …)
    cannot say "this is a dataset path". That is itself the weakness the issue in
    the tracker proposes to fix; until then the convention is load-bearing and
    `test_a_path_parameter_is_recognisable_by_its_name` keeps it honest.
    """
    names = []
    for parameter in entry.get("parameters", []):
        name = parameter["name"] if isinstance(parameter, dict) else str(parameter)
        if "path" in name:
            names.append(name)
    return names


@pytest.mark.parametrize(
    "entry",
    [op for op in catalog.OPERATIONS if op["name"] in BINDINGS],
    ids=lambda op: op["name"],
)
def test_every_path_parameter_is_covered_by_its_binding(entry):
    """A path the validator does not know about is a path nobody checks."""
    binding = BINDINGS[entry["name"]]
    covered = set(binding.input_args) | set(binding.list_input_args)
    if binding.output_arg:
        covered.add(binding.output_arg)

    uncovered = [name for name in _declared_paths(entry) if name not in covered]
    assert not uncovered, (
        f"{entry['name']} declares {uncovered} in the catalog and its binding does "
        "not name them, so `run_operation` and `execute_plan` will not check them "
        "for workspace containment or for non-local forms. Add them to "
        "`input_args` (one path) or `list_input_args` (a list of paths)."
    )


def test_a_path_parameter_is_recognisable_by_its_name():
    """The convention the check above rests on, asserted rather than assumed.

    If an operation ever takes a dataset path under a name without "path" in it,
    the coverage test above goes quiet and stays green while the hole reopens. So
    the arguments the bindings DO name are required to follow the convention: the
    day one does not, this fails and the coverage rule gets rewritten rather than
    silently weakened.
    """
    offenders = []
    for name, binding in BINDINGS.items():
        for arg in (*binding.input_args, *binding.list_input_args):
            if "path" not in arg:
                offenders.append(f"{name}.{arg}")
    assert not offenders, (
        f"these binding arguments carry paths without saying so in their name: "
        f"{offenders}. The containment coverage test finds path parameters by "
        "name, so either rename them or replace that rule with a declared type."
    )


@pytest.mark.parametrize("operation", sorted(BINDINGS))
def test_no_operation_reads_outside_the_workspace_through_the_generic_path(
    operation, monkeypatch
):
    """The end-to-end claim, per operation: what the dedicated tool refuses, the
    generic path refuses too.

    Built as a plan and validated rather than executed — execution needs real
    fixtures per operation, while containment is decided before anything runs and
    that is the property under test. Every path argument is pointed at a file
    outside the workspace; the validator must object to each of them.
    """
    binding = BINDINGS[operation]
    inputs = [*binding.input_args, *binding.list_input_args]
    if not inputs:
        pytest.skip("no path inputs to point outside")

    with tempfile.TemporaryDirectory() as inside, tempfile.TemporaryDirectory() as outside:
        monkeypatch.setenv("MAPSMITH_WORKSPACE", inside)
        stranger = str(Path(outside) / "stranger.parquet")

        arguments: dict[str, object] = {}
        for arg in binding.input_args:
            arguments[arg] = stranger
        for arg in binding.list_input_args:
            arguments[arg] = [stranger, stranger]
        if binding.output_arg:
            arguments[binding.output_arg] = str(Path(inside) / "out.parquet")

        report = validator.validate(
            models.Plan.model_validate(
                {
                    "goal": "containment",
                    "steps": [
                        {"id": "s", "operation": operation, "arguments": arguments}
                    ],
                }
            )
        )
        codes = {issue.code for issue in report.errors}
        assert "PATH_OUTSIDE_WORKSPACE" in codes, (
            f"{operation}: every path argument points outside MAPSMITH_WORKSPACE and "
            f"the validator raised {sorted(codes) or 'nothing'}. The dedicated tool "
            "refuses this; the generic path must too."
        )


@pytest.mark.parametrize("operation", sorted(BINDINGS))
def test_no_operation_reaches_the_network_through_the_generic_path(
    operation, monkeypatch
):
    """Same, for the non-local forms. `/vsicurl/` is a VSI handler rather than a
    driver, so `gdal_policy` cannot stop it — the textual check is the defence,
    and it has to run on every path argument including the ones in lists."""
    binding = BINDINGS[operation]
    inputs = [*binding.input_args, *binding.list_input_args]
    if not inputs:
        pytest.skip("no path inputs to point at the network")

    with tempfile.TemporaryDirectory() as inside:
        monkeypatch.setenv("MAPSMITH_WORKSPACE", inside)
        remote = "/vsicurl/https://example.invalid/remote.geojson"

        arguments: dict[str, object] = {}
        for arg in binding.input_args:
            arguments[arg] = remote
        for arg in binding.list_input_args:
            arguments[arg] = [remote, remote]
        if binding.output_arg:
            arguments[binding.output_arg] = str(Path(inside) / "out.parquet")

        report = validator.validate(
            models.Plan.model_validate(
                {
                    "goal": "egress",
                    "steps": [
                        {"id": "s", "operation": operation, "arguments": arguments}
                    ],
                }
            )
        )
        codes = {issue.code for issue in report.errors}
        assert codes & {"NON_LOCAL_PATH", "PATH_OUTSIDE_WORKSPACE"}, (
            f"{operation}: a /vsicurl/ path passed validation with "
            f"{sorted(codes) or 'no errors'}. SECURITY.md states that any way to "
            "make GDAL reach the network from a workspace-confined server is a "
            "vulnerability."
        )


def test_the_wire_contract_refuses_a_list_of_non_strings():
    """Where the element type of `list[str]` is actually enforced.

    An audit read `PARAM_TYPES["list[str]"] = (list,)` and concluded that
    `[123, {...}]` reaches the engine. It does not: `models.ArgValue` refuses it
    while the Plan is being parsed, and `Plan` is the only way into the validator
    and into `run_operation`. So the guarantee is real and lives one layer up —
    which is worth a test rather than a second implementation, because a check
    that can never fire is a comment claiming a protection that is not there.

    It matters for containment and not only for tidiness: every path check below
    skips values that are not `str`, so a non-string element in a list of paths
    would be a path nobody examined.
    """
    import pydantic
    import pytest as _pytest

    with _pytest.raises(pydantic.ValidationError):
        models.Plan.model_validate(
            {
                "goal": "element types",
                "steps": [
                    {
                        "id": "s",
                        "operation": "merge_layers",
                        "arguments": {
                            "input_paths": [123, {"a": 1}, "fine.parquet"],
                            "output_path": "out.parquet",
                        },
                    }
                ],
            }
        )


def test_the_catalog_search_makes_no_request_under_a_workspace(monkeypatch, tmp_path):
    """`SECURITY.md` promises no network egress in sandbox mode, in writing, and
    calls any exception a vulnerability. 0.3.0 made an engine that fetches a
    model the default for `list_operations`, which is the first tool an agent
    calls. This pins the resolution: with a workspace set and a cold cache, the
    fetch does not happen and the answer says which engine gave it.
    """
    from mapsmith import catalog, retrieval

    monkeypatch.setenv("MAPSMITH_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("HF_HOME", str(tmp_path / "cold-cache"))
    retrieval._model.cache_clear()

    reached = []

    def refuse(*args, **kwargs):
        if not kwargs.get("local_files_only"):
            reached.append(kwargs)
        raise OSError("no cached snapshot")

    monkeypatch.setattr(retrieval, "_require", lambda: (refuse, object))

    answer = catalog.search(
        "steepness of the terrain", limit=3, input_kind="raster",
        produces="dataset:raster",
    )
    assert not reached, (
        "the model download was attempted without `local_files_only` while a "
        "workspace was set, which is the egress SECURITY.md defines as a "
        "vulnerability"
    )
    assert answer, "the search returned nothing instead of falling back"
    assert answer[0].get("engine") == "lexical", (
        "the fallback ran but the answer does not say which engine produced it"
    )
    retrieval._model.cache_clear()


@pytest.mark.parametrize(
    "entry",
    [op for op in catalog.OPERATIONS if op["name"] in BINDINGS],
    ids=lambda op: op["name"],
)
def test_the_declared_arity_matches_the_binding(entry):
    """`dataset_inputs` is a filter input, so a wrong one hides an operation.

    It is declared in the catalogue rather than derived from the registry
    because the catalogue is the reachability layer and has to be readable
    without importing the engine bindings. That makes it a second copy of a
    fact, and a second copy of a fact drifts — so it is checked here against the
    thing it describes, the same way `produces` is checked against what the
    operation actually writes.

    The failure it prevents is silent in the worst way: an operation that takes
    two datasets but declares one is invisible to every caller who correctly
    says they are holding two, and no error is raised anywhere.
    """
    binding = BINDINGS[entry["name"]]
    declared = entry["applicability"]["dataset_inputs"]

    # A LIST argument is N datasets, not one. Counting arguments instead of
    # datasets is how `merge_layers` came to declare 1 while taking a list, and
    # how this test certified it: the first version read
    # `len(input_args) + len(list_input_args)` and agreed with the wrong number.
    # An operation with a list input has variable arity, which the catalogue
    # spells `null`.
    if binding.list_input_args:
        assert declared is None, (
            f"{entry['name']} takes {binding.list_input_args} — a list of datasets, "
            f"so its arity is variable — and declares {declared}. Any caller who "
            "names a different number will never be offered it."
        )
        return

    actual = len(binding.input_args)
    assert declared in (actual, None), (
        f"{entry['name']} declares dataset_inputs={declared} and its binding reads "
        f"{actual} dataset argument(s) ({binding.input_args}). "
        "A caller who declares the true number will never be offered it."
    )


def test_every_entry_declares_an_arity_at_all():
    """Including the ones with no binding — planned operations and the two plan
    tools. A missing declaration would make `applicable(dataset_inputs=...)`
    raise a KeyError deep inside a filter, which is a worse way to find out."""
    missing = [
        op["name"]
        for op in catalog.OPERATIONS
        if "dataset_inputs" not in op["applicability"]
    ]
    assert not missing, f"these entries declare no dataset_inputs: {missing}"


def test_an_operation_with_variable_arity_is_offered_to_every_caller():
    """`null` is kept for every declared arity, like `inputs: ["none"]`.

    Two operations have arity that is not a number: `merge_layers` takes a list,
    and `run_sql` names its inputs inside a query string. The first version of
    this facet gave them 1 and 0, and the measured result was that the obvious
    two-layer operation disappeared for anyone holding two layers and the
    product's general escape hatch disappeared for anyone holding any — in the
    release whose notes said discovery was fixed. The worked example on the
    README showed it: `run_sql` at position `None`.
    """
    variable = [
        op["name"]
        for op in catalog.OPERATIONS
        if op["applicability"]["dataset_inputs"] is None
    ]
    assert {"merge_layers", "run_sql"} <= set(variable), (
        f"these should have variable arity and do not: {variable}"
    )
    for arity in (0, 1, 2):
        offered = {op["name"] for op in catalog.applicable(dataset_inputs=arity)}
        missing = [name for name in variable if name not in offered]
        assert not missing, (
            f"declaring dataset_inputs={arity} hid {missing}, whose arity is not a "
            "number and which must therefore survive every declaration"
        )


def test_an_operation_declares_every_kind_of_data_it_reads():
    """`applicability.inputs` has to list every input, not just the first one.

    `sample_raster_at_points` and `elevation_profile` shipped declaring
    `['vector']` while taking a raster too, and `viewshed` declared `['raster']`
    while taking a point layer — so "I have a DEM and my levelling shots" did not
    find the operation written for that sentence. The parameter names say which
    kinds an operation reads; the declaration has to agree with them.
    """
    suffixes = {
        "raster_path": "raster", "dem_path": "raster",
        "flow_accumulation_path": "raster",
        "points_path": "vector", "line_path": "vector", "zones_path": "vector",
        "stations_path": "vector", "mask_path": "vector",
        "pour_points_path": "vector", "boundary_path": "vector",
    }
    wrong = []
    for op in catalog.OPERATIONS:
        declared = set(op["applicability"]["inputs"])
        if "dataset" in declared or "none" in declared:
            continue
        for parameter in op.get("parameters", []):
            name = parameter["name"] if isinstance(parameter, dict) else str(parameter)
            kind = suffixes.get(name)
            if kind and kind not in declared:
                wrong.append(f"{op['name']}.{name} is a {kind}, not in {sorted(declared)}")
    assert not wrong, (
        "these operations read a kind of data they do not declare, so a caller "
        f"who says they are holding it is never offered them: {wrong}"
    )


def test_no_writing_operation_leaves_a_file_in_the_working_directory(tmp_path):
    """The paths MapSmith's engines choose for themselves, not the ones a caller names.

    Everything above this line checks a path the caller can name. Nothing checked
    what an operation leaves behind, and on 2026-09-06 that turned out to matter:
    `contour_lines` wrote four files -- `contours_from_raster.{shp,shx,dbf,prj}`
    -- into the PROCESS working directory, because `WbEnvironment()` takes its
    `working_directory` from there and eleven call sites never set it. With
    `MAPSMITH_WORKSPACE` set and the server started anywhere else, that is four
    files outside the jail SECURITY.md promises nothing writes outside of. They
    had been sitting in the repository root for days, invisible to `git status`
    because `.gitignore` covers `*.shp`.

    **A behavioural check and not a lexical one, deliberately.** The obvious guard
    -- "no bare `wb.WbEnvironment()`" -- is anchored to a line of source rather
    than to behaviour: green the moment somebody writes `cls = wb.WbEnvironment;
    cls()`, and blind to the next engine that inherits a working directory. And
    there is nothing to read: the Whitebox package ships a taxonomy of 775 tools
    with two keys, neither of which says whether a tool is file-based. The only
    source is what the tool does.

    **Forcing the working directory outside the workspace is the load-bearing
    part.** The container image runs with `WORKDIR` equal to `MAPSMITH_WORKSPACE`,
    so a test that inherited the ambient directory would pass by construction --
    a guard that cannot fail, in the same shape this project has now found five
    times.

    The list comes from the catalogue, not from here: `test_verify` builds one
    real call per writing operation, and this reuses it rather than keeping a
    parallel set that would cover less the day an operation is added.

    Known exception, stated rather than discovered: DuckDB writes its `spatial`
    extension under `$HOME/.duckdb` on first use, ~15 MB, and does it with a
    workspace set. That is a second escape from the same sentence in
    SECURITY.md, it is deliberate on DuckDB's part, and it has a board entry of
    its own -- so this test watches the working directory and says so, instead
    of pretending HOME is covered.
    """
    import json
    import os

    from test_verify import _spec_fixtures

    workspace_dir = tmp_path / "workspace"
    elsewhere = tmp_path / "elsewhere"
    workspace_dir.mkdir()
    elsewhere.mkdir()

    fixtures = _spec_fixtures(workspace_dir)
    assert len(fixtures) >= 20, f"only {len(fixtures)} fixtures: the sweep would prove little"

    previous = Path.cwd()
    offenders: dict[str, list[str]] = {}
    ran = 0
    try:
        os.chdir(elsewhere)
        for name, call in sorted(fixtures.items()):
            try:
                call()
            except ImportError:
                continue  # an absent extra, as in the conformance sweep
            ran += 1
            left = sorted(p.name for p in elsewhere.iterdir())
            if left:
                offenders[name] = left
                for p in elsewhere.iterdir():
                    p.unlink() if p.is_file() else None
    finally:
        os.chdir(previous)

    assert ran >= 20, f"only {ran} operations actually ran"
    assert not offenders, (
        "these operations wrote into the process working directory, which is "
        f"outside the workspace: {json.dumps(offenders)}. An engine that drops a "
        "working file anywhere but a temporary directory inside the workspace is "
        "a bug in that engine binding -- SECURITY.md promises no tool call writes "
        "outside the workspace, and that promise is what this test is for."
    )


def test_no_subprocess_inherits_the_working_directory():
    """A child process writes where it was started, and that is not our choice.

    `stacks.esri_run` spawned the ArcPy sidecar with no `cwd=`, so it inherited
    whatever directory the server was started in. Nothing has leaked through it
    yet -- it needs ArcGIS Pro installed, and this machine has none, so the
    behavioural sweep above cannot reach it. That is precisely why this one is
    lexical: the alternative is to wait for a machine that can run it, and the
    QGIS/GRASS sidecar is on the list.

    The measured cousin is `contour_lines`, which leaked four files for a whole
    release because Whitebox took its working directory from the process. In
    process it was at least visible in `git status` once you knew to look; a
    subprocess writing relative paths on someone else's machine is not.

    Read from the source rather than from a list of call sites: the point is
    that the NEXT engine behind a process boundary meets this test before it
    meets a bug report.
    """
    import ast

    import mapsmith

    root = Path(mapsmith.__file__).parent
    naked: list[str] = []
    for module in sorted(root.rglob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = node.func
            if not isinstance(callee, ast.Attribute) or callee.attr not in {
                "run", "Popen", "check_call", "check_output", "call",
            }:
                continue
            if getattr(callee.value, "id", None) != "subprocess":
                continue
            if not any(keyword.arg == "cwd" for keyword in node.keywords):
                naked.append(f"{module.name}:{node.lineno}")

    assert not naked, (
        f"these spawn a process without saying where it should run: {naked}. A "
        "child inherits the server's working directory, so anything it writes "
        "relative to it lands wherever the operator happened to start MapSmith "
        "— outside the workspace SECURITY.md promises nothing writes outside of. "
        "Pass `cwd=` pointing at a scratch directory inside the workspace."
    )
