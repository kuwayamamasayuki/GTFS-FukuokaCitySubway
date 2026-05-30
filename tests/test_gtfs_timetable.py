"""生成 GTFS からの発車時刻抽出 gtfs_timetable のテスト。

小さな合成 GTFS を tmp に書き出して検証する（深夜 24/25 時の正規化を含む）。
"""

from fukuoka_gtfs.verify.gtfs_timetable import departures, load_feed
from fukuoka_gtfs.verify.jorudan_parser import Departure

STOPS = """stop_id,stop_name,location_type,parent_station
1,姪浜,1,
1_1,姪浜,0,1
1_2,姪浜,0,1
"""

ROUTES = """route_id,route_short_name,route_type
空港線,空港線,1
"""

TRIPS = """route_id,service_id,trip_id,trip_headsign,direction_id
空港線,空港箱崎_平日,T1,福岡空港,0
空港線,空港箱崎_平日,T2,貝塚,0
空港線,空港箱崎_平日,T3,姪浜,1
空港線,空港箱崎_平日,T5,福岡空港,0
空港線,空港箱崎_土曜,T4,福岡空港,0
"""

# T5 は深夜便（24:18 = 翌 0:18）
STOP_TIMES = """trip_id,arrival_time,departure_time,stop_id,stop_sequence
T1,05:30:00,05:30:00,1_2,1
T2,05:45:00,05:45:00,1_2,1
T3,06:00:00,06:00:00,1_1,1
T4,07:00:00,07:00:00,1_2,1
T5,24:18:00,24:18:00,1_2,1
"""

CALENDAR = """service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date
空港箱崎_平日,1,1,1,1,1,0,0,20260314,99991231
空港箱崎_土曜,0,0,0,0,0,1,0,20260314,99991231
"""


def _write_feed(d):
    (d / "stops.txt").write_text(STOPS, encoding="utf-8")
    (d / "routes.txt").write_text(ROUTES, encoding="utf-8")
    (d / "trips.txt").write_text(TRIPS, encoding="utf-8")
    (d / "stop_times.txt").write_text(STOP_TIMES, encoding="utf-8")
    (d / "calendar.txt").write_text(CALENDAR, encoding="utf-8")
    return d


def test_departures_for_station_direction_service(tmp_path):
    feed = load_feed(_write_feed(tmp_path))
    deps = departures(
        feed,
        stop_name="姪浜",
        route_id="空港線",
        direction_id=0,
        service_id="空港箱崎_平日",
    )
    # T1, T2, T5（T5 は深夜 24:18 → 0:18）。T3(dir1) と T4(土曜) は除外。
    assert Departure(5, 30, "福岡空港") in deps
    assert Departure(5, 45, "貝塚") in deps
    assert Departure(0, 18, "福岡空港") in deps
    assert len(deps) == 3


def test_excludes_other_direction_and_service(tmp_path):
    feed = load_feed(_write_feed(tmp_path))
    deps = departures(
        feed,
        stop_name="姪浜",
        route_id="空港線",
        direction_id=0,
        service_id="空港箱崎_平日",
    )
    assert Departure(6, 0, "姪浜") not in deps  # 反対方向 T3
    assert Departure(7, 0, "福岡空港") not in deps  # 土曜 T4


def test_after_midnight_25h_normalized(tmp_path):
    # 25:05 → 1:05 に正規化される
    st = STOP_TIMES + "T1,25:05:00,25:05:00,1_2,9\n"
    (tmp_path / "stops.txt").write_text(STOPS, encoding="utf-8")
    (tmp_path / "routes.txt").write_text(ROUTES, encoding="utf-8")
    (tmp_path / "trips.txt").write_text(TRIPS, encoding="utf-8")
    (tmp_path / "stop_times.txt").write_text(st, encoding="utf-8")
    (tmp_path / "calendar.txt").write_text(CALENDAR, encoding="utf-8")
    feed = load_feed(tmp_path)
    deps = departures(
        feed,
        stop_name="姪浜",
        route_id="空港線",
        direction_id=0,
        service_id="空港箱崎_平日",
    )
    assert Departure(1, 5, "福岡空港") in deps
