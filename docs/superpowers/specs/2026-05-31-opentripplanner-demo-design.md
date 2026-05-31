# demo に OpenTripPlanner を加える（Issue #25）

## 背景・目的

`demo/` には既製ツール連携の例として `gtfs-to-html/`（HTML 時刻表・Issue #17）と
`kepler-animation/`（運行アニメーション・Issue #18）があり、いずれも
「ディレクトリ＋準備スクリプト＋README＋Make ターゲット＋`index.html` からの導線」
という共通構成を持つ。

[OpenTripPlanner](https://www.opentripplanner.org/)（OTP）は GTFS と OSM を入力に
**マルチモーダル経路検索**を行う既製エンジンである。現状 `demo/index.html` には OTP の
起動コマンドがベタ書きされているだけで、他ツールのような第一級の例になっていない。
Issue #25 の目的は、**OTP を他ツールと同じ構成で demo に加える**こと。

## 制約

- OTP はブラウザ完結できない。**Java 17 以上**と OSM 抽出、グラフ構築（サーバ）が必要。
  本リポジトリ CI は既に Java 17 をセットアップしている。対象は **OTP 2.5.0**
  （Java 17 で動作する系列。Java 21 でも動く）。
- 経路検索 UI は **OTP 同梱のデバッグクライアント**（`http://localhost:8080`）を使い、
  ライブ経路検索の独自 UI は作らない（YAGNI）。
- ネット/Java 無しでも例が見えるよう、**実 OTP 実行で得たサンプル経路 JSON を同梱**し、
  軽量な静的ページで表示する。サンプルは Java 17+ 上で実際に OTP を起動して生成した
  本物のデータとする（捏造しない）。

## コンポーネント

### 1. `demo/opentripplanner/prepare_otp.py`（準備スクリプト）

OTP 作業ディレクトリを組み立てる。テストのため**純粋関数**を分離する:

- `bbox_from_stops(stops, margin_km)` — フィードの停留所座標から外接 bbox を求め、
  指定マージン（km）だけ広げた `(min_lon, min_lat, max_lon, max_lat)` を返す。
- `build_config()` / `router_config()` / `otp_config()` — OTP2 用の
  `build-config.json` / `router-config.json` / `otp-config.json` の内容（dict）を返す。
- `geofabrik_url(region="asia/japan/kyushu")` — Geofabrik の OSM DL URL を生成。
- `otp_jar_url(version="2.5.0")` — Maven Central の OTP shaded jar URL を生成。
- `osmium_extract_args(bbox, src, dst)` — `osmium extract` のコマンド引数列を生成。

ネットワーク/サブプロセス（jar・OSM の DL、osmium クリップ、feed.zip 配置、config 書き出し）
はこれら純粋関数を用いる薄いラッパとして実装し、`--workdir` などを `argparse` で受ける。
osmium 未導入時は明確なエラーと導入方法を案内する。

### 2. `demo/opentripplanner/fetch_sample.py`（サンプル取得）

ローカル起動中の OTP に GTFS GraphQL API で経路検索（既定: 橋本 → 福岡空港）し、
結果を `data/sample-itinerary.json` に保存する。テストのため純粋関数を分離:

- `find_stop_coord(stops, name)` — フィードの stops から駅名で緯度経度を引く。
- `plan_query(from_coord, to_coord, date, time)` — GraphQL クエリ文字列を生成。
- `summarize_itinerary(response)` — OTP の応答から所要時間・乗換回数・各 leg
  （mode/路線/出発到着）の要約を抽出した dict を返す。`data/sample-itinerary.json`
  はこの要約＋生応答の必要部分を含む。

### 3. `demo/opentripplanner/index.html`（オフライン表示ページ）

demo デザイン（ダーク基調・3 路線カラー、戻りリンク）に揃えた軽量ページ。
`data/sample-itinerary.json` を `fetch` して**同梱サンプル経路を静的表示**し、
起動中の OTP デバッグ UI（`http://localhost:8080`）へのリンクと起動手順を示す。
サンプル未生成時は「`make demo-otp-sample` で生成してください」と案内する。
ライブ経路検索は行わない。

このページはブラウザ描画のため、本 PR では**手動テスト**で確認する（Playwright による
GUI テスト基盤は別 PR #24 にあり master 未マージのため、本 PR では依存しない。#24
マージ後に GUI テストを追加できる）。手動手順は実装時に明示する。

### 4. `demo/opentripplanner/README.md`

他ツール README と同構成: OTP とは / なぜ OTP（経路検索の定番・BSD ライセンス）/
ライセンスと出典（OTP, および OSM データ = **ODbL**、Geofabrik 出典明記）/
Java 17 要件 / 手順（prepare → 起動 → sample 取得）/ オプション表 / 関連リンク。

### 5. `Makefile`

- `demo-otp` — `prepare_otp.py` を実行し OTP 作業ディレクトリを用意。
- `demo-otp-sample` — 起動中の OTP に問い合わせて `data/sample-itinerary.json` を生成。

### 6. 導線・ドキュメント更新

- `demo/index.html` の OTP 部分（jar コマンドのベタ書き）を新ディレクトリ/ページへの
  リンクに差し替える。
- `demo/README.md`・top `README.md` の表/記述を更新し OTP を第一級の例として加える。

### 7. テスト

- `tests/test_prepare_otp.py` — `bbox_from_stops` / 各 config 生成 / `geofabrik_url` /
  `otp_jar_url` / `osmium_extract_args` を単体テスト。
- `tests/test_otp_sample.py` — `find_stop_coord` / `plan_query` /
  `summarize_itinerary`（小さな OTP 応答フィクスチャを入力）を単体テスト。
- `demo/opentripplanner/index.html`（オフライン表示ページ）はブラウザ描画のため
  **手動テスト**（実装時に手順を明示）。Playwright 基盤が master に入り次第 GUI テスト追加可。

### 8. `.gitignore`

OTP の作業生成物（`demo/opentripplanner/work/`、`*.osm.pbf`、OTP jar、`graph.obj` 等）を
無視する。コミットするのは config テンプレ・スクリプト・README・`data/sample-itinerary.json`。

## サンプル生成の運用（本物のデータ）

サンプル `data/sample-itinerary.json` は、Java 17+ 環境で実際に OTP を起動して生成する:

```bash
make demo-otp                 # OSM/jar 取得・クリップ・config 生成
java -jar work/otp-2.5.0-shaded.jar --load work   # OTP 起動（別ターミナル）
make demo-otp-sample          # 橋本→福岡空港の経路を取得して data/ に保存
```

## 非目標（YAGNI）

- ライブ経路検索の独自 UI（OTP 同梱デバッグクライアントを使う）。
- CI での OTP グラフ構築・サーバ起動（重く不安定なため行わない。純粋関数のみ単体テスト）。
- リアルタイム（GTFS-RT）連携。
