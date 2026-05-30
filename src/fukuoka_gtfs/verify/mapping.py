"""ジョルダンのページと GTFS を対応付けるマッピング（config/jorudan_verify.yaml）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

__all__ = ["Mapping", "load_mapping"]


@dataclass(frozen=True)
class Mapping:
    index_url: str
    sample_dates: dict[str, str]
    daytypes: list[str]
    service_groups: dict[str, str]
    # (jorudan_line, terminal) -> (route_id, direction_id)
    _directions: dict[tuple[str, str], tuple[str, int]]
    station_aliases: dict[str, str]
    destination_aliases: dict[str, str]

    def service_id(self, route_id: str, daytype: str) -> str:
        """route_id と曜日区分から GTFS service_id を作る。"""
        return f"{self.service_groups[route_id]}_{daytype}"

    def resolve_direction(
        self, jorudan_line: str, terminal: str
    ) -> tuple[str, int] | None:
        """(路線名, 終端駅) -> (route_id, direction_id)。未知なら None。"""
        return self._directions.get((jorudan_line, terminal))

    def normalize_station(self, fr: str) -> str:
        """ジョルダンの駅名を GTFS stop_name に正規化する。"""
        return self.station_aliases.get(fr, fr)

    def normalize_destination(self, destination: str) -> str:
        """ジョルダンの行先表記を GTFS trip_headsign に正規化する。"""
        return self.destination_aliases.get(destination, destination)


def load_mapping(path: str | Path) -> Mapping:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    directions = {
        (d["jorudan_line"], d["terminal"]): (d["route_id"], int(d["direction_id"]))
        for d in data["directions"]
    }
    return Mapping(
        index_url=data["index_url"],
        sample_dates=data["sample_dates"],
        daytypes=list(data["daytypes"]),
        service_groups=data["service_groups"],
        _directions=directions,
        station_aliases=data.get("station_aliases") or {},
        destination_aliases=data.get("destination_aliases") or {},
    )
