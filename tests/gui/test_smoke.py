"""3 画面が読み込まれ主要 DOM が描画されることを確認するスモークテスト（Issue #24）。"""
from __future__ import annotations

import pytest

_pw = pytest.importorskip("playwright.sync_api")
expect = _pw.expect

pytestmark = pytest.mark.gui


def test_index_renders_stat_cards(page, demo_site):
    page.goto(f"{demo_site}/index.html", wait_until="domcontentloaded")
    # 統計インフォグラフィックのカードがデータから生成される
    expect(page.locator("#statgrid .lcard").first).to_be_visible(timeout=15000)


def test_board_renders_departures_on_select(page, demo_site):
    page.goto(f"{demo_site}/board.html", wait_until="domcontentloaded")
    # フィードに依らず、駅を選べば発車カードが出る
    page.click("#rail button:has-text('中洲川端')")
    expect(page.locator(".dirgrid").first).to_be_visible(timeout=15000)
    expect(page.locator(".dirgrid .dcard").first).to_be_visible()


def test_map_loads_data_and_renders_canvas(page, demo_site):
    page.goto(f"{demo_site}/map.html?t=0600&pause=1", wait_until="domcontentloaded")
    # data 読み込み失敗時は #clk が "DATA ERROR" になる
    clk = page.locator("#clk")
    expect(clk).not_to_have_text("DATA ERROR", timeout=15000)
    # deck.gl が WebGL キャンバスを生成する（SwiftShader 起動）
    expect(page.locator("#deck canvas").first).to_be_visible(timeout=20000)
