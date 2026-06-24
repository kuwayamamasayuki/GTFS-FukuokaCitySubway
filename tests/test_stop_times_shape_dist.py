"""stop_times.txt の shape_dist_traveled 付与（Issue #49）。

各停車を shapes.txt のポリライン上へ投影し、補間した累積距離(m)を列に持たせる。
"""
from __future__ import annotations

from pathlib import Path

from fukuoka_gtfs import validate
from fukuoka_gtfs.builders import schedule_builder
from fukuoka_gtfs.builders.shape_dist import project_dist
from fukuoka_gtfs.config import Config
from fukuoka_gtfs.gtfsio import read_csv, write_csv
from fukuoka_gtfs.model import StopVisit, Trip

ROOT = Path(__file__).resolve().parents[1]

# 同一緯度に沿った 1km の直線（経度方向）。dist は実距離におよそ一致する。
LAT = 33.0
# 経度 0.001 度 ≒ 93.3m（緯度33度）。3 点で約 187m の直線。
LINE = [
    (LAT, 130.0000, 0),
    (LAT, 130.0010, 93),
    (LAT, 130.0020, 187),
]


# ---------------------------------------------------------------- project_dist
def test_project_dist_at_vertex_returns_vertex_dist():
    assert project_dist(LINE, LAT, 130.0010) == 93


def test_project_dist_at_segment_midpoint_interpolates():
    # 始点と次点の中点 → dist は 0 と 93 のおよそ中間
    d = project_dist(LINE, LAT, 130.0005)
    assert 40 < d < 53


def test_project_dist_off_line_projects_perpendicular():
    # 線から少し北にずれた点でも、経度位置に対応する dist を返す
    d = project_dist(LINE, LAT + 0.0002, 130.0010)
    assert abs(d - 93) < 5


def test_project_dist_before_start_clamps_to_first():
    assert project_dist(LINE, LAT, 129.9990) == 0


def test_project_dist_single_point():
    assert project_dist([(LAT, 130.0, 42)], LAT, 130.5) == 42


def test_project_dist_empty_returns_none():
    assert project_dist([], LAT, 130.0) is None


# ---------------------------------------------------------------- builder
def _trip(route_id: str, direction_id: int, stop_ids: list[str]) -> Trip:
    visits = [StopVisit(s, 100 + 60 * i) for i, s in enumerate(stop_ids)]
    return Trip(
        route_id=route_id, service_id=f"{route_id}_平日", direction_id=direction_id,
        headsign="x", block_id="", service_segment="平日", visits=visits,
    )


def test_stop_times_header_has_shape_dist_traveled():
    assert "shape_dist_traveled" in schedule_builder.STOP_TIMES_HEADER


def test_build_assigns_increasing_shape_dist():
    shape_map = {("空港線", 0): "S"}
    shape_points = {"S": LINE}
    stop_coords = {"a": (LAT, 130.0000), "b": (LAT, 130.0010), "c": (LAT, 130.0020)}
    _, st = schedule_builder.build(
        [_trip("空港線", 0, ["a", "b", "c"])], shape_map, shape_points, stop_coords)
    dists = [int(r["shape_dist_traveled"]) for r in st]
    assert dists == sorted(dists)            # 非減少
    assert dists[0] == 0 and dists[-1] == 187


def test_build_enforces_non_decreasing_with_running_max():
    """投影が逆行しても running max で単調性を担保する。"""
    shape_map = {("空港線", 0): "S"}
    shape_points = {"S": LINE}
    # b, a の順（座標は逆行）でも shape_dist は減らない
    stop_coords = {"b": (LAT, 130.0010), "a": (LAT, 130.0000)}
    _, st = schedule_builder.build(
        [_trip("空港線", 0, ["b", "a"])], shape_map, shape_points, stop_coords)
    dists = [int(r["shape_dist_traveled"]) for r in st]
    assert dists == sorted(dists)
    assert dists[0] == 93 and dists[1] == 93   # a は b の dist へ引き上げ


def test_build_without_shape_data_leaves_empty():
    _, st = schedule_builder.build([_trip("空港線", 0, ["a", "b"])])
    assert all(r["shape_dist_traveled"] == "" for r in st)


def test_build_unknown_shape_id_leaves_empty():
    """shape_id が空（対応表に無い）の trip は shape_dist 空。"""
    shape_points = {"S": LINE}
    stop_coords = {"a": (LAT, 130.0), "b": (LAT, 130.001)}
    _, st = schedule_builder.build(
        [_trip("謎線", 0, ["a", "b"])], {}, shape_points, stop_coords)
    assert all(r["shape_dist_traveled"] == "" for r in st)


def test_build_missing_stop_coord_leaves_trip_empty():
    """座標欠落の駅を含む trip は安全側に倒し shape_dist 空。"""
    shape_map = {("空港線", 0): "S"}
    shape_points = {"S": LINE}
    stop_coords = {"a": (LAT, 130.0)}        # b の座標が無い
    _, st = schedule_builder.build(
        [_trip("空港線", 0, ["a", "b"])], shape_map, shape_points, stop_coords)
    assert all(r["shape_dist_traveled"] == "" for r in st)


# ---------------------------------------------------------------- 実データ整合
def test_real_shapes_and_stops_yield_monotonic_dist():
    """実際の shapes.txt / stops.txt から各路線の dist が単調かつ範囲内に収まる。"""
    config = Config(ROOT)
    shape_points = schedule_builder.load_shape_points(config.reference_dir / "shapes.txt")
    stop_coords = schedule_builder.load_stop_coords(config.reference_dir / "stops.txt")
    assert shape_points and stop_coords
    # 各 shape の総延長
    for sid, pts in shape_points.items():
        assert pts[0][2] == 0
        assert pts[-1][2] == max(d for _, _, d in pts)


# ---------------------------------------------------------------- validate
def _write_feed_with_dist(d: Path, dists: list[str]) -> None:
    write_csv(d / "stops.txt", ["stop_id", "location_type"],
              [{"stop_id": "a", "location_type": "0"}, {"stop_id": "b", "location_type": "0"}])
    write_csv(d / "routes.txt", ["route_id"], [{"route_id": "R"}])
    write_csv(d / "calendar.txt", ["service_id"], [{"service_id": "g"}])
    write_csv(d / "trips.txt", schedule_builder.TRIPS_HEADER, [dict(
        route_id="R", service_id="g", trip_id="t1", trip_headsign="x",
        direction_id=0, block_id="", shape_id="", wheelchair_accessible=1)])
    write_csv(d / "stop_times.txt", schedule_builder.STOP_TIMES_HEADER, [
        dict(trip_id="t1", arrival_time="05:00:00", departure_time="05:00:00",
             stop_id="a", stop_sequence=1, shape_dist_traveled=dists[0]),
        dict(trip_id="t1", arrival_time="05:05:00", departure_time="05:05:00",
             stop_id="b", stop_sequence=2, shape_dist_traveled=dists[1])])


def test_validate_accepts_non_decreasing_dist(tmp_path):
    _write_feed_with_dist(tmp_path, ["0", "187"])
    assert validate.check_integrity(tmp_path) == []


def test_validate_flags_decreasing_dist(tmp_path):
    _write_feed_with_dist(tmp_path, ["187", "0"])
    issues = validate.check_integrity(tmp_path)
    assert any("shape_dist_traveled" in x and "逆行" in x for x in issues)
