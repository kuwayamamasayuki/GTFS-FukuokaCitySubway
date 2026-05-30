"""旧 .xls（xlrd）と .xlsx（openpyxl）の差を吸収し、共通のセル格子を返す。

時刻の変換はここでは行わず、生のセル値（str / 数値 / datetime / None）を保持する。
時刻としての解釈は :func:`time_normalizer.to_fraction` が担う。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..errors import LayoutError


@dataclass
class Sheet:
    """1 シート分のセル格子。grid[r][c] は 0 始まりで生のセル値（空は None）。"""

    name: str
    grid: list[list[object]]

    @property
    def nrows(self) -> int:
        return len(self.grid)

    def cell(self, r: int, c: int) -> object:
        if 0 <= r < len(self.grid) and 0 <= c < len(self.grid[r]):
            return self.grid[r][c]
        return None


def load_sheets(path: str | Path) -> list[Sheet]:
    """Excel を読み、:class:`Sheet` のリストを返す。拡張子で読み込み方式を切替える。"""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".xls":
        return _load_xls(p)
    if suffix in (".xlsx", ".xlsm"):
        return _load_xlsx(p)
    raise LayoutError(f"未対応の拡張子です: {p.name}")


def _norm(value: object) -> object:
    """空文字は None に揃える。"""
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        return s or None
    return value


def _load_xls(path: Path) -> list[Sheet]:
    import xlrd  # 旧 BIFF 形式専用

    book = xlrd.open_workbook(str(path))
    sheets: list[Sheet] = []
    for sh in book.sheets():
        grid = [[_norm(sh.cell_value(r, c)) for c in range(sh.ncols)] for r in range(sh.nrows)]
        sheets.append(Sheet(name=sh.name, grid=grid))
    return sheets


def _load_xlsx(path: Path) -> list[Sheet]:
    import openpyxl

    book = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    try:
        sheets: list[Sheet] = []
        for ws in book.worksheets:
            grid = [[_norm(v) for v in row] for row in ws.iter_rows(values_only=True)]
            sheets.append(Sheet(name=ws.title, grid=grid))
        return sheets
    finally:
        book.close()
