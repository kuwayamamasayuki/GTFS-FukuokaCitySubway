"""routes.txt の route_sort_order 列に関するテスト（Issue #33）。

route_sort_order は GTFS 標準のオプションフィールドで、値が小さいほど経路一覧で
先に表示される。福岡市地下鉄では路線記号 K/H/N の順（空港線→箱崎線→七隈線）に
合わせて 1/2/3 を割り当てる。
仕様: https://gtfs.org/documentation/schedule/reference/#routestxt

- seed_reference.transform_routes が route_sort_order 列を補えること
- 値が空港線→箱崎線→七隈線 の昇順になること
- 公開済みデータ（reference_gtfs / dist / zip）に列と値が存在すること（回帰ガード）
"""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ORDER = {"空港線": "1", "箱崎線": "2", "七隈線": "3"}


def _load_seed():
    spec = importlib.util.spec_from_file_location(
        "seed_reference", ROOT / "scripts" / "seed_reference.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_routes(path: Path) -> tuple[list[str], list[dict]]:
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    return list(reader.fieldnames or []), list(reader)


def test_transform_routes_adds_missing_sort_order_column():
    """列が無い旧フィードを取り込むと route_sort_order が補われる。"""
    seed = _load_seed()
    legacy = (
        "route_id,agency_id,route_short_name,route_long_name,route_type,route_color\n"
        "空港線,3000020401307_0,空港線,,1,f7931d\n"
        "箱崎線,3000020401307_0,箱崎線,,1,00aeef\n"
        "七隈線,3000020401307_0,七隈線,,1,009157\n"
    )
    header, rows = seed.transform_routes(legacy)
    assert "route_sort_order" in header
    assert {r["route_id"]: r["route_sort_order"] for r in rows} == EXPECTED_ORDER


def test_transform_routes_orders_kuko_hakozaki_nanakuma():
    """空港線→箱崎線→七隈線 の昇順になっている。"""
    seed = _load_seed()
    legacy = (
        "route_id,agency_id,route_short_name,route_long_name,route_type,route_color\n"
        "空港線,3000020401307_0,空港線,,1,f7931d\n"
        "箱崎線,3000020401307_0,箱崎線,,1,00aeef\n"
        "七隈線,3000020401307_0,七隈線,,1,009157\n"
    )
    _, rows = seed.transform_routes(legacy)
    by_order = sorted(rows, key=lambda r: int(r["route_sort_order"]))
    assert [r["route_id"] for r in by_order] == ["空港線", "箱崎線", "七隈線"]


def test_transform_routes_preserves_existing_value():
    """既に値がある場合は上書きしない（冪等）。"""
    seed = _load_seed()
    existing = (
        "route_id,agency_id,route_short_name,route_long_name,route_type,route_color,route_sort_order\n"
        "空港線,3000020401307_0,空港線,,1,f7931d,9\n"
    )
    _, rows = seed.transform_routes(existing)
    assert rows[0]["route_sort_order"] == "9"


def test_reference_routes_has_sort_order():
    """reference_gtfs/routes.txt に route_sort_order が入っている。"""
    header, rows = _read_routes(ROOT / "reference_gtfs" / "routes.txt")
    assert "route_sort_order" in header
    assert {r["route_id"]: r["route_sort_order"] for r in rows} == EXPECTED_ORDER


def test_dist_routes_has_sort_order():
    """公開スナップショット dist/routes.txt も同じ値を持つ。"""
    header, rows = _read_routes(ROOT / "dist" / "routes.txt")
    assert "route_sort_order" in header
    assert {r["route_id"]: r["route_sort_order"] for r in rows} == EXPECTED_ORDER


def test_dist_zip_routes_has_sort_order():
    """配布 zip 内の routes.txt も同じ値を持つ。"""
    import zipfile

    with zipfile.ZipFile(ROOT / "dist" / "FukuokaCitySubway.zip") as z:
        name = next(n for n in z.namelist() if n.endswith("routes.txt") and "_jp" not in n)
        text = z.read(name).decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    assert "route_sort_order" in (reader.fieldnames or [])
    assert {r["route_id"]: r["route_sort_order"] for r in reader} == EXPECTED_ORDER
