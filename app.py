import pandas as pd
import plotly.express as px
import streamlit as st

from scheduler import calculate_metrics, schedule_greedy


st.set_page_config(page_title="Q-Charge Fair", layout="wide")
st.title("Q-Charge Fair")
st.caption("A small, grid-aware EV charging scheduling demo")

with st.sidebar:
    st.header("Scenario")
    grid_limit_kw = st.number_input(
        "Grid limit (kW)", min_value=1.0, max_value=500.0,
        value=10.0, step=1.0
    )
    n_slots = st.slider("Number of time slots", 2, 12, 4)
    slot_minutes = st.selectbox("Minutes per slot", [15, 30, 60], index=2)

    st.subheader("Vehicles")
    vehicles = []
    for i in range(3):
        st.markdown(f"**EV {i + 1}**")
        energy = st.number_input(
            f"Energy needed (kWh) — EV {i + 1}",
            min_value=0.0, max_value=50.0, value=[4.0, 3.0, 5.0][i],
            step=1.0, key=f"energy_{i}"
        )
        departure = st.number_input(
            f"Departure slot — EV {i + 1}",
            min_value=1, max_value=n_slots, value=min(i + 2, n_slots),
            step=1, key=f"departure_{i}"
        )
        priority = st.selectbox(
            f"Priority — EV {i + 1}",
            [1, 2, 3], index=2 - i, key=f"priority_{i}"
        )
        max_kw = st.number_input(
            f"Max charge rate (kW) — EV {i + 1}",
            min_value=1.0, max_value=50.0, value=7.0,
            step=1.0, key=f"max_kw_{i}"
        )

        vehicles.append({
            "id": f"EV{i + 1}",
            "energy_needed_kwh": energy,
            # Departure slot is exclusive: a vehicle can charge in slots
            # 0 through departure_slot - 1.
            "departure_slot": int(departure),
            "priority": int(priority),
            "max_charge_kw": max_kw,
        })

scenario = {
    "grid_limit_kw": grid_limit_kw,
    "n_slots": n_slots,
    "slot_minutes": slot_minutes,
    "vehicles": vehicles,
}

if st.button("Generate schedule", type="primary"):
    result = schedule_greedy(scenario)
    metrics = calculate_metrics(scenario, result)

    left, right = st.columns(2)
    left.metric("Unmet energy", f"{metrics['unmet_energy_kwh']} kWh")
    right.metric("Peak load", f"{metrics['peak_load_kw']} kW")

    left, right = st.columns(2)
    left.metric("Grid-limit violation", f"{metrics['grid_violation_kwh']} kWh")
    right.metric("Fairness (Jain index)", f"{metrics['fairness']}")

    st.subheader("Charging schedule")
    schedule_df = pd.DataFrame(result["schedule"])

    if schedule_df.empty:
        st.info("No charging was scheduled for this scenario.")
    else:
        st.dataframe(schedule_df, use_container_width=True)

        fig = px.bar(
            schedule_df,
            x="slot",
            y="energy_kwh",
            color="vehicle",
            barmode="stack",
            title="Energy scheduled in each time slot",
        )
        st.plotly_chart(fig, use_container_width=True)

    load_df = pd.DataFrame({
        "slot": list(range(n_slots)),
        "load_kwh": metrics["slot_load_kwh"],
    })
    load_df["load_kw"] = load_df["load_kwh"] * 60 / slot_minutes

    fig = px.line(
        load_df,
        x="slot",
        y="load_kw",
        markers=True,
        title="Grid load by time slot",
    )
    fig.add_hline(
        y=grid_limit_kw,
        line_dash="dash",
        annotation_text="Grid limit",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.caption(f"Scheduler runtime: {result['runtime_seconds']:.6f} seconds")
else:
    st.info("Adjust the scenario in the sidebar, then click **Generate schedule**.")