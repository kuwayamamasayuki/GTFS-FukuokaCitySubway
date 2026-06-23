"""Issue #53: 七隈線博多駅の緯度経度を空港線博多駅とは別に設定する。

空港線博多(K11, id 11)と七隈線博多(N18)は物理的に少し離れているため、七隈線博多を
独立した駅マーカー(親 id 37)として別座標で持たせる。ただし運賃ゾーンは空港線博多と
同一(zone_id=11)に保つ。

設計の非対称性（11 は K11/N18 のまま据え置き、37 は N18 のみ）の理由は
docs/design/hakata-nanakuma-station.md を参照。

このテストは以下を保証する:
  * 公開データ(reference_gtfs/stops.txt / dist/stops.txt)が新モデルを持つ
  * 再シード(seed_reference.transform_stops)が同じ結果を再現する
  * 親子(parent_station)の整合性が壊れていない
"""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF_STOPS = ROOT / "reference_gtfs" / "stops.txt"
DIST_STOPS = ROOT / "dist" / "stops.txt"

# 七隈線博多(N18) の独立駅マーカー
NANAKUMA_HAKATA_ID = "37"
NANAKUMA_LAT = "33.589616"
NANAKUMA_LON = "130.418599"
NANAKUMA_PLATFORMS = ("37_3", "37_4")
# 空港線博多(K11, id 11) の座標（七隈線とは別であること）
AIRPORT_HAKATA_LAT = "33.59013"
AIRPORT_HAKATA_LON = "130.420616"
FARE_ZONE = "11"  # 運賃ゾーンは両博多で同一


