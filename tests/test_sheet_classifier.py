from fukuoka_gtfs.excel.sheet_classifier import classify

SERVICE = {"平日": "平日", "土曜": "土曜", "休日": "休日"}
DIRS = {"空港貝塚方面": 0, "姪浜方面": 1, "博多方面": 0, "橋本方面": 1}


def test_classify_weekday_meinohama():
    k = classify("(平日　姪浜方面)", SERVICE, DIRS)
    assert k is not None
    assert (k.service_id, k.direction_id) == ("平日", 1)


def test_classify_holiday_hakata():
    k = classify("(休日　博多方面)", SERVICE, DIRS)
    assert (k.service_id, k.direction_id) == ("休日", 0)


def test_classify_non_data_sheet():
    assert classify("注意事項", SERVICE, DIRS) is None
