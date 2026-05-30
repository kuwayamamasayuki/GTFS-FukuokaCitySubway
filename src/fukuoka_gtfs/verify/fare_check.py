"""生成 GTFS の運賃（fare_attributes / fare_rules）とジョルダン運賃の突合。

運賃は方向に依存しないため、駅ペアは `frozenset({origin_id, destination_id})` を
キーとして扱う。既知の相違は許容リスト（``allow``）で除外し、それ以外の不一致のみを
報告する。
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Pair", "FareDiff", "gtfs_fares", "compare"]

Pair = frozenset  # frozenset[str]（2 駅の stop_id）


def gtfs_fares(attr_rows: list[dict], rule_rows: list[dict]) -> dict[Pair, int]:
    """fare_attributes/fare_rules から {frozenset(o, d): price} を作る。"""
    price = {r["fare_id"]: int(r["price"]) for r in attr_rows}
    fares: dict[Pair, int] = {}
    for r in rule_rows:
        fares[frozenset((r["origin_id"], r["destination_id"]))] = price[r["fare_id"]]
    return fares


@dataclass(frozen=True)
class FareDiff:
    """許容リストを差し引いた後の想定外の差分。

    - ``mismatch``: 両者にあるが額が違うペア (sorted (o, d), gtfs円, jorudan円)
    - ``missing_in_gtfs`` / ``missing_in_jorudan``: 片側にしか無いペア (sorted (o, d))
    """

    mismatch: list[tuple[tuple[str, str], int, int]]
    missing_in_gtfs: list[tuple[str, str]]
    missing_in_jorudan: list[tuple[str, str]]

    @property
    def ok(self) -> bool:
        return not (self.mismatch or self.missing_in_gtfs or self.missing_in_jorudan)


def _ordered(pair: Pair) -> tuple[str, str]:
    """stop_id を数値順に並べた (o, d)。表示・ソート用。"""
    return tuple(sorted(pair, key=int))  # type: ignore[return-value]


def compare(
    gtfs: dict[Pair, int],
    jorudan: dict[Pair, int],
    *,
    allow: set[Pair] = frozenset(),
) -> FareDiff:
    """GTFS とジョルダンの運賃辞書を突合する。``allow`` のペアは不一致でも無視する。"""
    mismatch = [
        (_ordered(p), gtfs[p], jorudan[p])
        for p in gtfs.keys() & jorudan.keys()
        if gtfs[p] != jorudan[p] and p not in allow
    ]
    missing_in_gtfs = [
        _ordered(p) for p in jorudan.keys() - gtfs.keys() if p not in allow
    ]
    missing_in_jorudan = [
        _ordered(p) for p in gtfs.keys() - jorudan.keys() if p not in allow
    ]
    keyfn = lambda od: (int(od[0]), int(od[1]))  # noqa: E731
    return FareDiff(
        mismatch=sorted(mismatch, key=lambda m: keyfn(m[0])),
        missing_in_gtfs=sorted(missing_in_gtfs, key=keyfn),
        missing_in_jorudan=sorted(missing_in_jorudan, key=keyfn),
    )
