"""agency.txt の cemv_support 列に関するテスト（Issue #31）。

cemv_support は GTFS 標準のオプションフィールドで、タッチ決済（Contactless EMV）
乗車に対応しているかを表す Enum（0 または空=情報なし / 1=対応 / 2=非対応）。
仕様: https://gtfs.org/documentation/schedule/reference/#agencytxt
福岡市地下鉄は 2024-04-01 から全 3 路線・全 36 駅でタッチ決済に対応しているため、
値は "1"（対応）とする。

- seed_reference.transform_agency が cemv_support 列を補えること
- 公開済みデータ（reference_gtfs / dist）に列と値が存在すること（回帰ガード）
"""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CEMV_SUPPORT = "1"


def _load_seed():
    spec = importlib.util.spec_from_file_location(
        "seed_reference", ROOT / "scripts" / "seed_reference.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_agency(path: Path) -> tuple[list[str], list[dict]]:
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    return list(reader.fieldnames or []), list(reader)


def test_transform_agency_adds_missing_cemv_column():
    """列が無い旧フィードを取り込むと cemv_support が補われる。"""
    seed = _load_seed()
    legacy = (
        "agency_id,agency_name,agency_url,agency_timezone,agency_lang,agency_phone\n"
        "3000020401307_0,福岡市地下鉄,https://subway.city.fukuoka.lg.jp/,Asia/Tokyo,ja,092-734-7800\n"
    )
    header, rows = seed.transform_agency(legacy)
    assert "cemv_support" in header
    assert rows[0]["cemv_support"] == CEMV_SUPPORT


def test_transform_agency_preserves_existing_cemv_value():
    """既に値がある場合は上書きしない（冪等）。"""
    seed = _load_seed()
    existing = (
        "agency_id,agency_name,agency_url,agency_timezone,agency_lang,agency_phone,cemv_support\n"
        "a,n,u,Asia/Tokyo,ja,000,0\n"
    )
    _, rows = seed.transform_agency(existing)
    assert rows[0]["cemv_support"] == "0"


def test_reference_agency_has_cemv_support():
    """reference_gtfs/agency.txt に cemv_support が入っている。"""
    header, rows = _read_agency(ROOT / "reference_gtfs" / "agency.txt")
    assert "cemv_support" in header
    assert all(r["cemv_support"] == CEMV_SUPPORT for r in rows)


def test_dist_agency_has_cemv_support():
    """公開スナップショット dist/agency.txt も同じ値を持つ。"""
    header, rows = _read_agency(ROOT / "dist" / "agency.txt")
    assert "cemv_support" in header
    assert all(r["cemv_support"] == CEMV_SUPPORT for r in rows)


def test_dist_zip_agency_has_cemv_support():
    """配布 zip 内の agency.txt も同じ値を持つ。"""
    import zipfile

    with zipfile.ZipFile(ROOT / "dist" / "FukuokaCitySubway.zip") as z:
        name = next(n for n in z.namelist() if n.endswith("agency.txt"))
        text = z.read(name).decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    assert "cemv_support" in (reader.fieldnames or [])
    assert all(r["cemv_support"] == CEMV_SUPPORT for r in reader)
