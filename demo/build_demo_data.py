#!/usr/bin/env python3
"""build/gtfs/ の GTFS から、デモ用の軽量 JSON / GeoJSON を生成する。

出力（demo/data/）:
  network.json    路線・駅・色・統計（路線図/インフォグラフィック用）
  animation.json  全便の経路と通過時刻（運行アニメーション用）
  departures.json 親駅ごと・区分ごとの発車時刻（発車標用）
  network.geojson 路線(LineString)+駅(Point)（既製ツール/kepler.gl 等用）
"""
from __future__ import annotations

import csv
import json
import math
import re
import shutil
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GTFS = ROOT / "build" / "gtfs"
OUT = Path(__file__).resolve().parent / "data"

LINE_ORDER = ["空港線", "箱崎線", "七隈線"]
LINE_EN = {"空港線": "Kuko Line", "箱崎線": "Hakozaki Line", "七隈線": "Nanakuma Line"}
CODE_LINE = {"K": "空港線", "H": "箱崎線", "N": "七隈線"}
SERVICES = ["平日", "土曜", "休日"]


def read(name: str) -> list[dict]:
    with (GTFS / name).open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def to_sec(hms: str) -> int:
    h, m, s = (int(x) for x in hms.split(":"))
    return h * 3600 + m * 60 + s


