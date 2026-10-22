"""Tiny QAOA example for a small EV charging schedule.

This example uses the current Qiskit Optimization API to solve a simple
binary optimization problem on a local statevector simulator.

We model six binary decisions:
    x[ev, slot] = 1 means charge this EV by 1 kWh in this slot.

Constraints:
- each EV can charge at most its requested energy across all slots
- each slot has a grid limit of 2 kWh

Objective:
- reward higher-priority EVs more strongly
- minimize unmet energy and prefer more valuable charging decisions
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from qiskit.primitives import StatevectorSampler
from qiskit_algorithms import QAOA
from qiskit_algorithms.optimizers import COBYLA
from qiskit_optimization import QuadraticProgram
from qiskit_optimization.algorithms import MinimumEigenOptimizer


NUM_EVS = 2
NUM_SLOTS = 1
ENERGY_REQUESTS = [1, 1]
PRIORITIES = [2, 1]
GRID_LIMIT_KWH = 1


def build_problem() -> QuadraticProgram:
    """Create a very small binary EV charging problem."""
    qp = QuadraticProgram("tiny_ev_charging_qaoa")

    # x_ev_slot = 1 means charge that EV by 1 kWh in that slot.
    for ev in range(NUM_EVS):
        for slot in range(NUM_SLOTS):
            qp.binary_var(name=f"x_{ev}_{slot}")

    # Respect each EV's energy request.
    for ev, requested in enumerate(ENERGY_REQUESTS):
        qp.linear_constraint(
            {f"x_{ev}_{slot}": 1.0 for slot in range(NUM_SLOTS)},
            "<=",
            requested,
            f"energy_ev_{ev}",
        )

    # Respect the grid limit in each slot.
    for slot in range(NUM_SLOTS):
        qp.linear_constraint(
            {f"x_{ev}_{slot}": 1.0 for ev in range(NUM_EVS)},
            "<=",
            GRID_LIMIT_KWH,
            f"grid_slot_{slot}",
        )

    # Reward charging higher-priority EVs.
    qp.minimize(
        linear={
            f"x_{ev}_{slot}": -PRIORITIES[ev]
            for ev in range(NUM_EVS)
            for slot in range(NUM_SLOTS)
        }
    )

    return qp


def solve_qaoa() -> List[Dict[str, float]]:
    """Solve the tiny scheduling problem and save its optimized QAOA circuit."""
    qp = build_problem()

    # Small settings to keep this simulator example lightweight.
    sampler = StatevectorSampler(default_shots=64, seed=7)
    qaoa = QAOA(
        sampler=sampler,
        optimizer=COBYLA(maxiter=5),
        reps=1,
    )

    result = MinimumEigenOptimizer(qaoa).solve(qp)

    # Get the optimized circuit and parameters from this QAOA run.
    solver_result = result.min_eigen_solver_result

    if solver_result is None or solver_result.optimal_circuit is None:
        raise RuntimeError("QAOA did not return an optimized circuit.")

    circuit = solver_result.optimal_circuit
    optimal_parameters = solver_result.optimal_parameters

    # Bind the optimized parameter values to the circuit.
    if circuit.parameters and optimal_parameters:
        circuit = circuit.assign_parameters(
            optimal_parameters,
            inplace=False,
        )

    # Add measurements for the circuit diagram if it has none.
    circuit_to_draw = circuit.copy()
    if circuit_to_draw.num_clbits == 0:
        circuit_to_draw.measure_all()

    # Print a text version in the terminal.
    print("\nQAOA circuit:")
    print(circuit_to_draw.draw(output="text"))

    # Save a PNG beside this Python file.
    figure = circuit_to_draw.decompose(reps=3).draw(
        output="mpl",
        fold=-1,
        style="bw",
    )
    image_path = Path(__file__).resolve().with_name(
        "qcharge_qaoa_circuit.png"
    )
    figure.savefig(image_path, dpi=250, bbox_inches="tight")
    print(f"\nSaved circuit: {image_path}")

    # Convert the selected binary variables into schedule rows.
    schedule = []
    for ev in range(NUM_EVS):
        for slot in range(NUM_SLOTS):
            name = f"x_{ev}_{slot}"
            index = qp.variables_index[name]

            if int(round(result.x[index])) == 1:
                schedule.append({
                    "vehicle": f"EV{ev + 1}",
                    "slot": slot,
                    "energy_kwh": 1.0,
                })

    return schedule


if __name__ == "__main__":
    print("QAOA schedule:")
    for item in solve_qaoa():
        print(item)