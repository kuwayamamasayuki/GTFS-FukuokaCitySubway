"""Issue #5 本体: 生成 GTFS の全駅・全方面・全曜日の発車時刻を、ジョルダンの
ダイヤ詳細（記録済み fixture）と突合する確認テスト。

- 合否は発車時刻(時:分)の集合一致で判定する（行先はジョルダンと GTFS で表記体系が
  異なるため判定に用いない。詳細は docs の設計書を参照）。
- 既知の差分（七隈線の一部 1 分差、姪浜/中洲川端の直通便など）は
  ``tests/fixtures/jorudan/expected_diffs.json`` で許容し、それ以外の新規差分が出たら失敗する。
- GTFS 生成物 ``build/gtfs`` を読む。無い場合は skip（リポジトリは build を生成物として
  追跡しないため、make build 後にローカルで実行する）。環境変数 ``FUKUOKA_GTFS_DIR`` で
  別の GTFS ディレクトリを指定できる。

ダイヤ改正で Excel/GTFS を更新したら:
  1. python scripts/fetch_jorudan_fixtures.py   # fixture を再取得
  2. make build                                 # GTFS を再生成
  3. python scripts/gen_expected_diffs.py       # 許容リストを作り直す
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from fukuoka_gtfs.verify.gtfs_timetable import departures, load_feed
from fukuoka_gtfs.verify.jorudan_parser import parse_diagram
from fukuoka_gtfs.verify.mapping import load_mapping
from fukuoka_gtfs.verify.timetable_check import check_times

_ROOT = Path(__file__).resolve().parents[1]
_FIXTURES = _ROOT / "tests" / "fixtures" / "jorudan"
_CONFIG = _ROOT / "config" / "jorudan_verify.yaml"


def _gtfs_dir() -> Path:
    return Path(os.environ.get("FUKUOKA_GTFS_DIR", str(_ROOT / "build" / "gtfs")))


def _index() -> list[dict]:
    path = _FIXTURES / "index.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _expected_diffs() -> dict[str, dict]:
    path = _FIXTURES / "expected_diffs.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("diffs", {})


_INDEX = _index()


@pytest.fixture(scope="module")
def feed():
    gtfs = _gtfs_dir()
    if not (gtfs / "stop_times.txt").exists():
        pytest.skip(
            f"GTFS 生成物が見つかりません ({gtfs})。make build 後に実行してください。"
        )
    return load_feed(gtfs)


@pytest.fixture(scope="module")
def mapping():
    return load_mapping(_CONFIG)


@pytest.fixture(scope="module")
def expected_diffs():
    return _expected_diffs()


@pytest.mark.skipif(not _INDEX, reason="ジョルダン fixture の index.json がありません")
@pytest.mark.parametrize(
    "entry", _INDEX, ids=[e["fixture"] for e in _INDEX] or None
)
def test_departure_times_match_jorudan(entry, feed, mapping, expected_diffs):
    default = mapping.default_destination(entry["route_id"], entry["direction_id"])
    jorudan = parse_diagram(
        (_FIXTURES / entry["fixture"]).read_text(encoding="utf-8"), default
    )
    gtfs = departures(
        feed,
        stop_name=entry["station"],
        route_id=entry["route_id"],
        direction_id=entry["direction_id"],
        service_id=entry["service_id"],
    )
    allow = expected_diffs.get(entry["fixture"], {})
    allow_missing = [tuple(t) for t in allow.get("missing", [])]
    allow_extra = [tuple(t) for t in allow.get("extra", [])]

    diff = check_times(
        jorudan, gtfs, allow_missing=allow_missing, allow_extra=allow_extra
    )
    assert diff.ok, (
        f"{entry['fixture']} で既知差分以外の発車時刻ズレを検出。\n"
        f"  ジョルダンにあり GTFS に無い(新規): {diff.missing}\n"
        f"  GTFS にありジョルダンに無い(新規): {diff.extra}\n"
        f"  （既知差分なら scripts/gen_expected_diffs.py で許容リストを更新）"
    )
