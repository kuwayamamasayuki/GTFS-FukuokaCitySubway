"""時刻表 Excel をダウンロードする。"""
from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

import requests

from .config import Config

log = logging.getLogger("fukuoka_gtfs")
_UA = "fukuoka-gtfs/1.0 (+https://github.com/kuwayamamasayuki/GTFS-FukuokaCitySubway)"


def download_all(config: Config, retries: int = 4) -> dict[str, str]:
    """全 source をダウンロードして data/ に保存。{filename: sha256} を返す。"""
    config.data_dir.mkdir(parents=True, exist_ok=True)
    digests: dict[str, str] = {}
    for src in config.sources:
        dest = config.data_dir / src.filename
        content = _get(src.url, retries)
        dest.write_bytes(content)
        sha = hashlib.sha256(content).hexdigest()
        digests[src.filename] = sha
        log.info("取得: %s (%d bytes, sha256=%s…)", src.filename, len(content), sha[:12])
    (config.data_dir / "sources.sha256").write_text(
        "\n".join(f"{sha}  {name}" for name, sha in digests.items()) + "\n", encoding="utf-8",
    )
    return digests


def _get(url: str, retries: int) -> bytes:
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers={"User-Agent": _UA}, timeout=60)
            r.raise_for_status()
            return r.content
        except Exception as e:  # noqa: BLE001 (ネットワークは一時失敗しうる)
            last = e
            log.warning("ダウンロード失敗 (%d/%d) %s: %s", attempt, retries, url, e)
            time.sleep(2 * attempt)
    raise RuntimeError(f"ダウンロードに失敗: {url}") from last
