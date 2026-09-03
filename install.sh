#!/bin/bash
# hyprtk-arc-menu installer for Hyprtk
# Creates a venv, installs the app, and drops a launcher on PATH.
# Usage: ./install.sh            — install
#        ./install.sh --uninstall — remove everything

set -euo pipefail

APP_NAME="hyprtk-arc-menu"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ "${1:-}" == "--uninstall" || "${1:-}" == "-u" ]]; then
    echo ":: Uninstalling $APP_NAME..."
    rm -rf "$INSTALL_DIR"
    rm -f "$BIN_DIR/$APP_NAME"
    rm -f "$BIN_DIR/$APP_NAME-toggle"
    rm -f "$APPS_DIR/$APP_NAME.desktop"
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
    echo ":: Done. $APP_NAME has been uninstalled."
    exit 0
fi

echo ":: Installing $APP_NAME..."

mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$APPS_DIR"

cp -r "$SCRIPT_DIR/src" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/pyproject.toml" "$INSTALL_DIR/"

python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install -e "$INSTALL_DIR" --quiet 2>/dev/null || \
"$INSTALL_DIR/venv/bin/pip" install -e "$INSTALL_DIR" --quiet

# Main launcher
cat > "$BIN_DIR/$APP_NAME" << LAUNCHER
#!/bin/bash
exec "$INSTALL_DIR/venv/bin/python3" -m hyprtk_arc_menu "\$@"
LAUNCHER
chmod +x "$BIN_DIR/$APP_NAME"

# Toggle helper (for a Hyprland hotkey). Uses a full path so it works even
# when Hyprland's exec environment PATH does not include ~/.local/bin.
cat > "$BIN_DIR/$APP_NAME-toggle" << TOGGLE
#!/bin/bash
exec "$HOME/.local/bin/$APP_NAME" --toggle "\$@"
TOGGLE
chmod +x "$BIN_DIR/$APP_NAME-toggle"

cp "$SCRIPT_DIR/$APP_NAME.desktop" "$APPS_DIR/"
update-desktop-database "$APPS_DIR" 2>/dev/null || true

echo ":: Installed to $BIN_DIR/$APP_NAME"
echo ":: Toggle helper at $BIN_DIR/$APP_NAME-toggle"
echo ":: Config: ~/.config/hyprtk-arc-menu/config.json"
echo ":: Run './install.sh --uninstall' to remove"

cat << 'HINT'

  Hyprland hotkey — add to ~/.config/hypr/keybindings.lua:
      hl.bind(mainMod .. " + CTRL + M", hl.dsp.exec_cmd("\$HOME/.local/bin/hyprtk-arc-menu-toggle"))
HINT
