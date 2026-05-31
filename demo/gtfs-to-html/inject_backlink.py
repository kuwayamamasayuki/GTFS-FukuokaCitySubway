#!/usr/bin/env python3
"""GTFS-to-HTML が生成した html/ の各ページ先頭に「デモTOPへ戻る」リンクを注入する。

GTFS-to-HTML には戻りリンクのオプションが無いため、生成後にこのスクリプトを実行する。
冪等（既に注入済みのページはスキップ）なので、再生成のたびに流せば戻り導線を復元できる。

  cd demo/gtfs-to-html
  npx gtfs-to-html       # html/ を再生成（戻りリンクは消える）
  python3 inject_backlink.py
"""
from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent          # demo/gtfs-to-html
HTML = HERE / "html"
DEMO = HERE.parent                               # demo/
MARKER = 'class="demo-backlink"'
STYLE = ("display:block;padding:10px 16px;background:#0f1722;color:#f7931d;"
         "font-family:'Zen Kaku Gothic New',sans-serif;font-size:14px;"
         "text-decoration:none;border-bottom:1px solid #2c3a4d;")


def main() -> None:
    count = 0
    for path in HTML.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        if MARKER in text or "<body>" not in text:
            continue
        rel = os.path.relpath(DEMO / "index.html", path.parent).replace(os.sep, "/")
        link = (f'<a class="demo-backlink" href="{rel}" style="{STYLE}">'
                "← 福岡市地下鉄 GTFS デモへ戻る</a>")
        path.write_text(text.replace("<body>", "<body>" + link, 1), encoding="utf-8")
        count += 1
        print(f"  + {path.relative_to(HERE)} → {rel}")
    print(f"戻りリンクを {count} ページに注入しました。")


if __name__ == "__main__":
    main()
