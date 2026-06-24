"""scripts/seed_reference.transform_shapes のユニットテスト（Issue #55）。

上流2019フィードの shapes は七隈線が天神南止まりのため、参照データ取り込み時に
天神南～博多の区間を注入する。その変換ロジックを検証する。
"""
import importlib.util
from pathlib import Path

# scripts/ はパッケージではないので spec から直接ロードする。
_SEED = Path(__file__).resolve().parent.parent / "scripts" / "seed_reference.py"
_spec = importlib.util.spec_from_file_location("seed_reference", _SEED)
seed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed)

# 上流2019フィードでは dir0 の shape_id は「天神南方面行き」（入力＝読み込みキー）。
# transform_shapes は博多区間を注入し、出力 shape_id を「博多方面行き」へ改称する（Issue #48）。
TM_SRC = "七隈線（天神南方面行き）"  # 入力（上流フィードの shape_id）
TM = "七隈線（博多方面行き）"        # 出力（改称後の shape_id）
HM = "七隈線（橋本方面行き）"

# 天神南方面行きで seq112(天神南) の後に続く博多側 8 点：(lat, lon, dist)。
EXT = [
    ("33.590296", "130.406567", 12500),
    ("33.591515", "130.409300", 12800),
    ("33.591804", "130.410062", 12850),
    ("33.591810", "130.410465", 12900),
    ("33.591625", "130.411039", 12950),
    ("33.591333", "130.411583", 13000),
    ("33.589836", "130.414235", 13250),
    ("33.589616", "130.418599", 13600),
]

# 天神南末尾(seq112, dist12000) と橋本先頭(seq0, dist0) を含む最小フィクスチャ。
# 関係ない空港線の shape も混ぜ、無変更であることを確かめる。
FIXTURE = (
    "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence,shape_dist_traveled\r\n"
    "空港線（西行き）,33.1,130.1,0,0\r\n"
    "空港線（西行き）,33.2,130.2,1,100\r\n"
    f"{TM_SRC},33.5883058,130.4017106,111,11950\r\n"
    f"{TM_SRC},33.5885707,130.4022468,112,12000\r\n"
    f"{HM},33.5885707,130.4022468,0,0\r\n"
    f"{HM},33.5883058,130.4017106,1,30\r\n"
)


def _by_shape(rows):
    out = {}
    for r in rows:
        out.setdefault(r["shape_id"], []).append(r)
    return out


def test_tenjinminami_appends_hakata_segment():
    _, rows = seed.transform_shapes(FIXTURE)
    tm = _by_shape(rows)[TM]
    # 元の 2 点 + 追加 8 点 = 10 点
    assert len(tm) == 2 + len(EXT)
    appended = tm[2:]
    for got, (lat, lon, dist) in zip(appended, EXT):
        assert got["shape_pt_lat"] == lat
        assert got["shape_pt_lon"] == lon
        assert got["shape_dist_traveled"] == str(dist)
    # seq は 112 の次から連番で 113..120
    assert [r["shape_pt_sequence"] for r in appended] == [str(s) for s in range(113, 121)]
    # 末尾は博多(N18) 座標・dist13600
    assert tm[-1]["shape_pt_lat"] == "33.589616"
    assert tm[-1]["shape_pt_lon"] == "130.418599"
    assert tm[-1]["shape_dist_traveled"] == "13600"


def test_hashimoto_prepends_reversed_segment_and_shifts():
    _, rows = seed.transform_shapes(FIXTURE)
    hm = _by_shape(rows)[HM]
    # 先頭 8 点 + 元の 2 点 = 10 点
    assert len(hm) == len(EXT) + 2
    head = hm[: len(EXT)]
    # 先頭は博多、逆順、dist は博多起点(=total - 天神南dist) で 0,350,600,650,700,750,800,1100
    expected_dist = [13600 - d for (_, _, d) in reversed(EXT)]
    assert expected_dist == [0, 350, 600, 650, 700, 750, 800, 1100]
    assert head[0]["shape_pt_lat"] == "33.589616"
    assert head[0]["shape_pt_lon"] == "130.418599"
    assert head[0]["shape_dist_traveled"] == "0"
    for got, (lat, lon, _), dist in zip(head, list(reversed(EXT)), expected_dist):
        assert got["shape_pt_lat"] == lat
        assert got["shape_pt_lon"] == lon
        assert got["shape_dist_traveled"] == str(dist)
    # 前置分は seq 0..7
    assert [r["shape_pt_sequence"] for r in head] == [str(s) for s in range(8)]
    # 元の先頭(天神南, 旧seq0/dist0) は seq8 / dist1600(=13600-12000) へずれる
    assert hm[len(EXT)]["shape_pt_sequence"] == "8"
    assert hm[len(EXT)]["shape_dist_traveled"] == "1600"
    # 次の元行(旧seq1/dist30) も +8 / +1600
    assert hm[len(EXT) + 1]["shape_pt_sequence"] == "9"
    assert hm[len(EXT) + 1]["shape_dist_traveled"] == "1630"


def test_sequence_and_distance_monotonic():
    """両方向とも seq 連番・dist 単調非減少で、区間が物理的に連続している。"""
    _, rows = seed.transform_shapes(FIXTURE)
    grouped = _by_shape(rows)
    for sid in (TM, HM):
        seqs = [int(r["shape_pt_sequence"]) for r in grouped[sid]]
        dists = [int(r["shape_dist_traveled"]) for r in grouped[sid]]
        assert seqs == list(range(len(seqs))) or seqs == list(range(seqs[0], seqs[0] + len(seqs)))
        assert all(b >= a for a, b in zip(dists, dists[1:]))


def test_unrelated_shape_untouched():
    _, rows = seed.transform_shapes(FIXTURE)
    kuko = _by_shape(rows)["空港線（西行き）"]
    assert [r["shape_pt_sequence"] for r in kuko] == ["0", "1"]
    assert [r["shape_dist_traveled"] for r in kuko] == ["0", "100"]


def test_idempotent():
    """二重適用しても一度適用と同じ（再シードで二重追加しない）。"""
    header, once = seed.transform_shapes(FIXTURE)
    # once を CSV 文字列へ戻して再投入
    import csv
    import io

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=header)
    w.writeheader()
    w.writerows(once)
    _, twice = seed.transform_shapes(buf.getvalue())
    assert len(twice) == len(once)
    assert [r["shape_pt_sequence"] for r in twice] == [r["shape_pt_sequence"] for r in once]
    assert [r["shape_dist_traveled"] for r in twice] == [r["shape_dist_traveled"] for r in once]
