from fukuoka_gtfs.station_mapper import StationMapper, lines_from_code, normalize_name

STOPS = [
    {"stop_id": "1", "stop_code": "K01", "stop_name": "姪浜", "location_type": "1"},
    {"stop_id": "8", "stop_code": "K08", "stop_name": "天神", "location_type": "1"},
    {"stop_id": "9", "stop_code": "K09/H01", "stop_name": "中洲川端", "location_type": "1"},
    {"stop_id": "19", "stop_code": "H07", "stop_name": "貝塚", "location_type": "1"},
    {"stop_id": "20", "stop_code": "N01", "stop_name": "橋本", "location_type": "1"},
    {"stop_id": "11", "stop_code": "K11/N18", "stop_name": "博多", "location_type": "1"},
    # 七隈線博多(N18) は空港線博多とは別位置の独立駅マーカー(id 37)。博多 という名前を
    # 11 と共有する（Issue #53）。名前解決はジャンクションである 11 が勝つこと（後述）。
    {"stop_id": "37", "stop_code": "N18", "stop_name": "博多", "location_type": "1"},
    # 子ホームは location_type=0 → 親としては登録されない
    {"stop_id": "1_1", "stop_code": "", "stop_name": "姪浜", "location_type": "0"},
]
OVERRIDES = {
    "9": {"空港線": {0: "9_3", 1: "9_4"}, "箱崎線": {0: "9_1", 1: "9_2"}},
    # 博多の七隈線ホームは独立駅 37 配下の 37_3/37_4。名前解決(parent_id)は 11 のままだが
    # platform() は親 11 のキーで 37_3/37_4 を返す（Issue #53）。
    "11": {"空港線": {0: "11_1", 1: "11_2"}, "七隈線": {0: "37_3", 1: "37_4"}},
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
    # 七隈線博多は独立駅 37 配下のホーム（親キーは 11 のまま）— Issue #53
    assert m.platform("11", "七隈線", 0) == "37_3"
    assert m.platform("11", "七隈線", 1) == "37_4"
    # 空港線博多は従来どおり 11 配下
    assert m.platform("11", "空港線", 0) == "11_1"
    assert m.platform("11", "空港線", 1) == "11_2"


def test_duplicate_name_resolves_to_junction_parent():
    """同名(博多)の親が複数あるとき、名前解決は路線数の多い共用駅(11)を採用する。

    博多 = 空港線 id11(K11/N18, 2路線=ジャンクション) と 七隈線 id37(N18, 1路線) の 2 駅。
    parent_id("博多") は split_segments のジャンクション判定が成立する 11 でなければならない
    （37 が選ばれると空港線トリップが platform(37,空港線)→存在しないホームで壊れる）。Issue #53。
    """
    m = _mapper()
    assert m.parent_id("博多") == "11"
    # 11 は両路線を兼ねる共用駅（single_line=None）であり続ける
    assert m.lines_of("11") == {"空港線", "七隈線"}
    assert m.single_line("11") is None


def test_duplicate_name_resolution_is_order_independent():
    """stops.txt 上の行順に関わらず、ジャンクション(11)が名前解決先になる。"""
    reordered = list(reversed(STOPS))  # 37 が 11 より前に来る並び
    m = StationMapper.from_stops(reordered, OVERRIDES)
    assert m.parent_id("博多") == "11"


def test_split_single_line():
    m = _mapper()
    segs = m.split_segments(["1", "8", "9"])  # 全て空港線(9は共用)
    assert len(segs) == 1
    assert segs[0][0] == "空港線"


def test_split_nanakuma_ending_at_hakata_stays_single():
    """純七隈線トリップ(橋本→櫛田神社前→博多)は博多が共用駅11でも 1 セグメントに留まる。

    博多(11)を空港線専用にすると present={七隈線,空港線} となり博多停車がドロップされる。
    11 が K11/N18(共用)であり続けることがこの不変条件を支える（Issue #53 の非対称性の核心）。
    """
    m = _mapper()
    segs = m.split_segments(["20", "11"])  # 橋本(七隈線)→博多(共用) の最小列
    assert len(segs) == 1
    assert segs[0][0] == "七隈線"


def test_split_through_train():
    m = _mapper()
    # 貝塚(箱崎) → 中洲川端(共用) → 天神(空港) → 姪浜(空港)
    segs = m.split_segments(["19", "9", "8", "1"])
    assert len(segs) == 2
    (l1, s1), (l2, s2) = segs
    assert l1 == "箱崎線" and l2 == "空港線"
    assert ["19", "9", "8", "1"][s1] == ["19", "9"]   # 共用駅を終点に含む
    assert ["19", "9", "8", "1"][s2] == ["9", "8", "1"]  # 共用駅を起点に含む
