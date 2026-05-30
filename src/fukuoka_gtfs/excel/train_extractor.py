"""バンドの各データ列（=1 便）を Trip へ変換する。

手順: 非空セルを行順に収集 → 同一駅の連続をマージ → 時刻正規化 →
路線別セグメントへ分割 → 各セグメントを Trip 化（停車は子ホーム stop_id）。
"""
from __future__ import annotations

from ..model import StopVisit, Trip
from ..station_mapper import StationMapper, normalize_name
from .band_detector import Band
from .sheet_classifier import SheetKind
from .time_normalizer import DEFAULT_OVERNIGHT_THRESHOLD_SEC, normalize_sequence, to_fraction


def extract_trips(
    sheet,
    band: Band,
    kind: SheetKind,
    mapper: StationMapper,
    *,
    block_prefix: str,
    route_group: dict[str, str] | None = None,
    overnight_threshold_sec: int = DEFAULT_OVERNIGHT_THRESHOLD_SEC,
) -> list[Trip]:
    trips: list[Trip] = []
    for col in band.data_cols:
        trip_segments = _extract_column(
            sheet, band, kind, mapper, col,
            block_prefix=block_prefix, route_group=route_group or {},
            overnight_threshold_sec=overnight_threshold_sec,
        )
        trips.extend(trip_segments)
    return trips


def _extract_column(sheet, band, kind, mapper, col, *, block_prefix, route_group, overnight_threshold_sec):
    # 1) 非空の時刻セルを行順に収集
    raw: list[tuple[str, str, float]] = []  # (parent_id, name, fraction)
    for srow in band.station_rows:
        frac = to_fraction(sheet.cell(srow.row, col))
        if frac is None:
            continue
        raw.append((mapper.parent_id(srow.name), srow.name, frac))

    if len(raw) < 2:  # 始発止まり・空列などは便とみなさない
        return []

    # 2) 同一駅の連続をマージ（中洲川端の着+発など → 後（発）の時刻を採用）
    merged: list[tuple[str, str, float]] = []
    for pid, name, frac in raw:
        if merged and merged[-1][0] == pid:
            merged[-1] = (pid, name, frac)
        else:
            merged.append((pid, name, frac))
    if len(merged) < 2:
        return []

    parent_ids = [m[0] for m in merged]
    names = [m[1] for m in merged]
    secs = normalize_sequence([m[2] for m in merged], threshold_sec=overnight_threshold_sec)

    # 3) 行先（ヘッダの「行先」セル）。無ければ終着駅名。
    dest = None
    if band.dest_row is not None:
        cell = sheet.cell(band.dest_row, col)
        if isinstance(cell, str):
            dest = normalize_name(cell)
    headsign = dest or normalize_name(names[-1])

    # 4) 路線別に分割し、各セグメントを Trip 化
    segments = mapper.split_segments(parent_ids)
    block_id = f"{block_prefix}{col}" if len(segments) >= 2 else ""
    trips: list[Trip] = []
    for route_id, sl in segments:
        seg_parents = parent_ids[sl]
        seg_secs = secs[sl]
        if len(seg_parents) < 2:  # 単独の境界駅のみ等は捨てる
            continue
        visits = [
            StopVisit(stop_id=mapper.platform(pid, route_id, kind.direction_id), sec=sec)
            for pid, sec in zip(seg_parents, seg_secs)
        ]
        segment = kind.service_id  # 区分（平日/土曜/休日）
        group = route_group.get(route_id)
        service_id = f"{group}_{segment}" if group else segment
        trips.append(Trip(
            route_id=route_id, service_id=service_id, service_segment=segment,
            direction_id=kind.direction_id, headsign=headsign, block_id=block_id, visits=visits,
        ))
    return trips
