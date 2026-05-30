"""ジョルダン運賃パーサ parse_fare の単体テスト。

結果ページの普通料金（`普通料金 &nbsp;210&nbsp; 円`）を、&nbsp;・空白・タグ・桁区切りを
吸収して整数（円）で取り出すことを確認する。記録済みサンプル HTML でも検証する。
"""

from pathlib import Path

from fukuoka_gtfs.verify.jorudan_fare import parse_fare

FIXTURE = Path(__file__).parent / "fixtures" / "jorudan" / "fare_sample.html"


def test_parse_nbsp_separated():
    html = "<dd>普通料金 &nbsp;210&nbsp; 円</dd>"
    assert parse_fare(html) == 210


def test_parse_with_tags_between():
    html = "普通料金<span class='x'> 340 </span>円"
    assert parse_fare(html) == 340


def test_parse_with_thousands_comma():
    # 地下鉄では発生しないが桁区切りを安全に吸収する
    html = "普通料金 1,230 円"
    assert parse_fare(html) == 1230


def test_returns_none_when_absent():
    assert parse_fare("<html><body>運行情報</body></html>") is None


def test_picks_first_ordinary_fare_only():
    # 普通料金の直後の数値を取る（小児料金など後続は無視）
    html = "普通料金 &nbsp;260&nbsp; 円 小児料金 130 円"
    assert parse_fare(html) == 260


def test_parses_recorded_sample():
    if not FIXTURE.exists():
        # フィクスチャ未取得の環境では明示的に失敗させず情報を残す
        import pytest

        pytest.skip(f"サンプル HTML 未取得: {FIXTURE}")
    fare = parse_fare(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(fare, int) and fare > 0
