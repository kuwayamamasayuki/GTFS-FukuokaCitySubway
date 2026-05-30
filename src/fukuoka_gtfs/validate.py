"""GTFS の検証。2 段構え:

1. Python 整合検査（必須・依存軽量）: 参照整合・時刻単調・連番などを自前で確認。
2. MobilityData Canonical GTFS Schedule Validator（Java）: 公式・権威ある検証。
   ローカルに Java が無ければポータブル JRE を tools/ に取得して実行する。
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tarfile
import time
import urllib.request
from pathlib import Path

from .errors import FukuokaGtfsError
from .gtfsio import read_csv

log = logging.getLogger("fukuoka_gtfs")


class ValidationError(FukuokaGtfsError):
    pass


# ---------------------------------------------------------------- Python 整合検査
def _to_sec(hms: str) -> int:
    h, m, s = (int(x) for x in hms.split(":"))
    return h * 3600 + m * 60 + s


def check_integrity(gtfs_dir: str | Path) -> list[str]:
    """参照整合などを確認し、問題点のリストを返す（空なら健全）。"""
    d = Path(gtfs_dir)
    issues: list[str] = []

    def ids(name: str, col: str) -> set[str]:
        _, rows = read_csv(d / name)
        return {r[col] for r in rows}

    stop_ids = ids("stops.txt", "stop_id")
    _, stops_rows = read_csv(d / "stops.txt")
    boardable = {r["stop_id"] for r in stops_rows if str(r.get("location_type", "")) in ("", "0")}
    route_ids = ids("routes.txt", "route_id")
    service_ids = ids("calendar.txt", "service_id")
    trip_ids = ids("trips.txt", "trip_id")

    # trips の参照
    _, trips_rows = read_csv(d / "trips.txt")
    for r in trips_rows:
        if r["route_id"] not in route_ids:
            issues.append(f"trips: 未知の route_id {r['route_id']} (trip {r['trip_id']})")
        if r["service_id"] not in service_ids:
            issues.append(f"trips: 未知の service_id {r['service_id']} (trip {r['trip_id']})")

    # calendar_dates の参照
    cd_path = d / "calendar_dates.txt"
    if cd_path.exists():
        _, cd_rows = read_csv(cd_path)
        for r in cd_rows:
            if r["service_id"] not in service_ids:
                issues.append(f"calendar_dates: 未知の service_id {r['service_id']} ({r['date']})")

    # stop_times の参照・連番・時刻単調
    _, st_rows = read_csv(d / "stop_times.txt")
    by_trip: dict[str, list[dict]] = {}
    for r in st_rows:
        if r["trip_id"] not in trip_ids:
            issues.append(f"stop_times: 未知の trip_id {r['trip_id']}")
        if r["stop_id"] not in stop_ids:
            issues.append(f"stop_times: 未知の stop_id {r['stop_id']} (trip {r['trip_id']})")
        elif r["stop_id"] not in boardable:
            issues.append(f"stop_times: 乗降不可な stop_id {r['stop_id']}（location_type≠0）")
        by_trip.setdefault(r["trip_id"], []).append(r)

    for trip_id, rows in by_trip.items():
        rows.sort(key=lambda x: int(x["stop_sequence"]))
        if len(rows) < 2:
            issues.append(f"stop_times: 停車が 1 つしかない trip {trip_id}")
        prev = -1
        for r in rows:
            sec = _to_sec(r["departure_time"])
            if sec < prev:
                issues.append(f"stop_times: 時刻が逆行 trip {trip_id} @seq{r['stop_sequence']}")
            prev = sec

    return issues


def assert_integrity(gtfs_dir: str | Path) -> None:
    issues = check_integrity(gtfs_dir)
    if issues:
        head = "\n".join(f"  - {x}" for x in issues[:30])
        more = "" if len(issues) <= 30 else f"\n  …他 {len(issues) - 30} 件"
        raise ValidationError(f"整合検査で {len(issues)} 件の問題:\n{head}{more}")
    log.info("Python 整合検査: 問題なし")


# ------------------------------------------------ Canonical Validator（Java）取得・実行
ADOPTIUM_JRE = ("https://api.adoptium.net/v3/binary/latest/17/ga/linux/x64/jre/hotspot/normal/eclipse")
GTFS_VALIDATOR_RELEASE_API = "https://api.github.com/repos/MobilityData/gtfs-validator/releases/latest"


def _try_curl(url: str, dest: Path) -> bool:
    if not shutil.which("curl"):
        return False
    try:
        subprocess.run(
            ["curl", "-fsSL", "--retry", "3", "--retry-all-errors", "-A", "fukuoka-gtfs/1.0",
             "-o", str(dest), url],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return dest.exists() and dest.stat().st_size > 0
    except Exception:  # noqa: BLE001
        return False


def _try_urllib(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "fukuoka-gtfs/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r, dest.open("wb") as f:  # noqa: S310
            shutil.copyfileobj(r, f)
        return dest.exists() and dest.stat().st_size > 0
    except Exception:  # noqa: BLE001
        return False


def _download(url: str, dest: Path, retries: int = 8) -> None:
    """curl と urllib を交互に試す（環境により失敗タイミングが異なるため）。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, retries + 1):
        if _try_curl(url, dest) or _try_urllib(url, dest):
            return
        log.warning("取得失敗 (%d/%d) %s", attempt, retries, url)
        time.sleep(min(5 * attempt, 30))
    raise RuntimeError(f"取得に失敗: {url}")


