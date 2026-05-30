"""パッケージ共通の例外。"""
from __future__ import annotations


class FukuokaGtfsError(Exception):
    """このパッケージが送出する全例外の基底。"""


class LayoutError(FukuokaGtfsError):
    """Excel のレイアウトが想定と異なるときに送出する。

    ダイヤ改正等でレイアウトが変わった場合に、どのシート・行・列・セル値が
    想定と食い違ったかを利用者へ明示するために用いる。
    """


class MappingError(FukuokaGtfsError):
    """駅名から stop_id を解決できない等、対応付けに失敗したときに送出する。"""
