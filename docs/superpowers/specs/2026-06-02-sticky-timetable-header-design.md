# GTFS-to-HTML 時刻表の駅名ヘッダ行を固定（Issue #38）

## 背景

Issue #35（PR #36）で空港線・箱崎線を 1 つの時刻表に統合した。生成された HTML 時刻表は
gtfs-to-html の vertical orientation で出力され、実際の DOM 構造は次の通り:

- **列 = 駅**（`thead` の `th.stop-header`、約 19 駅）+ 左端に便ラベル列（`trip-notes` / `run-footer`）
- **行 = 便**（`tbody` の `tr.trip-row`、383 便 ＝ 縦に非常に長い）
- `.table-container` が `overflow-x: scroll`、横スクロールバーは表の最下部に 1 本だけ

Issue 本文は「駅＝行／便＝列で列数が数百」と記述していたが、実際は逆（駅＝列／便＝行）。
383 行を縦スクロールすると駅名ヘッダ（`thead`）が画面外へ流れ、「どの列がどの駅か」を
見失うのが主要な操作性問題。ユーザー確認の結果、本 Issue では **駅名ヘッダ行の固定**を
全時刻表ページに対して実装する（左列固定・上部スクロールバーは今回スコープ外）。

## 目的

生成済み HTML 時刻表で、縦スクロール時も駅名ヘッダ行が常に見えるようにする。

## 技術的制約

単に `thead { position: sticky; top: 0 }` を入れても効かない。既存 CSS の
`.table-container { overflow-x: scroll }` によりこのコンテナがスクロール包含ブロックになるが、
コンテナ自体は縦スクロールしない（高さ = 内容）ため、ページ縦スクロール時に sticky が
固定対象を持たない（sticky + overflow 祖先の既知の落とし穴）。

## 解決策（標準パターン）

`.table-container` を高さ上限付きのスクロールボックス化し、その中で `thead` を sticky にする。

```css
/* Issue #38: 駅名ヘッダ行を固定（383 行を縦スクロールしても駅名が見える） */
.timetable-page .timetable .table-container {
  max-height: 80vh;   /* 表を高さ上限付きスクロール領域に */
  overflow: auto;     /* 縦横両方向スクロール（横バーも維持） */
}
.timetable-page .timetable .table-container thead th {
  position: sticky;
  top: 0;
  z-index: 2;
}
```

- 詳細度は既存 `.timetable-page .timetable .table-container`（0,3,0）と同等で、注入位置が
  リンク済み `<link rel="stylesheet">` より後（`</head>` 直前）になるため後勝ちで上書きする。
- 印刷用 `@media print` 内の `overflow` 指定（line 748/768）は screen には影響しない。

## 実装方式（`inject_backlink.py` と同方式 / 冪等）

新規スクリプト `demo/gtfs-to-html/inject_sticky_header.py`:

- `html/**/*.html` を走査
- `<head>` を持ち、かつ時刻表テーブル（`table-container`）を含むページのみ対象
  （= 概要ページ index.html 等は自然に除外）
- マーカー `id="issue38-sticky-header"` で冪等（既に注入済みならスキップ）
- `</head>` 直前に `<style id="issue38-sticky-header">…</style>` を注入
- 注入件数を表示

再生成手順（README に追記）:

```
cd demo/gtfs-to-html
npx gtfs-to-html
python3 inject_backlink.py
python3 inject_sticky_header.py
```

## テスト（`tests/test_demo_sticky_header.py`）

外部 Node ツールを用いるため、注入処理のロジックと同梱成果物のリグレッションを守る:

1. 注入後、時刻表ページにマーカー `id="issue38-sticky-header"` と `position: sticky` が存在
2. 冪等性: 2 回実行してもマーカーは 1 つだけ
3. 概要ページ（テーブルを含まない HTML）には注入されない
4. 同梱の生成 HTML 成果物（`html/timetables/*.html`）にマーカーが含まれる

実際の見た目は Node.js 20+ での再生成と画面目視で確認（手動）。

## スコープ外（今回見送り）

- 左端の便ラベル列の固定
- 上部の同期横スクロールバー
- ヘッダ行以外の固定

## 関連

- Issue #38 / Issue #35 / PR #36
