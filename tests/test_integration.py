"""実 Excel がある場合のみ走る統合・既知便回帰テスト。

data/ に時刻表 Excel が無い環境（CI の初回など）では自動スキップする。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from fukuoka_gtfs.assembler import load_mapper
from fukuoka_gtfs.config import Config
from fukuoka_gtfs.parse import parse_all

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def trips():
    config = Config(ROOT)
    missing = [s.filename for s in config.sources if not (config.data_dir / s.filename).exists()]
    if missing:
        pytest.skip(f"入力 Excel が無いためスキップ: {missing}")
    return parse_all(config, load_mapper(config))


def _first(trips, route_id, direction_id):
    cand = [t for t in trips if t.route_id == route_id and t.direction_id == direction_id]
    return min(cand, key=lambda t: t.first_sec)


def test_nanakuma_first_hakata_bound_trip(trips):
    """七隈線 博多方面(dir0) の始発は 橋本05:15発 → 博多(37_3)05:44着。

    七隈線博多は独立駅 37 配下のホーム 37_3 を使う（Issue #53）。
    """
    t = _first(trips, "七隈線", 0)
    seqs = [(v.stop_id, v.sec) for v in t.visits]
    assert seqs[0] == ("20_1", 5 * 3600 + 15 * 60)      # 橋本
    assert seqs[-1] == ("37_3", 5 * 3600 + 44 * 60)     # 博多(七隈線ホーム)
    assert ("36_1", 5 * 3600 + 42 * 60) in seqs         # 櫛田神社前


def test_airport_line_terminus_uses_child_platform(trips):
    """空港線 dir0 の始発便が中洲川端で 9_3 を使い、福岡空港(13_1)で終わる。"""
    t = _first(trips, "空港線", 0)
    stop_ids = [v.stop_id for v in t.visits]
    assert "9_3" in stop_ids
    assert stop_ids[-1] == "13_1"


def test_through_trains_are_split_and_blocked(trips):
    """直通便は箱崎線+空港線に分割され、block_id で連結される。"""
    blocked = [t for t in trips if t.block_id]
    by_block: dict[str, set[str]] = {}
    for t in blocked:
        by_block.setdefault(t.block_id, set()).add(t.route_id)
    # 少なくとも 1 つは 箱崎線+空港線 のペア
    assert any(routes == {"箱崎線", "空港線"} for routes in by_block.values())
