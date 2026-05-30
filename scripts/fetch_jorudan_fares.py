#!/usr/bin/env python3
"""ジョルダンの福岡市地下鉄「発着・料金検索」から全駅ペアの普通料金を取得し、
オフラインテスト用フィクスチャ tests/fixtures/jorudan_fares.json を生成する。

料金検索のトップ(/pc/route)は JS 駆動の SPA だが、検索結果ページ(/pc/nsresult)は
サーバ描画で、結果 URL を直接叩けば普通料金を含む HTML が返る（ブラウザ不要）。
よって取得は既存依存の requests のみで行い、解析は verify.jorudan_fare を借用する。

  python scripts/fetch_jorudan_fares.py              # 全 630 ペアを取得して書き出し
  python scripts/fetch_jorudan_fares.py --limit 5    # 先頭 5 ペアのみ（動作確認用）
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from itertools import combinations
from pathlib import Path
from urllib.parse import quote

import requests

# src/ をパスに追加して verify.jorudan_fare を借用（取得と解析で同じ規則を使う）
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from fukuoka_gtfs.verify.jorudan_fare import parse_fare  # noqa: E402

REF = ROOT / "reference_gtfs"
FIX_DIR = ROOT / "tests" / "fixtures"
FARES_JSON = FIX_DIR / "jorudan_fares.json"
SAMPLE_HTML = FIX_DIR / "jorudan" / "fare_sample.html"

BASE = "https://fukuoka-city-subway.jorudan.biz/pc"
DT = "202606011030"  # 運賃は日時非依存。任意の平日昼。
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def load_stations() -> list[tuple[str, str]]:
    """親駅(location_type=1)の (stop_id, stop_name) を stop_id 昇順で返す。"""
    with (REF / "stops.txt").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    parents = [(r["stop_id"], r["stop_name"]) for r in rows if r["location_type"] == "1"]
    return sorted(parents, key=lambda s: int(s[0]))


def result_url(fr: str, to: str) -> str:
    return (
        f"{BASE}/nsresult?mode=0&skbn=1"
        f"&fr={quote(fr)}&frkbn=4&frsk=R"
        f"&to={quote(to)}&tokbn=4&tosk=R&dt={DT}&p=1"
    )


def fetch_fare(session: requests.Session, fr: str, to: str) -> int | None:
    """1 ペアの普通料金を取得。一過性の失敗には 1 回だけ再試行する。"""
    for attempt in range(2):
        try:
            resp = session.get(result_url(fr, to), timeout=30)
            resp.raise_for_status()
        except requests.RequestException:
            time.sleep(1.0)
            continue
        fare = parse_fare(resp.text)
        if fare is not None:
            if not SAMPLE_HTML.exists():
                SAMPLE_HTML.parent.mkdir(parents=True, exist_ok=True)
                SAMPLE_HTML.write_text(resp.text, encoding="utf-8")
            return fare
        time.sleep(1.0)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="先頭 N ペアのみ取得")
    args = ap.parse_args()

    stations = load_stations()
    name_of = dict(stations)
    pairs = list(combinations([sid for sid, _ in stations], 2))
    if args.limit:
        pairs = pairs[: args.limit]
    print(f"駅 {len(stations)} / ペア {len(pairs)} を取得（dt={DT}）", flush=True)

    fares: dict[str, int] = {}
    failures: list[str] = []
    with requests.Session() as session:
        session.headers["User-Agent"] = UA
        for i, (o, d) in enumerate(pairs, 1):
            fare = fetch_fare(session, name_of[o], name_of[d])
            if fare is None:
                failures.append(f"{o}-{d}({name_of[o]}->{name_of[d]})")
                print(f"  [{i}/{len(pairs)}] {name_of[o]}->{name_of[d]}: 取得失敗", flush=True)
            else:
                fares[f"{o}-{d}"] = fare
            if i % 50 == 0 or i == len(pairs):
                print(f"  [{i}/{len(pairs)}] 取得済み {len(fares)} 件", flush=True)
            time.sleep(0.2)  # 過負荷を避ける

    if failures:
        print(f"\n取得失敗 {len(failures)} ペア: {', '.join(failures[:20])}")
        if not args.limit:
            print("失敗があるためフィクスチャは書き出しません。")
            return 1

    FARES_JSON.parent.mkdir(parents=True, exist_ok=True)
    FARES_JSON.write_text(
        json.dumps(fares, ensure_ascii=False, indent=0, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"\n書き出し: {FARES_JSON}（{len(fares)} ペア）")
    print(f"サンプル HTML: {SAMPLE_HTML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
