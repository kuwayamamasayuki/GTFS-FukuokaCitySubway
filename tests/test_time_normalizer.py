import datetime as dt

from fukuoka_gtfs.excel.time_normalizer import (
    normalize_sequence,
    sec_to_gtfs,
    to_fraction,
)


def test_to_fraction_types():
    assert to_fraction(0.5) == 0.5                       # .xls の小数(正午)
    assert abs(to_fraction(dt.time(5, 30)) - 5.5 / 24) < 1e-9
    assert abs(to_fraction(dt.datetime(1900, 1, 1, 0, 16, 25)) - (16 * 60 + 25) / 86400) < 1e-9
    assert to_fraction("発") is None
    assert to_fraction(None) is None
    assert to_fraction(True) is None                     # bool は時刻ではない
    # .xls の 24 時超(1.02 日)は小数部のみ → 0 時跨ぎは正規化器が復元
    assert abs(to_fraction(1.02) - 0.02) < 1e-9


def test_normalize_clean_minutes():
    # 05:30, 05:32, 05:34
    secs = normalize_sequence([5.5 / 24, (5 * 60 + 32) / 1440, (5 * 60 + 34) / 1440])
    assert secs == [5 * 3600 + 1800, 5 * 3600 + 32 * 60, 5 * 3600 + 34 * 60]


def test_normalize_truncates_seconds_below_30():
    # 00:16:25 → 秒切り捨てで 00:16、先頭が早朝なので +24h → 24:16
    frac = (16 * 60 + 25) / 86400
    assert normalize_sequence([frac]) == [24 * 3600 + 16 * 60]


def test_normalize_truncates_seconds_at_or_above_30():
    # Issue #7: 七隈線 .xlsx の深夜便は実秒付き（例 00:31:42）。
    # 公式公開時刻（ジョルダン）は秒を切り捨てる。四捨五入だと 00:32 になり +1 分ずれる。
    # 12:05:42 → 12:05（12:06 ではない）
    assert normalize_sequence([(12 * 3600 + 5 * 60 + 42) / 86400]) == [12 * 3600 + 5 * 60]
    # 12:05:30 ちょうど → 12:05（四捨五入なら 12:06 に切り上がる境界）
    assert normalize_sequence([(12 * 3600 + 5 * 60 + 30) / 86400]) == [12 * 3600 + 5 * 60]
    # 深夜便の実例 00:31:42 → 00:31、先頭が早朝なので +24h → 24:31
    assert normalize_sequence([(31 * 60 + 42) / 86400]) == [24 * 3600 + 31 * 60]


def test_normalize_truncation_no_float_drift():
    # float 誤差で丸め下げが 1 分早まらないこと（秒=0 の正分は厳密に保つ）。
    assert normalize_sequence([(12 * 3600 + 5 * 60) / 86400]) == [12 * 3600 + 5 * 60]
    assert normalize_sequence([(23 * 3600 + 48 * 60) / 86400]) == [23 * 3600 + 48 * 60]


def test_normalize_overnight_start():
    # 始発 00:03 は前日ダイヤの続き → 24:03 以降
    secs = normalize_sequence([3 / 1440, 32 / 1440])
    assert secs == [24 * 3600 + 3 * 60, 24 * 3600 + 32 * 60]


def test_normalize_midtrip_rollover():
    # 23:55 → 00:05 は運行中の 0 時跨ぎ → 24:05
    secs = normalize_sequence([(23 * 60 + 55) / 1440, 5 / 1440])
    assert secs == [23 * 3600 + 55 * 60, 24 * 3600 + 5 * 60]


def test_sec_to_gtfs_over_24h():
    assert sec_to_gtfs(25 * 3600 + 30 * 60) == "25:30:00"
    assert sec_to_gtfs(5 * 3600 + 9 * 60) == "05:09:00"
