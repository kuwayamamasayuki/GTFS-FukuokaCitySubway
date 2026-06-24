"""config/ 以下の YAML を読み込み、型付きで提供する。"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from .excel.band_detector import Vocab


class SourceCfg(BaseModel):
    name: str
    url: str
    filename: str
    lines: list[str]


class FeedCfg(BaseModel):
    feed_publisher_name: str
    feed_publisher_url: str
    feed_lang: str = "ja"
    feed_contact_url: str = ""
    feed_contact_email: str = ""
    feed_start_date: str | None = None
    feed_end_date: str | None = None
    feed_version: str | None = None


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Config:
    """プロジェクトの全設定。`root` はリポジトリのルート。"""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.config_dir = self.root / "config"
        self.reference_dir = self.root / "reference_gtfs"
        self.data_dir = self.root / "data"
        self.build_dir = self.root / "build"
        self.tools_dir = self.root / "tools"

        self.sources = [SourceCfg(**s) for s in _load_yaml(self.config_dir / "sources.yaml")["sources"]]
        self.feed = FeedCfg(**_load_yaml(self.config_dir / "feed.yaml"))
        self.routes = _load_yaml(self.config_dir / "routes.yaml")
        self.stations = _load_yaml(self.config_dir / "stations.yaml")
        self.calendar = _load_yaml(self.config_dir / "calendar.yaml")
        self.parser = _load_yaml(self.config_dir / "parser.yaml")

    # --- 便利アクセサ ---
    @property
    def service_labels(self) -> dict[str, str]:
        return self.routes["service_labels"]

    @property
    def directions(self) -> dict[str, int]:
        return {k: int(v) for k, v in self.routes["directions"].items()}

    @property
    def trip_shapes(self) -> dict[tuple[str, int], str]:
        """(route_id, direction_id) → shape_id（shapes.txt の shape_id と一致）。"""
        return {
            (route_id, int(direction_id)): shape_id
            for route_id, by_dir in self.routes.get("trip_shapes", {}).items()
            for direction_id, shape_id in by_dir.items()
        }

    @property
    def platform_overrides(self) -> dict:
        return self.stations.get("platform_overrides", {})

    @property
    def overnight_threshold_sec(self) -> int:
        return int(self.parser.get("overnight_threshold_hour", 4)) * 3600

    @property
    def service_groups(self) -> list[dict]:
        return self.calendar["service_groups"]

    @property
    def route_to_group(self) -> dict[str, str]:
        """route_id（路線名）→ サービスグループ id。"""
        return {line: g["id"] for g in self.service_groups for line in g["lines"]}

    def vocab(self) -> Vocab:
        return Vocab.from_config(self.parser)
