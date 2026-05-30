"""Generate scenario JSON files (run once to refresh scenarios/)."""

import json
from pathlib import Path

ROUTE = {
    "segments": [
        {"from": "Bengaluru", "to": "A", "distance_km": 100},
        {"from": "A", "to": "B", "distance_km": 120},
        {"from": "B", "to": "C", "distance_km": 100},
        {"from": "C", "to": "D", "distance_km": 120},
        {"from": "D", "to": "Kochi", "distance_km": 100},
    ],
    "charging_stations": ["A", "B", "C", "D"],
    "chargers_per_station": {"A": 1, "B": 1, "C": 1, "D": 1},
}

PHYSICS = {
    "battery_range_km": 240,
    "charge_time_min": 25,
    "speed_kmh": 60,
}


def _time_str(minutes: int) -> str:
    minutes = minutes % (24 * 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _buses_direction(
    direction: str,
    start_min: int,
    interval: int,
    count: int,
    operator_for_index,
) -> list[dict]:
    buses = []
    t = start_min
    for i in range(count):
        buses.append(
            {
                "id": f"bus-{direction}-{i + 1:02d}",
                "operator": operator_for_index(i),
                "direction": direction,
                "departure_time": _time_str(t),
            }
        )
        t += interval
    return buses


def _even_spacing_buses(
    bk_operator="kpn",
    kb_operator="kpn",
    kb_start_min: int = 19 * 60,
) -> list[dict]:
    bk = _buses_direction("BK", 19 * 60, 15, 10, lambda _: bk_operator)
    kb = _buses_direction("KB", kb_start_min, 15, 10, lambda _: kb_operator)
    return bk + kb


def _two_operator_buses() -> list[dict]:
    def op(i: int) -> str:
        return "kpn" if i < 5 else "srs"

    bk = _buses_direction("BK", 19 * 60, 15, 10, op)
    kb = _buses_direction("KB", 19 * 60, 15, 10, op)
    return bk + kb


def _peak_buses() -> list[dict]:
    """Six departures every 5 minutes, then four every 15 minutes (per direction)."""
    offsets = [0, 5, 10, 15, 20, 25, 60, 75, 90, 105]
    buses = []
    base = 19 * 60
    for direction in ("BK", "KB"):
        for i, off in enumerate(offsets):
            buses.append(
                {
                    "id": f"bus-{direction}-{i + 1:02d}",
                    "operator": "kpn",
                    "direction": direction,
                    "departure_time": _time_str(base + off),
                }
            )
    return buses


SCENARIOS = [
    {
        "id": "scenario_1",
        "name": "Even spacing",
        "description": "Buses depart every 15 minutes in each direction starting 19:00.",
        "weights": {"individual": 1.0, "operator": 1.0, "overall": 1.0},
        "buses": _even_spacing_buses(),
    },
    {
        "id": "scenario_2",
        "name": "Staggered directions",
        "description": "BK every 15 minutes from 19:00; KB every 15 minutes from 19:05.",
        "weights": {"individual": 1.0, "operator": 1.0, "overall": 1.0},
        "buses": _even_spacing_buses(kb_start_min=19 * 60 + 5),
    },
    {
        "id": "scenario_3",
        "name": "Two operators",
        "description": "kpn and srs each run 5 buses per direction on 15-minute headways from 19:00.",
        "weights": {"individual": 1.0, "operator": 1.0, "overall": 1.0},
        "buses": _two_operator_buses(),
    },
    {
        "id": "scenario_4",
        "name": "Operator-weighted",
        "description": "Same departures as scenario 3; operator fairness weight is doubled.",
        "weights": {"individual": 1.0, "operator": 2.0, "overall": 1.0},
        "buses": _two_operator_buses(),
    },
    {
        "id": "scenario_5",
        "name": "Peak burst",
        "description": "Six buses every 5 minutes, then four every 15 minutes, per direction from 19:00.",
        "weights": {"individual": 1.0, "operator": 1.0, "overall": 1.0},
        "buses": _peak_buses(),
    },
]


def main() -> None:
    out_dir = Path(__file__).resolve().parents[1] / "scenarios"
    out_dir.mkdir(exist_ok=True)
    for spec in SCENARIOS:
        payload = {
            "id": spec["id"],
            "name": spec["name"],
            "description": spec["description"],
            "route": ROUTE,
            "physics": PHYSICS,
            "weights": spec["weights"],
            "buses": spec["buses"],
        }
        path = out_dir / f"{spec['id']}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
