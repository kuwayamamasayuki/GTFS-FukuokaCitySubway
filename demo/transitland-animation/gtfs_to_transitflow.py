#!/usr/bin/env python3
"""GTFS-JP フィードを TransitFlow（transitland-processing-animation）の入力に変換する。

TransitFlow 本家（https://github.com/transitland/transitland-processing-animation）は
Mapzen 期の Transitland API v1 からスケジュールを取得してアニメーションを描くツールだが、
その API は既に廃止されている。本スクリプトは **本リポジトリが生成したローカル GTFS**
（既定で ``build/gtfs/``）を直接読み込み、TransitFlow の Processing スケッチがそのまま
読める入力データを生成することで、廃止 API に依存せず福岡市地下鉄の運行アニメーションを
作れるようにする。

生成物（``<out>/data/`` 配下、TransitFlow の ``sketches/<name>/<date>/data/`` と同じ構造）:
  output.csv                   全便を「駅間セグメント」に分解した運行データ
                               （start/end の時刻・緯度経度・所要秒・車種・方位）
  vehicle_counts/<mode>_<frames>.csv   各フレーム時点で走行中の車両数（スタックチャート用）

``--template`` に本家 ``transitflow/templates/template.pde`` を渡すと、緯度経度の中心や
総フレーム数を差し込んだ ``sketch.pde`` も生成する（本家のソースは同梱しない）。
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
from collections import defaultdict
from pathlib import Path
from string import Template

# GTFS の route_type（数値）→ TransitFlow が色分けに使う車種名。
# 本家スケッチの switch(vehicle_type) の case 名に合わせている。
ROUTE_TYPE_TO_VEHICLE = {
    "0": "tram",
    "1": "metro",
    "2": "rail",
    "3": "bus",
    "4": "ferry",
    "5": "cablecar",
    "6": "gondola",
    "7": "funicular",
}

# vehicle_counts として書き出すモード（本家スケッチが読む 7 ファイルに対応）。
# "vehicles" は全車種合計。
COUNT_MODES = ["vehicles", "buses", "trams", "cablecars", "metros", "trains", "ferries"]
# 各 vehicle_counts ファイルに集計する車種名（"vehicles" は合計なので None）。
COUNT_MODE_VEHICLE = {
    "buses": "bus",
    "trams": "tram",
    "cablecars": "cablecar",
    "metros": "metro",
    "trains": "rail",
    "ferries": "ferry",
    "vehicles": None,
}

DEFAULT_FRAMES = 3600  # 本家既定（3600 フレーム = 60 秒のアニメーション）
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


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


def calc_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """2 点間の方位角（度, 0=北・時計回り）。本家 calc_bearing_between_points と同じ式。"""
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    d_lon = lon2 - lon1
    d_phi = math.log(math.tan(lat2 / 2.0 + math.pi / 4.0) / math.tan(lat1 / 2.0 + math.pi / 4.0))
    if abs(d_lon) > math.pi:
        d_lon = -(2.0 * math.pi - d_lon) if d_lon > 0.0 else (2.0 * math.pi + d_lon)
    return (math.degrees(math.atan2(d_lon, d_phi)) + 360.0) % 360.0


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
        start = parse_date(row["start_date"])
        end = parse_date(row["end_date"])
        if start <= target <= end and row.get(dow) == "1":
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


def build_segments(gtfs_dir: Path, target: dt.date) -> list[dict]:
    """指定日の全便を「駅間セグメント」に分解し、start_time 昇順で返す。

    各セグメントは output.csv の 1 行に対応する。深夜便（24 時超）は
    ``date + 経過秒`` として翌日にまたがる datetime になる。
    """
    stops = read_csv(gtfs_dir / "stops.txt")
    routes = {r["route_id"]: r for r in read_csv(gtfs_dir / "routes.txt")}
    trips = {t["trip_id"]: t for t in read_csv(gtfs_dir / "trips.txt")}
    calendar_rows = read_csv(gtfs_dir / "calendar.txt")
    cd_path = gtfs_dir / "calendar_dates.txt"
    calendar_dates_rows = read_csv(cd_path) if cd_path.exists() else []

    coords = {
        s["stop_id"]: (float(s["stop_lat"]), float(s["stop_lon"]))
        for s in stops
        if s.get("stop_lat") and s.get("stop_lon")
    }
    services = active_services(calendar_rows, calendar_dates_rows, target)

    # trip_id ごとに stop_times を stop_sequence 昇順でまとめる。
    by_trip: dict[str, list[dict]] = defaultdict(list)
    for st in read_csv(gtfs_dir / "stop_times.txt"):
        by_trip[st["trip_id"]].append(st)

    base = dt.datetime(target.year, target.month, target.day)
    segments: list[dict] = []
    for trip_id, times in by_trip.items():
        trip = trips.get(trip_id)
        if trip is None or trip.get("service_id") not in services:
            continue
        route = routes.get(trip.get("route_id"), {})
        vehicle = ROUTE_TYPE_TO_VEHICLE.get(route.get("route_type", ""), "rail")
        times.sort(key=lambda r: int(r["stop_sequence"]))
        for a, b in zip(times, times[1:]):
            if a["stop_id"] not in coords or b["stop_id"] not in coords:
                continue
            origin_sec = time_to_seconds(a["departure_time"])
            dest_sec = time_to_seconds(b["arrival_time"])
            slat, slon = coords[a["stop_id"]]
            elat, elon = coords[b["stop_id"]]
            segments.append(
                {
                    "start_time": base + dt.timedelta(seconds=origin_sec),
                    "start_lat": slat,
                    "start_lon": slon,
                    "end_time": base + dt.timedelta(seconds=dest_sec),
                    "end_lat": elat,
                    "end_lon": elon,
                    "duration": dest_sec - origin_sec,
                    "route_type": vehicle,
                    "bearing": calc_bearing(slat, slon, elat, elon),
                }
            )
    segments.sort(key=lambda s: s["start_time"])
    return segments


def vehicle_counts(segments: list[dict], frames: int) -> dict[str, list[tuple[int, dt.datetime, int]]]:
    """各フレーム時点で走行中の車両数をモード別に数える。

    本家と同じく「end_time > t かつ start_time <= t」を走行中とみなす。
    戻り値は COUNT_MODES ごとに (frame, time, count) のリスト。
    """
    counts: dict[str, list[tuple[int, dt.datetime, int]]] = {m: [] for m in COUNT_MODES}
    if not segments:
        return counts
    min_time = min(s["start_time"] for s in segments)
    max_time = max(s["end_time"] for s in segments)
    step = (max_time - min_time) / frames
    for i in range(frames):
        t = min_time + i * step
        on_road = [s for s in segments if s["start_time"] <= t < s["end_time"]]
        for mode in COUNT_MODES:
            target_vehicle = COUNT_MODE_VEHICLE[mode]
            n = len(on_road) if target_vehicle is None else sum(
                1 for s in on_road if s["route_type"] == target_vehicle
            )
            counts[mode].append((i, t, n))
    return counts


def write_outputs(out_dir: Path, segments: list[dict], frames: int) -> dict[str, int]:
    """output.csv と vehicle_counts/*.csv を out_dir/data 配下に書き出す。"""
    data_dir = out_dir / "data"
    counts_dir = data_dir / "vehicle_counts"
    counts_dir.mkdir(parents=True, exist_ok=True)

    fields = [
        "start_time", "start_lat", "start_lon",
        "end_time", "end_lat", "end_lon",
        "duration", "route_type", "bearing",
    ]
    with (data_dir / "output.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for s in segments:
            w.writerow(
                {
                    "start_time": s["start_time"].strftime(_DATETIME_FMT),
                    "start_lat": f"{s['start_lat']:.6f}",
                    "start_lon": f"{s['start_lon']:.6f}",
                    "end_time": s["end_time"].strftime(_DATETIME_FMT),
                    "end_lat": f"{s['end_lat']:.6f}",
                    "end_lon": f"{s['end_lon']:.6f}",
                    "duration": s["duration"],
                    "route_type": s["route_type"],
                    "bearing": f"{s['bearing']:.4f}",
                }
            )

    counts = vehicle_counts(segments, frames)
    for mode in COUNT_MODES:
        path = counts_dir / f"{mode}_{frames}.csv"
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["frame", "time", "count"])
            for frame, t, n in counts[mode]:
                w.writerow([frame, t.strftime(_DATETIME_FMT), n])

    return {"segments": len(segments), "frames": frames}


def write_sketch(out_dir: Path, template_path: Path, name: str, target: dt.date,
                 frames: int, segments: list[dict], recording: bool) -> None:
    """本家 template.pde に中心座標・フレーム数等を差し込んで sketch.pde を生成する。"""
    lats = [s["start_lat"] for s in segments] + [s["end_lat"] for s in segments]
    lons = [s["start_lon"] for s in segments] + [s["end_lon"] for s in segments]
    avg_lat = (min(lats) + max(lats)) / 2.0 if lats else 0.0
    avg_lon = (min(lons) + max(lons)) / 2.0 if lons else 0.0
    tmpl = Template(template_path.read_text(encoding="utf-8"))
    sketch = tmpl.substitute(
        DIRECTORY_NAME=name,
        DATE=target.strftime("%Y-%m-%d"),
        TOTAL_FRAMES=frames,
        RECORDING=str(recording).lower(),
        AVG_LAT=avg_lat,
        AVG_LON=avg_lon,
    )
    sketch_dir = out_dir / "sketch"
    sketch_dir.mkdir(parents=True, exist_ok=True)
    (sketch_dir / "sketch.pde").write_text(sketch, encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gtfs", type=Path, default=Path("build/gtfs"),
                        help="入力 GTFS ディレクトリ（既定 build/gtfs）")
    parser.add_argument("--out", type=Path, required=True,
                        help="出力先（<out>/data/ に書き出す）")
    parser.add_argument("--date", help="アニメーション対象日（YYYY-MM-DD）。省略時は自動選択")
    parser.add_argument("--frames", type=int, default=DEFAULT_FRAMES,
                        help=f"総フレーム数（既定 {DEFAULT_FRAMES} = 60 秒）")
    parser.add_argument("--name", default="fukuoka", help="スケッチ名")
    parser.add_argument("--template", type=Path,
                        help="本家 template.pde のパス（指定時のみ sketch.pde を生成）")
    parser.add_argument("--recording", action="store_true",
                        help="sketch.pde を mp4 録画モードで生成する")
    args = parser.parse_args(argv)

    calendar_rows = read_csv(args.gtfs / "calendar.txt")
    target = parse_date(args.date) if args.date else default_service_date(calendar_rows)

    segments = build_segments(args.gtfs, target)
    stats = write_outputs(args.out, segments, args.frames)
    if args.template:
        write_sketch(args.out, args.template, args.name, target,
                     args.frames, segments, args.recording)

    print(f"{target}: {stats['segments']} セグメント / {stats['frames']} フレームを "
          f"{(args.out / 'data')} に書き出しました。")


if __name__ == "__main__":
    main()
