import argparse
import json
import sys
from pathlib import Path

_src_dir = Path(__file__).resolve().parent
_root_dir = _src_dir.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

DEFAULT_INPUT_DIR = _root_dir / "input_data"
DEFAULT_OUTPUT_PATH = _root_dir / "output" / "results.txt"
DEFAULT_LOG_PATH = _root_dir / "output" / "terminal_output.log"


def read_json(path):
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def read_optional_json(path):
    if not path.exists():
        return {}

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return {}

    return json.loads(content)


def ensure_matrix(name, value):
    if not isinstance(value, list) or not value or not all(isinstance(row, list) and row for row in value):
        raise ValueError(f"{name} must be a non-empty matrix.")

    row_length = len(value[0])
    if any(len(row) != row_length for row in value):
        raise ValueError(f"{name} must have the same number of columns in every row.")

    return value


def ensure_freeze(name, value, expected_items):
    if len(value) != expected_items:
        raise ValueError(f"{name} must contain one [mode, remaining_periods] entry per item.")

    return value


def ensure_mode_constraints(name, constraints, item_key, max_items, max_modes, n_periods):
    if constraints is None:
        return []
    if not isinstance(constraints, list):
        raise ValueError(f"user_constraints.{name} must be a list.")

    normalized_constraints = []
    seen = {}
    for position, constraint in enumerate(constraints):
        if not isinstance(constraint, dict):
            raise ValueError(f"user_constraints.{name}[{position}] must be an object.")

        try:
            item = int(constraint[item_key])
            time_step = int(constraint["time"])
            mode = int(constraint["mode"])
        except KeyError as exc:
            raise ValueError(
                f"user_constraints.{name}[{position}] is missing required key {exc.args[0]!r}."
            ) from exc

        if item < 0 or item >= max_items:
            raise ValueError(
                f"user_constraints.{name}[{position}].{item_key} must be between 0 and {max_items - 1}."
            )
        if time_step < 0 or time_step >= n_periods:
            raise ValueError(
                f"user_constraints.{name}[{position}].time must be between 0 and {n_periods - 1}."
            )
        if mode < 0 or mode >= max_modes:
            raise ValueError(
                f"user_constraints.{name}[{position}].mode must be between 0 and {max_modes - 1}."
            )

        key = (item, time_step)
        if key in seen and seen[key] != mode:
            raise ValueError(
                f"user_constraints.{name} contains conflicting modes for {item_key} {item} "
                f"at time {time_step}."
            )
        seen[key] = mode

        normalized_constraints.append(
            {
                item_key: item,
                "time": time_step,
                "mode": mode,
            }
        )

    return normalized_constraints


