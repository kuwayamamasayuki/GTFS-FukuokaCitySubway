"""trips.trip_headsign（行先）の翻訳に関するテスト（Issue #46）。

translations.txt は従来 stops の駅名と routes 名（en / ja-Hrkt）のみを持っていた。
行先（trip_headsign）も多言語表示できるよう、trips/trip_headsign の翻訳を追加する。

GTFS の translations は table_name + field_name + field_value で引かれるため、
たとえ "博多" が stops/stop_name で翻訳済みでも、trips/trip_headsign="博多" は
別レコードとして翻訳行が無ければ多言語表示されない。よって行先用の行を別途用意する。

- seed_reference.transform_translations が trips/trip_headsign 行を出力すること
- 駅名と一致する行先は stops の訳語と一致すること（相互直通の JR 駅は別表から補完）
- 公開済みデータ（reference_gtfs / dist / zip）に行先翻訳が存在すること（回帰ガード）
- dist/trips.txt の全行先が漏れなく翻訳されていること
"""
from __future__ import annotations

import csv
import importlib.util
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "reference_gtfs" / "translations.txt"
DIST = ROOT / "dist" / "translations.txt"
DIST_ZIP = ROOT / "dist" / "FukuokaCitySubway.zip"
TRIPS = ROOT / "dist" / "trips.txt"

# 行先（trip_headsign）の正しい翻訳。地下鉄駅は stops の訳語に揃え、
# 相互直通で乗り入れる JR 筑肥線の駅（地下鉄 stops に無い）も網羅する。
EXPECTED = {
    "姪浜": {"ja-Hrkt": "めいのはま", "en": "Meinohama"},
    "西新": {"ja-Hrkt": "にしじん", "en": "Nishijin"},
    "中洲川端": {"ja-Hrkt": "なかすかわばた", "en": "Nakasu-Kawabata"},
    "貝塚": {"ja-Hrkt": "かいづか", "en": "Kaizuka"},
    "博多": {"ja-Hrkt": "はかた", "en": "Hakata"},
    "福岡空港": {"ja-Hrkt": "ふくおかくうこう", "en": "Fukuoka Airport"},
    "橋本": {"ja-Hrkt": "はしもと", "en": "Hashimoto"},
    "唐津": {"ja-Hrkt": "からつ", "en": "Karatsu"},
    "西唐津": {"ja-Hrkt": "にしからつ", "en": "Nishi-Karatsu"},
    "筑前前原": {"ja-Hrkt": "ちくぜんまえばる", "en": "Chikuzen-Maebaru"},
    "筑前深江": {"ja-Hrkt": "ちくぜんふかえ", "en": "Chikuzen-Fukae"},
}


def _load_seed():
    spec = importlib.util.spec_from_file_location(
        "seed_reference", ROOT / "scripts" / "seed_reference.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _read_rows(text: str) -> list[dict]:
    return list(csv.DictReader(text.splitlines()))


def _headsign_translations(rows: list[dict]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for r in rows:
        if r["table_name"] == "trips" and r["field_name"] == "trip_headsign":
            out.setdefault(r["field_value"], {})[r["language"]] = r["translation"]
    return out


# --- 公開データ（回帰ガード） -------------------------------------------------

@pytest.mark.parametrize("path", [REFERENCE, DIST], ids=["reference", "dist"])
def test_published_translations_have_trip_headsigns(path):
    """reference_gtfs / dist の translations.txt に行先翻訳が揃っている。"""
    rows = _read_rows(path.read_text(encoding="utf-8-sig"))
    got = _headsign_translations(rows)
    for name, langs in EXPECTED.items():
        assert got.get(name) == langs, f"{path.name}: {name} の翻訳が不一致"


def test_dist_zip_has_trip_headsigns():
    """配布 zip 内の translations.txt も行先翻訳を持つ。"""
    with zipfile.ZipFile(DIST_ZIP) as z:
        name = next(n for n in z.namelist() if n.endswith("translations.txt"))
        text = z.read(name).decode("utf-8-sig")
    got = _headsign_translations(_read_rows(text))
    for name, langs in EXPECTED.items():
        assert got.get(name) == langs


def test_all_trip_headsigns_are_translated():
    """dist/trips.txt に現れる全ての trip_headsign が翻訳されている（漏れ検知）。"""
    trips = _read_rows(TRIPS.read_text(encoding="utf-8-sig"))
    used = {r["trip_headsign"] for r in trips if r.get("trip_headsign")}
    got = _headsign_translations(_read_rows(DIST.read_text(encoding="utf-8-sig")))
    missing = used - got.keys()
    assert not missing, f"翻訳が無い行先: {sorted(missing)}"
    # 全ての行先に en / ja-Hrkt の両方が揃っている
    for name in used:
        assert set(got[name]) == {"ja-Hrkt", "en"}, f"{name} の言語が不足"


def test_headsign_matches_stop_translation():
    """駅名と一致する行先は stops/stop_name の訳語と同一であること（表記揺れ防止）。"""
    rows = _read_rows(DIST.read_text(encoding="utf-8-sig"))
    stop_tr: dict[str, dict[str, str]] = {}
    for r in rows:
        if r["table_name"] == "stops" and r["field_name"] == "stop_name":
            stop_tr.setdefault(r["field_value"], {})[r["language"]] = r["translation"]
    head_tr = _headsign_translations(rows)
    for name, langs in head_tr.items():
        if name in stop_tr:
            assert langs == stop_tr[name], f"{name}: 行先と駅名で訳語が食い違う"


# --- 再シード（seed_reference.transform_translations） -------------------------

def test_transform_emits_trip_headsign_rows():
    """再シードしても transform_translations が trips/trip_headsign を出力する。"""
    seed = _load_seed()
    # 旧スキーマ最小入力：駅名（博多）と相互直通 JR 駅は別表から補完される。
    old_text = (
        "trans_id,lang,translation\n"
        "博多,ja,博多\n"
        "博多,ja-Hrkt,はかた\n"
        "博多,en,Hakata\n"
    )
    stops_rows = [{"stop_name": "博多"}]
    _, out = seed.transform_translations(old_text, stops_rows)
    got = _headsign_translations(out)
    # 駅名由来（stops の訳語を再利用）
    assert got.get("博多") == {"ja-Hrkt": "はかた", "en": "Hakata"}
    # JR 筑肥線直通（別表 TRIP_HEADSIGN_EXTRA から補完）
    assert got.get("唐津") == {"ja-Hrkt": "からつ", "en": "Karatsu"}
    assert got.get("筑前前原") == {"ja-Hrkt": "ちくぜんまえばる", "en": "Chikuzen-Maebaru"}


def test_transform_headsign_applies_en_override():
    """福岡空港の英語名は上流の誤表記でなく正式名 'Fukuoka Airport' になる。"""
    seed = _load_seed()
    old_text = (
        "trans_id,lang,translation\n"
        "福岡空港,ja,福岡空港\n"
        "福岡空港,ja-Hrkt,ふくおかくうこう\n"
        "福岡空港,en,Fukuokakuko(Airport)\n"
    )
    stops_rows = [{"stop_name": "福岡空港"}]
    _, out = seed.transform_translations(old_text, stops_rows)
    got = _headsign_translations(out)
    assert got.get("福岡空港") == {"ja-Hrkt": "ふくおかくうこう", "en": "Fukuoka Airport"}
