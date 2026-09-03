"""Settings dialog for editing the hyprtk-arc-menu configuration."""
from __future__ import annotations

from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GtkLayerShell", "0.1")

from gi.repository import Gdk, GLib, Gtk, GtkLayerShell

from .arc_menu import load_icon_image
from .config import POSITIONS, load, save

APP_DIRS = [
    Path.home() / ".local/share/applications",
    Path("/usr/local/share/applications"),
    Path("/usr/share/applications"),
    Path("/var/lib/flatpak/exports/share/applications"),
]


def _hex_to_rgba(hex_color: str) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    if not rgba.parse(hex_color or "#000000"):
        rgba.parse("#000000")
    return rgba


def _parse_desktop(path: Path) -> dict | None:
    name = exec_ = icon = comment = None
    in_section = False
    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("["):
            in_section = line == "[Desktop Entry]"
            continue
        if not in_section or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key == "Name":
            name = value
        elif key == "Exec":
            exec_ = value
        elif key == "Icon":
            icon = value
        elif key == "Comment":
            comment = value
        elif key in ("NoDisplay", "Hidden") and value.lower() in ("true", "1"):
            return None
    if not name or not exec_:
        return None
    clean = " ".join(tok for tok in exec_.split() if not tok.startswith("%"))
    return {
        "name": name,
        "exec": clean,
        "icon": icon or "application-x-executable",
        "comment": comment or name,
    }


def load_installed_apps() -> list[dict]:
    apps: dict[str, dict] = {}
    for directory in APP_DIRS:
        if not directory.is_dir():
            continue
        for f in sorted(directory.glob("*.desktop")):
            app = _parse_desktop(f)
            if app and app["exec"] not in apps:
                apps[app["exec"]] = app
    return sorted(apps.values(), key=lambda a: a["name"].lower())


def _rgba_to_hex(rgba: Gdk.RGBA) -> str:
    return "#{:02X}{:02X}{:02X}".format(
        int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255)
    )


