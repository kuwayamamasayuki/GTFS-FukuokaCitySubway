"""3 画面のスクリーンショットを撮影し、生成物のサニティを確認する（Issue #24）。

厳密なピクセル差分はフォント描画差で不安定になりやすいため採用しない。
ここでは「PNG が生成され、PNG シグネチャを持ち、明らかに非空（最小バイト数以上）」
であることのみを確認する。撮影した PNG は CI ではアーティファクトとして保存できる。
"""
from __future__ import annotations

import pytest

_pw = pytest.importorskip("playwright.sync_api")
expect = _pw.expect

pytestmark = pytest.mark.gui

_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_MIN_BYTES = 1000

# (パス, 読み込み完了を待つセレクタ)
_SHOTS = [
    ("index.html", "#statgrid .lcard"),
    ("map.html?t=0600&pause=1", "#deck canvas"),
]


@pytest.mark.parametrize("path,selector", _SHOTS)
def test_screenshot_is_generated(page, demo_site, tmp_path, path, selector):
    page.goto(f"{demo_site}/{path}", wait_until="domcontentloaded")
    expect(page.locator(selector).first).to_be_visible(timeout=20000)
    out = tmp_path / "shot.png"
    page.screenshot(path=str(out))
    data = out.read_bytes()
    assert data[:8] == _PNG_SIG
    assert len(data) > _MIN_BYTES


def test_board_screenshot_is_generated(page, demo_site, tmp_path):
    page.goto(f"{demo_site}/board.html", wait_until="domcontentloaded")
    page.click("#rail button:has-text('中洲川端')")
    expect(page.locator(".dirgrid .dcard").first).to_be_visible(timeout=20000)
    out = tmp_path / "board.png"
    page.screenshot(path=str(out))
    data = out.read_bytes()
    assert data[:8] == _PNG_SIG
    assert len(data) > _MIN_BYTES