def ensure_topology(topology, n_pumps, n_inlets):
    if not isinstance(topology, dict):
        raise ValueError("topology.json must contain an object.")

    elements = topology.get("elements")
    connections = topology.get("connections", [])
    equations = topology.get("equations")
    if not isinstance(elements, list) or not elements:
        raise ValueError("topology.elements must be a non-empty list.")
    if not isinstance(connections, list):
        raise ValueError("topology.connections must be a list.")
    if not isinstance(equations, list) or not equations:
        raise ValueError("topology.equations must be a non-empty list.")

    element_by_id = {}
    pump_elements = {}
    inlet_elements = {}
    allowed_types = {"storage", "level", "inflow", "pump", "inlet"}
    for position, element in enumerate(elements):
        if not isinstance(element, dict):
            raise ValueError(f"topology.elements[{position}] must be an object.")

        element_id = element.get("id")
        element_type = element.get("type")
        if not element_id:
            raise ValueError(f"topology.elements[{position}] must have an id.")
        if element_id in element_by_id:
            raise ValueError(f"topology element id {element_id!r} is duplicated.")
        if element_type not in allowed_types:
            raise ValueError(
                f"topology.elements[{position}].type must be one of {sorted(allowed_types)}."
            )

        if element_type in {"pump", "inlet"}:
            if "upstream" not in element or "downstream" not in element:
                raise ValueError(f"{element_id} must define both upstream and downstream.")
            if "index" not in element:
                raise ValueError(f"{element_id} must define an index.")

            index = int(element["index"])
            if element_type == "pump":
                if index < 0 or index >= n_pumps:
                    raise ValueError(f"{element_id}.index must be between 0 and {n_pumps - 1}.")
                pump_elements[element_id] = index
            else:
                if index < 0 or index >= n_inlets:
                    raise ValueError(f"{element_id}.index must be between 0 and {n_inlets - 1}.")
                inlet_elements[element_id] = index

        if element_type == "inflow":
            if "upstream" in element:
                raise ValueError(f"{element_id} is an inflow and must not define upstream.")
            if "downstream" not in element:
                raise ValueError(f"{element_id} must define downstream.")
            if "series" not in element:
                raise ValueError(f"{element_id} must define a time-series name.")

        if element_type == "level":
            if "downstream" in element:
                raise ValueError(f"{element_id} is a level element and must not define downstream.")
            if "series" not in element:
                raise ValueError(f"{element_id} must define a time-series name.")

        element_by_id[element_id] = element

    for position, connection in enumerate(connections):
        if not isinstance(connection, dict):
            raise ValueError(f"topology.connections[{position}] must be an object.")
        source = connection.get("from")
        target = connection.get("to")
        via = connection.get("via")
        if source not in element_by_id:
            raise ValueError(f"topology.connections[{position}].from references unknown element {source!r}.")
        if target not in element_by_id:
            raise ValueError(f"topology.connections[{position}].to references unknown element {target!r}.")
        if via is not None:
            if via not in element_by_id:
                raise ValueError(f"topology.connections[{position}].via references unknown element {via!r}.")
            via_element = element_by_id[via]
            if via_element["type"] not in {"pump", "inlet"}:
                raise ValueError(f"topology.connections[{position}].via must be a pump or inlet.")
            if via_element["upstream"] != source or via_element["downstream"] != target:
                raise ValueError(f"topology connection through {via!r} does not match its upstream/downstream.")

    storage_balance = None
    head_constraints = []
    pump_head_mode_constraints = []
    for position, equation in enumerate(equations):
        if not isinstance(equation, dict):
            raise ValueError(f"topology.equations[{position}] must be an object.")

        equation_type = equation.get("type")
        if equation_type == "storage_balance":
            if storage_balance is not None:
                raise ValueError("Only one storage_balance equation is supported.")
            storage = equation.get("storage")
            if storage not in element_by_id or element_by_id[storage]["type"] != "storage":
                raise ValueError("storage_balance.storage must reference a storage element.")

            inflows = equation.get("inflows", [])
            outflows = equation.get("outflows", [])
            for element_id in inflows:
                if element_id not in element_by_id:
                    raise ValueError(f"storage_balance.inflows references unknown element {element_id!r}.")
                element = element_by_id[element_id]
                if element["type"] not in {"inflow", "pump", "inlet"}:
                    raise ValueError(f"storage_balance.inflows element {element_id!r} cannot carry flow.")
                if element.get("downstream") != storage:
                    raise ValueError(f"storage_balance.inflows element {element_id!r} must flow into {storage!r}.")
            for element_id in outflows:
                if element_id not in element_by_id:
                    raise ValueError(f"storage_balance.outflows references unknown element {element_id!r}.")
                element = element_by_id[element_id]
                if element["type"] not in {"pump", "inlet"}:
                    raise ValueError(f"storage_balance.outflows element {element_id!r} cannot be an outflow.")
                if element.get("upstream") != storage:
                    raise ValueError(f"storage_balance.outflows element {element_id!r} must flow out of {storage!r}.")

            storage_balance = {
                "storage": storage,
                "inflows": inflows,
                "outflows": outflows,
            }
        elif equation_type == "hydraulic_head_constraint":
            upper = equation.get("upper")
            lower = equation.get("lower")
            controlled_elements = equation.get("controlled_elements", [])
            if upper not in element_by_id or element_by_id[upper]["type"] != "storage":
                raise ValueError("hydraulic_head_constraint.upper must reference a storage element.")
            if lower not in element_by_id or element_by_id[lower]["type"] != "level":
                raise ValueError("hydraulic_head_constraint.lower must reference a level element.")
            for element_id in controlled_elements:
                if element_id not in element_by_id:
                    raise ValueError(
                        f"hydraulic_head_constraint.controlled_elements references unknown element {element_id!r}."
                    )
                element = element_by_id[element_id]
                if element["type"] != "inlet":
                    raise ValueError(f"hydraulic_head_constraint element {element_id!r} must be an inlet.")
                if element.get("upstream") != upper or element.get("downstream") != lower:
                    raise ValueError(
                        f"hydraulic_head_constraint element {element_id!r} must connect {upper!r} to {lower!r}."
                    )

            head_constraints.append(
                {
                    "upper": upper,
                    "lower": lower,
                    "controlled_elements": controlled_elements,
                }
            )
        elif equation_type == "head_based_pump_mode_constraint":
            upper = equation.get("upper")
            lower = equation.get("lower")
            controlled_elements = equation.get("controlled_elements", [])
            required_mode = int(equation.get("required_mode", 0))
            condition = equation.get("condition", "upper_above_lower")

            if condition != "upper_above_lower":
                raise ValueError("head_based_pump_mode_constraint.condition must be 'upper_above_lower'.")
            if upper not in element_by_id or element_by_id[upper]["type"] != "storage":
                raise ValueError("head_based_pump_mode_constraint.upper must reference a storage element.")
            if lower not in element_by_id or element_by_id[lower]["type"] != "level":
                raise ValueError("head_based_pump_mode_constraint.lower must reference a level element.")
            if required_mode < 0:
                raise ValueError("head_based_pump_mode_constraint.required_mode must be non-negative.")

            for element_id in controlled_elements:
                if element_id not in element_by_id:
                    raise ValueError(
                        f"head_based_pump_mode_constraint.controlled_elements references unknown element {element_id!r}."
                    )
                element = element_by_id[element_id]
                if element["type"] != "pump":
                    raise ValueError(f"head_based_pump_mode_constraint element {element_id!r} must be a pump.")
                if element.get("upstream") != upper or element.get("downstream") != lower:
                    raise ValueError(
                        f"head_based_pump_mode_constraint element {element_id!r} must connect {upper!r} to {lower!r}."
                    )

            pump_head_mode_constraints.append(
                {
                    "upper": upper,
                    "lower": lower,
                    "controlled_elements": controlled_elements,
                    "required_mode": required_mode,
                    "condition": condition,
                }
            )
        else:
            raise ValueError(f"Unsupported topology equation type {equation_type!r}.")

    if storage_balance is None:
        raise ValueError("topology.equations must include a storage_balance equation.")

    if len(set(pump_elements.values())) != n_pumps:
        raise ValueError("topology.elements must include exactly one element for each pump index.")
    if len(set(inlet_elements.values())) != n_inlets:
        raise ValueError("topology.elements must include exactly one element for each inlet index.")

    return {
        "elements": elements,
        "element_by_id": element_by_id,
        "pump_elements": pump_elements,
        "inlet_elements": inlet_elements,
        "storage_balance": storage_balance,
        "head_constraints": head_constraints,
        "pump_head_mode_constraints": pump_head_mode_constraints,
    }


