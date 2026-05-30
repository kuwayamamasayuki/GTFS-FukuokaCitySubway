# TransitFlow で運行アニメーションを作る例（Issue #18）

[transitland-processing-animation（TransitFlow）](https://github.com/transitland/transitland-processing-animation)
は、一日の運行スケジュールを地図上で動く点として可視化する
[Processing](https://processing.org/) 製のアニメーションツールです
（[作例（San Francisco など）](https://vimeopro.com/willgeary/transit-flows)）。

本ディレクトリは、本リポジトリが生成した GTFS-JP フィードから福岡市地下鉄の
運行アニメーションを作るための **入力データ**と**変換器**、および手順をまとめたものです。

## なぜ変換器が必要か

TransitFlow 本家は Mapzen 期の **Transitland API v1**（`schedule_stop_pairs` 等）から
データを取得しますが、この API は既に廃止されています。そのため本家の
`transitflow.py` をそのまま実行してもスケジュールを取得できません。

そこで本ディレクトリの `gtfs_to_transitflow.py` が、**ローカル GTFS を直接読み込み**、
TransitFlow の Processing スケッチがそのまま読める入力（`output.csv` と
`vehicle_counts/*.csv`）を生成します。これにより廃止 API に依存せず、
本リポジトリの公開フィードから福岡市地下鉄のアニメーションを作れます。

## 成果物（同梱済み）

```
data/
  output.csv                       全便を駅間セグメントに分解した運行データ
  vehicle_counts/
    vehicles_3600.csv              各フレームの走行中車両数（全車種合計）
    metros_3600.csv                同（地下鉄）。他に buses/trams/... も生成（本フィードでは 0）
```

`output.csv` の各行は「ある列車がある駅から次の駅へ走る 1 区間」を表し、列は
`start_time, start_lat, start_lon, end_time, end_lat, end_lon, duration, route_type, bearing`
です。Processing スケッチがこの始終点と時刻から、列車の位置を毎フレーム補間して描画します。
深夜便（`24:30` など 24 時超）は翌日の日時（例: `00:30`）として正しく扱います。

同梱データは `build/gtfs/`（運行開始日 2026-04-01 の平日ダイヤ、3600 フレーム）から
生成したものです。

## 自分で再生成する

入力 GTFS を変えたい・ダイヤ改正を反映したい場合は変換器を再実行します
（追加の依存はなく、Python 標準ライブラリのみで動きます）。

```bash
# リポジトリのルートで GTFS を生成済みであること（build/gtfs/ が必要）
#   python -m fukuoka_gtfs.cli build
python demo/transitland-animation/gtfs_to_transitflow.py \
    --gtfs build/gtfs --out demo/transitland-animation
```

ルートからは `make demo-animation` でも同じことができます。

主なオプション:

| オプション | 既定 | 意味 |
|---|---|---|
| `--gtfs` | `build/gtfs` | 入力 GTFS ディレクトリ |
| `--out` | （必須） | 出力先（`<out>/data/` に書き出す） |
| `--date` | 自動選択 | 対象日 `YYYY-MM-DD`（省略時は運行開始日以降の最初の運行日） |
| `--frames` | `3600` | 総フレーム数（3600 ≒ 60 秒のアニメーション） |
| `--template` | なし | 本家 `template.pde` のパス。指定時のみ `sketch.pde` を生成 |
| `--recording` | off | `sketch.pde` を mp4 録画モードで生成 |

## アニメーションを描画する（Processing。GUI 操作が必要）

実際の描画は Processing アプリ上で行います（ヘッドレス不可）。

1. **Processing と Unfolding Maps を準備**
   本家 README の「Install Processing」に従い、[Processing 3](https://processing.org/) と
   [Unfolding Maps 0.9.9（Processing 3 用）](http://unfoldingmaps.org/) を導入し、
   Video Export ライブラリを追加します。

2. **本家リポジトリを取得**（スケッチ本体・アイコン・フォント等の素材のため）
   ```bash
   git clone https://github.com/transitland/transitland-processing-animation.git
   ```
   本家のスケッチ素材一式（`clock_icon.png` 等）は本リポジトリには同梱しません。

3. **本リポジトリのデータを差し込む**
   生成した `data/`（`output.csv` と `vehicle_counts/`）を、本家の
   `sketches/fukuoka/2026-04-01/data/` に配置します。

4. **`sketch.pde` を用意する**
   本家 `transitflow/templates/template.pde` を `--template` に渡すと、中心座標
   （福岡市地下鉄の緯度経度から算出）と総フレーム数を差し込んだ `sketch.pde` を
   `<out>/sketch/sketch.pde` に生成できます。
   ```bash
   python demo/transitland-animation/gtfs_to_transitflow.py \
       --gtfs build/gtfs --out demo/transitland-animation \
       --template /path/to/transitland-processing-animation/transitflow/templates/template.pde
   ```

5. **Processing で開いて再生**
   `sketch.pde` を Processing で開き、Play（`Cmd/Ctrl + R`）で再生します。
   mp4 として書き出すには `--recording` を付けて生成したスケッチを使います。

> 本家スケッチは地下鉄を赤（`route_type=metro`）で描画します。福岡市地下鉄の
> 3 路線はいずれも `route_type=1`（地下鉄）なので、すべて地下鉄の色で表示されます。

## 関連

- 同じ「既製ツール連携」の例として、HTML 時刻表を生成する
  [`../gtfs-to-html/`](../gtfs-to-html/README.md)（Issue #17）があります。
- 本リポジトリ内蔵の運行アニメーション（deck.gl 製・ブラウザ完結）は
  [`../map.html`](../README.md) を参照してください。
