#!/usr/bin/env python3
"""公式運賃表 PDF の三角運賃表を画像解析し、全駅ペアの運賃を抽出して
reference_gtfs/fare_rules.txt（現行の生成結果）と突き合わせ検証する。

原理:
  運賃表は区ごとに色分けされ、各セルの色＝区。駅コードの円（空港=橙/箱崎=青/
  七隈=緑）を検出して対角の駅順・座標を確定し、円座標＋オフセットで各セル中心の
  色を区へ分類する。オフセットは「同一路線で隣接する駅同士は 1区」という性質で
  自己校正する。

  python scripts/verify_fares.py            # 検証（差異を表示）
  python scripts/verify_fares.py --write     # PDF 抽出値で fare_* を上書き
"""
from __future__ import annotations

import csv
import subprocess
import sys
import urllib.request
from collections import defaultdict, deque
from pathlib import Path

import fitz
import numpy as np

PDF_URL = "https://subway.city.fukuoka.lg.jp/fare/pdf/renrakuA4Side.pdf"
PDF = Path("/tmp/fare.pdf")
ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "reference_gtfs"
S = 3.0
X0, Y0 = 100, 28
ZONE_PRICE = {1: 210, 2: 260, 3: 300, 4: 340, 5: 360, 6: 380}
CENT = {1: (255, 251, 209), 2: (249, 207, 221), 3: (179, 224, 246),
        4: (252, 214, 122), 5: (175, 214, 141), 6: (242, 151, 130)}

POS2SID = {1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8",
           9: "9", 10: "10", 11: "11", 12: "11", 13: "12", 14: "13",
           15: "14", 16: "15", 17: "16", 18: "17", 19: "18", 20: "19",
           21: "36", 22: "35", 23: "34", 24: "33", 25: "32", 26: "31",
           27: "30", 28: "29", 29: "28", 30: "27", 31: "26", 32: "25",
           33: "24", 34: "23", 35: "22", 36: "21", 37: "20"}
SID_NAME = {"1": "姪浜", "2": "室見", "3": "藤崎", "4": "西新", "5": "唐人町", "6": "大濠公園",
            "7": "赤坂", "8": "天神", "9": "中洲川端", "10": "祇園", "11": "博多", "12": "東比恵",
            "13": "福岡空港", "14": "呉服町", "15": "千代県庁口", "16": "馬出九大病院前",
            "17": "箱崎宮前", "18": "箱崎九大前", "19": "貝塚", "20": "橋本", "21": "次郎丸",
            "22": "賀茂", "23": "野芥", "24": "梅林", "25": "福大前", "26": "七隈", "27": "金山",
            "28": "茶山", "29": "別府", "30": "六本松", "31": "桜坂", "32": "薬院大通", "33": "薬院",
            "34": "渡辺通", "35": "天神南", "36": "櫛田神社前"}
# 同一路線で物理的に隣接する位置ペア（=1区）。路線跨ぎの (14,15)(20,21) と同一駅 (11,12) は除外。
ADJ_1KU = [(p, p + 1) for p in range(1, 37) if (p, p + 1) not in {(11, 12), (14, 15), (20, 21)}]


def render(x1, y1, x2, y2, s=S):
    pix = pg.get_pixmap(matrix=fitz.Matrix(s, s), clip=fitz.Rect(x1, y1, x2, y2))
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3].astype(int)


def components(mask, minsz):
    out = []
    ys, xs = np.where(mask)
    pts = set(zip(ys.tolist(), xs.tolist()))
    while pts:
        q = deque([pts.pop()]); comp = [q[0]]
        while q:
            y, x = q.popleft()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    p = (y + dy, x + dx)
                    if p in pts:
                        pts.discard(p); q.append(p); comp.append(p)
        if len(comp) >= minsz:
            out.append((sum(p[1] for p in comp) / len(comp), sum(p[0] for p in comp) / len(comp)))
    return out


def detect_stations():
    """駅コード円を検出し、位置 1..37 の (x, y) を返す。中洲川端(K+H) は統合。"""
    A = render(X0, Y0, 940, 660)
    R, G, B = A[:, :, 0], A[:, :, 1], A[:, :, 2]
    masks = {"K": (R > 200) & (G > 110) & (G < 195) & (B < 95),
             "H": (R < 120) & (G > 110) & (B > 180) & (B - G > 40),
             "N": (R < 140) & (G > 120) & (B < 175) & (G - B > 12) & (G - R > 30)}
    raw = []
    for c, m in masks.items():
        for cx, cy in components(m, 250):
            raw.append([cx / S + X0, cy / S + Y0, c])
    band = [b for b in raw if abs(b[1] - (105 + 0.67 * (b[0] - 233))) < 28]
    g = defaultdict(list)
    for cx, cy, c in band:
        g[(round(cx / 9), c)].append((cx, cy))
    merged = []
    for (_, c), lst in g.items():
        merged.append((sum(x for x, _ in lst) / len(lst), sum(y for _, y in lst) / len(lst), c))
    merged.sort()
    out = []
    i = 0
    while i < len(merged):
        x, y, c = merged[i]
        if i + 1 < len(merged) and abs(merged[i + 1][0] - x) < 6 and {c, merged[i + 1][2]} == {"K", "H"}:
            out.append(((x + merged[i + 1][0]) / 2, (y + merged[i + 1][1]) / 2))  # 中洲川端
            i += 2
        else:
            out.append((x, y)); i += 1
    return out


def classify(rgb):
    best = min(CENT, key=lambda z: sum((c - v) ** 2 for c, v in zip(CENT[z], rgb)))
    d = sum((c - v) ** 2 for c, v in zip(CENT[best], rgb)) ** 0.5
    return best if d < 95 else None


