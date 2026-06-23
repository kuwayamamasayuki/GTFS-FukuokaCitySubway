# calendar.txt の start_date を区分別に持たせる設計（Issue #42）

## 背景

2026/4/1 に月曜〜土曜の終電時刻を延長する「ミッドナイト・トレイン」の運行が開始した
（[参考](https://subway.city.fukuoka.lg.jp/topics/detail.php?id=2271)）。

これにより **平日・土曜ダイヤは 2026/4/1 に改正**された。一方、運行対象が月〜土のため
**休日（日曜・祝日）ダイヤは 4/1 改正の対象外**であり、従来の改正日のままとすべきである。

GTFS では有効期間（start_date / end_date）は service_id 単位で持つ。現状の
`config/calendar.yaml` は有効期間を路線グループ単位（空港箱崎 / 七隈）でしか持てず、
同一グループ内の平日 / 土曜 / 休日はすべて同じ start_date になる。Issue #42 を満たすには
**区分（平日 / 土曜 / 休日）ごとに start_date を持てる構造**へ拡張する必要がある。

## 目標

- 平日・土曜の start_date を `20260401` とする。
- 休日の start_date は従来の路線別改正日を維持する（空港箱崎 = `20260314`、七隈 = `20250804`）。
- 路線グループごとに改正日が異なる将来にも引き続き対応できること（既存の独立性を維持）。

## 設計

### 1. 設定ファイル `config/calendar.yaml`

各 service_group の単一 `start_date` を、区分ごとに完全明示した `start_dates` マッピングへ置き換える。
`end_date` はグループ単位のまま（区分で分ける要件はない）。

```yaml
service_groups:
  - id: 空港箱崎
    lines: [空港線, 箱崎線]
    end_date: "99991231"
    start_dates:
      平日: "20260401"   # ミッドナイト・トレイン（2026/4/1 改正）
      土曜: "20260401"
      休日: "20260314"   # 4/1 改正の対象外。従来の改正日を維持
  - id: 七隈
    lines: [七隈線]
    end_date: "99991231"
    start_dates:
      平日: "20260401"
      土曜: "20260401"
      休日: "20250804"
```

### 2. `src/fukuoka_gtfs/builders/calendar_builder.py`

- `build_calendar`: 各 calendar 行の `start_date` を `g["start_dates"][segment]` から取得する。
- `build_calendar_dates`: グループ内の **最早 start_date** から走査する。祝日例外のうち
  - 「通常区分の除外（exception_type=2）」は、その区分の start_date 以降の日付のみ出力。
  - 「休日区分の追加（exception_type=1）」は、休日区分の start_date 以降の日付のみ出力。

  これにより、平日が未開始（4/1 より前）の祝日に対して平日の除外例外を出さず、区分別の
  有効期間と整合する。

### 3. `src/fukuoka_gtfs/assembler.py`

`feed_info` の既定開始日を、全グループ・全区分の start_date の最小値とする
（`min(d for g in groups for d in g["start_dates"].values())`）。

### 4. 生成物

- `dist/calendar.txt`: 平日・土曜の start_date が `20260401`、休日は従来日に更新される。
- `dist/calendar_dates.txt`: 区分別ガードに伴う差分（平日が未開始の祝日に対する除外例外の抑止）を反映する。

## テスト

- `tests/test_calendar_builder.py`: 新構造（`start_dates`）に更新。区分ごとに start_date が
  反映されること、区分別の有効期間ガードが効くことを検証。
- `tests/test_calendar_config.py`: 実設定で平日・土曜 = `20260401`、休日 = 従来日であること、
  路線グループの独立性が保たれることを検証。
- 新規 Issue #42 検証: 平日・土曜が `20260401`、休日が従来の改正日であることを実設定で確認。

## 影響範囲

- service_id の体系（`<グループ>_<区分>`）は不変。dist 内の trips 等が参照する service_id は変わらない。
- 休日区分のグループ内最早 start_date は従来値と同じため、calendar_dates の走査範囲の起点は不変。
