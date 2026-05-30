"""発車時刻(時:分)の突合。行先は判定に用いず、既知差分は許容リストで除外する。

ジョルダンと GTFS では直通便の行先表記体系が異なるため（地下鉄表示 vs 実際の
直通先）、行先は厳密一致できない。よって合否は発車時刻の集合一致で判定し、
行先は参考情報として扱う。既知の時刻差（七隈線の一部 1 分差、境界駅の直通便など）は
``allow_missing`` / ``allow_extra`` に登録し、それ以外の新規差分のみを不一致とする。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .jorudan_parser import Departure

__all__ = ["TimeDiff", "check_times"]

Time = tuple[int, int]


@dataclass(frozen=True)
class TimeDiff:
    """許容リストを差し引いた後の想定外差分。"""

    missing: list[Time]  # ジョルダンにあり GTFS に無い（許容外）
    extra: list[Time]    # GTFS にありジョルダンに無い（許容外）

    @property
    def ok(self) -> bool:
        return not self.missing and not self.extra


def _times(departures: list[Departure]) -> Counter[Time]:
    return Counter((d.hour, d.minute) for d in departures)


def _subtract(diff: Counter[Time], allow: list[Time]) -> list[Time]:
    remaining = diff - Counter(allow)
    return sorted(remaining.elements())


def check_times(
    jorudan: list[Departure],
    gtfs: list[Departure],
    *,
    allow_missing: list[Time] = (),
    allow_extra: list[Time] = (),
) -> TimeDiff:
    jt = _times(jorudan)
    gt = _times(gtfs)
    return TimeDiff(
        missing=_subtract(jt - gt, list(allow_missing)),
        extra=_subtract(gt - jt, list(allow_extra)),
    )
