# Pump Element

A pump is a controllable element that moves water from one upstream element to
one downstream element.

Pump operating data is defined in `pumps.json`. The topology file connects each
pump index to physical upstream and downstream elements.

Required `pumps.json` fields:

- `flow_by_mode`: matrix with rows as modes and columns as pumps.
- `min_mode_duration`: matrix matching `flow_by_mode` dimensions.
- `freeze`: list of `[mode, remaining_periods]`, one entry per pump.

Required topology fields:

- `id`: unique element name.
- `type`: must be `"pump"`.
- `index`: pump index corresponding to a column in `pumps.json`.
- `upstream`: source element.
- `downstream`: receiving element.

Rules:

- A pump must have exactly one upstream and one downstream element.
- A pump must reference a valid pump index from `pumps.json`.
- Pump indexes are zero-based.
- At every time step, each pump must be in exactly one mode.
- Pump flow is determined by its selected mode.
- Mode 0 often represents off or no flow, but this depends on `flow_by_mode`.
- `min_mode_duration[m][p]` means that when pump `p` switches to mode `m`, it
  must remain there for the specified number of time steps.
- A pump can appear in `storage_balance.outflows` if its upstream is storage.
- A pump can appear in `storage_balance.inflows` if its downstream is storage.
- A pump can have a head-based mode rule using
  `head_based_pump_mode_constraint`. This is useful when a user says something
  like "pump 1 should be off whenever the downstream level is lower than the
  storage level."

Head-based pump mode rule:

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

This means each listed pump must be in `required_mode` whenever the `upper`
storage water level is higher than the `lower` level element. In many pump
configurations, `required_mode: 0` means the pump is off.

Important interpretation:

- If the user says "the pump should be off whenever sea level is below storage
  level", this should usually be modeled as a `head_based_pump_mode_constraint`
  with `upper` as the pump upstream storage, `lower` as the downstream level,
  and `required_mode` as the pump's off mode.
- Do not tell the user this is only possible for inlets. Pumps can also be
  restricted by this supported topology equation.
- Confirm which pump index the user means and confirm that mode 0 is the off
  mode before updating the topology.

Topology example:

```json
{
  "id": "pump_0",
  "type": "pump",
  "index": 0,
  "upstream": "storage",
  "downstream": "sea"
}
```

User explanation:

A pump actively moves water. The optimizer chooses the pump mode over time,
subject to the allowed modes and minimum duration constraints. If the user asks
to force a pump to a mode at a time step, this becomes a user constraint in
`user_constraints.json`.
