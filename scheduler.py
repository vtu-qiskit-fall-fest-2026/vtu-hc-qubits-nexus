from time import perf_counter


def schedule_greedy(scenario):
    """
    Assign charging in whole kWh blocks.

    Each vehicle can receive at most one block per time slot.
    A slot has a total energy limit of:
        grid_limit_kw * slot_minutes / 60

    Higher priority vehicles are scheduled first. Earlier departures
    break ties.
    """
    start = perf_counter()

    vehicles = scenario["vehicles"]
    n_slots = scenario["n_slots"]
    slot_minutes = scenario["slot_minutes"]
    grid_limit_kw = scenario["grid_limit_kw"]

    # For this starter app, use 1 kWh blocks. This keeps the schedule
    # understandable and is only an approximation of real charging.
    slot_capacity_kwh = grid_limit_kw * slot_minutes / 60

    remaining = {
        vehicle["id"]: float(vehicle["energy_needed_kwh"])
        for vehicle in vehicles
    }

    schedule = []

    # Fill early slots first, prioritizing urgent and high-priority vehicles.
    for slot in range(n_slots):
        slot_used = 0.0

        ordered = sorted(
            vehicles,
            key=lambda v: (
                slot >= v["departure_slot"],
                -v["priority"],
                v["departure_slot"],
            ),
        )

        for vehicle in ordered:
            vehicle_id = vehicle["id"]

            # Do not charge after the departure slot.
            if slot >= vehicle["departure_slot"]:
                continue

            if remaining[vehicle_id] <= 0:
                continue

            vehicle_slot_limit = (
                vehicle["max_charge_kw"] * slot_minutes / 60
            )
            amount = min(
                1.0,
                remaining[vehicle_id],
                vehicle_slot_limit,
                slot_capacity_kwh - slot_used,
            )

            if amount > 0:
                schedule.append({
                    "vehicle": vehicle_id,
                    "slot": slot,
                    "energy_kwh": round(amount, 2),
                    "priority": vehicle["priority"],
                })
                remaining[vehicle_id] -= amount
                slot_used += amount

    elapsed_seconds = perf_counter() - start

    return {
        "schedule": schedule,
        "remaining_kwh": {
            vehicle_id: round(amount, 2)
            for vehicle_id, amount in remaining.items()
        },
        "runtime_seconds": elapsed_seconds,
    }


def calculate_metrics(scenario, result):
    """Calculate simple schedule metrics."""
    vehicles = scenario["vehicles"]
    n_slots = scenario["n_slots"]
    slot_minutes = scenario["slot_minutes"]
    grid_limit_kw = scenario["grid_limit_kw"]

    slot_load_kwh = [0.0] * n_slots
    charged_by_vehicle = {vehicle["id"]: 0.0 for vehicle in vehicles}

    for item in result["schedule"]:
        slot_load_kwh[item["slot"]] += item["energy_kwh"]
        charged_by_vehicle[item["vehicle"]] += item["energy_kwh"]

    unmet_kwh = sum(result["remaining_kwh"].values())

    # Jain's fairness index: 1 means equal fulfillment ratios.
    fulfillment_ratios = []
    for vehicle in vehicles:
        requested = vehicle["energy_needed_kwh"]
        if requested > 0:
            fulfillment_ratios.append(
                charged_by_vehicle[vehicle["id"]] / requested
            )

    if fulfillment_ratios:
        total = sum(fulfillment_ratios)
        squares = sum(value * value for value in fulfillment_ratios)
        fairness = (total * total) / (len(fulfillment_ratios) * squares)
    else:
        fairness = 1.0

    slot_capacity_kwh = grid_limit_kw * slot_minutes / 60
    violations = sum(
        max(0.0, load - slot_capacity_kwh)
        for load in slot_load_kwh
    )

    return {
        "unmet_energy_kwh": round(unmet_kwh, 2),
        "peak_load_kw": round(
            max(slot_load_kwh, default=0.0) * 60 / slot_minutes, 2
        ),
        "grid_violation_kwh": round(violations, 2),
        "fairness": round(fairness, 3),
        "slot_load_kwh": [round(load, 2) for load in slot_load_kwh],
    }