"""時刻表 Excel をダウンロードする。

多くの自治体サイトは WAF を備え、データセンター IP（CI の GitHub Actions ランナー等）
からの非ブラウザ的アクセスに対して間欠的に 403 を返すことがある。そのため
ブラウザに近いヘッダを送り、一時的とみなせる HTTP ステータス（403/429/5xx 等）は
指数バックオフで再試行する。
"""
from __future__ import annotations

import hashlib
import logging
import time
from urllib.parse import urlsplit

import requests

from .config import Config

log = logging.getLogger("fukuoka_gtfs")

# ブラウザに近いヘッダ。WAF が非ブラウザ UA を弾く構成でも通りやすくする。
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/vnd.ms-excel,application/octet-stream,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

# 一時的（再試行する価値がある）とみなす HTTP ステータス。
# 403 は WAF の間欠ブロック、429 はレート制限、5xx はサーバ一時障害。
_RETRY_STATUS = {403, 408, 425, 429, 500, 502, 503, 504}


def download_all(config: Config, retries: int = 4) -> dict[str, str]:
    """全 source をダウンロードして data/ に保存。{filename: sha256} を返す。"""
    config.data_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(_HEADERS)
    digests: dict[str, str] = {}
    for src in config.sources:
        dest = config.data_dir / src.filename
        content = _get(session, src.url, retries)
        dest.write_bytes(content)
        sha = hashlib.sha256(content).hexdigest()
        digests[src.filename] = sha
        log.info("取得: %s (%d bytes, sha256=%s…)", src.filename, len(content), sha[:12])
    (config.data_dir / "sources.sha256").write_text(
        "\n".join(f"{sha}  {name}" for name, sha in digests.items()) + "\n", encoding="utf-8",
    )
    return digests


def _backoff_seconds(attempt: int) -> float:
    """指数バックオフ（上限 30 秒）。attempt は 1 始まり。"""
    return min(30.0, 2.0 ** attempt)


def _get(session: requests.Session, url: str, retries: int) -> bytes:
    # Referer をサイト直下にしておくと WAF の素性チェックを通りやすい。
    parts = urlsplit(url)
    headers = {"Referer": f"{parts.scheme}://{parts.netloc}/"}
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, headers=headers, timeout=60)
            r.raise_for_status()
            return r.content
        except requests.HTTPError as e:
            last = e
            status = e.response.status_code if e.response is not None else None
            log.warning("ダウンロード失敗 (%d/%d) %s: %s", attempt, retries, url, e)
            if status not in _RETRY_STATUS:
                break  # 404 など永続的エラーは再試行しても無駄
        except requests.RequestException as e:  # 接続・タイムアウト等は一時的
            last = e
            log.warning("ダウンロード失敗 (%d/%d) %s: %s", attempt, retries, url, e)
        if attempt < retries:
            time.sleep(_backoff_seconds(attempt))
    raise RuntimeError(f"ダウンロードに失敗: {url}") from last
