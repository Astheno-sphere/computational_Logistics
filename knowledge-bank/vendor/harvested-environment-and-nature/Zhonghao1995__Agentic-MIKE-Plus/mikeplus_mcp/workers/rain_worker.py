"""Write a rainfall .dfs0 from a timestamped CSV. Imports mikeio ONLY (+ pure contracts).
No license needed.

stdin payload: {csv, out_dfs0, time_col?, value_col?, unit?='mm/h', item_name?='Rainfall'}
"""
import json
import sys


def main() -> None:
    payload = json.load(sys.stdin)
    out = payload["__out"]
    try:
        import mikeio
        from mikeplus_mcp.contracts import rain

        s = rain.load_rain_csv(payload["csv"], payload.get("time_col"), payload.get("value_col"))
        inten, info = rain.to_intensity(s, payload.get("unit") or "mm/h")

        # same item shape as DHI's own example rain files: intensity, mm/h, mean-step-backward
        item = mikeio.ItemInfo(payload.get("item_name") or "Rainfall",
                               mikeio.EUMType.Rainfall_Intensity, mikeio.EUMUnit.mm_per_hour,
                               data_value_type="MeanStepBackward")
        da = mikeio.DataArray(inten.to_numpy(dtype=float), time=inten.index, item=item)
        out_dfs0 = payload["out_dfs0"]
        mikeio.Dataset([da]).to_dfs(out_dfs0)

        back = mikeio.read(out_dfs0)   # read-back check: the file must round-trip
        n_back = int(len(back.time))
        if n_back != info["n_steps"]:
            raise RuntimeError(f"dfs0 read-back has {n_back} steps, expected {info['n_steps']}")

        result = {"ok": True, "dfs0": out_dfs0, "item": str(back.items[0]),
                  "csv": payload["csv"], **info}
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, default=str)
    sys.exit(0 if result.get("ok") else 1)


main()
