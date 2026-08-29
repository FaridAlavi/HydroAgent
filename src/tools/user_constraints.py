import json
import sys
from pathlib import Path

_tools_dir = Path(__file__).resolve().parent
_src_dir = _tools_dir.parent
_root_dir = _src_dir.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

DEFAULT_INPUT_DIR = _root_dir / "input_data"
USER_CONSTRAINTS_FILENAME = "user_constraints.json"


def _read_json(path):
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _normalize_constraints(name, constraints, item_key):
    if constraints is None:
        return []
    if not isinstance(constraints, list):
        raise ValueError(f"{name} must be a list.")

    normalized = []
    seen = {}
    for position, constraint in enumerate(constraints):
        if not isinstance(constraint, dict):
            raise ValueError(f"{name}[{position}] must be an object.")

        try:
            item = int(constraint[item_key])
            time_step = int(constraint["time"])
            mode = int(constraint["mode"])
        except KeyError as exc:
            raise ValueError(f"{name}[{position}] is missing required key {exc.args[0]!r}.") from exc

        if item < 0:
            raise ValueError(f"{name}[{position}].{item_key} must be non-negative.")
        if time_step < 0:
            raise ValueError(f"{name}[{position}].time must be non-negative.")
        if mode < 0:
            raise ValueError(f"{name}[{position}].mode must be non-negative.")

        key = (item, time_step)
        if key in seen and seen[key] != mode:
            raise ValueError(f"{name} contains conflicting modes for {item_key} {item} at time {time_step}.")
        seen[key] = mode

        normalized.append({item_key: item, "time": time_step, "mode": mode})

    return normalized


def _validate_against_input_data(input_dir, pump_constraints, inlet_constraints):
    pumps = _read_json(input_dir / "pumps.json")
    inlets = _read_json(input_dir / "inlets.json")
    horizon = _read_json(input_dir / "horizon.json")

    n_pumps = len(pumps["flow_by_mode"][0])
    n_pump_modes = len(pumps["flow_by_mode"])
    n_inlets = len(inlets["flow_by_mode"][0])
    n_inlet_modes = len(inlets["flow_by_mode"])
    n_periods = int(horizon["n_periods"])

    for position, constraint in enumerate(pump_constraints):
        if constraint["pump"] >= n_pumps:
            raise ValueError(f"pumps[{position}].pump must be between 0 and {n_pumps - 1}.")
        if constraint["time"] >= n_periods:
            raise ValueError(f"pumps[{position}].time must be between 0 and {n_periods - 1}.")
        if constraint["mode"] >= n_pump_modes:
            raise ValueError(f"pumps[{position}].mode must be between 0 and {n_pump_modes - 1}.")

    for position, constraint in enumerate(inlet_constraints):
        if constraint["inlet"] >= n_inlets:
            raise ValueError(f"inlets[{position}].inlet must be between 0 and {n_inlets - 1}.")
        if constraint["time"] >= n_periods:
            raise ValueError(f"inlets[{position}].time must be between 0 and {n_periods - 1}.")
        if constraint["mode"] >= n_inlet_modes:
            raise ValueError(f"inlets[{position}].mode must be between 0 and {n_inlet_modes - 1}.")


def create_user_constraints(
    input_dir=DEFAULT_INPUT_DIR,
    pump_constraints=None,
    inlet_constraints=None,
    validate_against_input_data=True,
):
    """Create user_constraints.json for fixed pump and inlet mode requests.

    Args:
        input_dir: Folder containing the scenario input files.
        pump_constraints: List of {"pump": int, "time": int, "mode": int}.
        inlet_constraints: List of {"inlet": int, "time": int, "mode": int}.
        validate_against_input_data: Check indexes against pumps.json,
            inlets.json, and horizon.json before writing.

    Returns:
        Path to the generated user_constraints.json file.
    """
    input_dir = Path(input_dir)
    pump_constraints = _normalize_constraints("pumps", pump_constraints, "pump")
    inlet_constraints = _normalize_constraints("inlets", inlet_constraints, "inlet")

    if validate_against_input_data:
        _validate_against_input_data(input_dir, pump_constraints, inlet_constraints)

    output_path = input_dir / USER_CONSTRAINTS_FILENAME
    output_path.write_text(
        json.dumps(
            {
                "pumps": pump_constraints,
                "inlets": inlet_constraints,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return output_path
