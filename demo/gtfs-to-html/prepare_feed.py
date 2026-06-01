#!/usr/bin/env python3
"""gtfs-to-html へ渡す入力フィードを `feed/` に組み立てる。

gtfs-to-html の `show_trip_continuation` などは config.json ではなく、入力 GTFS
データセット内の追加ファイル（timetables.txt / timetable_pages.txt）で指定する。
公開スナップショット dist/FukuokaCitySubway.zip は標準 GTFS のまま保ちたいので、
ここで「dist の中身＋このデモの追加ファイル」を結合した作業用フォルダ feed/ を作る。
config.json の agencies[].path はこの feed/ を指す。

冪等。実行のたびに feed/ を作り直す（feed/ は .gitignore 済み）。
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIST_ZIP = HERE / ".." / ".." / "dist" / "FukuokaCitySubway.zip"
FEED_DIR = HERE / "feed"
# このデモ固有の gtfs-to-html 追加ファイル（入力 GTFS に同梱して読ませる）
EXTRA_FILES = ["timetables.txt", "timetable_pages.txt"]


def main() -> int:
    zip_path = DIST_ZIP.resolve()
    if not zip_path.exists():
        raise SystemExit(f"入力 zip が見つかりません: {zip_path}\n"
                         "先に `make build && make publish` で dist/ を生成してください。")

    if FEED_DIR.exists():
        shutil.rmtree(FEED_DIR)
    FEED_DIR.mkdir(parents=True)

    with zipfile.ZipFile(zip_path) as z:
        z.extractall(FEED_DIR)

    for name in EXTRA_FILES:
        src = HERE / name
        if not src.exists():
            raise SystemExit(f"追加ファイルが見つかりません: {src}")
        shutil.copy2(src, FEED_DIR / name)

    print(f"feed/ を作成しました: {FEED_DIR}")
    print(f"  GTFS({len(list(FEED_DIR.glob('*.txt')))} ファイル) + 追加: {', '.join(EXTRA_FILES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