def hhmm(sec: int) -> str:
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}"


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6371.0
    dlat = math.radians(b[0] - a[0])
    dlon = math.radians(b[1] - a[1])
    x = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(dlon / 2) ** 2)
    return r * 2 * math.asin(math.sqrt(x))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    stops = read("stops.txt")
    routes = {r["route_id"]: r for r in read("routes.txt")}
    trips = {t["trip_id"]: t for t in read("trips.txt")}
    stop_times = read("stop_times.txt")
    translations = read("translations.txt")

    # 翻訳（駅名→英語）
    en = {t["field_value"]: t["translation"] for t in translations
          if t["table_name"] == "stops" and t["language"] == "en"}

    # 親駅情報 / 子→親
    parents: dict[str, dict] = {}
    child_to_parent: dict[str, str] = {}
    for s in stops:
        if s["location_type"] == "1":
            parents[s["stop_id"]] = {
                "id": s["stop_id"], "code": s["stop_code"], "name": s["stop_name"],
                "name_en": en.get(s["stop_name"], s["stop_name"]),
                "lat": round(float(s["stop_lat"]), 6), "lon": round(float(s["stop_lon"]), 6),
            }
        else:
            child_to_parent[s["stop_id"]] = s["parent_station"]
    for pid in parents:
        child_to_parent[pid] = pid  # 念のため自己参照

    line_color = {lid: "#" + routes[lid]["route_color"] for lid in LINE_ORDER}

    # --- 路線ごとの駅順（stop_code の番号で並べる） ---
    line_stations: dict[str, dict[int, str]] = defaultdict(dict)
    for pid, p in parents.items():
        for token in p["code"].split("/"):
            m = re.match(r"([KHN])(\d+)", token.strip())
            if m:
                line_stations[CODE_LINE[m.group(1)]][int(m.group(2))] = pid

    lines_out = []
    for lid in LINE_ORDER:
        ordered = [parents[line_stations[lid][n]] for n in sorted(line_stations[lid])]
        lines_out.append({"id": lid, "name": lid, "name_en": LINE_EN[lid],
                          "color": line_color[lid], "stations": ordered})

    # --- 便ごとの (順序, 親駅, 秒) 列 ---
    seq_time: dict[str, list[tuple[int, str, int]]] = defaultdict(list)
    for st in stop_times:
        seq_time[st["trip_id"]].append(
            (int(st["stop_sequence"]), st["stop_id"], to_sec(st["departure_time"])))

    # --- animation.json ---
    anim_trips = []
    tmin, tmax = 10**9, 0
    for tid, items in seq_time.items():
        items.sort(key=lambda x: x[0])
        path, times = [], []
        for _, sid, sec in items:
            p = parents[child_to_parent.get(sid, sid)]
            path.append([p["lon"], p["lat"]])
            times.append(sec)
        if len(path) < 2:
            continue
        t = trips[tid]
        anim_trips.append({"r": t["route_id"], "c": line_color[t["route_id"]],
                           "s": t["service_id"], "d": int(t["direction_id"]),
                           "path": path, "times": times})
        tmin, tmax = min(tmin, times[0]), max(tmax, times[-1])

    (OUT / "animation.json").write_text(
        json.dumps({"tmin": tmin, "tmax": tmax, "trips": anim_trips},
                   ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # --- departures.json（親駅×区分） ---
    departures: dict[str, dict] = {}
    for pid, p in parents.items():
        departures[pid] = {"name": p["name"], "name_en": p["name_en"], "code": p["code"],
                           **{sv: [] for sv in SERVICES}}
    for tid, items in seq_time.items():
        t = trips[tid]
        sv, rid = t["service_id"], t["route_id"]
        for _, sid, sec in items:
            pid = child_to_parent.get(sid, sid)
            departures[pid][sv].append(
                {"t": sec, "hhmm": hhmm(sec), "route": rid, "color": line_color[rid],
                 "headsign": t["trip_headsign"], "dir": int(t["direction_id"])})
    for pid in departures:
        for sv in SERVICES:
            departures[pid][sv].sort(key=lambda x: x["t"])

    (OUT / "departures.json").write_text(
        json.dumps(departures, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # --- 統計 ---
    trips_by_line_service: dict[str, dict[str, int]] = {
        lid: dict.fromkeys(SERVICES, 0) for lid in LINE_ORDER}
    first_last: dict[str, dict[str, list[int]]] = {
        lid: {sv: [] for sv in SERVICES} for lid in LINE_ORDER}
    for tid, items in seq_time.items():
        t = trips[tid]
        trips_by_line_service[t["route_id"]][t["service_id"]] += 1
        secs = [s for _, _, s in items]
        first_last[t["route_id"]][t["service_id"]].extend([secs[0], secs[-1]])

    def line_length(lid: str) -> float:
        sts = [parents[line_stations[lid][n]] for n in sorted(line_stations[lid])]
        return round(sum(haversine((a["lat"], a["lon"]), (b["lat"], b["lon"]))
                         for a, b in zip(sts, sts[1:])), 1)

    by_line_stats = {}
    for lid in LINE_ORDER:
        all_secs = [s for sv in SERVICES for s in first_last[lid][sv]]
        by_line_stats[lid] = {
            "stations": len(line_stations[lid]),
            "length_km": line_length(lid),
            "color": line_color[lid],
            "name_en": LINE_EN[lid],
            "trips": trips_by_line_service[lid],
            "first": hhmm(min(all_secs)), "last": hhmm(max(all_secs)),
        }

    lats = [p["lat"] for p in parents.values()]
    lons = [p["lon"] for p in parents.values()]
    network = {
        "bbox": [min(lons), min(lats), max(lons), max(lats)],
        "center": [sum(lons) / len(lons), sum(lats) / len(lats)],
        "lines": lines_out,
        "stats": {
            "totals": {"trips": len(trips), "stations": len(parents),
                       "lines": len(LINE_ORDER), "stop_times": len(stop_times)},
            "by_line": by_line_stats,
            "services": SERVICES,
        },
    }
    (OUT / "network.json").write_text(
        json.dumps(network, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # --- GeoJSON（既製ツール用） ---
    features = []
    for lid in LINE_ORDER:
        sts = [parents[line_stations[lid][n]] for n in sorted(line_stations[lid])]
        features.append({"type": "Feature",
                         "properties": {"name": lid, "name_en": LINE_EN[lid],
                                        "stroke": line_color[lid], "stroke-width": 4},
                         "geometry": {"type": "LineString",
                                      "coordinates": [[s["lon"], s["lat"]] for s in sts]}})
    for p in parents.values():
        features.append({"type": "Feature",
                         "properties": {"name": p["name"], "name_en": p["name_en"],
                                        "code": p["code"], "marker-color": "#ffffff"},
                         "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]}})
    (OUT / "network.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        encoding="utf-8")

    # feed.zip をデモ配下へコピー（demo/ をルートに配信してもダウンロードできるように）
    feed_zip = ROOT / "build" / "feed.zip"
    if feed_zip.exists():
        shutil.copy(feed_zip, OUT / "feed.zip")

    # サイズ報告
    for f in ["network.json", "animation.json", "departures.json", "network.geojson"]:
        kb = (OUT / f).stat().st_size / 1024
        print(f"  {f}: {kb:.0f} KB")
    print(f"便数 {len(anim_trips)} / 時間帯 {hhmm(tmin)}〜{hhmm(tmax)}")


if __name__ == "__main__":
    main()
