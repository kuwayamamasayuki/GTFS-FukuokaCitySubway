# 福岡市地下鉄 時刻表Excel → GTFS-JP 生成ツール

福岡市交通局が公開する地下鉄時刻表の Excel
（[資料ページ](https://subway.city.fukuoka.lg.jp/subway/about/material.php)）から、
[GTFS](https://gtfs.org/)（GTFS-JP 拡張つき）静的データを生成するツールです。
ダイヤ改正で時刻表が変わっても、最新 Excel を取り込んで再実行するだけで
フィードを更新できます。

対象路線: **空港線・箱崎線**（`kukohakozaki_timetable.xls`）、**七隈線**（`nanakuma_timetable.xlsx`）。

## 必要環境

- Python 3.10 以上
- GNU Make（任意。`make` ターゲットを使う場合。直接 `python -m fukuoka_gtfs.cli ...` でも可）
- 検証（任意・推奨）に Java 17 以上。未導入でも `--download-tools` でポータブル JRE を
  `tools/` に自動取得して実行します（`sudo` 不要）。

## セットアップ

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"        # または: pip install -r requirements.txt
```

## 使い方

```bash
# 1) 時刻表 Excel を取得（data/ に保存・SHA256 記録）
python -m fukuoka_gtfs.cli download

# 2) GTFS を生成（build/gtfs/ と build/feed.zip、Python 整合検査つき）
python -m fukuoka_gtfs.cli build

# 3) 公式 Canonical Validator + Python 整合検査で検証
python -m fukuoka_gtfs.cli validate --download-tools

# まとめて実行
python -m fukuoka_gtfs.cli all --download-tools
```

`make download` / `make build` / `make validate` / `make all` / `make test` も利用できます。

## 生成される GTFS-JP ファイル

| 区分 | ファイル |
|---|---|
| **Excel から毎回生成** | `trips.txt` `stop_times.txt` `calendar.txt` `calendar_dates.txt` `feed_info.txt` |
| **参照データ（`reference_gtfs/`）** | `agency.txt` `agency_jp.txt` `routes.txt` `routes_jp.txt` `stops.txt` `translations.txt` `shapes.txt` `fare_attributes.txt` `fare_rules.txt` |

## 配布物（`dist/`）

最新ダイヤで生成済みの GTFS-JP フィードを `dist/` に同梱しています。パイプラインを
動かさなくても、そのまま利用・ダウンロードできます。

- `dist/*.txt` — フィード本体（GitHub 上で差分も追える）
- `dist/FukuokaCitySubway.zip` — 配信・各種ツール取り込み用の zip

更新は `make publish`（`build` 実行後に `build/gtfs/` を `dist/` へ反映）で行います。
（`build/` 自体は一時生成物として `.gitignore` 済み。`dist/` が公開スナップショット。）

## デモ（`demo/`）

生成した GTFS-JP フィードを可視化する、**ブラウザだけで動く**デモ一式を `demo/` に同梱
しています。フィードがどんなデータかを手早く確認したり、第三者に見せたりする用途に使えます。

[![デモ概要ハブ](demo/screenshots/index.png)](demo/screenshots/index_full.png)

| 画面 | ファイル | 内容 |
|---|---|---|
| 概要ハブ | `demo/index.html` | 路線図＋統計インフォグラフィックと、feed.zip / GeoJSON のダウンロード・各種既製ツール（Validator・transit.land・OTP）への導線 |
| 運行マップ | `demo/map.html` | 一日の全便を実ダイヤで走らせる運行アニメーション（deck.gl 製・ベースマップ不要） |
| 発車標 | `demo/board.html` | 駅・曜日区分・言語（日本語/English）・基準時刻を切り替えられる発車標／時刻表ビューア |
| 経路検索 | `demo/opentripplanner/` | OpenTripPlanner にフィードと OSM を読ませた経路検索。サンプル経路の静的表示と起動手順を同梱（Issue #25） |

```bash
# 事前に GTFS を生成（build/gtfs/ が必要）
python -m fukuoka_gtfs.cli build

# デモ用データ（demo/data/*.json, network.geojson）を生成
python demo/build_demo_data.py

# ローカルサーバで配信（fetch 利用のため file:// 直開きは不可）
cd demo && python -m http.server 8000   # → http://localhost:8000/
```

データはすべてフィードから自動生成されるため、ダイヤ改正後は `python demo/build_demo_data.py`
を再実行するだけで最新になります。画面構成・スクリーンショット撮影・既製ツール連携などの
詳細は `demo/README.md` を参照してください。

運行マップ（`demo/map.html`）は deck.gl(MIT) 製で、外部ツール不要のままブラウザだけで運行アニメーションを再生します。
既製ツール連携の例として、HTML 時刻表を生成する [GTFS-to-HTML](https://gtfstohtml.com/)（`demo/gtfs-to-html/`、Issue #17）、
運行アニメーションを既製ツールに取り込む [kepler.gl](https://github.com/keplergl/kepler.gl)(MIT)（`demo/kepler-animation/`、Issue #18）、
経路検索を行う [OpenTripPlanner](https://www.opentripplanner.org/)(BSD)（`demo/opentripplanner/`、Issue #25）も同梱しています。

## アーキテクチャ

```
config/         設定（改正時に主に触る場所）
  sources.yaml    Excel の URL と含む路線
  routes.yaml     シート名の語彙 → service_id / direction_id・shape_id 割当(trip_shapes)
  stations.yaml   共用駅のホーム割当の特例
  parser.yaml     パーサ語彙・0時跨ぎ閾値・健全性しきい値
  calendar.yaml   平日/土曜/休日・路線グループ別の有効期間・祝日ポリシー
  feed.yaml       feed_info（発行者・有効期間・版）
reference_gtfs/  滅多に変化しない参照データ（scripts/seed_reference.py で生成）
src/fukuoka_gtfs/
  excel/          Excel 解析（workbook/sheet_classifier/band_detector/
                  train_extractor/time_normalizer）
  station_mapper  駅名→stop_id、路線推定、直通便の分割
  builders/       trips/stop_times・calendar・feed_info の生成
  assembler       参照＋生成を統合し zip 化
  validate        Python 整合検査＋Canonical Validator 実行
  downloader / cli / config / model
scripts/seed_reference.py  参照データのシード（2019 年版から）
scripts/verify_fares.py    運賃を公式運賃表 PDF の三角表から抽出・全ペア検証（--write で再生成）
scripts/fetch_jorudan_fares.py  ジョルダン運賃を取得し突合フィクスチャを更新（Issue #10）
```

### 設計のポイント

- **参照データと生成データの分離**: 座標・路線色・運賃・翻訳などは滅多に変わらないため
  `reference_gtfs/` に保持して再利用し、Excel からは時刻系だけを生成する。
- **レイアウト非依存のパース**: 駅名・駅順・列車はハードコードせず、シートの
  「始発／行先／乗り入れ」「発／着」を語彙で探して動的に読む。改正や駅増設に強い。
  想定外のレイアウトは `LayoutError`（シート名・行・列・期待値つき）で早期に失敗する。
- **中洲川端での直通便分割**: 空港線↔箱崎線の直通便は中洲川端で路線別の 2 つの trip に
  分割し、同一 `block_id` で連結する（各 trip は単一 route_id という GTFS の制約に適合）。
- **0 時跨ぎ・秒誤差の正規化**: 深夜便の時刻を分単位へ**切り捨て**（公式公開時刻に倣う。
  七隈線 `.xlsx` は一部の深夜便を実秒付き＝例 `00:31:42` で持つため、四捨五入すると
  秒 ≥30 の便が +1 分ずれる: Issue #7）、`25:30:00` 形式の 24 時超表記へ統一する。
- **ホーム（子 stop）への割当**: `stop_times` は乗降可能な子ホーム（例 `9_3`）を参照する。
  通常駅は dir0→`_1`／dir1→`_2`、中洲川端・博多などの共用駅は `config/stations.yaml` で指定。
  なお博多は空港線博多(id 11)と七隈線博多(id 37)を別座標の 2 駅で表す（運賃ゾーンは同一）。
  この非対称なモデルの設計意図は [`docs/design/hakata-nanakuma-station.md`](docs/design/hakata-nanakuma-station.md) を参照（Issue #53）。
- **路線グループ・区分別の有効期間**: GTFS では有効期間（`calendar.txt` の start/end）は service_id 単位
  のため、有効期間が異なる路線はグループを分け、`service_id` を `<グループ>_<区分>`
  （例 `空港箱崎_平日`／`七隈_平日`）とする。期間は `config/calendar.yaml` の `service_groups`
  で設定。`start_dates` で **区分（平日/土曜/休日）ごとの改正日（start_date）** を独立して持たせ、
  `end_date` はグループ共通とする。改正が一部区分だけに及ぶ場合も、その区分の `start_dates` だけを
  更新すればよい（グループは独立して期間を持てる）。
  例: 2026/4/1 開始の「ミッドナイト・トレイン」（月〜土の終電延長）に伴い平日・土曜は 20260401〜、
  休日は 4/1 改正の対象外のため従来の改正日（空港箱崎 20260314〜／七隈 20250804〜）を維持（Issue #42）。
  `end_date` が遠い将来でも `calendar_dates`（祝日例外）は `horizon_years` 分だけ生成する。

## ダイヤ改正への対応手順

1. `python -m fukuoka_gtfs.cli download` で最新 Excel を取得し、健全性サマリ
   （6 シート検出・区分×方向・便数）を確認する。
2. 必要に応じて設定だけを更新する:
   - ダイヤ改正日（有効期間の開始）… `config/calendar.yaml` の `service_groups` の `start_dates`
     （路線・区分で改正日が異なる場合は該当する区分のみ更新）
   - フィード全体の有効期間・版 … `config/feed.yaml`（未指定なら start は全区分の最小、end はグループ最大）
   - URL・期待シート名 … `config/sources.yaml`
   - 祝日 … `config/calendar.yaml` の `holiday`
   - **駅が増えた場合のみ** … `reference_gtfs/stops.txt`（親駅＋子ホーム）と
     `config/stations.yaml`、`reference_gtfs/translations.txt`
3. `python -m fukuoka_gtfs.cli all --download-tools` で再生成・検証する。
4. 確認テストの基準データを更新する:
   - 時刻表（ジョルダン突合）: `python scripts/fetch_jorudan_fixtures.py` …
     ジョルダンの最新ダイヤを再取得（`tests/fixtures/jorudan/`）。続けて
     `python scripts/gen_expected_diffs.py` … 既知差分の許容リストを作り直す（`build/gtfs` が必要）。
   - 運賃（ジョルダン突合・Issue #10）: 運賃改定時のみ
     `python scripts/fetch_jorudan_fares.py` でジョルダン運賃を再取得し
     `tests/fixtures/jorudan_fares.json` を更新する。

## 検証（GTFS Validators）

[gtfs.org の Validators](https://gtfs.org/resources/producing-data/#gtfs-validators) のうち
以下を用いる:

1. **Python 整合検査**（必須・常時）: 参照整合（stop/route/service/trip）、時刻の単調性
   （24 時超含む）、`stop_sequence` の連番、乗降可能 stop の参照などを自前で確認。
2. **MobilityData Canonical GTFS Schedule Validator**（Java・公式）:
   `tools/` に JRE と CLI jar を取得して `report.json`/`report.html` を出力。
   合格基準は **ERROR 0 件**（GTFS-JP 拡張ファイルに対する unknown-file 系の通知は許容）。
   ブラウザ版 <https://gtfs-validator.mobilitydata.org/> でも `build/feed.zip` を検証可能。

## データ出典・ライセンス

- 時刻表: 福岡市交通局（上記資料ページ）。
- 運賃: 福岡市交通局「料金表」
  <https://subway.city.fukuoka.lg.jp/fare/pdf/renrakuA4Side.pdf>。三角運賃表（画像 PDF）を
  画像解析し、**全 630 駅ペア**の運賃を抽出して `fare_attributes.txt` / `fare_rules.txt` を生成
  （`scripts/verify_fares.py --write`）。
- 参照データ（座標・路線色・翻訳・shapes 等）: 制作者本人の 2019 年版フィード
  [kuwayamamasayuki/GTFS-FukuokaCitySubway](https://github.com/kuwayamamasayuki/GTFS-FukuokaCitySubway)
  を `scripts/seed_reference.py` で取り込み、現行仕様へ変換。
- 2023 年延伸の新駅座標: 櫛田神社前=日本語版ウィキペディア / 七隈線博多(id 37)=OpenStreetMap（Issue #53）。
- 本ツールのコードは MIT ライセンス。

## 既知の制約

- `shapes.txt` の 6 本（3 路線×2 方向）の線形は、`trips.txt` の `shape_id` 列で各便に紐づける。
  割り当ては `(route_id, direction_id) → shape_id` の対応表（`config/routes.yaml` の `trip_shapes`）に
  基づき機械的に行う（Issue #48）。direction_id の方面は `directions` と同一（0=空港/貝塚/博多方面、
  1=姪浜/橋本方面）。直通便（箱崎線＋空港線）は中洲川端で 2 つの trip に分割済みのため、
  各 trip は単一路線の線形に紐づく。なお七隈線 dir0 の shape_id は博多延伸を反映して
  `七隈線（博多方面行き）`（上流2019フィードの「天神南方面行き」を取り込み時に改称。Issue #48/#55）。
  七隈線の天神南～博多区間は 2019 年版フィードに含まれないため、`scripts/seed_reference.py`
  の `transform_shapes()` で取り込み時に注入している（駅間距離＝福岡市地下鉄事業概要（令和7年度）
  の料金区界表、途中座標＝OpenStreetMap。Issue #55）。
- `stop_times.txt` の `shape_dist_traveled` は、各停車（駅）の座標を紐づく `shapes.txt` の
  線形へ投影し、その最近点の累積距離（メートル、整数丸め）を `shapes.shape_dist_traveled` から
  線形補間して付与する（`builders/shape_dist.py`。Issue #49）。投影は駅ごとに独立に行うため、
  便内では running max で単調非減少に補正する。shape_id を持たない便は空欄になる。
- JR 筑肥線直通便は地下鉄区間（姪浜まで）のみを収録し、行先（筑前前原 等）は
  `trip_headsign` として保持する。

## テスト

```bash
python -m pytest -q
```

`tests/` は合成データによる単体テスト（時刻正規化・バンド検出・駅対応付け・直通分割）と、
`data/` に Excel がある場合の既知便回帰テストから成る。

### GUI テスト（Playwright・Issue #24）

`demo/` の 3 画面を Playwright + ヘッドレス Chromium で自動テストする（`tests/gui/`）。
固定の小さな GTFS フィクスチャからデモデータを生成して検証するため、`download`/`build` や
ネットワークは不要。通常の `make test` は GUI を除外（`-m "not gui"`）し高速に回る。

```bash
pip install -e ".[dev]" && python -m playwright install chromium
make test-gui          # = pytest -q -m gui
```

Chromium 未導入の環境では GUI テストは自動 skip される。詳細は
[`demo/README.md`](demo/README.md) の「GUI 自動テスト」を参照。

### 時刻表の確認テスト（ジョルダン突合・Issue #5）

生成 GTFS の **全駅・全方面・全曜日区分** の発車時刻を、外部の権威ある時刻表
（[ジョルダンの福岡市地下鉄ダイヤ詳細](https://subway.city.fukuoka.lg.jp/schedule/index.php)）
と突合する。ジョルダンの各ページ HTML は `tests/fixtures/jorudan/` に整形済みで同梱（207 件）、
対応関係は `config/jorudan_verify.yaml`。

- **判定は発車時刻（時:分）の集合一致**で行う。行先はジョルダン（地下鉄表示。直通便を
  「姪浜ゆき」等と表示）と GTFS（実際の直通先＝筑前前原等）で表記体系が異なり厳密一致
  できないため、判定には用いない（参考情報）。
- 既知の差分（姪浜・中洲川端の直通便の数え方）は
  `tests/fixtures/jorudan/expected_diffs.json` に記録して許容し、**それ以外の新規差分が
  出たら失敗**する（回帰検知）。七隈線の深夜便 1 分差は Issue #7 で解消済み（秒切り捨て）。
- `build/gtfs`（生成物）を読む。無い場合は skip するので、`make build` 後に実行する。
  別ディレクトリは環境変数 `FUKUOKA_GTFS_DIR` で指定できる。
- 索引に無い 天神南→博多（七隈線 dir0）は対象外。

詳細な設計は `docs/superpowers/specs/2026-05-30-timetable-verification-design.md`。

### 運賃の確認テスト（ジョルダン突合・Issue #10）

生成 GTFS の **全 630 駅ペア** の運賃（`fare_attributes.txt` / `fare_rules.txt`）を、
ジョルダンの[発着・料金検索](https://fukuoka-city-subway.jorudan.biz/pc/route)が示す
**普通料金**と突合する。公式運賃表 PDF（`scripts/verify_fares.py`）とは独立した第 2 の検証。

- 料金検索のトップは JS 駆動の SPA だが、結果ページ(`/pc/nsresult`)はサーバ描画なので、
  `scripts/fetch_jorudan_fares.py` が結果 URL を直接 GET して普通料金を一度だけ取得し
  （ブラウザ不要・既存の `requests` のみ）、`tests/fixtures/jorudan_fares.json` に保存する。
  **テストはこの JSON を読むだけでネットワークに依存しない**。
- 既知の相違は `config/jorudan_fare_verify.yaml` の `allow` に登録して許容し、
  **それ以外の不一致が出たら失敗**する（回帰検知）。原則 0 件。
- フィクスチャ未取得の環境では skip する（同梱済みなら常に実行）。

詳細な設計は `docs/superpowers/specs/2026-05-30-fare-verification-design.md`。
