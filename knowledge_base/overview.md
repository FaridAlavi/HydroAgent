# Pump And Inlet Scheduling Knowledge Base

This knowledge base describes the elements that can appear in the pump and inlet
scheduling model. It is intended for an AI agent that helps a user define input
files and topology.

The model represents water moving between elements. A storage element has a
finite volume and water level. Inflows add water to storage. Pumps and inlets can
move water between an upstream element and a downstream element. A level element
represents an external water body, such as the sea, with a known water level time
series.

When communicating with users, explain that indexes are zero-based unless a user
explicitly asks for natural-language numbering to be converted. For example,
`pump 0` is the first pump, `mode 0` is the first mode, and `time 0` is the
first time step.

Core files:

- `pumps.json`: pump mode flow rates, minimum mode durations, and pump freeze
  states.
- `inlets.json`: inlet mode flow rates, closed inlet mode, and inlet freeze
  states.
- `storage.json`: storage area, initial volume, and volume bounds.
- `horizon.json`: time horizon and time series, such as discharge and sea level.
- `topology.json`: elements, connections, and equations.
- `user_constraints.json`: optional fixed mode constraints requested by a user.

The agent should use the knowledge base to explain rules and collect complete
input from the user. Python validation remains the final guardrail.
