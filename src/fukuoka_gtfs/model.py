"""Excel から抽出した中間データの型。

GTFS のテーブルへ落とし込む前の「列車（便）」を表現する。1 つの Trip は必ず
単一の route_id に属する（空港線↔箱崎線の直通便は中洲川端で 2 つの Trip に
分割され、同一 block_id で連結される）。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StopVisit:
    """1 便の 1 停車。

    stop_id は GTFS の location_type=0 の子ホームを指す。
    sec は当日 00:00 からの経過秒（24 時以降は 86400 以上になりうる）。
    """

    stop_id: str
    sec: int


@dataclass
class Trip:
    """1 便（GTFS の 1 trip 相当）。"""

    route_id: str
    service_id: str
    direction_id: int
    headsign: str
    block_id: str
    visits: list[StopVisit] = field(default_factory=list)

    @property
    def first_sec(self) -> int:
        return self.visits[0].sec
