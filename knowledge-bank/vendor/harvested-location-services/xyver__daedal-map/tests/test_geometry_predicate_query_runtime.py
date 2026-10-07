from unittest.mock import MagicMock, patch

import pandas as pd

from mapmover.runtime import geometry_predicate_query


def test_geojson_containment_uses_one_exact_spatial_scan(tmp_path) -> None:
    path = tmp_path / "water.parquet"
    pd.DataFrame([{
        "loc_id": "XOP",
        "geometry": '{"type":"Polygon","coordinates":[]}',
        "bbox_min_lon": -180.0,
        "bbox_min_lat": -90.0,
        "bbox_max_lon": 180.0,
        "bbox_max_lat": 90.0,
    }]).to_parquet(path, index=False)
    expected = pd.DataFrame([{"point_position": 0, "loc_id": "XOP"}])
    connection = MagicMock()
    connection.execute.return_value.fetchdf.return_value = expected
    lease = MagicMock()
    lease.__enter__.return_value = connection

    with patch.object(
        geometry_predicate_query, "lease_query_connection", return_value=lease,
    ):
        result = geometry_predicate_query.read_geojson_containment_for_points(
            path,
            [{"lon": -120.0, "lat": 30.0}],
            columns=["loc_id", "geometry"],
        )

    assert result is expected
    assert connection.execute.call_count == 2
    sql, parameters = connection.execute.call_args.args
    assert "ST_Covers(ST_GeomFromGeoJSON(candidate.geometry)" in sql
    assert sql.count("read_parquet(?)") == 1
    assert parameters == [str(path), 0, -120.0, 30.0]


def test_hash_sharded_rows_use_one_duckdb_query_for_all_routed_files(tmp_path) -> None:
    values = ["candidate-a", "candidate-b"]
    while (
        geometry_predicate_query.stable_hash_shard(values[0], 4)
        == geometry_predicate_query.stable_hash_shard(values[1], 4)
    ):
        values[1] += "x"

    paths = {}
    for value in values:
        shard = geometry_predicate_query.stable_hash_shard(value, 4)
        path = tmp_path / f"{shard}.parquet"
        pd.DataFrame([{"candidate_id": value, "name": value.upper()}]).to_parquet(
            path, index=False,
        )
        paths[shard] = path

    real_run_df = geometry_predicate_query.run_df
    with patch.object(geometry_predicate_query, "run_df", wraps=real_run_df) as run:
        result = geometry_predicate_query.read_hash_sharded_rows(
            paths,
            values,
            shard_count=4,
            id_column="candidate_id",
            columns=["name"],
        )

    assert run.call_count == 1
    sql, parameters = run.call_args.args
    assert "read_parquet([?, ?], union_by_name=true)" in sql
    assert parameters[:2] == [str(paths[shard]) for shard in sorted(paths)]
    assert set(result["candidate_id"]) == set(values)
