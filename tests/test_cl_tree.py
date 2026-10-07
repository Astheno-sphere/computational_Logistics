import pytest

from cl_tree import Tree, fmt, match, parse


def T(d):
    return Tree([(parse(k), v) for k, v in d.items()])


def test_parse_and_format_roundtrip():
    assert parse("{0;1;2}") == (0, 1, 2) and fmt((0, 1, 2)) == "{0;1;2}" and parse("{}") == ()


def test_from_nested_matches_treehelpers_layout():
    t = Tree.from_nested([[1, 2, 3], [4, 5]])
    assert t == T({"{0}": [1, 2, 3], "{1}": [4, 5]})
    assert t.to_nested() == [[1, 2, 3], [4, 5]]


def test_flatten_and_graft():
    t = T({"{0;0}": ["a", "b"], "{0;1}": ["c"]})
    assert t.flatten() == T({"{0}": ["a", "b", "c"]})
    assert t.graft() == T({"{0;0;0}": ["a"], "{0;0;1}": ["b"], "{0;1;0}": ["c"]})


def test_graft_then_trim_is_identity():
    t = T({"{0}": [1, 2], "{1}": [3]})
    assert t.graft().trim(1) == t


def test_simplify_removes_shared_leading_indices():
    t = T({"{0;0;0}": [1], "{0;0;1}": [2]})
    assert t.simplify() == T({"{0}": [1], "{1}": [2]})


def test_simplify_removes_shared_trailing_indices_too():
    t = T({"{0;1;0}": [1], "{0;2;0}": [2]})
    assert t.simplify() == T({"{1}": [1], "{2}": [2]})


def test_matching_follows_book_rule_repeat_last_branch_then_last_item():
    a = T({"{0}": [1, 2, 3], "{1}": [4]})
    b = T({"{0}": [10], "{1}": [20, 30], "{2}": [40]})
    m = match({"A": a, "B": b})
    assert m["branches"] == 3
    assert [p["uses"]["A"] for p in m["plan"]] == ["{0}", "{1}", "{1}"]
    assert [p["iterations"] for p in m["plan"]] == [3, 2, 1]


def test_shift_paths_both_directions():
    t = T({"{2;0}": [1], "{2;1}": [2]})
    assert t.shift(-1) == T({"{2}": [1, 2]})
    assert t.shift(1) == T({"{0}": [1], "{1}": [2]})


def test_flip_matrix_and_ragged_nulls():
    assert T({"{0}": [1, 2], "{1}": [3, 4]}).flip() == T({"{0}": [1, 3], "{1}": [2, 4]})
    assert T({"{0}": [1, 2], "{1}": [3]}).flip() == T({"{0}": [1, 3], "{1}": [2, None]})


def test_path_mapper_masks():
    t = T({"{0;1}": ["a"], "{1;0}": ["b"]})
    assert t.path_mapper("{A;B}", "{B;A}") == T({"{1;0}": ["a"], "{0;1}": ["b"]})
    assert t.path_mapper("{A;B}", "{A}") == T({"{0}": ["a"], "{1}": ["b"]})
    assert T({"{0}": ["x", "y"]}).path_mapper("{A}(i)", "{A;i}") == T({"{0}": ["x", "y"]}).graft()
    with pytest.raises(ValueError):
        t.path_mapper("{A}", "{A}")


def test_match_pairs_branches_by_order_not_by_path_name():
    a = T({"{0}": [1, 2], "{1}": [3, 4]})
    b = T({"{7;3}": [10], "{9;9}": [20]})            # unrelated path names
    m = match({"A": a, "B": b})
    assert [p["uses"]["B"] for p in m["plan"]] == ["{7;3}", "{9;9}"]
    assert m["iterations"] == 4                      # 2 items x 2 branch pairs


def test_match_longest_list_repeats_last_branch_and_master_is_widest():
    a = T({"{0}": [1], "{1}": [2], "{2}": [3]})
    b = T({"{0}": [10]})
    m = match({"pts": b, "vec": a})
    assert m["master"] == "vec" and m["branches"] == 3
    assert all(p["uses"]["pts"] == "{0}" for p in m["plan"])


def test_graft_against_flat_list_multiplies_work():
    pts = T({"{0}": list(range(5))})
    m = match({"A": pts.graft(), "B": pts})
    assert m["iterations"] == 25                     # 5 branches x 5 items: the classic accidental cross product


def test_list_access_consumes_whole_branch():
    m = match({"crv": T({"{0}": [1, 2, 3]}), "t": T({"{0}": [0.5]})}, access={"crv": "list"})
    assert m["iterations"] == 1