def ensure_java(tools_dir: Path) -> str:
    """利用可能な java の実行パスを返す。無ければポータブル JRE を取得する。"""
    sys_java = shutil.which("java")
    if sys_java:
        return sys_java
    jre_dir = tools_dir / "jre"
    existing = list(jre_dir.glob("**/bin/java"))
    if existing:
        return str(existing[0])
    log.info("Java 未検出 → Temurin JRE 17 を取得します")
    tar = tools_dir / "jre.tar.gz"
    _download(ADOPTIUM_JRE, tar)
    jre_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar) as t:
        t.extractall(jre_dir)
    tar.unlink(missing_ok=True)
    found = list(jre_dir.glob("**/bin/java"))
    if not found:
        raise RuntimeError("JRE の展開後に java が見つかりません")
    found[0].chmod(0o755)
    return str(found[0])


def ensure_validator_jar(tools_dir: Path) -> Path:
    """gtfs-validator の CLI jar を取得（無ければ）してパスを返す。"""
    existing = list(tools_dir.glob("gtfs-validator-*cli.jar"))
    if existing:
        return existing[0]
    log.info("gtfs-validator の最新リリースを問い合わせ中")
    meta = tools_dir / "_release.json"
    _download(GTFS_VALIDATOR_RELEASE_API, meta)  # API 応答も堅牢に取得
    release = json.loads(meta.read_text(encoding="utf-8"))
    asset = next((a for a in release.get("assets", []) if a["name"].endswith("cli.jar")), None)
    if not asset:
        raise RuntimeError("gtfs-validator の cli.jar アセットが見つかりません")
    jar = tools_dir / asset["name"]
    _download(asset["browser_download_url"], jar)
    return jar


def run_canonical(zip_path: str | Path, out_dir: str | Path, tools_dir: str | Path,
                  download_tools: bool = True) -> dict:
    """Canonical Validator を実行し、{error, warning, ...} の件数 dict を返す。"""
    tools_dir = Path(tools_dir)
    out_dir = Path(out_dir)
    if not download_tools and not shutil.which("java") and not list(tools_dir.glob("**/bin/java")):
        raise ValidationError("Java が無く、--download-tools も指定されていません。")
    java = ensure_java(tools_dir)
    jar = ensure_validator_jar(tools_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [java, "-jar", str(jar), "-i", str(zip_path), "-o", str(out_dir)]
    log.info("Canonical Validator 実行: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return summarize_report(out_dir / "report.json")


def summarize_report(report_json: str | Path) -> dict:
    data = json.loads(Path(report_json).read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for notice in data.get("notices", []):
        sev = notice.get("severity", "UNKNOWN")
        counts[sev] = counts.get(sev, 0) + int(notice.get("totalNotices", 0))
    log.info("Canonical Validator 結果: %s", counts)
    return counts
