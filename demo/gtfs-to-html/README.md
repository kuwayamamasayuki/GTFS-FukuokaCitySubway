# GTFS-to-HTML で時刻表を作る例

[GTFS-to-HTML](https://gtfstohtml.com/) を使い、本リポジトリが生成した GTFS-JP
フィード（`dist/FukuokaCitySubway.zip`）から、人間が読める **HTML 時刻表**を生成する例です。

生成済みの成果物を `html/` に同梱しているので、まずはそのまま
`html/index.html` をブラウザで開けば閲覧できます（再生成は任意）。

## 成果物（同梱済み）

```
html/
  index.html                  概要ページ（路線一覧へのリンク）
  timetables/
    空港線・箱崎線.html         空港線＋箱崎線を 1 つにまとめた時刻表（平日/土曜/休日 × 上下）
    七隈線.html                七隈線の時刻表
  css/  js/                    GTFS-to-HTML 同梱のスタイル・スクリプト
```

## 空港線と箱崎線を 1 つの時刻表に（Issue #35）

空港線↔箱崎線は中洲川端で相互に直通運転しています。これを 1 つの時刻表として
見せるため、GTFS-to-HTML の追加ファイル [`timetables.txt`](https://gtfstohtml.com/docs/timetables)
／`timetable_pages.txt` を用意しています。

- **`show_trip_continuation=1`** … 直通便を `trips.txt` の `block_id` でたどり、
  「○○行きへ直通（Continues as …）」として連続表示します。
- **複数 route の統合** … 同じ `timetable_id` に空港線・箱崎線の 2 行を持たせ、
  両路線の便を 1 つの表へまとめています（七隈線は単独の時刻表）。

> `show_trip_continuation` は `config.json` ではなく **入力 GTFS 内の
> `timetables.txt` の列**です。このファイルを置くと自動生成は無効になり、
> 生成する時刻表（路線・方向・曜日）をすべて `timetables.txt` で定義します。

`timetables.txt` は入力 GTFS データセットに同梱して読ませる必要があります。
公開スナップショット `dist/FukuokaCitySubway.zip` は標準 GTFS のまま保ちたいので、
`prepare_feed.py` が「dist の中身＋このデモの追加ファイル」を結合した作業用フォルダ
`feed/` を作り、`config.json` はそれを入力に使います（`feed/` は再生成のたびに
作り直すため Git 管理外）。

## 自分で再生成する

[Node.js](https://nodejs.org/) **20 以上**が必要です（GTFS-to-HTML 2.12 の要件）。

```bash
cd demo/gtfs-to-html
npm install        # gtfs-to-html をローカル(node_modules/)へ導入
npm run build      # prebuild(prepare_feed.py) で feed/ を組み立て → config.json に従い html/ を生成
python3 inject_backlink.py   # 各ページ先頭に「デモTOPへ戻る」リンクを注入
```

> `npm run build` は npm の `prebuild` フックで自動的に `python3 prepare_feed.py`
> を実行し、`dist/FukuokaCitySubway.zip` ＋ `timetables.txt` ／ `timetable_pages.txt`
> を結合した `feed/` を用意してから時刻表を生成します。

> GTFS-to-HTML には戻りリンクのオプションが無いため、生成後に
> `inject_backlink.py` を実行して `../../index.html`（デモTOP）への導線を注入します。
> 冪等なので再生成のたびに流せば導線を復元できます。

リポジトリのルートからは `make demo-html` でも同じことができます。

> インストール時に Puppeteer が Chrome のダウンロードに失敗する環境では、
> `PUPPETEER_SKIP_DOWNLOAD=true npm install` としてください
> （HTML 時刻表の生成には Chrome は不要です）。

最新ダイヤを反映したい場合は、先にルートで GTFS を作り直して `dist/` を更新してください。

```bash
python -m fukuoka_gtfs.cli build && make publish   # dist/ を最新化
```

## 設定（`config.json`）

| キー | 値 | 意味 |
|---|---|---|
| `agencies[].path` | `feed` | 入力 GTFS（`prepare_feed.py` が dist＋追加ファイルから組み立てる作業用フォルダ） |
| `outputPath` | `html` | 出力先フォルダ |
| `useParentStation` | `true` | 子ホーム（`13_1` 等）を親駅にまとめる |
| `showMap` | `false` | 地図埋め込みを省略（地図タイル用トークン不要） |
| `menuType` | `jump` | 駅へのジャンプメニュー |

他のオプションは [GTFS-to-HTML の設定ドキュメント](https://gtfstohtml.com/docs/configuration)
を参照してください。`showMap` を `true` にすると路線図付きの時刻表になります
（地図タイルの取得にインターネット接続が必要です）。
