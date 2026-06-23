"""config/calendar.yaml の service_groups が満たすべき不変条件を実設定で検証する。

Issue #42: 2026/4/1 開始の「ミッドナイト・トレイン」（月〜土の終電延長）に伴い、
平日・土曜の start_date を 20260401 とする。休日（日曜・祝日）は 4/1 改正の対象外なので
従来の路線別改正日を維持する。区分（平日/土曜/休日）ごとに start_date を独立して
設定できる構造であることを確認する。
"""
from __future__ import annotations

from pathlib import Path

from fukuoka_gtfs.builders.calendar_builder import build_calendar
from fukuoka_gtfs.config import Config

ROOT = Path(__file__).resolve().parents[1]


def _config() -> Config:
    return Config(ROOT)


def test_weekday_and_saturday_start_on_2026_04_01():
    """平日・土曜は 2026/4/1 改正（start_date=20260401）。両グループ共通。"""
    groups = {g["id"]: g for g in _config().service_groups}
    for gid in ("空港箱崎", "七隈"):
        assert groups[gid]["start_dates"]["平日"] == "20260401"
        assert groups[gid]["start_dates"]["土曜"] == "20260401"


def test_holiday_keeps_previous_revision_date():
    """休日は 4/1 改正の対象外。従来の路線別改正日を維持する。"""
    groups = {g["id"]: g for g in _config().service_groups}
    assert groups["空港箱崎"]["start_dates"]["休日"] == "20260314"
    assert groups["七隈"]["start_dates"]["休日"] == "20250804"


def test_lines_map_to_expected_groups():
    """各路線が想定どおりのグループへ割り当たる。"""
    mapping = _config().route_to_group
    assert mapping["空港線"] == "空港箱崎"
    assert mapping["箱崎線"] == "空港箱崎"
    assert mapping["七隈線"] == "七隈"


def test_segments_reflect_their_own_start_date_in_calendar():
    """生成される calendar 行に、区分ごとの start_date がそのまま反映される。"""
    config = _config()
    groups = config.service_groups
    services = config.calendar["services"]

    rows = {r["service_id"]: r for r in build_calendar(services, groups)}
    for g in groups:
        for segment in services:
            row = rows[f"{g['id']}_{segment}"]
            assert row["start_date"] == g["start_dates"][segment]
            assert row["end_date"] == g["end_date"]


def test_groups_can_hold_independent_revision_dates():
    """グループは独立した有効期間を持てる（改正日が路線で異なる将来にも対応）。

    片方のグループだけ別日に改正しても、もう片方は影響を受けないことを確認する。
    """
    config = _config()
    groups = config.service_groups
    services = config.calendar["services"]

    hypothetical = [
        {**groups[0], "start_dates": {**groups[0]["start_dates"], "平日": "20270401"}}
        if groups[0]["id"] == "空港箱崎" else groups[0],
        groups[1],
    ]
    rows2 = {r["service_id"]: r for r in build_calendar(services, hypothetical)}
    assert rows2["空港箱崎_平日"]["start_date"] == "20270401"
    assert rows2["七隈_平日"]["start_date"] == groups[1]["start_dates"]["平日"]


def test_feed_start_date_follows_groups():
    """feed_info の開始日（既定）は全区分 start_date の最小値 = 20250804（七隈休日）。"""
    config = _config()
    groups = config.service_groups
    start_date = config.feed.feed_start_date or min(
        d for g in groups for d in g["start_dates"].values()
    )
    assert start_date == "20250804"
