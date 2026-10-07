from unittest import mock

from mapmover.runtime import external_reference_adapters as adapters
from mapmover.runtime.external_reference_adapters import ExternalReferenceEdge


def test_external_edge_batch_uses_one_partition_query() -> None:
    first = "11111111-1111-1111-1111-111111111111"
    second = "22222222-2222-2222-2222-222222222222"
    edge = ExternalReferenceEdge(
        external_id=first,
        loc_id="CAN-AB",
        relationship_type="equivalent_identity",
        is_primary=True,
        source_release="gers-v1",
        internal_release="can-v1",
        country="CAN",
        source_level=1,
        external_subtype="region",
        identity_confidence="high",
        geometry_confidence=1.0,
        external_name="Alberta",
        loc_name="Alberta",
    )
    bridge = object()
    partitions = (object(),)
    with (
        mock.patch.object(adapters, "admitted_bridge", return_value=bridge),
        mock.patch.object(adapters, "_bridge_available", return_value=True),
        mock.patch.object(adapters, "_selected_partitions", return_value=partitions),
        mock.patch.object(adapters, "_query_edges", return_value=[edge]) as query,
    ):
        result = adapters.lookup_external_edges_batch(
            "gers", [first, second, first], country_scope="CAN",
        )

    query.assert_called_once_with(
        bridge,
        partitions,
        reverse=False,
        values=[first, second],
        source_release=None,
        internal_release=None,
        country_scope="CAN",
    )
    assert result == {first: [edge], second: []}


def test_reverse_external_edge_batch_uses_one_partition_query() -> None:
    first = "CAN-AB"
    second = "CAN-BC"
    edge = ExternalReferenceEdge(
        external_id="11111111-1111-1111-1111-111111111111",
        loc_id=first,
        relationship_type="equivalent_identity",
        is_primary=True,
        source_release="gers-v1",
        internal_release="can-v1",
        country="CAN",
        source_level=1,
        external_subtype="region",
        identity_confidence="high",
        geometry_confidence=1.0,
        external_name="Alberta",
        loc_name="Alberta",
    )
    bridge = object()
    partitions = (object(),)
    with (
        mock.patch.object(adapters, "admitted_bridge", return_value=bridge),
        mock.patch.object(adapters, "_bridge_available", return_value=True),
        mock.patch.object(adapters, "_selected_partitions", return_value=partitions),
        mock.patch.object(adapters, "_query_edges", return_value=[edge]) as query,
    ):
        result = adapters.lookup_loc_id_edges_batch(
            "gers", [first, second, first], country_scope="CAN", limit=10,
        )

    query.assert_called_once_with(
        bridge,
        partitions,
        reverse=True,
        values=[first, second],
        source_release=None,
        internal_release=None,
        country_scope="CAN",
    )
    assert result == {first: [edge], second: []}
