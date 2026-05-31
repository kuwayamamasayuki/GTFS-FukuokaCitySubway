"""Issue #18: kepler.gl 運行アニメーション用 GeoJSON 変換の検証。

変換器 gtfs_to_kepler.py は本リポジトリの GTFS を kepler.gl(MIT) の Trip layer が
読める GeoJSON（LineString の各座標に時刻を持たせた形式）へ変換する。実際の
アニメーション再生はブラウザ(GUI)で行うため、ここでは変換ロジックと同梱成果物の
構造をリグレッションとして守る。
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "kepler-animation"
MODULE_PATH = DEMO / "gtfs_to_kepler.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("gtfs_to_kepler", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


kp = _load_module()


def _write_mini_gtfs(base: Path) -> Path:
    """空港線の 1 便（3 駅・深夜便含む）だけの最小 GTFS を作る。"""
    gtfs = base / "gtfs"
    gtfs.mkdir()
    files = {
        "stops.txt": (
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "A,駅A,33.5900,130.4000\n"
            "B,駅B,33.6000,130.4100\n"
            "C,駅C,33.6100,130.4200\n"
        ),
        "routes.txt": (
            "route_id,route_type,route_color\n"
            "L1,1,f7931d\n"
        ),
        "trips.txt": (
            "route_id,service_id,trip_id,trip_headsign\n"
            "L1,WD,T1,筑前前原\n"
            "L1,SAT,T2,姪浜\n"
        ),
        "stop_times.txt": (
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            # 平日便: stop_sequence を逆順で与えて整列を検証
            "T1,05:34:00,05:34:00,C,3\n"
            "T1,05:30:00,05:30:00,A,1\n"
            "T1,05:32:00,05:32:00,B,2\n"
            # 土曜便: 深夜便（24 時超）
            "T2,24:10:00,24:10:00,A,1\n"
            "T2,24:12:00,24:12:00,B,2\n"
        ),
        "calendar.txt": (
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
            "WD,1,1,1,1,1,0,0,20260401,20991231\n"
            "SAT,0,0,0,0,0,1,0,20260401,20991231\n"
        ),
        "calendar_dates.txt": (
            "service_id,date,exception_type\n"
            "WD,20260403,2\n"  # 2026-04-03(金) は運休
        ),
    }
    for name, body in files.items():
        (gtfs / name).write_text(body, encoding="utf-8")
    return gtfs


# --- 純粋関数 ---

def test_time_to_seconds_handles_over_24h():
    assert kp.time_to_seconds("05:30:00") == 5 * 3600 + 30 * 60
    assert kp.time_to_seconds("24:10:00") == 24 * 3600 + 10 * 60


def test_to_epoch_is_deterministic_utc():
    # 1970-01-01 00:00:00 を UTC とみなして 0 秒
    assert kp.to_epoch(dt.datetime(1970, 1, 1, 0, 0, 0)) == 0
    assert kp.to_epoch(dt.datetime(1970, 1, 1, 1, 0, 0)) == 3600


def test_active_services_weekday_saturday_and_exception():
    cal = [
        {"service_id": "WD", "monday": "1", "tuesday": "1", "wednesday": "1",
         "thursday": "1", "friday": "1", "saturday": "0", "sunday": "0",
         "start_date": "20260401", "end_date": "20991231"},
        {"service_id": "SAT", "monday": "0", "tuesday": "0", "wednesday": "0",
         "thursday": "0", "friday": "0", "saturday": "1", "sunday": "0",
         "start_date": "20260401", "end_date": "20991231"},
    ]
    cd = [{"service_id": "WD", "date": "20260403", "exception_type": "2"}]
    assert kp.active_services(cal, cd, dt.date(2026, 4, 1)) == {"WD"}   # 水曜
    assert kp.active_services(cal, cd, dt.date(2026, 4, 4)) == {"SAT"}  # 土曜
    assert kp.active_services(cal, cd, dt.date(2026, 4, 3)) == set()    # 運休


def test_default_service_date_picks_first_running_day(tmp_path):
    gtfs = _write_mini_gtfs(tmp_path)
    cal = kp.read_csv(gtfs / "calendar.txt")
    assert kp.default_service_date(cal) == dt.date(2026, 4, 1)


# --- Trip Feature 生成 ---

def test_build_trip_features_weekday(tmp_path):
    gtfs = _write_mini_gtfs(tmp_path)
    feats = kp.build_trip_features(gtfs, dt.date(2026, 4, 1))  # 水曜=WD のみ
    assert len(feats) == 1  # 平日便 T1 のみ（土曜便は対象外）
    feat = feats[0]
    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] == "LineString"
    coords = feat["geometry"]["coordinates"]
    # 3 駅 → 3 座標。各座標は [経度, 緯度, 高度, epoch] の 4 要素
    assert len(coords) == 3
    assert all(len(c) == 4 for c in coords)
    # stop_sequence 昇順（A→B→C）に整列され、時刻も単調増加
    assert coords[0][:2] == [130.4000, 33.5900]  # 駅A (lon, lat)
    assert coords[2][:2] == [130.4200, 33.6100]  # 駅C
    assert coords[0][3] < coords[1][3] < coords[2][3]
    # 始発 05:30 の epoch
    assert coords[0][3] == kp.to_epoch(dt.datetime(2026, 4, 1, 5, 30, 0))
    # プロパティ
    assert feat["properties"]["route_color"] == "#f7931d"
    assert feat["properties"]["route_type"] == "1"
    assert feat["properties"]["trip_headsign"] == "筑前前原"


def test_build_trip_features_overnight_rolls_to_next_day(tmp_path):
    gtfs = _write_mini_gtfs(tmp_path)
    feats = kp.build_trip_features(gtfs, dt.date(2026, 4, 4))  # 土曜=SAT（深夜便）
    assert len(feats) == 1
    coords = feats[0]["geometry"]["coordinates"]
    # 24:10 → 翌日 00:10
    assert coords[0][3] == kp.to_epoch(dt.datetime(2026, 4, 5, 0, 10, 0))


def test_write_geojson_is_valid_featurecollection(tmp_path):
    gtfs = _write_mini_gtfs(tmp_path)
    feats = kp.build_trip_features(gtfs, dt.date(2026, 4, 1))
    out = tmp_path / "out" / "trips.geojson"
    kp.write_geojson(out, feats)
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["type"] == "FeatureCollection"
    assert isinstance(data["features"], list) and data["features"]


# --- 同梱成果物・ドキュメントのリグレッション ---

def test_committed_artifacts_and_readme_exist():
    assert (DEMO / "README.md").exists(), "README が同梱されていること"
    geojson = DEMO / "data" / "trips.geojson"
    assert geojson.exists(), "生成済み trips.geojson が同梱されていること"
    data = json.loads(geojson.read_text(encoding="utf-8"))
    assert data["type"] == "FeatureCollection"
    feats = data["features"]
    assert feats, "同梱 trips.geojson が非空であること"
    # Trip layer 形式: 各 Feature の座標が 4 要素（時刻つき）
    sample = feats[0]["geometry"]["coordinates"]
    assert all(len(c) == 4 for c in sample), "座標は [経度,緯度,高度,時刻] の 4 要素であること"
