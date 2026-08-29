import json
import os
import re
import textwrap
import webbrowser
from pathlib import Path

import matplotlib

matplotlib.use("Agg")


WATER_LEVEL_PATTERN = re.compile(r"^H\[(?P<time>\d+)\]\s*=\s*(?P<value>[-+0-9.eE]+)$")
MODE_PATTERN = re.compile(r"^t=(?P<time>\d+)\s*->\s*mode=(?P<mode>\d+)$")
SECTION_PATTERN = re.compile(r"^(?P<kind>inlet|pump)\s+(?P<index>\d+):$", re.IGNORECASE)


def _resolve_horizon_path(input_dir_or_path):
    path = Path(input_dir_or_path)
    if path.is_dir():
        return path / "horizon.json"
    return path


def _read_horizon(input_dir_or_path):
    path = _resolve_horizon_path(input_dir_or_path)
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _resolve_topology_path(input_dir_or_path):
    path = Path(input_dir_or_path)
    if path.is_dir():
        return path / "topology.json"
    return path


def _read_topology(input_dir_or_path):
    path = _resolve_topology_path(input_dir_or_path)
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _trim_series(horizon, values, trim_to_horizon):
    if not trim_to_horizon:
        return list(values)

    n_periods = int(horizon["n_periods"])
    return list(values[:n_periods])


def read_horizon_series(input_dir_or_path, series_name, trim_to_horizon=True):
    """Read one time series from horizon.json.

    Args:
        input_dir_or_path: Folder containing horizon.json, or the horizon.json path.
        series_name: Key to read from horizon.json.
        trim_to_horizon: Return only n_periods values when True.

    Returns:
        A list of values from the requested series.
    """
    horizon = _read_horizon(input_dir_or_path)
    if series_name not in horizon:
        raise KeyError(f"horizon.json does not contain {series_name!r}.")
    return _trim_series(horizon, horizon[series_name], trim_to_horizon)


def read_discharge_sequence(input_dir_or_path, trim_to_horizon=True):
    return read_horizon_series(input_dir_or_path, "discharge_sequence", trim_to_horizon)


def read_sea_level(input_dir_or_path, trim_to_horizon=True):
    return read_horizon_series(input_dir_or_path, "sea_level", trim_to_horizon)


def read_desired_storage_level(input_dir_or_path, trim_to_horizon=True):
    return read_horizon_series(input_dir_or_path, "desired_storage_level", trim_to_horizon)


def read_water_level_trajectory(results_path):
    """Read the optimized storage water level trajectory from results.txt."""
    water_level_by_time = {}
    for raw_line in Path(results_path).read_text(encoding="utf-8").splitlines():
        match = WATER_LEVEL_PATTERN.match(raw_line.strip())
        if match:
            water_level_by_time[int(match.group("time"))] = float(match.group("value"))

    if not water_level_by_time:
        raise ValueError(f"No water level values found in {results_path}.")

    return [water_level_by_time[t] for t in sorted(water_level_by_time)]


def _read_modes(results_path, kind):
    mode_by_item = {}
    active_kind = None
    active_index = None

    for raw_line in Path(results_path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        section_match = SECTION_PATTERN.match(line)
        if section_match:
            active_kind = section_match.group("kind").lower()
            active_index = int(section_match.group("index"))
            if active_kind == kind:
                mode_by_item.setdefault(active_index, {})
            continue

        mode_match = MODE_PATTERN.match(line)
        if mode_match and active_kind == kind and active_index is not None:
            time_step = int(mode_match.group("time"))
            mode = int(mode_match.group("mode"))
            mode_by_item[active_index][time_step] = mode

    if not mode_by_item:
        raise ValueError(f"No {kind} modes found in {results_path}.")

    return {
        item_index: [time_to_mode[t] for t in sorted(time_to_mode)]
        for item_index, time_to_mode in sorted(mode_by_item.items())
    }


def read_inlet_modes(results_path):
    """Read inlet modes from results.txt as {inlet_index: [mode_by_time]}."""
    return _read_modes(results_path, "inlet")


def read_pump_modes(results_path):
    """Read pump modes from results.txt as {pump_index: [mode_by_time]}."""
    return _read_modes(results_path, "pump")


def _time_axis(values):
    return list(range(len(values)))


def _finish_plot(fig, save_path=None, show=False):
    if save_path is not None:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, bbox_inches="tight", dpi=150)

    if show:
        import matplotlib.pyplot as plt

        plt.show()
    return fig


