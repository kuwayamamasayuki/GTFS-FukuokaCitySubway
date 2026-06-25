"""stops.txt の地上出入口(location_type=2) に関するテスト（Issue #50）。

地下鉄の地上出入口を location_type=2 / parent_station=駅 の stop として追加すると、
徒歩を含むドアtoドアの経路検索ができるようになる。
仕様: https://gtfs.org/documentation/schedule/reference/#stopstxt

出入口名は公式駅立体図から採録、座標は公式が緯度経度を非公開のため親駅座標を基準に
推定した近似値（福岡空港のみ旧フィード由来の実測値）。詳細は
docs/design/station-entrances.md を参照。

ここでは「座標の正確さ」ではなく「構造の正しさ」を検証する:
  - transform_stops が location_type=2 の出入口を追加すること
  - 各出入口の parent_station が実在の駅(location_type=1)を指すこと
  - 座標が福岡近傍 bbox 内かつ親駅の近傍にあること（推定の sanity ガード）
  - 再投入しても重複しないこと（冪等）
  - 公開済みデータ(reference_gtfs / dist / zip)に反映されていること（回帰ガード）
"""
from __future__ import annotations

import csv
import importlib.util
import io
import math
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 福岡市地下鉄が収まる緯度経度の範囲（推定座標の sanity 用）。
LAT_MIN, LAT_MAX = 33.5, 33.65
LON_MIN, LON_MAX = 130.30, 130.46
# 出入口は親駅から概ねこの範囲内（度。約1km強）に居るべき。
MAX_PARENT_DELTA = 0.01

EXPECTED_TOTAL = 197  # reference_gtfs/stops.txt に入る出入口の総数


