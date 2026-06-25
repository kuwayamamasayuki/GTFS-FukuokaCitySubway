#!/usr/bin/env python3
"""reference_gtfs/ を生成（シード）するワンタイム・スクリプト。

出所: ユーザー本人の 2019 年版フィード
  https://github.com/kuwayamamasayuki/GTFS-FukuokaCitySubway （3 生成物/）

このスクリプトは「滅多に変化しない参照データ」だけを取り込み、現行仕様に合わせて
変換したうえで reference_gtfs/ に書き出す。trips/stop_times/calendar/feed_info は
Excel から毎回生成するため、ここでは扱わない。

主な変換:
  * stops.txt   : 2023 年の七隈線博多延伸を反映。
                  - 博多(id 11) は空港線駅として据え置き、stop_code を "K11/N18" に更新
                    （N18 はジャンクション判定用。詳細は station_mapper / 設計ドキュメント）。
                  - 七隈線博多(N18) は空港線博多と物理的に別位置のため、独立駅 id 37 +
                    子ホーム 37_3/37_4 として別座標で追加（運賃ゾーンは zone_id=11 で同一）。
                    Issue #53。
                  - 櫛田神社前(N17, 新 id 36) を親+子ホーム 36_1/36_2 で追加。
  * translations: 旧スキーマ(trans_id,lang,translation) → 現行スキーマ
                  (table_name,field_name,language,field_value,translation) へ移行。
                  feed_lang(ja) と同一の自己翻訳は除外。新駅の訳語を追加。
  * routes.txt  : route_sort_order 列を補い、空港線→箱崎線→七隈線の順で表示させる。
  * agency_jp / routes_jp : GTFS-JP 拡張ファイルを新規作成（公開用）。
  * shapes/fare_attributes/fare_rules : ほぼそのまま取り込み。
  * transfers.txt : 取り込まない。七隈線の博多延伸で天神・天神南が連絡駅とみなされ
                    なくなったため、連絡駅情報のファイル自体を廃止した（Issue #40）。

新駅の座標出典: 櫛田神社前駅=日本語版ウィキペディア / 七隈線博多駅(id 37)=OpenStreetMap(Issue #53)。
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

# shapes.txt は transform_shapes() で七隈線の天神南～博多を注入して取り込む（Issue #55）。
# 運賃 fare_* は scripts/verify_fares.py が公式運賃表 PDF から生成。
# transfers.txt は取り込まない（Issue #40: 連絡駅情報の廃止）。

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

# 七隈線博多(N18) — 空港線博多(K11, id 11)とは物理的に少し離れているため、独立した親駅
# id 37 として別座標で持たせる（Issue #53）。ただし運賃ゾーンは空港線博多と同一(zone_id=11)に
# 保ち、駅名「博多」も共有する。
#   * 11 は "K11/N18"(共用ジャンクション)・空港線座標のまま据え置く。これは StationMapper の
#     名前解決とジャンクション判定が 11 を単一情報源とするため（理由は station_mapper.from_stops
#     と docs/design/hakata-nanakuma-station.md を参照）。
#   * 七隈線ホームは 37_3/37_4(parent_station=37) として 37 配下へ。config/stations.yaml の
#     platform_overrides が親 11 のキーで 37_3/37_4 を返すよう設定する。
# 座標出典: OpenStreetMap（七隈線博多駅ホーム付近）。
NANAKUMA_HAKATA_ID = "37"
NANAKUMA_HAKATA = dict(stop_code="N18", stop_name="博多",
                       stop_lat="33.589616", stop_lon="130.418599", zone_id="11")

# 七隈線 天神南～博多の延伸形状（Issue #55）。
# 上流2019フィードの shapes.txt は七隈線が天神南止まりで博多までの区間を含まない
# （延伸開業前のデータのため）。公開フィードでは博多まで描画したいので、取り込み時に注入する。
#   * 駅間距離(shape_dist_traveled)は福岡市地下鉄事業概要(令和7年度)の料金区界表より、
#     途中の座標は OpenStreetMap から取得（出典は Issue #55 / docs を参照）。
# 上流2019フィードでは七隈線が天神南止まりで、dir0 の shape_id も「天神南方面行き」。
# 延伸で終点が博多になったため、出力 shape_id は実態に合わせ「博多方面行き」へ改称する
# （Issue #48）。読み込みは上流名(_SRC)で行い、区間注入後に出力名へリネームする。
SHAPE_NANAKUMA_TM_SRC = "七隈線（天神南方面行き）"  # 上流フィードの dir0 shape_id（読み込みキー）
SHAPE_NANAKUMA_TM = "七隈線（博多方面行き）"  # 出力 dir0 shape_id（末尾=博多。後ろへ博多側を追記）
SHAPE_NANAKUMA_HM = "七隈線（橋本方面行き）"  # 橋本方面行き（先頭=天神南。前へ博多側を前置）
# 天神南方面行きで seq112(天神南) の後に続く博多側の点列：(lat, lon, dist[m])。
# dist は天神南方面行きの起点(橋本側)からの累積距離。末尾(13600)が博多(N18)。
NANAKUMA_HAKATA_SHAPE = [
    ("33.590296", "130.406567", 12500),
    ("33.591515", "130.409300", 12800),
    ("33.591804", "130.410062", 12850),
    ("33.591810", "130.410465", 12900),
    ("33.591625", "130.411039", 12950),
    ("33.591333", "130.411583", 13000),
    ("33.589836", "130.414235", 13250),
    ("33.589616", "130.418599", 13600),  # 博多(N18)
]

# --- 各駅の地上出入口(location_type=2) (Issue #50) ---------------------------------
# 目的: 出入口を stop として持たせると、徒歩を含むドアtoドアの経路検索が可能になる。
# 出入口データ（名称・緯度経度・親駅・wheelchair_boarding）は、ユーザー本人が過去に
# 各駅・各ホーム・各出入口の緯度経度を実測登録した旧フィード（git 0e19136「各駅の各
# ホーム，各出入口の緯度・経度を登録しました」, 2018年版）からそのまま採録した実測値で、
# scripts/data/legacy_entrances.csv に置く（現行 stops.txt と同じ列構成）。
#   * 対象は当時の全35駅(parent 1〜35)・計198出入口。2023年開業の新駅 36(櫛田神社前) /
#     37(七隈線博多) は当時存在せず未収録（博多複合駅の出入口は当時の id 11 配下にある）。
# 仕様: https://gtfs.org/documentation/schedule/reference/#stopstxt (location_type=2)
LEGACY_ENTRANCES_CSV = Path(__file__).resolve().parent / "data" / "legacy_entrances.csv"


def load_legacy_entrances() -> list[dict]:
    """scripts/data/legacy_entrances.csv から出入口(location_type=2)行を読み込む。"""
    _, rows = read_rows(LEGACY_ENTRANCES_CSV.read_text(encoding="utf-8-sig"))
    return [r for r in rows if r.get("location_type") == "2"]


# stops.stop_name の英語訳の上書き（上流フィードの表記を公開フィード向けに補正）。
# 福岡空港: 上流は "Fukuokakuko(Airport)" だが正式英語名称は "Fukuoka Airport"。
# 櫛田神社前: 新駅定義の en と一致（再掲して意図を明示）。
EN_OVERRIDES = {
    "福岡空港": "Fukuoka Airport",
    "櫛田神社前": "Kushida Shrine",
}

# trips.trip_headsign（行先）として現れる値。translations は
# table_name+field_name+field_value で引かれるため、駅名が stops で翻訳済みでも
# trips/trip_headsign は別レコードとして翻訳行を用意しないと多言語表示されない（Issue #46）。
# 地下鉄駅と一致する行先は stops の訳語をそのまま再利用し、相互直通で乗り入れる
# JR 筑肥線の駅（地下鉄 stops に存在しない）は TRIP_HEADSIGN_EXTRA から補う。
TRIP_HEADSIGNS = [
    "姪浜", "西新", "中洲川端", "貝塚", "博多", "福岡空港", "橋本",  # 地下鉄各駅
    "唐津", "西唐津", "筑前前原", "筑前深江",  # 相互直通 JR 筑肥線（地下鉄 stops に無い）
]
TRIP_HEADSIGN_EXTRA = {
    "唐津": {"ja-Hrkt": "からつ", "en": "Karatsu"},
    "西唐津": {"ja-Hrkt": "にしからつ", "en": "Nishi-Karatsu"},
    "筑前前原": {"ja-Hrkt": "ちくぜんまえばる", "en": "Chikuzen-Maebaru"},
    "筑前深江": {"ja-Hrkt": "ちくぜんふかえ", "en": "Chikuzen-Fukae"},
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

    # --- 博多(id 11): 空港線側はそのまま。stop_code を共用表記 "K11/N18" に更新 ---
    # （N18 を 11 に残すのは StationMapper のジャンクション判定に必須。詳細は
    #   NANAKUMA_HAKATA の定義コメント / docs/design/hakata-nanakuma-station.md 参照）
    by_id["11"]["stop_code"] = "K11/N18"

    # --- 七隈線博多(N18) を独立駅 id 37 として追加（座標は空港線博多と別、運賃ゾーンは同一） ---
    nh = NANAKUMA_HAKATA
    if NANAKUMA_HAKATA_ID not in by_id:
        rows.append(dict(stop_id=NANAKUMA_HAKATA_ID, stop_code=nh["stop_code"],
                         stop_name=nh["stop_name"], stop_lat=nh["stop_lat"], stop_lon=nh["stop_lon"],
                         zone_id=nh["zone_id"], stop_url="", location_type="1",
                         parent_station="", wheelchair_boarding="1"))
        for plat in ("37_3", "37_4"):
            rows.append(dict(stop_id=plat, stop_code="", stop_name=nh["stop_name"],
                             stop_lat=nh["stop_lat"], stop_lon=nh["stop_lon"], zone_id=nh["zone_id"],
                             stop_url="", location_type="0", parent_station=NANAKUMA_HAKATA_ID,
                             wheelchair_boarding="1"))

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

    # --- 各駅の地上出入口(location_type=2) を追加（Issue #50） ---
    # 旧フィード(2018年版)由来の実測出入口を採録する。stop_id が既にあれば追加しない
    # （冪等：出力を再投入しても重複しない）。列は現行 stops.txt に合わせて補完する。
    by_id = {r["stop_id"]: r for r in rows}
    for e in load_legacy_entrances():
        if e["stop_id"] in by_id:
            continue
        row = {col: e.get(col, "") for col in header}
        rows.append(row)
        by_id[e["stop_id"]] = row

    return header, rows


def transform_shapes(text: str) -> tuple[list[str], list[dict]]:
    """七隈線に天神南～博多の区間を注入する（Issue #55）。

    上流2019フィードの shapes は七隈線が天神南止まりのため、取り込み時に
      * dir0(上流名「天神南方面行き」) … 末尾(天神南, seq112) の後ろへ博多側 8 点を
                        追記し、shape_id を出力名「博多方面行き」へ改称する（Issue #48）。
      * 橋本方面行き   … 先頭へ博多→天神南の 8 点(seq0..7) を前置し、既存点の
                        shape_pt_sequence/shape_dist_traveled を博多起点へずらす。
    博多は dir0 で dist=13600。橋本方面行きでは博多が起点(dist0)になるため、
    各点の橋本側 dist = 13600 - (天神南側 dist)。既存点のずらし幅は天神南末尾(天神南駅)の
    dist 12000 を用いて 13600-12000=1600。再実行しても二重追加しない（冪等）。
    """
    header, rows = read_rows(text)
    hakata_lat, hakata_lon, total = NANAKUMA_HAKATA_SHAPE[-1]

    def extend_tm(block: list[dict]) -> list[dict]:
        if any(r["shape_pt_lat"] == hakata_lat and r["shape_pt_lon"] == hakata_lon
               for r in block):
            return block  # 既に延伸済み
        seq = int(block[-1]["shape_pt_sequence"])
        for lat, lon, dist in NANAKUMA_HAKATA_SHAPE:
            seq += 1
            block.append({"shape_id": SHAPE_NANAKUMA_TM, "shape_pt_lat": lat,
                          "shape_pt_lon": lon, "shape_pt_sequence": str(seq),
                          "shape_dist_traveled": str(dist)})
        return block

    def prepend_hm(block: list[dict], d_tenjinminami: int) -> list[dict]:
        if block[0]["shape_pt_lat"] == hakata_lat and block[0]["shape_pt_lon"] == hakata_lon:
            return block  # 既に前置済み
        shift_seq = len(NANAKUMA_HAKATA_SHAPE)
        shift_dist = total - d_tenjinminami  # 博多→天神南の距離(=1600)
        for r in block:
            r["shape_pt_sequence"] = str(int(r["shape_pt_sequence"]) + shift_seq)
            r["shape_dist_traveled"] = str(int(r["shape_dist_traveled"]) + shift_dist)
        head = [{"shape_id": SHAPE_NANAKUMA_HM, "shape_pt_lat": lat, "shape_pt_lon": lon,
                 "shape_pt_sequence": str(seq), "shape_dist_traveled": str(total - dist)}
                for seq, (lat, lon, dist) in enumerate(reversed(NANAKUMA_HAKATA_SHAPE))]
        return head + block

    # 橋本方面のずらし幅に使う、dir0(上流名)の元の末尾(天神南駅)の dist を控える。
    tm_orig = [r for r in rows if r["shape_id"] == SHAPE_NANAKUMA_TM_SRC]
    d_tenjinminami = int(tm_orig[-1]["shape_dist_traveled"]) if tm_orig else total

    # shape_id ごとの連続ブロック単位で処理し、元の行順を保つ。
    out: list[dict] = []
    i, n = 0, len(rows)
    while i < n:
        sid = rows[i]["shape_id"]
        j = i
        while j < n and rows[j]["shape_id"] == sid:
            j += 1
        block = rows[i:j]
        if sid == SHAPE_NANAKUMA_TM_SRC:
            block = extend_tm(block)
            for r in block:
                r["shape_id"] = SHAPE_NANAKUMA_TM  # 上流名「天神南方面行き」→出力名「博多方面行き」
        elif sid == SHAPE_NANAKUMA_HM:
            block = prepend_hm(block, d_tenjinminami)
        out.extend(block)
        i = j
    return header, out


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

    # trips.trip_headsign（行先）の翻訳を追記（Issue #46）。駅名と一致する行先は
    # 上で組み立てた駅の訳語を再利用し（en は EN_OVERRIDES を反映）、相互直通の
    # JR 駅は TRIP_HEADSIGN_EXTRA から補う。
    for name in TRIP_HEADSIGNS:
        if name in table:
            langs = {lg: tr for lg, tr in table[name].items() if lg != "ja"}
            if "en" in langs and name in EN_OVERRIDES:
                langs["en"] = EN_OVERRIDES[name]
        elif name in TRIP_HEADSIGN_EXTRA:
            langs = dict(TRIP_HEADSIGN_EXTRA[name])
        else:
            print(f"  注意: 行先の訳語不明のためスキップ: {name!r}", file=sys.stderr)
            continue
        for lang, tr in langs.items():
            out.append(dict(table_name="trips", field_name="trip_headsign",
                            language=lang, field_value=name, translation=tr))
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

    sh_header, sh_rows = transform_shapes(fetch("shapes.txt"))
    write_rows(REF_DIR / "shapes.txt", sh_header, sh_rows)

    write_agency_jp()
    write_routes_jp()
    print("完了。運賃(fare_*)は scripts/verify_fares.py --write で生成してください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