def _topology_node_label(element):
    label = "\n".join(textwrap.wrap(element["id"].replace("_", " "), width=12))
    details = [element["type"]]
    if "index" in element:
        details.append(f"index {element['index']}")
    if "series" in element:
        details.append(str(element["series"]).replace("_", " "))
    return f"{label}\n({', '.join(details)})"


def _topology_positions(graph):
    layer_to_nodes = {}
    for node, data in graph.nodes(data=True):
        layer_to_nodes.setdefault(data["layer"], []).append(node)

    positions = {}
    for layer, nodes in sorted(layer_to_nodes.items()):
        ordered_nodes = sorted(nodes)
        offset = (len(ordered_nodes) - 1) / 2
        for position, node in enumerate(ordered_nodes):
            positions[node] = (layer * 2.2, offset - position)
    return positions


def plot_topology_graph(input_dir, save_path=None, show=False):
    """Plot topology.json as a directed graph.

    Pumps and inlets are shown as graph nodes. A topology connection with a
    ``via`` element is drawn as source -> via -> target.
    """
    try:
        import networkx as nx
    except ModuleNotFoundError as exc:
        raise RuntimeError("NetworkX is not installed. Run: pip install -r requirements.txt") from exc

    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    topology = _read_topology(input_dir)
    elements = topology.get("elements", [])
    element_by_id = {element["id"]: element for element in elements}

    type_to_layer = {
        "inflow": 0,
        "storage": 1,
        "pump": 2,
        "inlet": 2,
        "level": 3,
    }
    type_to_color = {
        "storage": "#4C78A8",
        "level": "#72B7B2",
        "inflow": "#59A14F",
        "pump": "#F28E2B",
        "inlet": "#E15759",
    }

    graph = nx.DiGraph()
    for element in elements:
        element_id = element["id"]
        element_type = element["type"]
        graph.add_node(
            element_id,
            label=_topology_node_label(element),
            layer=type_to_layer.get(element_type, 4),
            element_type=element_type,
            color=type_to_color.get(element_type, "#9C9C9C"),
        )

    for connection in topology.get("connections", []):
        source = connection["from"]
        target = connection["to"]
        via = connection.get("via")
        if via:
            graph.add_edge(source, via)
            graph.add_edge(via, target)
        else:
            graph.add_edge(source, target)

    fig, ax = plt.subplots(figsize=(10, 5.6))
    positions = _topology_positions(graph)
    labels = {node: data["label"] for node, data in graph.nodes(data=True)}

    for element_type, color in type_to_color.items():
        nodes = [
            node
            for node, data in graph.nodes(data=True)
            if data["element_type"] == element_type
        ]
        if nodes:
            nx.draw_networkx_nodes(
                graph,
                positions,
                nodelist=nodes,
                node_color=color,
                node_size=900,
                edgecolors="#2F2F2F",
                linewidths=1.1,
                ax=ax,
            )

    nx.draw_networkx_edges(
        graph,
        positions,
        arrows=True,
        arrowstyle="-|>",
        arrowsize=18,
        edge_color="#4A4A4A",
        width=1.8,
        min_source_margin=18,
        min_target_margin=18,
        ax=ax,
    )
    for node, (x_position, y_position) in positions.items():
        node_color = graph.nodes[node]["color"]
        ax.text(
            x_position,
            y_position - 0.45,
            labels[node],
            ha="center",
            va="top",
            fontsize=8,
            color="#1F1F1F",
            bbox={
                "boxstyle": "round,pad=0.25",
                "facecolor": "white",
                "edgecolor": node_color,
                "linewidth": 1.1,
                "alpha": 0.95,
            },
        )

    legend_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor=color,
            markeredgecolor="#2F2F2F",
            markersize=10,
            label=element_type,
        )
        for element_type, color in type_to_color.items()
        if any(data["element_type"] == element_type for _, data in graph.nodes(data=True))
    ]
    ax.legend(handles=legend_handles, loc="upper center", ncol=len(legend_handles))
    ax.set_title("Topology graph")
    ax.margins(0.18)
    ax.axis("off")
    fig.tight_layout()
    return _finish_plot(fig, save_path=save_path, show=show)


