# make_neural_network

## Purpose

Generates stylized neural network schematics as SVG diagrams inside Inkscape.
Each layer is a vertical column of circles connected by lines, with one Nord
Frost/Aurora color assigned per layer. Intended for producing clean architecture
figures for papers or slides without any external dependencies.

## Module contents

**`make_neural_network.py`** — The sole implementation file. `MakeNeuralNetwork`
parses the layer topology from a comma-separated string, computes vertically centred
node positions, and draws connections before nodes so that node circles naturally
occlude line endpoints without needing explicit clipping. Canvas width and height
are derived automatically from the topology and spacing parameters, so the diagram
always fits the content with consistent padding (`3 × node_radius` on each side).

For local connectivity, each source node `si` is mapped to a target index
`k = round(si × (n_dst − 1) / max(n_src − 1, 1))` and connected to `k−1`, `k`,
`k+1` (clamped). This proportional mapping keeps local receptive fields visually
sensible even when adjacent layers have different node counts.

**`make_neural_network.inx`** — Inkscape manifest with two tabs: *Network* (layer
topology string, connection type, opacity and width) and *Style* (node radius,
horizontal and vertical spacing).

## Data contracts

| Parameter | Type | Format / Range |
|---|---|---|
| `layers` | str | comma-separated integers, e.g. `"3,4,4,2"` |
| `connection_type` | str | `"none"`, `"full"`, or `"local"` |
| `node_radius` | float | px; canvas padding = 3 × radius |
| `h_spacing` | float | px between layer center x-coordinates |
| `v_spacing` | float | px between node center y-coordinates |

**Canvas size (auto-computed):**
- `W = (n_layers − 1) × h_spacing + 2 × pad`
- `H = (max_nodes − 1) × v_spacing + 2 × pad`

**Output:** a `<g label="neural_network">` group containing a background rectangle,
an optional `<g label="connections">` group, and one `<g label="layer_N">` per layer.

## Critical parameters

- **`layers` must be comma-separated integers.** Non-integer values raise an error
  via `inkex.errormsg` and abort without modifying the document.
- **Single-layer topology** (`layers = "5"`) produces nodes with no connections
  regardless of `connection_type`, since connections are only drawn between
  adjacent layer pairs.
- **Local connectivity with `n_src = 1`** maps the single source node to index 0
  in the target layer and connects to indices 0 and 1 (if present). The
  `max(n_src − 1, 1)` guard prevents division by zero.

## Dependencies on other modules

Standalone — no imports beyond the Python standard library and `inkex`. Does not
use the shared pixi environment.
