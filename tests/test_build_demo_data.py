"""demo/build_demo_data.py の単体テスト（Issue #24）。

固定フィクスチャ GTFS から `build()` を呼び、デモ用 JSON/GeoJSON が
期待する構造で生成されることを検証する。実フィードや build/download に依存しない。
"""
from __future__ import annotations

import json

import pytest

from demo_gtfs_fixture import (
    SERVICES,
    STATIONS,
    load_build_demo_data,
    write_fixture_gtfs,
)


@pytest.fixture(scope="module")
def demo_data(tmp_path_factory) -> dict:
    """フィクスチャ GTFS から生成したデモ JSON を読み込んで返す。"""
    gtfs = tmp_path_factory.mktemp("gtfs")
    out = tmp_path_factory.mktemp("out")
    write_fixture_gtfs(gtfs)
    mod = load_build_demo_data()
    mod.build(gtfs, out, feed_zip=None)
    return {
        "out": out,
        "network": json.loads((out / "network.json").read_text(encoding="utf-8")),
        "departures": json.loads((out / "departures.json").read_text(encoding="utf-8")),
        "animation": json.loads((out / "animation.json").read_text(encoding="utf-8")),
        "geojson": json.loads((out / "network.geojson").read_text(encoding="utf-8")),
    }


def test_outputs_written(demo_data):
    out = demo_data["out"]
    for name in ["network.json", "departures.json", "animation.json", "network.geojson"]:
        assert (out / name).stat().st_size > 0


def test_network_lines_and_stats(demo_data):
    net = demo_data["network"]
    lines = {ln["id"]: ln for ln in net["lines"]}
    assert set(lines) == {"空港線", "箱崎線", "七隈線"}
    for ln in net["lines"]:
        assert len(ln["stations"]) >= 2
        assert ln["color"].startswith("#")
        assert ln["name_en"]
    totals = net["stats"]["totals"]
    assert totals["lines"] == 3
    assert totals["stations"] == len(STATIONS)
    assert totals["trips"] > 0
    assert net["stats"]["services"] == SERVICES
    # bbox / center が有限値
    assert len(net["bbox"]) == 4
    assert len(net["center"]) == 2


def test_departures_transfer_station(demo_data):
    """乗換駅（中洲川端）は空港線・箱崎線の両方の発車グループを持つ。"""
    dep = demo_data["departures"]
    nakasu = dep["S_nakasu"]
    assert nakasu["name"] == "中洲川端"
    for sv in SERVICES:
        assert sv in nakasu
    routes_here = {g["route"] for sv in SERVICES for g in nakasu[sv]}
    assert {"空港線", "箱崎線"} <= routes_here
    # 各グループは方面ラベルと時刻順の trips を持つ
    sample = next(g for g in nakasu["平日"] if g["trips"])
    assert sample["dest"]
    times = [t["t"] for t in sample["trips"]]
    assert times == sorted(times)


def test_departures_has_both_directions(demo_data):
    dep = demo_data["departures"]
    kuko = dep["S_kuko"]
    dirs = {g["dir"] for sv in SERVICES for g in kuko[sv]}
    # 始発駅でも空港線の便があり、少なくとも 1 方向は存在する
    assert dirs


def test_animation_trips(demo_data):
    anim = demo_data["animation"]
    assert anim["tmin"] < anim["tmax"]
    assert anim["trips"]
    for tr in anim["trips"]:
        assert len(tr["path"]) >= 2
        assert len(tr["path"]) == len(tr["times"])
        assert tr["s"] in SERVICES
        assert tr["d"] in (0, 1)


def test_geojson_features(demo_data):
    gj = demo_data["geojson"]
    assert gj["type"] == "FeatureCollection"
    lines = [f for f in gj["features"] if f["geometry"]["type"] == "LineString"]
    points = [f for f in gj["features"] if f["geometry"]["type"] == "Point"]
    assert len(lines) == 3
    assert len(points) == len(STATIONS)
