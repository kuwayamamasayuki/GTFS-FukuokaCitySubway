# 福岡市地下鉄 GTFS — デモ

生成した GTFS-JP フィードを可視化する、ブラウザだけで動くデモ一式です。
ご要望の 4 種類をすべて収録しています。

| 画面 | ファイル | 内容（ご要望との対応） |
|---|---|---|
| 概要ハブ | `index.html` | **路線図 + 統計インフォグラフィック**（D）と、**既製ツール連携**（C: feed.zip / GeoJSON ダウンロード、Validator・transit.land・OTP への導線） |
| 運行マップ | `map.html` | **運行アニメーション**（A）。一日の全便が 3 色の路線を実ダイヤで走行。時刻・速度・区分・走行本数。deck.gl 製 |
| 発車標 | `board.html` | **発車標・時刻表ビューア**（B）。駅選択・平日/土曜/休日・日本語/English・基準時刻スライダー |
| HTML 時刻表 | `gtfs-to-html/html/index.html` | **既製ツール [GTFS-to-HTML](https://gtfstohtml.com/) 連携**（Issue #17）。フィードから路線別の印刷向け時刻表 HTML を自動生成。詳細は [`gtfs-to-html/README.md`](gtfs-to-html/README.md) |

## 動かし方

データは `fetch` で読み込むため、ローカルサーバ経由で開いてください（`file://` 直開きは不可）。

```bash
# リポジトリのルートで GTFS を生成済みであること（build/gtfs/ が必要）
#   python -m fukuoka_gtfs.cli build
python demo/build_demo_data.py        # build/gtfs/ → demo/data/*.json, network.geojson

cd demo
python -m http.server 8000
# ブラウザで http://localhost:8000/ を開く
```

## データ再生成

ダイヤ改正でフィードを作り直したら、`python demo/build_demo_data.py` を再実行すれば
`demo/data/` が最新になります（駅・路線・色・時刻すべてフィードから自動取得）。

## 構成

```
demo/
  index.html          概要ハブ（路線図・統計・ツール連携）
  map.html            運行アニメーションマップ（deck.gl）
  board.html          発車標・時刻表ビューア
  style.css           共通スタイル（ダーク基調・3 路線カラー）
  build_demo_data.py  GTFS → デモ用 JSON/GeoJSON 変換
  data/
    network.json      路線・駅・色・統計
    animation.json    全便の経路と通過時刻
    departures.json   親駅×区分の発車時刻
    network.geojson   路線+駅（geojson.io / kepler.gl / QGIS 用）
  gtfs-to-html/       既製ツール GTFS-to-HTML で HTML 時刻表を生成する例（Issue #17）
    config.json       gtfs-to-html 設定（入力=dist の feed.zip、出力=html/）
    package.json      gtfs-to-html をローカル導入する定義（要 Node.js 20+）
    html/             生成済み HTML 時刻表（index + 路線別ページ）
```

## スクリーンショット撮影

`capture.py` で 3 画面を自動撮影できます（Playwright + Chromium）。

```bash
pip install playwright && python -m playwright install chromium
python demo/capture.py            # → demo/screenshots/{index,board,map}.png
```

`map.html` は `?t=0800`（開始時刻）・`?speed=120`・`?pause=1` を URL で指定できます。
deck.gl は `vendor/` に同梱済みなので、地図描画は CDN 非依存です。

> ヘッドレス環境で `libnss3` / `libnspr4` / `libasound2` が無く Chromium が起動しない場合
> （sudo 不可のとき）は、`apt-get download` で取得・展開し `LD_LIBRARY_PATH` を通せば動きます。

## 既製ツールで使う（C の詳細）

- **地図に重ねる**: `data/network.geojson` を [geojson.io](https://geojson.io) /
  [kepler.gl](https://kepler.gl) / QGIS にドラッグ。
- **公式検証**: `build/feed.zip` を [gtfs-validator.mobilitydata.org](https://gtfs-validator.mobilitydata.org/) にアップロード。
- **データカタログ**: [transit.land](https://www.transit.land/) などに登録可能な標準フィード。
- **経路検索**: OpenTripPlanner に `feed.zip` と福岡の OSM 抽出を読ませると、
  橋本→福岡空港などの経路検索デモになります。

## HTML 時刻表（GTFS-to-HTML）

[GTFS-to-HTML](https://gtfstohtml.com/) は GTFS から印刷にも向く HTML 時刻表を生成する
既製ツールです。本リポジトリの公開フィード（`dist/FukuokaCitySubway.zip`）を入力とする
設定と、**生成済みの成果物**を `gtfs-to-html/` に同梱しています。

```bash
# まずは同梱の成果物をそのまま開くだけでも閲覧できます
#   demo/gtfs-to-html/html/index.html

# 再生成する場合（Node.js 20+ が必要）
make demo-html            # = cd demo/gtfs-to-html && npm install && npm run build
```

詳細・設定の説明は [`gtfs-to-html/README.md`](gtfs-to-html/README.md) を参照してください。

## 技術メモ

- `map.html` の地図は **ベースマップタイル不要**（ダーク背景に路線と列車のみ描画）。
  deck.gl と Web フォントのみ CDN を使用するため、表示時にインターネット接続が必要です。
  データ（`demo/data/`）はすべてローカルです。
- 深夜便は GTFS 表記に合わせ `24:30` のように 24 時超で表示します。
