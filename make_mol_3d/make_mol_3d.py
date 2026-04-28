#!/usr/bin/env python3
"""Inkscape plugin: ray-traced 3D ball-and-stick molecular image via PyMOL.

RDKit (3D conformer generation) and PyMOL (rendering) both run in the
pixi-managed Python environment alongside this script.  See README.md.
"""

import os
import json
import tempfile
import subprocess
import inkex
from inkex.elements import Group

# ---------------------------------------------------------------------------
# PyMOL / RDKit helper — run in the pixi Python via subprocess
# ---------------------------------------------------------------------------
# Workspace settings and BallnStick() replicate sabari_pymolrc exactly.

_HELPER = """\
import sys, os, json, base64, tempfile, time

input_type        = sys.argv[1]               # 'smiles' or 'sdf'
mol_input         = sys.argv[2]               # SMILES string OR path to SDF
show_h            = sys.argv[3].lower() == 'true'
camera            = sys.argv[4]               # 'default' | 'front' | 'top' | 'perspective'
width             = int(sys.argv[5])
height            = int(sys.argv[6])
show_ensemble     = sys.argv[7].lower() == 'true'
num_conformers    = int(sys.argv[8])
conf_transparency = float(sys.argv[9])
DPI               = 600

# Ensemble mode is only meaningful with SMILES (need to generate multiple confs)
ensemble_mode = show_ensemble and input_type == 'smiles' and num_conformers > 1

sdf_paths    = []
cleanup_sdfs = []

# ── Step 1: produce SDF(s) ──────────────────────────────────────────────────
if input_type == 'smiles':
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem, rdMolAlign
    except ImportError:
        print(json.dumps({"error": "rdkit not available in this Python environment."}))
        sys.exit(0)

    mol = Chem.MolFromSmiles(mol_input)
    if mol is None:
        print(json.dumps({"error": f"Invalid SMILES: {mol_input!r}"}))
        sys.exit(0)

    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()

    if ensemble_mode:
        conf_ids = list(AllChem.EmbedMultipleConfs(mol, numConfs=num_conformers,
                                                    params=params))
        if not conf_ids:
            print(json.dumps({"error": "RDKit failed to embed any conformers."}))
            sys.exit(0)

        # results: [(converged_flag, energy), ...] in conf_id order
        results = AllChem.MMFFOptimizeMoleculeConfs(mol)
        scored = [(cid, results[i][1]) for i, cid in enumerate(conf_ids)
                  if results[i][0] == 0]
        if not scored:
            print(json.dumps({"error": "MMFF did not converge for any conformer."}))
            sys.exit(0)
        scored.sort(key=lambda x: x[1])     # ascending energy

        # Align all conformers to the lowest-energy one (in-place RMSD min)
        ref_cid = scored[0][0]
        for cid, _ in scored[1:]:
            try:
                rdMolAlign.AlignMol(mol, mol, prbCid=cid, refCid=ref_cid)
            except Exception:
                pass  # alignment isn't critical for rendering

        # Write each conformer to its own SDF, lowest-energy first
        for cid, _ in scored:
            tmp = tempfile.NamedTemporaryFile(suffix='.sdf', delete=False, mode='w')
            w = Chem.SDWriter(tmp.name)
            w.write(mol, confId=cid)
            w.close()
            tmp.close()
            sdf_paths.append(tmp.name)
            cleanup_sdfs.append(tmp.name)
    else:
        if AllChem.EmbedMolecule(mol, params) == -1:
            print(json.dumps({"error": "RDKit ETKDGv3 embedding failed for this SMILES."}))
            sys.exit(0)
        AllChem.MMFFOptimizeMolecule(mol)

        tmp = tempfile.NamedTemporaryFile(suffix='.sdf', delete=False, mode='w')
        w = Chem.SDWriter(tmp.name)
        w.write(mol)
        w.close()
        tmp.close()
        sdf_paths.append(tmp.name)
        cleanup_sdfs.append(tmp.name)

else:  # 'sdf'
    if not os.path.isfile(mol_input):
        print(json.dumps({"error": f"SDF file not found: {mol_input!r}"}))
        sys.exit(0)
    sdf_paths.append(mol_input)
    # not added to cleanup_sdfs — user-provided file, do not delete

# ── Step 2: PyMOL render ────────────────────────────────────────────────────
tmp_png = None
try:
    try:
        import pymol
        from pymol import cmd, preset
    except ImportError:
        print(json.dumps({"error": "pymol not available in this Python environment."}))
        sys.exit(0)

    pymol.finish_launching(['pymol', '-cq'])

    # ── Workspace settings from sabari_pymolrc ──────────────────────────────
    cmd.bg_color("white")
    cmd.set("ray_opaque_background", "off")
    cmd.set("orthoscopic", 0)
    cmd.set("transparency", 0.5)
    cmd.set("dash_gap", 0)
    cmd.set("ray_trace_mode", 1)
    cmd.set("ray_texture", 2)
    cmd.set("antialias", 3)
    cmd.set("ambient", 0.5)
    cmd.set("spec_count", 5)
    cmd.set("shininess", 50)
    cmd.set("specular", 1)
    cmd.set("reflect", 0.1)
    cmd.space("cmyk")

    bondi = {  # Bondi VDW radii from sabari_pymolrc
        'Ac':2.00,'Al':2.00,'Am':2.00,'Sb':2.00,'Ar':1.88,'As':1.85,
        'At':2.00,'Ba':2.00,'Bk':2.00,'Be':2.00,'Bi':2.00,'Bh':2.00,
        'B' :2.00,'Br':1.85,'Cd':1.58,'Cs':2.00,'Ca':2.00,'Cf':2.00,
        'C' :1.70,'Ce':2.00,'Cl':1.75,'Cr':2.00,'Co':2.00,'Cu':1.40,
        'Cm':2.00,'Ds':2.00,'Db':2.00,'Dy':2.00,'Es':2.00,'Er':2.00,
        'Eu':2.00,'Fm':2.00,'F' :1.47,'Fr':2.00,'Gd':2.00,'Ga':1.87,
        'Ge':2.00,'Au':1.66,'Hf':2.00,'Hs':2.00,'He':1.40,'Ho':2.00,
        'In':1.93,'I' :1.98,'Ir':2.00,'Fe':2.00,'Kr':2.02,'La':2.00,
        'Lr':2.00,'Pb':2.02,'Li':1.82,'Lu':2.00,'Mg':1.73,'Mn':2.00,
        'Mt':2.00,'Md':2.00,'Hg':1.55,'Mo':2.00,'Nd':2.00,'Ne':1.54,
        'Np':2.00,'Ni':1.63,'Nb':2.00,'N' :1.55,'No':2.00,'Os':2.00,
        'O' :1.52,'Pd':1.63,'P' :1.80,'Pt':1.72,'Pu':2.00,'Po':2.00,
        'K' :2.75,'Pr':2.00,'Pm':2.00,'Pa':2.00,'Ra':2.00,'Rn':2.00,
        'Re':2.00,'Rh':2.00,'Rb':2.00,'Ru':2.00,'Rf':2.00,'Sm':2.00,
        'Sc':2.00,'Sg':2.00,'Se':1.90,'Si':2.10,'Ag':1.72,'Na':2.27,
        'Sr':2.00,'S' :1.80,'Ta':2.00,'Tc':2.00,'Te':2.06,'Tb':2.00,
        'Tl':1.96,'Th':2.00,'Tm':2.00,'Sn':2.17,'Ti':2.00,'W' :2.00,
        'U' :1.86,'V' :2.00,'Xe':2.16,'Yb':2.00,'Y' :2.00,'Zn':1.39,'Zr':2.00,
    }

    # Load each SDF as its own object — conf_0 is the lowest-energy structure
    for i, sdf_path in enumerate(sdf_paths):
        cmd.load(sdf_path, f"conf_{i}")

    for elem, r in bondi.items():
        cmd.alter(f"elem {elem}", f"vdw={r}")
    cmd.rebuild()

    if not show_h:
        cmd.remove('elem H')

    # ── BallnStick() from sabari_pymolrc ────────────────────────────────────
    cmd.color("gray30", "elem C")
    cmd.set("dash_gap", 0.01)
    cmd.set("dash_radius", 0.035)
    cmd.set("surface_quality", 2)
    cmd.set("surface_type", 4)
    cmd.set("depth_cue", "off")
    preset.ball_and_stick(selection='all', mode=1)

    # ── Ensemble transparency: opaque conf_0, transparent overlays ──────────
    if len(sdf_paths) > 1:
        for i in range(1, len(sdf_paths)):
            cmd.set("sphere_transparency", conf_transparency, f"conf_{i}")
            cmd.set("stick_transparency",  conf_transparency, f"conf_{i}")

    # ── Camera preset ───────────────────────────────────────────────────────
    cmd.orient()
    cmd.zoom('all', buffer=2)

    if camera == 'top':
        cmd.rotate('x', -90)
    elif camera == 'perspective':
        cmd.set('orthoscopic', 0)

    # ── Ray-trace and save ──────────────────────────────────────────────────
    tmp_f = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    tmp_f.close()
    tmp_png = tmp_f.name

    cmd.png(tmp_png, width=width, height=height, dpi=DPI, ray=1)
    cmd.quit()
    time.sleep(0.5)

    with open(tmp_png, 'rb') as fh:
        png_b64 = base64.b64encode(fh.read()).decode()

    # Marker prefix so the plugin can pluck the JSON out of any PyMOL chatter
    print("__MOL3D_JSON__" + json.dumps({"png_b64": png_b64, "width": width, "height": height}))

finally:
    for p in cleanup_sdfs:
        if p and os.path.exists(p):
            os.unlink(p)
    if tmp_png and os.path.exists(tmp_png):
        os.unlink(tmp_png)
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_python(override: str) -> str:
    """
    Return the path to a Python interpreter that has RDKit and PyMOL installed.

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
    for candidate in [
        os.path.join(script_dir, ".pixi", "envs", "default", "bin", "python"),
        os.path.join(script_dir, ".pixi", "envs", "default", "python.exe"),
    ]:
        if os.path.isfile(candidate):
            return candidate
    return "python3"


