"""時刻の正規化。

Excel の時刻セルは「当日に占める割合（0〜1 の小数）」として渡される
（日付部分は信頼できないため呼び出し側で破棄済み）。本モジュールは便ごとの
時刻列を GTFS 用に正規化する。

注意点（実データで確認済み）:
  * 一部の深夜便は秒の誤差を含む（例 00:16:25, 23:47:10）→ 分単位に丸める。
  * 0 時跨ぎは 2 通りでエンコードされうる → 下記 (a)(b) の規則で統一し、
    GTFS の 24 時超表記（例 ``25:30:00``）で出力する。
"""
from __future__ import annotations

import datetime as _dt

DAY_SEC = 86400
DEFAULT_OVERNIGHT_THRESHOLD_SEC = 4 * 3600  # 04:00 より前の始発は前日ダイヤの続き


def to_fraction(value: object) -> float | None:
    """セル値を「当日に占める割合（0〜1）」へ変換する。時刻でなければ None。

    * float/int（.xls = 1 日の小数 serial）: 小数部のみを採用（24 時超は呼出側で復元）。
    * datetime.time / datetime.datetime（.xlsx）: 時分秒のみを採用。
    """
    if isinstance(value, bool):  # bool は int のサブクラスなので先に除外
        return None
    if isinstance(value, _dt.datetime):
        t = value.time()
    elif isinstance(value, _dt.time):
        t = value
    elif isinstance(value, (int, float)):
        return float(value) % 1.0
    else:
        return None
    return (t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1e6) / DAY_SEC


def normalize_sequence(
    fractions: list[float],
    threshold_sec: int = DEFAULT_OVERNIGHT_THRESHOLD_SEC,
) -> list[int]:
    """1 便の時刻割合列 → 00:00 起点の経過秒列（24 時超は 86400 以上）。

    規則:
      0. 各時刻を分単位に丸める（秒の誤差を吸収）。
      (a) 先頭が threshold 未満なら前日ダイヤの続きとみなし全体に +24h。
      (b) 便内で前停車より小さい時刻が出たら、それ以降に +24h（運行中の 0 時跨ぎ）。
    """
    secs = [round(f * 1440) * 60 for f in fractions]  # 分丸め
    if secs and secs[0] < threshold_sec:
        secs = [s + DAY_SEC for s in secs]
    for i in range(1, len(secs)):
        while secs[i] < secs[i - 1]:
            secs[i] += DAY_SEC
    return secs


def sec_to_gtfs(sec: int) -> str:
    """経過秒 → GTFS の時刻表記 ``HH:MM:SS``（HH は 24 以上もありうる）。"""
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
