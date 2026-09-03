"""The arc menu widget: a FAB in the corner with sub-items spread along a 90° arc.

Ported conceptually from the Android MaterialArcMenu custom view
(https://github.com/saurabharora90/MaterialArcMenu), rendered as a GTK3 widget
inside a layer-shell surface.
"""
from __future__ import annotations

import math
import time
from typing import Optional

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gdk, GLib, Gtk

from .config import POSITIONS, resolve_palette


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def _rgba_from_hex(hex_color: str) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    rgba.parse(hex_color if hex_color else "#000000")
    return rgba


def load_icon_image(icon_name: str, pixel: int, fg_hex: str) -> Gtk.Image:
    """Load an icon theme image at an exact pixel size.

    Colored icons are loaded as-is; symbolic icons are tinted with ``fg_hex`` so
    they stay readable against any (pywal) background.
    """
    theme = Gtk.IconTheme.get_default()
    info = theme.lookup_icon(icon_name, pixel, 0)
    if info is None:
        info = theme.lookup_icon("application-x-executable", pixel, 0)
    try:
        if info is not None and info.is_symbolic():
            fg = _rgba_from_hex(fg_hex)
            pixbuf = info.load_symbolic(fg, fg, fg, fg)[0]
        elif info is not None:
            pixbuf = info.load_icon()
        else:
            pixbuf = None
    except GLib.Error:
        pixbuf = None
    if pixbuf is None:
        return Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON)
    return Gtk.Image.new_from_pixbuf(pixbuf)


def make_round_button(size: int, icon_name: str, css_class: str, fg_color: str = "#000000") -> Gtk.Button:
    btn = Gtk.Button()
    btn.set_size_request(size, size)
    btn.get_style_context().add_class(css_class)
    btn.set_image(load_icon_image(icon_name, max(8, int(size * 0.5)), fg_color))
    btn.set_can_focus(False)
    return btn


