# make_clustered_points

## Purpose

Generates a rectangle filled with point clouds sampled from Gaussian distributions,
coloured by cluster using the Nord Aurora and Frost palette. Intended for producing
stylized data-visualization figures directly inside Inkscape without any external
dependencies beyond the `inkex` library that ships with Inkscape itself.

## Module contents

**`make_clustered_points.py`** — The sole implementation file. The `MakeClusteredPoints`
class reads user parameters, places cluster centers via rejection sampling, samples
per-cluster standard deviations from a log-normal distribution, then scatters dots
with Gaussian noise. All generated points are wrapped in a single SVG `clipPath`
element so they are hard-clipped to the rectangle boundary even though their
coordinates may extend outside it — this is preferable to discarding out-of-bounds
points, which would bias clusters near edges. The rejection sampler allows up to 500
placement attempts per center before falling back to an unconstrained placement, so
the requested cluster count is always honoured regardless of how densely packed the
configuration is.

**`make_clustered_points.inx`** — Inkscape manifest declaring two UI tabs: *Layout*
(rectangle dimensions) and *Clusters* (cluster count, point density, spread and
size sliders, random seed). All dimensional parameters are expressed as percentages
of `min(width, height)` so output scales correctly when the canvas size is changed.

## Data contracts

| Parameter | Type | Range | Unit |
|---|---|---|---|
| `rect_width`, `rect_height` | float | 50–5000 | px |
| `spread_pct` | float | 1–30 | % of min(W, H) |
| `point_radius_pct` | float | 0.1–10 | % of min(W, H) |
| `num_clusters` | int | 1–20 | — |
| `points_per_cluster` | int | 5–1000 | — |

**Output:** a single `<g label="clustered_points">` group containing a background
rectangle, a `<clipPath>` in `<defs>`, and one `<g label="cluster_N">` per cluster
holding the dot circles.

## Critical parameters

- **`spread_pct` max is 30**, not 50. The upper limit was deliberately reduced to 0.6×
  after visual testing showed values above ~30% produced indistinguishable overlap
  even with rejection sampling.
- **Rejection sampling minimum separation = 3 × spread**. If this is too strict for
  a given combination of cluster count, canvas size, and spread, the fallback places
  centers without the constraint rather than silently dropping clusters.
- **Per-cluster sigma** is drawn from `lognormal(log(spread), 0.4)`. The 0.4
  log-scale deviation is hardcoded and controls how much cluster sizes vary from
  each other; it is not exposed in the UI.

## Dependencies on other modules

Standalone — no imports beyond the Python standard library and `inkex`. Does not
use the shared pixi environment.
