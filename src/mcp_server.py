import argparse
import asyncio
import json
import os
import sys
import webbrowser
from pathlib import Path

# Ensure src and root directories are in sys.path
_src_dir = Path(__file__).resolve().parent
_root_dir = _src_dir.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except (ImportError, ModuleNotFoundError):
    from mcp.server.fastmcp import FastMCP

from pump_inlet_scheduling import DEFAULT_INPUT_DIR, DEFAULT_OUTPUT_PATH
from tools.input_file_writers import (
    create_inlets_json,
    create_pumps_json,
    create_storage_json,
    create_topology_json,
)
from tools.plotting import (
    plot_inflow,
    plot_results_overview,
    plot_topology_graph,
    plot_water_level_trajectory,
    read_desired_storage_level,
    read_discharge_sequence,
    read_horizon_series,
    read_inlet_modes,
    read_pump_modes,
    read_sea_level,
    read_water_level_trajectory,
)
from tools.topology_explainer import create_topology_explanation as explain_topology
from tools.user_constraints import create_user_constraints as write_constraints

DEFAULT_PLOTS_DIR = _root_dir / "output" / "plots"
mcp = FastMCP(
    "Pump Scheduling Tools",
    instructions="Inspect, update, solve, and visualize a pump and inlet scheduling scenario.",
)
_active_input_dir = DEFAULT_INPUT_DIR


def _read_json_if_present(path):
    path = Path(path)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@mcp.tool()
def get_current_model_summary() -> str:
    """Read all active scenario JSON files and return their current contents."""
    filenames = [
        "pumps.json",
        "inlets.json",
        "storage.json",
        "horizon.json",
        "topology.json",
        "user_constraints.json",
    ]
    summary = {
        filename: _read_json_if_present(_active_input_dir / filename)
        for filename in filenames
    }
    return json.dumps(summary, indent=2)


@mcp.tool(name="create_pumps_json")
def create_pumps_file(
    flow_by_mode: list[list[float]],
    min_mode_duration: list[list[int]],
    freeze: list[list[int]] | None = None,
) -> str:
    """Write pumps.json in the active scenario folder."""
    output_path = create_pumps_json(
        input_dir=_active_input_dir,
        flow_by_mode=flow_by_mode,
        min_mode_duration=min_mode_duration,
        freeze=freeze,
    )
    return f"Updated {output_path}"


@mcp.tool(name="create_inlets_json")
def create_inlets_file(
    flow_by_mode: list[list[float]],
    closed_mode: int = 0,
    freeze: list[list[int]] | None = None,
) -> str:
    """Write inlets.json in the active scenario folder."""
    output_path = create_inlets_json(
        input_dir=_active_input_dir,
        flow_by_mode=flow_by_mode,
        closed_mode=closed_mode,
        freeze=freeze,
    )
    return f"Updated {output_path}"


@mcp.tool(name="create_storage_json")
def create_storage_file(
    area: float,
    initial_volume: float,
    min_volume: float,
    max_volume: float,
) -> str:
    """Write storage.json in the active scenario folder."""
    output_path = create_storage_json(
        input_dir=_active_input_dir,
        area=area,
        initial_volume=initial_volume,
        min_volume=min_volume,
        max_volume=max_volume,
    )
    return f"Updated {output_path}"


@mcp.tool(name="create_topology_json")
def create_topology_file(
    elements_json: str,
    connections_json: str,
    equations_json: str,
    n_pumps: int,
    n_inlets: int,
) -> str:
    """Write topology.json from JSON-array strings in the active scenario folder."""
    output_path = create_topology_json(
        input_dir=_active_input_dir,
        elements=json.loads(elements_json),
        connections=json.loads(connections_json),
        equations=json.loads(equations_json),
        n_pumps=n_pumps,
        n_inlets=n_inlets,
    )
    return f"Updated {output_path}"


@mcp.tool()
def create_topology_explanation() -> str:
    """Return a plain-language explanation of the active topology.json file."""
    return explain_topology(input_dir=_active_input_dir)


@mcp.tool(name="create_user_constraints")
def create_constraints_file(
    pump_constraints: list[dict],
    inlet_constraints: list[dict],
) -> str:
    """Write fixed pump and inlet mode constraints to user_constraints.json."""
    output_path = write_constraints(
        input_dir=_active_input_dir,
        pump_constraints=pump_constraints,
        inlet_constraints=inlet_constraints,
    )
    return f"Updated {output_path}"


@mcp.tool(name="run_optimization")
async def run_optimization_model() -> str:
    """Run the Pyomo scheduling model using the active scenario folder."""
    scheduler_script = Path(__file__).with_name("pump_inlet_scheduling.py").resolve()
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(scheduler_script),
        "--input-dir",
        str(_active_input_dir.resolve()),
        "--output",
        str(DEFAULT_OUTPUT_PATH.resolve()),
        cwd=_root_dir,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        message = stderr.decode().strip() or stdout.decode().strip()
        raise RuntimeError(f"Optimization failed: {message}")
    return f"Optimization completed. Results written to {DEFAULT_OUTPUT_PATH}"


