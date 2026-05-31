#!/usr/bin/env python3
"""GTFS-JP フィードを kepler.gl の Trip layer 用 GeoJSON に変換する。

[kepler.gl](https://github.com/keplergl/kepler.gl)（MIT License, Uber/vis.gl）は、
ブラウザだけで動く既製の地理空間可視化ツール。LineString の各座標に時刻を持たせた
GeoJSON（Trip layer 形式）を読み込ませると、スケジュールどおりに動く列車の
**運行アニメーション**を再生できる。

Trip layer 形式: 各 Feature は LineString で、座標は
``[経度, 緯度, 高度, 時刻(Unix epoch 秒)]`` の 4 要素。1 便（trip）= 1 Feature とし、
停車駅ごとに 1 座標を、その駅の発着時刻で打つ。kepler.gl はこの 4 要素目を
検出して自動的に Trip layer（時間アニメーション）を作る。

既定では本リポジトリが生成した ``build/gtfs/`` を入力に、指定日（省略時は運行開始日
以降の最初の運行日）の全便を ``data/trips.geojson`` に書き出す。追加の依存はなく
Python 標準ライブラリのみで動く。
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

# kepler.gl が時刻を Unix epoch 秒として解釈するための基準時刻（naive を UTC とみなす）。
_EPOCH = dt.datetime(1970, 1, 1)
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def read_csv(path: Path) -> list[dict]:
    """GTFS のテキストファイルを行 dict のリストとして読む（BOM 許容）。"""
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def time_to_seconds(hms: str) -> int:
    """GTFS 時刻 ``HH:MM:SS``（24 時超を含む）を秒に変換する。"""
    h, m, s = (int(x) for x in hms.strip().split(":"))
    return h * 3600 + m * 60 + s


def parse_date(value: str) -> dt.date:
    """``YYYYMMDD`` または ``YYYY-MM-DD`` を date に変換する。"""
    value = value.strip()
    fmt = "%Y%m%d" if len(value) == 8 and "-" not in value else "%Y-%m-%d"
    return dt.datetime.strptime(value, fmt).date()


def to_epoch(when: dt.datetime) -> int:
    """naive datetime を（UTC とみなした）Unix epoch 秒に変換する。"""
    return int((when - _EPOCH).total_seconds())


def active_services(
    calendar_rows: list[dict],
    calendar_dates_rows: list[dict],
    target: dt.date,
) -> set[str]:
    """指定日に運行する service_id 集合を calendar / calendar_dates から求める。"""
    active: set[str] = set()
    dow = _WEEKDAYS[target.weekday()]
    ymd = target.strftime("%Y%m%d")
    for row in calendar_rows:
        if parse_date(row["start_date"]) <= target <= parse_date(row["end_date"]) and row.get(dow) == "1":
            active.add(row["service_id"])
    for row in calendar_dates_rows:
        if row.get("date") != ymd:
            continue
        if row.get("exception_type") == "1":
            active.add(row["service_id"])
        elif row.get("exception_type") == "2":
            active.discard(row["service_id"])
    return active


def default_service_date(calendar_rows: list[dict]) -> dt.date:
    """calendar の運行開始日以降で、運行便のある最初の日を返す。"""
    starts = [parse_date(r["start_date"]) for r in calendar_rows]
    base = min(starts) if starts else dt.date.today()
    for offset in range(14):
        day = base + dt.timedelta(days=offset)
        if active_services(calendar_rows, [], day):
            return day
    return base


def build_trip_features(gtfs_dir: Path, target: dt.date) -> list[dict]:
    """指定日の全便を kepler.gl Trip layer の Feature（LineString）に変換する。

    1 便 = 1 Feature。座標は停車駅ごとに ``[経度, 緯度, 0, epoch秒]``。
    深夜便（24 時超）は ``date + 経過秒`` として翌日にまたがる時刻になる。
    便は trip_id 昇順で安定して並べる。
    """
    stops = read_csv(gtfs_dir / "stops.txt")
    routes = {r["route_id"]: r for r in read_csv(gtfs_dir / "routes.txt")}
    trips = {t["trip_id"]: t for t in read_csv(gtfs_dir / "trips.txt")}
    calendar_rows = read_csv(gtfs_dir / "calendar.txt")
    cd_path = gtfs_dir / "calendar_dates.txt"
    calendar_dates_rows = read_csv(cd_path) if cd_path.exists() else []

    coords = {
        s["stop_id"]: (float(s["stop_lon"]), float(s["stop_lat"]))
        for s in stops
        if s.get("stop_lat") and s.get("stop_lon")
    }
    services = active_services(calendar_rows, calendar_dates_rows, target)

    by_trip: dict[str, list[dict]] = defaultdict(list)
    for st in read_csv(gtfs_dir / "stop_times.txt"):
        by_trip[st["trip_id"]].append(st)

    base = dt.datetime(target.year, target.month, target.day)
    features: list[dict] = []
    for trip_id in sorted(by_trip):
        trip = trips.get(trip_id)
        if trip is None or trip.get("service_id") not in services:
            continue
        route = routes.get(trip.get("route_id"), {})
        times = sorted(by_trip[trip_id], key=lambda r: int(r["stop_sequence"]))
        line: list[list[float]] = []
        for st in times:
            if st["stop_id"] not in coords:
                continue
            lon, lat = coords[st["stop_id"]]
            # 出発時刻優先（始発駅以外も走行アニメは出発時刻で前進させる）
            hms = st.get("departure_time") or st.get("arrival_time")
            epoch = to_epoch(base + dt.timedelta(seconds=time_to_seconds(hms)))
            line.append([lon, lat, 0, epoch])
        if len(line) < 2:
            continue
        color = route.get("route_color", "") or ""
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "trip_id": trip_id,
                    "route_id": trip.get("route_id", ""),
                    "route_color": f"#{color}" if color else "",
                    "route_type": route.get("route_type", ""),
                    "trip_headsign": trip.get("trip_headsign", ""),
                },
                "geometry": {"type": "LineString", "coordinates": line},
            }
        )
    return features


def write_geojson(out_path: Path, features: list[dict]) -> None:
    """Feature 列を FeatureCollection として書き出す。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fc = {"type": "FeatureCollection", "features": features}
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False)
        f.write("\n")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gtfs", type=Path, default=Path("build/gtfs"),
                        help="入力 GTFS ディレクトリ（既定 build/gtfs）")
    parser.add_argument("--out", type=Path,
                        default=Path("demo/kepler-animation/data/trips.geojson"),
                        help="出力 GeoJSON パス")
    parser.add_argument("--date", help="アニメーション対象日（YYYY-MM-DD）。省略時は自動選択")
    args = parser.parse_args(argv)

    calendar_rows = read_csv(args.gtfs / "calendar.txt")
    target = parse_date(args.date) if args.date else default_service_date(calendar_rows)

    features = build_trip_features(args.gtfs, target)
    write_geojson(args.out, features)
    print(f"{target}: {len(features)} 便を {args.out} に書き出しました。")


if __name__ == "__main__":
    main()
