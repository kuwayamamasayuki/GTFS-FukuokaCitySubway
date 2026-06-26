# 地上出入口モデル（stops.txt の location_type=2）— Issue #50

## 背景と目的

`stops.txt` には従来、駅（`location_type=1`）とホーム（`location_type=0`）しか無かった。
地下鉄は地上出入口が多数あり、出入口を `location_type=2` / `parent_station=駅` の stop として
追加すると、経路検索エンジンが「最寄り出入口 ↔ 目的地」の徒歩を含めて案内でき、
ドアtoドアの正確な経路案内ができる（`pathways.txt` と組み合わせると効果大）。

## データの出典（実測値）

出入口データ（名称・緯度経度・親駅・`wheelchair_boarding`）は、**ユーザー本人が過去に
各駅・各ホーム・各出入口の緯度経度を実測登録した旧フィード**から採録した実測値である。

- 出典コミット: git `0e19136`「各駅の各ホーム，各出入口の緯度・経度を登録しました」（2018年版）。
- 採録ファイル: `scripts/data/legacy_entrances.csv`（現行 `stops.txt` と同じ列構成）。
- 件数: **205 出入口** = 旧フィードの**全 35 駅（`parent_station` 1〜35）198 件**に、
  後から **櫛田神社前（id 36）の実測 7 件**を追記したもの。

> 公式サイト・公式オープンデータは出入口の緯度経度を公表していない（駅ページは駅立体図
> 画像と Google マップリンクのみ）。本人実測の旧フィードが唯一の信頼できる座標源のため、
> これを一次採用した。

## データモデル

| 列 | 値 |
|---|---|
| `stop_id` | 旧フィードの ID をそのまま使用（例 `1_Nex`=姪浜北、`11_W1ex`=博多西1、`13_2ex`=福岡空港2） |
| `stop_name` | 旧フィードの出入口名（例 `姪浜北出入口`, `博多西1番出入口`, `福岡空港1A番出入口`） |
| `stop_lat` / `stop_lon` | 旧フィードの実測座標 |
| `zone_id` / `stop_url` | 空 |
| `location_type` | `2` |
| `parent_station` | 親駅（`location_type=1`）の `stop_id` |
| `wheelchair_boarding` | 旧フィードの値（1 または 2）。ただし下記の補正対象を除く |

`legacy_entrances.csv` は 2018 年版フィードのスナップショットを**そのまま**保持する（不変条件）。
当時の値を現況に合わせて補正したい場合は、CSV を書き換えず `transform_stops` で明示的に上書きする
（`stop_name` の英語訳 `EN_OVERRIDES` と同じ流儀）。これにより「原データ」と「公開向け補正」を分離し、
補正の意図と根拠を追跡できる。

- `wheelchair_boarding` の補正: `WHEELCHAIR_BOARDING_OVERRIDES`（`stop_id` → 値）。
  - 薬院大通2番出入口（`32_2ex`）: 2018 年版は `2`（非対応）だが、実際は1番出入口だけでなく
    2番出入口も車椅子対応のため `1` に補正（Issue #66）。
  - 櫛田神社前1番出入口（`36_1ex`）: 採録元は `2`（非対応）だが、実際は6番出入口だけでなく
    1番出入口も車椅子対応のため `1` に補正（Issue #67）。
  - 中洲川端4番/6番/7番出入口（`9_4ex` / `9_6ex` / `9_7ex`）: 採録元は `2`（非対応）だが、
    実際は車椅子対応のため `1` に補正（Issue #63）。

実装は `scripts/seed_reference.py`:
- `LEGACY_ENTRANCES_CSV` / `load_legacy_entrances()` が `scripts/data/legacy_entrances.csv` を読む。
- `transform_stops` 末尾で各出入口行を**冪等**に追加（既存 `stop_id` があればスキップ。
  列は現行 `stops.txt` のヘッダに合わせて補完）。その後 `WHEELCHAIR_BOARDING_OVERRIDES` を
  適用する（出力を再投入しても結果は同じ＝冪等）。
- `reference_gtfs/stops.txt` が真実のソース。`make build` / `make publish` で `dist/stops.txt` と
  `dist/FukuokaCitySubway.zip` に反映される。

## 新駅の扱い

2023 年開業の新駅は旧フィード（2018年版）には存在しなかった。

- **櫛田神社前（id 36）**: 実測 7 出入口（`36_1ex`〜`36_7ex`）を後から
  `scripts/data/legacy_entrances.csv` に追記済み。
- **七隈線博多（id 37）**: 現状**未収録**。博多複合駅の出入口は旧フィードでは当時の
  **id 11（博多）配下**にまとまっており、本実装でも 11 配下に入る。

新駅の出入口を追加する場合は、実測座標を `scripts/data/legacy_entrances.csv` に
追記すればよい（`parent_station` に駅 id を指定）。

## スコープ外

- 出入口名の多言語訳（`translations.txt`）。駅名（`stops.stop_name`）の訳は既存のままで、
  出入口名そのものの訳は今回追加しない。
- `pathways.txt`（出入口↔ホームの通路・所要時間）。別 Issue。
