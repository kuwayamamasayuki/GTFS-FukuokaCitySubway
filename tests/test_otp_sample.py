"""demo/opentripplanner/fetch_sample.py の純粋関数の単体テスト（Issue #25）。

OTP の起動を要さず、駅座標の解決・GraphQL クエリ生成・応答の要約を検証する。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fs = _load("fetch_sample", "demo/opentripplanner/fetch_sample.py")

STOPS = [
    {"stop_id": "P1", "stop_name": "博多", "stop_lat": "33.590", "stop_lon": "130.420", "location_type": "1"},
    {"stop_id": "C1", "stop_name": "博多", "stop_lat": "33.591", "stop_lon": "130.421", "location_type": "0"},
    {"stop_id": "P2", "stop_name": "福岡空港", "stop_lat": "33.5859", "stop_lon": "130.4505", "location_type": "1"},
]


def test_find_stop_coord_prefers_parent():
    # 同名の子(location_type=0)より親(=1)を優先
    assert fs.find_stop_coord(STOPS, "博多") == (33.590, 130.420)


def test_find_stop_coord_missing_raises():
    with pytest.raises(KeyError):
        fs.find_stop_coord(STOPS, "存在しない駅")


def test_plan_query_contains_coords_and_datetime():
    body = fs.plan_query((33.59, 130.42), (33.5859, 130.4505), "2026-04-01", "08:00:00")
    q = body["query"]
    assert "33.59" in q and "130.42" in q
    assert "33.5859" in q and "130.4505" in q
    assert '"2026-04-01"' in q
    assert '"08:00:00"' in q
    assert "plan(" in q


def _sample_response() -> dict:
    return {
        "data": {
            "plan": {
                "itineraries": [
                    {
                        "duration": 1980,
                        "walkDistance": 320.0,
                        "legs": [
                            {"mode": "WALK", "startTime": 1, "endTime": 2,
                             "from": {"name": "橋本"}, "to": {"name": "橋本駅"}, "route": None},
                            {"mode": "SUBWAY", "startTime": 2, "endTime": 3,
                             "from": {"name": "橋本駅"}, "to": {"name": "天神南"},
                             "route": {"shortName": "七隈線", "longName": "Nanakuma"}},
                            {"mode": "SUBWAY", "startTime": 4, "endTime": 5,
                             "from": {"name": "天神"}, "to": {"name": "福岡空港"},
                             "route": {"shortName": "空港線", "longName": "Kuko"}},
                        ],
                    }
                ]
            }
        }
    }


def test_summarize_itinerary():
    s = fs.summarize_itinerary(_sample_response())
    assert s["duration_sec"] == 1980
    assert s["duration_min"] == 33
    assert s["walk_distance_m"] == 320
    # 乗換 = 交通機関 leg 数 - 1（WALK を除く 2 本 → 1 回）
    assert s["transfers"] == 1
    assert len(s["legs"]) == 3
    assert s["legs"][1]["route"] == "七隈線"


def test_summarize_itinerary_empty_raises():
    with pytest.raises(ValueError):
        fs.summarize_itinerary({"data": {"plan": {"itineraries": []}}})
