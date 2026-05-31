"""GUI/デモ用テストの固定フィクスチャ GTFS を一時ディレクトリへ書き出すヘルパ。

`build_demo_data.build()` が読む最小限の GTFS を決定的に生成する。
ネットワーク・実フィードのビルドに依存せず、テストを再現可能にするためのもの。

含めている特徴（設計書 Issue #24 の要件）:
  - 3 路線（空港線・箱崎線・七隈線）すべて
  - 乗換駅（中洲川端: stop_code "K03/H01" で空港線・箱崎線の両方に属する）
  - 両方向（direction_id 0/1）
  - 平日・土曜・休日の 3 区分（service_id の接尾辞で表現）
  - 駅名の英語翻訳（translations）
"""
from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def load_build_demo_data():
    """demo/build_demo_data.py をモジュールとして読み込む（demo は非パッケージ）。"""
    path = _ROOT / "demo" / "build_demo_data.py"
    spec = importlib.util.spec_from_file_location("build_demo_data", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_demo_data"] = mod
    spec.loader.exec_module(mod)
    return mod

# (stop_id, stop_code, 駅名, 英語名, lat, lon)
STATIONS = [
    ("S_kuko", "K01", "福岡空港", "Fukuoka Airport", 33.5859, 130.4505),
    ("S_hakata", "K02", "博多", "Hakata", 33.5897, 130.4207),
    ("S_nakasu", "K03/H01", "中洲川端", "Nakasukawabata", 33.5950, 130.4060),
    ("S_gofuku", "H02", "呉服町", "Gofukumachi", 33.6010, 130.4070),
    ("S_hakozaki", "H03", "箱崎宮前", "Hakozakimiyamae", 33.6160, 130.4170),
    ("S_tenjinminami", "N01", "天神南", "Tenjin-Minami", 33.5880, 130.4000),
    ("S_yakuin", "N02", "薬院", "Yakuin", 33.5830, 130.4010),
    ("S_fukudai", "N03", "福大前", "Fukudaimae", 33.5510, 130.3640),
]

# (route_id, route_color)。build は route_id をそのまま路線名として使う。
ROUTES = [
    ("空港線", "e35709"),
    ("箱崎線", "0079c2"),
    ("七隈線", "cba12c"),
]

# 路線 → 方向 0 の駅順（stop_id）。方向 1 は逆順。
LINE_SEQ = {
    "空港線": ["S_kuko", "S_hakata", "S_nakasu"],
    "箱崎線": ["S_nakasu", "S_gofuku", "S_hakozaki"],
    "七隈線": ["S_tenjinminami", "S_yakuin", "S_fukudai"],
}

SERVICES = ["平日", "土曜", "休日"]

_NAME = {sid: name for sid, _code, name, _en, _lat, _lon in STATIONS}

# 路線略号（service_id / trip_id 生成用）
_ABBR = {"空港線": "K", "箱崎線": "H", "七隈線": "N"}

# 区分ごとの始発時刻（時）。便ごとに 1 時間ずらして複数便を作る。
_BASE_HOUR = {"平日": 6, "土曜": 7, "休日": 8}
_TRIPS_PER_DIR = 2  # 区分×方向ごとの便数


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def write_fixture_gtfs(dest: Path) -> None:
    """最小限のデモ用 GTFS を ``dest`` ディレクトリへ書き出す。"""
    dest.mkdir(parents=True, exist_ok=True)

    # stops.txt（親駅のみ。stop_times は親 stop_id を直接参照する）
    stop_rows = [
        [sid, code, name, lat, lon, "1", ""]
        for sid, code, name, _en, lat, lon in STATIONS
    ]
    _write_csv(
        dest / "stops.txt",
        ["stop_id", "stop_code", "stop_name", "stop_lat", "stop_lon",
         "location_type", "parent_station"],
        stop_rows,
    )

    # routes.txt
    _write_csv(
        dest / "routes.txt",
        ["route_id", "route_short_name", "route_type", "route_color"],
        [[rid, rid, "1", color] for rid, color in ROUTES],
    )

    # trips.txt / stop_times.txt
    trip_rows: list[list] = []
    st_rows: list[list] = []
    for rid, color in ROUTES:
        abbr = _ABBR[rid]
        for svc in SERVICES:
            for direction in (0, 1):
                seq = LINE_SEQ[rid] if direction == 0 else list(reversed(LINE_SEQ[rid]))
                headsign = _NAME[seq[-1]]
                for n in range(_TRIPS_PER_DIR):
                    trip_id = f"{abbr}_{svc}_{direction}_{n}"
                    trip_rows.append([trip_id, rid, f"{abbr}_{svc}", direction, headsign])
                    start_min = (_BASE_HOUR[svc] + n) * 60
                    for order, sid in enumerate(seq):
                        m = start_min + order * 3
                        dep = f"{m // 60:02d}:{m % 60:02d}:00"
                        st_rows.append([trip_id, order + 1, sid, dep, dep])

    _write_csv(
        dest / "trips.txt",
        ["trip_id", "route_id", "service_id", "direction_id", "trip_headsign"],
        trip_rows,
    )
    _write_csv(
        dest / "stop_times.txt",
        ["trip_id", "stop_sequence", "stop_id", "arrival_time", "departure_time"],
        st_rows,
    )

    # translations.txt（駅名 → 英語）
    _write_csv(
        dest / "translations.txt",
        ["table_name", "field_name", "field_value", "language", "translation"],
        [["stops", "stop_name", name, "en", en]
         for _sid, _code, name, en, _lat, _lon in STATIONS],
    )
