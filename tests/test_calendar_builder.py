import datetime as dt

import pytest

from fukuoka_gtfs.builders.calendar_builder import build_calendar, build_calendar_dates

SERVICES = {
    "平日": {"monday": 1, "tuesday": 1, "wednesday": 1, "thursday": 1, "friday": 1, "saturday": 0, "sunday": 0},
    "土曜": {"monday": 0, "tuesday": 0, "wednesday": 0, "thursday": 0, "friday": 0, "saturday": 1, "sunday": 0},
    "休日": {"monday": 0, "tuesday": 0, "wednesday": 0, "thursday": 0, "friday": 0, "saturday": 0, "sunday": 1},
}
# Issue #42: 平日・土曜は 2026/4/1 改正、休日は対象外（従来の改正日）。区分ごとに start_date を持つ。
GROUPS = [
    {"id": "空港箱崎", "lines": ["空港線", "箱崎線"], "end_date": "99991231",
     "start_dates": {"平日": "20260401", "土曜": "20260401", "休日": "20260314"}},
    {"id": "七隈", "lines": ["七隈線"], "end_date": "99991231",
     "start_dates": {"平日": "20260401", "土曜": "20260401", "休日": "20250804"}},
]
HOLIDAY = {"apply_service": "休日", "use_jpholiday": True, "horizon_years": 2,
           "extra_holiday_dates": [], "extra_normal_dates": []}


def test_build_calendar_segments_have_own_start_date():
    rows = build_calendar(SERVICES, GROUPS)
    assert {r["service_id"] for r in rows} == {
        "空港箱崎_平日", "空港箱崎_土曜", "空港箱崎_休日", "七隈_平日", "七隈_土曜", "七隈_休日"}
    by = {r["service_id"]: r for r in rows}
    # 平日・土曜は 20260401、休日は従来の改正日（グループ別）
    assert by["空港箱崎_平日"]["start_date"] == "20260401"
    assert by["空港箱崎_土曜"]["start_date"] == "20260401"
    assert by["空港箱崎_休日"]["start_date"] == "20260314"
    assert by["七隈_平日"]["start_date"] == "20260401"
    assert by["七隈_土曜"]["start_date"] == "20260401"
    assert by["七隈_休日"]["start_date"] == "20250804"
    # end_date はグループ値が全区分に反映される
    assert all(r["end_date"] == "99991231" for r in rows)
    # 曜日フラグは区分どおり
    assert by["空港箱崎_平日"]["monday"] == 1 and by["空港箱崎_平日"]["saturday"] == 0
    assert by["空港箱崎_土曜"]["saturday"] == 1
    assert by["空港箱崎_休日"]["sunday"] == 1


def test_holiday_dates_per_group():
    pytest.importorskip("jpholiday")
    today = dt.date(2026, 5, 1)
    rows = build_calendar_dates(SERVICES, GROUPS, HOLIDAY, today)
    by = {(r["service_id"], r["date"]): r["exception_type"] for r in rows}
    # 2026-05-04 みどりの日(月) → 各グループで 平日除外 + 休日追加（平日は 20260401 開始なので有効）
    assert by[("空港箱崎_平日", "20260504")] == 2
    assert by[("空港箱崎_休日", "20260504")] == 1
    assert by[("七隈_平日", "20260504")] == 2
    assert by[("七隈_休日", "20260504")] == 1


def test_normal_segment_removed_only_after_its_start_date():
    """平日が未開始（4/1 より前）の祝日には平日除外を出さず、休日追加のみ行う。"""
    pytest.importorskip("jpholiday")
    today = dt.date(2026, 5, 1)
    rows = build_calendar_dates(SERVICES, GROUPS, HOLIDAY, today)
    by = {(r["service_id"], r["date"]): r["exception_type"] for r in rows}
    # 2026-03-20 春分の日(金) は平日の start_date(20260401) より前
    assert ("空港箱崎_平日", "20260320") not in by  # 平日は未開始 → 除外例外を出さない
    assert ("七隈_平日", "20260320") not in by
    # 休日は 20260314 / 20250804 開始済み → 休日追加は出力される
    assert by[("空港箱崎_休日", "20260320")] == 1
    assert by[("七隈_休日", "20260320")] == 1


def test_holiday_add_only_after_holiday_start_date():
    """休日区分の start_date より前の祝日には休日追加を出さない。"""
    pytest.importorskip("jpholiday")
    today = dt.date(2025, 1, 1)
    # 七隈休日は 20250804 開始。2025-07-21 海の日 はそれより前。
    rows = build_calendar_dates(SERVICES, [GROUPS[1]], HOLIDAY, today)
    by = {(r["service_id"], r["date"]): r["exception_type"] for r in rows}
    assert ("七隈_休日", "20250721") not in by
    # 開始後の祝日（2025-09-15 敬老の日）は出力される
    assert by[("七隈_休日", "20250915")] == 1


def test_horizon_caps_far_future_end_date():
    pytest.importorskip("jpholiday")
    today = dt.date(2026, 5, 1)  # horizon_years=2 → 2028-05-01 まで
    rows = build_calendar_dates(SERVICES, GROUPS, HOLIDAY, today)
    assert rows, "祝日例外が生成されるはず"
    assert all(r["date"] <= "20280501" for r in rows)  # 9999 でも打ち切られる
    # 七隈グループ(休日 start 2025-08-04)の 2025 年祝日も含まれる
    assert any(r["date"].startswith("2025") for r in rows)


def test_extra_normal_date_overrides_holiday():
    today = dt.date(2026, 5, 1)
    rows = build_calendar_dates(SERVICES, [GROUPS[0]],
                                {**HOLIDAY, "extra_normal_dates": ["20260504"]}, today)
    assert all(r["date"] != "20260504" for r in rows)
