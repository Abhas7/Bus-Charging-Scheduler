"""Greedy dispatcher: assign plans and resolve charger conflicts."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from scheduler.cost import compute_cost
from scheduler.models import (
    Bus,
    BusTimeline,
    ChargingStop,
    Physics,
    Route,
    Scenario,
)
from scheduler.planner import generate_charging_plans


def _init_charger_slots(route: Route) -> dict[str, list[float]]:
    """Per station: list of 'free at' timestamps, one per charger."""
    slots: dict[str, list[float]] = {}
    for station, count in route.chargers_per_station.items():
        slots[station] = [0.0] * max(1, int(count))
    return slots


def _simulate_plan(
    bus: Bus,
    plan: list[str],
    route: Route,
    physics: Physics,
    charger_slots: dict[str, list[float]],
) -> tuple[BusTimeline, dict[str, list[float]]]:
    """
    Simulate one bus on a plan; assign earliest-available charger at each stop.

    charge_start = max(arrival, charger_free_at)
    """
    slots = copy.deepcopy(charger_slots)
    current_time = float(bus.departure_time_min)
    pos = route.start_node(bus.direction)
    end = route.end_node(bus.direction)
    charging_stops: list[ChargingStop] = []
    total_wait = 0.0

    for station in plan:
        dist = route.distance_for_bus(bus.direction, pos, station)
        current_time += physics.travel_time_min(dist)
        arrival = current_time

        station_slots = slots.get(station, [0.0])
        best_idx = 0
        best_start = max(arrival, station_slots[0])
        for idx, free_at in enumerate(station_slots):
            start = max(arrival, free_at)
            if start < best_start:
                best_start = start
                best_idx = idx

        wait = best_start - arrival
        charge_start = best_start
        charge_end = charge_start + physics.charge_time_min
        station_slots[best_idx] = charge_end
        slots[station] = station_slots

        charging_stops.append(
            ChargingStop(
                station=station,
                arrival_time=arrival,
                wait_time=wait,
                charge_start=charge_start,
                charge_end=charge_end,
            )
        )
        total_wait += wait
        current_time = charge_end
        pos = station

    dist = route.distance_for_bus(bus.direction, pos, end)
    current_time += physics.travel_time_min(dist)

    timeline = BusTimeline(
        bus_id=bus.id,
        operator=bus.operator,
        direction=bus.direction,
        departure_time=bus.departure_time_min,
        charging_stops=charging_stops,
        arrival_time=current_time,
        total_wait_min=total_wait,
        plan_stations=list(plan),
    )
    return timeline, slots


def schedule(scenario: Scenario) -> list[BusTimeline]:
    """
    Assign each bus a charging plan and resolve station conflicts greedily.

    Buses are processed in departure order (ties broken by bus ID).
    For each bus, the plan with lowest marginal cost is chosen given
  chargers already reserved by earlier buses.
    """
    route = scenario.route
    physics = scenario.physics
    weights = scenario.weights

    buses_sorted = sorted(
        scenario.buses,
        key=lambda b: (b.departure_time_min, b.id),
    )

    charger_slots = _init_charger_slots(route)
    timelines: list[BusTimeline] = []

    for bus in buses_sorted:
        plans = generate_charging_plans(bus, route, physics)
        if not plans:
            raise RuntimeError(f"No valid charging plan for bus {bus.id}")

        best_timeline: BusTimeline | None = None
        best_slots: dict[str, list[float]] | None = None
        best_cost = float("inf")

        for plan in plans:
            candidate, new_slots = _simulate_plan(
                bus, plan, route, physics, charger_slots
            )
            hypothetical = timelines + [candidate]
            cost = compute_cost(
                candidate, hypothetical, weights, route, physics
            )
            if cost < best_cost:
                best_cost = cost
                best_timeline = candidate
                best_slots = new_slots

        assert best_timeline is not None and best_slots is not None
        timelines.append(best_timeline)
        charger_slots = best_slots

    return timelines


def load_scenario(path: str | Path) -> Scenario:
    """Load a scenario JSON file."""
    with open(path, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return Scenario.from_dict(data)