def load_input_data(input_dir):
    input_dir = Path(input_dir)
    pumps = read_json(input_dir / "pumps.json")
    inlets = read_json(input_dir / "inlets.json")
    storage = read_json(input_dir / "storage.json")
    horizon = read_json(input_dir / "horizon.json")
    topology = read_json(input_dir / "topology.json")
    user_constraints = read_optional_json(input_dir / "user_constraints.json")

    q_pumps = ensure_matrix("pumps.flow_by_mode", pumps["flow_by_mode"])
    min_mode_duration = ensure_matrix("pumps.min_mode_duration", pumps["min_mode_duration"])
    q_inlets = ensure_matrix("inlets.flow_by_mode", inlets["flow_by_mode"])

    n_pumps = len(q_pumps[0])
    n_pump_modes = len(q_pumps)
    n_inlets = len(q_inlets[0])
    n_inlet_modes = len(q_inlets)
    n_periods = int(horizon["n_periods"])

    if len(min_mode_duration) != n_pump_modes or len(min_mode_duration[0]) != n_pumps:
        raise ValueError("pumps.min_mode_duration must match pumps.flow_by_mode dimensions.")

    if len(horizon["discharge_sequence"]) < n_periods:
        raise ValueError("horizon.discharge_sequence must contain at least n_periods values.")
    if len(horizon["sea_level"]) < n_periods:
        raise ValueError("horizon.sea_level must contain at least n_periods values.")
    if len(horizon["desired_storage_level"]) < n_periods:
        raise ValueError("horizon.desired_storage_level must contain at least n_periods values.")

    pump_freeze = ensure_freeze("pumps.freeze", pumps.get("freeze", [[0, 0]] * n_pumps), n_pumps)
    inlet_freeze = ensure_freeze("inlets.freeze", inlets.get("freeze", [[0, 0]] * n_inlets), n_inlets)
    pump_mode_constraints = ensure_mode_constraints(
        "pumps",
        user_constraints.get("pumps", []),
        "pump",
        n_pumps,
        n_pump_modes,
        n_periods,
    )
    inlet_mode_constraints = ensure_mode_constraints(
        "inlets",
        user_constraints.get("inlets", []),
        "inlet",
        n_inlets,
        n_inlet_modes,
        n_periods,
    )
    topology = ensure_topology(topology, n_pumps, n_inlets)

    return {
        "q_pumps": q_pumps,
        "n_pumps": n_pumps,
        "n_pump_modes": n_pump_modes,
        "q_inlets": q_inlets,
        "n_inlets": n_inlets,
        "n_inlet_modes": n_inlet_modes,
        "min_mode_duration": min_mode_duration,
        "n_periods": n_periods,
        "discharge_sequence": horizon["discharge_sequence"],
        "sea_level": horizon["sea_level"],
        "desired_storage_level": horizon["desired_storage_level"],
        "time_series": {
            "discharge_sequence": horizon["discharge_sequence"],
            "sea_level": horizon["sea_level"],
            "desired_storage_level": horizon["desired_storage_level"],
        },
        "storage_area": storage["area"],
        "initial_storage_volume": storage["initial_volume"],
        "min_storage_volume": storage["min_volume"],
        "max_storage_volume": storage["max_volume"],
        "pump_freeze": pump_freeze,
        "inlet_freeze": inlet_freeze,
        "closed_inlet_mode": inlets.get("closed_mode", 0),
        "pump_mode_constraints": pump_mode_constraints,
        "inlet_mode_constraints": inlet_mode_constraints,
        "topology": topology,
    }


