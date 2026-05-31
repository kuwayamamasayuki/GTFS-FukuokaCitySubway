"""Issue #22: 発車標(board.html)の方向別表示を支えるデータ生成の検証。

board.html は方向（路線×direction_id）ごとにカードを分けて表示するため、
build_demo_data.py は departures.json を「方向グループの配列」として出力する。
実際の描画はブラウザ(GUI)で行うので、ここでは方向ラベル算出・グルーピング
ロジックと、最小 GTFS から生成した departures.json の構造を守る。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "demo" / "build_demo_data.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_demo_data", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bd = _load_module()
LINE_ORDER = bd.LINE_ORDER


# --- direction_label（代表方面ラベル＝最頻 headsign） ---

def test_direction_label_single():
    assert bd.direction_label(["福岡空港"]) == "福岡空港"


def test_direction_label_most_frequent_wins():
    # 福岡空港 が最頻。途中行き(博多)が混じっても代表は福岡空港。
    assert bd.direction_label(["福岡空港", "博多", "福岡空港"]) == "福岡空港"


def test_direction_label_tie_breaks_by_string_order_deterministically():
    # 同数のときは headsign の文字列順（コードポイント昇順）で決定的に選ぶ。
    # 姪浜(U+59EA) < 西新(U+897F) なので姪浜。
    assert bd.direction_label(["西新", "姪浜"]) == "姪浜"
    assert bd.direction_label(["姪浜", "西新"]) == "姪浜"  # 入力順に依存しない


# --- group_by_direction ---

def _entry(route, d, t, headsign, color="#f7931d"):
    return {"route": route, "dir": d, "t": t,
            "hhmm": f"{t // 3600:02d}:{t % 3600 // 60:02d}",
            "headsign": headsign, "color": color}


def test_group_by_direction_keys_order_and_trip_sort():
    entries = [
        _entry("空港線", 1, 600, "姪浜"),
        _entry("空港線", 0, 300, "福岡空港"),
        _entry("空港線", 0, 120, "福岡空港"),
        _entry("空港線", 0, 500, "博多"),
        _entry("箱崎線", 0, 200, "貝塚", color="#00aeef"),
    ]
    groups = bd.group_by_direction(entries, LINE_ORDER)

    # グループ順は LINE_ORDER → dir(0,1)
    assert [(g["route"], g["dir"]) for g in groups] == [
        ("空港線", 0), ("空港線", 1), ("箱崎線", 0)]

    g0 = groups[0]
    # 代表方面＝最頻 headsign（福岡空港 ×2 > 博多 ×1）
    assert g0["dest"] == "福岡空港"
    # 色はグループ内エントリから取る
    assert g0["color"] == "#f7931d"
    # trips は時刻昇順
    assert [t["t"] for t in g0["trips"]] == [120, 300, 500]
    # trips が持つキーは t / hhmm / headsign のみ（route/dir/color はグループ側）
    assert set(g0["trips"][0]) == {"t", "hhmm", "headsign"}

    assert groups[2]["color"] == "#00aeef"
    assert groups[2]["dest"] == "貝塚"


def test_group_by_direction_empty():
    assert bd.group_by_direction([], LINE_ORDER) == []


# --- 統合: 最小 GTFS から departures.json を生成 ---

def _write_mini_gtfs(gtfs: Path) -> None:
    """3 路線（各 1 便以上）と乗換駅 1 つを持つ最小 GTFS。

    P_K2 は空港線(K2)と箱崎線(H1)が乗り入れる乗換駅。空港線は両方向、
    箱崎線・七隈線は片方向の便を置く（main() は全路線に 1 便以上を要求）。
    """
    gtfs.mkdir(parents=True)
    files = {
        "stops.txt": (
            "stop_id,stop_code,stop_name,stop_lat,stop_lon,location_type,parent_station\n"
            # 親駅（location_type=1）
            "P_K1,K1,空港駅1,33.59,130.40,1,\n"
            "P_K2,K2/H1,乗換駅,33.60,130.41,1,\n"   # 空港線×箱崎線の乗換
            "P_H2,H2,箱崎駅2,33.61,130.42,1,\n"
            "P_N1,N1,七隈駅1,33.55,130.38,1,\n"
            "P_N2,N2,七隈駅2,33.56,130.39,1,\n"
            # 子停留所（location_type=0、parent_station で親に紐づく）
            "C_K1,,空港駅1,33.59,130.40,0,P_K1\n"
            "C_K2,,乗換駅,33.60,130.41,0,P_K2\n"
            "C_H2,,箱崎駅2,33.61,130.42,0,P_H2\n"
            "C_N1,,七隈駅1,33.55,130.38,0,P_N1\n"
            "C_N2,,七隈駅2,33.56,130.39,0,P_N2\n"
        ),
        "routes.txt": (
            "route_id,route_type,route_color\n"
            "空港線,1,f7931d\n"
            "箱崎線,1,00aeef\n"
            "七隈線,1,009157\n"
        ),
        "trips.txt": (
            "route_id,service_id,trip_id,trip_headsign,direction_id\n"
            "空港線,空港箱崎_平日,TK0,福岡空港,0\n"
            "空港線,空港箱崎_平日,TK1,姪浜,1\n"
            "箱崎線,空港箱崎_平日,TH0,貝塚,0\n"
            "七隈線,七隈_平日,TN0,博多,0\n"
        ),
        "stop_times.txt": (
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            # 空港線 dir0: K1 -> K2
            "TK0,06:00:00,06:00:00,C_K1,1\n"
            "TK0,06:05:00,06:05:00,C_K2,2\n"
            # 空港線 dir1: K2 -> K1
            "TK1,06:10:00,06:10:00,C_K2,1\n"
            "TK1,06:15:00,06:15:00,C_K1,2\n"
            # 箱崎線 dir0: 乗換駅 K2 -> H2
            "TH0,06:20:00,06:20:00,C_K2,1\n"
            "TH0,06:25:00,06:25:00,C_H2,2\n"
            # 七隈線 dir0: N1 -> N2
            "TN0,06:30:00,06:30:00,C_N1,1\n"
            "TN0,06:35:00,06:35:00,C_N2,2\n"
        ),
        "translations.txt": (
            "table_name,field_name,field_value,language,translation\n"
            "stops,stop_name,乗換駅,en,Transfer\n"
        ),
    }
    for name, body in files.items():
        (gtfs / name).write_text(body, encoding="utf-8")


def test_main_generates_grouped_departures(tmp_path, monkeypatch):
    gtfs = tmp_path / "gtfs"
    out = tmp_path / "data"
    _write_mini_gtfs(gtfs)
    monkeypatch.setattr(bd, "GTFS", gtfs)
    monkeypatch.setattr(bd, "OUT", out)

    bd.main()

    dep = json.loads((out / "departures.json").read_text(encoding="utf-8"))

    # 乗換駅 P_K2 は 空港線×2方向 + 箱崎線×1方向 = 3 グループ
    transfer = dep["P_K2"]["平日"]
    assert [(g["route"], g["dir"]) for g in transfer] == [
        ("空港線", 0), ("空港線", 1), ("箱崎線", 0)]
    # 各グループは方面ラベルと時刻昇順の trips を持つ
    g0 = transfer[0]
    assert g0["dest"] == "福岡空港"
    assert g0["color"] == "#f7931d"
    assert g0["trips"][0]["hhmm"] == "06:05"
    assert set(g0["trips"][0]) == {"t", "hhmm", "headsign"}

    # 単一路線駅は 1 路線×2方向（始発側 K1 は空港線のみ）
    k1 = dep["P_K1"]["平日"]
    assert [(g["route"], g["dir"]) for g in k1] == [("空港線", 0), ("空港線", 1)]

    # 当該サービスに運行が無い区分は空配列
    assert dep["P_K2"]["休日"] == []
