#!/usr/bin/env python3
"""Inkscape plugin: draw a neural network schematic."""

import random
import inkex
from inkex.elements import Group, Rectangle
from inkex import Circle, PathElement

# Named Nord colors — used by both the default cycle order and custom mode
NORD_NAMED = {
    "frost_light_blue": "#88C0D0",
    "frost_blue":       "#81A1C1",
    "frost_dark_blue":  "#5E81AC",
    "frost_teal":       "#8FBCBB",
    "aurora_red":       "#BF616A",
    "aurora_orange":    "#D08770",
    "aurora_yellow":    "#EBCB8B",
    "aurora_green":     "#A3BE8C",
    "aurora_purple":    "#B48EAD",
}

# Default cycle order (Frost first, then Aurora — matches the previous behaviour)
NORD_LAYER_COLORS = [
    NORD_NAMED["frost_light_blue"],
    NORD_NAMED["frost_blue"],
    NORD_NAMED["frost_dark_blue"],
    NORD_NAMED["aurora_red"],
    NORD_NAMED["aurora_orange"],
    NORD_NAMED["aurora_yellow"],
    NORD_NAMED["aurora_green"],
    NORD_NAMED["aurora_purple"],
    NORD_NAMED["frost_teal"],
]

NORD_DARK  = "#2E3440"  # node stroke
NORD_MID   = "#4C566A"  # connection stroke


def _resolve_layer_colors(n_layers: int, mode: str,
                           custom_spec: str, seed: int) -> list:
    """
    Build a list of n_layers hex color strings according to the chosen mode.

    Modes:
      - "default": cycle through NORD_LAYER_COLORS in fixed order
      - "random":  shuffle the Nord palette using `seed`, then cycle if needed
      - "custom":  parse custom_spec (comma-separated Nord names), cycle to fill

    Unknown names in custom_spec are dropped silently. If no valid names are
    given in custom mode, falls back to the default cycle.

    Params:
        n_layers: int : number of layers requiring a color
        mode: str : one of "default", "random", "custom"
        custom_spec: str : comma-separated color names (used when mode == "custom")
        seed: int : RNG seed (used when mode == "random")
    Returns:
        list[str] : exactly n_layers hex color strings
    """
    if mode == "random":
        rng = random.Random(seed)
        palette = list(NORD_NAMED.values())
        rng.shuffle(palette)
        return [palette[i % len(palette)] for i in range(n_layers)]

    if mode == "custom":
        chosen = []
        for name in (n.strip().lower() for n in custom_spec.split(",")):
            if name and name in NORD_NAMED:
                chosen.append(NORD_NAMED[name])
        if not chosen:
            chosen = NORD_LAYER_COLORS
        return [chosen[i % len(chosen)] for i in range(n_layers)]

    # default
    return [NORD_LAYER_COLORS[i % len(NORD_LAYER_COLORS)] for i in range(n_layers)]


