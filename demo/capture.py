#!/usr/bin/env python3
"""デモ 3 画面のスクリーンショットを Playwright(Chromium) で撮影する。

  python demo/capture.py
出力: demo/screenshots/{index,board,map}.png
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

DEMO = Path(__file__).resolve().parent
OUT = DEMO / "screenshots"
PORT = 8809

SHOTS = [
    # (パス, 出力名, 読み込み完了を待つセレクタ, 追加待機ms)
    ("index.html", "index.png", "#statgrid .lcard", 2200),
    ("board.html", "board.png", ".rows .row", 1800),
    ("map.html?t=0800&pause=1", "map.png", "#deck canvas", 3500),
]


def main() -> int:
    OUT.mkdir(exist_ok=True)
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT)],
                           cwd=DEMO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=[
                "--use-gl=angle", "--use-angle=swiftshader",
                "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
            ])
            page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
            for path, name, sel, extra in SHOTS:
                page.goto(f"http://localhost:{PORT}/{path}", wait_until="domcontentloaded", timeout=30000)
                try:
                    page.wait_for_selector(sel, timeout=15000)
                except Exception as e:  # noqa: BLE001
                    print(f"  警告: {name} のセレクタ {sel} 待機に失敗: {e}")
                page.wait_for_timeout(extra)
                page.screenshot(path=str(OUT / name))
                print(f"  撮影: {name}")
            browser.close()
    finally:
        srv.terminate()
    print("完了:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
