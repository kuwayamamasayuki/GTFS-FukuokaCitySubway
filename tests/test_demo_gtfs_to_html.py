"""Issue #17 / #35: GTFS-to-HTML デモ例の構成を検証する。

外部 Node ツール(gtfs-to-html)を用いる例のため、ここでは「設定と同梱成果物が
壊れていないこと」をリグレッションとして守る。実際の HTML 生成は
demo/gtfs-to-html/README.md の手順（Node.js 20+）で行う。

Issue #35: timetables.txt を追加し、空港線と箱崎線を 1 つの時刻表へ統合
（同一 timetable_id に両 route の行）かつ show_trip_continuation=1 で直通便
(block_id) を継続表示する。七隈線は単独の時刻表のまま。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "gtfs-to-html"
CONFIG = DEMO / "config.json"
PACKAGE = DEMO / "package.json"
TIMETABLES = DEMO / "timetables.txt"
TIMETABLE_PAGES = DEMO / "timetable_pages.txt"
TIMETABLE_STOP_ORDER = DEMO / "timetable_stop_order.txt"
ROUTES = ["空港線", "箱崎線", "七隈線"]
CONTINUATION_ROUTES = {"空港線", "箱崎線"}  # 直通で 1 時刻表に統合する 2 路線


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _read_csv(path: Path) -> tuple[list[str], list[dict]]:
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    return list(reader.fieldnames or []), list(reader)


def test_config_points_to_feed_and_source_zip_exists():
    """config.json は組み立て済みフィード feed/ を指し、元の dist zip が実在する。"""
    cfg = _load_json(CONFIG)
    agencies = cfg.get("agencies")
    assert isinstance(agencies, list) and agencies, "agencies は非空リストであること"
    assert all(ag.get("path") == "feed" for ag in agencies), "入力は組み立て済み feed/"
    # feed/ は prepare_feed.py が dist zip から毎回生成する（.gitignore 済み）。
    assert (DEMO / "prepare_feed.py").exists(), "feed/ を生成する prepare_feed.py が必要"
    assert (ROOT / "dist" / "FukuokaCitySubway.zip").exists(), "元データの dist zip が実在すること"
    assert cfg.get("outputPath") == "html"
    assert cfg.get("outputFormat") == "html"


def test_package_declares_gtfs_to_html_and_build_scripts():
    """package.json が gtfs-to-html 依存・prebuild(feed 組み立て)・build・Node 要件を宣言する。"""
    pkg = _load_json(PACKAGE)
    assert "gtfs-to-html" in pkg.get("devDependencies", {})
    scripts = pkg.get("scripts", {})
    assert "prepare_feed.py" in scripts.get("prebuild", ""), "build 前に feed/ を組み立てること"
    build = scripts.get("build", "")
    assert "gtfs-to-html" in build and "config.json" in build
    assert pkg.get("engines", {}).get("node"), "Node のバージョン要件を明記すること"


def test_timetables_combine_kuko_and_hakozaki_with_continuation():
    """空港線と箱崎線が同一 timetable_id に統合され、show_trip_continuation=1 を持つ。"""
    header, rows = _read_csv(TIMETABLES)
    assert "show_trip_continuation" in header
    # timetable_id ごとに含まれる route の集合
    by_id: dict[str, set[str]] = {}
    cont_by_id: dict[str, set[str]] = {}
    for r in rows:
        by_id.setdefault(r["timetable_id"], set()).add(r["route_id"])
        cont_by_id.setdefault(r["timetable_id"], set()).add(r["show_trip_continuation"])
    combined = [tid for tid, rs in by_id.items() if rs == CONTINUATION_ROUTES]
    assert combined, "空港線・箱崎線を 1 つに統合した timetable_id が存在すること"
    for tid in combined:
        assert cont_by_id[tid] == {"1"}, f"{tid} は show_trip_continuation=1 であること"


def test_nanakuma_is_standalone_without_continuation():
    """七隈線は単独の時刻表で、show_trip_continuation=0。"""
    _, rows = _read_csv(TIMETABLES)
    nanakuma = [r for r in rows if r["route_id"] == "七隈線"]
    assert nanakuma, "七隈線の時刻表定義が存在すること"
    for r in nanakuma:
        assert r["show_trip_continuation"] == "0"
        # 七隈線の timetable_id は他 route と相乗りしない
        same = [x for x in rows if x["timetable_id"] == r["timetable_id"]]
        assert all(x["route_id"] == "七隈線" for x in same)


def test_timetables_reference_valid_routes_and_pages():
    """timetables.txt の route_id は dist の routes に存在し、page は timetable_pages.txt に定義される。"""
    _, tt_rows = _read_csv(TIMETABLES)
    _, dist_routes = _read_csv(ROOT / "dist" / "routes.txt")
    valid_routes = {r["route_id"] for r in dist_routes}
    _, page_rows = _read_csv(TIMETABLE_PAGES)
    valid_pages = {p["timetable_page_id"] for p in page_rows}
    for r in tt_rows:
        assert r["route_id"] in valid_routes, f"未知の route_id: {r['route_id']}"
        assert r["timetable_page_id"] in valid_pages, f"未知の page: {r['timetable_page_id']}"


def test_stop_order_lists_full_kuko_then_hakozaki_branch():
    """統合時刻表の駅順は『空港線を全区間通し→箱崎線の分岐』になっている。

    下り(方面0)では 姪浜(1)…中洲川端(9)…福岡空港(13) の後に
    呉服町(14)…貝塚(19) が並ぶ（Issue #35 のレビュー指摘の並び）。
    """
    _, rows = _read_csv(TIMETABLE_STOP_ORDER)
    _, tt_rows = _read_csv(TIMETABLES)
    combined_ids = {
        r["timetable_id"] for r in tt_rows
        if r["route_id"] in CONTINUATION_ROUTES
    }
    by_tt: dict[str, list[str]] = {}
    for r in rows:
        assert r["timetable_id"] in combined_ids, \
            f"stop_order は統合時刻表のみ対象: {r['timetable_id']}"
        by_tt.setdefault(r["timetable_id"], []).append(r["stop_id"])
    # 下り(_0)の代表で順序を検証
    down = next(t for t in by_tt if t.endswith("_0"))
    order = by_tt[down]
    assert order == [str(i) for i in range(1, 20)], "下りは空港線1..13→箱崎線14..19の順"
    # 福岡空港(13)が貝塚(19)より前、中洲川端(9)が福岡空港(13)より前
    assert order.index("13") < order.index("19")
    assert order.index("9") < order.index("13")


def test_westbound_stop_order_branch_first_with_junction_twice():
    """西向き(上り _1)の駅順は『貝塚→中洲川端（箱崎線）→福岡空港→…→姪浜（空港線）』。

    接続駅 中洲川端(9) は箱崎線区間の末尾と空港線区間内の双方に現れる（=2回表示）。
    箱崎線の便は前者の列、空港線の便は後者の列を使う。
    """
    _, rows = _read_csv(TIMETABLE_STOP_ORDER)
    by_tt: dict[str, list[str]] = {}
    for r in rows:
        by_tt.setdefault(r["timetable_id"], []).append(r["stop_id"])
    up = next(t for t in by_tt if t.endswith("_1"))
    order = by_tt[up]
    expected = ["19", "18", "17", "16", "15", "14", "9",
                "13", "12", "11", "10", "9", "8", "7", "6", "5", "4", "3", "2", "1"]
    assert order == expected, "上りは 貝塚→中洲川端 → 福岡空港→中洲川端→姪浜（中洲川端=9を2回）"
    assert order.count("9") == 2, "接続駅 中洲川端(9) は 2 回現れること"
    # 貝塚(19) は福岡空港(13)より前（箱崎線区間が先）
    assert order.index("19") < order.index("13")


def test_committed_html_renders_junction_twice_for_westbound():
    """同梱HTMLの上り(kh_wd_1)thead で 中洲川端 が 2 列描画されている（リグレッション）。"""
    import re
    html = (DEMO / "html" / "timetables" / "空港線・箱崎線.html").read_text(encoding="utf-8")
    m = html.find('data-timetable-id="kh_wd_1"')
    assert m != -1, "上り平日(kh_wd_1)の時刻表が存在すること"
    head = html[html.find("<thead>", m):html.find("</thead>", m)]
    names = re.findall(r'class="stop-name"[^>]*>([^<]+)<', head)
    assert names.count("中洲川端") == 2, "上りでは中洲川端が2列描画されること"
    assert names[0] == "貝塚" and names[-1] == "姪浜", "貝塚で始まり姪浜で終わること"


def test_committed_html_artifacts_exist():
    """同梱の生成 HTML（概要 + 統合/単独ページ）が存在する。"""
    assert (DEMO / "html" / "index.html").exists(), "概要ページ index.html が同梱されていること"
    assert (DEMO / "html" / "timetables" / "空港線・箱崎線.html").exists(), \
        "空港線・箱崎線を統合した時刻表ページが同梱されていること"
    assert (DEMO / "html" / "timetables" / "七隈線.html").exists(), \
        "七隈線の時刻表ページが同梱されていること"
