# make_mol_3d

![Conformer ensemble of cyclohexylmethanol](example_ensemble.png)

*Cyclohexylmethanol (`OCC1CCCCC1`) rendered with conformer ensemble enabled
(8 conformers, 0.7 transparency on overlays). The lowest-energy structure is
opaque; the rigid ring overlays nearly perfectly, while the rotatable
hydroxymethyl arm shows the spread of accessible orientations.*

## Purpose

Generates ray-traced 3D ball-and-stick molecular images inside Inkscape using PyMOL.
Accepts either a SMILES string (3D geometry generated automatically by RDKit) or a
pre-computed SDF file. The rendered PNG is embedded directly in the SVG as a base64
data URI so the document is fully self-contained. Rendering settings replicate the
`sabari_pymolrc` configuration exactly, including Bondi VDW radii, CMYK color space,
and the `BallnStick(mode=1)` preset.

## Module contents

**`make_mol_3d.py`** — Main extension file. Contains the embedded `_HELPER` script
(a string literal), two module-level functions, and the `MakeMol3D` extension class.

- `_HELPER`: Complete Python script run in the pixi subprocess. Handles both input
  branches (SMILES → RDKit ETKDGv3 + MMFF → SDF; or direct SDF load), applies all
  PyMOL workspace settings and the BallnStick preset, ray-traces to a temp PNG at
  600 DPI, base64-encodes it, and prints a single JSON line to stdout. Temp files
  are cleaned up in a `finally` block.

- `_find_python(override)`: Resolves the Python interpreter to use. Looks for the
  pixi environment at `.pixi/envs/default/bin/python` relative to the script's own
  location (i.e., the Inkscape extensions folder after deployment).

- `_run_helper(...)`: Writes `_HELPER` to a `NamedTemporaryFile`, invokes it via
  `subprocess.run` with a 300-second timeout, and parses the JSON result. All
  errors — import failures, invalid input, timeouts — are returned as
  `{"error": str}` and surfaced to the user via `inkex.errormsg`.

- `MakeMol3D`: The Inkscape extension class. Validates input, calls `_run_helper`,
  and inserts an SVG `<image>` element with both `href` and `xlink:href` attributes
  set for compatibility across Inkscape versions.

**`make_mol_3d.inx`** — Inkscape manifest with three tabs: *Molecule* (input type,
SMILES field, SDF file picker, hydrogen toggle), *Render* (camera preset, pixel
dimensions), and *Advanced* (Python interpreter override).

## Data contracts

**Inputs:**

| Parameter | Type | Description |
|---|---|---|
| `input_type` | str | `"smiles"` or `"sdf"` |
| `smiles` | str | Valid SMILES string; ignored when `input_type = "sdf"` |
| `sdf_file` | str | Absolute path to an SDF file; ignored when `input_type = "smiles"` |
| `show_hydrogens` | bool | Include H atoms in render (default: false) |
| `camera` | str | `"default"`, `"front"`, `"top"`, or `"perspective"` |
| `render_width` / `render_height` | int | Pixel dimensions; default 1800 × 1200 = 3" × 2" at 600 DPI |
| `show_ensemble` | bool | Render multiple superimposed conformers (SMILES input only) |
| `num_conformers` | int | Conformers to generate when ensemble is on (default 10) |
| `conformer_transparency` | float | Transparency of overlay conformers; 0 = opaque, 1 = invisible (default 0.7) |

**Helper stdout contract:**
```json
{"png_b64": "<base64 string>", "width": 1800, "height": 1200}
```
Or on failure:
```json
{"error": "<message>"}
```

**Output:** a `<g label="mol_3d">` group containing a single `<image>` element
with the PNG embedded as a `data:image/png;base64,...` URI.

## Critical parameters

- **Bondi VDW radii must be applied *after* `cmd.load()`**, not before. PyMOL's
  `cmd.alter()` operates on loaded atoms; calling it on an empty scene is a no-op.
  The helper applies them immediately after loading the SDF.
- **Ray-tracing timeout is 300 seconds.** Large or complex molecules with many atoms
  may exceed this on slow hardware. The timeout can be raised by editing `_run_helper`
  directly.
- **Both `href` and `xlink:href` are set** on the embedded `<image>` element.
  Inkscape 1.x prefers `href` (SVG 2.0) but older versions require `xlink:href`.
- **Camera presets all start from `cmd.orient()`**. `top` additionally rotates
  −90° around x; `perspective` explicitly re-enables `orthoscopic=0` (which is
  already the default from the pymolrc settings). `front` and `default` are
  effectively identical — both use the `orient()` result without further rotation.
- **SMILES with no embeddable 3D geometry** (e.g., highly strained or exotic
  structures where ETKDGv3 fails) will return an error from the helper rather than
  silently producing a bad structure.
- **Ensemble mode requires SMILES input.** With SDF input the ensemble flag is
  silently ignored — single-conformer rendering happens regardless. Multi-conformer
  SDFs are not unpacked.
- **Ensemble alignment uses `rdMolAlign.AlignMol`** to superimpose each conformer
  onto the lowest-energy one in RDKit before writing SDFs. PyMOL's `align` is not
  used (it is sequence-based and unsuitable for small molecules).
- **Ensemble loads each conformer as a separate PyMOL object** (`conf_0`, `conf_1`, …)
  so per-object transparency can be applied via `sphere_transparency` and
  `stick_transparency`. `conf_0` is always the lowest-energy structure and remains
  opaque.

## Dependencies on other modules

Requires the **shared pixi environment** (`shared_env/pixi.toml`) with:
- `rdkit >= 2023` — ETKDGv3 conformer generation and MMFF optimisation
- `pymol-open-source >= 2.5` — headless ray-traced rendering

The pixi Python must be co-located with the plugin in the Inkscape extensions folder
(deployed by `deploy.sh`). See the repo-level `CLAUDE.md` for the discovery mechanism.
