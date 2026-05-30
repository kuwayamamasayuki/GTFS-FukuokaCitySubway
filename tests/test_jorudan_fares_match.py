"""ジョルダン運賃フィクスチャと生成 GTFS の運賃を全駅ペアで突合する統合テスト。

tests/fixtures/jorudan_fares.json（scripts/fetch_jorudan_fares.py が生成）を読み、
reference_gtfs/ の fare_attributes/fare_rules から作った運賃と突き合わせる。ネットワーク
には依存しない。既知の相違は config/jorudan_fare_verify.yaml の allow で許容する。
"""

import json
from pathlib import Path

import pytest
import yaml

from fukuoka_gtfs.gtfsio import read_csv
from fukuoka_gtfs.verify.fare_check import compare, gtfs_fares

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "reference_gtfs"
FARES_JSON = ROOT / "tests" / "fixtures" / "jorudan_fares.json"
CONFIG = ROOT / "config" / "jorudan_fare_verify.yaml"

N_STATIONS = 36
N_PAIRS = N_STATIONS * (N_STATIONS - 1) // 2  # 630


def _load_jorudan() -> dict[frozenset, int]:
    raw = json.loads(FARES_JSON.read_text(encoding="utf-8"))
    out: dict[frozenset, int] = {}
    for key, fare in raw.items():
        o, d = key.split("-")
        out[frozenset((o, d))] = int(fare)
    return out


def _load_allow() -> set[frozenset]:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    allow = set()
    for key in cfg.get("allow") or []:
        o, d = str(key).split("-")
        allow.add(frozenset((o, d)))
    return allow


@pytest.fixture(scope="module")
def gtfs_fare_map() -> dict[frozenset, int]:
    _, attr = read_csv(REF / "fare_attributes.txt")
    _, rules = read_csv(REF / "fare_rules.txt")
    return gtfs_fares(attr, rules)


@pytest.mark.skipif(
    not FARES_JSON.exists(),
    reason=f"フィクスチャ未取得: {FARES_JSON}（scripts/fetch_jorudan_fares.py で生成）",
)
def test_jorudan_fixture_covers_all_pairs():
    jorudan = _load_jorudan()
    assert len(jorudan) == N_PAIRS, f"全 {N_PAIRS} ペア中 {len(jorudan)} ペアのみ"


@pytest.mark.skipif(
    not FARES_JSON.exists(),
    reason=f"フィクスチャ未取得: {FARES_JSON}（scripts/fetch_jorudan_fares.py で生成）",
)
def test_gtfs_fares_match_jorudan(gtfs_fare_map):
    jorudan = _load_jorudan()
    diff = compare(gtfs_fare_map, jorudan, allow=_load_allow())
    assert diff.ok, (
        "GTFS とジョルダンの運賃が相違:\n"
        f"  金額相違 {len(diff.mismatch)}: {diff.mismatch[:20]}\n"
        f"  GTFS欠落 {len(diff.missing_in_gtfs)}: {diff.missing_in_gtfs[:20]}\n"
        f"  ジョルダン欠落 {len(diff.missing_in_jorudan)}: {diff.missing_in_jorudan[:20]}"
    )
