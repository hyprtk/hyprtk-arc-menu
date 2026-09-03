"""Read the active Waybar theme and derive an arc menu palette from it.

The arc menu can mirror the look of the current Waybar theme: the menu button and
items pick up the theme's bar background (glass) and text color, and re-theme
live when the Waybar theme changes.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

log = logging.getLogger("hyprtk_arc_menu.waybar")

THEME_STATE = Path.home() / ".cache" / ".themestyle.sh"
THEMES_DIR = Path.home() / "hyprtk" / "configs" / "waybar" / "themes"
DEFAULT_VARIATION = "hyprtk-aero-top"


def _rgba_string(r, g, b, a) -> str:
    return f"rgba({int(r)},{int(g)},{int(b)},{a:.2f})"


def _color_from(value: str, pywal: dict | None) -> str | None:
    """Convert a CSS color token (@colorN, rgba/rgb/hex) into an rgba() string."""
    value = value.strip()
    m = re.match(r"@color(\d+)", value, re.I)
    if m and pywal:
        hex_color = pywal.get(f"color{m.group(1)}")
        if hex_color and hex_color.startswith("#"):
            h = hex_color.lstrip("#")
            return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},1.0)"
    m = re.search(
        r"rgba\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)", value, re.I
    )
    if m:
        return _rgba_string(float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)))
    m = re.search(r"rgb\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)", value, re.I)
    if m:
        return _rgba_string(float(m.group(1)), float(m.group(2)), float(m.group(3)), 1.0)
    m = re.search(r"#([0-9a-fA-F]{6})", value)
    if m:
        h = m.group(1)
        return _rgba_string(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    return None


def _find_block(css: str, selector: str) -> str | None:
    """Return the text of the first `selector { ... }` block, or None."""
    idx = css.find(selector)
    if idx < 0:
        return None
    brace = css.find("{", idx)
    if brace < 0:
        return None
    depth = 0
    for i in range(brace, len(css)):
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                return css[brace + 1:i]
    return None


def current_theme_dir() -> Path | None:
    """Directory of the currently selected Waybar theme."""
    variation = None
    if THEME_STATE.is_file():
        text = THEME_STATE.read_text().strip()
        parts = text.split(";")
        if len(parts) >= 2 and parts[1].strip("/"):
            variation = parts[1].strip("/")
    if variation is None:
        variation = DEFAULT_VARIATION
    theme_dir = THEMES_DIR / variation
    return theme_dir if theme_dir.is_dir() else None


def read_theme_palette(pywal: dict | None = None) -> dict | None:
    """Build an arc menu palette from the active Waybar theme.

    Returns {fab_color, item_color, fab_icon_color, item_icon_color} or None if
    the theme cannot be read.
    """
    theme_dir = current_theme_dir()
    if theme_dir is None:
        return None
    style = theme_dir / "style.css"
    if not style.is_file():
        return None
    css = style.read_text(errors="ignore")

    block = _find_block(css, "window#waybar") or _find_block(css, "window #waybar")
    if block is None:
        return None

    background = _color_from(
        re.search(r"background\s*:\s*([^;]+)", block).group(1) if re.search(r"background\s*:\s*([^;]+)", block) else "",
        pywal,
    )
    color = _color_from(
        re.search(r"color\s*:\s*([^;]+)", block).group(1) if re.search(r"color\s*:\s*([^;]+)", block) else "",
        pywal,
    )

    if background is None:
        # Fall back to the theme text color as a solid, and default glass.
        background = color or "rgba(20,20,25,0.6)"
    if color is None:
        color = "rgba(230,230,240,0.95)"

    # Semi-transparent glass for the FAB and slightly lighter for the items.
    fab = background
    item = background
    m = re.search(r"rgba\((\d+),(\d+),(\d+),([\d.]+)\)", background)
    if m:
        r, g, b, _a = int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4))
        fab = _rgba_string(r, g, b, min(0.75, max(0.25, _a + 0.05)))
        item = _rgba_string(r, g, b, min(0.6, max(0.15, _a - 0.2)))

    return {
        "fab_color": fab,
        "item_color": item,
        "fab_icon_color": color,
        "item_icon_color": color,
    }