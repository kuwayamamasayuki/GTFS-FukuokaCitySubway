"""運賃突合ロジック gtfs_fares / compare の単体テスト。

- fare_attributes/fare_rules から駅ペア→運賃の辞書を作る。
- ジョルダン運賃と突合し、許容リストを差し引いた不一致のみ報告する。
- 運賃は方向に依存しないため (o, d) と (d, o) は同一視する。
"""

from fukuoka_gtfs.verify.fare_check import compare, gtfs_fares

ATTR = [
    {"fare_id": "fare_210", "price": "210"},
    {"fare_id": "fare_260", "price": "260"},
]
RULES = [
    {"fare_id": "fare_210", "origin_id": "1", "destination_id": "2"},
    {"fare_id": "fare_210", "origin_id": "2", "destination_id": "1"},  # 逆方向
    {"fare_id": "fare_260", "origin_id": "1", "destination_id": "3"},
]


def test_gtfs_fares_builds_symmetric_pair_map():
    fares = gtfs_fares(ATTR, RULES)
    assert fares[frozenset(("1", "2"))] == 210
    assert fares[frozenset(("1", "3"))] == 260
    # (1,2) と (2,1) は同一キーに畳まれる
    assert len(fares) == 2


def test_compare_all_match_is_ok():
    g = gtfs_fares(ATTR, RULES)
    j = {frozenset(("1", "2")): 210, frozenset(("1", "3")): 260}
    diff = compare(g, j)
    assert diff.ok


def test_compare_detects_mismatch():
    g = gtfs_fares(ATTR, RULES)
    j = {frozenset(("1", "2")): 250, frozenset(("1", "3")): 260}
    diff = compare(g, j)
    assert not diff.ok
    assert diff.mismatch == [(("1", "2"), 210, 250)]


def test_compare_allowlist_suppresses_known_diff():
    g = gtfs_fares(ATTR, RULES)
    j = {frozenset(("1", "2")): 250, frozenset(("1", "3")): 260}
    diff = compare(g, j, allow={frozenset(("1", "2"))})
    assert diff.ok


def test_compare_reports_missing_pairs():
    g = gtfs_fares(ATTR, RULES)
    j = {frozenset(("1", "2")): 210}  # (1,3) がジョルダンに無い
    diff = compare(g, j)
    assert diff.missing_in_jorudan == [("1", "3")]
    assert not diff.ok


def test_compare_reports_missing_in_gtfs():
    g = {frozenset(("1", "2")): 210}
    j = {frozenset(("1", "2")): 210, frozenset(("2", "3")): 300}
    diff = compare(g, j)
    assert diff.missing_in_gtfs == [("2", "3")]


def test_mismatch_sorted_by_station_id_numerically():
    g = {frozenset(("2", "10")): 210, frozenset(("2", "3")): 210}
    j = {frozenset(("2", "10")): 999, frozenset(("2", "3")): 999}
    diff = compare(g, j)
    # 数値順（3 < 10）でソートされる
    assert [m[0] for m in diff.mismatch] == [("2", "3"), ("2", "10")]
