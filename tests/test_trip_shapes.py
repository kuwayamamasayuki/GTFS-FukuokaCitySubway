"""trips.txt の shape_id 付与（Issue #48）。

shapes.txt の 3 路線×2 方向=6 本の線形を、(route_id, direction_id) から
機械的に trip へ紐付ける。割り当て表は config/routes.yaml の trip_shapes に持つ。
"""
from __future__ import annotations

from pathlib import Path

from fukuoka_gtfs import validate
from fukuoka_gtfs.builders import schedule_builder
from fukuoka_gtfs.config import Config
from fukuoka_gtfs.gtfsio import read_csv, write_csv
from fukuoka_gtfs.model import StopVisit, Trip

ROOT = Path(__file__).resolve().parents[1]


def _trip(route_id: str, direction_id: int) -> Trip:
    return Trip(
        route_id=route_id, service_id=f"{route_id}_平日", direction_id=direction_id,
        headsign="x", block_id="", service_segment="平日",
        visits=[StopVisit("a", 100), StopVisit("b", 200)],
    )


# ---------------------------------------------------------------- builder
def test_trips_header_has_shape_id():
    assert "shape_id" in schedule_builder.TRIPS_HEADER


def test_build_assigns_shape_id_from_map():
    shape_map = {("空港線", 0): "空港線（福岡空港方面行き）"}
    trips_rows, _ = schedule_builder.build([_trip("空港線", 0)], shape_map)
    assert trips_rows[0]["shape_id"] == "空港線（福岡空港方面行き）"


def test_build_unknown_combo_gets_empty_shape_id():
    """対応表に無い組み合わせは空文字（GTFS で shape 任意のため）。"""
    trips_rows, _ = schedule_builder.build([_trip("謎線", 0)], {("空港線", 0): "s"})
    assert trips_rows[0]["shape_id"] == ""


def test_build_without_map_is_backward_compatible():
    trips_rows, _ = schedule_builder.build([_trip("空港線", 0)])
    assert trips_rows[0]["shape_id"] == ""


# ---------------------------------------------------------------- config
def test_config_trip_shapes_covers_all_six_shapes():
    """config の trip_shapes が shapes.txt の 6 本を過不足なく指す。"""
    config = Config(ROOT)
    mapping = config.trip_shapes
    _, shape_rows = read_csv(config.reference_dir / "shapes.txt")
    shape_ids = {r["shape_id"] for r in shape_rows}

    assert set(mapping.values()) == shape_ids          # 全 shape を参照
    assert len(mapping) == len(shape_ids) == 6         # 1 対 1


def test_config_trip_shapes_direction_assignment():
    """方面割り当ては directions（0=空港/貝塚/博多, 1=姪浜/橋本）と整合する。"""
    mapping = Config(ROOT).trip_shapes
    assert mapping[("空港線", 0)] == "空港線（福岡空港方面行き）"
    assert mapping[("空港線", 1)] == "空港線（姪浜方面行き）"
    assert mapping[("箱崎線", 0)] == "箱崎線（貝塚方面行き）"
    assert mapping[("箱崎線", 1)] == "箱崎線（中洲川端方面行き）"
    assert mapping[("七隈線", 0)] == "七隈線（天神南方面行き）"
    assert mapping[("七隈線", 1)] == "七隈線（橋本方面行き）"


# ---------------------------------------------------------------- validate
def _write_minimal_feed(d: Path, trip_shape_id: str) -> None:
    """check_integrity を通る最小フィードを書く。trips の shape_id だけ可変。"""
    write_csv(d / "stops.txt", ["stop_id", "location_type"],
              [{"stop_id": "a", "location_type": "0"}, {"stop_id": "b", "location_type": "0"}])
    write_csv(d / "routes.txt", ["route_id"], [{"route_id": "空港線"}])
    write_csv(d / "calendar.txt", ["service_id"], [{"service_id": "g"}])
    write_csv(d / "shapes.txt", ["shape_id", "shape_pt_sequence"],
              [{"shape_id": "空港線（福岡空港方面行き）", "shape_pt_sequence": "1"}])
    write_csv(d / "trips.txt", schedule_builder.TRIPS_HEADER, [dict(
        route_id="空港線", service_id="g", trip_id="t1", trip_headsign="x",
        direction_id=0, block_id="", shape_id=trip_shape_id, wheelchair_accessible=1)])
    write_csv(d / "stop_times.txt", schedule_builder.STOP_TIMES_HEADER, [
        dict(trip_id="t1", arrival_time="05:00:00", departure_time="05:00:00", stop_id="a", stop_sequence=1),
        dict(trip_id="t1", arrival_time="05:05:00", departure_time="05:05:00", stop_id="b", stop_sequence=2)])


def test_validate_accepts_known_shape_id(tmp_path):
    _write_minimal_feed(tmp_path, "空港線（福岡空港方面行き）")
    assert validate.check_integrity(tmp_path) == []


def test_validate_flags_unknown_shape_id(tmp_path):
    _write_minimal_feed(tmp_path, "存在しない線形")
    issues = validate.check_integrity(tmp_path)
    assert any("未知の shape_id" in x and "存在しない線形" in x for x in issues)
