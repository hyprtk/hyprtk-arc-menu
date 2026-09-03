"""hyprtk-arc-menu entry point.

The menu is a plain always-running GTK window (layer-shell surface) driven by
Gtk.main(), with a GLib unix-signal handler so a SIGUSR1 toggles it. Using a bare
Gtk.Window + Gtk.main() keeps the overlay running (Gtk.Application would exit
immediately because the window isn't registered as an application window).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")

from gi.repository import GLib, GLibUnix, Gtk

from .app import ArcWindow
from .config import load as load_config

STATE_DIR = Path.home() / ".local" / "state" / "hyprtk-arc-menu"
PIDFILE = STATE_DIR / "pid"


def _write_pidfile() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    PIDFILE.write_text(str(os.getpid()))


def _remove_pidfile() -> None:
    try:
        PIDFILE.unlink()
    except FileNotFoundError:
        pass


def _toggle_running() -> bool:
    """Send SIGUSR1 to a running instance if present; else start one."""
    if PIDFILE.is_file():
        try:
            pid = int(PIDFILE.read_text().strip())
        except ValueError:
            pid = None
        if pid and os.path.isdir(f"/proc/{pid}"):
            os.kill(pid, signal.SIGUSR1)
            return True
    return False


def _print_config() -> None:
    print(json.dumps(load_config(), indent=2))


def _run_window() -> int:
    cfg = load_config()
    win = ArcWindow(cfg)
    win.show_all()

    def on_sigusr1(*_args):
        win.toggle()
        return GLib.SOURCE_CONTINUE

    def on_sigterm(*_args):
        Gtk.main_quit()
        return GLib.SOURCE_REMOVE

    GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, on_sigusr1, None)
    GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, on_sigterm, None)

    _write_pidfile()
    try:
        Gtk.main()
    finally:
        _remove_pidfile()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="hyprtk-arc-menu",
        description="Material-style arc menu for Wayland (GTK3 + layer shell).",
    )
    parser.add_argument(
        "--toggle",
        action="store_true",
        help="Toggle a running instance via SIGUSR1, or start one if none is running.",
    )
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="Print the resolved config as JSON and exit.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging."
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.print_config:
        _print_config()
        return 0

    if args.toggle and _toggle_running():
        return 0

    return _run_window()


if __name__ == "__main__":
    sys.exit(main())
