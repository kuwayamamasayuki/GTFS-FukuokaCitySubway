"""GTFS とジョルダンの発車便集合を厳密に突合する。

突合は ``(hour, minute, destination)`` の多重集合（本数も含む）として行う。
時刻も行先も厳密一致が合否基準。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .jorudan_parser import Departure

__all__ = ["ComparisonResult", "compare"]


@dataclass(frozen=True)
class ComparisonResult:
    """突合結果。

    - ``missing``: ジョルダンにあって GTFS に無い便。
    - ``extra``: GTFS にあってジョルダンに無い便。
    """

    missing: list[Departure]
    extra: list[Departure]

    @property
    def ok(self) -> bool:
        return not self.missing and not self.extra


def _sort_key(d: Departure) -> tuple[int, int, str]:
    return (d.hour, d.minute, d.destination)


def _diff(a: Counter[Departure], b: Counter[Departure]) -> list[Departure]:
    """多重集合の差 a - b を、本数を保ったまま整列リストで返す。"""
    out: list[Departure] = []
    for dep, n in (a - b).items():
        out.extend([dep] * n)
    out.sort(key=_sort_key)
    return out


def compare(
    jorudan: list[Departure], gtfs: list[Departure]
) -> ComparisonResult:
    jc = Counter(jorudan)
    gc = Counter(gtfs)
    return ComparisonResult(missing=_diff(jc, gc), extra=_diff(gc, jc))
