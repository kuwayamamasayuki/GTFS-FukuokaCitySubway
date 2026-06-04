#!/usr/bin/env python3
"""reference_gtfs/ を生成（シード）するワンタイム・スクリプト。

出所: ユーザー本人の 2019 年版フィード
  https://github.com/kuwayamamasayuki/GTFS-FukuokaCitySubway （3 生成物/）

このスクリプトは「滅多に変化しない参照データ」だけを取り込み、現行仕様に合わせて
変換したうえで reference_gtfs/ に書き出す。trips/stop_times/calendar/feed_info は
Excel から毎回生成するため、ここでは扱わない。

主な変換:
  * stops.txt   : 2023 年の七隈線博多延伸を反映。
                  - 博多(id 11) を空港線・七隈線共用駅にし、子ホーム 11_3/11_4 を追加、
                    stop_code を "K11/N18" に更新。
                  - 櫛田神社前(N17, 新 id 36) を親+子ホーム 36_1/36_2 で追加。
  * translations: 旧スキーマ(trans_id,lang,translation) → 現行スキーマ
                  (table_name,field_name,language,field_value,translation) へ移行。
                  feed_lang(ja) と同一の自己翻訳は除外。新駅の訳語を追加。
  * routes.txt  : route_sort_order 列を補い、空港線→箱崎線→七隈線の順で表示させる。
  * agency_jp / routes_jp : GTFS-JP 拡張ファイルを新規作成（公開用）。
  * shapes/fare_attributes/fare_rules : ほぼそのまま取り込み。
  * transfers.txt : 取り込まない。七隈線の博多延伸で天神・天神南が連絡駅とみなされ
                    なくなったため、連絡駅情報のファイル自体を廃止した（Issue #40）。

新駅の座標出典: 日本語版ウィキペディア（櫛田神社前駅 / 博多駅）。
"""
from __future__ import annotations

import csv
import io
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# 2019 年版の生成物はタグ `legacy-2019` に保存されている（本リポジトリを本ツールへ
# 全面刷新した際、旧データを参照できるよう固定タグ化した）。
# "3 生成物" を完全に percent-encode（生成物 = %E7%94%9F%E6%88%90%E7%89%A9）
REPO_RAW = ("https://raw.githubusercontent.com/kuwayamamasayuki/GTFS-FukuokaCitySubway"
            "/legacy-2019/3%20%E7%94%9F%E6%88%90%E7%89%A9")
REF_DIR = Path(__file__).resolve().parent.parent / "reference_gtfs"

AGENCY_ID = "3000020401307_0"

# agency.txt に補う運賃案内 URL（福岡市地下鉄 公式運賃ページ）。
# 2019 年版フィードには無い列のため、取り込み時に注入する（COPY_FILES では扱わない）。
AGENCY_FARE_URL = "https://subway.city.fukuoka.lg.jp/fare/index.php"

# agency.txt に補うタッチ決済（Contactless EMV）対応フラグ。GTFS 標準のオプション
# フィールド cemv_support（Enum: 0 または空=情報なし / 1=対応 / 2=非対応）。
# 当該事業者の全サービスで対応する場合にのみ 1 を指定すべきとされる。福岡市地下鉄は
# 2024-04-01 から全 3 路線・全 36 駅でタッチ決済乗車に対応しているため "1"。
# 仕様: https://gtfs.org/documentation/schedule/reference/#agencytxt
# 参考: https://subway.city.fukuoka.lg.jp/topics/detail.php?id=1895
CEMV_SUPPORT = "1"

# そのまま取り込む参照ファイル（運賃 fare_* は scripts/verify_fares.py が公式運賃表 PDF から生成）
# transfers.txt は取り込まない（Issue #40: 連絡駅情報の廃止）。
COPY_FILES = ["shapes.txt"]

# routes.txt に補う route_sort_order（GTFS 標準のオプションフィールド）。
# 値が小さいほど経路一覧で先に表示される。福岡市地下鉄の路線記号 K/H/N（空港線/箱崎線/
# 七隈線）の順に合わせ、空港線=1 → 箱崎線=2 → 七隈線=3 とする。
# 仕様: https://gtfs.org/documentation/schedule/reference/#routestxt
ROUTE_SORT_ORDER = {"空港線": "1", "箱崎線": "2", "七隈線": "3"}