class ItemDialog(Gtk.Dialog):
    """Add/edit a single menu item (icon, command, tooltip), with an embedded
    application search panel."""

    def __init__(self, parent, item: dict | None = None):
        super().__init__(title="Menu Item", transient_for=parent, modal=True)
        self.set_decorated(False)
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_namespace(self, "hyprtk-arc-menu-item")
        GtkLayerShell.set_exclusive_zone(self, -1)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        self.connect("key-press-event", self._on_key_press)

        self._apps = load_installed_apps()

        self.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("Save", Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)

        item = item or {"icon": "", "command": "", "tooltip": ""}
        box = self.get_content_area()
        box.set_spacing(8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)

        def field(label: str, value: str) -> Gtk.Entry:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            lbl = Gtk.Label(label=label, xalign=0)
            lbl.set_size_request(90, -1)
            entry = Gtk.Entry()
            entry.set_text(value or "")
            row.pack_start(lbl, False, False, 0)
            row.pack_start(entry, True, True, 0)
            box.pack_start(row, False, False, 0)
            return entry

        self._icon_entry = field("Icon", item.get("icon", ""))
        self._tooltip_entry = field("Tooltip", item.get("tooltip", ""))
        self._command_entry = field("Command", item.get("command", ""))
        self._action_entry = field("Action", item.get("action", ""))

        search_btn = Gtk.Button(label="Search Applications...")
        search_btn.connect("clicked", lambda _b: self._show_app_search())
        box.pack_start(search_btn, False, False, 0)

        # ── embedded application search panel (hidden until opened) ──
        self._search = Gtk.SearchEntry()
        self._search.set_placeholder_text("Type to search applications...")
        self._search.connect("search-changed", lambda _e: self._populate_apps())
        self._search.connect("activate", lambda _e: self._select_app())

        self._apps_list = Gtk.ListBox()
        self._apps_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._apps_list.connect("row-activated", lambda _l, _r: self._select_app())

        self._apps_scroll = Gtk.ScrolledWindow()
        self._apps_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._apps_scroll.set_size_request(-1, 280)
        self._apps_scroll.add(self._apps_list)

        hide_btn = Gtk.Button(label="Hide Search")
        hide_btn.connect("clicked", lambda _b: self._hide_app_search())

        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        search_row.pack_start(self._search, True, True, 0)
        search_row.pack_start(hide_btn, False, False, 0)

        for widget in (self._search, search_row, self._apps_scroll):
            widget.set_no_show_all(True)

        box.pack_start(search_row, False, False, 0)
        box.pack_start(self._apps_scroll, True, True, 0)

        hint = Gtk.Label(
            label="Icon: theme icon name (e.g. firefox).\n"
            "Action: 'settings' opens the arc menu settings instead of a command.",
            xalign=0,
            wrap=True,
        )
        hint.set_margin_top(4)
        box.pack_start(hint, False, False, 0)
        self.show_all()

    # ── embedded app search ─────────────────────────────────────

    def _show_app_search(self) -> None:
        self._search.set_visible(True)
        self._apps_scroll.set_visible(True)
        self._populate_apps()
        self._search.grab_focus()

    def _hide_app_search(self) -> None:
        self._search.set_visible(False)
        self._apps_scroll.set_visible(False)
        self._search.set_text("")

    def _populate_apps(self) -> None:
        for child in self._apps_list.get_children():
            self._apps_list.remove(child)
        query = self._search.get_text().strip().lower()
        for app in self._apps:
            if query and query not in app["name"].lower() and query not in (app["comment"] or "").lower():
                continue
            row = Gtk.ListBoxRow()
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            hbox.set_margin_top(4)
            hbox.set_margin_bottom(4)
            hbox.set_margin_start(6)
            hbox.set_margin_end(6)
            icon = load_icon_image(app["icon"], 24, "#000000")
            hbox.pack_start(icon, False, False, 0)
            labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            title = Gtk.Label(label=app["name"], xalign=0)
            sub = Gtk.Label(label=app.get("comment") or app["exec"], xalign=0, width_chars=45, ellipsize=True)
            sub.get_style_context().add_class("dim-label")
            labels.pack_start(title, False, False, 0)
            labels.pack_start(sub, False, False, 0)
            hbox.pack_start(labels, True, True, 0)
            row.add(hbox)
            row._app = app
            self._apps_list.add(row)
        self._apps_list.show_all()

    def _select_app(self) -> None:
        row = self._apps_list.get_selected_row() or self._apps_list.get_row_at_index(0)
        app = getattr(row, "_app", None)
        if app:
            self._icon_entry.set_text(app["icon"])
            self._tooltip_entry.set_text(app["name"])
            self._command_entry.set_text(app["exec"])
            self._action_entry.set_text("")
            self._hide_app_search()

    def _on_key_press(self, _widget, event) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
            return True
        return False

    def get_item(self) -> dict:
        item = {
            "icon": self._icon_entry.get_text().strip(),
            "tooltip": self._tooltip_entry.get_text().strip(),
        }
        action = self._action_entry.get_text().strip()
        command = self._command_entry.get_text().strip()
        if action:
            item["action"] = action
        if command:
            item["command"] = command
        return item


