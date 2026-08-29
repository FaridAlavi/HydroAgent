import json
import sys
from collections import defaultdict
from pathlib import Path

_tools_dir = Path(__file__).resolve().parent
_src_dir = _tools_dir.parent
_root_dir = _src_dir.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

try:
    from ..pump_inlet_scheduling import DEFAULT_INPUT_DIR
except (ImportError, ValueError):
    from pump_inlet_scheduling import DEFAULT_INPUT_DIR


def _read_json(path):
    with Path(path).open(encoding="utf-8") as file:
        return json.load(file)


def _element_name(element_id, element_by_id):
    element = element_by_id[element_id]
    element_type = element["type"]
    if element_type in {"pump", "inlet"}:
        return f"{element_id} ({element_type} index {element['index']})"
    if element_type == "level":
        return f"{element_id} (level element)"
    if element_type == "storage":
        return f"{element_id} (storage element)"
    if element_type == "inflow":
        return f"{element_id} (inflow time series '{element['series']}')"

    return f"{element_id} ({element_type})"


def _plural(count, singular, plural=None):
    if count == 1:
        return singular
    return plural or f"{singular}s"


def _format_element_list(element_ids):
    return ", ".join(element_ids) if element_ids else "none"


def create_topology_explanation(input_dir=DEFAULT_INPUT_DIR):
    """Create a text explanation of the model topology.

    Args:
        input_dir: Folder containing topology.json.

    Returns:
        Text explanation of the topology.
    """
    input_dir = Path(input_dir)
    topology = _read_json(input_dir / "topology.json")
    elements = topology.get("elements", [])
    connections = topology.get("connections", [])
    equations = topology.get("equations", [])
    element_by_id = {element["id"]: element for element in elements}

    lines = [
        "Topology explanation",
        "====================",
        "",
        "Elements",
        "--------",
    ]

    elements_by_type = defaultdict(list)
    for element in elements:
        elements_by_type[element["type"]].append(element["id"])

    for element_type in sorted(elements_by_type):
        ids = elements_by_type[element_type]
        lines.append(f"- {len(ids)} {_plural(len(ids), element_type)}: {_format_element_list(ids)}")

    lines.extend(["", "Connections", "-----------"])

    grouped_via_connections = defaultdict(list)
    direct_connections = []
    for connection in connections:
        source = connection["from"]
        target = connection["to"]
        via = connection.get("via")
        if via:
            via_type = element_by_id[via]["type"]
            grouped_via_connections[(source, target, via_type)].append(via)
        else:
            direct_connections.append(connection)

    if not connections:
        lines.append("- No connections are defined.")

    for connection in direct_connections:
        source = connection["from"]
        target = connection["to"]
        lines.append(
            f"- {_element_name(source, element_by_id)} flows directly to "
            f"{_element_name(target, element_by_id)}."
        )

    for (source, target, via_type), via_elements in sorted(grouped_via_connections.items()):
        verb = "connects" if len(via_elements) == 1 else "connect"
        lines.append(
            f"- {len(via_elements)} {_plural(len(via_elements), via_type)} "
            f"({_format_element_list(via_elements)}) {verb} "
            f"{_element_name(source, element_by_id)} to {_element_name(target, element_by_id)}."
        )

    storage_ids = elements_by_type.get("storage", [])
    if storage_ids:
        lines.extend(["", "Storage-Oriented View", "---------------------"])

    for storage_id in storage_ids:
        incoming = []
        outgoing = []
        for connection in connections:
            source = connection["from"]
            target = connection["to"]
            via = connection.get("via")
            if target == storage_id:
                incoming.append(via or source)
            if source == storage_id:
                outgoing.append(via or target)

        lines.append(f"- {storage_id}:")
        lines.append(f"  - Incoming elements: {_format_element_list(incoming)}")
        lines.append(f"  - Outgoing elements: {_format_element_list(outgoing)}")

    lines.extend(["", "Equations", "---------"])

    if not equations:
        lines.append("- No topology equations are defined.")

    for equation in equations:
        equation_type = equation.get("type")
        if equation_type == "storage_balance":
            storage = equation["storage"]
            inflows = equation.get("inflows", [])
            outflows = equation.get("outflows", [])
            lines.append(
                f"- Storage balance for {storage}: volume increases through "
                f"{_format_element_list(inflows)} and decreases through "
                f"{_format_element_list(outflows)}."
            )
        elif equation_type == "hydraulic_head_constraint":
            upper = equation["upper"]
            lower = equation["lower"]
            controlled = equation.get("controlled_elements", [])
            lines.append(
                f"- Hydraulic head constraint: {_format_element_list(controlled)} can open only when "
                f"{upper} has a higher water level than {lower}."
            )
        elif equation_type == "head_based_pump_mode_constraint":
            upper = equation["upper"]
            lower = equation["lower"]
            controlled = equation.get("controlled_elements", [])
            required_mode = equation.get("required_mode", 0)
            lines.append(
                f"- Head-based pump mode constraint: {_format_element_list(controlled)} must be in "
                f"mode {required_mode} whenever {upper} has a higher water level than {lower}."
            )
        else:
            lines.append(f"- Unsupported or custom equation '{equation_type}' is listed.")

    return "\n".join(lines)
