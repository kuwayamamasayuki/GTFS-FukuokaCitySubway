"""Issue #17: GTFS-to-HTML デモ例の構成を検証する。

外部 Node ツール(gtfs-to-html)を用いる例のため、ここでは「設定と同梱成果物が
壊れていないこと」をリグレッションとして守る。実際の HTML 生成は
demo/gtfs-to-html/README.md の手順（Node.js 20+）で行う。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "gtfs-to-html"
CONFIG = DEMO / "config.json"
PACKAGE = DEMO / "package.json"
ROUTES = ["空港線", "箱崎線", "七隈線"]


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def test_config_is_valid_and_points_to_existing_feed():
    """config.json が妥当で、入力フィードが config からの相対で実在する。"""
    cfg = _load_json(CONFIG)
    agencies = cfg.get("agencies")
    assert isinstance(agencies, list) and agencies, "agencies は非空リストであること"
    for ag in agencies:
        assert "path" in ag, "ローカルフィードを指す path を持つこと"
        feed = (CONFIG.parent / ag["path"]).resolve()
        assert feed.exists(), f"入力フィードが存在しない: {feed}"
    assert cfg.get("outputPath") == "html"
    assert cfg.get("outputFormat") == "html"


def test_package_declares_gtfs_to_html_and_build_script():
    """package.json が gtfs-to-html 依存・build スクリプト・Node 要件を宣言する。"""
    pkg = _load_json(PACKAGE)
    assert "gtfs-to-html" in pkg.get("devDependencies", {})
    build = pkg.get("scripts", {}).get("build", "")
    assert "gtfs-to-html" in build and "config.json" in build
    assert pkg.get("engines", {}).get("node"), "Node のバージョン要件を明記すること"


def test_committed_html_artifacts_exist():
    """同梱の生成 HTML（概要 + 路線別時刻表）が存在する。"""
    assert (DEMO / "html" / "index.html").exists(), "概要ページ index.html が同梱されていること"
    for r in ROUTES:
        # 各路線の時刻表ページが運行期間フォルダ配下に存在する（フォルダ名はフィード依存）
        pages = list(DEMO.glob(f"html/*/{r}.html"))
        assert pages, f"{r} の時刻表ページが見つからない"
