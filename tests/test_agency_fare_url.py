"""agency.txt の agency_fare_url 列に関するテスト（Issue #29）。

- seed_reference.transform_agency が運賃案内 URL 列を補えること
- 公開済みデータ（reference_gtfs / dist）に列と値が存在すること（回帰ガード）
"""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FARE_URL = "https://subway.city.fukuoka.lg.jp/fare/index.php"


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


def test_transform_agency_adds_missing_column():
    """列が無い旧フィードを取り込むと agency_fare_url が補われる。"""
    seed = _load_seed()
    legacy = (
        "agency_id,agency_name,agency_url,agency_timezone,agency_lang,agency_phone\n"
        "3000020401307_0,福岡市地下鉄,https://subway.city.fukuoka.lg.jp/,Asia/Tokyo,ja,092-734-7800\n"
    )
    header, rows = seed.transform_agency(legacy)
    assert "agency_fare_url" in header
    assert rows[0]["agency_fare_url"] == FARE_URL


def test_transform_agency_preserves_existing_value():
    """既に値がある場合は上書きしない（冪等）。"""
    seed = _load_seed()
    existing = (
        "agency_id,agency_name,agency_url,agency_timezone,agency_lang,agency_phone,agency_fare_url\n"
        "a,n,u,Asia/Tokyo,ja,000,https://example.com/fare\n"
    )
    _, rows = seed.transform_agency(existing)
    assert rows[0]["agency_fare_url"] == "https://example.com/fare"


def test_reference_agency_has_fare_url():
    """reference_gtfs/agency.txt に運賃案内 URL が入っている。"""
    header, rows = _read_agency(ROOT / "reference_gtfs" / "agency.txt")
    assert "agency_fare_url" in header
    assert all(r["agency_fare_url"] == FARE_URL for r in rows)


def test_dist_agency_has_fare_url():
    """公開スナップショット dist/agency.txt も同じ値を持つ。"""
    header, rows = _read_agency(ROOT / "dist" / "agency.txt")
    assert "agency_fare_url" in header
    assert all(r["agency_fare_url"] == FARE_URL for r in rows)