def plot_water_level_trajectory(results_path, input_dir=None, save_path=None, show=False):
    """Plot optimized water level, optionally with desired level and sea level."""
    import matplotlib.pyplot as plt

    water_level = read_water_level_trajectory(results_path)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(_time_axis(water_level), water_level, marker="o", label="Storage water level")

    if input_dir is not None:
        desired = read_desired_storage_level(input_dir)
        ax.plot(_time_axis(desired), desired, linestyle="--", label="Desired storage level")
        sea_level = read_sea_level(input_dir)
        ax.plot(_time_axis(sea_level), sea_level, linestyle=":", label="Sea level")

    ax.set_title("Water level trajectory")
    ax.set_xlabel("Time step")
    ax.set_ylabel("Level")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    return _finish_plot(fig, save_path=save_path, show=show)


def plot_inflow(input_dir, save_path=None, show=False):
    """Plot the discharge sequence from horizon.json."""
    import matplotlib.pyplot as plt

    discharge = read_discharge_sequence(input_dir)
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.step(_time_axis(discharge), discharge, where="post", label="Discharge")
    ax.set_title("Discharge sequence")
    ax.set_xlabel("Time step")
    ax.set_ylabel("Discharge")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    return _finish_plot(fig, save_path=save_path, show=show)


def plot_modes(modes_by_item, label, ax=None):
    """Plot pump or inlet mode trajectories from a {index: [mode_by_time]} mapping."""
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(9, 3.8))

    for item_index, modes in sorted(modes_by_item.items()):
        ax.step(_time_axis(modes), modes, where="post", marker="o", label=f"{label} {item_index}")

    ax.set_xlabel("Time step")
    ax.set_ylabel("Mode")
    ax.grid(True, alpha=0.25)
    ax.legend()
    return ax


def plot_results_overview(results_path, input_dir=None, save_path=None, show=False):
    """Plot water level, horizon input series, inlet modes, and pump modes together."""
    import matplotlib.pyplot as plt

    water_level = read_water_level_trajectory(results_path)
    inlet_modes = read_inlet_modes(results_path)
    pump_modes = read_pump_modes(results_path)

    fig, axes = plt.subplots(4, 1, figsize=(10, 11), sharex=True)

    axes[0].plot(_time_axis(water_level), water_level, marker="o", label="Storage water level")
    if input_dir is not None:
        desired = read_desired_storage_level(input_dir)
        sea_level = read_sea_level(input_dir)
        discharge = read_discharge_sequence(input_dir)
        axes[0].plot(_time_axis(desired), desired, linestyle="--", label="Desired storage level")
        axes[0].plot(_time_axis(sea_level), sea_level, linestyle=":", label="Sea level")
        axes[1].step(_time_axis(discharge), discharge, where="post", label="Discharge")
    else:
        axes[1].axis("off")

    axes[0].set_title("Water level trajectory")
    axes[0].set_ylabel("Level")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend()

    if input_dir is not None:
        axes[1].set_title("Discharge sequence")
        axes[1].set_ylabel("Discharge")
        axes[1].grid(True, alpha=0.25)
        axes[1].legend()

    plot_modes(inlet_modes, "Inlet", ax=axes[2])
    axes[2].set_title("Inlet modes")

    plot_modes(pump_modes, "Pump", ax=axes[3])
    axes[3].set_title("Pump modes")
    axes[3].set_xlabel("Time step")

    fig.tight_layout()
    return _finish_plot(fig, save_path=save_path, show=show)


def open_plot_file(plot_path):
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
