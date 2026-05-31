# OpenTripPlanner で経路検索を試す例（Issue #25）

[OpenTripPlanner](https://www.opentripplanner.org/)（OTP・**2-clause BSD License**）は、
GTFS と OpenStreetMap（OSM）を入力にマルチモーダルな**経路検索**を行う定番の OSS
エンジンです。本リポジトリが生成した GTFS-JP フィードと福岡周辺の OSM を読ませると、
「橋本 → 福岡空港」のような検索ができます。

このディレクトリには、

- OTP の作業ディレクトリを組み立てる準備スクリプト `prepare_otp.py`
- 起動中の OTP からサンプル経路を取得する `fetch_sample.py`
- ネット/Java 無しでもサンプル経路を閲覧できる静的ページ `index.html`

を同梱しています。OTP 本体（jar）と OSM・グラフは大きいため**コミットしません**
（`.gitignore` 済み）。コミットするのはスクリプト・ページ・取得済みサンプル
（`data/sample-itinerary.json`）です。

> ブラウザ完結で運行を眺めたいだけなら、同梱の [`../map.html`](../README.md)（deck.gl 製）が
> そのまま使えます。本ディレクトリは「既製の経路検索エンジン（OTP）に取り込む」例です。

## 必要環境

- **Java 17 以上**（OTP 2.x の要件。本リポジトリ CI も Java 17 を使用）。
- OSM のクリップに [osmium-tool](https://osmcode.org/osmium-tool/)（`apt-get install osmium-tool`
  / `brew install osmium-tool`）。クリップ済み OSM を `--osm` で渡せば不要です。
- メモリは `-Xmx4g` 程度を推奨。

## 使い方

```bash
# 1) 作業ディレクトリを用意（フィードから bbox を算出 → OSM 取得・クリップ → OTP jar 取得 → config 生成）
make demo-otp
#   = python demo/opentripplanner/prepare_otp.py
#   work/ に fukuoka.osm.pbf / otp-2.5.0-shaded.jar / FukuokaCitySubway.zip / *-config.json

# 2) グラフ構築 → サーバ起動（http://localhost:8080）
cd demo/opentripplanner/work
java -Xmx4g -jar otp-2.5.0-shaded.jar --build --save .
java -Xmx4g -jar otp-2.5.0-shaded.jar --load .

# 3) 別ターミナルでサンプル経路を取得（橋本 → 福岡空港）
make demo-otp-sample
#   = python demo/opentripplanner/fetch_sample.py
#   → data/sample-itinerary.json を更新（index.html がこれを表示）
```

OTP を起動したら、付属の**デバッグ用 Web クライアント**（<http://localhost:8080/>）でも
地図上の経路検索を試せます。

## オフライン表示ページ（`index.html`）

`data/sample-itinerary.json` を読み込み、サンプル経路（所要時間・乗換・各 leg）を静的に
表示します。デモをローカルサーバで配信していれば
`http://localhost:8000/opentripplanner/` で開けます（`file://` 直開きは fetch 不可）。
サンプル未生成時は生成手順を案内します。

## `prepare_otp.py` のオプション

| オプション | 既定 | 意味 |
|---|---|---|
| `--workdir` | `demo/opentripplanner/work` | 作業ディレクトリ |
| `--feed` | `dist/FukuokaCitySubway.zip` | 入力 GTFS zip |
| `--region` | `asia/japan/kyushu` | Geofabrik の OSM リージョン |
| `--otp-version` | `2.5.0` | OTP のバージョン（Maven Central から取得） |
| `--margin-km` | `3.0` | フィード外接 bbox に足す余白(km) |
| `--osm` | （なし） | bbox 抽出済みの OSM を直接指定（DL/クリップをスキップ） |

## `fetch_sample.py` のオプション

| オプション | 既定 | 意味 |
|---|---|---|
| `--endpoint` | `http://localhost:8080/otp/routers/default/index/graphql` | OTP GraphQL |
| `--feed` | `dist/FukuokaCitySubway.zip` | 駅座標の参照元 |
| `--from` / `--to` | `橋本` / `福岡空港` | 出発・目的駅名 |
| `--date` / `--time` | `2026-04-01` / `08:00:00` | 検索日時 |
| `--out` | `data/sample-itinerary.json` | 保存先 |

## ライセンス・出典

- **OpenTripPlanner**: 2-clause BSD License（[opentripplanner/OpenTripPlanner](https://github.com/opentripplanner/OpenTripPlanner)）。
- **OSM データ**: © OpenStreetMap contributors、**ODbL**。
  [Geofabrik](https://download.geofabrik.de/) 配布の九州抽出を bbox でクリップして使用します。
- 時刻表データ: 福岡市交通局。

## 関連

- 既製ツール連携の例: HTML 時刻表 [`../gtfs-to-html/`](../gtfs-to-html/README.md)（Issue #17）、
  運行アニメーション [`../kepler-animation/`](../kepler-animation/README.md)（Issue #18）。
- ブラウザ完結の運行アニメーション: [`../map.html`](../README.md)（deck.gl 製）。
