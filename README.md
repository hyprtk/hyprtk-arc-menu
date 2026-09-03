# hyprtk-arc-menu

A Material-style arc menu for Arch Linux on Wayland (Hyprland), ported from the
Android [MaterialArcMenu](https://github.com/saurabharora90/MaterialArcMenu)
custom view.

A round FAB-style button sits in a configurable screen position (any corner, or
centered top/bottom). Clicking it (or pressing a global hotkey) fans its
sub-items out along an arc. Clicking an item launches its command and closes the
menu.

Built with **GTK3 + Python** and rendered as a **gtk-layer-shell** overlay, so it
floats above windows without reserving screen space.

## Features

- Configurable position: `top-left`, `top-center`, `top-right`,
  `bottom-left`, `bottom-center`, `bottom-right` (centers fan 180°, corners 90°)
- Two shapes: `circle` (items on an arc) or `square` (square button, items
  encircle it along a square perimeter)
- **Transparent mode** — no colored button backgrounds, icons only
- **Follow Waybar theme** (default) — mirrors the active Waybar theme's bar glass
  and text color, and re-themes live when the Waybar theme changes
- Configurable radius, margins, item/FAB sizes, colors, animation time
- Items are icon + command (any shell command)
- Open/close via the FAB or a global hotkey (SIGUSR1 toggle)
- Close on Escape, close on item click (configurable)
- No reserved space — floats over the desktop
- **pywal theming** — FAB and item colors follow the active wallpaper (color5 /
  color6), updated live when `wal` regenerates `~/.cache/wal/colors.json`
- Icon colors auto-contrast (black/white) against the pywal background

## Requirements

Arch packages:

```sh
sudo pacman -S gtk3 gtk-layer-shell python-gobject
```

## Install

```sh
./install.sh
```

Installs to `~/.local/bin/hyprtk-arc-menu` (and a `-toggle` helper). Remove with
`./install.sh --uninstall`.

## Config

Config is written to `~/.config/hyprtk-arc-menu/config.json` on first run.

```jsonc
{
  "position": "bottom-right", // top-left | top-center | top-right | bottom-left | bottom-center | bottom-right
  "shape": "circle",         // circle | square
  "transparent": false,      // transparent button/item backgrounds (icons only)
  "follow_waybar": true,     // mirror the active Waybar theme (glass + text color)
  "margin": 24,               // px from screen edge to the FAB
  "radius": 140,              // px arc radius
  "fab_size": 56,             // px FAB diameter
  "item_size": 48,            // px item diameter
  "animation_time": 300,      // ms
  "fab_icon": "view-grid-symbolic",
  "fab_color": "#c084fc",
  "fab_icon_color": "#000000",
  "item_color": "#22d3ee",
  "item_icon_color": "#000000",
  "use_pywal": true,          // theme FAB/items from pywal color5/color6
  "close_on_unfocus": false,
  "close_on_click": true,
  "items": [
    { "icon": "firefox", "command": "firefox", "tooltip": "Firefox" },
    { "icon": "utilities-terminal", "command": "alacritty", "tooltip": "Terminal" }
  ]
}
```

Icons are looked up from your installed icon theme (e.g. Papirus). Colors default
to the hyprtk mauve/sky accents but are fully configurable. When `use_pywal` is
enabled (default), the FAB uses pywal `color5` and the items pywal `color6` —
matching the hyprtk waybar `@mauve`/`@sky` mapping — and the menu re-themes
itself automatically whenever `wal` regenerates the color cache (i.e. on any
wallpaper change). Set explicit `*_color` values and `use_pywal: false` to pin
the colors.

## Usage

```sh
hyprtk-arc-menu               # run
hyprtk-arc-menu --toggle      # toggle a running instance (or start one)
hyprtk-arc-menu --print-config
```

### Hotkey

The app toggles on `SIGUSR1`. Wire a global keybind in Hyprland:

```
bind = SUPER, CTRL, M, exec, hyprtk-arc-menu-toggle
```

In the Lua config (`~/.config/hypr/keybindings.lua`):

```lua
hl.bind(mainMod .. " + CTRL + M", hl.dsp.exec_cmd("$HOME/.local/bin/hyprtk-arc-menu-toggle"))
```

## Run as a service (optional)

Launch at Hyprland start (`~/.config/hypr/autostart.lua`):

```lua
hl.exec_cmd("hyprtk-arc-menu")
```

## License

GPL-2.0. Ported concept from MaterialArcMenu (Apache-2.0).