class SettingsDialog(Gtk.Window):
    """Floating, centered layer-shell window to edit the arc menu config."""

    def __init__(self, cfg: dict, on_saved=None):
        super().__init__(title="Arc Menu Settings")
        self._on_saved = on_saved
        self._cfg = cfg
        self._items: list[dict] = [dict(i) for i in cfg.get("items", [])]

        self.set_decorated(False)
        self.set_default_size(560, 620)
        self.set_resizable(True)
        self._init_layer_shell()
        self.connect("key-press-event", self._on_key_press)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.set_margin_start(16)
        vbox.set_margin_end(16)
        vbox.set_margin_top(16)
        vbox.set_margin_bottom(16)
        self.add(vbox)

        # ── general section ───────────────────────────────────────
        general = Gtk.Frame(label="General")
        gbox = Gtk.Grid(row_spacing=8, column_spacing=12)
        gbox.set_margin_start(12)
        gbox.set_margin_end(12)
        gbox.set_margin_top(8)
        gbox.set_margin_bottom(8)
        general.add(gbox)

        def spinner(value: int, lo: int, hi: int, step: int) -> Gtk.SpinButton:
            adj = Gtk.Adjustment(value=value, lower=lo, upper=hi, step_increment=step)
            spin = Gtk.SpinButton(adjustment=adj)
            return spin

        self._position_combo = Gtk.ComboBoxText()
        for position in POSITIONS:
            self._position_combo.append_text(position)
        current = cfg.get("position") or cfg.get("corner", "bottom-right")
        for i, position in enumerate(POSITIONS):
            if position == current:
                self._position_combo.set_active(i)
                break

        self._shape_combo = Gtk.ComboBoxText()
        for shape in ("circle", "square"):
            self._shape_combo.append_text(shape)
        self._shape_combo.set_active(0 if cfg.get("shape", "circle") == "circle" else 1)

        self._radius_spin = spinner(cfg.get("radius", 140), 40, 600, 10)
        self._margin_spin = spinner(cfg.get("margin", 24), 0, 200, 2)
        self._fab_spin = spinner(cfg.get("fab_size", 56), 24, 120, 4)
        self._item_spin = spinner(cfg.get("item_size", 48), 24, 120, 4)
        self._anim_spin = spinner(cfg.get("animation_time", 300), 50, 2000, 25)

        self._pywal_switch = Gtk.Switch()
        self._pywal_switch.set_active(bool(cfg.get("use_pywal", True)))

        self._waybar_switch = Gtk.Switch()
        self._waybar_switch.set_active(bool(cfg.get("follow_waybar", True)))

        self._transparent_switch = Gtk.Switch()
        self._transparent_switch.set_active(bool(cfg.get("transparent", False)))

        self._fab_color = Gtk.ColorButton()
        self._fab_color.set_rgba(_hex_to_rgba(cfg.get("fab_color", "#c084fc")))
        self._item_color = Gtk.ColorButton()
        self._item_color.set_rgba(_hex_to_rgba(cfg.get("item_color", "#22d3ee")))

        rows = [
            ("Position", self._position_combo),
            ("Shape", self._shape_combo),
            ("Radius (px)", self._radius_spin),
            ("Margin (px)", self._margin_spin),
            ("Menu button size (px)", self._fab_spin),
            ("Item size (px)", self._item_spin),
            ("Animation (ms)", self._anim_spin),
            ("Use pywal colors", self._pywal_switch),
            ("Follow Waybar theme", self._waybar_switch),
            ("Transparent (no background)", self._transparent_switch),
            ("Menu button color", self._fab_color),
            ("Item color", self._item_color),
        ]
        for r, (label, widget) in enumerate(rows):
            gbox.attach(Gtk.Label(label=label, xalign=0), 0, r, 1, 1)
            gbox.attach(widget, 1, r, 1, 1)

        vbox.pack_start(general, False, False, 0)

        # ── items section ─────────────────────────────────────────
        items_frame = Gtk.Frame(label="Menu Items")
        ivbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        ivbox.set_margin_start(12)
        ivbox.set_margin_end(12)
        ivbox.set_margin_top(8)
        ivbox.set_margin_bottom(8)
        items_frame.add(ivbox)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._populate_items()
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(220)
        scroll.add(self._list)
        ivbox.pack_start(scroll, True, True, 0)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        up_btn = Gtk.Button.new_from_icon_name("go-up", Gtk.IconSize.BUTTON)
        down_btn = Gtk.Button.new_from_icon_name("go-down", Gtk.IconSize.BUTTON)
        up_btn.set_tooltip_text("Move item up")
        down_btn.set_tooltip_text("Move item down")
        add_btn = Gtk.Button(label="Add")
        edit_btn = Gtk.Button(label="Edit")
        remove_btn = Gtk.Button(label="Remove")
        up_btn.connect("clicked", self._on_move_up)
        down_btn.connect("clicked", self._on_move_down)
        add_btn.connect("clicked", self._on_add)
        edit_btn.connect("clicked", self._on_edit)
        remove_btn.connect("clicked", self._on_remove)
        btn_row.pack_start(up_btn, False, False, 0)
        btn_row.pack_start(down_btn, False, False, 0)
        btn_row.pack_start(add_btn, False, False, 0)
        btn_row.pack_start(edit_btn, False, False, 0)
        btn_row.pack_start(remove_btn, False, False, 0)
        ivbox.pack_start(btn_row, False, False, 0)

        vbox.pack_start(items_frame, True, True, 0)

        # ── bottom buttons ────────────────────────────────────────
        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._status = Gtk.Label(xalign=0)
        self._status.get_style_context().add_class("dim-label")
        close_btn = Gtk.Button(label="Close")
        cancel = Gtk.Button(label="Cancel")
        save = Gtk.Button(label="Save")
        save.get_style_context().add_class("suggested-action")
        close_btn.connect("clicked", lambda _b: self.destroy())
        cancel.connect("clicked", lambda _b: self.destroy())
        save.connect("clicked", self._on_save)
        bottom.pack_start(self._status, True, True, 0)
        bottom.pack_end(save, False, False, 0)
        bottom.pack_end(cancel, False, False, 0)
        bottom.pack_end(close_btn, False, False, 0)
        vbox.pack_start(bottom, False, False, 0)

        self.show_all()

    # ── layer shell (floating, centered) ──────────────────────────

    def _init_layer_shell(self) -> None:
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_namespace(self, "hyprtk-arc-menu-settings")
        # No anchors on either axis -> the surface is centered on screen.
        GtkLayerShell.set_exclusive_zone(self, -1)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)

    def _on_key_press(self, _widget, event) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
            return True
        return False

    # ── items list ───────────────────────────────────────────────

    def _populate_items(self) -> None:
        for child in self._list.get_children():
            self._list.remove(child)
        for item in self._items:
            self._list.add(self._make_item_row(item))
        self._list.show_all()

    def _select_index(self, index: int) -> None:
        row = self._list.get_row_at_index(index)
        if row is not None:
            self._list.select_row(row)

    def _move_selected(self, delta: int) -> None:
        idx = self._selected_index()
        if idx is None:
            return
        new = idx + delta
        if new < 0 or new >= len(self._items):
            return
        self._items[idx], self._items[new] = self._items[new], self._items[idx]
        self._populate_items()
        self._select_index(new)

    def _on_move_up(self, _btn) -> None:
        self._move_selected(-1)

    def _on_move_down(self, _btn) -> None:
        self._move_selected(1)

    def _make_item_row(self, item: dict) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox.set_margin_top(4)
        hbox.set_margin_bottom(4)
        hbox.set_margin_start(6)
        hbox.set_margin_end(6)
        icon = load_icon_image(item.get("icon", "application-x-executable"), 24, "#000000")
        hbox.pack_start(icon, False, False, 0)
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title = Gtk.Label(
            label=item.get("tooltip") or item.get("command") or item.get("action", ""),
            xalign=0,
        )
        sub = Gtk.Label(
            label=(item.get("command") or item.get("action", "no command")),
            xalign=0,
            width_chars=50,
            ellipsize=True,
        )
        sub.get_style_context().add_class("dim-label")
        labels.pack_start(title, False, False, 0)
        labels.pack_start(sub, False, False, 0)
        hbox.pack_start(labels, True, True, 0)
        row.add(hbox)
        return row

    def _selected_index(self) -> int | None:
        row = self._list.get_selected_row()
        if row is None:
            return None
        return row.get_index()

    def _on_add(self, _btn) -> None:
        dlg = ItemDialog(self)
        if dlg.run() == Gtk.ResponseType.OK:
            self._items.append(dlg.get_item())
            self._populate_items()
        dlg.destroy()

    def _on_edit(self, _btn) -> None:
        idx = self._selected_index()
        if idx is None:
            return
        dlg = ItemDialog(self, self._items[idx])
        if dlg.run() == Gtk.ResponseType.OK:
            self._items[idx] = dlg.get_item()
            self._populate_items()
        dlg.destroy()

    def _on_remove(self, _btn) -> None:
        idx = self._selected_index()
        if idx is None:
            return
        del self._items[idx]
        self._populate_items()

    # ── save ─────────────────────────────────────────────────────

    def _on_save(self, _btn) -> None:
        position_list = list(POSITIONS)
        self._cfg["position"] = position_list[self._position_combo.get_active()]
        self._cfg["shape"] = "circle" if self._shape_combo.get_active() == 0 else "square"
        self._cfg["radius"] = self._radius_spin.get_value_as_int()
        self._cfg["margin"] = self._margin_spin.get_value_as_int()
        self._cfg["fab_size"] = self._fab_spin.get_value_as_int()
        self._cfg["item_size"] = self._item_spin.get_value_as_int()
        self._cfg["animation_time"] = self._anim_spin.get_value_as_int()
        self._cfg["use_pywal"] = self._pywal_switch.get_active()
        self._cfg["follow_waybar"] = self._waybar_switch.get_active()
        self._cfg["transparent"] = self._transparent_switch.get_active()
        self._cfg["fab_color"] = _rgba_to_hex(self._fab_color.get_rgba())
        self._cfg["item_color"] = _rgba_to_hex(self._item_color.get_rgba())
        self._cfg["items"] = self._items
        save(self._cfg)
        if self._on_saved:
            self._on_saved()
        self._status.set_text("Saved")
        if getattr(self, "_status_timer", None) is not None:
            GLib.source_remove(self._status_timer)
        self._status_timer = GLib.timeout_add(2000, self._clear_status)

    def _clear_status(self) -> bool:
        self._status.set_text("")
        self._status_timer = None
        return GLib.SOURCE_REMOVE