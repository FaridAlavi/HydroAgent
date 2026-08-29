# Level Element

A level element represents an external water body with a known water level time
series. In this project, the typical level element is the sea.

A level element does not have a finite storage volume in the optimization model.
Its level is read from a time series in `horizon.json`.

Required topology fields:

- `id`: unique element name.
- `type`: must be `"level"`.
- `series`: name of the time series in `horizon.json`.

Optional topology fields:

- `upstream`: list of elements that discharge into this level element.

Rules:

- A level element has no downstream element.
- A level element does not have a volume decision variable.
- A level element can be downstream of pumps or inlets.
- In hydraulic head constraints, a level element can be the `lower` element.
- The `series` must refer to an available time series, such as `sea_level`.

Topology example:

```json
{
  "id": "sea",
  "type": "level",
  "series": "sea_level",
  "upstream": ["pump_0", "inlet_0"]
}
```

User explanation:

The level element is the outside water body. For example, if the downstream side
is the sea, the model uses the known sea level at each time step. Some structures,
especially inlets, may only be allowed to open when the upstream water level is
higher than this downstream level.