def build_model(data):
    try:
        import pyomo.environ as pyo
    except ModuleNotFoundError as exc:
        raise RuntimeError("Pyomo is not installed. Run: pip install -r requirements.txt") from exc

    q_pumps = data["q_pumps"]
    n_pumps = data["n_pumps"]
    n_pump_modes = data["n_pump_modes"]
    q_inlets = data["q_inlets"]
    n_inlets = data["n_inlets"]
    n_inlet_modes = data["n_inlet_modes"]
    min_mode_duration = data["min_mode_duration"]
    n_periods = data["n_periods"]
    desired_storage_level = data["desired_storage_level"]
    time_series = data["time_series"]
    storage_area = data["storage_area"]
    initial_storage_volume = data["initial_storage_volume"]
    min_storage_volume = data["min_storage_volume"]
    max_storage_volume = data["max_storage_volume"]
    pump_freeze = data["pump_freeze"]
    inlet_freeze = data["inlet_freeze"]
    closed_inlet_mode = data["closed_inlet_mode"]
    pump_mode_constraints = data["pump_mode_constraints"]
    inlet_mode_constraints = data["inlet_mode_constraints"]
    topology = data["topology"]

    model = pyo.ConcreteModel(name="GoudaMILP")
    model.x = pyo.Var(
        range(n_pump_modes), range(n_periods), range(n_pumps), domain=pyo.Binary
    )
    model.y = pyo.Var(
        range(n_inlet_modes), range(n_periods), range(n_inlets), domain=pyo.Binary
    )
    model.volume = pyo.Var(range(n_periods), domain=pyo.Reals)
    model.z = pyo.Var(
        range(n_pump_modes), range(n_periods - 1), range(n_pumps), domain=pyo.Binary
    )
    model.absolute_level_error = pyo.Var(range(n_periods), domain=pyo.NonNegativeReals)
    model.constraints = pyo.ConstraintList()

    x = model.x
    y = model.y
    volume = model.volume
    z = model.z
    absolute_level_error = model.absolute_level_error

    for t in range(n_periods):
        for p in range(n_pumps):
            model.constraints.add(sum(x[m, t, p] for m in range(n_pump_modes)) == 1)

    for t in range(n_periods):
        for i in range(n_inlets):
            model.constraints.add(sum(y[m, t, i] for m in range(n_inlet_modes)) == 1)

    for m in range(n_pump_modes):
        for t in range(n_periods - 1):
            for p in range(n_pumps):
                model.constraints.add(z[m, t, p] <= x[m, t, p] + x[m, t + 1, p])
                model.constraints.add(z[m, t, p] >= x[m, t + 1, p] - x[m, t, p])
                model.constraints.add(z[m, t, p] >= x[m, t, p] - x[m, t + 1, p])
                model.constraints.add(z[m, t, p] <= 2 - x[m, t, p] - x[m, t + 1, p])

    for p in range(n_pumps):
        for t in range(int(pump_freeze[p][1])):
            mode = int(pump_freeze[p][0])
            model.constraints.add(x[mode, t, p] == 1)

    for i in range(n_inlets):
        for t in range(int(inlet_freeze[i][1])):
            mode = int(inlet_freeze[i][0])
            model.constraints.add(y[mode, t, i] == 1)

    for constraint in pump_mode_constraints:
        model.constraints.add(x[constraint["mode"], constraint["time"], constraint["pump"]] == 1)

    for constraint in inlet_mode_constraints:
        model.constraints.add(y[constraint["mode"], constraint["time"], constraint["inlet"]] == 1)

    for m in range(n_pump_modes):
        for t in range(n_periods - 1):
            for p in range(n_pumps):
                for k in range(min(int(min_mode_duration[m][p]), n_periods - 2 - t)):
                    model.constraints.add(z[m, t + k + 1, p] <= 1 - z[m, t, p])

    def flow_expression(element_id, t):
        element = topology["element_by_id"][element_id]
        if element["type"] == "inflow":
            series = element["series"]
            if series not in time_series:
                raise ValueError(f"Unknown inflow time series {series!r}.")
            return time_series[series][t]
        if element["type"] == "pump":
            pump_index = topology["pump_elements"][element_id]
            return sum(
                q_pumps[m][pump_index] * x[m, t, pump_index]
                for m in range(n_pump_modes)
            )
        if element["type"] == "inlet":
            inlet_index = topology["inlet_elements"][element_id]
            return sum(
                q_inlets[m][inlet_index] * y[m, t, inlet_index]
                for m in range(n_inlet_modes)
            )
        raise ValueError(f"Element {element_id!r} cannot carry flow.")

    model.constraints.add(volume[0] == initial_storage_volume)
    storage_balance = topology["storage_balance"]
    for t in range(n_periods - 1):
        inflow = sum(flow_expression(element_id, t) for element_id in storage_balance["inflows"])
        outflow = sum(flow_expression(element_id, t) for element_id in storage_balance["outflows"])
        model.constraints.add(volume[t + 1] == volume[t] + inflow - outflow)

    big_m = 50
    epsilon = 1e-3
    storage_area_inverse = 1 / storage_area
    for head_constraint in topology["head_constraints"]:
        lower_element = topology["element_by_id"][head_constraint["lower"]]
        lower_series = lower_element["series"]
        if lower_series not in time_series:
            raise ValueError(f"Unknown level time series {lower_series!r}.")
        for t in range(n_periods):
            for inlet_id in head_constraint["controlled_elements"]:
                inlet_index = topology["inlet_elements"][inlet_id]
                model.constraints.add(
                    volume[t] * storage_area_inverse - time_series[lower_series][t]
                    >= epsilon - big_m * y[closed_inlet_mode, t, inlet_index]
                )

    for pump_constraint in topology["pump_head_mode_constraints"]:
        lower_element = topology["element_by_id"][pump_constraint["lower"]]
        lower_series = lower_element["series"]
        required_mode = pump_constraint["required_mode"]
        if lower_series not in time_series:
            raise ValueError(f"Unknown level time series {lower_series!r}.")
        if required_mode < 0 or required_mode >= n_pump_modes:
            raise ValueError(
                f"head_based_pump_mode_constraint.required_mode must be between 0 and {n_pump_modes - 1}."
            )

        for t in range(n_periods):
            for pump_id in pump_constraint["controlled_elements"]:
                pump_index = topology["pump_elements"][pump_id]
                model.constraints.add(
                    volume[t] * storage_area_inverse - time_series[lower_series][t]
                    <= big_m * x[required_mode, t, pump_index]
                )

    for t in range(n_periods):
        model.constraints.add(volume[t] <= max_storage_volume)
        model.constraints.add(volume[t] >= min_storage_volume)

    for t in range(n_periods):
        model.constraints.add(
            absolute_level_error[t] >= volume[t] * storage_area_inverse - desired_storage_level[t]
        )
        model.constraints.add(
            absolute_level_error[t] >= -volume[t] * storage_area_inverse + desired_storage_level[t]
        )

    model.objective = pyo.Objective(
        expr=sum(absolute_level_error[t] for t in range(n_periods)),
        sense=pyo.minimize,
    )

    return model, x, y, volume


