"""Generate feasible charging station plans for each bus."""

from __future__ import annotations

from itertools import combinations

from scheduler.models import Bus, Physics, Route


def _validate_plan(
    bus: Bus,
    route: Route,
    physics: Physics,
    stations: list[str],
) -> bool:
    """Return True if every leg is within battery range."""
    if len(stations) < 2:
        return False

    ordered = route.stations_for_direction(bus.direction)
    station_set = set(stations)
    if not all(s in ordered for s in stations):
        return False
    indices = [ordered.index(s) for s in stations]
    if indices != sorted(indices):
        return False

    start = route.start_node(bus.direction)
    end = route.end_node(bus.direction)
    pos = start
    for station in stations:
        leg = route.distance_for_bus(bus.direction, pos, station)
        if leg > physics.battery_range_km + 1e-9:
            return False
        pos = station
    final_leg = route.distance_for_bus(bus.direction, pos, end)
    if final_leg > physics.battery_range_km + 1e-9:
        return False
    return True


def generate_charging_plans(
    bus: Bus,
    route: Route,
    physics: Physics,
) -> list[list[str]]:
    """
    Enumerate all valid ordered charging station subsets (at least 2 stops).

    Returns a list of plans; each plan is an ordered list of station names.
    """
    ordered_stations = route.stations_for_direction(bus.direction)
    n = len(ordered_stations)
    plans: list[list[str]] = []

    for size in range(2, n + 1):
        for combo in combinations(range(n), size):
            plan = [ordered_stations[i] for i in combo]
            if _validate_plan(bus, route, physics, plan):
                plans.append(plan)

    for plan in plans:
        assert _validate_plan(bus, route, physics, plan), (
            f"Invalid plan {plan} for bus {bus.id}"
        )

    return plans


# Spec alias: singular name, each plan is a list of station names.
generate_charging_plan = generate_charging_plans
