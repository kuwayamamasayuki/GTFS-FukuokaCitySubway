"""生成 GTFS からの発車時刻抽出 gtfs_timetable のテスト。

- 駅×方面×サービスで発車便を抽出する。
- 深夜 24/25 時は ``% 24`` で 0/1 時に正規化する。
- 各 trip の最終停車（終着駅での到着）は「発車」ではないため除外する。
"""

from fukuoka_gtfs.verify.gtfs_timetable import departures, load_feed
from fukuoka_gtfs.verify.jorudan_parser import Departure

STOPS = """stop_id,stop_name,location_type,parent_station
1,姪浜,1,
1_1,姪浜,0,1
1_2,姪浜,0,1
13,福岡空港,1,
13_1,福岡空港,0,13
13_2,福岡空港,0,13
"""

ROUTES = """route_id,route_short_name,route_type
空港線,空港線,1
"""

TRIPS = """route_id,service_id,trip_id,trip_headsign,direction_id
空港線,空港箱崎_平日,T1,福岡空港,0
空港線,空港箱崎_平日,T2,福岡空港,0
空港線,空港箱崎_平日,T5,福岡空港,0
空港線,空港箱崎_平日,TTERM,姪浜,1
空港線,空港箱崎_平日,TTHRU,筑前前原,1
空港線,空港箱崎_土曜,T4,福岡空港,0
"""

# T1/T2/T5 は姪浜(seq1)発→福岡空港(seq2)着。姪浜発が発車として数えられる。
# T5 は深夜 24:18（翌 0:18）。
# TTERM は福岡空港(seq1)発→姪浜(seq2)着、行先=姪浜 → 姪浜が真の終着 → 発車に数えない。
# TTHRU は福岡空港(seq1)発→姪浜(seq2)着だが行先=筑前前原（JR直通でフィード境界の先へ継続）
#   → 姪浜は最終停車だが真の終着ではないので発車として数える。
# T4 は土曜サービス。
STOP_TIMES = """trip_id,arrival_time,departure_time,stop_id,stop_sequence
T1,05:30:00,05:30:00,1_2,1
T1,06:00:00,06:00:00,13_2,2
T2,05:45:00,05:45:00,1_2,1
T2,06:10:00,06:10:00,13_2,2
T5,24:18:00,24:18:00,1_2,1
T5,24:48:00,24:48:00,13_2,2
TTERM,07:00:00,07:00:00,13_1,1
TTERM,07:30:00,07:30:00,1_1,2
TTHRU,08:00:00,08:00:00,13_1,1
TTHRU,08:40:00,08:40:00,1_1,2
T4,07:00:00,07:00:00,1_2,1
T4,07:25:00,07:25:00,13_2,2
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
    # 姪浜発(dir0 平日): T1 5:30, T2 5:45, T5 0:18(深夜正規化)
    assert Departure(5, 30, "福岡空港") in deps
    assert Departure(5, 45, "福岡空港") in deps
    assert Departure(0, 18, "福岡空港") in deps
    assert len(deps) == 3


def test_true_terminus_excluded_but_through_train_kept(tmp_path):
    # 姪浜(dir1): TTERM(行先=姪浜)は真の終着→除外。
    # TTHRU(行先=筑前前原, 姪浜は最終停車だが直通)→発車として残す。
    feed = load_feed(_write_feed(tmp_path))
    deps = departures(
        feed,
        stop_name="姪浜",
        route_id="空港線",
        direction_id=1,
        service_id="空港箱崎_平日",
    )
    assert deps == [Departure(8, 40, "筑前前原")]


def test_excludes_other_service(tmp_path):
    feed = load_feed(_write_feed(tmp_path))
    deps = departures(
        feed,
        stop_name="姪浜",
        route_id="空港線",
        direction_id=0,
        service_id="空港箱崎_平日",
    )
    assert Departure(7, 0, "福岡空港") not in deps  # 土曜 T4


def test_after_midnight_25h_normalized(tmp_path):
    # 25:05 → 1:05。途中停車として追加（終着ではない）。
    st = STOP_TIMES + "T1,25:05:00,25:05:00,1_2,0\n"
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
