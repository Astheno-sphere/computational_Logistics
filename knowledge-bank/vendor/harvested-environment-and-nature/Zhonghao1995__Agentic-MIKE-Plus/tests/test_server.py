"""The server must give every failure the same {ok:false} shape the skills expect."""
from mikeplus_mcp._types import ToolDef
from mikeplus_mcp.server import _safe_invoke


def _tool(handler):
    return ToolDef(name="t", description="d",
                   input_schema={"type": "object", "properties": {}}, handler=handler)


def test_passes_through_a_normal_result():
    out = _safe_invoke(_tool(lambda a: {"ok": True, "v": a.get("x")}), {"x": 1})
    assert out == {"ok": True, "v": 1}


def test_coerces_an_exception_to_ok_false():
    def boom(_):
        raise RuntimeError("worker 'run_worker' timed out after 1800s")

    out = _safe_invoke(_tool(boom), {})
    assert out["ok"] is False
    assert out["error"].startswith("RuntimeError")
    assert "timed out" in out["error"]


def test_handles_none_arguments():
    out = _safe_invoke(_tool(lambda a: {"ok": True, "n": len(a)}), None)
    assert out == {"ok": True, "n": 0}
