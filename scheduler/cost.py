"""Cost functions for soft scheduling rules."""

from __future__ import annotations

from scheduler.models import BusTimeline, Physics, Route


def baseline_arrival_min(
    bus_direction: str,
    departure_time_min: int,
    route: Route,
    physics: Physics,
    plan_stations: list[str],
) -> float:
    """Arrival time with no waiting (travel + fixed charge durations only)."""
    start = route.start_node(bus_direction)
    end = route.end_node(bus_direction)
    t = float(departure_time_min)
    pos = start
    for station in plan_stations:
        dist = route.distance_for_bus(bus_direction, pos, station)
        t += physics.travel_time_min(dist)
        t += physics.charge_time_min
        pos = station
    dist = route.distance_for_bus(bus_direction, pos, end)
    t += physics.travel_time_min(dist)
    return t


def compute_cost(
    timeline: BusTimeline,
    all_timelines: list[BusTimeline],
    weights: dict[str, float],
    route: Route,
    physics: Physics,
) -> float:
    """
    Weighted sum of individual, operator, and overall cost components.

    - individual_cost: this bus's total wait (minutes)
    - operator_cost: fleet average wait for same operator minus this bus's wait
    - overall_cost: arrival delay vs no-wait baseline for this bus's plan
    """
    individual_cost = timeline.total_wait_min

    same_operator = [
        tl for tl in all_timelines if tl.operator == timeline.operator
    ]
    if same_operator:
        avg_wait = sum(tl.total_wait_min for tl in same_operator) / len(
            same_operator
        )
        operator_cost = avg_wait - timeline.total_wait_min
    else:
        operator_cost = 0.0

    travel_time = physics.travel_time_min(route.total_distance_km)
    baseline = timeline.departure_time + travel_time + 2.0 * physics.charge_time_min
    overall_cost = max(0.0, timeline.arrival_time - baseline)

    return (
        weights.get("individual", 1.0) * individual_cost
        + weights.get("operator", 1.0) * operator_cost
        + weights.get("overall", 1.0) * overall_cost
    )
