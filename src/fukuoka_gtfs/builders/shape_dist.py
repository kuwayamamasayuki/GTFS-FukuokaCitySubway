"""停車（駅）位置を shapes.txt のポリライン上へ投影し、累積距離(m)を求める。

stop_times.shape_dist_traveled は shapes.shape_dist_traveled と同一単位（本フィードでは
メートル）でなければならない。そこで各駅座標を線形上の最近点へ投影し、その点の
shape_dist_traveled を 2 端点の値から線形補間して採用する（Issue #49）。

緯度経度は福岡程度の狭域なら等距離円筒図法（緯度方向 111320 m/度、経度方向は
基準緯度の cos を掛ける）で十分な精度の平面近似が得られるため、これで投影する。
"""
from __future__ import annotations

import math

_M_PER_DEG_LAT = 111320.0


def _to_xy(lat: float, lon: float, lat0: float) -> tuple[float, float]:
    """基準緯度 lat0 を用いた平面メートル座標（x=東, y=北）へ変換する。"""
    m_per_deg_lon = _M_PER_DEG_LAT * math.cos(math.radians(lat0))
    return lon * m_per_deg_lon, lat * _M_PER_DEG_LAT


def project_dist(
    shape_points: list[tuple[float, float, float]], lat: float, lon: float,
) -> float | None:
    """(lat, lon) を shape_points 上へ投影した点の shape_dist_traveled を返す。

    shape_points は (lat, lon, dist) の順序付きリスト。最近セグメントへ垂線を下ろし、
    その足の位置に対応する dist を 2 端点から線形補間する。点が無ければ None。
    """
    if not shape_points:
        return None
    if len(shape_points) == 1:
        return shape_points[0][2]

    lat0 = shape_points[0][0]
    px, py = _to_xy(lat, lon, lat0)

    best_d2 = math.inf
    best_dist = shape_points[0][2]
    for (la, lo, da), (lb, lob, db) in zip(shape_points, shape_points[1:]):
        ax, ay = _to_xy(la, lo, lat0)
        bx, by = _to_xy(lb, lob, lat0)
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        if seg2 == 0:                       # 重複点（長さ 0 セグメント）
            t = 0.0
        else:
            t = ((px - ax) * dx + (py - ay) * dy) / seg2
            t = max(0.0, min(1.0, t))       # セグメント内へクランプ
        cx, cy = ax + t * dx, ay + t * dy
        d2 = (px - cx) ** 2 + (py - cy) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_dist = da + t * (db - da)
    return best_dist
