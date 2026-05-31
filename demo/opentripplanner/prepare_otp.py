#!/usr/bin/env python3
"""OpenTripPlanner(OTP 2.x) の作業ディレクトリを用意する（Issue #25）。

本リポジトリの GTFS-JP フィードと OSM を入力に、OTP の経路検索デモを動かすための
作業ディレクトリ（OSM・OTP jar・GTFS・config）を組み立てる。

既定の流れ:
  1. フィード（zip）の停留所から福岡周辺の bbox を算出
  2. Geofabrik から九州の OSM(.osm.pbf) を取得（既にあれば再利用）
  3. osmium で bbox にクリップ（`--osm` で既存 OSM を渡せばこの 2 段はスキップ）
  4. Maven Central から OTP の shaded jar を取得
  5. フィード zip を作業ディレクトリへコピー
  6. OTP2 用の config(build/router/otp) を書き出す
  7. 起動手順を表示

OTP は Java 17 以上が必要。詳細は README.md を参照。
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FEED = ROOT / "dist" / "FukuokaCitySubway.zip"
DEFAULT_WORKDIR = Path(__file__).resolve().parent / "work"

OTP_VERSION = "2.5.0"
GEOFABRIK_REGION = "asia/japan/kyushu"
OSM_NAME = "fukuoka.osm.pbf"
FEED_NAME = "FukuokaCitySubway.zip"
MARGIN_KM = 3.0


# --------------------------------------------------------------------------
# 純粋関数（単体テスト対象。ネットワーク/サブプロセスに依存しない）
# --------------------------------------------------------------------------
def bbox_from_stops(stops: list[dict], margin_km: float = MARGIN_KM) -> tuple[float, float, float, float]:
    """停留所列から外接 bbox を求め、margin_km だけ広げて返す。

    返り値は ``(min_lon, min_lat, max_lon, max_lat)``（osmium / Geofabrik 互換の順）。
    """
    lats = [float(s["stop_lat"]) for s in stops]
    lons = [float(s["stop_lon"]) for s in stops]
    if not lats or not lons:
        raise ValueError("停留所に座標がありません")
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    dlat = margin_km / 111.0
    mid_lat = (min_lat + max_lat) / 2
    dlon = margin_km / (111.0 * max(math.cos(math.radians(mid_lat)), 1e-6))
    return (
        round(min_lon - dlon, 6),
        round(min_lat - dlat, 6),
        round(max_lon + dlon, 6),
        round(max_lat + dlat, 6),
    )


def geofabrik_url(region: str = GEOFABRIK_REGION) -> str:
    """Geofabrik の OSM(.osm.pbf) ダウンロード URL を返す。"""
    return f"https://download.geofabrik.de/{region}-latest.osm.pbf"


def otp_jar_url(version: str = OTP_VERSION) -> str:
    """Maven Central の OTP shaded jar の URL を返す。"""
    return (
        "https://repo1.maven.org/maven2/org/opentripplanner/otp/"
        f"{version}/otp-{version}-shaded.jar"
    )


def osmium_extract_args(
    bbox: tuple[float, float, float, float], src: Path, dst: Path
) -> list[str]:
    """`osmium extract` のコマンド引数列を返す（bbox で OSM をクリップ）。"""
    min_lon, min_lat, max_lon, max_lat = bbox
    return [
        "osmium", "extract",
        "-b", f"{min_lon},{min_lat},{max_lon},{max_lat}",
        "--overwrite",
        str(src),
        "-o", str(dst),
    ]


def build_config(osm_file: str = OSM_NAME, feed_file: str = FEED_NAME) -> dict:
    """OTP2 の build-config.json 内容を返す（OSM と GTFS を明示指定）。"""
    return {
        "osm": [{"source": osm_file}],
        "transitFeeds": [{"type": "gtfs", "source": feed_file}],
    }


def router_config() -> dict:
    """OTP2 の router-config.json 内容を返す（無難な徒歩・乗換の既定値）。"""
    return {
        "routingDefaults": {
            "walkSpeed": 1.3,
            "transferSlack": 120,
        }
    }


def otp_config() -> dict:
    """OTP2 の otp-config.json 内容を返す（feature フラグ。既定は素のまま）。"""
    return {"otpFeatures": {}}


def read_stops_from_feed(feed_zip: Path) -> list[dict]:
    """GTFS zip 内の stops.txt を読み、stop_lat/stop_lon を持つ行の dict 列を返す。"""
    import csv
    import io

    with zipfile.ZipFile(feed_zip) as zf:
        with zf.open("stops.txt") as f:
            text = io.TextIOWrapper(f, encoding="utf-8-sig")
            rows = [r for r in csv.DictReader(text) if r.get("stop_lat") and r.get("stop_lon")]
    if not rows:
        raise ValueError(f"{feed_zip} の stops.txt に座標がありません")
    return rows


# --------------------------------------------------------------------------
# 副作用を伴う処理（DL・サブプロセス・ファイル書き出し）
# --------------------------------------------------------------------------
def _download(url: str, dst: Path) -> None:
    if dst.exists() and dst.stat().st_size > 0:
        print(f"  既存を再利用: {dst.name}")
        return
    print(f"  取得: {url}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    with urllib.request.urlopen(url) as r, tmp.open("wb") as out:  # noqa: S310
        shutil.copyfileobj(r, out)
    tmp.replace(dst)


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  書き出し: {path.name}")


def prepare(workdir: Path, feed_zip: Path, *, region: str, otp_version: str,
            margin_km: float, osm_path: Path | None) -> None:
    workdir.mkdir(parents=True, exist_ok=True)

    bbox = bbox_from_stops(read_stops_from_feed(feed_zip), margin_km)
    print(f"  bbox(min_lon,min_lat,max_lon,max_lat) = {bbox}")

    osm_dst = workdir / OSM_NAME
    if osm_path is not None:
        print(f"  OSM をコピー: {osm_path}")
        shutil.copy(osm_path, osm_dst)
    else:
        raw = workdir / f"{region.replace('/', '_')}-latest.osm.pbf"
        _download(geofabrik_url(region), raw)
        args = osmium_extract_args(bbox, raw, osm_dst)
        if shutil.which("osmium") is None:
            raise SystemExit(
                "osmium が見つかりません。`apt-get install osmium-tool`（または brew install osmium-tool）"
                "で導入するか、--osm で bbox 抽出済みの OSM を指定してください。"
            )
        print("  クリップ: " + " ".join(args))
        subprocess.run(args, check=True)

    _download(otp_jar_url(otp_version), workdir / f"otp-{otp_version}-shaded.jar")
    shutil.copy(feed_zip, workdir / FEED_NAME)
    print(f"  コピー: {FEED_NAME}")

    _write_json(workdir / "build-config.json", build_config())
    _write_json(workdir / "router-config.json", router_config())
    _write_json(workdir / "otp-config.json", otp_config())

    jar = f"otp-{otp_version}-shaded.jar"
    print(
        "\n完了。次の手順で起動します（Java 17 以上が必要）:\n"
        f"  cd {workdir}\n"
        f"  java -Xmx4g -jar {jar} --build --save .   # グラフ構築\n"
        f"  java -Xmx4g -jar {jar} --load .           # サーバ起動（http://localhost:8080）\n"
        "別ターミナルで:  make demo-otp-sample          # サンプル経路を data/ に保存\n"
    )


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workdir", type=Path, default=DEFAULT_WORKDIR, help="作業ディレクトリ")
    p.add_argument("--feed", type=Path, default=DEFAULT_FEED, help="入力 GTFS zip")
    p.add_argument("--region", default=GEOFABRIK_REGION, help="Geofabrik のリージョン")
    p.add_argument("--otp-version", default=OTP_VERSION, help="OTP のバージョン")
    p.add_argument("--margin-km", type=float, default=MARGIN_KM, help="bbox の余白(km)")
    p.add_argument("--osm", type=Path, default=None,
                   help="bbox 抽出済みの OSM を直接指定（DL/クリップをスキップ）")
    args = p.parse_args(argv)
    prepare(args.workdir, args.feed, region=args.region, otp_version=args.otp_version,
            margin_km=args.margin_km, osm_path=args.osm)


if __name__ == "__main__":
    main()
