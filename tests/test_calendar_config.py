"""config/calendar.yaml の service_groups が満たすべき不変条件を実設定で検証する。

Issue #9: 2026/4/1 ダイヤ改正に合わせ、空港箱崎・七隈の両グループとも
有効期間の開始を 20260401 とする。あわせて、路線ごとに改正日（start_date）を
独立して設定できる構造であることを確認する。
"""
from __future__ import annotations

from pathlib import Path

from fukuoka_gtfs.builders.calendar_builder import build_calendar
from fukuoka_gtfs.config import Config

ROOT = Path(__file__).resolve().parents[1]


def _config() -> Config:
    return Config(ROOT)


def test_both_groups_start_on_2026_04_01():
    """空港箱崎・七隈の両グループとも 2026/4/1 改正（start_date=20260401）。"""
    groups = {g["id"]: g for g in _config().service_groups}
    assert groups["空港箱崎"]["start_date"] == "20260401"
    assert groups["七隈"]["start_date"] == "20260401"


def test_lines_map_to_expected_groups():
    """各路線が想定どおりのグループへ割り当たる。"""
    mapping = _config().route_to_group
    assert mapping["空港線"] == "空港箱崎"
    assert mapping["箱崎線"] == "空港箱崎"
    assert mapping["七隈線"] == "七隈"


def test_groups_can_hold_independent_revision_dates():
    """グループは独立した有効期間を持てる（改正日が路線で異なる将来にも対応）。

    各 service_group が自前の start_date/end_date を持ち、生成される calendar 行に
    そのまま反映されることを確認する。実設定では両グループ同日だが、構造として
    片方だけ別日に更新できることを担保する。
    """
    config = _config()
    groups = config.service_groups
    services = config.calendar["services"]

    # service_id ごとに start/end がグループ値で出力される
    rows = {r["service_id"]: r for r in build_calendar(services, groups)}
    for g in groups:
        for segment in services:
            row = rows[f"{g['id']}_{segment}"]
            assert row["start_date"] == g["start_date"]
            assert row["end_date"] == g["end_date"]

    # 仮に空港箱崎だけ別日に改正しても、七隈は影響を受けない（独立性）
    hypothetical = [
        {**groups[0], "start_date": "20270401"} if groups[0]["id"] == "空港箱崎" else groups[0],
        groups[1],
    ]
    rows2 = {r["service_id"]: r for r in build_calendar(services, hypothetical)}
    assert rows2["空港箱崎_平日"]["start_date"] == "20270401"
    assert rows2["七隈_平日"]["start_date"] == groups[1]["start_date"]


def test_feed_start_date_follows_groups():
    """feed_info の開始日（既定）はグループ start_date の最小値 = 20260401。"""
    config = _config()
    groups = config.service_groups
    start_date = config.feed.feed_start_date or min(g["start_date"] for g in groups)
    assert start_date == "20260401"
