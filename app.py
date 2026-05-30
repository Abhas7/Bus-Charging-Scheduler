"""Streamlit UI for the electric bus charging scheduler."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from scheduler.dispatcher import load_scenario, schedule
from scheduler.models import format_time_minutes

SCENARIOS_DIR = Path(__file__).parent / "scenarios"


@st.cache_data
def load_all_scenario_ids() -> list[str]:
    return sorted(p.stem for p in SCENARIOS_DIR.glob("scenario_*.json"))


@st.cache_data
def run_schedule(scenario_id: str):
    scenario = load_scenario(SCENARIOS_DIR / f"{scenario_id}.json")
    timelines = schedule(scenario)
    return scenario, timelines


def _bus_input_df(scenario) -> pd.DataFrame:
    rows = []
    for bus in sorted(
        scenario.buses,
        key=lambda b: (b.departure_time_min, b.id),
    ):
        dep_h = bus.departure_time_min // 60
        dep_m = bus.departure_time_min % 60
        rows.append(
            {
                "Bus ID": bus.id,
                "Operator": bus.operator,
                "Direction": bus.direction,
                "Departure Time": f"{dep_h:02d}:{dep_m:02d}",
            }
        )
    return pd.DataFrame(rows)


def _timetable_rows(timelines) -> list[dict]:
    rows: list[dict] = []
    for tl in sorted(timelines, key=lambda t: (t.departure_time, t.bus_id)):
        dep = format_time_minutes(tl.departure_time)
        final = format_time_minutes(tl.arrival_time)
        if not tl.charging_stops:
            rows.append(
                {
                    "Bus ID": tl.bus_id,
                    "Operator": tl.operator,
                    "Direction": tl.direction,
                    "Dep. Time": dep,
                    "Station": "—",
                    "Arrival": "—",
                    "Wait (min)": 0.0,
                    "Charge Start": "—",
                    "Charge End": "—",
                    "Final Arrival": final,
                }
            )
            continue
        for idx, stop in enumerate(tl.charging_stops):
            rows.append(
                {
                    "Bus ID": tl.bus_id,
                    "Operator": tl.operator,
                    "Direction": tl.direction,
                    "Dep. Time": dep if idx == 0 else "",
                    "Station": stop.station,
                    "Arrival": format_time_minutes(stop.arrival_time),
                    "Wait (min)": round(stop.wait_time, 1),
                    "Charge Start": format_time_minutes(stop.charge_start),
                    "Charge End": format_time_minutes(stop.charge_end),
                    "Final Arrival": final if idx == len(tl.charging_stops) - 1 else "",
                }
            )
    return rows


def _station_queues(timelines, stations: list[str]) -> dict[str, pd.DataFrame]:
    result: dict[str, list[dict]] = {s: [] for s in stations}
    for tl in timelines:
        for stop in tl.charging_stops:
            result[stop.station].append(
                {
                    "bus_id": tl.bus_id,
                    "operator": tl.operator,
                    "direction": tl.direction,
                    "charge_start": stop.charge_start,
                    "charge_end": stop.charge_end,
                    "wait": stop.wait_time,
                }
            )

    frames: dict[str, pd.DataFrame] = {}
    for station in stations:
        events = sorted(
            result[station],
            key=lambda e: (e["charge_start"], e["bus_id"]),
        )
        rows = []
        for order, ev in enumerate(events, start=1):
            rows.append(
                {
                    "Order": order,
                    "Bus ID": ev["bus_id"],
                    "Operator": ev["operator"],
                    "Direction": ev["direction"],
                    "Charge Start": format_time_minutes(ev["charge_start"]),
                    "Charge End": format_time_minutes(ev["charge_end"]),
                    "Wait (min)": round(ev["wait"], 1),
                }
            )
        frames[station] = pd.DataFrame(rows)
    return frames


def main() -> None:
    st.set_page_config(page_title="Bus Charging Scheduler", layout="wide")
    st.title("Electric Bus Charging Scheduler")

    scenario_ids = load_all_scenario_ids()
    if not scenario_ids:
        st.error("No scenario files found in scenarios/")
        return

    scenario_id = st.selectbox("Select scenario", scenario_ids)
    scenario, timelines = run_schedule(scenario_id)

    st.subheader(scenario.name)
    st.caption(scenario.description)
    w = scenario.weights
    st.write(
        f"**Weights:** individual={w.get('individual', 1.0)}, "
        f"operator={w.get('operator', 1.0)}, overall={w.get('overall', 1.0)}"
    )

    st.markdown("### Input — Bus Departures")
    st.dataframe(_bus_input_df(scenario), use_container_width=True, hide_index=True)

    st.markdown("### Per-bus timetable")
    timetable_df = pd.DataFrame(_timetable_rows(timelines))
    bus_filter = st.multiselect(
        "Filter buses (empty = all)",
        options=sorted({tl.bus_id for tl in timelines}),
        default=[],
    )
    if bus_filter:
        timetable_df = timetable_df[timetable_df["Bus ID"].isin(bus_filter)]

    with st.expander("All buses (table)", expanded=False):
        st.dataframe(timetable_df, use_container_width=True, hide_index=True)

    for tl in sorted(timelines, key=lambda t: (t.departure_time, t.bus_id)):
        if bus_filter and tl.bus_id not in bus_filter:
            continue
        dep = format_time_minutes(tl.departure_time)
        final = format_time_minutes(tl.arrival_time)
        with st.expander(
            f"{tl.bus_id} · {tl.operator} · {tl.direction} · dep {dep} · arr {final}",
            expanded=False,
        ):
            bus_rows = [r for r in _timetable_rows([tl]) if r["Bus ID"]]
            st.dataframe(
                pd.DataFrame(bus_rows),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("### Per-station charging queue")
    station_frames = _station_queues(timelines, scenario.route.charging_stations)
    for station in scenario.route.charging_stations:
        st.markdown(f"**Station {station}**")
        df = station_frames[station]
        if df.empty:
            st.caption("No charging events.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
