#!/usr/bin/env python3
"""生成 GTFS とジョルダン fixture の「既知の発車時刻差」許容リストを作る。

突合テスト(test_timetable_comparison.py)は、ここで生成した
``tests/fixtures/jorudan/expected_diffs.json`` を差し引いた「新規差分」のみを
不一致として失敗させる。これにより回帰（新たなズレ）を検出しつつ、既知差は緑にする。

既知差の代表（2026-05 時点。要調査として文書化）:
  * 七隈線の一部便で発車時刻が 1 分ずれる（GTFS 生成側の中間駅補間に起因か）。
  * 境界駅（姪浜・中洲川端）で、JR 筑肥線直通便などが GTFS では終着扱いとなり
    発車に現れない／直通の数え方が異なる。

要 `build/gtfs`（事前に make build 等で生成）。ダイヤ改正で fixture や GTFS を
更新したら本スクリプトを再実行して許容リストを作り直す。

使い方:
    python scripts/gen_expected_diffs.py [--gtfs build/gtfs]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from fukuoka_gtfs.verify.gtfs_timetable import departures, load_feed  # noqa: E402
from fukuoka_gtfs.verify.jorudan_parser import parse_diagram  # noqa: E402
from fukuoka_gtfs.verify.mapping import load_mapping  # noqa: E402
from fukuoka_gtfs.verify.timetable_check import check_times  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gtfs", default=str(_ROOT / "build" / "gtfs"))
    ap.add_argument("--config", default=str(_ROOT / "config" / "jorudan_verify.yaml"))
    ap.add_argument("--fixtures", default=str(_ROOT / "tests" / "fixtures" / "jorudan"))
    args = ap.parse_args()

    fixtures = Path(args.fixtures)
    mapping = load_mapping(args.config)
    feed = load_feed(args.gtfs)
    index = json.loads((fixtures / "index.json").read_text(encoding="utf-8"))

    diffs: dict[str, dict] = {}
    n_missing = n_extra = 0
    for e in index:
        default = mapping.default_destination(e["route_id"], e["direction_id"])
        jor = parse_diagram(
            (fixtures / e["fixture"]).read_text(encoding="utf-8"), default
        )
        gtfs = departures(
            feed,
            stop_name=e["station"],
            route_id=e["route_id"],
            direction_id=e["direction_id"],
            service_id=e["service_id"],
        )
        d = check_times(jor, gtfs)  # 許容なしで生の差分を得る
        if d.ok:
            continue
        diffs[e["fixture"]] = {
            "missing": [list(t) for t in d.missing],
            "extra": [list(t) for t in d.extra],
        }
        n_missing += len(d.missing)
        n_extra += len(d.extra)

    out = {
        "_note": (
            "build/gtfs とジョルダン fixture の既知の発車時刻差（要調査）。"
            "七隈線の一部 1 分差・境界駅の直通便など。"
            "突合テストはこれを差し引いた新規差分のみ失敗とする。"
            "scripts/gen_expected_diffs.py で再生成。"
        ),
        "diffs": dict(sorted(diffs.items())),
    }
    path = fixtures / "expected_diffs.json"
    path.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"既知差分: {len(diffs)} ページ "
        f"(missing={n_missing}, extra={n_extra}) -> {path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
