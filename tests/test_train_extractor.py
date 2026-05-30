from fukuoka_gtfs.excel.band_detector import Vocab, detect_bands
from fukuoka_gtfs.excel.sheet_classifier import SheetKind
from fukuoka_gtfs.excel.train_extractor import extract_trips
from fukuoka_gtfs.excel.workbook import Sheet
from fukuoka_gtfs.station_mapper import StationMapper

STOPS = [
    {"stop_id": "1", "stop_code": "K01", "stop_name": "姪浜", "location_type": "1"},
    {"stop_id": "8", "stop_code": "K08", "stop_name": "天神", "location_type": "1"},
    {"stop_id": "9", "stop_code": "K09/H01", "stop_name": "中洲川端", "location_type": "1"},
    {"stop_id": "13", "stop_code": "K13", "stop_name": "福岡空港", "location_type": "1"},
    {"stop_id": "19", "stop_code": "H07", "stop_name": "貝塚", "location_type": "1"},
]
OVERRIDES = {"9": {"空港線": {0: "9_3", 1: "9_4"}, "箱崎線": {0: "9_1", 1: "9_2"}}}


def _sheet():
    grid = [
        ["始発", None, "貝塚", "福岡空港"],
        ["行先", None, "姪浜", "姪浜"],
        ["乗り入れ", None, None, None],
        ["貝塚", "発", 0.25, None],
        ["中洲川端", "発", 0.26, 0.27],
        ["天神", "発", 0.27, 0.28],
        ["姪浜", "着", 0.28, 0.29],
    ]
    return Sheet(name="(平日　姪浜方面)", grid=grid)


def _extract():
    sheet = _sheet()
    band = detect_bands(sheet, Vocab())[0]
    mapper = StationMapper.from_stops(STOPS, OVERRIDES)
    kind = SheetKind(service_id="平日", direction_id=1, direction_label="姪浜方面")
    return extract_trips(sheet, band, kind, mapper, block_prefix="t_")


def test_total_trips():
    # col2(貝塚→姪浜 直通)=2 trip + col3(中洲川端→姪浜)=1 trip
    assert len(_extract()) == 3


def test_through_train_split_and_block():
    trips = _extract()
    through = [t for t in trips if t.block_id]
    assert len(through) == 2
    assert {t.route_id for t in through} == {"空港線", "箱崎線"}
    assert through[0].block_id == through[1].block_id  # 同一便を連結
    hak = next(t for t in through if t.route_id == "箱崎線")
    kuko = next(t for t in through if t.route_id == "空港線")
    # 箱崎線: 貝塚(19_2) → 中洲川端(9_2)   dir1
    assert [v.stop_id for v in hak.visits] == ["19_2", "9_2"]
    # 空港線: 中洲川端(9_4) → 天神(8_2) → 姪浜(1_2)
    assert [v.stop_id for v in kuko.visits] == ["9_4", "8_2", "1_2"]


def test_single_line_trip_has_no_block():
    trips = _extract()
    single = [t for t in trips if not t.block_id]
    assert len(single) == 1
    assert single[0].route_id == "空港線"
    assert single[0].headsign == "姪浜"
    assert [v.stop_id for v in single[0].visits] == ["9_4", "8_2", "1_2"]
