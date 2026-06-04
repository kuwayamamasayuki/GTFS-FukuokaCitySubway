"""calendar.txt / calendar_dates.txt を生成する。

有効期間は路線グループ・区分ごとに異なりうるため、service_id を ``<グループid>_<区分>``
（例: ``空港箱崎_平日``）として、グループ × 区分（平日/土曜/休日）の組で出力する。
start_date は ``service_groups[].start_dates`` で区分ごとに、end_date はグループ共通で持つ。
日本の祝日は「休日」ダイヤで運行する想定で calendar_dates に例外を書く（各区分は自身の
start_date 以降のみ例外を出す）。

end_date が遠い将来（例: 99991231）でも calendar_dates が無限に増えないよう、
祝日例外の生成は本日からの horizon_years（既定 2 年）で打ち切る。
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


def _service_id(group_id: str, segment: str) -> str:
    return f"{group_id}_{segment}"


def build_calendar(services: dict[str, dict], service_groups: list[dict]) -> list[dict]:
    """グループ × 区分 ごとに calendar 行を作る。

    start_date は区分ごと（``g["start_dates"][区分]``）、end_date はグループ共通。
    """
    rows = []
    for g in service_groups:
        for segment, flags in services.items():
            row = {"service_id": _service_id(g["id"], segment),
                   "start_date": g["start_dates"][segment], "end_date": g["end_date"]}
            for wd in WEEKDAYS:
                row[wd] = int(flags.get(wd, 0))
            rows.append(row)
    return rows


def build_calendar_dates(
    services: dict[str, dict],
    service_groups: list[dict],
    holiday_cfg: dict,
    today: dt.date,
) -> list[dict]:
    apply_segment = holiday_cfg.get("apply_service", "休日")
    use_jpholiday = bool(holiday_cfg.get("use_jpholiday", True))
    horizon_years = int(holiday_cfg.get("horizon_years", 2))
    extra_holidays = set(holiday_cfg.get("extra_holiday_dates") or [])
    extra_normal = set(holiday_cfg.get("extra_normal_dates") or [])
    is_holiday = _build_holiday_check(use_jpholiday)

    # 曜日 index → その日に通常運行する区分
    weekday_segment: dict[int, str] = {}
    for segment, flags in services.items():
        for i, wd in enumerate(WEEKDAYS):
            if int(flags.get(wd, 0)) == 1:
                weekday_segment[i] = segment

    horizon = _add_years(today, horizon_years)
    one = dt.timedelta(days=1)
    rows: list[dict] = []
    adds = 0
    for g in service_groups:
        seg_start = {seg: _parse(d) for seg, d in g["start_dates"].items()}
        d = min(seg_start.values())  # グループ内の最早 start_date から走査
        gend = min(_parse(g["end_date"]), horizon)  # 遠い将来を打ち切る
        apply_start = seg_start.get(apply_segment)
        while d <= gend:
            ymd = d.strftime("%Y%m%d")
            holiday = (ymd in extra_holidays) or (ymd not in extra_normal and is_holiday(d))
            if holiday:
                normal = weekday_segment.get(d.weekday())
                if normal and normal != apply_segment:
                    # 各区分は自身の start_date 以降のみ例外を出す（区分別の有効期間に整合）
                    if d >= seg_start.get(normal, d):
                        rows.append({"service_id": _service_id(g["id"], normal), "date": ymd, "exception_type": 2})
                    if apply_start is not None and d >= apply_start:
                        rows.append({"service_id": _service_id(g["id"], apply_segment), "date": ymd, "exception_type": 1})
                        adds += 1
            d += one
    log.info("calendar_dates: 祝日例外 %d 件（〜%s）", adds, horizon.strftime("%Y%m%d"))
    return rows


def _add_years(d: dt.date, years: int) -> dt.date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 2/29
        return d.replace(year=d.year + years, day=28)


def _build_holiday_check(use_jpholiday: bool):
    if not use_jpholiday:
        return lambda d: False
    try:
        import jpholiday
    except ImportError:  # 任意依存。無ければ祝日自動算出は無効化
        log.warning("jpholiday 未導入のため祝日の自動算出を無効化します")
        return lambda d: False
    return lambda d: jpholiday.is_holiday(d)
