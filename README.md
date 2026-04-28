# Inkscape Plugins

A small collection of Inkscape extensions for generating stylized scientific
figures directly inside Inkscape — clustered point distributions, neural network
schematics, 2D molecular graphs, and ray-traced 3D molecular images.

All plugins appear under **Extensions → Generate** after deployment.

## Plugins

| Plugin | What it does | Deps |
|---|---|---|
| [`make_clustered_points`](make_clustered_points/README.md) | Rectangle filled with Gaussian-clustered points using the Nord palette | inkex only |
| [`make_neural_network`](make_neural_network/README.md) | Stylized neural-network schematic from a comma-separated layer topology | inkex only |
| [`make_mol_graph`](make_mol_graph/README.md) | 2D molecular graph from SMILES with pastel CPK colors and gray bonds | rdkit |
| [`make_mol_3d`](make_mol_3d/README.md) | Ray-traced 3D ball-and-stick rendering with optional conformer ensembles | rdkit + pymol-open-source |

The two molecular plugins call out to a shared [pixi](https://prefix.dev/) environment
(`shared_env/`) for RDKit and PyMOL, since Inkscape's bundled Python cannot install
those packages directly. The other two plugins have no external dependencies.

## Installation

You'll need [pixi](https://pixi.sh) installed (one-line install:
`curl -fsSL https://pixi.sh/install.sh | bash`).

Then from the repo root:

```sh
./deploy.sh
```

The script prompts for your Inkscape **User Extensions** path. To find it:

> **Inkscape → Edit → Preferences → System → User extensions**

Copy that path and paste it into the prompt. The script will:

1. Build the shared pixi environment (`pixi install` in `shared_env/`) — this
   pulls down RDKit and PyMOL on the first run and may take a few minutes.
2. Copy every plugin's `.py` and `.inx` files to your extensions folder.
3. Copy the shared `.pixi/` directory alongside them so the molecular plugins
   can find their Python interpreter.

Restart Inkscape and the new menu items will be available under
**Extensions → Generate**.

## Re-deploying after changes

Run `./deploy.sh` again. The script overwrites the deployed files in place; the
shared `.pixi/` is reused unless you've changed `shared_env/pixi.toml`.

## Repository layout

```
inkscape_plugins/
├── deploy.sh                       Interactive deploy script
├── shared_env/pixi.toml            Shared rdkit + pymol-open-source environment
├── make_clustered_points/          Plugin (.py + .inx + README)
├── make_neural_network/            Plugin (.py + .inx + README)
├── make_mol_graph/                 Plugin (.py + .inx + README)
├── make_mol_3d/                    Plugin (.py + .inx + README)
└── README.md                       This file
```
