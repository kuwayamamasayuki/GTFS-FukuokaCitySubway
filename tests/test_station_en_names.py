"""Issue #15: 駅名の英語表記の修正。

福岡空港 → "Fukuoka Airport"、櫛田神社前 → "Kushida Shrine"。
公開データ(reference_gtfs/translations.txt)と、再シード時の transform_translations の
両方を検証する（再シードで旧表記へ逆戻りしないことを保証）。
"""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS = ROOT / "reference_gtfs" / "translations.txt"

# 修正後の正しい英語表記（translations.txt 既存の慣例に合わせ Title Case）
EXPECTED_EN = {
    "福岡空港": "Fukuoka Airport",
    "櫛田神社前": "Kushida Shrine",
}
# 修正前の誤表記（残っていてはいけない）
LEGACY_EN = {
    "福岡空港": "Fukuokakuko(Airport)",
    "櫛田神社前": "Kushida Jinja-mae",
}


def _load_seed_reference():
    path = ROOT / "scripts" / "seed_reference.py"
    spec = importlib.util.spec_from_file_location("seed_reference", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _en_names_from_translations() -> dict[str, str]:
    with TRANSLATIONS.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {
        r["field_value"]: r["translation"]
        for r in rows
        if r["table_name"] == "stops"
        and r["field_name"] == "stop_name"
        and r["language"] == "en"
    }


@pytest.mark.parametrize("ja,en", list(EXPECTED_EN.items()))
def test_reference_translations_have_corrected_en(ja, en):
    """公開される translations.txt が修正後の英語表記を持つ。"""
    names = _en_names_from_translations()
    assert names.get(ja) == en


@pytest.mark.parametrize("ja,legacy", list(LEGACY_EN.items()))
def test_reference_translations_no_legacy_en(ja, legacy):
    """旧（誤）表記が残っていないこと。"""
    names = _en_names_from_translations()
    assert names.get(ja) != legacy


def test_seed_reference_transform_applies_en_overrides():
    """再シードしても transform_translations が修正後の英語表記を出力する。

    福岡空港の英語名は上流フィード由来で誤表記(Fukuokakuko(Airport))を含むため、
    seed_reference 側の上書きが効くことを確認する。櫛田神社前は新駅定義から付与される。
    """
    seed = _load_seed_reference()
    # 旧スキーマ(trans_id,lang,translation) の最小入力。福岡空港は誤表記を含む。
    old_text = (
        "trans_id,lang,translation\n"
        "福岡空港,ja,福岡空港\n"
        "福岡空港,en,Fukuokakuko(Airport)\n"
    )
    stops_rows = [{"stop_name": "福岡空港"}, {"stop_name": "櫛田神社前"}]
    _, out = seed.transform_translations(old_text, stops_rows)
    en = {
        r["field_value"]: r["translation"]
        for r in out
        if r["field_name"] == "stop_name" and r["language"] == "en"
    }
    assert en["福岡空港"] == "Fukuoka Airport"
    assert en["櫛田神社前"] == "Kushida Shrine"
