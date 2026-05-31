"""概要ハブ index.html のリンク・導線を検証する（Issue #24）。"""
from __future__ import annotations

import pytest

_pw = pytest.importorskip("playwright.sync_api")
expect = _pw.expect

pytestmark = pytest.mark.gui


def _open_index(page, demo_site):
    page.goto(f"{demo_site}/index.html", wait_until="domcontentloaded")
    expect(page.locator("#statgrid .lcard").first).to_be_visible(timeout=15000)


def test_download_links_present(page, demo_site):
    _open_index(page, demo_site)
    for href in ["data/feed.zip", "data/network.geojson",
                 "kepler-animation/data/trips.geojson"]:
        assert page.locator(f"a[href='{href}'][download]").count() == 1


def test_nav_links_present(page, demo_site):
    _open_index(page, demo_site)
    for href in ["map.html", "board.html", "gtfs-to-html/html/index.html"]:
        assert page.locator(f"a[href='{href}']").count() >= 1


def test_external_tool_links_open_in_new_tab(page, demo_site):
    _open_index(page, demo_site)
    for needle in ["gtfs-validator", "transit.land", "kepler.gl"]:
        link = page.locator(f"a[href*='{needle}'][target='_blank']")
        assert link.count() >= 1


def test_nav_to_board(page, demo_site):
    _open_index(page, demo_site)
    page.click("nav a[href='board.html']")
    page.wait_for_url("**/board.html", timeout=10000)
    assert page.url.endswith("board.html")
