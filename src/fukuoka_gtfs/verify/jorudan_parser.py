"""ジョルダンの福岡市地下鉄ダイヤ詳細ページ（diagramdtl）の HTML パーサ。

ページ構造（PC 用 `ttArea pc`）::

    <ul class="ttArea pc">
      <li class="pc"><dl class="ttBox ttBoxHeader">…ヘッダ…</dl></li>   ← 読み飛ばす
      <li class="pc"><dl class="ttBox">
        <dt class="ttToggle"><span>5</span></dt>                       ← 時
        <dd><ul class="ttList"><li class="…linindexlink">
           <span class="legend">…記号…</span><a>30</a>…              ← 行先記号 / 分
        </li>…</ul></dd>
        <dd>…ホーム列が複数…</dd>
      </dl></li>
    </ul>

行先記号と最終行先の対応はページ末尾の「凡例」から解析する::

    <div class="legendArea"><dl>
      <dd><span>無印</span>=福岡空港ゆき</dd>
      <dd><span>貝</span>=貝塚ゆき</dd>
      <dd><span>●印</span>=中洲川端で貝塚ゆきにのりかえが便利な福岡空港ゆき電車</dd>
    </dl></div>

ホーム列は方面単位に統合する。`destination` は凡例で解決した「最終行先駅」。
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

_LEGEND_AREA = re.compile(r'<div class="legendArea">(.*?)</div>', re.S)
_LEGEND_DD = re.compile(r"<dd>(.*?)</dd>", re.S)
_LEGEND_MARKER = re.compile(r"<span>(.*?)</span>", re.S)
# 行先駅名（漢字・カタカナ・全角括弧等。助詞のひらがなは含めない）
_DEST = re.compile(r"([一-龥ァ-ヶー（）()]+)ゆき")

_TAGS = re.compile(r"<[^>]+>")


def _text(fragment: str) -> str:
    """タグと &nbsp; を除去し、空白を畳んだテキストを返す。"""
    s = _TAGS.sub("", fragment)
    s = s.replace("&nbsp;", " ").replace("　", " ")
    return s.strip()


def _normalize_marker(legend_marker: str) -> str:
    """凡例の記号表記を時刻表 li の記号表記に正規化する。

    凡例「無印」→ "", 「●印」→ "●", 「▲印」→ "▲", 「貝」→ "貝"。
    """
    s = _text(legend_marker)
    if s in ("無印", "無", ""):
        return ""
    return s[:-1] if s.endswith("印") else s


def parse_legend(html: str) -> dict[str, str]:
    """凡例を解析し {記号: 最終行先駅} を返す。無印は空文字キー。"""
    area = _LEGEND_AREA.search(html)
    if not area:
        return {}
    legend: dict[str, str] = {}
    for dd in _LEGEND_DD.finditer(area.group(1)):
        body = dd.group(1)
        m = _LEGEND_MARKER.search(body)
        if not m:
            continue
        marker = _normalize_marker(m.group(1))
        dests = _DEST.findall(_text(body))
        if not dests:
            continue
        legend[marker] = dests[-1]  # 最終行先（乗換案内文でも末尾が行先）
    return legend


def _ttarea_pc(html: str) -> str:
    """PC 用時刻表領域を切り出す。`ttList` の入れ子 ``</ul>`` を避けるため、
    開始タグからモバイル(sp)領域または文書末までを文字列スライスで取る。"""
    start = html.find('<ul class="ttArea pc">')
    if start == -1:
        return ""
    end = html.find('<ul class="ttArea sp"', start)
    if end == -1:
        end = len(html)
    return html[start:end]


def parse_diagram(html: str) -> list[Departure]:
    """ダイヤ詳細 HTML から全ホームの発車便を抽出する。"""
    legend = parse_legend(html)
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
            minute = int(minute_m.group(1))
            marker = ""
            sp = _LEGEND_SPAN.search(seg)
            if sp:
                marker = _text(sp.group(1))
            destination = legend.get(marker, legend.get("", ""))
            departures.append(
                Departure(hour=hour, minute=minute, destination=destination)
            )
    return departures