def _run_helper(python_cmd, input_type, mol_input,
                show_h, camera, width, height,
                show_ensemble, num_conformers, conf_transparency) -> dict:
    """
    Execute the PyMOL rendering helper in a subprocess and return base64 PNG data.

    Writes _HELPER to a temp file, runs it with python_cmd, reads the single
    JSON line from stdout, and deletes the temp file unconditionally.
    Ray-tracing can be slow; the subprocess is allowed up to 300 seconds.

    Params:
        python_cmd: str : path to the Python interpreter to use
        input_type: str : "smiles" or "sdf"
        mol_input: str : SMILES string or absolute path to an SDF file
        show_h: bool : whether to show hydrogen atoms in the render
        camera: str : camera preset — "default", "front", "top", or "perspective"
        width: int : render width in pixels
        height: int : render height in pixels
        show_ensemble: bool : whether to render multiple conformers as overlays
        num_conformers: int : number of conformers to generate (used only when show_ensemble)
        conf_transparency: float : transparency [0..1] applied to non-lowest-energy conformers
    Returns:
        dict : {"png_b64": str, "width": int, "height": int} on success,
               or {"error": str} on failure
    """
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as fh:
            fh.write(_HELPER)
            tmp_path = fh.name

        result = subprocess.run(
            [python_cmd, tmp_path,
             input_type, mol_input,
             str(show_h), camera,
             str(width), str(height),
             str(show_ensemble), str(num_conformers), str(conf_transparency)],
            capture_output=True,
            text=True,
            timeout=300,   # ray-tracing can be slow
        )
        stdout = result.stdout
        if not stdout.strip():
            return {
                "error": (
                    f"Helper produced no output.\n"
                    f"Python: {python_cmd}\n"
                    f"stderr: {result.stderr.strip()}"
                )
            }

        # PyMOL prints chatter to stdout. Look for the marker prefix; if absent,
        # fall back to parsing the whole stdout (early errors print plain JSON).
        marker = "__MOL3D_JSON__"
        idx = stdout.rfind(marker)
        payload = stdout[idx + len(marker):].splitlines()[0] if idx >= 0 else stdout.strip()
        return json.loads(payload)

    except FileNotFoundError:
        return {
            "error": (
                f"Python interpreter not found: {python_cmd!r}\n"
                "Run 'pixi install' in the plugin directory, then redeploy."
            )
        }
    except subprocess.TimeoutExpired:
        return {"error": "Timed out during ray-tracing (>5 min)."}
    except json.JSONDecodeError as exc:
        return {"error": f"Could not parse helper output: {exc}\n"
                         f"stderr: {result.stderr.strip()}"}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Extension
