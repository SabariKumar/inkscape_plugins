#!/usr/bin/env bash
# deploy.sh — build the shared pixi environment and install all Inkscape plugins
# Run from the root of the inkscape_plugins repository.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Prompt for the Inkscape user extensions directory ──────────────────────
echo ""
echo "┌─────────────────────────────────────────────────────────────────┐"
echo "│  Inkscape Plugin Deployer                                       │"
echo "└─────────────────────────────────────────────────────────────────┘"
echo ""
echo "  To find your User Extensions path:"
echo "    1. Open Inkscape"
echo "    2. Go to Edit → Preferences → System"
echo "    3. Look for 'User extensions' and copy the path shown there"
echo ""

while true; do
    read -r -p "Paste your User Extensions path: " INKSCAPE_EXT
    # Strip any surrounding quotes the user may have pasted
    INKSCAPE_EXT="${INKSCAPE_EXT%\"}"
    INKSCAPE_EXT="${INKSCAPE_EXT#\"}"
    INKSCAPE_EXT="${INKSCAPE_EXT%\'}"
    INKSCAPE_EXT="${INKSCAPE_EXT#\'}"
    # Expand ~ manually (read doesn't expand it)
    INKSCAPE_EXT="${INKSCAPE_EXT/#\~/$HOME}"

    if [ -z "$INKSCAPE_EXT" ]; then
        echo "  Path cannot be empty. Please try again."
    else
        break
    fi
done

echo ""
echo "==> Target: $INKSCAPE_EXT"
mkdir -p "$INKSCAPE_EXT"

# ── 1. Build shared pixi environment ───────────────────────────────────────
echo "==> Installing shared pixi environment (rdkit + pymol-open-source)..."
cd "$SCRIPT_DIR/shared_env"
pixi install
echo "    Done."

# ── 2. Copy plugin files ────────────────────────────────────────────────────
echo "==> Copying plugin files..."

for plugin in make_clustered_points make_neural_network make_mol_graph make_mol_3d; do
    src="$SCRIPT_DIR/$plugin"
    if [ -d "$src" ]; then
        # Copy all .py and .inx files (skip README, pixi.toml, etc.)
        while IFS= read -r -d '' f; do
            cp "$f" "$INKSCAPE_EXT/" && echo "    $plugin/$(basename "$f")"
        done < <(find "$src" -maxdepth 1 \( -name "*.py" -o -name "*.inx" \) -print0)
    else
        echo "    WARNING: $plugin/ not found, skipping."
    fi
done

# ── 3. Copy shared pixi environment ────────────────────────────────────────
echo "==> Copying .pixi environment..."
cp -r "$SCRIPT_DIR/shared_env/.pixi" "$INKSCAPE_EXT/"
echo "    Done."

echo ""
echo "✓ All plugins deployed to:"
echo "  $INKSCAPE_EXT"
echo ""
echo "Restart Inkscape, then look under Extensions → Generate."
