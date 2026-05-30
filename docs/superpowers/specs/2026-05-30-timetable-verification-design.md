# 時刻表確認テストの設計 (Issue #5)

- **Issue**: [#5 時刻表の確認テストの作成](https://github.com/kuwayamamasayuki/GTFS-FukuokaCitySubway/issues/5)
- **日付**: 2026-05-30
- **目的**: 生成された GTFS の全駅・全方面・全曜日区分の時刻表を、外部の権威ある時刻表
  （ジョルダンの福岡市地下鉄ダイヤ詳細ページ）と突合し、発車時刻・行先の不一致を検出するテストを作る。

## 背景

福岡市交通局の時刻表索引ページ
`https://subway.city.fukuoka.lg.jp/schedule/index.php`
には、ジョルダンのダイヤ詳細ページ
`https://fukuoka-city-subway.jorudan.biz/pc/diagramdtl?...`
への 140 本のリンクが埋め込まれており、全駅×両方面を網羅している（同一の駅×方面が
平日用・別曜日用の 2 つの `dt` で重複するため、実質 70 の駅×方面）。
このリンク集合をスクレイプすれば、全ダイヤの URL を自動列挙できる。

ダイヤ詳細ページは `dt`（日時）パラメータの曜日種別 1 つ分の時刻表のみを表示する。
平日／土曜／休日を得るには、それぞれの曜日区分に該当する日付を `dt` に与えて 3 回取得する。

## 方式

- **記録済みゴールデン HTML 方式**。ジョルダンの各ページを一度だけ取得し、整形した HTML を
  `tests/fixtures/jorudan/` に保存する。テストはネットワークに依存せず、毎回同じ結果になる。
- 新規依存は追加しない。解析は標準ライブラリ（`re` / `html.parser`）、取得は既存の `requests`、
  設定は既存の `PyYAML` を用いる。

## ジョルダン HTML の構造（解析仕様）

時刻表本体は `<ul class="ttArea pc">`（PC 用）。構造:

```
<ul class="ttArea pc">
  <li class="pc"><dl class="ttBox ttBoxHeader"><dt class="ttToggle"></dt><dd>1,2番ホームから</dd><dd>3番ホームから</dd></dl></li>
  <li class="pc"><dl class="ttBox">
     <dt class="ttToggle"><span>5</span></dt>          ← 時（hour）
     <dd><ul class="ttList">
        <li class="tooltip linindexlink">
           <span class="legend"> <font color="#FF0000">貝</font> </span>  ← 行先記号（空=既定行先）
           <a href="javascript:void(0);">30</a>                          ← 分（minute）
           <input type="hidden" value="464507;;30" class="lineindex" />  ← 便ID;;分
        </li> ...
     </ul></dd>
     <dd>...</dd>   ← ホーム列が複数（方面単位で統合する）
  </dl></li>
  ...
</ul>
```

- ヘッダ行（`ttBox ttBoxHeader`）は読み飛ばす。
- `dt.ttToggle > span` が「時」。各 `dd` がホーム列。`ttList > li.linindexlink` が 1 便。
- 「分」は `li` 内の `<a>` テキスト。「行先記号」は `span.legend` 内のテキスト
  （`&nbsp;` のみ＝記号なし＝既定行先）。
- 記号→行先の対応は、ページ内の凡例から解析する。例（空港線・福岡空港方面）:
  無印＝福岡空港ゆき、`貝`＝貝塚ゆき、`●`＝福岡空港ゆき（中洲川端乗換）、`▲`＝福岡空港ゆき（西新乗換）。
  比較に用いる「行先」は最終到達駅とする（`●`/`▲`/無印はいずれも福岡空港）。

## コンポーネント

### 1. `src/fukuoka_gtfs/verify/jorudan_parser.py`
- `parse_diagram(html: str) -> JorudanTimetable`
- 整形 HTML（または生 HTML）から発車便を抽出。返り値は
  `Departure(hour: int, minute: int, marker: str, destination: str)` のリスト。
  ホーム列はすべて統合する。`destination` は凡例の記号→行先対応で解決した最終行先。
- 凡例パース `parse_legend(html) -> dict[str, str]`（記号→行先、無印は既定行先）。

### 2. `src/fukuoka_gtfs/verify/gtfs_timetable.py`
- `load_feed(gtfs_dir: Path) -> Feed`（stops/routes/trips/stop_times/calendar/calendar_dates を読む。既存 `gtfsio.read_csv` を利用）。
- `departures(feed, *, stop_name, route_id, direction_id, service_id) -> list[Departure]`
  指定駅（親駅名→子ホーム stop_id 群）・路線・方面・サービスの発車時刻を抽出し、
  `trip_headsign` を行先とする。
- 深夜時刻の正規化: GTFS の `24:mm`/`25:mm` は `hour % 24` で 0/1 時に丸めてから比較する。

### 3. `src/fukuoka_gtfs/verify/comparator.py`
- `compare(jorudan: list[Departure], gtfs: list[Departure]) -> ComparisonResult`
- `(hour, minute, destination)` の集合として厳密比較。
  `missing`（ジョルダンにあり GTFS にない）・`extra`（GTFS にありジョルダンにない）を返す。
- **時刻も行先も厳密一致**を合否基準とする。

### 4. `config/jorudan_verify.yaml`（取得・突合のマッピング）
- ジョルダン `fr`（駅名）→ GTFS 親駅 `stop_name`（例: `藤崎（福岡）`→`藤崎` の正規化表）。
- ジョルダンの終端駅（`dgm` の terminal、例 福岡空港／西唐津／貝塚／博多／橋本）→ GTFS
  `route_id` と `direction_id` の対応（例: 福岡空港・貝塚=空港箱崎 dir 0／西唐津・筑前前原・姪浜=dir 1）。
- 曜日区分（平日／土曜／休日）→ 各路線グループの `service_id`。
- 取得用の代表日（平日・土曜・休日それぞれの `dt` 日付）。

### 5. `scripts/fetch_jorudan_fixtures.py`（fixture 生成・手動実行）
- 福岡市索引ページを取得→ `diagramdtl` リンクを列挙→駅×方面ごとに重複排除。
- 各リンクの `dt` を平日／土曜／休日の代表日に差し替えて 3 回取得。
- `<ul class="ttArea pc">` と凡例ブロックのみを抜き出して整形 HTML として保存:
  `tests/fixtures/jorudan/<route>/<station>_<direction>_<daytype>.html`。
- あわせて `tests/fixtures/jorudan/index.json`（駅・方面・曜日・対応する GTFS キーの一覧）を生成。

### 6. テスト
- `tests/test_jorudan_parser.py` — 代表 fixture を解析し、時・分・行先・件数を検証（単体）。
  記号→行先、深夜 0/1 時、複数ホーム統合のケースを含む。
- `tests/test_comparator.py` — 合成データで `compare` の missing/extra/一致を検証（単体）。
- `tests/test_gtfs_timetable.py` — 小さな合成 GTFS で `departures` 抽出と深夜正規化を検証（単体）。
- `tests/test_timetable_comparison.py` — `index.json` をパラメータ化し、`build/gtfs` の生成済み
  GTFS と各 fixture を突合（Issue 本体の確認テスト）。
  - `build/gtfs` か fixtures が無い場合は `pytest.skip`（生成物に依存するため）。

## データフロー

```
索引ページ ──fetch script──▶ tests/fixtures/jorudan/*.html + index.json   （一度だけ／手動）
                                          │
build/gtfs/*.txt ─load_feed─▶ gtfs Departures ┐
tests/fixtures/jorudan/*.html ─parse_diagram─▶ jorudan Departures ┘─ compare ─▶ 合否（厳密一致）
```

## エッジケースと注意点

- **深夜時刻**: GTFS は `24:mm`/`25:mm`、ジョルダンは 0/1 時表示。比較前に GTFS 側を `% 24` で正規化。
- **駅名正規化**: `藤崎（福岡）`→`藤崎`、全角括弧等。マッピング表で吸収。
- **直通・乗換記号**: `●`/`▲` は乗換案内であって行先は終端（福岡空港）。凡例の記号→行先で最終行先に解決。
- **共用駅**: 中洲川端（空港線/箱崎線）・博多（空港線/七隈線）は路線ごとに別ページ・別 fixture。
- **方面に複数行先が混在**: 空港線福岡空港方面には福岡空港ゆきと貝塚ゆきが混在。GTFS では
  同一 `direction_id` の別 `trip_headsign` として現れるため、行先込みで突合すれば整合する。
- **ダイヤ改正時の運用**: Excel 更新で GTFS を再生成したら、`scripts/fetch_jorudan_fixtures.py` を
  再実行して fixture を更新する。手順は README に追記。

## 不採用案

- **ライブ突合（テスト実行時にジョルダンへアクセス）**: 低速・不安定で CI 不適。→ 不採用。
- **解析済み JSON をゴールデンに**: 実 HTML マークアップに対するパーサ検証ができない。→ 整形 HTML を採用。

## fixture の取得運用

- **本 PR**: ユーザー承認のもと、実装者（Claude）が `scripts/fetch_jorudan_fixtures.py` 相当の
  処理でジョルダンの全ページを一度だけ取得し、整形 fixture と `index.json` を PR に同梱する。
  これにより全単体テストはネットワーク無しで完結する。
- **将来のダイヤ改正時**: ユーザー環境で `! python scripts/fetch_jorudan_fixtures.py` を実行して
  fixture を更新する（手順は README に追記）。

## テストで人手確認が必要な点

- 自動単体テストはすべてネットワーク無しで完結するため、追加の人手確認は不要。
- `scripts/fetch_jorudan_fixtures.py` のライブ取得が将来も正しく動くこと（サイト構造変化の検知）は、
  ダイヤ改正時の fixture 再取得の中で確認される。

## 実装結果と設計変更（2026-05-30）

実装中に、当初設計の前提と異なる以下のデータ実態が判明したため設計を更新した。

### 1. 行先は「厳密一致」できない → 時刻のみで判定（行先は参考）

ジョルダンは地下鉄の枠で行先を表示し、JR 筑肥線直通便を多くの駅で「姪浜ゆき」と表示する一方、
GTFS は実際の直通先（筑前前原・西唐津 等）を `trip_headsign` に持つ。この語彙体系の差は構造的で、
全 207 ページの突合で `姪浜→筑前前原` 1090 件、`福岡空港→博多` 27 件などの行先差が生じた。
よって **合否判定は発車時刻（時:分）の集合一致**とし、行先は判定に用いない（`comparator` は廃し
`verify/timetable_check.py` に集約）。凡例の解析は行先の参考情報として残す:
無印＝既定行先、素の駅名記号＝上書き、注記記号（●印/前●印 等）＝既定のまま、
七隈線（凡例 dd 無し）＝(路線,方面) の終端（`config` の `line_defaults`）。

### 2. 終着の到着を発車から除外（直通便は残す）

GTFS は各 trip の終着駅にも `departure_time` を持つが、発車時刻表には載らない。
そこで `gtfs_timetable.departures` は **「最終停車 かつ 行先＝当駅名」** の停車を除外する。
行先が当駅と異なる便（フィード境界の先へ継続する JR 直通等）は最終停車でも発車として残す。

### 3. 既知差分の許容リスト（回帰検知）

`build/gtfs` とジョルダン fixture の現存差分を `tests/fixtures/jorudan/expected_diffs.json`
（`scripts/gen_expected_diffs.py` で生成）に記録し、それを差し引いた**新規差分のみ失敗**とする。
既知差分（2026-05 時点）:
  * **境界/接続駅 6 ページ**: 姪浜 dir1（×3）と中洲川端 dir0（×3）。JR 直通・箱崎⇄空港直通の
    GTFS 表現（block 分割・境界終着）とジョルダンの単一駅発車表示の差。
  * 残り 201 ページは時刻が完全一致。

> **解消済み（Issue #7）**: かつて七隈線 44 ページ・計 60 便で「正確に 1 分差」があった。
> 原因は七隈線 `.xlsx` が一部の深夜便を実秒付き（例 `00:31:42`）で持ち、`normalize_sequence`
> が分へ**四捨五入**していたため、秒 ≥30 の便が +1 分繰り上がっていた（空港・箱崎線は
> `.xls` の serial で秒=0 のため無影響）。公式公開時刻に倣い**秒切り捨て**へ修正して解消。

### 4. GTFS スナップショットは同梱しない

trips/stop_times/calendar は毎回 Excel から生成する設計に合わせ、突合テストは `build/gtfs` を
読み、無ければ skip する（`FUKUOKA_GTFS_DIR` で上書き可）。

### 5. カバレッジの限界

公式索引が `天神南→博多`（七隈線 dir0）のページを提供しないため、当該方面のみ突合対象外。
それ以外の全駅×全方面×全曜日区分（69 駅×方面 × 3 = 207 ページ）を網羅する。

### モジュール構成（最終）

`verify/jorudan_parser.py`（HTML 解析）, `verify/gtfs_timetable.py`（GTFS 抽出）,
`verify/mapping.py`（対応付け）, `verify/timetable_check.py`（時刻突合＋許容リスト）。
スクリプト: `scripts/fetch_jorudan_fixtures.py`（fixture 取得）,
`scripts/gen_expected_diffs.py`（許容リスト生成）。
テスト: `tests/test_jorudan_parser.py` / `test_jorudan_mapping.py` / `test_gtfs_timetable.py` /
`test_timetable_check.py`（単体）, `tests/test_timetable_comparison.py`（Issue 本体）。