# ---------------------------------------------------------------------------

class MakeMol3D(inkex.EffectExtension):
    """
    Inkscape effect extension that embeds a ray-traced 3D molecular image via PyMOL.

    For SMILES input, RDKit generates a 3D conformer using ETKDGv3 followed by MMFF
    geometry optimisation before passing the structure to PyMOL. For SDF input the
    file is loaded directly. PyMOL applies the sabari_pymolrc workspace settings
    (ray_trace_mode=1, ray_texture=2, antialias=3, CMYK color space) and the
    BallnStick(mode=1) preset with Bondi VDW radii, then ray-traces at 600 DPI.
    The result is embedded as a base64 PNG <image> element in the SVG document.

    Ensemble mode (SMILES only) generates multiple conformers, MMFF-optimises them,
    aligns each to the lowest-energy structure, and renders all of them in PyMOL with
    the lowest-energy structure opaque and the rest as transparent overlays.

    Params:
        input_type: str : "smiles" or "sdf"
        smiles: str : SMILES string (used when input_type is "smiles")
        sdf_file: str : path to an SDF file (used when input_type is "sdf")
        show_hydrogens: bool : whether to include hydrogen atoms in the render
        camera: str : camera preset — "default", "front", "top", or "perspective"
        render_width: int : output image width in pixels (default 1800 = 3" at 600 DPI)
        render_height: int : output image height in pixels (default 1200 = 2" at 600 DPI)
        show_ensemble: bool : whether to render a conformer ensemble (SMILES input only)
        num_conformers: int : number of conformers to generate when show_ensemble is true
        conformer_transparency: float : transparency for overlay conformers (0 = opaque, 1 = invisible)
        python_cmd: str : override path for the RDKit/PyMOL interpreter; blank = auto-detect
    """

    def add_arguments(self, pars):
        """
        Register extension parameters from the INX manifest.

        Params:
            pars: argparse.ArgumentParser : Inkscape-provided argument parser
        Returns:
            None
        """
        pars.add_argument("--tab",                    type=str,           default="molecule")
        pars.add_argument("--input_type",             type=str,           default="smiles")
        pars.add_argument("--smiles",                 type=str,           default="c1ccccc1[N+](=O)[O-]")
        pars.add_argument("--sdf_file",               type=str,           default="")
        pars.add_argument("--show_hydrogens",         type=inkex.Boolean, default=False)
        pars.add_argument("--camera",                 type=str,           default="default")
        pars.add_argument("--render_width",           type=int,           default=1800)
        pars.add_argument("--render_height",          type=int,           default=1200)
        pars.add_argument("--show_ensemble",          type=inkex.Boolean, default=False)
        pars.add_argument("--num_conformers",         type=int,           default=10)
        pars.add_argument("--conformer_transparency", type=float,         default=0.7)
        pars.add_argument("--python_cmd",             type=str,           default="")

    def effect(self):
        """
        Generate the ray-traced molecular image and embed it in the document.

        Validates input, delegates rendering to _run_helper, then inserts an SVG
        <image> element with both href and xlink:href set for compatibility across
        Inkscape versions. The PNG is embedded as a base64 data URI so the document
        is fully self-contained with no external file references.

        Params:
            None
        Returns:
            None
        """
        o = self.options

        python_cmd = _find_python(o.python_cmd)

        if o.input_type == "sdf":
            mol_input = o.sdf_file.strip()
            if not mol_input:
                inkex.errormsg("SDF File path is empty. "
                               "Select a file or switch Input Type to SMILES.")
                return
        else:
            mol_input = o.smiles.strip()
            if not mol_input:
                inkex.errormsg("SMILES string is empty.")
                return

        data = _run_helper(
            python_cmd,
            o.input_type,
            mol_input,
            o.show_hydrogens,
            o.camera,
            o.render_width,
            o.render_height,
            o.show_ensemble,
            o.num_conformers,
            o.conformer_transparency,
        )

        if "error" in data:
            inkex.errormsg(data["error"])
            return

        png_b64 = data["png_b64"]
        W       = data["width"]
        H       = data["height"]

        # Embed as base64 <image> in the SVG
        root = self.svg.add(Group.new(label="mol_3d"))
        img  = root.add(inkex.Image())
        img.set("x", "0")
        img.set("y", "0")
        img.set("width",  str(W))
        img.set("height", str(H))
        # Set both href forms for maximum Inkscape compatibility
        img.set("href", f"data:image/png;base64,{png_b64}")
        img.set("{http://www.w3.org/1999/xlink}href",
                f"data:image/png;base64,{png_b64}")


if __name__ == "__main__":
    MakeMol3D().run()
