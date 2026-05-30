"""Excel 群を走査して全 Trip を抽出するオーケストレータ。

各シートをシート名で分類し、バンド検出 → 列車抽出を行う。実行冒頭に健全性
サマリ（検出シート数・区分×方向の網羅・便数）を出力し、想定外は LayoutError。
"""
from __future__ import annotations

import logging

from .config import Config
from .errors import LayoutError
from .excel import band_detector, train_extractor
from .excel.sheet_classifier import classify
from .excel.workbook import load_sheets
from .model import Trip
from .station_mapper import StationMapper

log = logging.getLogger("fukuoka_gtfs")


def parse_all(config: Config, mapper: StationMapper) -> list[Trip]:
    vocab = config.vocab()
    expected_sheets = int(config.parser.get("expected_sheets_per_file", 6))
    min_trips = int(config.parser.get("min_trips_per_sheet", 0))
    max_trips = int(config.parser.get("max_trips_per_sheet", 10**9))

    all_trips: list[Trip] = []
    for src in config.sources:
        path = config.data_dir / src.filename
        if not path.exists():
            raise LayoutError(f"入力 Excel がありません: {path}（先に download を実行してください）")
        sheets = load_sheets(path)
        log.info("[%s] %d シート検出", src.name, len(sheets))

        classified = 0
        seen: set[tuple[str, int]] = set()
        for sheet in sheets:
            kind = classify(sheet.name, config.service_labels, config.directions)
            if kind is None:
                log.debug("[%s] 区分判定不能のためスキップ: '%s'", src.name, sheet.name)
                continue
            classified += 1
            seen.add((kind.service_id, kind.direction_id))

            bands = band_detector.detect_bands(sheet, vocab)
            sheet_trips: list[Trip] = []
            for bi, band in enumerate(bands):
                sheet_trips.extend(train_extractor.extract_trips(
                    sheet, band, kind, mapper,
                    block_prefix=f"{src.name}_{kind.service_id}_{kind.direction_id}_b{bi}_",
                    route_group=config.route_to_group,
                    overnight_threshold_sec=config.overnight_threshold_sec,
                ))
            n = len(sheet_trips)
            log.info("  '%s' → %d バンド, %d 便", sheet.name, len(bands), n)
            if not (min_trips <= n <= max_trips):
                raise LayoutError(
                    f"シート '{sheet.name}' の便数 {n} が想定範囲 [{min_trips},{max_trips}] 外です。"
                    "ダイヤ改正かレイアウト変化の可能性があります（config/parser.yaml で調整可）。"
                )
            all_trips.extend(sheet_trips)

        if classified != expected_sheets:
            raise LayoutError(
                f"[{src.name}] データシート数 {classified} が想定 {expected_sheets} と異なります。"
            )
        # 区分 × 方向（3区分 × 2方向 = 6）が網羅されているか
        services = {s for s, _ in seen}
        directions = {d for _, d in seen}
        if len(seen) != len(services) * len(directions):
            raise LayoutError(f"[{src.name}] 区分×方向の組合せに欠落があります: {sorted(seen)}")

    log.info("合計 %d 便（trip）を抽出", len(all_trips))
    return all_trips