def _load_seed():
    spec = importlib.util.spec_from_file_location(
        "seed_reference", ROOT / "scripts" / "seed_reference.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_stops(path: Path) -> tuple[list[str], list[dict]]:
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    return list(reader.fieldnames or []), list(reader)


def _stops_text_without_entrances() -> str:
    """現行 reference_gtfs/stops.txt から出入口(location_type=2)を除いた CSV を作る。

    transform_stops は冪等なので、これを入力すると出入口が再付与される（=「追加」の検証）。
    """
    header, rows = _read_stops(ROOT / "reference_gtfs" / "stops.txt")
    kept = [r for r in rows if r["location_type"] != "2"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=header)
    writer.writeheader()
    writer.writerows(kept)
    return buf.getvalue()


def _rows_to_text(header: list[str], rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=header)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _assert_entrances_valid(header: list[str], rows: list[dict]) -> list[dict]:
    """出入口行を取り出し、構造（parent/座標/近傍）を検証して返す。"""
    by_id = {r["stop_id"]: r for r in rows}
    stations = {r["stop_id"] for r in rows if r["location_type"] == "1"}
    entrances = [r for r in rows if r["location_type"] == "2"]
    assert entrances, "出入口(location_type=2)が1件も無い"
    for e in entrances:
        parent = e["parent_station"]
        assert parent in stations, f"{e['stop_id']} の parent {parent} が駅でない"
        assert by_id[parent]["location_type"] == "1"
        lat, lon = float(e["stop_lat"]), float(e["stop_lon"])
        assert LAT_MIN <= lat <= LAT_MAX, f"{e['stop_id']} lat 範囲外: {lat}"
        assert LON_MIN <= lon <= LON_MAX, f"{e['stop_id']} lon 範囲外: {lon}"
        plat, plon = float(by_id[parent]["stop_lat"]), float(by_id[parent]["stop_lon"])
        assert abs(lat - plat) <= MAX_PARENT_DELTA, f"{e['stop_id']} が親駅から遠い(lat)"
        assert abs(lon - plon) <= MAX_PARENT_DELTA, f"{e['stop_id']} が親駅から遠い(lon)"
        assert e["zone_id"] == "", f"{e['stop_id']} に zone_id が付いている"
    return entrances


def test_transform_stops_adds_entrances():
    """出入口の無い stops を取り込むと location_type=2 が付与される。"""
    seed = _load_seed()
    header, rows = seed.transform_stops(_stops_text_without_entrances())
    entrances = _assert_entrances_valid(header, rows)
    assert len(entrances) == EXPECTED_TOTAL


def test_transform_stops_entrances_idempotent():
    """出力を再投入しても出入口が重複しない（冪等）。"""
    seed = _load_seed()
    header, rows = seed.transform_stops(_stops_text_without_entrances())
    n1 = sum(1 for r in rows if r["location_type"] == "2")
    header2, rows2 = seed.transform_stops(_rows_to_text(header, rows))
    n2 = sum(1 for r in rows2 if r["location_type"] == "2")
    assert n1 == n2 == EXPECTED_TOTAL
    ids = [r["stop_id"] for r in rows2 if r["location_type"] == "2"]
    assert len(ids) == len(set(ids)), "出入口 stop_id が重複している"


def test_airport_entrances_use_measured_coords():
    """福岡空港(13) は公式立体図が未公開のため旧フィード由来の実測座標を使う。"""
    seed = _load_seed()
    header, rows = seed.transform_stops(_stops_text_without_entrances())
    by_name = {r["stop_name"]: r for r in rows}
    e = by_name["福岡空港1A番出入口"]
    assert e["location_type"] == "2"
    assert e["parent_station"] == "13"
    assert (e["stop_lat"], e["stop_lon"]) == ("33.596909", "130.448456")


def test_hakata_entrances_split_between_lines():
    """博多複合駅は西側を七隈線博多(37)、東/中央側を空港線博多(11)へ割り当てる。"""
    seed = _load_seed()
    _, rows = seed.transform_stops(_stops_text_without_entrances())
    n11 = [r for r in rows if r["location_type"] == "2" and r["parent_station"] == "11"]
    n37 = [r for r in rows if r["location_type"] == "2" and r["parent_station"] == "37"]
    assert all("西" not in r["stop_name"] for r in n11)
    assert all("西" in r["stop_name"] for r in n37)
    assert len(n37) == 21
    assert len(n11) == 11  # 東1-7 + 中1-4


def test_estimate_entrance_coord_directions():
    """名称の方角語に応じて推定座標が正しい向きへずれる。"""
    seed = _load_seed()
    plat, plon = 33.59, 130.40
    n_lat, _ = seed._estimate_entrance_coord(plat, plon, "北", 0, 4)
    s_lat, _ = seed._estimate_entrance_coord(plat, plon, "南", 0, 4)
    _, e_lon = seed._estimate_entrance_coord(plat, plon, "東", 0, 4)
    _, w_lon = seed._estimate_entrance_coord(plat, plon, "西", 0, 4)
    assert float(n_lat) > plat > float(s_lat)
    assert float(e_lon) > plon > float(w_lon)


def test_estimate_entrance_coord_numbered_spread():
    """方角語が無い連番出入口は駅を中心に放射状へ散る（全点が一致しない）。"""
    seed = _load_seed()
    coords = {seed._estimate_entrance_coord(33.59, 130.40, "", i, 6) for i in range(6)}
    assert len(coords) > 1
    for lat, lon in coords:
        assert math.isclose(float(lat), 33.59, abs_tol=0.01)
        assert math.isclose(float(lon), 130.40, abs_tol=0.01)


def test_reference_stops_has_entrances():
    """reference_gtfs/stops.txt に出入口が入っている（回帰ガード）。"""
    header, rows = _read_stops(ROOT / "reference_gtfs" / "stops.txt")
    entrances = _assert_entrances_valid(header, rows)
    assert len(entrances) == EXPECTED_TOTAL
    names = {r["stop_name"] for r in entrances}
    assert "姪浜北出口" in names
    assert "福岡空港1A番出入口" in names
    assert "博多西1出入口" in names


def test_dist_stops_has_entrances():
    """公開スナップショット dist/stops.txt も出入口を持つ。"""
    header, rows = _read_stops(ROOT / "dist" / "stops.txt")
    assert len(_assert_entrances_valid(header, rows)) == EXPECTED_TOTAL


def test_dist_zip_stops_has_entrances():
    """配布 zip 内の stops.txt も出入口を持つ。"""
    with zipfile.ZipFile(ROOT / "dist" / "FukuokaCitySubway.zip") as z:
        name = next(n for n in z.namelist() if n.endswith("stops.txt"))
        text = z.read(name).decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    header = list(reader.fieldnames or [])
    rows = list(reader)
    assert len(_assert_entrances_valid(header, rows)) == EXPECTED_TOTAL
