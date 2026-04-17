#!/usr/bin/env python3
"""Inkscape plugin: draw a neural network schematic."""

import inkex
from inkex.elements import Group, Rectangle
from inkex import Circle, PathElement

# One Nord color per layer, cycling
NORD_LAYER_COLORS = [
    "#88C0D0",  # Frost light blue
    "#81A1C1",  # Frost blue
    "#5E81AC",  # Frost dark blue
    "#BF616A",  # Aurora red
    "#D08770",  # Aurora orange
    "#EBCB8B",  # Aurora yellow
    "#A3BE8C",  # Aurora green
    "#B48EAD",  # Aurora purple
    "#8FBCBB",  # Frost teal
]

NORD_DARK  = "#2E3440"  # node stroke
NORD_MID   = "#4C566A"  # connection stroke


class MakeNeuralNetwork(inkex.EffectExtension):

    def add_arguments(self, pars):
        pars.add_argument("--tab",             type=str,   default="network")
        pars.add_argument("--layers",          type=str,   default="3,4,4,2")
        pars.add_argument("--connection_type", type=str,   default="full")
        pars.add_argument("--conn_opacity",    type=float, default=0.25)
        pars.add_argument("--conn_width",      type=float, default=1.0)
        pars.add_argument("--node_radius",     type=float, default=22.0)
        pars.add_argument("--h_spacing",       type=float, default=130.0)
        pars.add_argument("--v_spacing",       type=float, default=65.0)

    def effect(self):
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

                conn_color = NORD_LAYER_COLORS[li % len(NORD_LAYER_COLORS)]

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
            color       = NORD_LAYER_COLORS[li % len(NORD_LAYER_COLORS)]
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
