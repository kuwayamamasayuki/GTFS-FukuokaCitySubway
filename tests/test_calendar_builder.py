import datetime as dt

import pytest

from fukuoka_gtfs.builders.calendar_builder import build_calendar, build_calendar_dates

SERVICES = {
    "平日": {"monday": 1, "tuesday": 1, "wednesday": 1, "thursday": 1, "friday": 1, "saturday": 0, "sunday": 0},
    "土曜": {"monday": 0, "tuesday": 0, "wednesday": 0, "thursday": 0, "friday": 0, "saturday": 1, "sunday": 0},
    "休日": {"monday": 0, "tuesday": 0, "wednesday": 0, "thursday": 0, "friday": 0, "saturday": 0, "sunday": 1},
}
GROUPS = [
    {"id": "空港箱崎", "lines": ["空港線", "箱崎線"], "start_date": "20260314", "end_date": "99991231"},
    {"id": "七隈", "lines": ["七隈線"], "start_date": "20250804", "end_date": "99991231"},
]
HOLIDAY = {"apply_service": "休日", "use_jpholiday": True, "horizon_years": 2,
           "extra_holiday_dates": [], "extra_normal_dates": []}


def test_build_calendar_groups_have_own_periods():
    rows = build_calendar(SERVICES, GROUPS)
    assert {r["service_id"] for r in rows} == {
        "空港箱崎_平日", "空港箱崎_土曜", "空港箱崎_休日", "七隈_平日", "七隈_土曜", "七隈_休日"}
    kh = next(r for r in rows if r["service_id"] == "空港箱崎_平日")
    assert kh["start_date"] == "20260314" and kh["end_date"] == "99991231"
    assert kh["monday"] == 1 and kh["saturday"] == 0
    n = next(r for r in rows if r["service_id"] == "七隈_平日")
    assert n["start_date"] == "20250804" and n["end_date"] == "99991231"


def test_holiday_dates_per_group():
    pytest.importorskip("jpholiday")
    today = dt.date(2026, 5, 1)
    rows = build_calendar_dates(SERVICES, GROUPS, HOLIDAY, today)
    by = {(r["service_id"], r["date"]): r["exception_type"] for r in rows}
    # 2026-05-04 みどりの日(月) → 各グループで 平日除外 + 休日追加
    assert by[("空港箱崎_平日", "20260504")] == 2
    assert by[("空港箱崎_休日", "20260504")] == 1
    assert by[("七隈_平日", "20260504")] == 2
    assert by[("七隈_休日", "20260504")] == 1


def test_horizon_caps_far_future_end_date():
    pytest.importorskip("jpholiday")
    today = dt.date(2026, 5, 1)  # horizon_years=2 → 2028-05-01 まで
    rows = build_calendar_dates(SERVICES, GROUPS, HOLIDAY, today)
    assert rows, "祝日例外が生成されるはず"
    assert all(r["date"] <= "20280501" for r in rows)  # 9999 でも打ち切られる
    # 七隈グループ(start 2025-08-04)の 2025 年祝日も含まれる
    assert any(r["date"].startswith("2025") for r in rows)


def test_extra_normal_date_overrides_holiday():
    today = dt.date(2026, 5, 1)
    rows = build_calendar_dates(SERVICES, [GROUPS[0]],
                                {**HOLIDAY, "extra_normal_dates": ["20260504"]}, today)
    assert all(r["date"] != "20260504" for r in rows)
