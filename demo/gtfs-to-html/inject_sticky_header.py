#!/usr/bin/env python3
"""GTFS-to-HTML が生成した時刻表ページに「駅名ヘッダ行を固定」する CSS を注入する。

vertical orientation の時刻表は駅＝列／便＝行で、便が数百行に及ぶため縦スクロールすると
駅名ヘッダ(thead)が画面外へ流れ、どの列がどの駅か分からなくなる。gtfs-to-html には
ヘッダ固定のオプションが無いため、生成後にこのスクリプトを実行して CSS を注入する。
冪等（既に注入済みのページはスキップ）なので、再生成のたびに流せば固定を復元できる。

  cd demo/gtfs-to-html
  npx gtfs-to-html          # html/ を再生成（注入分は消える）
  python3 inject_backlink.py
  python3 inject_sticky_header.py

単に thead を sticky にしても、既存 CSS の .table-container { overflow-x: scroll } が
スクロール包含ブロックになり、コンテナ自体は縦スクロールしないため固定が効かない。
そこで .table-container を高さ上限付きスクロールボックスにし、その中で thead を sticky
にする。リンク済み CSS より後（</head> 直前）に注入するため、同詳細度で後勝ちする。
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent          # demo/gtfs-to-html
HTML = HERE / "html"
MARKER = 'id="issue38-sticky-header"'

STYLE = (
    f'<style {MARKER}>'
    "/* Issue #38: 駅名ヘッダ行を固定（便が数百行でも駅名が常に見える） */"
    ".timetable-page .timetable .table-container{max-height:80vh;overflow:auto;}"
    ".timetable-page .timetable .table-container thead th{"
    "position: sticky;top:0;z-index:2;}"
    "</style>"
)


def inject_into_html(text: str) -> str | None:
    """時刻表ページなら CSS を注入した文字列を返す。対象外/注入済みなら None。

    対象: <head> を持ち、かつ時刻表テーブル(table-container)を含むページ。
    概要ページ(index.html)等はテーブルを含まないため自然に除外される。
    """
    if MARKER in text:
        return None  # 既に注入済み（冪等）
    if "</head>" not in text or "table-container" not in text:
        return None  # head が無い断片 / 時刻表でないページは対象外
    return text.replace("</head>", STYLE + "</head>", 1)


def main() -> None:
    count = 0
    for path in HTML.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        injected = inject_into_html(text)
        if injected is None:
            continue
        path.write_text(injected, encoding="utf-8")
        count += 1
        print(f"  + {path.relative_to(HERE)}")
    print(f"駅名ヘッダ固定を {count} ページに注入しました。")


if __name__ == "__main__":
    main()
