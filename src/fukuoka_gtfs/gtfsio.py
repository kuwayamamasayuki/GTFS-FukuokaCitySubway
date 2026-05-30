"""GTFS テキストファイル（CSV）の読み書き。BOM 無し UTF-8・LF で統一する。"""
from __future__ import annotations

import csv
import io
from pathlib import Path


def read_csv(path: str | Path) -> tuple[list[str], list[dict]]:
    """GTFS txt を読み、(ヘッダ, 行リスト) を返す。BOM があっても除去する。"""
    text = Path(path).read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader.fieldnames or []), list(reader)


def write_csv(path: str | Path, header: list[str], rows: list[dict]) -> None:
    """行（dict）を GTFS txt として書き出す。header の列順で固定。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in header})