def cell_zone(A, xpt, ypt):
    x, y = int((xpt - X0) * S), int((ypt - Y0) * S)
    patch = A[max(0, y - 5):y + 6, max(0, x - 6):x + 7].reshape(-1, 3)
    m = ~(((patch.sum(1) < 175)) | ((patch > 248).all(1)))
    if m.sum() < 8:
        return None
    return classify(tuple(np.median(patch[m], axis=0).astype(int).tolist()))


def ensure_pdf():
    if PDF.exists() and PDF.stat().st_size > 0:
        return
    print(f"運賃表 PDF を取得: {PDF_URL}")
    for _ in range(5):
        try:
            subprocess.run(["curl", "-fsSL", "-o", str(PDF), PDF_URL], check=True)
            if PDF.stat().st_size > 0:
                return
        except Exception:  # noqa: BLE001
            try:
                with urllib.request.urlopen(PDF_URL, timeout=60) as r:  # noqa: S310
                    PDF.write_bytes(r.read())
                return
            except Exception:  # noqa: BLE001
                pass
    raise RuntimeError(f"PDF 取得に失敗: {PDF_URL}")


def main():
    global pg
    ensure_pdf()
    pg = fitz.open(str(PDF))[0]
    st = detect_stations()
    print(f"駅検出 = {len(st)}（期待 37）")
    if len(st) != 37:
        return 1
    X = {p + 1: st[p][0] for p in range(37)}
    Y = {p + 1: st[p][1] for p in range(37)}
    A = render(X0, Y0, 940, 660)

    # オフセット (dx, dy) を「隣接=1区」率で自己校正
    best, best_off = -1, (0, 10)
    for dy in range(2, 22):
        for dx in range(-6, 7, 2):
            ok = sum(cell_zone(A, X[c] + dx, Y[r] + dy) == 1 for r, c in
                     [(b, a) for a, b in ADJ_1KU])
            if ok > best:
                best, best_off = ok, (dx, dy)
    dx, dy = best_off
    print(f"校正: offset={best_off} 隣接1区 {best}/{len(ADJ_1KU)}")

    # 全セル抽出
    pdf_fare = {}
    for r in range(2, 38):
        for c in range(1, r):
            z = cell_zone(A, X[c] + dx, Y[r] + dy)
            if z is None:
                continue
            a, b = POS2SID[r], POS2SID[c]
            if a != b:
                pdf_fare[frozenset((a, b))] = ZONE_PRICE[z]
    all_pairs = {frozenset((str(i), str(j))) for i in range(1, 37) for j in range(i + 1, 37)}
    print(f"抽出ペア = {len(pdf_fare)} / 全 {len(all_pairs)}")

    # 現行値と比較
    with (REF / "fare_attributes.txt").open(encoding="utf-8-sig") as f:
        price = {r["fare_id"]: int(r["price"]) for r in csv.DictReader(f)}
    cur = {}
    with (REF / "fare_rules.txt").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            cur[frozenset((r["origin_id"], r["destination_id"]))] = price[r["fare_id"]]
    diffs = [(a, b, cur[p], pf) for p, pf in pdf_fare.items() if p in cur
             for a, b in [sorted(p, key=int)] if cur[p] != pf]
    checked = sum(1 for p in pdf_fare if p in cur)
    print(f"\n比較 {checked} ペア: 一致 {checked - len(diffs)} / 相違 {len(diffs)}")
    # 路線種別で分類: 空港/箱崎のみ(sid<=19, 七隈非関与)は本来不変 → 相違 0 が健全性の証明
    nana = lambda s: int(s) >= 20 or s == "11"   # 七隈線関与(11=博多)
    non_nana = [d for d in diffs if not (nana(d[0]) or nana(d[1]))]
    print(f"  うち 空港/箱崎のみ(七隈非関与)の相違 = {len(non_nana)}（0 ならグリッド健全）")
    for a, b, c0, pf in sorted(non_nana, key=lambda d: (int(d[0]), int(d[1]))):
        print(f"    [要確認] {a}:{SID_NAME[a]} ↔ {b}:{SID_NAME[b]} 現行={c0} PDF={pf}")
    print(f"  七隈線関与の相違 = {len(diffs) - len(non_nana)}（2019 は延伸前で陳腐化、PDF が正）")
    missing = all_pairs - set(pdf_fare)
    if missing:
        print(f"\n未抽出 {len(missing)} ペア: " +
              ", ".join(f"{min(p,key=int)}-{max(p,key=int)}" for p in list(missing)[:20]))

    if "--write" in sys.argv:
        _write(pdf_fare)
    return 0


def _write(pdf_fare):
    AGENCY = "3000020401307_0"
    od = {}
    for pair, p in pdf_fare.items():
        a, b = sorted(pair, key=int)
        od[(a, b)] = p; od[(b, a)] = p
    with (REF / "fare_attributes.txt").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["fare_id", "agency_id", "price", "currency_type", "payment_method", "transfers"])
        for p in sorted(set(od.values())):
            w.writerow([f"fare_{p}", AGENCY, p, "JPY", 1, ""])
    with (REF / "fare_rules.txt").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["fare_id", "origin_id", "destination_id"])
        for (o, d), p in sorted(od.items(), key=lambda kv: (int(kv[0][0]), int(kv[0][1]))):
            w.writerow([f"fare_{p}", o, d])
    print(f"上書き完了: {len(od)} OD ルール")


if __name__ == "__main__":
    raise SystemExit(main())
