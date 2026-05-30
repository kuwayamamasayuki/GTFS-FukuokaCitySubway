"""calendar.txt / calendar_dates.txt を生成する。

平日 / 土曜 / 休日 の 3 区分を calendar.txt に出力し、日本の祝日は
「休日」ダイヤで運行する想定で calendar_dates.txt に例外を書く
（該当日の通常サービスを除外し、休日サービスを追加）。
"""
from __future__ import annotations

import datetime as dt
import logging

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
CALENDAR_HEADER = ["service_id", *WEEKDAYS, "start_date", "end_date"]
CALENDAR_DATES_HEADER = ["service_id", "date", "exception_type"]

log = logging.getLogger("fukuoka_gtfs")


def _parse(d: str) -> dt.date:
    return dt.datetime.strptime(d, "%Y%m%d").date()


def build_calendar(services: dict[str, dict], start_date: str, end_date: str) -> list[dict]:
    rows = []
    for sid, flags in services.items():
        row = {"service_id": sid, "start_date": start_date, "end_date": end_date}
        for wd in WEEKDAYS:
            row[wd] = int(flags.get(wd, 0))
        rows.append(row)
    return rows


def build_calendar_dates(
    services: dict[str, dict],
    holiday_cfg: dict,
    start_date: str,
    end_date: str,
) -> list[dict]:
    apply_service = holiday_cfg.get("apply_service", "休日")
    use_jpholiday = bool(holiday_cfg.get("use_jpholiday", True))
    extra_holidays = set(holiday_cfg.get("extra_holiday_dates") or [])
    extra_normal = set(holiday_cfg.get("extra_normal_dates") or [])

    is_holiday = _build_holiday_check(use_jpholiday)

    # 曜日 index → その日に通常運行するサービス
    weekday_service: dict[int, str] = {}
    for sid, flags in services.items():
        for i, wd in enumerate(WEEKDAYS):
            if int(flags.get(wd, 0)) == 1:
                weekday_service[i] = sid

    rows: list[dict] = []
    d, end = _parse(start_date), _parse(end_date)
    one = dt.timedelta(days=1)
    while d <= end:
        ymd = d.strftime("%Y%m%d")
        holiday = (ymd in extra_holidays) or (ymd not in extra_normal and is_holiday(d))
        if holiday:
            normal = weekday_service.get(d.weekday())
            if normal and normal != apply_service:
                rows.append({"service_id": normal, "date": ymd, "exception_type": 2})
                rows.append({"service_id": apply_service, "date": ymd, "exception_type": 1})
        d += one
    log.info("calendar_dates: 祝日例外 %d 件", len(rows) // 2)
    return rows


def _build_holiday_check(use_jpholiday: bool):
    if not use_jpholiday:
        return lambda d: False
    try:
        import jpholiday
    except ImportError:  # 任意依存。無ければ祝日自動算出は無効化
        log.warning("jpholiday 未導入のため祝日の自動算出を無効化します")
        return lambda d: False
    return lambda d: jpholiday.is_holiday(d)
