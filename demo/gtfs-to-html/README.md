# GTFS-to-HTML で時刻表を作る例

[GTFS-to-HTML](https://gtfstohtml.com/) を使い、本リポジトリが生成した GTFS-JP
フィード（`dist/FukuokaCitySubway.zip`）から、人間が読める **HTML 時刻表**を生成する例です。

生成済みの成果物を `html/` に同梱しているので、まずはそのまま
`html/index.html` をブラウザで開けば閲覧できます（再生成は任意）。

## 成果物（同梱済み）

```
html/
  index.html                  概要ページ（路線一覧へのリンク）
  20250804-99991231/
    空港線.html                空港線の全時刻表（平日/土曜/休日 × 上下）
    箱崎線.html
    七隈線.html
  css/  js/                    GTFS-to-HTML 同梱のスタイル・スクリプト
```

`20250804-99991231` はフィードの運行期間（`calendar.txt` 由来）から付く
フォルダ名です。ダイヤ改正で期間が変われば名前も変わります。

## 自分で再生成する

[Node.js](https://nodejs.org/) **20 以上**が必要です（GTFS-to-HTML 2.12 の要件）。

```bash
cd demo/gtfs-to-html
npm install        # gtfs-to-html をローカル(node_modules/)へ導入
npm run build      # config.json に従い ../../dist/FukuokaCitySubway.zip → html/ を生成
python3 inject_backlink.py   # 各ページ先頭に「デモTOPへ戻る」リンクを注入
```

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
| `agencies[].path` | `../../dist/FukuokaCitySubway.zip` | 入力 GTFS（公開スナップショット） |
| `outputPath` | `html` | 出力先フォルダ |
| `useParentStation` | `true` | 子ホーム（`13_1` 等）を親駅にまとめる |
| `showMap` | `false` | 地図埋め込みを省略（地図タイル用トークン不要） |
| `menuType` | `jump` | 駅へのジャンプメニュー |

他のオプションは [GTFS-to-HTML の設定ドキュメント](https://gtfstohtml.com/docs/configuration)
を参照してください。`showMap` を `true` にすると路線図付きの時刻表になります
（地図タイルの取得にインターネット接続が必要です）。
