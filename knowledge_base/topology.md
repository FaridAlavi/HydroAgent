# Topology File

`topology.json` describes which physical elements exist and how they are
connected. The optimizer builds model equations from this file instead of using
a hard-coded network.

The file has three sections:

- `elements`: all elements in the model.
- `connections`: readable physical links between elements.
- `equations`: equations that the optimizer should build.

Supported element types:

- `storage`
- `level`
- `inflow`
- `pump`
- `inlet`

Supported equation types:

- `storage_balance`
- `hydraulic_head_constraint`
- `head_based_pump_mode_constraint`

`storage_balance` equation:

```json
{
  "type": "storage_balance",
  "storage": "storage",
  "inflows": ["catchment_inflow"],
  "outflows": ["pump_0", "inlet_0"]
}
```

This equation means:

```text
next storage volume = current storage volume + inflows - outflows
```

Rules:

- There must be exactly one `storage_balance` equation.
- The `storage` field must reference a storage element.
- Elements in `inflows` must flow into the storage.
- Elements in `outflows` must flow out of the storage.

`hydraulic_head_constraint` equation:

```json
{
  "type": "hydraulic_head_constraint",
  "upper": "storage",
  "lower": "sea",
  "controlled_elements": ["inlet_0"]
}
```

This equation means the controlled inlet can be open only when the upper level is
higher than the lower level.

Rules:

- `upper` must currently be a storage element.
- `lower` must be a level element.
- `controlled_elements` must be inlet elements.
- Each controlled inlet must connect from `upper` to `lower`.

`head_based_pump_mode_constraint` equation:

```json
{
  "type": "head_based_pump_mode_constraint",
  "upper": "storage",
  "lower": "sea",
  "controlled_elements": ["pump_1"],
  "required_mode": 0,
  "condition": "upper_above_lower"
}
```

This equation means the controlled pump must be in `required_mode` whenever the
upper storage water level is higher than the lower level element.

Example user request:

```text
The second pump should be off whenever the sea level is below the storage level.
```

If the user confirms that "second pump" means pump index `1` and mode `0` is the
off mode, this can be represented by the JSON equation above.

Rules:

- `upper` must currently be a storage element.
- `lower` must be a level element.
- `controlled_elements` must be pump elements.
- Each controlled pump must connect from `upper` to `lower`.
- `condition` currently supports `"upper_above_lower"`.
- `required_mode` must be a valid pump mode, usually `0` for off.

Connection example:

```json
{
  "from": "storage",
  "to": "sea",
  "via": "pump_0"
}
```

User explanation:

The topology is the map of the system. It tells the model where water starts,
where it can go, and which devices move it. The equations tell the optimizer how
to turn that map into mathematical constraints.
