# Inflow Element

An inflow element represents an external water source that adds water to a
downstream element, usually the storage.

The inflow amount is read from a time series in `horizon.json`.

Required topology fields:

- `id`: unique element name.
- `type`: must be `"inflow"`.
- `series`: name of the time series in `horizon.json`.
- `downstream`: element that receives the inflow.

Rules:

- An inflow has only downstream.
- An inflow must not define upstream.
- An inflow is not controllable by the optimizer.
- An inflow does not have operating modes.
- An inflow can appear in `storage_balance.inflows` when its downstream is the
  storage element.
- The `series` must refer to an available time series, such as
  `discharge_sequence`.

Topology example:

```json
{
  "id": "catchment_inflow",
  "type": "inflow",
  "series": "discharge_sequence",
  "downstream": "storage"
}
```

User explanation:

The inflow is water that enters the system from outside, such as rainfall runoff
or upstream discharge. The optimizer cannot choose this amount; it is given by
the input time series.
