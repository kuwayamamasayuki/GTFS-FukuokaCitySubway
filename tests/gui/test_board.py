"""発車標 board.html の操作（駅選択・区分・言語・基準時刻）を検証する（Issue #24）。"""
from __future__ import annotations

import pytest

_pw = pytest.importorskip("playwright.sync_api")
expect = _pw.expect

pytestmark = pytest.mark.gui


def _open_board(page, demo_site):
    page.goto(f"{demo_site}/board.html", wait_until="domcontentloaded")
    # 左レールが生成されるまで待つ
    expect(page.locator("#rail button").first).to_be_visible(timeout=15000)


def test_select_station_shows_direction_cards(page, demo_site):
    _open_board(page, demo_site)
    page.click("#rail button:has-text('中洲川端')")
    # 乗換駅なので複数路線の方向カードが出る
    expect(page.locator(".dirgrid .dcard").first).to_be_visible(timeout=15000)
    assert page.locator(".dirgrid .dcard").count() >= 2
    expect(page.locator("#b-name")).to_have_text("中洲川端")


def test_service_tab_switch_rerenders(page, demo_site):
    _open_board(page, demo_site)
    page.click("#rail button:has-text('博多')")
    expect(page.locator(".dirgrid").first).to_be_visible(timeout=15000)
    # 土曜タブへ切替 → on クラスが付き、再描画される
    page.click("#svtabs button:has-text('土曜')")
    sat = page.locator("#svtabs button:has-text('土曜')")
    expect(sat).to_have_class("on")
    expect(page.locator(".dirgrid").first).to_be_visible()


def test_language_toggle_switches_station_name(page, demo_site):
    _open_board(page, demo_site)
    page.click("#rail button:has-text('中洲川端')")
    expect(page.locator("#b-name")).to_have_text("中洲川端")
    # English に切替 → 駅名が英語表記になる
    page.click("#lang button[data-l='en']")
    expect(page.locator("#b-name")).to_have_text("Nakasukawabata", timeout=10000)


def test_now_slider_filters_departures(page, demo_site):
    _open_board(page, demo_site)
    page.click("#rail button:has-text('中洲川端')")
    expect(page.locator(".dirgrid").first).to_be_visible(timeout=15000)
    # 基準時刻を 25:00 へ（フィクスチャの全便より後）→ 以降の発車なし表示
    page.eval_on_selector(
        "#now",
        "el => { el.value = el.max; el.dispatchEvent(new Event('input')); }",
    )
    expect(page.locator("#b-now")).to_have_text("25:00")
    expect(page.locator(".dcard .empty2").first).to_be_visible(timeout=10000)
