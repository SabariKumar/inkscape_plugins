#!/usr/bin/env python3
"""Inkscape plugin: draw a stylized molecular graph from a SMILES string.

RDKit is called via subprocess using the pixi-managed Python that lives
alongside this script in .pixi/envs/default/bin/python.  See README.md.
"""

import os
import sys
import json
import math
import tempfile
import subprocess
import inkex
from inkex.elements import Group, Rectangle
from inkex import Circle, PathElement, TextElement

# ---------------------------------------------------------------------------
# Pastel CPK color palette
# ---------------------------------------------------------------------------
CPK_PASTEL = {
    "H":  "#F0F0F0",  # near-white
    "C":  "#C8C8C8",  # light gray  (CPK: black)
    "N":  "#A8C4F0",  # pastel blue (CPK: dark blue)
    "O":  "#FFB3B3",  # pastel red  (CPK: red)
    "F":  "#AAEEBB",  # pastel green
    "Cl": "#AADDAA",  # pastel green
    "Br": "#DEB8A0",  # pastel brown
    "I":  "#D4A4D4",  # pastel purple
    "S":  "#FFFAA0",  # pastel yellow
    "P":  "#FFD8A0",  # pastel orange
}
DEFAULT_ATOM_COLOR = "#D0D0D0"

BOND_COLOR = "#999999"  # neutral gray for all bonds

# Relative radius per element (multiplied by the atom_radius parameter)
ATOM_RADIUS_SCALE = {
    "H":  0.60, "C":  0.80, "N":  0.78, "O":  0.75,
    "F":  0.68, "Cl": 1.00, "Br": 1.10, "I":  1.25,
    "S":  1.00, "P":  1.00,
}
DEFAULT_RADIUS_SCALE = 0.85

# ---------------------------------------------------------------------------
# RDKit helper — run in the pixi Python via subprocess, returns JSON
# ---------------------------------------------------------------------------
_RDKIT_HELPER = """\
import sys, json
try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
except ImportError:
    print(json.dumps({"error": "rdkit not available in this Python environment."}))
    sys.exit(0)

smiles   = sys.argv[1]
remove_h = sys.argv[2].lower() == "true"

mol = Chem.MolFromSmiles(smiles)
if mol is None:
    print(json.dumps({"error": f"Could not parse SMILES: {smiles!r}"}))
    sys.exit(0)

mol = Chem.AddHs(mol)
AllChem.Compute2DCoords(mol)
if remove_h:
    mol = Chem.RemoveHs(mol)

try:
    Chem.Kekulize(mol, clearAromaticFlags=True)
except Exception:
    pass  # fall back to whatever bond types are present

conf  = mol.GetConformer()
atoms = []
for atom in mol.GetAtoms():
    pos = conf.GetAtomPosition(atom.GetIdx())
    atoms.append({
        "idx":    atom.GetIdx(),
        "symbol": atom.GetSymbol(),
        "x":      float(pos.x),
        "y":      float(pos.y),
        "charge": atom.GetFormalCharge(),
    })

BOND_MAP = {"SINGLE": "single", "DOUBLE": "double",
            "TRIPLE": "triple", "AROMATIC": "aromatic"}
bonds = []
for bond in mol.GetBonds():
    bt = str(bond.GetBondType()).split(".")[-1]
    bonds.append({
        "begin": bond.GetBeginAtomIdx(),
        "end":   bond.GetEndAtomIdx(),
        "type":  BOND_MAP.get(bt, "single"),
    })

print(json.dumps({"atoms": atoms, "bonds": bonds}))
"""


def _find_python(override: str) -> str:
    """
    Return the path to a Python interpreter that has RDKit installed.

    Checks the user override first, then the bundled pixi environment
    co-located with this script, then falls back to system python3.

    Params:
        override: str : explicit interpreter path from the plugin UI, or empty string
    Returns:
        str : absolute path to a Python executable
    """
    if override and override.strip():
        return override.strip()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, ".pixi", "envs", "default", "bin", "python"),
        os.path.join(script_dir, ".pixi", "envs", "default", "python.exe"),  # Windows
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path

    return "python3"  # fallback — may or may not have rdkit


