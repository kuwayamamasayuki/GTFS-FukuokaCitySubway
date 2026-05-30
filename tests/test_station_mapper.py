from fukuoka_gtfs.station_mapper import StationMapper, lines_from_code, normalize_name

STOPS = [
    {"stop_id": "1", "stop_code": "K01", "stop_name": "姪浜", "location_type": "1"},
    {"stop_id": "8", "stop_code": "K08", "stop_name": "天神", "location_type": "1"},
    {"stop_id": "9", "stop_code": "K09/H01", "stop_name": "中洲川端", "location_type": "1"},
    {"stop_id": "19", "stop_code": "H07", "stop_name": "貝塚", "location_type": "1"},
    {"stop_id": "20", "stop_code": "N01", "stop_name": "橋本", "location_type": "1"},
    {"stop_id": "11", "stop_code": "K11/N18", "stop_name": "博多", "location_type": "1"},
    # 子ホームは location_type=0 → 親としては登録されない
    {"stop_id": "1_1", "stop_code": "", "stop_name": "姪浜", "location_type": "0"},
]
OVERRIDES = {
    "9": {"空港線": {0: "9_3", 1: "9_4"}, "箱崎線": {0: "9_1", 1: "9_2"}},
    "11": {"空港線": {0: "11_1", 1: "11_2"}, "七隈線": {0: "11_3", 1: "11_4"}},
}


def test_normalize_name_strips_prefecture():
    assert normalize_name("橋本(福岡県)") == "橋本"
    assert normalize_name("梅林（福岡県）") == "梅林"
    assert normalize_name(" 中洲川端 ") == "中洲川端"


def test_lines_from_code():
    assert lines_from_code("K09/H01") == {"空港線", "箱崎線"}
    assert lines_from_code("N01") == {"七隈線"}


def _mapper():
    return StationMapper.from_stops(STOPS, OVERRIDES)


def test_parent_resolution_with_normalization():
    m = _mapper()
    assert m.parent_id("橋本(福岡県)") == "20"
    assert m.parent_id("中洲川端") == "9"


def test_platform_default_and_override():
    m = _mapper()
    assert m.platform("1", "空港線", 0) == "1_1"
    assert m.platform("1", "空港線", 1) == "1_2"
    assert m.platform("9", "空港線", 0) == "9_3"
    assert m.platform("9", "箱崎線", 1) == "9_2"
    assert m.platform("11", "七隈線", 0) == "11_3"


def test_split_single_line():
    m = _mapper()
    segs = m.split_segments(["1", "8", "9"])  # 全て空港線(9は共用)
    assert len(segs) == 1
    assert segs[0][0] == "空港線"


def test_split_through_train():
    m = _mapper()
    # 貝塚(箱崎) → 中洲川端(共用) → 天神(空港) → 姪浜(空港)
    segs = m.split_segments(["19", "9", "8", "1"])
    assert len(segs) == 2
    (l1, s1), (l2, s2) = segs
    assert l1 == "箱崎線" and l2 == "空港線"
    assert ["19", "9", "8", "1"][s1] == ["19", "9"]   # 共用駅を終点に含む
    assert ["19", "9", "8", "1"][s2] == ["9", "8", "1"]  # 共用駅を起点に含む
