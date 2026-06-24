"""Trip 群から trips.txt と stop_times.txt を生成する。

trip_id は ``{route_id}_{区分}_{direction_id}_{連番:03d}``（区分=平日/土曜/休日）。
連番は出発時刻順に振るため、差分が読みやすく安定する。service_id（trips.txt の列）は
グループ別（例: 空港箱崎_平日）で、calendar.txt の有効期間に対応する。
"""
from __future__ import annotations

from ..excel.time_normalizer import sec_to_gtfs
from ..model import Trip

TRIPS_HEADER = [
    "route_id", "service_id", "trip_id", "trip_headsign",
    "direction_id", "block_id", "shape_id", "wheelchair_accessible",
]
STOP_TIMES_HEADER = [
    "trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence",
]


def build(
    trips: list[Trip],
    shape_map: dict[tuple[str, int], str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """(trips 行, stop_times 行) を返す。

    shape_map は (route_id, direction_id) → shape_id。対応が無い組み合わせの
    shape_id は空文字（GTFS では shape の紐付けは任意）。
    """
    shape_map = shape_map or {}
    # (route, service, direction) ごとに出発時刻順へ並べ、連番を振る
    groups: dict[tuple[str, str, int], list[Trip]] = {}
    for t in trips:
        groups.setdefault((t.route_id, t.service_id, t.direction_id), []).append(t)

    trips_rows: list[dict] = []
    stop_times_rows: list[dict] = []
    for (route_id, service_id, direction_id), group in groups.items():
        group.sort(key=lambda t: t.first_sec)
        for i, trip in enumerate(group, start=1):
            seg = trip.service_segment or service_id
            trip_id = f"{route_id}_{seg}_{direction_id}_{i:03d}"
            trips_rows.append(dict(
                route_id=route_id, service_id=service_id, trip_id=trip_id,
                trip_headsign=trip.headsign, direction_id=direction_id,
                block_id=trip.block_id,
                shape_id=shape_map.get((route_id, direction_id), ""),
                wheelchair_accessible=1,
            ))
            for seq, visit in enumerate(trip.visits, start=1):
                t = sec_to_gtfs(visit.sec)
                stop_times_rows.append(dict(
                    trip_id=trip_id, arrival_time=t, departure_time=t,
                    stop_id=visit.stop_id, stop_sequence=seq,
                ))
    return trips_rows, stop_times_rows
