"""demo/opentripplanner/prepare_otp.py の純粋関数の単体テスト（Issue #25）。

ネットワーク/サブプロセスに触れず、bbox 算出・URL 生成・config 生成・OSM クリップ引数・
フィードからの停留所読み取りを検証する。
"""
from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


prep = _load("prepare_otp", "demo/opentripplanner/prepare_otp.py")


def test_bbox_from_stops_order_and_margin():
    stops = [
        {"stop_lat": "33.50", "stop_lon": "130.40"},
        {"stop_lat": "33.60", "stop_lon": "130.50"},
    ]
    # マージン 0 なら外接そのもの（順序: min_lon, min_lat, max_lon, max_lat）
    bbox = prep.bbox_from_stops(stops, margin_km=0.0)
    assert bbox == (130.40, 33.50, 130.50, 33.60)
    # マージンを付けると外側へ広がる
    wide = prep.bbox_from_stops(stops, margin_km=3.0)
    assert wide[0] < 130.40 and wide[1] < 33.50
    assert wide[2] > 130.50 and wide[3] > 33.60


def test_bbox_from_stops_empty_raises():
    with pytest.raises(ValueError):
        prep.bbox_from_stops([], margin_km=1.0)


def test_geofabrik_url():
    assert prep.geofabrik_url("asia/japan/kyushu") == \
        "https://download.geofabrik.de/asia/japan/kyushu-latest.osm.pbf"


def test_otp_jar_url():
    url = prep.otp_jar_url("2.5.0")
    assert url.endswith("/org/opentripplanner/otp/2.5.0/otp-2.5.0-shaded.jar")
    assert url.startswith("https://repo1.maven.org/maven2/")


def test_osmium_extract_args():
    bbox = (130.3, 33.4, 130.6, 33.7)
    args = prep.osmium_extract_args(bbox, Path("in.pbf"), Path("out.pbf"))
    assert args[:2] == ["osmium", "extract"]
    assert "-b" in args
    assert args[args.index("-b") + 1] == "130.3,33.4,130.6,33.7"
    assert "in.pbf" in args
    assert args[-2:] == ["-o", "out.pbf"]


def test_build_config_has_osm_and_feed():
    cfg = prep.build_config("fukuoka.osm.pbf", "feed.zip")
    assert cfg["osm"][0]["source"] == "fukuoka.osm.pbf"
    assert cfg["transitFeeds"][0]["source"] == "feed.zip"
    assert cfg["transitFeeds"][0]["type"] == "gtfs"
    json.dumps(cfg)  # JSON シリアライズ可能


def test_router_and_otp_config_serializable():
    rc = prep.router_config()
    assert "routingDefaults" in rc
    json.dumps(rc)
    json.dumps(prep.otp_config())


def test_read_stops_from_feed(tmp_path):
    feed = tmp_path / "feed.zip"
    stops_txt = (
        "stop_id,stop_name,stop_lat,stop_lon,location_type\n"
        "P1,博多,33.59,130.42,1\n"
        "P2,天神,33.59,130.40,1\n"
        "BAD,座標なし,,,1\n"   # 座標欠落行は除外される
    )
    with zipfile.ZipFile(feed, "w") as zf:
        zf.writestr("stops.txt", stops_txt)
    rows = prep.read_stops_from_feed(feed)
    assert len(rows) == 2
    assert {r["stop_name"] for r in rows} == {"博多", "天神"}
