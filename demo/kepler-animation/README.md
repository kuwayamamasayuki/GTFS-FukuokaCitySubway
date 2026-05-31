# kepler.gl で運行アニメーションを作る例（Issue #18）

[kepler.gl](https://github.com/keplergl/kepler.gl)（**MIT License** / Uber・vis.gl）は、
ブラウザだけで動く既製の地理空間可視化ツールです。時刻つきの GeoJSON（Trip layer 形式）を
読み込ませると、スケジュールどおりに動く列車の**運行アニメーション**を再生できます。

このディレクトリには、本リポジトリが生成した GTFS-JP フィードを kepler.gl の Trip layer
用 GeoJSON に変換する変換器と、**生成済みの GeoJSON** を同梱しています。

> 既製ツールに頼らず**ブラウザ完結**で運行アニメーションを見たい場合は、本リポジトリ同梱の
> [`../map.html`](../README.md)（**deck.gl** 製・MIT・ベースマップ不要）がそのまま使えます。
> 本ディレクトリは「既製の可視化ツール（kepler.gl）に取り込む」例です。

## なぜ kepler.gl か

GTFS から運行アニメーションを作る既製ツールはいくつかありますが、
[transitland-processing-animation](https://github.com/transitland/transitland-processing-animation)
は明示的な LICENSE が無く、また廃止済みの Transitland API v1 に依存します。
kepler.gl は **MIT ライセンスが明確**で、廃止 API にも依存せず、ローカルの GeoJSON を
ドラッグ＆ドロップするだけで動く点が利点です。

## 成果物（同梱済み）

```
data/
  trips.geojson    指定日の全便を Trip layer 形式で表した GeoJSON
```

各 Feature は 1 便（trip）に対応する LineString で、座標は
``[経度, 緯度, 高度, 時刻(Unix epoch 秒)]`` の 4 要素です。kepler.gl はこの 4 要素目
（時刻）を検出して自動的に Trip layer を作り、時間アニメーションを再生します。
Feature の `properties` には `route_id` / `route_color`（路線色）/ `route_type` /
`trip_headsign` を含めています。深夜便（`24:30` など 24 時超）は翌日の時刻として
正しく扱います。

同梱データは `build/gtfs/`（運行開始日 2026-04-01 の平日ダイヤ）から生成したものです。

## 使い方（ブラウザ。GUI 操作）

1. [https://kepler.gl/demo](https://kepler.gl/demo) を開く（インストール不要）。
2. `data/trips.geojson` を地図にドラッグ＆ドロップする。
3. 時刻つき座標が検出され **Trip layer** が自動作成される。下部に時間スライダーが現れ、
   再生ボタンで列車がダイヤどおりに走るアニメーションが見られる。
4. レイヤ設定で色を `route_color`（路線色）に、太さや軌跡の残り時間（trail length）を
   調整すると見やすくなる。

> kepler.gl はクライアント側で完結し、ドロップしたデータは外部送信されません
> （[kepler.gl について](https://kepler.gl/)）。自前でホストしたい場合は MIT ライセンスの
> もとでソースを取得できます。

## 自分で再生成する

入力 GTFS を変えたい・ダイヤ改正を反映したい場合は変換器を再実行します
（追加の依存はなく、Python 標準ライブラリのみで動きます）。

```bash
# リポジトリのルートで GTFS を生成済みであること（build/gtfs/ が必要）
#   python -m fukuoka_gtfs.cli build
python demo/kepler-animation/gtfs_to_kepler.py \
    --gtfs build/gtfs --out demo/kepler-animation/data/trips.geojson
```

ルートからは `make demo-animation` でも同じことができます。

| オプション | 既定 | 意味 |
|---|---|---|
| `--gtfs` | `build/gtfs` | 入力 GTFS ディレクトリ |
| `--out` | `demo/kepler-animation/data/trips.geojson` | 出力 GeoJSON パス |
| `--date` | 自動選択 | 対象日 `YYYY-MM-DD`（省略時は運行開始日以降の最初の運行日） |

## 関連

- ブラウザ完結の自前アニメーション: [`../map.html`](../README.md)（deck.gl 製）。
- 同じ「既製ツール連携」の例: HTML 時刻表を作る [`../gtfs-to-html/`](../gtfs-to-html/README.md)（Issue #17）。
- `data/trips.geojson` は標準的な GeoJSON なので、[geojson.io](https://geojson.io) や
  QGIS でも開けます（時間アニメーションは kepler.gl が対応）。
