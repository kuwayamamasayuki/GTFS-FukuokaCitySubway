"""Issue #18: TransitFlow（transitland-processing-animation）デモ例の検証。

変換器 gtfs_to_transitflow.py は本リポジトリの GTFS を TransitFlow の Processing
スケッチが読める入力（output.csv / vehicle_counts/*.csv）へ変換する。実際の動画
レンダリングは Processing(GUI) が必要なため、ここでは変換ロジックと同梱成果物の
構造をリグレッションとして守る。
"""
from __future__ import annotations

import csv
import datetime as dt
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "transitland-animation"
MODULE_PATH = DEMO / "gtfs_to_transitflow.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("gtfs_to_transitflow", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tf = _load_module()


def _write_mini_gtfs(base: Path) -> Path:
    """空港線の 1 便（3 駅・深夜便含む）だけの最小 GTFS を作る。"""
    gtfs = base / "gtfs"
    gtfs.mkdir()
    files = {
        "stops.txt": (
            "stop_id,stop_name,stop_lat,stop_lon\n"
            "A,駅A,33.5900,130.4000\n"
            "B,駅B,33.6000,130.4100\n"
            "C,駅C,33.6100,130.4200\n"
        ),
        "routes.txt": (
            "route_id,route_type,route_color\n"
            "L1,1,f7931d\n"
        ),
        "trips.txt": (
            "route_id,service_id,trip_id\n"
            "L1,WD,T1\n"
            "L1,SAT,T2\n"
        ),
        "stop_times.txt": (
            "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
            # 平日便: 通常時刻、stop_sequence は逆順で与えて整列を検証
            "T1,05:30:00,05:30:00,A,1\n"
            "T1,05:32:00,05:32:00,B,2\n"
            "T1,05:34:00,05:34:00,C,3\n"
            # 土曜便: 深夜便（24 時超）
            "T2,24:10:00,24:10:00,A,1\n"
            "T2,24:12:00,24:12:00,B,2\n"
        ),
        "calendar.txt": (
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
            "WD,1,1,1,1,1,0,0,20260401,20991231\n"
            "SAT,0,0,0,0,0,1,0,20260401,20991231\n"
        ),
        "calendar_dates.txt": (
            "service_id,date,exception_type\n"
            "WD,20260403,2\n"  # 2026-04-03(金) は運休
        ),
    }
    for name, body in files.items():
        (gtfs / name).write_text(body, encoding="utf-8")
    return gtfs


# --- 純粋関数 ---

def test_time_to_seconds_handles_over_24h():
    assert tf.time_to_seconds("05:30:00") == 5 * 3600 + 30 * 60
    assert tf.time_to_seconds("24:10:00") == 24 * 3600 + 10 * 60


def test_route_type_mapping_subway_is_metro():
    assert tf.ROUTE_TYPE_TO_VEHICLE["1"] == "metro"
    assert tf.ROUTE_TYPE_TO_VEHICLE["3"] == "bus"


def test_calc_bearing_due_north_and_east():
    # 真北はおおよそ 0 度、真東はおおよそ 90 度
    assert tf.calc_bearing(33.0, 130.0, 34.0, 130.0) == 0.0
    east = tf.calc_bearing(33.0, 130.0, 33.0, 131.0)
    assert 89.0 < east < 91.0


def test_active_services_weekday_saturday_and_exception():
    cal = [
        {"service_id": "WD", "monday": "1", "tuesday": "1", "wednesday": "1",
         "thursday": "1", "friday": "1", "saturday": "0", "sunday": "0",
         "start_date": "20260401", "end_date": "20991231"},
        {"service_id": "SAT", "monday": "0", "tuesday": "0", "wednesday": "0",
         "thursday": "0", "friday": "0", "saturday": "1", "sunday": "0",
         "start_date": "20260401", "end_date": "20991231"},
    ]
    cd = [{"service_id": "WD", "date": "20260403", "exception_type": "2"}]
    # 2026-04-01 は水曜 → WD
    assert tf.active_services(cal, cd, dt.date(2026, 4, 1)) == {"WD"}
    # 2026-04-04 は土曜 → SAT
    assert tf.active_services(cal, cd, dt.date(2026, 4, 4)) == {"SAT"}
    # 2026-04-03 は金曜だが calendar_dates で運休
    assert tf.active_services(cal, cd, dt.date(2026, 4, 3)) == set()


# --- セグメント生成 ---

