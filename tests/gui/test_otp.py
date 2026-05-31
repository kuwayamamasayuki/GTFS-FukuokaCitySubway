"""経路検索ページ opentripplanner/index.html の GUI テスト（Issue #25）。

同梱サンプル経路（data/sample-itinerary.json）を静的表示できること、
サンプルが無い場合は生成手順を案内することを Playwright で検証する。
"""
from __future__ import annotations

import pytest

_pw = pytest.importorskip("playwright.sync_api")
expect = _pw.expect

pytestmark = pytest.mark.gui


def test_renders_bundled_sample(page, demo_site):
    page.goto(f"{demo_site}/opentripplanner/index.html", wait_until="domcontentloaded")
    # 同梱サンプル（橋本→福岡空港）の要約が描画される
    expect(page.locator(".meta .od")).to_have_text("橋本 → 福岡空港", timeout=15000)
    expect(page.locator(".meta .big")).to_contain_text("分")
    # leg カードが 2 本以上（七隈線→空港線）出る
    legs = page.locator(".legs .leg")
    assert legs.count() >= 2
    modes = page.locator(".legs .leg .mode").all_inner_texts()
    assert any("七隈線" in m for m in modes)
    assert any("空港線" in m for m in modes)


def test_shows_guidance_when_sample_missing(page, demo_site):
    # サンプル取得を失敗させると、生成手順の案内に切り替わる
    page.route("**/sample-itinerary.json", lambda route: route.abort())
    page.goto(f"{demo_site}/opentripplanner/index.html", wait_until="domcontentloaded")
    expect(page.locator("#sample")).to_contain_text("make demo-otp-sample", timeout=15000)


def test_links_to_otp_debug_ui(page, demo_site):
    page.goto(f"{demo_site}/opentripplanner/index.html", wait_until="domcontentloaded")
    # 起動中の OTP デバッグ UI（localhost:8080）への導線がある
    assert page.locator("a[href*='localhost:8080']").count() >= 1
    # ナビの「経路検索」が現在ページとしてアクティブ
    expect(page.locator("nav a.active")).to_have_text("経路検索")