class ArcMenu(Gtk.Fixed):
    """FAB + arc items laid out on a Gtk.Fixed, with open/close animation."""

    def __init__(self, cfg: dict, on_close=None, on_run=None, on_toggle=None, palette: dict | None = None):
        super().__init__()
        self.cfg = cfg
        self.on_close = on_close          # callback when menu fully closed
        self.on_run = on_run              # callback(item) when an item is launched
        self.on_toggle = on_toggle        # callback when the FAB is clicked

        self._palette = palette or resolve_palette(cfg, None)
        self._css_provider: Optional[Gtk.CssProvider] = None

        self._open = False
        self._opening = False
        self._anim_start = 0.0
        self._anim_timer: Optional[int] = None
        self._items: list[dict] = []      # {btn, entry}

        self._fab = self._build_fab()
        self.put(self._fab, 0, 0)

        for entry in cfg.get("items", []):
            self._add_item(entry)

        # Middle-click is handled at the toplevel window (see app.py).

        self._apply_css()

    # ── geometry helpers ──────────────────────────────────────────

    def _is_square(self) -> bool:
        return self.cfg.get("shape") == "square"

    def _position_dir(self) -> tuple[int, int, int]:
        p = POSITIONS.get(self.cfg["position"], POSITIONS["bottom-right"])
        return p["dx"], p["dy"], p["fan"]

    @property
    def fab_size(self) -> int:
        return int(self.cfg["fab_size"])

    @property
    def item_size(self) -> int:
        return int(self.cfg["item_size"])

    @property
    def margin(self) -> int:
        return int(self.cfg["margin"])

    @property
    def radius(self) -> int:
        return int(self.cfg["radius"])

    def effective_radius(self) -> int:
        """Ring radius that keeps items from overlapping on the arc fan.

        Items are spread over the position's fan (90° corners, 180° centers); as
        their count grows they crowd together. Grow the radius so adjacent item
        edges always keep a small gap.
        """
        n = len(self._items)
        if n <= 1:
            return self.radius
        if self._is_square():
            return max(self.radius, int(math.ceil(self._square_radius())))
        _, _, fan = self._position_dir()
        delta = math.radians(fan / (n - 1))
        min_radius = (self.item_size + 4) / (2 * math.sin(delta / 2))
        return max(self.radius, int(math.ceil(min_radius)))

    def _square_radius(self) -> float:
        """Minimum radius for the square-perimeter layout (unit-square spacing)."""
        n = len(self._items)
        _, _, fan = self._position_dir()
        pts = []
        for i in range(n):
            ang = math.radians(fan * i / (n - 1)) if n > 1 else math.radians(fan / 2)
            u, v = math.cos(ang), math.sin(ang)
            m = max(abs(u), abs(v)) or 1.0
            pts.append((u / m, v / m))
        min_dist = min(
            math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
            for i in range(n - 1)
        )
        return (self.item_size + 4) / min_dist

    @property
    def animation_time(self) -> int:
        return int(self.cfg["animation_time"])

    def open_size(self) -> tuple[int, int]:
        m = self.margin
        f = self.fab_size
        r = self.effective_radius()
        i = self.item_size
        if "center" in self.cfg["position"]:
            # FAB is horizontally centered: items span R + half an item on each side.
            return 2 * r + i, m + f // 2 + r + i // 2
        return m + f // 2 + r + i // 2, m + f // 2 + r + i // 2

    # ── construction ──────────────────────────────────────────────

    def _build_fab(self) -> Gtk.Button:
        fab = make_round_button(
            self.fab_size,
            self.cfg.get("fab_icon", "view-grid-symbolic"),
            "arc-fab",
            self._palette["fab_icon_color"],
        )
        fab.set_tooltip_text("Menu")
        fab.connect("clicked", lambda _b: self._on_fab_clicked())
        return fab

    def _on_fab_clicked(self) -> None:
        # The window owns open/close (it knows the surface sizes), so hand off.
        if self.on_toggle:
            self.on_toggle()

    def _add_item(self, entry: dict) -> None:
        icon = entry.get("icon", "application-x-executable")
        btn = make_round_button(
            self.item_size, icon, "arc-item", self._palette["item_icon_color"]
        )
        tooltip = entry.get("tooltip") or entry.get("command") or ""
        if tooltip:
            btn.set_tooltip_text(tooltip)
        command = entry.get("command", "")
        btn.connect("clicked", self._on_item_clicked, entry)
        btn.set_opacity(0.0)
        btn.set_no_show_all(True)
        self.put(btn, 0, 0)
        self._items.append({"btn": btn, "entry": entry})

    # ── styling ───────────────────────────────────────────────────

    def apply_palette(self, palette: dict) -> None:
        """Re-theme the FAB/items live (e.g. after a pywal update)."""
        self._palette = palette
        self._apply_css()
        self.refresh_icons()

    def refresh_icons(self) -> None:
        """Reload icons so symbolic ones pick up the current fg color."""
        fab_icon = self.cfg.get("fab_icon", "view-grid-symbolic")
        self._fab.set_image(
            load_icon_image(
                fab_icon, max(8, int(self.fab_size * 0.5)), self._palette["fab_icon_color"]
            )
        )
        for item in self._items:
            icon = item["entry"].get("icon", "application-x-executable")
            item["btn"].set_image(
                load_icon_image(
                    icon, max(8, int(self.item_size * 0.5)), self._palette["item_icon_color"]
                )
            )

    def _apply_css(self) -> None:
        p = self._palette
        radius = "50%" if not self._is_square() else "24%"
        if self.cfg.get("transparent"):
            fab_bg = "transparent"
            item_bg = "transparent"
            hover = "rgba(255,255,255,0.12)"
            fab_shadow = "none"
            item_shadow = "none"
        else:
            fab_bg = p["fab_color"]
            item_bg = p["item_color"]
            hover = None
            fab_shadow = "0 2px 8px rgba(0,0,0,0.35)"
            item_shadow = "0 2px 6px rgba(0,0,0,0.3)"
        css = f"""
        .arc-fab {{
            background-image: none;
            background-color: {fab_bg};
            color: {p["fab_icon_color"]};
            border-radius: {radius};
            border: none;
            box-shadow: {fab_shadow};
        }}
        .arc-fab:hover {{
            background-color: {hover or "shade(" + p["fab_color"] + ", 1.1)"};
        }}
        .arc-item {{
            background-image: none;
            background-color: {item_bg};
            color: {p["item_icon_color"]};
            border-radius: {radius};
            border: none;
            box-shadow: {item_shadow};
        }}
        .arc-item:hover {{
            background-color: {hover or "shade(" + p["item_color"] + ", 1.1)"};
        }}
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        screen = Gdk.Screen.get_default()
        if self._css_provider is not None:
            Gtk.StyleContext.remove_provider_for_screen(screen, self._css_provider)
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self._css_provider = provider

    # ── layout ────────────────────────────────────────────────────

    def fab_center(self, win_w: int, win_h: int) -> tuple[int, int]:
        """Center of the FAB in window coords for a given window size."""
        position = self.cfg["position"]
        m = self.margin
        f = self.fab_size
        if "center" in position:
            cx = win_w // 2
        elif "right" in position:
            cx = win_w - m - f // 2
        else:
            cx = m + f // 2
        if "bottom" in position:
            cy = win_h - m - f // 2
        else:
            cy = m + f // 2
        return cx, cy

    def layout_fab(self, win_w: int, win_h: int) -> None:
        cx, cy = self.fab_center(win_w, win_h)
        self.move(self._fab, int(cx - self.fab_size / 2), int(cy - self.fab_size / 2))

    def layout_items(self, win_w: int, win_h: int, radius: float, opacity: float) -> None:
        cx, cy = self.fab_center(win_w, win_h)
        dx, dy, fan = self._position_dir()
        square = self._is_square()
        n = len(self._items)
        half = self.item_size / 2
        for idx, item in enumerate(self._items):
            if n == 1:
                angle = math.radians(fan / 2)
            else:
                angle = math.radians(fan * idx / (n - 1))
            u = math.cos(angle)
            v = math.sin(angle)
            if square:
                # Map the arc angle onto the perimeter of a square so items
                # encircle the square menu button in a square layout.
                m = max(abs(u), abs(v)) or 1.0
                u /= m
                v /= m
            ox = dx * radius * u
            oy = dy * radius * v
            x = cx + ox - half
            y = cy + oy - half
            self.move(item["btn"], int(x), int(y))
            item["btn"].set_opacity(opacity)

    def set_items_visible(self, visible: bool) -> None:
        for item in self._items:
            item["btn"].set_visible(visible)
            if not visible:
                item["btn"].set_opacity(0.0)

    # ── state / animation ─────────────────────────────────────────

    def is_open(self) -> bool:
        return self._open

    def cancel_animation(self) -> None:
        if self._anim_timer is not None:
            GLib.source_remove(self._anim_timer)
            self._anim_timer = None

    def open(self, win_w: int, win_h: int) -> None:
        if self._open:
            return
        self._open = True
        self._opening = True
        self.set_items_visible(True)
        self.layout_fab(win_w, win_h)
        self._anim_start = time.monotonic()
        self._schedule_tick(win_w, win_h)

    def close(self, win_w: int, win_h: int) -> None:
        if not self._open:
            return
        self._open = False
        self._opening = False
        self._anim_start = time.monotonic()
        self._schedule_tick(win_w, win_h)

    def _schedule_tick(self, win_w: int, win_h: int) -> None:
        if self._anim_timer is not None:
            GLib.source_remove(self._anim_timer)
        self._anim_timer = GLib.timeout_add(16, self._tick, win_w, win_h)

    def _tick(self, win_w: int, win_h: int) -> bool:
        elapsed_ms = (time.monotonic() - self._anim_start) * 1000
        duration = max(1, self.animation_time)
        t = min(1.0, elapsed_ms / duration)
        eased = ease_out_cubic(t)

        if self._opening:
            # Items emerge from the FAB and spread outward while fading in.
            radius = eased * self.effective_radius()
            opacity = eased
        else:
            # Items stay in place and simply fade out, so they never bunch up
            # onto the FAB at the end of the collapse.
            radius = self.effective_radius()
            opacity = 1 - eased

        self.layout_items(win_w, win_h, radius, opacity)

        if t >= 1.0:
            self._anim_timer = None
            if self._opening:
                self.set_items_visible(True)
                for item in self._items:
                    item["btn"].set_opacity(1.0)
            else:
                self.set_items_visible(False)
                if self.on_close:
                    self.on_close()
            return False
        return True

    # ── actions ───────────────────────────────────────────────────

    def _on_item_clicked(self, _btn, entry: dict) -> None:
        if self.on_run:
            self.on_run(entry)