# 新駅・延伸の定義（座標は日本語版ウィキペディア由来）
KUSHIDA_ID = "36"
NEW_STATIONS = {
    # 櫛田神社前(N17)
    KUSHIDA_ID: dict(stop_code="N17", stop_name="櫛田神社前",
                     stop_lat="33.591333", stop_lon="130.411583", zone_id=KUSHIDA_ID,
                     stop_url="", yomi="くしだじんじゃまえ", en="Kushida Shrine"),
}

# stops.stop_name の英語訳の上書き（上流フィードの表記を公開フィード向けに補正）。
# 福岡空港: 上流は "Fukuokakuko(Airport)" だが正式英語名称は "Fukuoka Airport"。
# 櫛田神社前: 新駅定義の en と一致（再掲して意図を明示）。
EN_OVERRIDES = {
    "福岡空港": "Fukuoka Airport",
    "櫛田神社前": "Kushida Shrine",
}


def fetch(name: str, retries: int = 5) -> str:
    url = f"{REPO_RAW}/{urllib.parse.quote(name)}"
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310 (信頼できる固定URL)
                return r.read().decode("utf-8-sig")
        except Exception as e:  # noqa: BLE001 (ネットワークは一時失敗しうるので再試行)
            last = e
            print(f"  取得失敗({attempt}/{retries}) {name}: {e}", file=sys.stderr)
            time.sleep(2 * attempt)
    raise RuntimeError(f"取得に失敗: {name}") from last


def read_rows(text: str) -> tuple[list[str], list[dict]]:
    reader = csv.DictReader(io.StringIO(text))
    return list(reader.fieldnames or []), list(reader)


