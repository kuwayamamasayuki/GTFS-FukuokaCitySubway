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
| **参照データ（`reference_gtfs/`）** | `agency.txt` `agency_jp.txt` `routes.txt` `routes_jp.txt` `stops.txt` `translations.txt` `transfers.txt` `shapes.txt` `fare_attributes.txt` `fare_rules.txt` |

## 配布物（`dist/`）

最新ダイヤで生成済みの GTFS-JP フィードを `dist/` に同梱しています。パイプラインを
動かさなくても、そのまま利用・ダウンロードできます。

- `dist/*.txt` — フィード本体（GitHub 上で差分も追える）
- `dist/FukuokaCitySubway.zip` — 配信・各種ツール取り込み用の zip

更新は `make publish`（`build` 実行後に `build/gtfs/` を `dist/` へ反映）で行います。
（`build/` 自体は一時生成物として `.gitignore` 済み。`dist/` が公開スナップショット。）

## アーキテクチャ

```
config/         設定（改正時に主に触る場所）
  sources.yaml    Excel の URL と含む路線
  routes.yaml     シート名の語彙 → service_id / direction_id
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
```

### 設計のポイント

- **参照データと生成データの分離**: 座標・路線色・運賃・翻訳などは滅多に変わらないため
  `reference_gtfs/` に保持して再利用し、Excel からは時刻系だけを生成する。
- **レイアウト非依存のパース**: 駅名・駅順・列車はハードコードせず、シートの
  「始発／行先／乗り入れ」「発／着」を語彙で探して動的に読む。改正や駅増設に強い。
  想定外のレイアウトは `LayoutError`（シート名・行・列・期待値つき）で早期に失敗する。
- **中洲川端での直通便分割**: 空港線↔箱崎線の直通便は中洲川端で路線別の 2 つの trip に
  分割し、同一 `block_id` で連結する（各 trip は単一 route_id という GTFS の制約に適合）。
- **0 時跨ぎ・秒誤差の正規化**: 深夜便の時刻を分単位に丸め、`25:30:00` 形式の 24 時超
  表記へ統一する。
- **ホーム（子 stop）への割当**: `stop_times` は乗降可能な子ホーム（例 `9_3`）を参照する。
  通常駅は dir0→`_1`／dir1→`_2`、中洲川端・博多などの共用駅は `config/stations.yaml` で指定。
- **路線グループ別の有効期間**: GTFS では有効期間（`calendar.txt` の start/end）は service_id 単位
  のため、有効期間が異なる路線はグループを分け、`service_id` を `<グループ>_<区分>`
  （例 `空港箱崎_平日`／`七隈_平日`）とする。期間は `config/calendar.yaml` の `service_groups`
  で設定（例: 空港線・箱崎線 20260314〜、七隈線 20250804〜、ともに 99991231 まで）。
  `end_date` が遠い将来でも `calendar_dates`（祝日例外）は `horizon_years` 分だけ生成する。

## ダイヤ改正への対応手順

1. `python -m fukuoka_gtfs.cli download` で最新 Excel を取得し、健全性サマリ
   （6 シート検出・区分×方向・便数）を確認する。
2. 必要に応じて設定だけを更新する:
   - 有効期間・版 … `config/feed.yaml`
   - URL・期待シート名 … `config/sources.yaml`
   - 祝日 … `config/calendar.yaml`
   - **駅が増えた場合のみ** … `reference_gtfs/stops.txt`（親駅＋子ホーム）と
     `config/stations.yaml`、`reference_gtfs/translations.txt`
3. `python -m fukuoka_gtfs.cli all --download-tools` で再生成・検証する。
4. 時刻表確認テスト（ジョルダン突合）の基準データを更新する:
   - `python scripts/fetch_jorudan_fixtures.py` … ジョルダンの最新ダイヤを再取得（`tests/fixtures/jorudan/`）。
   - `python scripts/gen_expected_diffs.py` … 既知差分の許容リストを作り直す（`build/gtfs` が必要）。

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
- 2023 年延伸の新駅座標（櫛田神社前・七隈線博多）: 日本語版ウィキペディア。
- 本ツールのコードは MIT ライセンス。

## 既知の制約

- `shapes.txt` は参照用に同梱するが trip には紐づけていない（七隈線の形状は天神南止まりで
  延伸前のもの。直通便は単一形状で表せない）。地図描画用途では別途整備が必要。
- JR 筑肥線直通便は地下鉄区間（姪浜まで）のみを収録し、行先（筑前前原 等）は
  `trip_headsign` として保持する。

## テスト

```bash
python -m pytest -q
```

`tests/` は合成データによる単体テスト（時刻正規化・バンド検出・駅対応付け・直通分割）と、
`data/` に Excel がある場合の既知便回帰テストから成る。

### 時刻表の確認テスト（ジョルダン突合・Issue #5）

生成 GTFS の **全駅・全方面・全曜日区分** の発車時刻を、外部の権威ある時刻表
（[ジョルダンの福岡市地下鉄ダイヤ詳細](https://subway.city.fukuoka.lg.jp/schedule/index.php)）
と突合する。ジョルダンの各ページ HTML は `tests/fixtures/jorudan/` に整形済みで同梱（207 件）、
対応関係は `config/jorudan_verify.yaml`。

- **判定は発車時刻（時:分）の集合一致**で行う。行先はジョルダン（地下鉄表示。直通便を
  「姪浜ゆき」等と表示）と GTFS（実際の直通先＝筑前前原等）で表記体系が異なり厳密一致
  できないため、判定には用いない（参考情報）。
- 既知の差分（七隈線の一部便の 1 分差、姪浜・中洲川端の直通便の数え方）は
  `tests/fixtures/jorudan/expected_diffs.json` に記録して許容し、**それ以外の新規差分が
  出たら失敗**する（回帰検知）。既知差分は要調査事項として残している。
- `build/gtfs`（生成物）を読む。無い場合は skip するので、`make build` 後に実行する。
  別ディレクトリは環境変数 `FUKUOKA_GTFS_DIR` で指定できる。
- 索引に無い 天神南→博多（七隈線 dir0）は対象外。

詳細な設計は `docs/superpowers/specs/2026-05-30-timetable-verification-design.md`。
