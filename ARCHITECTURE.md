# Electric Bus Charging Scheduler — Architecture

## 1. JSON scenario schema

Each file under `scenarios/` is a **self-contained problem instance**. The scheduler never hardcodes route geometry, fleet size, or tuning knobs.

| Field | Role |
|-------|------|
| `id` | Stable key for UI selection and tests. |
| `name` / `description` | Human-readable metadata shown in Streamlit. |
| `route.segments` | Ordered legs defining distance along the corridor. All distance math derives from this list. |
| `route.charging_stations` | Ordered station IDs **along the forward (Bengaluru→Kochi) corridor**. BK buses use this order; KB uses the reverse. New stations are data-only. |
| `route.chargers_per_station` | Map `station → count`. Models multiple physical plugs without schema changes. Dispatcher keeps one “free at” timestamp per slot. |
| `physics` | Per-scenario vehicle assumptions (`battery_range_km`, `charge_time_min`, `speed_kmh`). Enables different vehicle types or corridors in separate JSON files. |
| `weights` | **Only** place cost tuning lives. `cost.py` multiplies each component by its weight; no magic constants in code. |
| `buses[]` | Fleet input: `id`, `operator`, `direction` (`BK` / `KB`), `departure_time` (`HH:MM`). Direction is an opaque code so new corridors need new codes, not dispatcher branches on city names. |

**Why strings for direction and operator?** Extensibility: new operators or route codes are JSON edits. The Python layer treats them as labels for ordering and cost grouping.

**Why minutes-since-midnight internally?** Simple arithmetic for travel, wait, and queue simulation; UI formats back to `HH:MM`.

---

## 2. Future changes without code changes (or minimal)

| Change | How the design supports it |
|--------|----------------------------|
| More chargers per station | Raise values in `chargers_per_station`; dispatcher already allocates per-slot `free_at` lists. |
| More / different stations | Extend `segments`, `charging_stations`, and `chargers_per_station`; planner enumerates ordered subsets from JSON. |
| More buses | Append to `buses` array. |
| New operators | New `operator` string on bus rows. |
| Multiple routes | Add `route_id` on scenario or bus; load the matching `route` block (data loader change only). |
| Priority buses | Add `priority` on bus; multiply or offset cost in `cost.py`. |
| Time-of-day electricity | Add `tariff_schedule` to scenario; add tariff term in `cost.py` using `charge_start`. |
| Driver shift limits | Add `shift_end_time` on bus; reject or penalize timelines that end after it in simulation. |
| Per-bus range | Add optional `range_km` on bus; planner/dispatcher use `bus.range_km or physics.battery_range_km`. |
| Weight tuning | Edit `weights` in JSON only. |
| New soft rules | New function in `cost.py` + new weight key in JSON. |

---

## 3. Scheduling algorithm

### 3.1 Planning (`planner.py`)

For each bus:

1. Take charging stations in **travel order** (BK: A→B→C→D, KB: D→C→B→A).
2. Enumerate every **subsequence** of length ≥ 2 (at least two charges for the 540 km / 240 km corridor).
3. Keep plans where every leg (origin→first stop, between stops, last stop→destination) ≤ `battery_range_km`.
4. Assert validity before returning.

This is exhaustive over a tiny station set (typically ≪ 2^n plans), so it stays fast and correct.

### 3.2 Dispatching (`dispatcher.py`)

Greedy **sequential** assignment (no MILP):

1. Sort buses by `(departure_time, bus_id)`.
2. For each bus, evaluate every feasible plan by **simulating** the full trip against the **current** charger slot state.
3. At each stop: `charge_start = max(arrival, earliest_slot_free)`; wait = `charge_start - arrival`; slot updated to `charge_end`.
4. Pick the plan with lowest `compute_cost` given timelines already committed.
5. Persist slot state for later buses.

Conflict resolution is implicit: earlier-departing buses (or same time, lower ID) reserve chargers first; later buses wait in simulation.

### 3.3 Cost (`cost.py`)

Per bus timeline:

- **Individual:** total wait minutes.
- **Operator:** (average wait of same operator) − (this bus wait) — discourages one bus absorbing all fleet delay.
- **Overall:** actual arrival − baseline arrival (travel + charges, **no** queue wait).

Weighted sum uses scenario `weights`.

### 3.4 Why this scales for MVP

- Station count is small → plan enumeration is cheap.
- Per-bus simulation is O(stops × chargers at station).
- Overall ~O(buses × plans × stops), fine for tens of buses and few stations.
- Easy to extend: swap plan picker (e.g. beam search) or add tariff terms without touching UI.

Global optimum is not guaranteed; the tradeoff is transparency, testability, and JSON-driven behavior.

---

## 4. Module map

```
app.py              Streamlit: scenario pick, input table, timetables, station queues
scheduler/models.py Dataclasses + scenario JSON parsing
scheduler/planner.py Feasible charging station subsets
scheduler/dispatcher.py Greedy plan choice + charger simulation
scheduler/cost.py   Weighted soft costs
scenarios/*.json    Problem instances
```

---

## 5. Running

```bash
pip install -r requirements.txt
streamlit run app.py
```

Regenerate scenario JSON from `scripts/build_scenarios.py` after editing departure logic there.
