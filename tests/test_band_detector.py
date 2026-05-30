from fukuoka_gtfs.excel.band_detector import Vocab, detect_bands
from fukuoka_gtfs.excel.workbook import Sheet

VOCAB = Vocab()


def _sheet():
    grid = [
        ["始発", None, "貝塚", "福岡空港"],   # r0 バンド1
        ["行先", None, "姪浜", "姪浜"],
        ["乗り入れ", None, None, None],
        ["貝塚", "発", 0.25, None],
        ["中洲川端", "発", 0.26, 0.27],
        ["天神", "発", 0.27, 0.28],
        ["姪浜", "着", 0.28, 0.29],
        [None, None, None, None],            # 空行
        ["始発", None, "貝塚", None],          # r8 バンド2
        ["行先", None, "姪浜", None],
        ["乗り入れ", None, None, None],
        ["貝塚", "発", 0.6, None],
        ["姪浜", "着", 0.62, None],
    ]
    return Sheet(name="(平日　姪浜方面)", grid=grid)


def test_two_bands_detected():
    bands = detect_bands(_sheet(), VOCAB)
    assert len(bands) == 2


def test_band_structure():
    b1 = detect_bands(_sheet(), VOCAB)[0]
    assert b1.origin_row == 0
    assert b1.dest_row == 1
    assert b1.through_row == 2
    assert [s.name for s in b1.station_rows] == ["貝塚", "中洲川端", "天神", "姪浜"]
    assert b1.data_cols == [2, 3]


def test_band2_only_one_data_col():
    b2 = detect_bands(_sheet(), VOCAB)[1]
    assert b2.data_cols == [2]
    assert [s.name for s in b2.station_rows] == ["貝塚", "姪浜"]
