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

from typing import Dict, List

from qiskit.primitives import StatevectorSampler
from qiskit_algorithms import QAOA
from qiskit_algorithms.optimizers import COBYLA
from qiskit_optimization import QuadraticProgram
from qiskit_optimization.algorithms import MinimumEigenOptimizer


def build_problem() -> QuadraticProgram:
    """Create a tiny binary optimization problem."""
    # 3 EVs, 2 time slots, 1 kWh per binary decision.
    # x[ev, slot] = 1 means charge this EV by 1 kWh in this slot.
    qp = QuadraticProgram("ev_charging_qaoa")

    # Add one binary variable per EV-slot pair.
    for ev in range(3):
        for slot in range(2):
            qp.binary_var(name=f"x_{ev}_{slot}")

    # Each EV cannot exceed its requested energy across both slots.
    energy_requests = [2, 1, 3]
    for ev, requested in enumerate(energy_requests):
        linear = {f"x_{ev}_{slot}": 1.0 for slot in range(2)}
        qp.linear_constraint(linear, "<=", requested, f"energy_ev_{ev}")

    # Each slot has a grid limit of 2 kWh.
    for slot in range(2):
        linear = {f"x_{ev}_{slot}": 1.0 for ev in range(3)}
        qp.linear_constraint(linear, "<=", 2, f"grid_slot_{slot}")

    # Higher-priority EVs get a bigger reward for being charged.
    # Because Qiskit minimizes the objective, we use negative coefficients.
    linear = {}
    priorities = [3, 2, 1]
    for ev, priority in enumerate(priorities):
        for slot in range(2):
            linear[f"x_{ev}_{slot}"] = -priority
    qp.minimize(linear=linear)

    return qp


def solve_qaoa() -> List[Dict[str, float]]:
    """Solve the small scheduling problem with QAOA and return schedule rows."""
    qp = build_problem()

    # Local statevector simulator + classical optimizer.
    sampler = StatevectorSampler()
    qaoa = QAOA(sampler=sampler, optimizer=COBYLA(maxiter=80), reps=1)
    optimizer = MinimumEigenOptimizer(qaoa)
    result = optimizer.solve(qp)

    schedule: List[Dict[str, float]] = []
    for ev in range(3):
        for slot in range(2):
            variable_name = f"x_{ev}_{slot}"
            value = int(round(result.x[qp.variables_index[variable_name]]))
            if value:
                schedule.append({
                    "vehicle": f"EV{ev + 1}",
                    "slot": slot,
                    "energy_kwh": 1.0,
                })

    return schedule


if __name__ == "__main__":
    schedule = solve_qaoa()
    print("QAOA schedule:")
    for item in schedule:
        print(item)