class MakeNeuralNetwork(inkex.EffectExtension):
    """
    Inkscape effect extension that draws a stylized neural network schematic.

    Layers are arranged as vertical columns of circles spaced horizontally.
    Canvas size is computed automatically from the topology so the diagram is
    always vertically centred with consistent padding. Connections are drawn
    before nodes so node circles naturally occlude line endpoints.

    Params:
        layers: str : comma-separated node counts per layer, e.g. "3,4,4,2"
        connection_type: str : "none", "full" (all-to-all), or "local" (±1 neighbor)
        conn_opacity: float : stroke opacity for connection lines
        conn_width: float : stroke width for connection lines in pixels
        node_radius: float : radius of each node circle in pixels
        h_spacing: float : horizontal distance between layer centers in pixels
        v_spacing: float : vertical distance between node centers in pixels
        color_mode: str : "default" (Nord cycle), "random" (shuffled Nord), or "custom"
        custom_colors: str : comma-separated Nord color names for custom mode
        color_seed: int : RNG seed used by random mode
    """

    def add_arguments(self, pars):
        """
        Register extension parameters from the INX manifest.

        Params:
            pars: argparse.ArgumentParser : Inkscape-provided argument parser
        Returns:
            None
        """
        pars.add_argument("--tab",             type=str,   default="network")
        pars.add_argument("--layers",          type=str,   default="3,4,4,2")
        pars.add_argument("--connection_type", type=str,   default="full")
        pars.add_argument("--conn_opacity",    type=float, default=0.25)
        pars.add_argument("--conn_width",      type=float, default=1.0)
        pars.add_argument("--node_radius",     type=float, default=22.0)
        pars.add_argument("--h_spacing",       type=float, default=130.0)
        pars.add_argument("--v_spacing",       type=float, default=65.0)
        pars.add_argument("--color_mode",      type=str,   default="default")
        pars.add_argument("--custom_colors",   type=str,
                          default="frost_blue,aurora_red,frost_teal,aurora_purple")
        pars.add_argument("--color_seed",      type=int,   default=42)

    def effect(self):
        """
        Generate the neural network SVG and add it to the document.

        Parses the layer topology string, computes centred node positions for each
        layer, then draws connections followed by node circles. For local connectivity,
        each source node maps to a proportionally scaled target index and connects to
        that index ±1, clamped to valid range.

        Params:
            None
        Returns:
            None
        """
        o = self.options

        try:
            layer_sizes = [int(x.strip()) for x in o.layers.split(",") if x.strip()]
        except ValueError:
            inkex.errormsg("Nodes per Layer must be comma-separated integers, e.g. '3,4,3'")
            return

        if not layer_sizes:
            inkex.errormsg("Please specify at least one layer.")
            return

        n_layers  = len(layer_sizes)
        max_nodes = max(layer_sizes)
        r         = o.node_radius
        hs        = o.h_spacing
        vs        = o.v_spacing

        layer_colors = _resolve_layer_colors(
            n_layers, o.color_mode, o.custom_colors, o.color_seed,
        )

        pad = r * 3
        W   = (n_layers - 1) * hs + 2 * pad
        H   = (max_nodes - 1) * vs + 2 * pad

        root = self.svg.add(Group.new(label="neural_network"))

        bg = root.add(Rectangle.new(0, 0, W, H))
        bg.style = inkex.Style({
            "fill":         "#FFFFFF",
            "stroke":       "#000000",
            "stroke-width": "1",
        })

        # Compute centred node positions for each layer
        positions = []
        for li, n in enumerate(layer_sizes):
            x         = pad + li * hs
            col_h     = (n - 1) * vs
            y_start   = (H - col_h) / 2
            positions.append([(x, y_start + ni * vs) for ni in range(n)])

        # Connections (drawn first so they sit behind nodes)
        if o.connection_type != "none":
            conn_group = root.add(Group.new(label="connections"))

            for li in range(n_layers - 1):
                src = positions[li]
                dst = positions[li + 1]
                n_src, n_dst = len(src), len(dst)

                if o.connection_type == "full":
                    pairs = [(si, di) for si in range(n_src) for di in range(n_dst)]
                else:
                    # local: each src node connects to its mapped dst index ± 1
                    pairs = []
                    for si in range(n_src):
                        k = round(si * (n_dst - 1) / max(n_src - 1, 1))
                        for di in range(max(0, k - 1), min(n_dst, k + 2)):
                            pairs.append((si, di))

                conn_color = layer_colors[li]

                for si, di in pairs:
                    x1, y1 = src[si]
                    x2, y2 = dst[di]
                    line = conn_group.add(PathElement())
                    line.set("d", f"M {x1},{y1} L {x2},{y2}")
                    line.style = inkex.Style({
                        "stroke":         conn_color,
                        "stroke-width":   str(o.conn_width),
                        "stroke-opacity": str(o.conn_opacity),
                        "fill":           "none",
                    })

        # Nodes (drawn on top of connections)
        for li, (n, layer_pos) in enumerate(zip(layer_sizes, positions)):
            color       = layer_colors[li]
            layer_group = root.add(Group.new(label=f"layer_{li + 1}"))

            for x, y in layer_pos:
                dot = layer_group.add(Circle.new(center=(x, y), radius=r))
                dot.style = inkex.Style({
                    "fill":         color,
                    "stroke":       NORD_DARK,
                    "stroke-width": str(max(0.5, r * 0.08)),
                })


if __name__ == "__main__":
    MakeNeuralNetwork().run()
