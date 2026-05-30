# 運賃確認テストの設計 (Issue #10)

- **Issue**: [#10 料金の確認テスト](https://github.com/kuwayamamasayuki/GTFS-FukuokaCitySubway/issues/10)
- **日付**: 2026-05-30
- **目的**: 生成された GTFS の全駅ペアの運賃を、ジョルダンの福岡市地下鉄
  発着・料金検索（`https://fukuoka-city-subway.jorudan.biz/pc/route`）が示す普通料金と
  突合し、運賃テーブル（`fare_attributes.txt` / `fare_rules.txt`）の誤りを検出するテストを作る。

## 背景

福岡市地下鉄は 36 駅。全駅ペアは 36×35/2 = **630 ペア**。GTFS では運賃は

- `fare_attributes.txt`: `fare_id` → `price`（210/260/300/340/360/380 円の 6 区）
- `fare_rules.txt`: `(origin_id, destination_id)` → `fare_id`（`origin_id`/`destination_id` は親駅 `stop_id` = 1..36）

で表現される。これと独立な外部の権威ある運賃源（ジョルダン）を突き合わせる。

### ジョルダン料金検索の仕組み（調査結果）

`/pc/route` は JS 駆動の SPA で、出発・到着駅を選んで「検索」すると
`/pc/nsresult` へ遷移し、結果ページに **普通料金** が表示される。結果ページは
次の GET で直接取得できる（UI 操作不要）:

```
https://fukuoka-city-subway.jorudan.biz/pc/nsresult?mode=0&skbn=1
  &fr=<出発駅名>&frkbn=4&frsk=R&to=<到着駅名>&tokbn=4&tosk=R&dt=YYYYMMDDHHMM&p=1
```

結果 HTML 中に `普通料金 &nbsp;210&nbsp; 円` の形で普通料金が現れる。駅名は
GTFS の `stop_name` と一致する（例: 天神, 博多, 福岡空港, 橋本, 天神南, 櫛田神社前）。

料金検索のトップ(`/pc/route`)は JS 駆動の SPA だが、**検索結果ページ(`/pc/nsresult`)は
サーバ描画**で、上記 URL を直接 GET すれば（cookie・referer 無しでも）普通料金を含む
HTML が返る。したがって **ブラウザは不要**で、取得は既存依存の `requests` だけで行える。

## 方式

- **記録済みフィクスチャ方式**（Issue #5 の時刻表突合と同じ哲学）。ジョルダンの
  全 630 ペアの普通料金を一度だけ取得し、`tests/fixtures/jorudan_fares.json` に
  保存する。**テストはネットワークに依存せず**、毎回同じ結果になり CI でも安定・高速。
- **新規依存は追加しない**。取得は既存の `requests`、解析は標準ライブラリ（`re`）、
  設定は既存の `PyYAML`。
- フィクスチャの更新（運賃改定時）は保守者が取得スクリプトを手動実行して行う。

## コンポーネント

### 1. `src/fukuoka_gtfs/verify/jorudan_fare.py`（純粋・ネットワーク非依存）

- `parse_fare(html: str) -> int | None`
  結果 HTML から普通料金（円）を 1 つ抽出する。`普通料金 ... 円` を正規表現で拾い、
  桁区切りカンマと `&nbsp;`・タグ・空白を吸収する。見つからなければ `None`。

### 2. `src/fukuoka_gtfs/verify/fare_check.py`（純粋）

- `gtfs_fares(attr_rows, rule_rows) -> dict[frozenset[str], int]`
  `fare_attributes` と `fare_rules` から `{frozenset(origin_id, destination_id): price}` を作る。
- `FareDiff` / `compare(gtfs, jorudan, *, allow=()) -> FareDiff`
  両辞書を突合し、`allow`（許容する `(id, id)` ペア集合）を差し引いた不一致のみ返す。

### 3. `scripts/fetch_jorudan_fares.py`（requests・取得専用）

- `reference_gtfs/stops.txt` の親駅（location_type=1）36 駅から駅名↔stop_id を得る。
- 全 630 ペアについて `/pc/nsresult` を GET し、`parse_fare` で普通料金を抽出。
- `tests/fixtures/jorudan_fares.json` を `{"<o>-<d>": price, ...}`（o<d の stop_id）で出力。
- 代表 1 ペアの生 HTML を `tests/fixtures/jorudan/fare_sample.html` に保存（パーサ単体テスト用）。
- `--limit N` で先頭 N ペアのみ取得（デバッグ用）。

### 4. テスト（すべてオフライン）

- `tests/test_jorudan_fare.py`: `parse_fare` の単体テスト。保存済みサンプル HTML と
  合成スニペット（カンマ区切り・タグ混在・運賃なし）で検証。
- `tests/test_fare_check.py`: `gtfs_fares` / `compare` の単体テスト（小さな合成データ）。
- `tests/test_jorudan_fares_match.py`: `jorudan_fares.json` フィクスチャと
  `reference_gtfs/` の運賃を全 630 ペアで突合し、`compare` の結果が空（許容リスト適用後）で
  あることを表明する統合テスト。

### 5. 設定・許容リスト

- `config/jorudan_fare_verify.yaml`: 取得日時（`dt`）の既定値と、既知の運賃相違を
  許容する `allow`（`["<o>-<d>", ...]`）。原則 0 件。ジョルダンと GTFS が真に食い違う
  場合のみ、根拠コメント付きで登録する（実データの誤りは隠さない）。

### 6. Makefile / ドキュメント

- `fetch-jorudan-fares` ターゲット: 取得スクリプトを実行してフィクスチャを更新。
- `README` の検証セクションに、ジョルダン運賃突合テストと更新手順、Playwright 任意依存を追記。

## スコープ外（YAGNI）

- IC 運賃・小児運賃・定期運賃の突合（GTFS は普通料金のみ表現）。
- ライブ取得をテスト実行時に行うこと（脆く遅いので採らない）。
