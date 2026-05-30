"""config/jorudan_verify.yaml を読むマッピングローダのテスト。"""

from pathlib import Path

from fukuoka_gtfs.verify.mapping import Mapping, load_mapping

CONFIG = Path(__file__).resolve().parents[1] / "config" / "jorudan_verify.yaml"


def _m() -> Mapping:
    return load_mapping(CONFIG)


def test_service_id_combines_group_and_daytype():
    m = _m()
    assert m.service_id("空港線", "平日") == "空港箱崎_平日"
    assert m.service_id("箱崎線", "土曜") == "空港箱崎_土曜"
    assert m.service_id("七隈線", "休日") == "七隈_休日"


def test_resolve_direction_for_each_terminal():
    m = _m()
    assert m.resolve_direction("福岡地下鉄空港線", "福岡空港") == ("空港線", 0)
    assert m.resolve_direction("福岡地下鉄空港線", "西唐津") == ("空港線", 1)
    assert m.resolve_direction("福岡地下鉄箱崎線", "貝塚（福岡）") == ("箱崎線", 0)
    assert m.resolve_direction("福岡地下鉄箱崎線", "中洲川端") == ("箱崎線", 1)
    assert m.resolve_direction("福岡地下鉄七隈線", "博多") == ("七隈線", 0)
    # 天神南 も博多方面(dir 0)
    assert m.resolve_direction("福岡地下鉄七隈線", "天神南") == ("七隈線", 0)
    assert m.resolve_direction("福岡地下鉄七隈線", "橋本（福岡）") == ("七隈線", 1)


def test_resolve_direction_unknown_returns_none():
    assert _m().resolve_direction("福岡地下鉄空港線", "存在しない駅") is None


def test_station_and_destination_normalization_passthrough():
    m = _m()
    assert m.normalize_station("姪浜") == "姪浜"
    assert m.normalize_destination("福岡空港") == "福岡空港"


def test_daytypes_and_sample_dates():
    m = _m()
    assert m.daytypes == ["平日", "土曜", "休日"]
    assert m.sample_dates["平日"] == "20260601"
