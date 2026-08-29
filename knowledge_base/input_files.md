# Input Files

The model input is split into several JSON files. The AI agent should help the
user update these files by asking for missing information and explaining the
rules in plain language.

Required files:

- `pumps.json`
- `inlets.json`
- `storage.json`
- `horizon.json`
- `topology.json`
- `user_constraints.json`

`pumps.json`:

```json
{
  "flow_by_mode": [[0, 0], [12, 12]],
  "min_mode_duration": [[4, 4], [4, 4]],
  "freeze": [[0, 0], [0, 0]]
}
```

`inlets.json`:

```json
{
  "flow_by_mode": [[0], [10]],
  "closed_mode": 0,
  "freeze": [[0, 0]]
}
```

`storage.json`:

```json
{
  "area": 10,
  "initial_volume": 20,
  "min_volume": 5,
  "max_volume": 200
}
```

`user_constraints.json`:

```json
{
  "pumps": [
    {
      "pump": 1,
      "time": 7,
      "mode": 2
    }
  ],
  "inlets": [
    {
      "inlet": 0,
      "time": 5,
      "mode": 2
    }
  ]
}
```

General rules:

- Lists and indexes are zero-based.
- Matrices must have the same number of columns in every row.
- Pump columns in `pumps.json` must match pump indexes in `topology.json`.
- Inlet columns in `inlets.json` must match inlet indexes in `topology.json`.
- The number of time steps in `horizon.json` limits valid user constraint times.
- Empty `user_constraints.json` or empty lists mean no extra user constraints.

User explanation:

These files separate physical data from user requests. Pump and inlet files
describe what devices can do. The storage file describes the controlled basin.
The topology file describes how everything is connected. User constraints are
temporary requests like forcing a pump or inlet to a specific mode at a specific
time.
