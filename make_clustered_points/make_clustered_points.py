#!/usr/bin/env python3
"""Inkscape plugin: generate a rectangle filled with Gaussian-clustered points."""

import random
import math
import inkex
from inkex.elements import Group, Rectangle, ClipPath
from inkex import Circle

# Nord Aurora + Frost — cycled per cluster
NORD_CLUSTER_COLORS = [
    "#BF616A",  # Aurora red
    "#D08770",  # Aurora orange
    "#EBCB8B",  # Aurora yellow
    "#A3BE8C",  # Aurora green
    "#B48EAD",  # Aurora purple
    "#88C0D0",  # Frost light blue
    "#81A1C1",  # Frost blue
    "#5E81AC",  # Frost dark blue
    "#8FBCBB",  # Frost teal
]

RECT_BG    = "#FFFFFF"
RECT_FRAME = "#000000"


class MakeClusteredPoints(inkex.EffectExtension):
    """
    Inkscape effect extension that fills a rectangle with Gaussian-clustered point clouds.

    Cluster centers are placed via rejection sampling to prevent visual overlap.
    Each cluster's spread is independently drawn from a log-normal distribution
    centred on the user-supplied spread percentage, producing natural size variation
    across clusters. A SVG clipPath constrains all generated points to the rectangle
    boundary so no dots bleed outside the frame.

    Params:
        rect_width: float : rectangle width in pixels
        rect_height: float : rectangle height in pixels
        num_clusters: int : number of Gaussian clusters to generate
        points_per_cluster: int : number of dots drawn per cluster
        spread_pct: float : base spread as a percentage of min(width, height);
                            per-cluster sigma is sampled from lognormal(log(spread), 0.4)
        point_radius_pct: float : dot radius as a percentage of min(width, height)
        seed: int : random seed for reproducible layouts
    """

    def add_arguments(self, pars):
        """
        Register extension parameters from the INX manifest.

        Params:
            pars: argparse.ArgumentParser : Inkscape-provided argument parser
        Returns:
            None
        """
        pars.add_argument("--tab",                type=str,   default="clusters")
        pars.add_argument("--rect_width",         type=float, default=500.0)
        pars.add_argument("--rect_height",        type=float, default=400.0)
        pars.add_argument("--point_radius_pct",   type=float, default=0.6)
        pars.add_argument("--num_clusters",       type=int,   default=5)
        pars.add_argument("--points_per_cluster", type=int,   default=60)
        pars.add_argument("--spread_pct",         type=float, default=10.0)
        pars.add_argument("--seed",               type=int,   default=42)

    def effect(self):
        """
        Generate the clustered-points SVG and add it to the document.

        Places cluster centers with rejection sampling (min separation = 3 × spread),
        samples per-cluster sigmas from a log-normal distribution, scatters dots
        with Gaussian noise, and clips the entire points group to the bounding rectangle.
        Falls back to placing a center without the separation constraint if 500 attempts
        are exhausted, so the requested cluster count is always honoured.

        Params:
            None
        Returns:
            None
        """
        o   = self.options
        rng = random.Random(o.seed)

        W, H = o.rect_width, o.rect_height
        base = min(W, H)  # reference dimension — everything scales off this

        spread = base * o.spread_pct / 100.0
        radius = base * o.point_radius_pct / 100.0

        n_c   = o.num_clusters
        n_pts = o.points_per_cluster

        root = self.svg.add(Group.new(label="clustered_points"))

        # Background
        bg = root.add(Rectangle.new(0, 0, W, H))
        bg.style = inkex.Style({
            "fill":         RECT_BG,
            "stroke":       RECT_FRAME,
            "stroke-width": str(max(0.5, base * 0.002)),
        })

        # clipPath so points never bleed outside the rectangle
        clip = self.svg.defs.add(ClipPath())
        clip.add(Rectangle.new(0, 0, W, H))
        clip_url = f"url(#{clip.get_id()})"

        # Place cluster centers using rejection sampling to avoid overlap.
        # Minimum separation = 3 * spread keeps clusters visually distinct.
        min_dist  = spread * 3.0
        margin    = spread * 0.5
        centers   = []
        max_tries = 500

        for i in range(n_c):
            for _ in range(max_tries):
                cx = rng.uniform(margin, W - margin)
                cy = rng.uniform(margin, H - margin)
                if all(math.hypot(cx - ex, cy - ey) >= min_dist for ex, ey in centers):
                    centers.append((cx, cy))
                    break
            else:
                # Couldn't place without overlap — relax and place anyway
                centers.append((cx, cy))

        # Draw clusters
        points_group = root.add(Group.new(label="points"))
        points_group.set("clip-path", clip_url)

        for i, (cx, cy) in enumerate(centers):
            color = NORD_CLUSTER_COLORS[i % len(NORD_CLUSTER_COLORS)]
            sigma = rng.lognormvariate(math.log(spread), 0.4)
            cluster_group = points_group.add(Group.new(label=f"cluster_{i+1}"))

            for _ in range(n_pts):
                x = rng.gauss(cx, sigma)
                y = rng.gauss(cy, sigma)

                dot = cluster_group.add(Circle.new(center=(x, y), radius=radius))
                dot.style = inkex.Style({
                    "fill":         color,
                    "fill-opacity": "0.85",
                    "stroke":       "none",
                })


if __name__ == "__main__":
    MakeClusteredPoints().run()