def write_results(output_path, data, x, y, volume):
    from pyomo.environ import value

    n_periods = data["n_periods"]
    n_inlets = data["n_inlets"]
    n_inlet_modes = data["n_inlet_modes"]
    n_pumps = data["n_pumps"]
    n_pump_modes = data["n_pump_modes"]
    storage_area = data["storage_area"]

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as outfile:
        outfile.write("Water level:\n")
        for t in range(n_periods):
            outfile.write(f"H[{t}] = {value(volume[t]) / storage_area}\n")

        outfile.write("------------------------\n")
        for i in range(n_inlets):
            outfile.write(f"inlet {i}:\n")
            for t in range(n_periods):
                for m in range(n_inlet_modes):
                    if value(y[m, t, i]) > 0.5:
                        outfile.write(f"t={t} -> mode={m}\n")

        outfile.write("------------------------\n")
        for p in range(n_pumps):
            outfile.write(f"pump {p}:\n")
            for t in range(n_periods):
                for m in range(n_pump_modes):
                    if value(x[m, t, p]) > 0.5:
                        outfile.write(f"t={t} -> mode={m}\n")


def run_optimization(
    input_dir=DEFAULT_INPUT_DIR,
    output_path=DEFAULT_OUTPUT_PATH,
    log_path=DEFAULT_LOG_PATH,
    solver_msg=True,
):
    try:
        import pyomo.environ as pyo
        from pyomo.opt import SolverStatus, TerminationCondition
    except ModuleNotFoundError as exc:
        raise RuntimeError("Pyomo is not installed. Run: pip install -r requirements.txt") from exc

    data = load_input_data(input_dir)
    model, x, y, volume = build_model(data)
    log_path = Path(log_path) if log_path is not None else None
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)

    solver = pyo.SolverFactory("appsi_highs")
    if not solver.available(exception_flag=False):
        raise RuntimeError(
            "The HiGHS solver is not available. Run: pip install -r requirements.txt"
        )
    solver.options["mip_rel_gap"] = 0.001
    results = solver.solve(model, tee=solver_msg)
    termination = results.solver.termination_condition
    if termination == TerminationCondition.infeasible:
        raise ValueError("The optimization problem is infeasible.")
    if results.solver.status != SolverStatus.ok or termination not in {
        TerminationCondition.optimal,
        TerminationCondition.feasible,
    }:
        raise ValueError(
            f"Optimization failed with status {results.solver.status} and termination {termination}."
        )

    if log_path is not None:
        log_path.write_text(
            f"Solver: appsi_highs\nStatus: {results.solver.status}\n"
            f"Termination condition: {termination}\n",
            encoding="utf-8",
        )

    write_results(output_path, data, x, y, volume)
    return Path(output_path)


def parse_args():
    parser = argparse.ArgumentParser(description="Solve the pump and inlet scheduling MILP.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH)
    return parser.parse_args()


def main():
    args = parse_args()
    run_optimization(input_dir=args.input_dir, output_path=args.output, log_path=args.log)


if __name__ == "__main__":
    main()
