# Changelog

All notable changes to hyprtk-arc-menu are documented in this file.
Dates are in YYYY-MM-DD format.

## [0.1.0] - 2026-09-03

Initial release. Material-style arc menu for Wayland (GTK3 + gtk-layer-shell).

### Added

- Round FAB-style launcher button at a configurable screen position
  (`top-left`, `top-center`, `top-right`, `bottom-left`, `bottom-center`,
  `bottom-right`; centers fan 180°, corners 90°)
- Two shapes: `circle` (arc) and `square` (perimeter)
- Transparent mode (icons only, no button backgrounds)
- Follows the active Waybar theme (`~/.cache/.themestyle.sh`), re-themes live
- pywal theming — FAB/item colors follow the active wallpaper (color5/color6),
  updated live on `wal` regeneration, with auto-contrast icon colors
- Configurable radius, margins, item/FAB sizes, colors, animation time
- Items are icon + arbitrary shell command
- Open/close via FAB or global hotkey (SIGUSR1 toggle), Escape closes,
  configurable close-on-click
- No reserved space — floats over the desktop
- `install.sh` (install / uninstall) to `~/.local/bin/hyprtk-arc-menu`
- `hyprtk-arc-menu --print-config`