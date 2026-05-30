"""発車時刻集合の厳密突合 comparator のテスト。"""

from fukuoka_gtfs.verify.comparator import ComparisonResult, compare
from fukuoka_gtfs.verify.jorudan_parser import Departure


def _d(h, m, dest="福岡空港"):
    return Departure(hour=h, minute=m, destination=dest)


def test_identical_sets_are_ok():
    jorudan = [_d(5, 30), _d(5, 45, "貝塚")]
    gtfs = [_d(5, 45, "貝塚"), _d(5, 30)]  # 順序が違っても一致
    result = compare(jorudan, gtfs)
    assert result.ok
    assert result.missing == []
    assert result.extra == []


def test_detects_missing_departure_in_gtfs():
    jorudan = [_d(5, 30), _d(5, 45, "貝塚")]
    gtfs = [_d(5, 30)]
    result = compare(jorudan, gtfs)
    assert not result.ok
    assert result.missing == [_d(5, 45, "貝塚")]
    assert result.extra == []


def test_detects_extra_departure_in_gtfs():
    jorudan = [_d(5, 30)]
    gtfs = [_d(5, 30), _d(6, 0)]
    result = compare(jorudan, gtfs)
    assert not result.ok
    assert result.missing == []
    assert result.extra == [_d(6, 0)]


def test_destination_mismatch_is_both_missing_and_extra():
    # 時刻は同じだが行先が異なる → 厳密一致では不一致
    jorudan = [_d(5, 30, "福岡空港")]
    gtfs = [_d(5, 30, "貝塚")]
    result = compare(jorudan, gtfs)
    assert not result.ok
    assert result.missing == [_d(5, 30, "福岡空港")]
    assert result.extra == [_d(5, 30, "貝塚")]


def test_duplicate_counts_matter():
    # 同一便が 2 本(複線/別ホーム)。本数差を検出する。
    jorudan = [_d(5, 30), _d(5, 30)]
    gtfs = [_d(5, 30)]
    result = compare(jorudan, gtfs)
    assert not result.ok
    assert result.missing == [_d(5, 30)]


def test_result_type():
    assert isinstance(compare([], []), ComparisonResult)
    assert compare([], []).ok
