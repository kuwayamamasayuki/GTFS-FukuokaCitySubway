import pytest

from fukuoka_gtfs.builders.calendar_builder import build_calendar, build_calendar_dates

SERVICES = {
    "平日": {"monday": 1, "tuesday": 1, "wednesday": 1, "thursday": 1, "friday": 1, "saturday": 0, "sunday": 0},
    "土曜": {"monday": 0, "tuesday": 0, "wednesday": 0, "thursday": 0, "friday": 0, "saturday": 1, "sunday": 0},
    "休日": {"monday": 0, "tuesday": 0, "wednesday": 0, "thursday": 0, "friday": 0, "saturday": 0, "sunday": 1},
}
HOLIDAY = {"apply_service": "休日", "use_jpholiday": True, "extra_holiday_dates": [], "extra_normal_dates": []}


def test_build_calendar_three_services():
    rows = build_calendar(SERVICES, "20260401", "20270331")
    assert {r["service_id"] for r in rows} == {"平日", "土曜", "休日"}
    weekday = next(r for r in rows if r["service_id"] == "平日")
    assert weekday["monday"] == 1 and weekday["saturday"] == 0
    assert weekday["start_date"] == "20260401" and weekday["end_date"] == "20270331"


def test_holiday_weekday_switches_to_holiday_service():
    jpholiday = pytest.importorskip("jpholiday")
    # 2026-05-04 みどりの日(月)・2026-05-05 こどもの日(火) は祝日
    rows = build_calendar_dates(SERVICES, HOLIDAY, "20260504", "20260505")
    by_date = {}
    for r in rows:
        by_date.setdefault(r["date"], {})[r["service_id"]] = r["exception_type"]
    assert by_date["20260504"]["平日"] == 2   # 平日を除外
    assert by_date["20260504"]["休日"] == 1   # 休日を追加
    assert by_date["20260505"]["休日"] == 1


def test_extra_normal_date_overrides_holiday():
    rows = build_calendar_dates(SERVICES, {**HOLIDAY, "extra_normal_dates": ["20260504"]},
                                "20260504", "20260504")
    assert rows == []  # 祝日でも通常ダイヤに戻すため例外なし
