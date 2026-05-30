"""時刻のみ突合＋既知差分許容リスト check_times のテスト。

発車時刻(時:分)の多重集合を比較し、許容リスト(expected)を差し引いた
「新規(想定外)の差分」だけを返す。行先は判定に用いない。
"""

from fukuoka_gtfs.verify.jorudan_parser import Departure
from fukuoka_gtfs.verify.timetable_check import check_times


def _d(h, m, dest="x"):
    return Departure(h, m, dest)


def test_identical_times_ok_regardless_of_destination():
    jor = [_d(5, 30, "福岡空港"), _d(5, 45, "貝塚")]
    gtfs = [_d(5, 45, "博多"), _d(5, 30, "姪浜")]  # 行先が違っても時刻一致なら OK
    diff = check_times(jor, gtfs)
    assert diff.ok
    assert diff.missing == [] and diff.extra == []


def test_unexpected_missing_fails():
    jor = [_d(5, 30), _d(5, 45)]
    gtfs = [_d(5, 30)]
    diff = check_times(jor, gtfs)
    assert not diff.ok
    assert diff.missing == [(5, 45)]


def test_unexpected_extra_fails():
    jor = [_d(5, 30)]
    gtfs = [_d(5, 30), _d(6, 0)]
    diff = check_times(jor, gtfs)
    assert not diff.ok
    assert diff.extra == [(6, 0)]


def test_allowlisted_diff_is_ok():
    jor = [_d(23, 48)]
    gtfs = [_d(23, 49)]
    diff = check_times(
        jor, gtfs, allow_missing=[(23, 48)], allow_extra=[(23, 49)]
    )
    assert diff.ok


def test_new_diff_beyond_allowlist_fails():
    jor = [_d(23, 48), _d(7, 0)]
    gtfs = [_d(23, 49)]
    diff = check_times(jor, gtfs, allow_missing=[(23, 48)], allow_extra=[(23, 49)])
    assert not diff.ok
    assert diff.missing == [(7, 0)]  # 許容外の新規欠落のみ


def test_allowlist_is_tolerant_when_diff_resolved():
    # 許容に挙げた差分が実際には出ていなくても失敗しない（バグ修正で差分が消えても緑）
    jor = [_d(5, 30)]
    gtfs = [_d(5, 30)]
    diff = check_times(jor, gtfs, allow_missing=[(23, 48)], allow_extra=[(23, 49)])
    assert diff.ok