def _rows(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8") as f:
        return {r["stop_id"]: r for r in csv.DictReader(f)}


def _load_seed_reference():
    spec = importlib.util.spec_from_file_location(
        "seed_reference", ROOT / "scripts" / "seed_reference.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


# --- 公開データ(reference_gtfs/stops.txt) ---------------------------------

def test_reference_has_independent_nanakuma_parent():
    """七隈線博多 親 id 37(N18) が独立駅として存在し、空港線とは別座標を持つ。"""
    by_id = _rows(REF_STOPS)
    assert NANAKUMA_HAKATA_ID in by_id, "親 37 が reference_gtfs/stops.txt に無い"
    p = by_id[NANAKUMA_HAKATA_ID]
    assert p["stop_code"] == "N18"
    assert p["stop_name"] == "博多"
    assert p["location_type"] == "1"
    assert p["parent_station"] == ""
    assert (p["stop_lat"], p["stop_lon"]) == (NANAKUMA_LAT, NANAKUMA_LON)
    assert p["zone_id"] == FARE_ZONE  # 運賃ゾーンは空港線博多と同一


def test_reference_nanakuma_platforms_belong_to_parent_37():
    """七隈線ホーム 37_3/37_4 が親 37 配下で、七隈線座標・運賃ゾーン11 を持つ。"""
    by_id = _rows(REF_STOPS)
    for pid in NANAKUMA_PLATFORMS:
        assert pid in by_id, f"{pid} が無い"
        c = by_id[pid]
        assert c["location_type"] == "0"
        assert c["parent_station"] == NANAKUMA_HAKATA_ID
        assert (c["stop_lat"], c["stop_lon"]) == (NANAKUMA_LAT, NANAKUMA_LON)
        assert c["zone_id"] == FARE_ZONE


def test_reference_old_nanakuma_platforms_removed():
    """旧・空港線博多配下の七隈線ホーム 11_3/11_4 は廃止されている。"""
    by_id = _rows(REF_STOPS)
    assert "11_3" not in by_id
    assert "11_4" not in by_id


def test_reference_airport_hakata_unchanged():
    """空港線博多(11)は K11/N18(ジャンクション)・従来座標のまま据え置き。"""
    by_id = _rows(REF_STOPS)
    p = by_id["11"]
    assert p["stop_code"] == "K11/N18"  # split_segments のジャンクション判定に必須
    assert p["location_type"] == "1"
    assert (p["stop_lat"], p["stop_lon"]) == (AIRPORT_HAKATA_LAT, AIRPORT_HAKATA_LON)
    # 空港線ホームは 11 配下のまま、空港線座標
    for pid in ("11_1", "11_2"):
        c = by_id[pid]
        assert c["parent_station"] == "11"
        assert (c["stop_lat"], c["stop_lon"]) == (AIRPORT_HAKATA_LAT, AIRPORT_HAKATA_LON)


def test_two_hakata_coordinates_differ():
    """空港線博多と七隈線博多の座標が実際に異なる（Issue #53 の目的）。"""
    by_id = _rows(REF_STOPS)
    air = (by_id["11"]["stop_lat"], by_id["11"]["stop_lon"])
    nana = (by_id["37"]["stop_lat"], by_id["37"]["stop_lon"])
    assert air != nana


def test_parent_station_integrity():
    """全子ホームの parent_station が実在する親(location_type=1)を指す。"""
    by_id = _rows(REF_STOPS)
    parents = {sid for sid, r in by_id.items() if r["location_type"] == "1"}
    for sid, r in by_id.items():
        ps = r["parent_station"]
        if ps:
            assert ps in parents, f"{sid} の parent_station={ps} が実在しない"


# --- 再シード(seed_reference.transform_stops) -----------------------------

def test_seed_transform_reproduces_nanakuma_model():
    """上流フィード(七隈線延伸前)から transform_stops が新モデルを再現する。"""
    seed = _load_seed_reference()
    # 上流(2019)は空港線のみ。博多 11 と空港線ホーム 11_1/11_2 を持つ最小入力。
    header = ("stop_id,stop_code,stop_name,stop_lat,stop_lon,zone_id,"
              "stop_url,location_type,parent_station,wheelchair_boarding")
    text = "\n".join([
        header,
        f"11,K11,博多,{AIRPORT_HAKATA_LAT},{AIRPORT_HAKATA_LON},11,,1,,1",
        f"11_1,,博多,{AIRPORT_HAKATA_LAT},{AIRPORT_HAKATA_LON},11,,0,11,1",
        f"11_2,,博多,{AIRPORT_HAKATA_LAT},{AIRPORT_HAKATA_LON},11,,0,11,1",
    ]) + "\n"
    _, rows = seed.transform_stops(text)
    by_id = {r["stop_id"]: r for r in rows}
    # 11 は K11/N18 へ更新され、座標は据え置き
    assert by_id["11"]["stop_code"] == "K11/N18"
    assert (by_id["11"]["stop_lat"], by_id["11"]["stop_lon"]) == (AIRPORT_HAKATA_LAT, AIRPORT_HAKATA_LON)
    # 37 と 37_3/37_4 が七隈線座標・zone11 で生成される
    assert by_id["37"]["stop_code"] == "N18"
    assert by_id["37"]["location_type"] == "1"
    assert (by_id["37"]["stop_lat"], by_id["37"]["stop_lon"]) == (NANAKUMA_LAT, NANAKUMA_LON)
    assert by_id["37"]["zone_id"] == FARE_ZONE
    for pid in NANAKUMA_PLATFORMS:
        assert by_id[pid]["parent_station"] == "37"
        assert (by_id[pid]["stop_lat"], by_id[pid]["stop_lon"]) == (NANAKUMA_LAT, NANAKUMA_LON)
    # 旧 11_3/11_4 は作られない
    assert "11_3" not in by_id and "11_4" not in by_id


def test_seed_transform_is_idempotent():
    """既に新モデルを含むデータを再変換しても 37 系を重複生成しない。"""
    seed = _load_seed_reference()
    with REF_STOPS.open(encoding="utf-8") as f:
        text = f.read()
    _, rows = seed.transform_stops(text)
    ids = [r["stop_id"] for r in rows]
    assert ids.count("37") == 1
    assert ids.count("37_3") == 1 and ids.count("37_4") == 1


# --- 公開スナップショット(dist/stops.txt) との同期 -------------------------

def test_dist_stops_in_sync_with_reference():
    """dist/stops.txt が reference_gtfs/stops.txt と同じ博多モデルを持つ。"""
    by_id = _rows(DIST_STOPS)
    assert by_id["37"]["stop_code"] == "N18"
    assert (by_id["37"]["stop_lat"], by_id["37"]["stop_lon"]) == (NANAKUMA_LAT, NANAKUMA_LON)
    assert "11_3" not in by_id and "11_4" not in by_id
    for pid in NANAKUMA_PLATFORMS:
        assert by_id[pid]["parent_station"] == "37"
