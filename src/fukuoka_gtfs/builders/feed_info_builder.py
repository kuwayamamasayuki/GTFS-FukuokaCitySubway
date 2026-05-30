"""feed_info.txt を生成する。"""
from __future__ import annotations

from ..config import FeedCfg

FEED_INFO_HEADER = [
    "feed_publisher_name", "feed_publisher_url", "feed_lang",
    "feed_start_date", "feed_end_date", "feed_version",
    "feed_contact_email", "feed_contact_url",
]


def build(feed: FeedCfg, start_date: str, end_date: str, version: str) -> list[dict]:
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
