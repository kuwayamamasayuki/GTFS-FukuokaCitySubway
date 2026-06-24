"""Trip 群から trips.txt と stop_times.txt を生成する。

trip_id は ``{route_id}_{区分}_{direction_id}_{連番:03d}``（区分=平日/土曜/休日）。
連番は出発時刻順に振るため、差分が読みやすく安定する。service_id（trips.txt の列）は
グループ別（例: 空港箱崎_平日）で、calendar.txt の有効期間に対応する。
"""
from __future__ import annotations

from pathlib import Path

from ..excel.time_normalizer import sec_to_gtfs
from ..gtfsio import read_csv
from ..model import Trip
from .shape_dist import project_dist

TRIPS_HEADER = [
    "route_id", "service_id", "trip_id", "trip_headsign",
    "direction_id", "block_id", "shape_id", "wheelchair_accessible",
]
STOP_TIMES_HEADER = [
    "trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence",
    "shape_dist_traveled",
]


def load_shape_points(path: str | Path) -> dict[str, list[tuple[float, float, float]]]:
    """shapes.txt を shape_id → [(lat, lon, dist), ...]（seq 昇順）へ読み込む。"""
    _, rows = read_csv(path)
    by_shape: dict[str, list[tuple[int, float, float, float]]] = {}
    for r in rows:
        by_shape.setdefault(r["shape_id"], []).append((
            int(r["shape_pt_sequence"]), float(r["shape_pt_lat"]),
            float(r["shape_pt_lon"]), float(r["shape_dist_traveled"]),
        ))
    return {
        sid: [(lat, lon, dist) for _, lat, lon, dist in sorted(pts)]
        for sid, pts in by_shape.items()
    }


def load_stop_coords(path: str | Path) -> dict[str, tuple[float, float]]:
    """stops.txt を stop_id → (lat, lon) へ読み込む（座標欠落の行は除く）。"""
    _, rows = read_csv(path)
    coords: dict[str, tuple[float, float]] = {}
    for r in rows:
        lat, lon = r.get("stop_lat", ""), r.get("stop_lon", "")
        if lat and lon:
            coords[r["stop_id"]] = (float(lat), float(lon))
    return coords


def _stop_distances(
    shape_points: list[tuple[float, float, float]],
    stop_coords: dict[str, tuple[float, float]],
    stop_ids: list[str],
) -> list[str] | None:
    """1 便の各停車の shape_dist_traveled（文字列）を返す。算出不能なら None。

    投影は各駅で独立に行うため微小な逆行が起こりうる。running max で単調非減少に
    補正し、整数メートル（shapes.txt と同じ粒度）の文字列へ整える。
    """
    out: list[str] = []
    running = 0.0
    for sid in stop_ids:
        coord = stop_coords.get(sid)
        if coord is None:
            return None                      # 1 駅でも座標欠落なら便全体を空に倒す
        d = project_dist(shape_points, coord[0], coord[1])
        if d is None:
            return None
        running = max(running, d)
        out.append(str(round(running)))
    return out


def build(
    trips: list[Trip],
    shape_map: dict[tuple[str, int], str] | None = None,
    shape_points: dict[str, list[tuple[float, float, float]]] | None = None,
    stop_coords: dict[str, tuple[float, float]] | None = None,
) -> tuple[list[dict], list[dict]]:
    """(trips 行, stop_times 行) を返す。

    shape_map は (route_id, direction_id) → shape_id。対応が無い組み合わせの
    shape_id は空文字（GTFS では shape の紐付けは任意）。

    shape_points（shape_id → 線形）と stop_coords（stop_id → 座標）が与えられ、かつ
    便に shape_id が付く場合は、各停車を線形へ投影して shape_dist_traveled を算出する。
    いずれか欠ける便は shape_dist_traveled を空文字にする。
    """
    shape_map = shape_map or {}
    shape_points = shape_points or {}
    stop_coords = stop_coords or {}
    # (route, service, direction) ごとに出発時刻順へ並べ、連番を振る
    groups: dict[tuple[str, str, int], list[Trip]] = {}
    for t in trips:
        groups.setdefault((t.route_id, t.service_id, t.direction_id), []).append(t)

    trips_rows: list[dict] = []
    stop_times_rows: list[dict] = []
    for (route_id, service_id, direction_id), group in groups.items():
        group.sort(key=lambda t: t.first_sec)
        shape_id = shape_map.get((route_id, direction_id), "")
        for i, trip in enumerate(group, start=1):
            seg = trip.service_segment or service_id
            trip_id = f"{route_id}_{seg}_{direction_id}_{i:03d}"
            trips_rows.append(dict(
                route_id=route_id, service_id=service_id, trip_id=trip_id,
                trip_headsign=trip.headsign, direction_id=direction_id,
                block_id=trip.block_id, shape_id=shape_id,
                wheelchair_accessible=1,
            ))
            dists = None
            pts = shape_points.get(shape_id) if shape_id else None
            if pts:
                dists = _stop_distances(
                    pts, stop_coords, [v.stop_id for v in trip.visits])
            for seq, visit in enumerate(trip.visits, start=1):
                t = sec_to_gtfs(visit.sec)
                stop_times_rows.append(dict(
                    trip_id=trip_id, arrival_time=t, departure_time=t,
                    stop_id=visit.stop_id, stop_sequence=seq,
                    shape_dist_traveled=dists[seq - 1] if dists else "",
                ))
    return trips_rows, stop_times_rows
