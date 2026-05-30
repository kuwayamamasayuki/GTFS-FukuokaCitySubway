"""ジョルダンの福岡市地下鉄ダイヤ詳細ページ（diagramdtl）の HTML パーサ。

時刻表本体は PC 用 `ttArea pc`。各時間 `ttBox` の `dt.ttToggle>span` が「時」、
各 `dd` がホーム列、`li.linindexlink` 内の `span.legend`（行先記号）と `<a>`（分）が 1 便。
ホーム列は方面単位に統合する。

行先の決め方（凡例 `legendArea` の各 dd は「記号=説明」形式）:
  * 凡例値が「素の駅名」（例 `福岡空港ゆき`→福岡空港, `唐津`）のものだけを採用する。
  * 「無印」の値が既定行先。凡例に無印が無ければ ``default_destination`` 引数を既定とする。
  * 「…で…に接続/のりかえ…」のような注記（例 `●印`, `前●印`）は行先を変えない＝既定のまま。
  * 凡例 dd が無い路線（七隈線）は全便が ``default_destination``（終端駅）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["Departure", "parse_diagram", "parse_legend"]


@dataclass(frozen=True)
class Departure:
    """1 便の発車。時・分・最終行先駅で同一性を判定する。"""

    hour: int
    minute: int
    destination: str


# ヘッダ(ttBoxHeader)を除く時刻ブロック
_HOUR_BLOCK = re.compile(r'<dl class="ttBox">(.*?)</dl>', re.S)
_HOUR = re.compile(r'<dt class="ttToggle">\s*<span>\s*(\d{1,2})\s*</span>', re.S)
_TRAIN = re.compile(r'<li[^>]*linindexlink[^>]*>(.*?)</li>', re.S)
_LEGEND_SPAN = re.compile(r'<span class="legend">(.*?)</span>', re.S)
_MINUTE = re.compile(r"<a[^>]*>\s*(\d{1,2})\s*</a>", re.S)

_LEGEND_DD = re.compile(r"<dd>(.*?)</dd>", re.S)
_LEGEND_MARKER = re.compile(r"<span[^>]*>(.*?)</span>", re.S)

_TAGS = re.compile(r"<[^>]+>")
# 行先定義ではなく注記であることを示す文字・語
_ANNOTATION = re.compile(r"[でにを、。]|接続|のりかえ|便利|最終|します|乗換")
# 素の行先駅名（漢字・カタカナ・長音・全角括弧）
_STATION = re.compile(r"[一-龥ァ-ヶー（）()]+")


def _text(fragment: str) -> str:
    """タグ・&nbsp;・空白をすべて除去した連結テキストを返す（記号照合用）。"""
    s = _TAGS.sub("", fragment)
    s = s.replace("&nbsp;", "").replace("　", "")
    return re.sub(r"\s+", "", s)


def _normalize_marker(marker_text: str) -> str:
    """凡例/セルの記号表記を正規化する。「無印」→"", 末尾「印」を除去。"""
    s = _text(marker_text)
    if s in ("無印", "無", ""):
        return ""
    return s[:-1] if s.endswith("印") else s


def _clean_destination(value_text: str) -> str | None:
    """凡例値が「素の駅名」なら駅名を返す。注記なら None。"""
    v = _text(value_text)
    if _ANNOTATION.search(v):
        return None
    v = v.removesuffix("電車").removesuffix("ゆき")
    return v if v and _STATION.fullmatch(v) else None


def parse_legend(html: str) -> dict[str, str]:
    """凡例から {記号: 素の行先駅} を返す。無印は空文字キー。注記は含めない。"""
    i = html.find('<div class="legendArea">')
    if i == -1:
        return {}
    area = html[i:]
    legend: dict[str, str] = {}
    for dd in _LEGEND_DD.finditer(area):
        body = dd.group(1)
        m = _LEGEND_MARKER.search(body)
        if not m:
            continue
        # 記号部分を除いた値（"="の後ろ）から行先を判定
        value = body[m.end():].lstrip().lstrip("=")
        dest = _clean_destination(value)
        if dest is None:
            continue
        legend[_normalize_marker(m.group(1))] = dest
    return legend


def _ttarea_pc(html: str) -> str:
    """PC 用時刻表領域を切り出す（`ttList` の入れ子 ``</ul>`` を避ける）。"""
    start = html.find('<ul class="ttArea pc">')
    if start == -1:
        return ""
    end = html.find('<ul class="ttArea sp"', start)
    if end == -1:
        end = len(html)
    return html[start:end]


def parse_diagram(html: str, default_destination: str = "") -> list[Departure]:
    """ダイヤ詳細 HTML から全ホームの発車便を抽出する。

    ``default_destination`` は凡例に「無印」が無いとき（七隈線など）の既定行先。
    凡例に無印があればそちらを優先する。
    """
    legend = parse_legend(html)
    default = legend.get("", default_destination)
    area = _ttarea_pc(html)
    if not area:
        return []
    departures: list[Departure] = []
    for block in _HOUR_BLOCK.finditer(area):
        body = block.group(1)
        hm = _HOUR.search(body)
        if not hm:  # ヘッダ行など
            continue
        hour = int(hm.group(1))
        for train in _TRAIN.finditer(body):
            seg = train.group(1)
            minute_m = _MINUTE.search(seg)
            if not minute_m:
                continue
            sp = _LEGEND_SPAN.search(seg)
            marker = _normalize_marker(sp.group(1)) if sp else ""
            destination = legend.get(marker, default)
            departures.append(
                Departure(
                    hour=hour, minute=int(minute_m.group(1)), destination=destination
                )
            )
    return departures
