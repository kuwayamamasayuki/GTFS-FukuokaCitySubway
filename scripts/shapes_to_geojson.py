#!/usr/bin/env python3
"""shapes.txt を GeoJSON に変換して地図上で形状を目視確認するための補助ツール。

kepler-animation の trips.geojson は trips/stop_times（駅の座標）から線を引くため
駅間が直線になり、shapes.txt の形状そのものは描画されない。本ツールは shapes.txt の
点列を LineString（経路）＋ Point（各形状点）として出力する。出力した .geojson を
https://geojson.io や https://kepler.gl にドラッグ＆ドロップすると、OSM 背景の上に
形状を重ねて確認できる。

使い方:
  python scripts/shapes_to_geojson.py                       # dist/shapes.txt 全形状
  python scripts/shapes_to_geojson.py --filter 七隈線        # shape_id 部分一致で絞り込み
  python scripts/shapes_to_geojson.py --input reference_gtfs/shapes.txt --points
  python scripts/shapes_to_geojson.py --filter 七隈線 -o build/nanakuma_shapes.geojson
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_shapes(path: Path) -> dict[str, list[dict]]:
    """shape_id ごとに (seq 昇順の) 点リストへまとめる。"""
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    shapes: dict[str, list[dict]] = {}
    for r in rows:
        shapes.setdefault(r["shape_id"], []).append(r)
    for sid in shapes:
        shapes[sid].sort(key=lambda r: int(r["shape_pt_sequence"]))
    return shapes


def to_feature_collection(shapes: dict[str, list[dict]], with_points: bool) -> dict:
    features: list[dict] = []
    for sid, pts in shapes.items():
        coords = [[float(p["shape_pt_lon"]), float(p["shape_pt_lat"])] for p in pts]
        features.append({
            "type": "Feature",
            "properties": {"shape_id": sid, "points": len(coords)},
            "geometry": {"type": "LineString", "coordinates": coords},
        })
        if with_points:
            for p in pts:
                features.append({
                    "type": "Feature",
                    "properties": {
                        "shape_id": sid,
                        "shape_pt_sequence": p["shape_pt_sequence"],
                        "shape_dist_traveled": p.get("shape_dist_traveled", ""),
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [float(p["shape_pt_lon"]), float(p["shape_pt_lat"])],
                    },
                })
    return {"type": "FeatureCollection", "features": features}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="shapes.txt → GeoJSON")
    ap.add_argument("--input", "-i", type=Path, default=ROOT / "dist" / "shapes.txt",
                    help="入力 shapes.txt（既定: dist/shapes.txt）")
    ap.add_argument("--output", "-o", type=Path, default=None,
                    help="出力 .geojson（既定: 標準出力）")
    ap.add_argument("--filter", "-f", default=None,
                    help="shape_id 部分一致でこの形状だけ出力")
    ap.add_argument("--points", action="store_true",
                    help="各形状点を Point マーカーとしても出力（seq/dist を確認したいとき）")
    args = ap.parse_args(argv)

    shapes = load_shapes(args.input)
    if args.filter:
        shapes = {k: v for k, v in shapes.items() if args.filter in k}
        if not shapes:
            print(f"該当する shape_id がありません: {args.filter}", file=sys.stderr)
            return 1

    fc = to_feature_collection(shapes, args.points)
    text = json.dumps(fc, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"書き出し: {args.output}  （{len(shapes)} 形状 / {len(fc['features'])} feature）",
              file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
