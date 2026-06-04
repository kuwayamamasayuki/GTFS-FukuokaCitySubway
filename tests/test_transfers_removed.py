"""transfers.txt を廃止したことを保証する回帰テスト（Issue #40）。

七隈線の博多延伸に伴い、福岡市交通局は天神駅・天神南駅を連絡（乗換）駅とみなさなく
なった。これに合わせて連絡駅情報を表す transfers.txt をフィードから完全に削除する。

- 取り込み対象リスト（assembler.REFERENCE_FILES / seed_reference.COPY_FILES）に
  transfers.txt が含まれないこと
- 参照データ・公開スナップショット（reference_gtfs / dist / zip）に
  transfers.txt が存在しないこと（回帰ガード）
"""
from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

from fukuoka_gtfs.assembler import REFERENCE_FILES

ROOT = Path(__file__).resolve().parents[1]


def _load_seed():
    spec = importlib.util.spec_from_file_location(
        "seed_reference", ROOT / "scripts" / "seed_reference.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_assembler_does_not_reference_transfers():
    """統合処理が transfers.txt を取り込み対象に含めない。"""
    assert "transfers.txt" not in REFERENCE_FILES


def test_seed_does_not_copy_transfers():
    """シードスクリプトが transfers.txt を複製対象に含めない。"""
    seed = _load_seed()
    assert "transfers.txt" not in seed.COPY_FILES


def test_reference_gtfs_has_no_transfers():
    """参照データに transfers.txt が残っていない。"""
    assert not (ROOT / "reference_gtfs" / "transfers.txt").exists()


def test_dist_has_no_transfers():
    """公開スナップショット dist/ に transfers.txt が残っていない。"""
    assert not (ROOT / "dist" / "transfers.txt").exists()


def test_dist_zip_has_no_transfers():
    """配布 zip に transfers.txt が含まれていない。"""
    with zipfile.ZipFile(ROOT / "dist" / "FukuokaCitySubway.zip") as z:
        names = z.namelist()
    assert not any(n.endswith("transfers.txt") for n in names)
