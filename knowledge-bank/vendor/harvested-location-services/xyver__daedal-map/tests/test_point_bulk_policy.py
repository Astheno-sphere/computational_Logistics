from mapmover.point_bulk_policy import apply_point_lookup_mode, point_bulk_shape_error


def test_standard_mode_caps_io_at_admin3_without_requiring_country() -> None:
    mode, target, maximum, error = apply_point_lookup_mode(
        None, country_scope=None, target_admin_level=None,
    )

    assert (mode, target, maximum, error) == ("standard", None, 3, None)
    assert point_bulk_shape_error(
        point_count=5_000,
        country_scope=None,
        target_admin_level=None,
        bulk_preset=None,
        lookup_mode=mode,
        threshold=100,
    ) is None


def test_standard_mode_rejects_deep_target() -> None:
    mode, target, maximum, error = apply_point_lookup_mode(
        "standard", country_scope="USA", target_admin_level=4,
    )

    assert (mode, target, maximum) == ("standard", 4, 3)
    assert error["code"] == "deep_mode_required"


def test_deep_mode_requires_exactly_one_declared_country() -> None:
    _, _, _, error = apply_point_lookup_mode(
        "deep", country_scope=None, target_admin_level=5,
    )
    assert error["code"] == "deep_country_scope_required"

    mode, target, maximum, error = apply_point_lookup_mode(
        "deep", country_scope="USA", target_admin_level=5,
    )
    assert error["code"] == "deep_admin_1_scope_required"

    mode, target, maximum, error = apply_point_lookup_mode(
        "deep", country_scope="USA", target_admin_level=5,
        admin_1_scope="USA-CA",
    )
    assert (mode, target, maximum, error) == ("deep", 5, None, None)


def test_deep_admin_1_scope_must_belong_to_country() -> None:
    _, _, _, error = apply_point_lookup_mode(
        "deep", country_scope="USA", target_admin_level=4,
        admin_1_scope="CAN-ON",
    )

    assert error["code"] == "deep_scope_mismatch"
