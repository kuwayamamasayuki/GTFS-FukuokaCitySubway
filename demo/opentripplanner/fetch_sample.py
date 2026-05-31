#!/usr/bin/env python3
"""起動中の OTP に経路検索を投げ、サンプル経路を data/sample-itinerary.json に保存する。

OTP の GTFS GraphQL API（既定: http://localhost:8080/otp/routers/default/index/graphql）に
出発地→目的地（既定: 橋本 → 福岡空港）の経路を問い合わせ、オフライン表示用の要約と
生データを保存する。OTP を起動した状態で実行すること（README.md 参照）。
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FEED = ROOT / "dist" / "FukuokaCitySubway.zip"
DEFAULT_OUT = Path(__file__).resolve().parent / "data" / "sample-itinerary.json"
DEFAULT_ENDPOINT = "http://localhost:8080/otp/routers/default/index/graphql"

DEFAULT_FROM = "橋本"
DEFAULT_TO = "福岡空港"
DEFAULT_DATE = "2026-04-01"
DEFAULT_TIME = "08:00:00"


# --------------------------------------------------------------------------
# 純粋関数（単体テスト対象）
# --------------------------------------------------------------------------
def find_stop_coord(stops: list[dict], name: str) -> tuple[float, float]:
    """stops 列から駅名で (lat, lon) を引く。親駅(location_type=1)を優先。"""
    matches = [s for s in stops if s.get("stop_name") == name]
    if not matches:
        raise KeyError(f"駅が見つかりません: {name}")
    parents = [s for s in matches if s.get("location_type") == "1"]
    s = (parents or matches)[0]
    return (float(s["stop_lat"]), float(s["stop_lon"]))


def plan_query(from_coord: tuple[float, float], to_coord: tuple[float, float],
               date: str, time: str, num_itineraries: int = 3) -> dict:
    """OTP GTFS GraphQL の plan クエリ（POST ボディ）を生成する。"""
    fl, fo = from_coord
    tl, to = to_coord
    query = f"""{{
  plan(
    from: {{lat: {fl}, lon: {fo}}}
    to: {{lat: {tl}, lon: {to}}}
    date: "{date}"
    time: "{time}"
    numItineraries: {num_itineraries}
    transportModes: [{{mode: WALK}}, {{mode: TRANSIT}}]
  ) {{
    itineraries {{
      duration
      walkDistance
      legs {{
        mode
        startTime
        endTime
        from {{ name }}
        to {{ name }}
        route {{ shortName longName }}
      }}
    }}
  }}
}}"""
    return {"query": query}


def summarize_itinerary(response: dict) -> dict:
    """OTP の plan 応答から先頭経路の要約（所要時間・乗換数・leg 列）を抽出する。"""
    itineraries = response.get("data", {}).get("plan", {}).get("itineraries", [])
    if not itineraries:
        raise ValueError("経路が見つかりません（itineraries が空）")
    it = itineraries[0]
    legs = []
    for leg in it.get("legs", []):
        route = leg.get("route") or {}
        legs.append({
            "mode": leg.get("mode"),
            "route": route.get("shortName") or route.get("longName"),
            "from": (leg.get("from") or {}).get("name"),
            "to": (leg.get("to") or {}).get("name"),
            "startTime": leg.get("startTime"),
            "endTime": leg.get("endTime"),
        })
    transit_legs = [leg for leg in legs if leg["mode"] not in (None, "WALK")]
    return {
        "duration_sec": it.get("duration"),
        "duration_min": round(it["duration"] / 60) if it.get("duration") else None,
        "walk_distance_m": round(it["walkDistance"]) if it.get("walkDistance") is not None else None,
        "transfers": max(len(transit_legs) - 1, 0),
        "legs": legs,
    }


def read_stops_from_feed(feed_zip: Path) -> list[dict]:
    with zipfile.ZipFile(feed_zip) as zf:
        with zf.open("stops.txt") as f:
            return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig")))


# --------------------------------------------------------------------------
# 副作用（HTTP）
# --------------------------------------------------------------------------
def post_graphql(endpoint: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310
        endpoint, data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
        return json.loads(r.read().decode("utf-8"))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="OTP GraphQL エンドポイント")
    p.add_argument("--feed", type=Path, default=DEFAULT_FEED, help="駅座標の参照元 GTFS zip")
    p.add_argument("--from", dest="from_name", default=DEFAULT_FROM, help="出発駅名")
    p.add_argument("--to", dest="to_name", default=DEFAULT_TO, help="目的駅名")
    p.add_argument("--date", default=DEFAULT_DATE, help="検索日 YYYY-MM-DD")
    p.add_argument("--time", default=DEFAULT_TIME, help="検索時刻 HH:MM:SS")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help="保存先 JSON")
    args = p.parse_args(argv)

    stops = read_stops_from_feed(args.feed)
    from_coord = find_stop_coord(stops, args.from_name)
    to_coord = find_stop_coord(stops, args.to_name)
    body = plan_query(from_coord, to_coord, args.date, args.time)

    print(f"  問い合わせ: {args.from_name} → {args.to_name} @ {args.date} {args.time}")
    response = post_graphql(args.endpoint, body)
    if response.get("errors"):
        raise SystemExit(f"OTP がエラーを返しました: {response['errors']}")
    summary = summarize_itinerary(response)

    out = {
        "from": args.from_name,
        "to": args.to_name,
        "date": args.date,
        "time": args.time,
        "summary": summary,
        "itineraries": response["data"]["plan"]["itineraries"],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  保存: {args.out}（所要 {summary['duration_min']} 分 / 乗換 {summary['transfers']} 回）")


if __name__ == "__main__":
    main()
