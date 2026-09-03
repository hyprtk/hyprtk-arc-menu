"""Layer-shell window hosting the arc menu, plus hotkey handling."""
from __future__ import annotations

import logging

import cairo

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")

from gi.repository import Gdk, Gio, GLib, Gtk, GtkLayerShell

from .arc_menu import ArcMenu
from .config import POSITIONS, PYWAL_PATH, load, load_pywal_colors, resolve_palette
from .settings import SettingsDialog
from .waybar_theme import THEME_STATE, read_theme_palette

log = logging.getLogger("hyprtk_arc_menu.app")


class ArcWindow(Gtk.Window):
    """A borderless, transparent layer-shell surface pinned to a screen corner."""

    def __init__(self, cfg: dict):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self._cfg = cfg
        self._wal_monitor: Gio.FileMonitor | None = None
        self._wal_debounce: int | None = None
        self._waybar_monitor: Gio.FileMonitor | None = None
        self._theme_debounce: int | None = None

        self.set_title("hyprtk-arc-menu")
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_app_paintable(True)
        self.set_accept_focus(False)

        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)

        self._menu = ArcMenu(
            cfg,
            on_close=self._on_menu_closed,
            on_run=self._on_run,
            on_toggle=self.toggle,
            palette=self._build_palette(),
        )
        self.add(self._menu)

        self._init_layer_shell()
        # Constant surface size (the arc size); the window never resizes.
        w, h = self._menu.open_size()
        self._set_surface_size(w, h)
        self._menu.layout_fab(w, h)
        self._apply_closed()

        self.connect("key-press-event", self._on_key_press)
        self.connect("focus-out-event", self._on_focus_out)
        # Middle-click anywhere on the menu surface closes it. Handled at the
        # toplevel window so it works over empty areas and buttons alike.
        self.connect("button-press-event", self._on_pointer_press)

        if cfg.get("follow_waybar", True):
            self._setup_waybar_monitor()
        if cfg.get("use_pywal", True):
            self._setup_wal_monitor()

    # ── theming (pywal + waybar theme) ───────────────────────────

    def _build_palette(self) -> dict:
        """Current palette: Waybar theme glass/text, else pywal, else config."""
        pywal = load_pywal_colors()
        if self._cfg.get("follow_waybar", True):
            waybar = read_theme_palette(pywal)
            if waybar:
                return resolve_palette(self._cfg, pywal, waybar)
        return resolve_palette(self._cfg, pywal, None)

    def _apply_current_palette(self) -> None:
        self._menu.apply_palette(self._build_palette())

    def _setup_wal_monitor(self) -> None:
        """Watch ~/.cache/wal/ so a wallpaper change re-themes the menu live."""
        try:
            self._wal_monitor = Gio.File.new_for_path(
                str(PYWAL_PATH.parent)
            ).monitor_directory(Gio.FileMonitorFlags.NONE, None)
        except GLib.Error as exc:
            log.warning("Could not monitor pywal cache: %s", exc)
            return
        self._wal_monitor.connect("changed", self._on_wal_changed)

    def _on_wal_changed(self, _monitor, file, *_args) -> None:
        if file.get_basename() != PYWAL_PATH.name:
            return
        if self._wal_debounce is not None:
            GLib.source_remove(self._wal_debounce)
        self._wal_debounce = GLib.timeout_add(400, self._reload_wal)

    def _reload_wal(self) -> bool:
        self._wal_debounce = None
        self._apply_current_palette()
        return GLib.SOURCE_REMOVE

    def _setup_waybar_monitor(self) -> None:
        """Watch the Waybar theme state file so theme switches re-theme live."""
        try:
            self._waybar_monitor = Gio.File.new_for_path(
                str(THEME_STATE.parent)
            ).monitor_directory(Gio.FileMonitorFlags.NONE, None)
        except GLib.Error as exc:
            log.warning("Could not monitor waybar theme state: %s", exc)
            return
        self._waybar_monitor.connect("changed", self._on_waybar_changed)

    def _on_waybar_changed(self, _monitor, file, *_args) -> None:
        if file.get_basename() != THEME_STATE.name:
            return
        if self._theme_debounce is not None:
            GLib.source_remove(self._theme_debounce)
        self._theme_debounce = GLib.timeout_add(400, self._reload_theme)

    def _reload_theme(self) -> bool:
        self._theme_debounce = None
        self._apply_current_palette()
        return GLib.SOURCE_REMOVE

    # ── layer shell ───────────────────────────────────────────────

    def _init_layer_shell(self) -> None:
        position = POSITIONS[self._cfg["position"]]
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_namespace(self, "hyprtk-arc-menu")
        for edge in position["edges"]:
            GtkLayerShell.set_anchor(self, edge, True)
        # Do not reserve space; float above windows.
        GtkLayerShell.set_exclusive_zone(self, -1)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.NONE)

    def _set_keyboard_mode(self, on: bool) -> None:
        mode = (
            GtkLayerShell.KeyboardMode.ON_DEMAND
            if on
            else GtkLayerShell.KeyboardMode.NONE
        )
        GtkLayerShell.set_keyboard_mode(self, mode)
        self.set_accept_focus(on)
        if on:
            self.grab_focus()

    # ── sizing ────────────────────────────────────────────────────
    # The surface keeps a constant size (the open/arc size) at all times so
    # collapsing never resizes it (which caused a visual "pop"). When closed,
    # an input shape limits clicks to the FAB and the rest passes through.

    def _fab_rect(self) -> Gdk.Rectangle:
        m = self._menu.margin
        f = self._menu.fab_size
        w, h = self._menu.open_size()
        position = self._cfg["position"]
        if "center" in position:
            x = w // 2 - f // 2
        elif "left" in position:
            x = m
        else:
            x = w - m - f
        y = m if "top" in position else h - m - f
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = x, y, f, f
        return rect

    def _set_input_region(self, rect: Gdk.Rectangle | None) -> None:
        wnd = self.get_window()
        if wnd is None:
            return
        if rect is None:
            # Reset: the whole surface is interactive.
            w, h = self._menu.open_size()
            rect = Gdk.Rectangle()
            rect.x, rect.y, rect.width, rect.height = 0, 0, w, h
        region = cairo.Region(cairo.RectangleInt(rect.x, rect.y, rect.width, rect.height))
        wnd.input_shape_combine_region(region, 0, 0)

    def _set_surface_size(self, w: int, h: int) -> None:
        # Layer-shell surfaces size more reliably via set_size_request than
        # gtk_window_resize (which can be overridden by content size request).
        self._menu.set_size_request(w, h)
        self.set_size_request(w, h)

    def _apply_closed(self) -> None:
        self._menu.set_items_visible(False)
        self._set_input_region(self._fab_rect())

    def _apply_open(self) -> None:
        self._set_input_region(None)

    # ── state control ─────────────────────────────────────────────

    def toggle(self) -> None:
        if self._menu.is_open():
            self.close_menu()
        else:
            self.open_menu()

    def open_menu(self) -> None:
        w, h = self._menu.open_size()
        self._menu.layout_fab(w, h)
        self._apply_open()
        self._set_keyboard_mode(True)
        self._menu.open(w, h)

    def close_menu(self) -> None:
        if not self._menu.is_open():
            return
        w, h = self._menu.open_size()
        self._menu.close(w, h)

    def _on_menu_closed(self) -> None:
        self._apply_closed()
        self._set_keyboard_mode(False)

    def _on_run(self, entry: dict) -> None:
        if entry.get("action") == "settings":
            self.close_menu()
            self.open_settings()
            return
        command = entry.get("command")
        if command:
            try:
                GLib.spawn_command_line_async(command)
            except GLib.Error as exc:
                log.warning("Failed to launch %r: %s", command, exc)
        if self._cfg.get("close_on_click", True):
            self.close_menu()

    # ── settings / reload ─────────────────────────────────────────

    def open_settings(self) -> None:
        """Open the arc menu settings dialog; apply changes on save."""
        SettingsDialog(load(), on_saved=self.reload)

    def reload(self) -> None:
        """Reload config from disk and rebuild the menu in place."""
        self._cfg = load()

        for deb in ("_wal_debounce", "_theme_debounce"):
            if getattr(self, deb, None) is not None:
                GLib.source_remove(getattr(self, deb))
                setattr(self, deb, None)
        for mon in ("_wal_monitor", "_waybar_monitor"):
            if getattr(self, mon, None) is not None:
                getattr(self, mon).cancel()
                setattr(self, mon, None)

        # Reset all layer-shell anchors, then re-apply the (possibly new) position.
        for edge in (
            GtkLayerShell.Edge.LEFT,
            GtkLayerShell.Edge.RIGHT,
            GtkLayerShell.Edge.TOP,
            GtkLayerShell.Edge.BOTTOM,
        ):
            GtkLayerShell.set_anchor(self, edge, False)

        self.remove(self._menu)
        self._menu.cancel_animation()
        self._menu.destroy()
        self._menu = ArcMenu(
            self._cfg,
            on_close=self._on_menu_closed,
            on_run=self._on_run,
            on_toggle=self.toggle,
            palette=self._build_palette(),
        )
        self.add(self._menu)

        position = POSITIONS[self._cfg["position"]]
        for edge in position["edges"]:
            GtkLayerShell.set_anchor(self, edge, True)

        if self._cfg.get("follow_waybar", True):
            self._setup_waybar_monitor()
        if self._cfg.get("use_pywal", True):
            self._setup_wal_monitor()

        # Re-apply the (possibly changed) constant surface size and closed state.
        w, h = self._menu.open_size()
        self._set_surface_size(w, h)
        self._menu.layout_fab(w, h)
        self._apply_closed()
        self._set_keyboard_mode(False)
        self.show_all()

    # ── events ────────────────────────────────────────────────────

    def _on_key_press(self, _widget, event) -> bool:
        if event.keyval == Gdk.KEY_Escape and self._menu.is_open():
            self.close_menu()
            return True
        return False

    def _on_pointer_press(self, _widget, event) -> bool:
        # Middle-click anywhere on the menu surface quits the app entirely.
        if event.button == Gdk.BUTTON_MIDDLE:
            Gtk.main_quit()
            return True
        return False

    def _on_focus_out(self, *_args) -> bool:
        if self._cfg.get("close_on_unfocus") and self._menu.is_open():
            self.close_menu()
        return False