def test_build_segments_weekday(tmp_path):
    gtfs = _write_mini_gtfs(tmp_path)
    segs = tf.build_segments(gtfs, dt.date(2026, 4, 1))  # 水曜=WD のみ
    # 平日便 T1 の駅間は A-B, B-C の 2 セグメント。土曜便は対象外。
    assert len(segs) == 2
    assert all(s["route_type"] == "metro" for s in segs)
    first = segs[0]
    assert first["start_time"] == dt.datetime(2026, 4, 1, 5, 30, 0)
    assert first["end_time"] == dt.datetime(2026, 4, 1, 5, 32, 0)
    assert first["duration"] == 120
    # start_time 昇順
    assert segs[0]["start_time"] <= segs[1]["start_time"]


def test_build_segments_overnight_rolls_to_next_day(tmp_path):
    gtfs = _write_mini_gtfs(tmp_path)
    segs = tf.build_segments(gtfs, dt.date(2026, 4, 4))  # 土曜=SAT（深夜便）
    assert len(segs) == 1
    seg = segs[0]
    # 24:10 → 翌日 00:10
    assert seg["start_time"] == dt.datetime(2026, 4, 5, 0, 10, 0)
    assert seg["end_time"] == dt.datetime(2026, 4, 5, 0, 12, 0)


def test_default_service_date_picks_first_running_day(tmp_path):
    gtfs = _write_mini_gtfs(tmp_path)
    cal = tf.read_csv(gtfs / "calendar.txt")
    # 2026-04-01 は水曜で WD が走る → 開始日がそのまま採用される
    assert tf.default_service_date(cal) == dt.date(2026, 4, 1)


# --- 出力ファイル ---

def test_vehicle_counts_shape_and_metro_count(tmp_path):
    gtfs = _write_mini_gtfs(tmp_path)
    segs = tf.build_segments(gtfs, dt.date(2026, 4, 1))
    counts = tf.vehicle_counts(segs, frames=10)
    assert set(counts.keys()) == set(tf.COUNT_MODES)
    for mode in tf.COUNT_MODES:
        assert len(counts[mode]) == 10  # frames 行
    # bus は本フィードに存在しないので常に 0
    assert all(n == 0 for _, _, n in counts["buses"])
    # metro と vehicles(合計) はどこかで 1 以上になる
    assert max(n for _, _, n in counts["metros"]) >= 1
    assert max(n for _, _, n in counts["vehicles"]) >= 1


def test_write_outputs_creates_expected_files(tmp_path):
    gtfs = _write_mini_gtfs(tmp_path)
    segs = tf.build_segments(gtfs, dt.date(2026, 4, 1))
    out = tmp_path / "sketch_out"
    tf.write_outputs(out, segs, frames=10)

    output_csv = out / "data" / "output.csv"
    assert output_csv.exists()
    with output_csv.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows, "output.csv は非空であること"
    assert set(rows[0].keys()) == {
        "start_time", "start_lat", "start_lon", "end_time", "end_lat",
        "end_lon", "duration", "route_type", "bearing",
    }
    # 時刻は "YYYY-MM-DD HH:MM:SS" 形式
    dt.datetime.strptime(rows[0]["start_time"], "%Y-%m-%d %H:%M:%S")

    for mode in tf.COUNT_MODES:
        f = out / "data" / "vehicle_counts" / f"{mode}_10.csv"
        assert f.exists(), f"{f} が無い"
        with f.open(encoding="utf-8") as fh:
            header = next(csv.reader(fh))
        assert header == ["frame", "time", "count"]


def test_write_sketch_substitutes_template(tmp_path):
    gtfs = _write_mini_gtfs(tmp_path)
    segs = tf.build_segments(gtfs, dt.date(2026, 4, 1))
    template = tmp_path / "template.pde"
    template.write_text(
        'date="${DATE}"; frames=${TOTAL_FRAMES}; rec=${RECORDING};'
        ' c=(${AVG_LAT},${AVG_LON}); name="${DIRECTORY_NAME}";',
        encoding="utf-8",
    )
    out = tmp_path / "sketch_out"
    tf.write_sketch(out, template, "fukuoka", dt.date(2026, 4, 1), 3600, segs, recording=False)
    text = (out / "sketch" / "sketch.pde").read_text(encoding="utf-8")
    assert 'date="2026-04-01"' in text
    assert "frames=3600" in text
    assert "rec=false" in text
    assert 'name="fukuoka"' in text


# --- 同梱成果物・ドキュメントのリグレッション ---

def test_committed_artifacts_and_readme_exist():
    assert (DEMO / "README.md").exists(), "README が同梱されていること"
    output_csv = DEMO / "data" / "output.csv"
    assert output_csv.exists(), "生成済み output.csv が同梱されていること"
    counts = list((DEMO / "data" / "vehicle_counts").glob("metros_*.csv"))
    assert counts, "生成済み vehicle_counts（metros）が同梱されていること"
    # output.csv はすべて地下鉄(metro)であること
    with output_csv.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows, "同梱 output.csv が非空であること"
    assert all(r["route_type"] == "metro" for r in rows)