def _run_rdkit(smiles: str, remove_h: bool, python_cmd: str) -> dict:
    """
    Execute the RDKit helper in a subprocess and return parsed atom/bond data.

    Writes _RDKIT_HELPER to a temp file, runs it with python_cmd, reads the
    single JSON line from stdout, and deletes the temp file unconditionally.

    Params:
        smiles: str : SMILES string to parse and embed in 2D
        remove_h: bool : whether to strip explicit hydrogens before output
        python_cmd: str : path to the Python interpreter to use
    Returns:
        dict : {"atoms": [...], "bonds": [...]} on success, or {"error": str} on failure
    """
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as fh:
            fh.write(_RDKIT_HELPER)
            tmp_path = fh.name

        result = subprocess.run(
            [python_cmd, tmp_path, smiles, str(remove_h)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        stdout = result.stdout.strip()
        if not stdout:
            return {
                "error": (
                    f"RDKit helper produced no output.\n"
                    f"Python: {python_cmd}\n"
                    f"stderr: {result.stderr.strip()}"
                )
            }
        return json.loads(stdout)

    except FileNotFoundError:
        return {
            "error": (
                f"Python interpreter not found: {python_cmd!r}\n"
                "Set the Python Path on the Advanced tab, or run "
                "'pixi install' in the plugin directory."
            )
        }
    except subprocess.TimeoutExpired:
        return {"error": "Timed out while computing 2D coordinates."}
    except json.JSONDecodeError as exc:
        return {"error": f"Could not parse helper output: {exc}"}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _perp(x1, y1, x2, y2):
    """
    Return the perpendicular unit vector to the segment (x1,y1)→(x2,y2).

    Used to offset parallel lines when rendering double and triple bonds.
    Returns (0.0, 1.0) for a zero-length segment to avoid division by zero.

    Params:
        x1: float : x-coordinate of segment start
        y1: float : y-coordinate of segment start
        x2: float : x-coordinate of segment end
        y2: float : y-coordinate of segment end
    Returns:
        tuple[float, float] : (px, py) perpendicular unit vector
    """
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        return 0.0, 1.0
    return -dy / length, dx / length


def _draw_bond(group, x1, y1, x2, y2, bond_type, width, spacing):
    """
    Draw a bond between two atom positions into the given SVG group.

    Single and aromatic bonds produce one centered line. Double bonds produce
    two parallel lines offset by ±spacing/2 along the perpendicular vector.
    Triple bonds produce three lines: one central and two offset by ±spacing.

    Params:
        group: inkex.elements.Group : parent SVG group to add path elements to
        x1: float : x-coordinate of the first atom center
        y1: float : y-coordinate of the first atom center
        x2: float : x-coordinate of the second atom center
        y2: float : y-coordinate of the second atom center
        bond_type: str : one of "single", "aromatic", "double", "triple"
        width: float : stroke width in pixels
        spacing: float : separation between parallel lines for multi-order bonds
    Returns:
        None
    """
    px, py = _perp(x1, y1, x2, y2)

    def line(ax, ay, bx, by):
        el = group.add(PathElement())
        el.set("d", f"M {ax:.3f},{ay:.3f} L {bx:.3f},{by:.3f}")
        el.style = inkex.Style({
            "stroke":          BOND_COLOR,
            "stroke-width":    str(width),
            "stroke-linecap":  "round",
            "fill":            "none",
        })

    if bond_type in ("single", "aromatic"):
        line(x1, y1, x2, y2)
    elif bond_type == "double":
        o = spacing / 2
        line(x1 + px * o, y1 + py * o, x2 + px * o, y2 + py * o)
        line(x1 - px * o, y1 - py * o, x2 - px * o, y2 - py * o)
    elif bond_type == "triple":
        line(x1, y1, x2, y2)
        line(x1 + px * spacing, y1 + py * spacing,
             x2 + px * spacing, y2 + py * spacing)
        line(x1 - px * spacing, y1 - py * spacing,
             x2 - px * spacing, y2 - py * spacing)


# ---------------------------------------------------------------------------
# Extension
# ---------------------------------------------------------------------------

class MakeMolGraph(inkex.EffectExtension):
    """
    Inkscape effect extension that draws a stylized 2D molecular graph from a SMILES string.

    RDKit runs in a subprocess (pixi-managed Python) to parse the SMILES, compute
    2D coordinates, and kekulize bond orders. Atoms are rendered as pastel CPK-colored
    circles; bonds are drawn as gray SVG paths with optional parallel lines for
    double/triple bond order. Aromatic bonds are treated as single lines by default.

    Params:
        smiles: str : SMILES string for the molecule to draw
        show_hydrogens: bool : whether to include explicit hydrogen atoms
        render_atomic_symbols: bool : whether to draw element labels on atoms
        show_carbon_labels: bool : whether to label carbon atoms (requires render_atomic_symbols)
        render_bond_order: bool : whether to draw double/triple bonds as parallel lines
        scale: float : pixels per RDKit coordinate unit (~1.5 Å per bond length)
        atom_radius: float : base circle radius in pixels, scaled per element by ATOM_RADIUS_SCALE
        bond_width: float : bond stroke width in pixels
        bond_spacing: float : gap between parallel lines for multi-order bonds in pixels
        python_cmd: str : override path for the RDKit Python interpreter; blank = auto-detect
    """

    def add_arguments(self, pars):
        """
        Register extension parameters from the INX manifest.

        Params:
            pars: argparse.ArgumentParser : Inkscape-provided argument parser
        Returns:
            None
        """
        pars.add_argument("--tab",                type=str,          default="molecule")
        pars.add_argument("--smiles",             type=str,          default="c1ccccc1[N+](=O)[O-]")
        pars.add_argument("--show_hydrogens",       type=inkex.Boolean, default=False)
        pars.add_argument("--render_atomic_symbols", type=inkex.Boolean, default=False)
        pars.add_argument("--show_carbon_labels",  type=inkex.Boolean, default=False)
        pars.add_argument("--render_bond_order",   type=inkex.Boolean, default=False)
        pars.add_argument("--scale",               type=float,        default=50.0)
        pars.add_argument("--atom_radius",         type=float,        default=36.0)
        pars.add_argument("--bond_width",          type=float,        default=1.0)
        pars.add_argument("--bond_spacing",        type=float,        default=4.0)
        pars.add_argument("--python_cmd",         type=str,          default="")

    def effect(self):
        """
        Generate the molecular graph SVG and add it to the document.

        Calls _run_rdkit to obtain atom positions and bond topology, applies
        a y-axis flip to convert RDKit (y-up) coordinates to SVG (y-down) space,
        draws bonds first then atom circles and optional labels on top.

        Params:
            None
        Returns:
            None
        """
        o = self.options

        python_cmd = _find_python(o.python_cmd)
        remove_h   = not o.show_hydrogens
        mol_data   = _run_rdkit(o.smiles, remove_h, python_cmd)

        if "error" in mol_data:
            inkex.errormsg(mol_data["error"])
            return

        atoms = mol_data["atoms"]
        bonds = mol_data["bonds"]

        if not atoms:
            inkex.errormsg("No atoms found in the molecule.")
            return

        # --- coordinate transform: RDKit → SVG pixels ----------------------
        xs    = [a["x"] for a in atoms]
        ys    = [a["y"] for a in atoms]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        pad = o.atom_radius * 3
        W   = max((max_x - min_x) * o.scale + 2 * pad, 2 * pad)
        H   = max((max_y - min_y) * o.scale + 2 * pad, 2 * pad)

        def tx(x, y):
            # Flip y-axis (RDKit: y-up, SVG: y-down)
            return (x - min_x) * o.scale + pad, (max_y - y) * o.scale + pad

        atom_px = {a["idx"]: tx(a["x"], a["y"]) for a in atoms}
        atom_r  = {
            a["idx"]: ATOM_RADIUS_SCALE.get(a["symbol"], DEFAULT_RADIUS_SCALE)
                      * o.atom_radius
            for a in atoms
        }

        # --- build SVG ------------------------------------------------------
        root = self.svg.add(Group.new(label="mol_graph"))

        bg = root.add(Rectangle.new(0, 0, W, H))
        bg.style = inkex.Style({
            "fill":         "#FFFFFF",
            "stroke":       "#000000",
            "stroke-width": "1",
        })

        # Bonds (drawn first, underneath atoms)
        bond_group = root.add(Group.new(label="bonds"))
        for bond in bonds:
            x1, y1 = atom_px[bond["begin"]]
            x2, y2 = atom_px[bond["end"]]
            bond_type = bond["type"] if o.render_bond_order else "single"
            _draw_bond(bond_group, x1, y1, x2, y2,
                       bond_type, o.bond_width, o.bond_spacing)

        # Atoms + labels (drawn on top)
        atom_group = root.add(Group.new(label="atoms"))
        for atom in atoms:
            x, y   = atom_px[atom["idx"]]
            r      = atom_r[atom["idx"]]
            color  = CPK_PASTEL.get(atom["symbol"], DEFAULT_ATOM_COLOR)
            symbol = atom["symbol"]

            dot = atom_group.add(Circle.new(center=(x, y), radius=r))
            dot.style = inkex.Style({
                "fill":         color,
                "stroke":       "#666666",
                "stroke-width": str(max(0.5, o.atom_radius * 0.07)),
            })

            if o.render_atomic_symbols and not (symbol == "C" and not o.show_carbon_labels):
                lbl = atom_group.add(TextElement())
                lbl.set("x", f"{x:.3f}")
                lbl.set("y", f"{y:.3f}")
                lbl.style = inkex.Style({
                    "font-size":          f"{r * 1.1:.1f}px",
                    "font-family":        "sans-serif",
                    "font-weight":        "bold",
                    "text-anchor":        "middle",
                    "dominant-baseline":  "central",
                    "fill":               "#333333",
                    "stroke":             "none",
                })
                lbl.text = symbol


if __name__ == "__main__":
    MakeMolGraph().run()
