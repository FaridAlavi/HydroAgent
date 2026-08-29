# Storage Element

A storage element represents a finite water body whose volume and water level are
controlled by the optimization model.

In the current model, there is one storage element. Its water level is computed
as:

```text
water level = volume / area
```

The storage data is defined in `storage.json`.

Required `storage.json` fields:

- `area`: positive number used to convert volume to water level.
- `initial_volume`: initial volume at time step 0.
- `min_volume`: minimum allowed storage volume.
- `max_volume`: maximum allowed storage volume.

Rules:

- `area` must be positive.
- `min_volume` must be less than or equal to `max_volume`.
- `initial_volume` must be between `min_volume` and `max_volume`.
- A storage element can receive water from inflows, pumps, or inlets.
- A storage element can send water through pumps or inlets.
- A storage element is usually the `storage` field in a `storage_balance`
  equation.

Topology example:

```json
{
  "id": "storage",
  "type": "storage"
}
```

User explanation:

The storage is the basin or reservoir whose water level we want to control. If
too much water enters, pumps or inlets may need to remove water. The optimization
keeps the storage volume within its allowed range and tries to keep the water
level close to the desired target.
