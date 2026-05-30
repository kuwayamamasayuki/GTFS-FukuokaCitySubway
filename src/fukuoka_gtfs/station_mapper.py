"""Excel の駅名を GTFS の stop_id（子ホーム）へ対応付け、路線推定と
直通便の路線別分割を担う。

参照は reference_gtfs/stops.txt を単一情報源とする:
  * 親駅（location_type=1）の stop_name → parent_id
  * stop_code（例 ``K09/H01``）の接頭字から所属路線を推定
ダイヤ改正で駅が増えても、reference_gtfs/stops.txt に親駅を 1 行足すだけで追従する。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import MappingError

# stop_code 接頭字 → 路線名
_CODE_TO_LINE = {"K": "空港線", "H": "箱崎線", "N": "七隈線"}
_PAREN_RE = re.compile(r"[（(].*?[）)]\s*$")  # 末尾の (福岡県) 等


def normalize_name(name: str) -> str:
    """駅名を正規化（末尾の括弧注記を除去し前後空白を削る）。

    例: ``橋本(福岡県)`` → ``橋本`` 。
    """
    return _PAREN_RE.sub("", name).strip()


def lines_from_code(stop_code: str) -> set[str]:
    """``K09/H01`` のような stop_code から所属路線の集合を得る。"""
    lines: set[str] = set()
    for token in (stop_code or "").split("/"):
        token = token.strip()
        if token and token[0] in _CODE_TO_LINE:
            lines.add(_CODE_TO_LINE[token[0]])
    return lines


@dataclass
class StationMapper:
    parent_by_name: dict[str, str]
    lines_by_parent: dict[str, set[str]]
    # parent_id -> line -> direction_id -> 子ホーム stop_id（中洲川端・博多など共用駅の特例）
    platform_overrides: dict[str, dict[str, dict[int, str]]]

    @classmethod
    def from_stops(cls, stops_rows: list[dict], platform_overrides: dict) -> "StationMapper":
        parent_by_name: dict[str, str] = {}
        lines_by_parent: dict[str, set[str]] = {}
        for r in stops_rows:
            if str(r.get("location_type", "")) != "1":
                continue
            name = normalize_name(r["stop_name"])
            sid = r["stop_id"]
            parent_by_name[name] = sid
            lines_by_parent[sid] = lines_from_code(r.get("stop_code", ""))
        # YAML のキーは文字列なので direction を int 化して取り込む
        ov: dict[str, dict[str, dict[int, str]]] = {}
        for pid, by_line in (platform_overrides or {}).items():
            ov[str(pid)] = {ln: {int(d): cid for d, cid in dirs.items()} for ln, dirs in by_line.items()}
        return cls(parent_by_name, lines_by_parent, ov)

    def parent_id(self, excel_name: str) -> str:
        key = normalize_name(excel_name)
        try:
            return self.parent_by_name[key]
        except KeyError as e:
            raise MappingError(
                f"駅名 '{excel_name}'（正規化後 '{key}'）に対応する stop が "
                "reference_gtfs/stops.txt に見つかりません。新駅の場合は追記してください。"
            ) from e

    def lines_of(self, parent_id: str) -> set[str]:
        return self.lines_by_parent.get(parent_id, set())

    def single_line(self, parent_id: str) -> str | None:
        """単一路線にのみ属するならその路線名、共用駅なら None。"""
        ls = self.lines_of(parent_id)
        return next(iter(ls)) if len(ls) == 1 else None

    def platform(self, parent_id: str, line: str, direction_id: int) -> str:
        """(親駅, 路線, 方向) → 子ホーム stop_id。

        共用駅は platform_overrides を優先。通常駅は dir0→``_1`` / dir1→``_2``。
        """
        ov = self.platform_overrides.get(parent_id, {}).get(line)
        if ov and direction_id in ov:
            return ov[direction_id]
        return f"{parent_id}_{1 if direction_id == 0 else 2}"

    def split_segments(self, parent_ids: list[str]) -> list[tuple[str, slice]]:
        """便の停車駅（親 id 列）を路線別セグメントへ分割する。

        単一路線ならそのまま 1 セグメント。空港線↔箱崎線の直通便は共用駅
        （中洲川端）で 2 セグメントに割る。戻り値は (route_id, 範囲スライス)。
        共用駅は両セグメントに含まれる（前者の終点・後者の起点）。
        """
        definite = [self.single_line(pid) for pid in parent_ids]
        present = {ln for ln in definite if ln}
        if len(present) <= 1:
            line = next(iter(present), None) or (next(iter(self.lines_of(parent_ids[0])), "不明"))
            return [(line, slice(0, len(parent_ids)))]

        # 2 路線: 共用駅（definite=None）を境界に分割
        junctions = [i for i, ln in enumerate(definite) if ln is None]
        if junctions:
            j = junctions[len(junctions) // 2]
            line1 = next((ln for ln in definite[:j] if ln), "不明")
            line2 = next((ln for ln in definite[j + 1:] if ln), "不明")
            return [(line1, slice(0, j + 1)), (line2, slice(j, len(parent_ids)))]

        # 共用駅が無いのに 2 路線（想定外）: 路線が切り替わる位置で割る
        for i in range(1, len(definite)):
            if definite[i] and definite[i - 1] and definite[i] != definite[i - 1]:
                return [(definite[i - 1], slice(0, i)), (definite[i], slice(i, len(parent_ids)))]
        return [(next(iter(present)), slice(0, len(parent_ids)))]
