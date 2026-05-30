#!/usr/bin/env python3
"""ジョルダンのダイヤ詳細ページを取得し、突合テスト用の整形 fixture を生成する。

処理:
  1. 福岡市交通局の時刻表索引ページから diagramdtl リンクを列挙。
  2. 各リンクの (路線, 終端駅) を config/jorudan_verify.yaml で
     (route_id, direction_id) に解決。ダイヤ詳細ページは終端ラベルに関わらず
     その方面の全便を表示するため、(駅, route_id, direction_id) で重複排除。
  3. 各ページの dt を平日/土曜/休日の代表日に差し替えて取得。
  4. 時刻表本体(ttArea pc)と凡例(legendArea)のみを抜き出して整形 HTML として保存:
       tests/fixtures/jorudan/<route_id>/<fr>_<dir>_<daytype>.html
  5. tests/fixtures/jorudan/index.json に突合用メタデータを書き出す。

ネットワークアクセスを伴う「一度だけ／ダイヤ改正時」の手動実行スクリプト。
テスト本体(test_timetable_comparison.py)はこの出力(同梱 fixture)のみを使う。

使い方:
    python scripts/fetch_jorudan_fixtures.py [--out tests/fixtures/jorudan] [--sleep 0.7]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

import requests

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from fukuoka_gtfs.verify.jorudan_parser import parse_diagram  # noqa: E402
from fukuoka_gtfs.verify.mapping import load_mapping  # noqa: E402

_UA = "Mozilla/5.0 (compatible; fukuoka-gtfs-verify/1.0; +https://github.com/kuwayamamasayuki/GTFS-FukuokaCitySubway)"
_LINK = re.compile(
    r'href="(https://fukuoka-city-subway\.jorudan\.biz/pc/diagramdtl\?[^"]+)"'
)
_LEGEND_AREA = re.compile(r'<div class="legendArea">.*?</div>', re.S)
_LINEINDEX = re.compile(r'<input[^>]*class="lineindex"[^>]*/?>', re.S)
_DROP_ATTR = re.compile(r'\s+(?:style|href|cursor)="[^"]*"')
_WS_BETWEEN_TAGS = re.compile(r">\s+<")
_WS_RUN = re.compile(r"\s{2,}")


def _get(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": _UA}, timeout=60)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def _minify(fragment: str) -> str:
    """パーサが読む構造(クラス・タグ)は保ったまま、不要要素と空白を除去する。

    削除対象: `lineindex` の hidden input、`style`/`href` 属性、タグ間の空白。
    パーサは時(ttToggle>span)・行先記号(span.legend)・分(a) のみを参照するため、
    これらの除去で解析結果は変わらない（呼び出し側で同一性を検証する）。
    """
    s = _LINEINDEX.sub("", fragment)
    s = _DROP_ATTR.sub("", s)
    s = _WS_BETWEEN_TAGS.sub("><", s)
    s = _WS_RUN.sub(" ", s)
    return s.strip()


def _trim(html: str) -> str:
    """時刻表本体(ttArea pc)と凡例のみを抜き出し、最小化した整形 HTML を返す。"""
    start = html.find('<ul class="ttArea pc">')
    end = html.find('<ul class="ttArea sp"', start)
    if start == -1:
        raise ValueError("ttArea pc が見つかりません")
    if end == -1:
        end = len(html)
    tt = _minify(html[start:end])
    legend = _LEGEND_AREA.search(html)
    legend_html = _minify(legend.group(0)) if legend else ""
    return (
        "<!-- ジョルダン diagramdtl から ttArea pc と凡例のみを抽出・最小化した fixture -->\n"
        f"<html><body>\n{tt}\n{legend_html}\n</body></html>\n"
    )


def _override_dt(url: str, yyyymmdd: str) -> str:
    """URL の dt を <yyyymmdd>0500 に差し替える（他パラメータは保持）。"""
    parts = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qs(parts.query, keep_blank_values=True)
    q["dt"] = [f"{yyyymmdd}0500"]
    new_q = urllib.parse.urlencode(q, doseq=True, encoding="utf-8")
    return urllib.parse.urlunsplit(parts._replace(query=new_q))


def collect_pages(index_html: str, mapping) -> list[dict]:
    """索引 HTML から (駅, 路線, 方面) ごとに 1 ページへ集約したリストを返す。"""
    seen: set[tuple[str, str, int]] = set()
    pages: list[dict] = []
    for url in _LINK.findall(index_html):
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        fr = q["fr"][0]
        dgm = q["dgm"][0].split(":")
        jline, terminal = dgm[1], dgm[2]
        resolved = mapping.resolve_direction(jline, terminal)
        if resolved is None:
            continue
        route_id, direction_id = resolved
        key = (fr, route_id, direction_id)
        if key in seen:
            continue
        seen.add(key)
        pages.append(
            {
                "fr": fr,
                "url": url,
                "route_id": route_id,
                "direction_id": direction_id,
            }
        )
    return pages


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(_ROOT / "tests" / "fixtures" / "jorudan"))
    ap.add_argument("--sleep", type=float, default=0.7, help="リクエスト間の待機秒")
    ap.add_argument("--config", default=str(_ROOT / "config" / "jorudan_verify.yaml"))
    args = ap.parse_args()

    mapping = load_mapping(args.config)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"索引ページを取得: {mapping.index_url}")
    index_html = _get(mapping.index_url)
    pages = collect_pages(index_html, mapping)
    print(f"対象ページ: {len(pages)} 駅×方面 × {len(mapping.daytypes)} 曜日区分")

    index_entries: list[dict] = []
    for i, page in enumerate(pages, 1):
        for daytype in mapping.daytypes:
            url = _override_dt(page["url"], mapping.sample_dates[daytype])
            html = _get(url)
            trimmed = _trim(html)
            # 整形が解析結果を変えないことを自己検証
            if parse_diagram(trimmed) != parse_diagram(html):
                raise AssertionError(f"整形で解析結果が変化: {page['fr']} {daytype}")
            rel = Path(page["route_id"]) / (
                f"{page['fr']}_{page['direction_id']}_{daytype}.html"
            )
            dest = out_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(trimmed, encoding="utf-8")
            index_entries.append(
                {
                    "fixture": str(rel).replace("\\", "/"),
                    "station": mapping.normalize_station(page["fr"]),
                    "route_id": page["route_id"],
                    "direction_id": page["direction_id"],
                    "daytype": daytype,
                    "service_id": mapping.service_id(page["route_id"], daytype),
                    "source_url": url,
                }
            )
            time.sleep(args.sleep)
        print(f"  [{i}/{len(pages)}] {page['fr']} ({page['route_id']} dir{page['direction_id']})")

    index_path = out_dir / "index.json"
    index_path.write_text(
        json.dumps(index_entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"完了: {len(index_entries)} fixture, index -> {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