@mcp.tool(name="read_water_level_trajectory")
def read_water_level_results(results_path: str = str(DEFAULT_OUTPUT_PATH)) -> str:
    """Read the optimized storage water-level trajectory from results.txt."""
    return json.dumps(read_water_level_trajectory(results_path))


@mcp.tool(name="read_inlet_modes")
def read_inlet_mode_results(results_path: str = str(DEFAULT_OUTPUT_PATH)) -> str:
    """Read inlet modes from results.txt, grouped by inlet index."""
    return json.dumps(read_inlet_modes(results_path), indent=2)


@mcp.tool(name="read_pump_modes")
def read_pump_mode_results(results_path: str = str(DEFAULT_OUTPUT_PATH)) -> str:
    """Read pump modes from results.txt, grouped by pump index."""
    return json.dumps(read_pump_modes(results_path), indent=2)


@mcp.tool(name="read_horizon_series")
def read_horizon_series_tool(series_name: str, trim_to_horizon: bool = True) -> str:
    """Read one named series from horizon.json in the active scenario folder."""
    return json.dumps(read_horizon_series(_active_input_dir, series_name, trim_to_horizon))


@mcp.tool(name="read_discharge_sequence")
def read_discharge_sequence_tool(trim_to_horizon: bool = True) -> str:
    """Read discharge_sequence from the active horizon.json file."""
    return json.dumps(read_discharge_sequence(_active_input_dir, trim_to_horizon))


@mcp.tool(name="read_sea_level")
def read_sea_level_tool(trim_to_horizon: bool = True) -> str:
    """Read sea_level from the active horizon.json file."""
    return json.dumps(read_sea_level(_active_input_dir, trim_to_horizon))


@mcp.tool(name="read_desired_storage_level")
def read_desired_storage_level_tool(trim_to_horizon: bool = True) -> str:
    """Read desired_storage_level from the active horizon.json file."""
    return json.dumps(read_desired_storage_level(_active_input_dir, trim_to_horizon))


@mcp.tool(name="plot_water_level_trajectory")
def plot_water_level_results(
    results_path: str = str(DEFAULT_OUTPUT_PATH),
    save_path: str = str(DEFAULT_PLOTS_DIR / "water_level.png"),
    include_horizon_series: bool = True,
) -> str:
    """Save a water-level plot, optionally including desired and sea levels."""
    input_dir = _active_input_dir if include_horizon_series else None
    plot_water_level_trajectory(results_path, input_dir, save_path, show=False)
    return f"Created plot at {save_path}. Call open_plot_file with this path to open it."


@mcp.tool(name="plot_inflow")
def plot_inflow_results(save_path: str = str(DEFAULT_PLOTS_DIR / "inflow.png")) -> str:
    """Save a discharge-sequence plot from the active horizon.json file."""
    plot_inflow(_active_input_dir, save_path, show=False)
    return f"Created plot at {save_path}. Call open_plot_file with this path to open it."


@mcp.tool(name="plot_results_overview")
def plot_results_overview_tool(
    results_path: str = str(DEFAULT_OUTPUT_PATH),
    save_path: str = str(DEFAULT_PLOTS_DIR / "results_overview.png"),
    include_horizon_series: bool = True,
) -> str:
    """Save a combined water-level, input-series, inlet-mode, and pump-mode plot."""
    input_dir = _active_input_dir if include_horizon_series else None
    plot_results_overview(results_path, input_dir, save_path, show=False)
    return f"Created plot at {save_path}. Call open_plot_file with this path to open it."


@mcp.tool(name="plot_topology_graph")
def plot_topology_graph_tool(
    save_path: str = str(DEFAULT_PLOTS_DIR / "topology.png"),
) -> str:
    """Save a directed graph visualization of the active topology.json file."""
    plot_topology_graph(_active_input_dir, save_path, show=False)
    return f"Created topology plot at {save_path}. Call open_plot_file with this path to open it."


@mcp.tool(name="open_plot_file")
def open_plot_file_tool(
    plot_path: str = str(DEFAULT_PLOTS_DIR / "results_overview.png"),
) -> str:
    """Open a generated PNG plot in the system default viewer."""
    path = Path(plot_path)
    if not path.exists():
        raise FileNotFoundError(f"Plot file does not exist: {plot_path}")
    if path.suffix.lower() != ".png":
        raise ValueError("open_plot_file only opens PNG plot files.")

    absolute_path = path.resolve()
    if hasattr(os, "startfile"):
        os.startfile(absolute_path)
    else:
        webbrowser.open(absolute_path.as_uri())
    return f"Opened plot at {absolute_path}"


def parse_args():
    parser = argparse.ArgumentParser(description="Serve pump scheduling tools over MCP.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default="stdio",
    )
    return parser.parse_args()


def main():
    global _active_input_dir
    args = parse_args()
    _active_input_dir = args.input_dir
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
