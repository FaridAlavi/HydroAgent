# Inlet Element

An inlet is a controllable hydraulic connection between one upstream element and
one downstream element. In this model, an inlet can remove water from storage to
a lower downstream level when hydraulic conditions allow it.

Inlet operating data is defined in `inlets.json`. The topology file connects
each inlet index to physical upstream and downstream elements.

Required `inlets.json` fields:

- `flow_by_mode`: matrix with rows as modes and columns as inlets.
- `closed_mode`: mode index that represents the closed inlet state.
- `freeze`: list of `[mode, remaining_periods]`, one entry per inlet.

Required topology fields:

- `id`: unique element name.
- `type`: must be `"inlet"`.
- `index`: inlet index corresponding to a column in `inlets.json`.
- `upstream`: source element.
- `downstream`: receiving element.

Rules:

- An inlet must have exactly one upstream and one downstream element.
- An inlet must reference a valid inlet index from `inlets.json`.
- Inlet indexes are zero-based.
- At every time step, each inlet must be in exactly one mode.
- Inlet flow is determined by its selected mode.
- `closed_mode` must be a valid inlet mode.
- An inlet can appear in `storage_balance.outflows` if its upstream is storage.
- An inlet can appear in `storage_balance.inflows` if its downstream is storage.
- If an inlet is controlled by a `hydraulic_head_constraint`, it can be open only
  when the upstream water level is higher than the downstream level.
- In the current model, the hydraulic head rule is:

```text
storage water level >= downstream level + epsilon
```

when the inlet is not in its closed mode.

Topology example:

```json
{
  "id": "inlet_0",
  "type": "inlet",
  "index": 0,
  "upstream": "storage",
  "downstream": "sea"
}
```

User explanation:

An inlet is not the same as a pump. It does not actively force water uphill. It
can only be opened when the upstream side is high enough compared with the
downstream side. If the downstream level is equal to or higher than the upstream
level, the inlet must stay closed.
