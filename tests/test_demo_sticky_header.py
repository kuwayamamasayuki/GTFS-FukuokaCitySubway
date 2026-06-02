"""Issue #38: GTFS-to-HTML 時刻表に駅名ヘッダ行固定の CSS を注入する後処理を検証する。

外部 Node ツール(gtfs-to-html)が生成した html/ に対し、`inject_backlink.py` と同方式で
生成後に CSS を注入するスクリプト inject_sticky_header.py の挙動（マーカー存在・冪等性・
対象選別）と、同梱の生成 HTML 成果物のリグレッションを守る。
実際の見た目は demo/gtfs-to-html/README.md の手順（Node.js 20+）と画面目視で確認する。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "gtfs-to-html"
SCRIPT = DEMO / "inject_sticky_header.py"
MARKER = 'id="issue38-sticky-header"'

# 最小限の時刻表ページ（gtfs-to-html の vertical orientation を模した骨格）
TIMETABLE_HTML = (
    '<!DOCTYPE html><html><head><title>t</title>'
    '<link rel="stylesheet" href="../css/timetable_styles.css"></head>'
    '<body><div class="timetable-page"><div class="timetable">'
    '<div class="table-container"><table class="table-vertical">'
    '<thead><tr><th class="stop-header">姪浜</th></tr></thead>'
    '<tbody><tr class="trip-row"><td class="stop-time">5:39am</td></tr></tbody>'
    '</table></div></div></div></body></html>'
)
# テーブルを含まない概要ページ（注入対象外）
OVERVIEW_HTML = (
    '<!DOCTYPE html><html><head><title>index</title></head>'
    '<body><h1>概要</h1><ul><li><a href="t.html">空港線</a></li></ul></body></html>'
)


def _load_module():
    spec = importlib.util.spec_from_file_location("inject_sticky_header", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_injects_sticky_css_into_timetable_page():
    """時刻表ページにマーカーと position: sticky が注入される。"""
    mod = _load_module()
    out = mod.inject_into_html(TIMETABLE_HTML)
    assert out is not None, "時刻表ページには注入されること"
    assert MARKER in out, "冪等判定用マーカーが入ること"
    assert "position: sticky" in out, "ヘッダ固定の CSS が入ること"
    # </head> 直前（リンク済み CSS より後）に入り、cascade で後勝ちすること
    assert out.index(MARKER) < out.index("</head>")
    assert out.index('href="../css/timetable_styles.css"') < out.index(MARKER)


def test_injection_is_idempotent():
    """2 回注入してもマーカーは 1 つだけ（再生成・再実行に耐える）。"""
    mod = _load_module()
    once = mod.inject_into_html(TIMETABLE_HTML)
    twice = mod.inject_into_html(once)
    assert twice is None, "注入済みページは None を返してスキップすること"
    assert once.count(MARKER) == 1


def test_skips_pages_without_timetable_table():
    """テーブルを含まない概要ページには注入しない。"""
    mod = _load_module()
    assert mod.inject_into_html(OVERVIEW_HTML) is None


def test_skips_pages_without_head():
    """<head> の無い断片には注入しない。"""
    mod = _load_module()
    fragment = '<div class="table-container"><table></table></div>'
    assert mod.inject_into_html(fragment) is None


def test_committed_html_artifacts_have_sticky_marker():
    """同梱の生成 HTML 時刻表ページにマーカーが含まれる（リグレッション）。"""
    pages = [
        DEMO / "html" / "timetables" / "空港線・箱崎線.html",
        DEMO / "html" / "timetables" / "七隈線.html",
    ]
    for page in pages:
        assert page.exists(), f"{page.name} が同梱されていること"
        assert MARKER in page.read_text(encoding="utf-8"), \
            f"{page.name} に駅名ヘッダ固定が注入済みであること"
