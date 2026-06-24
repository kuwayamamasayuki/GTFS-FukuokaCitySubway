"""GUI（Playwright）テスト用の共通フィクスチャ（Issue #24）。

- `demo_site`: フィクスチャ GTFS からデモデータを生成し、demo の HTML/CSS/vendor と
  ともに一時ディレクトリへ組み立て、ローカル HTTP サーバで配信して base URL を返す。
- Chromium（Playwright のブラウザ）が未導入の環境では、このディレクトリ配下の
  テストを自動 skip する（通常の `make test` を壊さないため）。
- WebGL（deck.gl の地図）を描画できるよう、Chromium を SwiftShader 付きで起動する。
"""
from __future__ import annotations

import shutil
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demo_gtfs_fixture import load_build_demo_data, write_fixture_gtfs  # noqa: E402

GUI_DIR = Path(__file__).resolve().parent
ROOT = GUI_DIR.parents[1]
DEMO = ROOT / "demo"

# demo/ をルートに配信したときダウンロードできる最小の空 ZIP（index の feed.zip 用）。
_EMPTY_ZIP = b"PK\x05\x06" + b"\x00" * 18


def _chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            return Path(p.chromium.executable_path).exists()
    except Exception:
        return False


CHROMIUM_OK = _chromium_available()


def pytest_collection_modifyitems(config, items):
    """tests/gui 配下に `gui` マーカーを付け、Chromium 未導入なら skip する。"""
    skip = pytest.mark.skip(
        reason="Chromium 未導入: `python -m playwright install chromium` を実行してください"
    )
    for item in items:
        if str(GUI_DIR) not in str(item.fspath):
            continue
        item.add_marker(pytest.mark.gui)
        if not CHROMIUM_OK:
            item.add_marker(skip)


def _serve(directory: Path):
    def handler(*args, **kwargs):
        return SimpleHTTPRequestHandler(*args, directory=str(directory), **kwargs)

    # ThreadingHTTPServer: 1 ページが vendor JS（deck.gl 等）を多数並行取得するため、
    # 単一スレッドだとリクエストが直列化し CI 負荷下で page.goto が 30s を超えうる。
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


@pytest.fixture(scope="session")
def demo_site(tmp_path_factory):
    """demo サイト一式を組み立てて配信し、base URL（末尾スラッシュ無し）を返す。"""
    site = tmp_path_factory.mktemp("demo_site")
    for name in ["index.html", "board.html", "map.html", "style.css"]:
        shutil.copy(DEMO / name, site / name)
    shutil.copytree(DEMO / "vendor", site / "vendor")

    gtfs = tmp_path_factory.mktemp("gtfs")
    write_fixture_gtfs(gtfs)
    data_dir = site / "data"
    load_build_demo_data().build(gtfs, data_dir, feed_zip=None)
    # index のダウンロードリンク（data/feed.zip）が 404 にならないよう空 ZIP を置く。
    (data_dir / "feed.zip").write_bytes(_EMPTY_ZIP)

    # OpenTripPlanner オフライン表示ページ（Issue #25）と同梱サンプル経路。
    otp_src = DEMO / "opentripplanner"
    otp_dst = site / "opentripplanner"
    (otp_dst / "data").mkdir(parents=True)
    shutil.copy(otp_src / "index.html", otp_dst / "index.html")
    shutil.copy(otp_src / "data" / "sample-itinerary.json",
                otp_dst / "data" / "sample-itinerary.json")

    httpd = _serve(site)
    port = httpd.server_address[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    """deck.gl の WebGL 描画のため SwiftShader を有効化する（capture.py と同じ）。"""
    return {
        **browser_type_launch_args,
        "args": [
            "--use-gl=angle",
            "--use-angle=swiftshader",
            "--enable-unsafe-swiftshader",
            "--ignore-gpu-blocklist",
        ],
    }
