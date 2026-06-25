"""stops.txt の地上出入口(location_type=2) に関するテスト（Issue #50）。

地下鉄の地上出入口を location_type=2 / parent_station=駅 の stop として追加すると、
経路検索エンジンが最寄り出入口を含む徒歩経路を案内でき、ドアtoドアの正確な経路案内が
できる。仕様: https://gtfs.org/documentation/schedule/reference/#stopstxt

出入口データ（名称・緯度経度・親駅・wheelchair_boarding）は、ユーザー本人が実測登録した
旧フィード（git 0e19136, 2018年版）由来の実測値で scripts/data/legacy_entrances.csv に
置き、seed_reference.transform_stops が取り込む。対象は当時の全35駅(parent 1〜35)・計198。
詳細は docs/design/station-entrances.md を参照。

検証内容:
  - transform_stops が location_type=2 の出入口を追加すること
  - 各出入口の parent_station が実在の駅(location_type=1)を指すこと
  - 座標が福岡近傍 bbox 内かつ親駅の近傍にあること（実測値の sanity ガード）
  - 再投入しても重複しないこと（冪等）
  - 公開済みデータ(reference_gtfs / dist / zip)に反映されていること（回帰ガード）
"""
from __future__ import annotations

import csv
import importlib.util
import io
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 福岡市地下鉄が収まる緯度経度の範囲（座標の sanity 用）。
LAT_MIN, LAT_MAX = 33.5, 33.65
LON_MIN, LON_MAX = 130.30, 130.46
# 出入口は親駅から概ねこの範囲内（度。約1km強。博多の連絡通路出入口を含む）。
MAX_PARENT_DELTA = 0.01

EXPECTED_TOTAL = 198  # 旧フィード由来の出入口総数（parent 1〜35）


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
    return entrances


def test_legacy_entrances_csv_loads():
    """データファイルが 198 件の出入口を返す。"""
    seed = _load_seed()
    entrances = seed.load_legacy_entrances()
    assert len(entrances) == EXPECTED_TOTAL
    assert all(e["location_type"] == "2" for e in entrances)
    # 親駅は当時の全35駅。
    assert {e["parent_station"] for e in entrances} == {str(i) for i in range(1, 36)}


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


def test_entrances_are_measured_values():
    """旧フィード由来の実測座標・名称がそのまま入っている。"""
    seed = _load_seed()
    _, rows = seed.transform_stops(_stops_text_without_entrances())
    by_id = {r["stop_id"]: r for r in rows}
    meinohama = by_id["1_Nex"]
    assert meinohama["stop_name"] == "姪浜北出入口"
    assert meinohama["parent_station"] == "1"
    assert (meinohama["stop_lat"], meinohama["stop_lon"]) == ("33.583835", "130.324827")
    airport = by_id["13_3ex"]
    assert airport["stop_name"] == "福岡空港3番出入口"
    assert (airport["stop_lat"], airport["stop_lon"]) == ("33.596709", "130.448961")


def test_reference_stops_has_entrances():
    """reference_gtfs/stops.txt に出入口が入っている（回帰ガード）。"""
    header, rows = _read_stops(ROOT / "reference_gtfs" / "stops.txt")
    entrances = _assert_entrances_valid(header, rows)
    assert len(entrances) == EXPECTED_TOTAL
    names = {r["stop_name"] for r in entrances}
    assert "姪浜北出入口" in names
    assert "博多西1番出入口" in names
    assert "福岡空港1A番出入口" in names


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
