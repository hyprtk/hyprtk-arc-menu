"""Configuration loading/saving for hyprtk-arc-menu.

Config lives at ~/.config/hyprtk-arc-menu/config.json (JSON).
On first run a default config is written so the user can edit it.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import gi
gi.require_version("GtkLayerShell", "0.1")

from gi.repository import GtkLayerShell

CONFIG_DIR = Path.home() / ".config" / "hyprtk-arc-menu"
CONFIG_PATH = CONFIG_DIR / "config.json"
PYWAL_PATH = Path.home() / ".cache" / "wal" / "colors.json"

log = logging.getLogger("hyprtk_arc_menu.config")

# Menu positions. dx/dy are the arc direction signs, `fan` is the arc spread in
# degrees (90 for corners, 180 for top/bottom center), `edges` the layer-shell
# anchors used to pin the surface.
POSITIONS = {
    "top-left": {
        "dx": 1, "dy": 1, "fan": 90,
        "edges": (GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.TOP),
    },
    "top-center": {
        "dx": 1, "dy": 1, "fan": 180,
        "edges": (GtkLayerShell.Edge.TOP,),
    },
    "top-right": {
        "dx": -1, "dy": 1, "fan": 90,
        "edges": (GtkLayerShell.Edge.RIGHT, GtkLayerShell.Edge.TOP),
    },
    "bottom-left": {
        "dx": 1, "dy": -1, "fan": 90,
        "edges": (GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.BOTTOM),
    },
    "bottom-center": {
        "dx": 1, "dy": -1, "fan": 180,
        "edges": (GtkLayerShell.Edge.BOTTOM,),
    },
    "bottom-right": {
        "dx": -1, "dy": -1, "fan": 90,
        "edges": (GtkLayerShell.Edge.RIGHT, GtkLayerShell.Edge.BOTTOM),
    },
}

DEFAULT_ITEMS = [
    {"icon": "firefox", "command": "firefox", "tooltip": "Firefox"},
    {"icon": "utilities-terminal", "command": "alacritty", "tooltip": "Terminal"},
    {"icon": "system-file-manager", "command": "thunar", "tooltip": "Files"},
    {"icon": "accessories-calculator", "command": "qalculate-gtk", "tooltip": "Calculator"},
    {"icon": "preferences-system", "action": "settings", "tooltip": "Settings"},
]

DEFAULTS = {
    "position": "bottom-right",
    "shape": "circle",              # circle | square (square fans items on a square perimeter)
    "transparent": False,           # transparent button/item backgrounds (icons only)
    "follow_waybar": True,          # mirror the active Waybar theme's glass + text colors
    "margin": 24,
    "radius": 140,
    "fab_size": 56,
    "item_size": 48,
    "animation_time": 300,          # ms
    "fab_icon": "view-grid-symbolic",
    "fab_color": "#c084fc",         # mauve / color5 accent
    "fab_icon_color": "#000000",
    "item_color": "#22d3ee",        # sky / color6 accent
    "item_icon_color": "#000000",
    "use_pywal": True,              # theme FAB/items from pywal color5/color6
    "close_on_unfocus": False,
    "close_on_click": True,
    "items": DEFAULT_ITEMS,
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Return a copy of ``base`` with ``override`` applied recursively."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def validate(cfg: dict) -> dict:
    """Coerce/correct known config fields, falling back to defaults."""
    # Backwards compatibility: the old key was "corner".
    if "corner" in cfg and "position" not in cfg:
        cfg = dict(cfg)
        cfg["position"] = cfg.pop("corner")
    valid = _deep_merge(DEFAULTS, cfg)

    position = valid.get("position", "bottom-right")
    if position not in POSITIONS:
        log.warning("Unknown position %r, using bottom-right", position)
        valid["position"] = "bottom-right"

    if valid.get("shape") not in ("circle", "square"):
        valid["shape"] = "circle"

    valid["transparent"] = bool(valid.get("transparent", False))
    valid["follow_waybar"] = bool(valid.get("follow_waybar", True))

    for key in ("margin", "radius", "fab_size", "item_size", "animation_time"):
        try:
            valid[key] = max(0, int(valid.get(key, DEFAULTS[key])))
        except (TypeError, ValueError):
            valid[key] = DEFAULTS[key]

    if not isinstance(valid.get("items"), list):
        valid["items"] = list(DEFAULT_ITEMS)

    return valid


def load() -> dict:
    """Load config from disk, writing defaults on first run."""
    if not CONFIG_PATH.is_file():
        save(DEFAULTS)
        return dict(DEFAULTS)

    try:
        raw = json.loads(CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not read config (%s); using defaults", exc)
        return dict(DEFAULTS)

    return validate(raw)


def save(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n")


# ── pywal theming ────────────────────────────────────────────────

def load_pywal_colors() -> dict | None:
    """Read ~/.cache/wal/colors.json; returns color map or None if unavailable."""
    try:
        data = json.loads(PYWAL_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    out = dict(data.get("colors") or {})
    special = data.get("special") or {}
    out["background"] = special.get("background")
    out["foreground"] = special.get("foreground")
    return out or None


def contrast_fg(hex_color: str) -> str:
    """Pick black or white text that contrasts with the given hex background."""
    try:
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join(c * 2 for c in hex_color)
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return "#000000"
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "#000000" if luminance > 140 else "#ffffff"


def _css_rgb(css_color: str) -> tuple[int, int, int] | None:
    if not css_color:
        return None
    if css_color.startswith("#"):
        h = css_color.lstrip("#")
        if len(h) >= 6:
            try:
                return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            except ValueError:
                return None
    m = re.search(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", css_color, re.I)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None


def _contrast_ok(fg_css: str, bg_css: str) -> bool:
    """True if fg and bg are sufficiently different in luminance."""
    frgb = _css_rgb(fg_css)
    brgb = _css_rgb(bg_css)
    if frgb is None or brgb is None:
        return False
    lum = lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]  # noqa: E731
    return abs(lum(frgb) - lum(brgb)) > 100


def resolve_palette(cfg: dict, pywal: dict | None = None, waybar: dict | None = None) -> dict:
    """Resolve FAB/item colors.

    - follow_waybar + use_pywal: pywal accents for the buttons, Waybar theme
      decides icon lightness (so pywal colors are never lost on theme switches).
    - follow_waybar only: Waybar theme glass + text.
    - otherwise: pywal color5/color6, or explicit config colors.
    """
    palette = {
        "fab_color": cfg.get("fab_color", "#c084fc"),
        "fab_icon_color": cfg.get("fab_icon_color", "#000000"),
        "item_color": cfg.get("item_color", "#22d3ee"),
        "item_icon_color": cfg.get("item_icon_color", "#000000"),
    }
    pywal_on = cfg.get("use_pywal", True) and bool(pywal)
    wb_on = cfg.get("follow_waybar", True) and bool(waybar)

    if wb_on and pywal_on:
        fab = pywal.get("color5") or palette["fab_color"]
        item = pywal.get("color6") or palette["item_color"]
        palette["fab_color"] = fab
        palette["item_color"] = item
        theme_fg = waybar.get("fab_icon_color") or palette["fab_icon_color"]
        palette["fab_icon_color"] = theme_fg if _contrast_ok(theme_fg, fab) else contrast_fg(fab)
        theme_fg = waybar.get("item_icon_color") or palette["item_icon_color"]
        palette["item_icon_color"] = theme_fg if _contrast_ok(theme_fg, item) else contrast_fg(item)
        return palette
    if wb_on:
        palette.update(waybar)
        return palette
    if pywal_on:
        fab = pywal.get("color5") or palette["fab_color"]
        item = pywal.get("color6") or palette["item_color"]
        palette["fab_color"] = fab
        palette["item_color"] = item
        palette["fab_icon_color"] = contrast_fg(fab)
        palette["item_icon_color"] = contrast_fg(item)
    return palette
