"""Data models for the electric bus charging scheduler."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def parse_time_hhmm(value: str) -> int:
    """Convert HH:MM to minutes since midnight."""
    parts = value.strip().split(":")
    hours = int(parts[0])
    minutes = int(parts[1]) if len(parts) > 1 else 0
    return hours * 60 + minutes


def format_time_minutes(minutes: float) -> str:
    """Format minutes since midnight as HH:MM (24h)."""
    total = int(round(minutes)) % (24 * 60)
    hours = total // 60
    mins = total % 60
    return f"{hours:02d}:{mins:02d}"


@dataclass(frozen=True)
class Segment:
    from_node: str
    to_node: str
    distance_km: float


@dataclass
class Route:
    segments: list[Segment]
    charging_stations: list[str]
    chargers_per_station: dict[str, int]

    _nodes_forward: list[str] = field(init=False, repr=False)
    _cum_dist_km: dict[str, float] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._nodes_forward = [self.segments[0].from_node]
        cum = 0.0
        self._cum_dist_km = {self._nodes_forward[0]: 0.0}
        for seg in self.segments:
            cum += seg.distance_km
            self._nodes_forward.append(seg.to_node)
            self._cum_dist_km[seg.to_node] = cum

    @property
    def origin(self) -> str:
        return self._nodes_forward[0]

    @property
    def destination(self) -> str:
        return self._nodes_forward[-1]

    @property
    def total_distance_km(self) -> float:
        return self._cum_dist_km[self.destination]

    def distance_between(self, from_node: str, to_node: str) -> float:
        """Distance along the forward route (origin → destination)."""
        if from_node not in self._cum_dist_km or to_node not in self._cum_dist_km:
            raise ValueError(f"Unknown node(s): {from_node}, {to_node}")
        d_from = self._cum_dist_km[from_node]
        d_to = self._cum_dist_km[to_node]
        if d_to < d_from:
            raise ValueError(f"{to_node} is before {from_node} on the forward route")
        return d_to - d_from

    def stations_for_direction(self, direction: str) -> list[str]:
        """Charging stations in travel order for BK or KB."""
        if direction == "BK":
            return list(self.charging_stations)
        if direction == "KB":
            return list(reversed(self.charging_stations))
        raise ValueError(f"Unknown direction: {direction}")

    def start_node(self, direction: str) -> str:
        return self.origin if direction == "BK" else self.destination

    def end_node(self, direction: str) -> str:
        return self.destination if direction == "BK" else self.origin

    def distance_for_bus(self, direction: str, from_node: str, to_node: str) -> float:
        """Distance along the bus's travel direction."""
        if direction == "BK":
            return self.distance_between(from_node, to_node)
        return self.distance_between(to_node, from_node)


@dataclass(frozen=True)
class Bus:
    id: str
    operator: str
    direction: str
    departure_time_min: int


@dataclass
class ChargingStop:
    station: str
    arrival_time: float
    wait_time: float
    charge_start: float
    charge_end: float


@dataclass
class BusTimeline:
    bus_id: str
    operator: str
    direction: str
    departure_time: int
    charging_stops: list[ChargingStop]
    arrival_time: float
    total_wait_min: float
    plan_stations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Physics:
    battery_range_km: float
    charge_time_min: float
    speed_kmh: float

    def travel_time_min(self, distance_km: float) -> float:
        return (distance_km / self.speed_kmh) * 60.0


@dataclass
class Scenario:
    id: str
    name: str
    description: str
    route: Route
    physics: Physics
    weights: dict[str, float]
    buses: list[Bus]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Scenario:
        route_data = data["route"]
        segments = [
            Segment(s["from"], s["to"], float(s["distance_km"]))
            for s in route_data["segments"]
        ]
        route = Route(
            segments=segments,
            charging_stations=list(route_data["charging_stations"]),
            chargers_per_station={
                k: int(v) for k, v in route_data["chargers_per_station"].items()
            },
        )
        phys = data["physics"]
        physics = Physics(
            battery_range_km=float(phys["battery_range_km"]),
            charge_time_min=float(phys["charge_time_min"]),
            speed_kmh=float(phys["speed_kmh"]),
        )
        buses = [
            Bus(
                id=b["id"],
                operator=b["operator"],
                direction=b["direction"],
                departure_time_min=parse_time_hhmm(b["departure_time"]),
            )
            for b in data["buses"]
        ]
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            route=route,
            physics=physics,
            weights=dict(data["weights"]),
            buses=buses,
        )
