# Changelog

All notable changes to hyprtk-arc-menu are documented in this file.
Dates are in YYYY-MM-DD format.

## [0.1.2] - 2026-09-07

### Changed

- **Follows hyprtk-bar instead of waybar** — `follow_waybar` is now
  `follow_bar`; the menu reads the bar's imported theme
  (`~/.config/hyprtk-bar/config.json` `theme.source: "imported"` +
  `theme.theme_name` + `~/.config/hyprtk-bar/themes/`) instead of the stale
  `~/.cache/.themestyle.sh` + system waybar themes dir. `waybar_theme.py` is
  now `bar_theme.py`. Matches the hyprtk-bar schema rename.

## [0.1.1] - 2026-09-03

### Changed

- Relicensed to **GPL-2.0** (was Apache-2.0); full GPL-2.0 text added to
  `LICENSE` and README references updated.

## [0.1.0] - 2026-09-03

Initial release. Material-style arc menu for Wayland (GTK3 + gtk-layer-shell).

### Added

- Round FAB-style launcher button at a configurable screen position
  (`top-left`, `top-center`, `top-right`, `bottom-left`, `bottom-center`,
  `bottom-right`; centers fan 180°, corners 90°)
- Two shapes: `circle` (arc) and `square` (perimeter)
- Transparent mode (icons only, no button backgrounds)
- Follows the active Waybar theme (`~/.cache/.themestyle.sh`), re-themes live,
  keeping pywal accents (theme controls icon lightness)
- pywal theming — FAB/item colors follow the active wallpaper (color5/color6),
  updated live on `wal` regeneration, with auto-contrast icon colors
- Configurable radius, margins, item/FAB sizes, colors, animation time
- Dynamic ring radius so items never overlap as the item count grows
- Items are icon + arbitrary shell command; right-click pin/unpin
- Open/close via FAB or global hotkey, Escape closes, configurable
  close-on-click; middle-click anywhere quits the app
- Settings dialog (floating centered layer-shell): position, shape, radius,
  margin, sizes, animation, pywal / follow-waybar, transparent, colors, and an
  item list editor (Add/Edit/Remove, Move Up/Down, embedded app search)
- Constant-size surface + input shape (no collapse "pop"); items fade out in
  place on close
- No reserved space — floats over the desktop
- `install.sh` (install / uninstall) to `~/.local/bin/hyprtk-arc-menu`
  (+ `-toggle` wrapper) and `~/.local/share/hyprtk-arc-menu/`
- `hyprtk-arc-menu --print-config`; config at
  `~/.config/hyprtk-arc-menu/config.json` (legacy `corner` key migrates to
  `position`)
- SUPER+CTRL+M hotkey + autostart wired into the Hyprland config (via the
  merged installer)