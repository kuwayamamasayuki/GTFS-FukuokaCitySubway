"""参照データ（reference_gtfs/）と Excel 由来の生成データを 1 つの GTFS へ統合し、
build/gtfs/ に書き出して zip 化する。
"""
from __future__ import annotations

import datetime as dt
import logging
import shutil
import zipfile
from pathlib import Path

from .builders import calendar_builder, feed_info_builder, schedule_builder
from .config import Config
from .errors import FukuokaGtfsError
from .gtfsio import read_csv, write_csv
from .parse import parse_all
from .station_mapper import StationMapper

log = logging.getLogger("fukuoka_gtfs")

# reference_gtfs/ からそのまま取り込む参照ファイル（滅多に変化しない）
REFERENCE_FILES = [
    "agency.txt", "agency_jp.txt", "routes.txt", "routes_jp.txt", "stops.txt",
    "translations.txt", "transfers.txt", "shapes.txt",
    "fare_attributes.txt", "fare_rules.txt",
]


def load_mapper(config: Config) -> StationMapper:
    _, stops_rows = read_csv(config.reference_dir / "stops.txt")
    return StationMapper.from_stops(stops_rows, config.platform_overrides)


def assemble(config: Config, today: dt.date | None = None) -> dict:
    """フィードを生成して build/gtfs/ と build/feed.zip を作る。統計 dict を返す。"""
    today = today or dt.date.today()
    out_dir = config.build_dir / "gtfs"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    mapper = load_mapper(config)
    trips = parse_all(config, mapper)
    if not trips:
        raise FukuokaGtfsError("便が 1 つも抽出できませんでした。")

    # 生成テーブル
    trips_rows, stop_times_rows = schedule_builder.build(trips)
    start_date, end_date = feed_info_builder.resolve_period(config.feed, today)
    calendar_rows = calendar_builder.build_calendar(config.calendar["services"], start_date, end_date)
    calendar_dates_rows = calendar_builder.build_calendar_dates(
        config.calendar["services"], config.calendar.get("holiday", {}), start_date, end_date,
    )
    feed_info_rows = feed_info_builder.build(config.feed, start_date, end_date)

    # 参照ファイルを取り込み（BOM 除去・LF 統一のため read→write）
    for name in REFERENCE_FILES:
        src = config.reference_dir / name
        if not src.exists():
            log.warning("参照ファイルが見つかりません（スキップ）: %s", name)
            continue
        header, rows = read_csv(src)
        write_csv(out_dir / name, header, rows)

    # 生成ファイルを書き出し
    write_csv(out_dir / "trips.txt", schedule_builder.TRIPS_HEADER, trips_rows)
    write_csv(out_dir / "stop_times.txt", schedule_builder.STOP_TIMES_HEADER, stop_times_rows)
    write_csv(out_dir / "calendar.txt", calendar_builder.CALENDAR_HEADER, calendar_rows)
    write_csv(out_dir / "calendar_dates.txt", calendar_builder.CALENDAR_DATES_HEADER, calendar_dates_rows)
    write_csv(out_dir / "feed_info.txt", feed_info_builder.FEED_INFO_HEADER, feed_info_rows)

    zip_path = _zip_feed(out_dir, config.build_dir / "feed.zip")
    stats = dict(
        trips=len(trips_rows), stop_times=len(stop_times_rows),
        calendar=len(calendar_rows), calendar_dates=len(calendar_dates_rows),
        start_date=start_date, end_date=end_date,
        out_dir=str(out_dir), zip=str(zip_path),
    )
    log.info("GTFS 生成完了: %s", stats)
    return stats


def _zip_feed(gtfs_dir: Path, zip_path: Path) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for txt in sorted(gtfs_dir.glob("*.txt")):
            z.write(txt, arcname=txt.name)
    return zip_path
