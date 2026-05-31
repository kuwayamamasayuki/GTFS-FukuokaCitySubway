# Playwright による GUI 自動テスト導入（Issue #24）

## 背景・目的

本リポジトリの GUI 部分は `demo/` 配下の 3 つの静的ページ（`index.html` 概要ハブ、
`board.html` 発車標、`map.html` 運行マップ）であり、いずれも `fetch` で
`demo/data/*.json` を読み込んで描画する。これらはブラウザ上の動作であるため、
既存の pytest 単体テストでは検証できていない。

Issue #24 の目的は、**Playwright を導入して GUI 部分の動作も自動テストできるようにする**
ことである。

## 全体方針

- 既存資産との統一性を優先し、**`pytest-playwright`（Python）** を採用する。
  既存テストは pytest で書かれており、`demo/capture.py` も Playwright の sync API を
  既に使用している。言語・ツールチェーンを Python に統一することで、CI への追加も最小で済む。
- GUI テストはヘッドレス Chromium で実行する。
- ブラウザ未導入の環境（通常の `make test`）では GUI テストを **skip** し、
  既存の単体テスト実行を一切重くしない。

## コンポーネント

### 1. テストデータ・フィクスチャ（同梱・固定）

`demo/data/*.json` は `.gitignore` 対象（`build/gtfs/` からの生成物）であるため、
テストでは再現性のある固定データを使う。

- `tests/fixtures/demo_gtfs/` に **小さな GTFS フィクスチャ** を同梱する。
  `dist/` の実フィードから、以下を満たす最小サブセットを切り出す:
  - 複数路線（空港線・箱崎線・七隈線のうち少なくとも 2 路線、できれば乗換駅を含む）
  - 両方向（`direction_id` 0/1）
  - 平日・土曜・休日の 3 区分（`calendar` / `calendar_dates`）
  - `shapes`（`network.geojson` の LineString 生成に必要）
  - `stops` の親子（`parent_station`）関係
- GUI テストは起動時にこのフィクスチャからデモデータを生成し、**一時ディレクトリ**へ
  出力する。これによりネットワーク・`build`/`download` 不要で、完全に決定的に動作する。
  生成済み JSON をコミットしないため、出力スキーマ変更時の陳腐化も起きない。

### 2. `build_demo_data.py` の小改修

現状の `build_demo_data.py` は入出力パスが定数固定（`GTFS = ROOT/build/gtfs`、
`OUT = demo/data`）で、関数分割もされていない。テストとフィクスチャ生成を可能にするため:

- 生成処理を `build(gtfs_dir: Path, out_dir: Path) -> None` 関数に切り出す。
- `argparse` で `--gtfs` / `--out` を受け取れるようにする（**デフォルトは現行と同じ**
  `build/gtfs` → `demo/data` を維持し、既存の使い方・Makefile を壊さない）。

これはテスト容易性のための限定的な改善であり、Issue の範囲内とする。

→ プログラム変更を伴うため**単体テスト必須**:
`tests/test_build_demo_data.py` で、フィクスチャ GTFS から `build()` を呼び、
`network.json` / `departures.json` / `animation.json` / `network.geojson` が生成され、
主要キー（路線・駅・色・統計・発車時刻・経路）が期待構造を持つことを検証する。

### 3. GUI テストハーネス `tests/gui/conftest.py`

- セッションスコープの fixture `demo_site` を提供する:
  1. 一時ディレクトリに demo の `*.html` / `style.css` / `vendor/` をコピー
  2. フィクスチャ GTFS から生成したデモデータを `data/` 配下へ配置
  3. `http.server` を空きポートで起動し、base URL を yield
  4. 終了時にサーバを停止
- ページ操作は pytest-playwright が提供する `page` fixture を用いる。
- GUI テストには `@pytest.mark.gui` を付与し、Playwright のブラウザが未導入の場合は
  skip する（`pytest.importorskip` + ブラウザ起動失敗時 skip）。マーカーは
  `pyproject.toml` の `[tool.pytest.ini_options].markers` に登録する。

### 4. GUI テスト `tests/gui/`

- `test_smoke.py`: index / board / map の 3 ページが読み込まれ、主要 DOM が描画される
  ことを確認する。
  - index: `#statgrid .lcard`（統計カード）が表示される
  - board: 駅を 1 つ選ぶと `.rows .row` ないし `.dirgrid` が出る
  - map: `#deck canvas`（deck.gl の描画キャンバス）が生成される
- `test_board.py`: 発車標の操作を検証する。
  - 駅選択（`#rail button`）→ 発車カード `.dirgrid` が出現
  - 平日/土曜/休日タブ（`#svtabs`）切替で `#rows` 内容が更新される
  - 日本語/English（`#lang` のボタン）切替で表示言語が変わる
  - 基準時刻スライダー（`#now`）操作で表示が更新される（`#b-now` 等）
- `test_index.py`: 概要ハブのリンク・導線を検証する。
  - ダウンロードリンク（`data/feed.zip` / `data/network.geojson` /
    `kepler-animation/data/trips.geojson`）の `href` と `download` 属性
  - ナビ（map.html / board.html / 時刻表）への遷移
  - 外部ツール導線（Validator / transit.land / kepler.gl）の `href` 妥当性

### 5. スクリーンショット回帰

厳密なピクセル差分はフォント描画差などで CI が不安定になりやすいため、**採用しない**。
代わりに `demo/capture.py` を流用し、CI でスクリーンショットを**アーティファクトとして撮影**
した上で、テストでは「ファイルが生成され、非空かつ想定サイズ（PNG ヘッダ・最小バイト数）」
であることのサニティ確認に留める。
（将来、緩い閾値付きピクセル差分を入れたくなった場合に拡張できる余地は残す。）

### 6. 依存・CI・Make

- dev 依存に `pytest-playwright` を追加する（`requirements.txt` の開発用節と
  `pyproject.toml` の `[project.optional-dependencies].dev`）。
- CI（`.github/workflows/ci.yml`）の `build-validate` ジョブで、`Unit tests` ステップの
  後に以下を追加する:
  - `python -m playwright install --with-deps chromium`
  - `python -m pytest -m gui`（GUI テストのみ）
- `Makefile` に `test-gui` ターゲットを追加する。
  既存の `test` ターゲットは GUI を除外（`-m "not gui"`）して高速性を維持する。

### 7. ドキュメント

- `demo/README.md` の「スクリーンショット撮影」付近に、GUI 自動テストの実行方法を追記する。
- 本設計書を `docs/superpowers/specs/` に保存・コミットする。

## テスト戦略まとめ

| 対象 | テスト | 種別 |
|---|---|---|
| `build_demo_data.build()` | `tests/test_build_demo_data.py` | 単体（フィクスチャ入出力検証） |
| 3 画面スモーク | `tests/gui/test_smoke.py` | GUI（Playwright） |
| 発車標の操作 | `tests/gui/test_board.py` | GUI（Playwright） |
| 概要ハブのリンク/導線 | `tests/gui/test_index.py` | GUI（Playwright） |
| スクショ撮影 | `tests/gui/test_screenshot.py` | GUI（生成・サニティ確認） |

## 非目標（YAGNI）

- 厳密なピクセル単位のビジュアル回帰テスト。
- `gtfs-to-html` 生成物・`kepler-animation` の GUI テスト（静的成果物であり別 Issue 範囲）。
- Node ベースの `@playwright/test` 併用。
