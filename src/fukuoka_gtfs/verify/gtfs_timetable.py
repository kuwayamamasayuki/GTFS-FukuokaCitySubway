"""生成 GTFS から「駅×方面×サービス」の発車便を抽出する。

深夜の ``24:mm`` / ``25:mm`` は ``hour % 24`` で 0/1 時に正規化し、ジョルダンの
0/1 時表示と突き合わせられるようにする。行先は ``trip_headsign`` をそのまま用いる
（表記揺れの吸収は突合側のマッピングで行う）。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from ..gtfsio import read_csv
from .jorudan_parser import Departure

__all__ = ["Feed", "load_feed", "departures"]


@dataclass(frozen=True)
class Feed:
    """突合に必要な GTFS テーブル群。"""

    stops: list[dict]
    trips: list[dict]
    stop_times: list[dict]


def load_feed(gtfs_dir: str | Path) -> Feed:
    """GTFS ディレクトリから stops / trips / stop_times を読み込む。"""
    d = Path(gtfs_dir)
    _, stops = read_csv(d / "stops.txt")
    _, trips = read_csv(d / "trips.txt")
    _, stop_times = read_csv(d / "stop_times.txt")
    return Feed(stops=stops, trips=trips, stop_times=stop_times)


def _child_stop_ids(stops: list[dict], stop_name: str) -> set[str]:
    """指定駅名の親駅に属する子ホーム stop_id の集合を返す。

    親駅(location_type=1)を駅名で特定し、その parent_station を持つ子を集める。
    停車時刻は子ホームの stop_id に記録されるため。
    """
    parents = {
        s["stop_id"]
        for s in stops
        if s.get("stop_name") == stop_name and s.get("location_type") == "1"
    }
    return {s["stop_id"] for s in stops if s.get("parent_station") in parents}


def departures(
    feed: Feed,
    *,
    stop_name: str,
    route_id: str,
    direction_id: int,
    service_id: str,
) -> list[Departure]:
    """指定の駅・路線・方面・サービスの発車便を抽出する。"""
    child_ids = _child_stop_ids(feed.stops, stop_name)
    dir_str = str(direction_id)
    trip_meta: dict[str, str] = {}  # trip_id -> headsign
    for t in feed.trips:
        if (
            t.get("route_id") == route_id
            and t.get("direction_id") == dir_str
            and t.get("service_id") == service_id
        ):
            trip_meta[t["trip_id"]] = t.get("trip_headsign", "")

    # 各 trip の最終 stop_sequence（終着）。終着での停車は発車に数えない。
    last_seq: dict[str, int] = defaultdict(lambda: -1)
    for st in feed.stop_times:
        tid = st.get("trip_id")
        if tid in trip_meta:
            seq = int(st["stop_sequence"])
            if seq > last_seq[tid]:
                last_seq[tid] = seq

    out: list[Departure] = []
    for st in feed.stop_times:
        if st.get("stop_id") not in child_ids:
            continue
        trip_id = st.get("trip_id")
        if trip_id not in trip_meta:
            continue
        # 真の終着（行先＝当駅名）での到着は発車ではないので除外する。
        # 行先が当駅名と異なる便（JR 直通などフィード境界の先へ継続する便）は、
        # 当駅が最終停車であっても実際には発車するため残す。
        if (
            int(st["stop_sequence"]) == last_seq[trip_id]
            and trip_meta[trip_id] == stop_name
        ):
            continue
        hh, mm, _ = st["departure_time"].split(":")
        out.append(
            Departure(
                hour=int(hh) % 24,
                minute=int(mm),
                destination=trip_meta[trip_id],
            )
        )
    return out
