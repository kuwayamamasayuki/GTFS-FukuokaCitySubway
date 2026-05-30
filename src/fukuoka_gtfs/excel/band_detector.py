"""シート内の「バンド」（午前便/午後便などの縦分割ブロック）を検出し、
各バンドのヘッダ行・駅行・データ列を構造化する。

固定オフセットではなく語彙（始発/行先/乗り入れ/発/着）で行を見つけるため、
ダイヤ改正でバンド数や行位置が変わっても追従しやすい。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..errors import LayoutError
from .workbook import Sheet


@dataclass(frozen=True)
class StationRow:
    row: int
    name: str
    kind: str  # "発" or "着"


@dataclass
class Band:
    origin_row: int                       # 「始発」行
    dest_row: int | None                  # 「行先」行
    through_row: int | None               # 「乗り入れ」行（任意）
    station_rows: list[StationRow] = field(default_factory=list)
    data_cols: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class Vocab:
    origin: str = "始発"
    destination: str = "行先"
    through: str = "乗り入れ"
    departure: str = "発"
    arrival: str = "着"
    first_data_col: int = 2

    @classmethod
    def from_config(cls, cfg: dict) -> "Vocab":
        h = cfg.get("header_labels", {})
        k = cfg.get("stop_kinds", {})
        return cls(
            origin=h.get("origin", "始発"),
            destination=h.get("destination", "行先"),
            through=h.get("through", "乗り入れ"),
            departure=k.get("departure", "発"),
            arrival=k.get("arrival", "着"),
            first_data_col=int(cfg.get("first_data_col", 2)),
        )


def detect_bands(sheet: Sheet, vocab: Vocab) -> list[Band]:
    """シートのバンド一覧を返す。バンドが 1 つも無ければ LayoutError。"""
    starts = [r for r in range(sheet.nrows) if sheet.cell(r, 0) == vocab.origin]
    if not starts:
        raise LayoutError(
            f"シート '{sheet.name}': 「{vocab.origin}」で始まるヘッダ行が見つかりません。"
            "レイアウトが変わった可能性があります。"
        )
    bounds = starts + [sheet.nrows]
    bands: list[Band] = []
    for i, start in enumerate(starts):
        band = _build_band(sheet, vocab, start, bounds[i + 1])
        if not band.station_rows:
            raise LayoutError(f"シート '{sheet.name}' のバンド(開始 r{start}) に駅行がありません。")
        if not band.data_cols:
            raise LayoutError(f"シート '{sheet.name}' のバンド(開始 r{start}) に列車データ列がありません。")
        bands.append(band)
    return bands


def _build_band(sheet: Sheet, vocab: Vocab, start: int, stop: int) -> Band:
    dest_row = through_row = None
    station_rows: list[StationRow] = []
    for r in range(start, stop):
        c0 = sheet.cell(r, 0)
        c1 = sheet.cell(r, 1)
        if c0 == vocab.destination:
            dest_row = r
        elif c0 == vocab.through:
            through_row = r
        elif c1 in (vocab.departure, vocab.arrival) and isinstance(c0, str):
            station_rows.append(StationRow(row=r, name=c0, kind=str(c1)))

    # 列車データ列 = 「始発」行で値の入っている列（first_data_col 以降）
    data_cols = [
        c for c in range(vocab.first_data_col, len(sheet.grid[start]))
        if sheet.cell(start, c) is not None
    ]
    return Band(origin_row=start, dest_row=dest_row, through_row=through_row,
                station_rows=station_rows, data_cols=data_cols)
