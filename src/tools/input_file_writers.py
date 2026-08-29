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

try:
    from ..pump_inlet_scheduling import DEFAULT_INPUT_DIR, ensure_topology
except (ImportError, ValueError):
    from pump_inlet_scheduling import DEFAULT_INPUT_DIR, ensure_topology


def _write_json(input_dir, filename, data):
    input_dir = Path(input_dir)
    input_dir.mkdir(parents=True, exist_ok=True)
    output_path = input_dir / filename
    output_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return output_path


def _ensure_matrix(name, value):
    if not isinstance(value, list) or not value or not all(isinstance(row, list) and row for row in value):
        raise ValueError(f"{name} must be a non-empty matrix.")

    row_length = len(value[0])
    if any(len(row) != row_length for row in value):
        raise ValueError(f"{name} must have the same number of columns in every row.")

    return value


def _ensure_freeze(name, value, expected_items):
    if value is None:
        return [[0, 0] for _ in range(expected_items)]
    if len(value) != expected_items:
        raise ValueError(f"{name} must contain one [mode, remaining_periods] entry per item.")

    return value


def _ensure_number(name, value):
    if value is None:
        raise ValueError(f"{name} is required.")

    return float(value)


def create_pumps_json(
    input_dir=DEFAULT_INPUT_DIR,
    flow_by_mode=None,
    min_mode_duration=None,
    freeze=None,
):
    """Create pumps.json.

    Args:
        input_dir: Folder where pumps.json should be written.
        flow_by_mode: Matrix with rows as modes and columns as pumps.
        min_mode_duration: Matrix matching flow_by_mode dimensions.
        freeze: Optional list of [mode, remaining_periods], one per pump.

    Returns:
        Path to the generated pumps.json file.
    """
    flow_by_mode = _ensure_matrix("flow_by_mode", flow_by_mode)
    min_mode_duration = _ensure_matrix("min_mode_duration", min_mode_duration)
    n_pumps = len(flow_by_mode[0])

    if len(min_mode_duration) != len(flow_by_mode) or len(min_mode_duration[0]) != n_pumps:
        raise ValueError("min_mode_duration must match flow_by_mode dimensions.")

    data = {
        "flow_by_mode": flow_by_mode,
        "min_mode_duration": min_mode_duration,
        "freeze": _ensure_freeze("freeze", freeze, n_pumps),
    }
    return _write_json(input_dir, "pumps.json", data)


def create_inlets_json(
    input_dir=DEFAULT_INPUT_DIR,
    flow_by_mode=None,
    closed_mode=0,
    freeze=None,
):
    """Create inlets.json.

    Args:
        input_dir: Folder where inlets.json should be written.
        flow_by_mode: Matrix with rows as modes and columns as inlets.
        closed_mode: Mode index representing a closed inlet.
        freeze: Optional list of [mode, remaining_periods], one per inlet.

    Returns:
        Path to the generated inlets.json file.
    """
    flow_by_mode = _ensure_matrix("flow_by_mode", flow_by_mode)
    n_inlets = len(flow_by_mode[0])
    n_modes = len(flow_by_mode)
    closed_mode = int(closed_mode)

    if closed_mode < 0 or closed_mode >= n_modes:
        raise ValueError(f"closed_mode must be between 0 and {n_modes - 1}.")

    data = {
        "flow_by_mode": flow_by_mode,
        "closed_mode": closed_mode,
        "freeze": _ensure_freeze("freeze", freeze, n_inlets),
    }
    return _write_json(input_dir, "inlets.json", data)


def create_storage_json(
    input_dir=DEFAULT_INPUT_DIR,
    area=None,
    initial_volume=None,
    min_volume=None,
    max_volume=None,
):
    """Create storage.json.

    Args:
        input_dir: Folder where storage.json should be written.
        area: Storage surface area used to convert volume to water level.
        initial_volume: Initial storage volume.
        min_volume: Minimum allowed storage volume.
        max_volume: Maximum allowed storage volume.

    Returns:
        Path to the generated storage.json file.
    """
    area = _ensure_number("area", area)
    initial_volume = _ensure_number("initial_volume", initial_volume)
    min_volume = _ensure_number("min_volume", min_volume)
    max_volume = _ensure_number("max_volume", max_volume)

    if area <= 0:
        raise ValueError("area must be positive.")
    if min_volume > max_volume:
        raise ValueError("min_volume must be less than or equal to max_volume.")
    if initial_volume < min_volume or initial_volume > max_volume:
        raise ValueError("initial_volume must be between min_volume and max_volume.")

    data = {
        "area": area,
        "initial_volume": initial_volume,
        "min_volume": min_volume,
        "max_volume": max_volume,
    }
    return _write_json(input_dir, "storage.json", data)


def create_topology_json(
    input_dir=DEFAULT_INPUT_DIR,
    elements=None,
    connections=None,
    equations=None,
    n_pumps=None,
    n_inlets=None,
):
    """Create topology.json.

    Args:
        input_dir: Folder where topology.json should be written.
        elements: List of element objects.
        connections: List of connection objects.
        equations: List of equation objects.
        n_pumps: Number of pump indexes expected in the topology.
        n_inlets: Number of inlet indexes expected in the topology.

    Returns:
        Path to the generated topology.json file.
    """
    data = {
        "elements": elements,
        "connections": connections or [],
        "equations": equations,
    }
    ensure_topology(data, int(n_pumps), int(n_inlets))
    return _write_json(input_dir, "topology.json", data)
