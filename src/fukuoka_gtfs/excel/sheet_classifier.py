"""シート名から運行区分（service_id）と方向（direction_id）を判定する。

シート名は ``(平日　姪浜方面)`` のような形式。固定の並びに依存せず、設定の語彙を
部分一致で探す（ダイヤ改正でシート名の体裁が多少変わっても耐えるように）。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SheetKind:
    service_id: str
    direction_id: int
    direction_label: str


def classify(
    sheet_name: str,
    service_labels: dict[str, str],
    directions: dict[str, int],
) -> SheetKind | None:
    """シート名を分類する。判定不能なら None（=データシートでないとみなす）。"""
    service_id = next((sid for kw, sid in service_labels.items() if kw in sheet_name), None)
    direction = next(
        ((label, did) for label, did in directions.items() if label in sheet_name),
        None,
    )
    if service_id is None or direction is None:
        return None
    return SheetKind(service_id=service_id, direction_id=direction[1], direction_label=direction[0])
