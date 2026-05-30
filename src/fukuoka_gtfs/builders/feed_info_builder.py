"""feed_info.txt を生成し、フィードの有効期間を解決する。"""
from __future__ import annotations

import datetime as dt

from ..config import FeedCfg

FEED_INFO_HEADER = [
    "feed_publisher_name", "feed_publisher_url", "feed_lang",
    "feed_start_date", "feed_end_date", "feed_version",
    "feed_contact_email", "feed_contact_url",
]


def resolve_period(feed: FeedCfg, today: dt.date) -> tuple[str, str]:
    """(start_date, end_date) を YYYYMMDD で返す。未指定なら本日〜1 年後。"""
    start = feed.feed_start_date or today.strftime("%Y%m%d")
    if feed.feed_end_date:
        end = feed.feed_end_date
    else:
        s = dt.datetime.strptime(start, "%Y%m%d").date()
        try:
            end_date = s.replace(year=s.year + 1) - dt.timedelta(days=1)
        except ValueError:  # 2/29 対策
            end_date = s.replace(year=s.year + 1, day=28)
        end = end_date.strftime("%Y%m%d")
    return start, end


def build(feed: FeedCfg, start_date: str, end_date: str) -> list[dict]:
    version = feed.feed_version or start_date
    return [dict(
        feed_publisher_name=feed.feed_publisher_name,
        feed_publisher_url=feed.feed_publisher_url,
        feed_lang=feed.feed_lang,
        feed_start_date=start_date,
        feed_end_date=end_date,
        feed_version=version,
        feed_contact_email=feed.feed_contact_email,
        feed_contact_url=feed.feed_contact_url,
    )]