def write_rows(path: Path, header: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  書き出し: {path.name}  ({len(rows)} 行)")


def transform_stops(text: str) -> tuple[list[str], list[dict]]:
    header, rows = read_rows(text)
    by_id = {r["stop_id"]: r for r in rows}

    # --- 博多(id 11) を空港線・七隈線共用に ---
    hakata = by_id["11"]
    hakata["stop_code"] = "K11/N18"
    base = {k: hakata[k] for k in ("stop_name", "stop_lat", "stop_lon", "zone_id")}
    for plat in ("11_3", "11_4"):
        if plat not in by_id:
            rows.append(dict(stop_id=plat, stop_code="", **base, stop_url="",
                             location_type="0", parent_station="11", wheelchair_boarding="1"))

    # --- 櫛田神社前(N17) を新規追加 ---
    for sid, s in NEW_STATIONS.items():
        if sid in by_id:
            continue
        rows.append(dict(stop_id=sid, stop_code=s["stop_code"], stop_name=s["stop_name"],
                         stop_lat=s["stop_lat"], stop_lon=s["stop_lon"], zone_id=s["zone_id"],
                         stop_url=s["stop_url"], location_type="1", parent_station="",
                         wheelchair_boarding="1"))
        for plat in (f"{sid}_1", f"{sid}_2"):
            rows.append(dict(stop_id=plat, stop_code="", stop_name=s["stop_name"],
                             stop_lat=s["stop_lat"], stop_lon=s["stop_lon"], zone_id=s["zone_id"],
                             stop_url="", location_type="0", parent_station=sid,
                             wheelchair_boarding="1"))
    return header, rows


def transform_agency(text: str) -> tuple[list[str], list[dict]]:
    """agency.txt に agency_fare_url / cemv_support 列を補う（無ければ追加、空なら補完）。"""
    header, rows = read_rows(text)
    if "agency_fare_url" not in header:
        header = [*header, "agency_fare_url"]
    if "cemv_support" not in header:
        header = [*header, "cemv_support"]
    for r in rows:
        if not r.get("agency_fare_url"):
            r["agency_fare_url"] = AGENCY_FARE_URL
        if not r.get("cemv_support"):
            r["cemv_support"] = CEMV_SUPPORT
    return header, rows


def transform_translations(text: str, stops_rows: list[dict]) -> tuple[list[str], list[dict]]:
    """旧 translations を現行スキーマ(field_value 方式)へ移行する。"""
    _, old = read_rows(text)
    # name -> {lang: translation}
    table: dict[str, dict[str, str]] = {}
    for r in old:
        table.setdefault(r["trans_id"], {})[r["lang"]] = r["translation"]
    # 新駅の訳語を追記
    for s in NEW_STATIONS.values():
        table.setdefault(s["stop_name"], {}).update({"ja-Hrkt": s["yomi"], "en": s["en"]})

    stop_names = {r["stop_name"] for r in stops_rows}
    route_names = {"空港線", "箱崎線", "七隈線"}

    header = ["table_name", "field_name", "language", "field_value", "translation"]
    out: list[dict] = []
    for name, langs in table.items():
        if name in stop_names:
            tbl, fld = "stops", "stop_name"
        elif name in route_names:
            tbl, fld = "routes", "route_short_name"  # 路線名は route_short_name に入っている
        else:
            print(f"  注意: 翻訳の対象不明のためスキップ: {name!r}", file=sys.stderr)
            continue
        for lang, tr in langs.items():
            if lang == "ja":  # feed_lang と同一の自己翻訳は不要
                continue
            if lang == "en" and tbl == "stops" and name in EN_OVERRIDES:
                tr = EN_OVERRIDES[name]  # 上流の誤表記を正式英語名称へ補正
            out.append(dict(table_name=tbl, field_name=fld, language=lang,
                            field_value=name, translation=tr))
    return header, out


def transform_routes(text: str) -> tuple[list[str], list[dict]]:
    """routes.txt に route_sort_order 列を補う（無ければ追加、空なら補完）。

    空港線→箱崎線→七隈線 の順で表示されるよう ROUTE_SORT_ORDER を割り当てる。
    既に値がある行は上書きしない（冪等）。
    """
    header, rows = read_rows(text)
    if "route_sort_order" not in header:
        header = [*header, "route_sort_order"]
    for r in rows:
        if not r.get("route_sort_order"):
            order = ROUTE_SORT_ORDER.get(r["route_id"])
            if order is None:
                print(f"  注意: route_sort_order 未定義の route_id: {r['route_id']!r}",
                      file=sys.stderr)
                continue
            r["route_sort_order"] = order
    return header, rows


def write_agency_jp() -> None:
    header = ["agency_id", "agency_official_name", "agency_zip_number", "agency_address",
              "agency_president_pos", "agency_president_name"]
    rows = [dict(agency_id="3000020401307_0", agency_official_name="福岡市交通局",
                 agency_zip_number="8100041", agency_address="福岡県福岡市中央区大名2丁目5番31号",
                 agency_president_pos="交通事業管理者", agency_president_name="")]
    write_rows(REF_DIR / "agency_jp.txt", header, rows)


def write_routes_jp() -> None:
    header = ["route_id", "route_update_date", "origin_stop", "via_stop", "destination_stop"]
    rows = [
        dict(route_id="空港線", route_update_date="", origin_stop="姪浜", via_stop="天神", destination_stop="福岡空港"),
        dict(route_id="箱崎線", route_update_date="", origin_stop="中洲川端", via_stop="", destination_stop="貝塚"),
        dict(route_id="七隈線", route_update_date="", origin_stop="橋本", via_stop="天神南", destination_stop="博多"),
    ]
    write_rows(REF_DIR / "routes_jp.txt", header, rows)


def main() -> int:
    REF_DIR.mkdir(parents=True, exist_ok=True)
    print(f"参照データを取得・生成: {REF_DIR}")

    stops_text = fetch("stops.txt")
    s_header, s_rows = transform_stops(stops_text)
    write_rows(REF_DIR / "stops.txt", s_header, s_rows)

    t_header, t_rows = transform_translations(fetch("translations.txt"), s_rows)
    write_rows(REF_DIR / "translations.txt", t_header, t_rows)

    a_header, a_rows = transform_agency(fetch("agency.txt"))
    write_rows(REF_DIR / "agency.txt", a_header, a_rows)

    r_header, r_rows = transform_routes(fetch("routes.txt"))
    write_rows(REF_DIR / "routes.txt", r_header, r_rows)

    for name in COPY_FILES:
        header, rows = read_rows(fetch(name))
        write_rows(REF_DIR / name, header, rows)

    write_agency_jp()
    write_routes_jp()
    print("完了。運賃(fare_*)は scripts/verify_fares.py --write で生成してください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
