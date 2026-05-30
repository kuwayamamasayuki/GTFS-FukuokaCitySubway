"""ジョルダンの福岡市地下鉄「発着・料金検索」結果ページ（nsresult）の運賃パーサ。

結果 HTML 中に普通料金が `普通料金 &nbsp;210&nbsp; 円` の形で現れる。数字と `円` の
あいだに `&nbsp;`・空白・タグが挟まるため、それらを吸収して数値（円）を取り出す。
"""

from __future__ import annotations

import re

__all__ = ["parse_fare"]

# 「普通料金 … <数値> … 円」。あいだの &nbsp;・空白・タグを読み飛ばす。
_NOISE = r"(?:&nbsp;|&#160;|\s|<[^>]+>)*"
_FARE = re.compile(rf"普通料金{_NOISE}([0-9,]+){_NOISE}円")


def parse_fare(html: str) -> int | None:
    """結果 HTML から普通料金（円）を返す。見つからなければ None。"""
    m = _FARE.search(html)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))
