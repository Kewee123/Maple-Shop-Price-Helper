"""The Mac-first prototype window."""
from __future__ import annotations

import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox

from . import __version__, capture, ocr, tooltip
from .model import PriceQuote, ShopItem, fmt_mesos, fmt_volume, parse_count, parse_mesos
from .pricing import ManualPriceProvider, ManualStore, PriceService, app_data_dir, site_links

BG = "#11151c"
CARD = "#19212d"
CARD_2 = "#202a38"
FG = "#e8edf5"
DIM = "#9aa7b8"
FAINT = "#6e7c8f"
ACCENT = "#f5c451"
GOOD = "#7ee2a8"
BAD = "#ff8a7a"

FONT = "Helvetica Neue"


def _label(parent, text="", *, size=12, color=FG, weight="normal", bg=BG, **kw):
    return tk.Label(parent, text=text, font=(FONT, size, weight), fg=color, bg=bg,
                    justify="left", anchor="w", **kw)


def _button(parent, text, command, *, kind="secondary", bg=CARD):
    """A flat, dark button: Tk's native buttons ignore bg on macOS."""
    button_bg, foreground, hover = ((ACCENT, "#1a1406", "#ffd875") if kind == "primary"
                                    else (CARD_2, FG, "#2b3748"))
    button = tk.Label(parent, text=text, font=(FONT, 11, "bold"), bg=button_bg, fg=foreground,
                      padx=10, pady=6, cursor="pointinghand")
    button.bind("<Button-1>", lambda _event: command())
    button.bind("<Enter>", lambda _event: button.configure(bg=hover))
    button.bind("<Leave>", lambda _event: button.configure(bg=button_bg))
    return button


def _point_in(rect, x, y) -> bool:
    if not rect:
        return False
    left, top, right, bottom = rect
    return left <= x <= right and top <= y <= bottom


class ShopPriceApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"Shop Price Helper {__version__} (prototype)")
        self.root.configure(bg=BG)
        self.root.geometry("620x840")
        self.root.minsize(560, 720)

        self.item: ShopItem | None = None
        self._editing_name = False
        self._last_image = None
        self._last_focus = None
        self._own_rect = None
        self._suggested_unit = self._suggested_total = None
        self._watching = threading.Event()
        self._force_read = threading.Event()
        self._stop = threading.Event()
        self._queue: queue.Queue = queue.Queue()

        self.manual_store = ManualStore()
        self.service = PriceService([ManualPriceProvider(self.manual_store)])

        self._build()
        self._apply_topmost()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(100, self._poll)
        self.root.after(500, self._track_own_rect)

        granted = capture.screen_recording_granted()
        self._granted = granted
        if granted:
            self._set_watching(True)
        else:
            self._set_watching(False)
            self._set_status("Screen Recording permission is needed. Allow this app (or Terminal "
                             "when running from source), then restart it.")

        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()

    # ------------------------------------------------------------------ UI
    def _build(self):
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill="both", expand=True, padx=18, pady=16)

        _label(outer, "Shop Price Helper", size=22, weight="bold").pack(anchor="w")
        _label(outer, "Hover an item in your shop or inventory. The OCR result is editable, because tooltips are small.",
               size=11, color=DIM).pack(anchor="w", pady=(0, 10))

        self.status_var = tk.StringVar(value="Starting…")
        _label(outer, textvariable=self.status_var, size=11, color=ACCENT,
               wraplength=540).pack(anchor="w", pady=(0, 10))

        watch_row = tk.Frame(outer, bg=BG)
        watch_row.pack(fill="x", pady=(0, 12))
        self.watch_btn = _button(watch_row, "Start watching", self._toggle_watch, kind="primary")
        self.watch_btn.pack(side="left")
        _button(watch_row, "Read last", self._read_last).pack(side="left", padx=(8, 0))
        _button(watch_row, "Save", self._save_capture).pack(side="left", padx=(8, 0))

        # ---- item card
        item_card = tk.Frame(outer, bg=CARD)
        item_card.pack(fill="x", pady=(0, 12))
        inner = tk.Frame(item_card, bg=CARD)
        inner.pack(fill="x", padx=14, pady=12)
        _label(inner, "ITEM", size=10, color=ACCENT, weight="bold", bg=CARD).pack(anchor="w")

        self.name_var = tk.StringVar()
        self.name_entry = tk.Entry(inner, textvariable=self.name_var, font=(FONT, 18, "bold"),
                                   bg=CARD, fg=FG, insertbackground=FG, relief="flat",
                                   highlightthickness=1, highlightbackground=CARD_2,
                                   highlightcolor=ACCENT)
        self.name_entry.pack(fill="x", pady=(4, 6))
        self.name_entry.bind("<FocusIn>", lambda _e: self._set_editing(True))
        self.name_entry.bind("<FocusOut>", lambda _e: self._name_changed())
        self.name_entry.bind("<Return>", lambda _e: self._name_changed())

        self.stats_var = tk.StringVar(value="Hover an item in your shop or inventory.")
        _label(inner, textvariable=self.stats_var, size=11, color=DIM, bg=CARD,
               wraplength=520).pack(anchor="w")

        qty_row = tk.Frame(inner, bg=CARD)
        qty_row.pack(fill="x", pady=(6, 0))
        _label(qty_row, "Quantity", size=10, color=FAINT, bg=CARD).pack(side="left")
        self.qty_var = tk.StringVar(value="1")
        self.qty_entry = tk.Entry(qty_row, textvariable=self.qty_var, width=8,
                                  font=(FONT, 12), bg=CARD_2, fg=FG, insertbackground=FG,
                                  relief="flat", highlightthickness=1, highlightbackground=CARD_2,
                                  highlightcolor=ACCENT)
        self.qty_entry.pack(side="left", padx=(8, 0))
        self.qty_entry.bind("<Return>", lambda _e: self._quantity_changed())
        self.qty_entry.bind("<FocusOut>", lambda _e: self._quantity_changed())

        self.raw_text = tk.Text(inner, height=3, width=1, font=("Menlo", 10), bg=CARD_2, fg=DIM,
                                bd=0, relief="flat", wrap="word", padx=8, pady=6)
        self.raw_text.pack(fill="x", pady=(8, 0))
        self.raw_text.configure(state="disabled")

        # ---- price card
        price_card = tk.Frame(outer, bg=CARD)
        price_card.pack(fill="x", pady=(0, 12))
        pinner = tk.Frame(price_card, bg=CARD)
        pinner.pack(fill="x", padx=14, pady=12)
        _label(pinner, "PRICES", size=10, color=ACCENT, weight="bold", bg=CARD).pack(anchor="w")

        self.suggested_var = tk.StringVar(value="—")
        suggested_row = tk.Frame(pinner, bg=CARD)
        suggested_row.pack(fill="x", pady=(6, 8))
        _label(suggested_row, "Suggested list", size=12, color=DIM, bg=CARD).pack(side="left")
        _label(suggested_row, textvariable=self.suggested_var, size=24, color=ACCENT,
               weight="bold", bg=CARD).pack(side="right")
        self.total_var = tk.StringVar(value="")
        _label(pinner, textvariable=self.total_var, size=10, color=FAINT, bg=CARD).pack(anchor="e")

        grid = tk.Frame(pinner, bg=CARD)
        grid.pack(fill="x")
        self.price_vars = {}
        rows = [
            ("typical", "Typical / median sold"),
            ("last", "Last sold"),
            ("volume", "24h sales / volume"),
            ("range", "Low – high"),
            ("sources", "Sources"),
        ]
        for row, (key, title) in enumerate(rows):
            _label(grid, title, size=10, color=FAINT, bg=CARD).grid(row=row, column=0, sticky="w", pady=1)
            var = tk.StringVar(value="—")
            self.price_vars[key] = var
            _label(grid, textvariable=var, size=11, color=FG, bg=CARD).grid(
                row=row, column=1, sticky="e", pady=1)
        grid.columnconfigure(0, weight=1)

        self.notice_var = tk.StringVar(value="")
        _label(pinner, textvariable=self.notice_var, size=10, color=FAINT, bg=CARD,
               wraplength=520).pack(anchor="w", pady=(8, 6))

        actions = tk.Frame(pinner, bg=CARD)
        actions.pack(fill="x", pady=(4, 0))
        _button(actions, "Set price…", self._edit_manual, kind="primary", bg=CARD).pack(side="left")
        _button(actions, "Copy suggested", self._copy_suggested, bg=CARD).pack(side="left", padx=(6, 0))
        self.meso_btn = _button(actions, "Open MesoWatch", lambda: self._open_source("MesoWatch"), bg=CARD)
        self.meso_btn.pack(side="right")
        self.cozy_btn = _button(actions, "Open Cozy", lambda: self._open_source("Cozy Market"), bg=CARD)
        self.cozy_btn.pack(side="right", padx=(0, 6))

        # ---- footer
        footer = tk.Frame(outer, bg=BG)
        footer.pack(fill="x", pady=(2, 0))
        _label(footer, "Manual prices only. MesoWatch is link-only; no site data is copied.",
               size=9, color=FAINT, wraplength=250).pack(side="left")
        _button(footer, "Allow screen…", self._ask_screen).pack(side="right")
        self.topmost_var = tk.BooleanVar(value=True)
        tk.Checkbutton(footer, text="Always on top", variable=self.topmost_var,
                       command=self._apply_topmost, bg=BG, fg=DIM, selectcolor=CARD,
                       activebackground=BG, activeforeground=FG,
                       font=(FONT, 10)).pack(side="right", padx=(0, 8))

    def _apply_topmost(self):
        self.root.attributes("-topmost", bool(self.topmost_var.get()))

    def _set_status(self, text: str):
        if text != self.status_var.get():
            self.status_var.set(text)

    def _set_watching(self, on: bool):
        if on and not self._granted:
            on = False
        if on:
            self._watching.set()
            self.watch_btn.configure(text="Pause watching")
            self._set_status("Watching for a tooltip near the cursor…")
        else:
            self._watching.clear()
            self.watch_btn.configure(text="Start watching")
            self._set_status("Paused.")

    def _toggle_watch(self):
        self._set_watching(not self._watching.is_set())

    def _ask_screen(self):
        capture.request_screen_recording()
        capture.open_screen_recording_settings()
        self._set_status("Turn on Screen Recording for this app (or Terminal), then restart it.")

    # -------------------------------------------------------------- capture
    def _track_own_rect(self):
        try:
            x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
            self._own_rect = (x, y, x + self.root.winfo_width(), y + self.root.winfo_height())
        except tk.TclError:
            return
        self.root.after(500, self._track_own_rect)

    def _watch_loop(self):
        last_pos = None
        stable_since = 0.0
        last_frame = None
        last_processed = 0.0
        last_note = ""
        while not self._stop.is_set():
            if not self._watching.is_set():
                time.sleep(0.15)
                continue
            if not self._granted:
                time.sleep(0.5)
                continue
            pos = capture.mouse_position()
            if pos is None:
                time.sleep(0.5)
                continue
            if _point_in(self._own_rect, *pos):
                time.sleep(0.15)
                continue
            window = capture.window_under_cursor(*pos)
            if not capture.is_game_window(window):
                note = "Move the cursor over the MapleStory game window."
                if note != last_note:
                    self._queue.put(("status", note))
                    last_note = note
                time.sleep(0.35)
                continue
            note = f"Watching {window.owner} · {window.title}".strip(" ·")
            if note != last_note:
                self._queue.put(("status", note))
                last_note = note
            now = time.monotonic()
            forced = self._force_read.is_set()
            if forced:
                self._force_read.clear()
            elif last_pos is None or abs(pos[0] - last_pos[0]) + abs(pos[1] - last_pos[1]) > 3:
                last_pos, stable_since, last_frame = pos, now, None
                continue
            elif now - stable_since < 0.35 or now - last_processed < 0.35:
                time.sleep(0.05)
                continue
            last_pos = pos
            region = capture.region_around(*pos)
            focus = ((pos[0] - region["left"]) / region["width"],
                     1 - (pos[1] - region["top"]) / region["height"])
            try:
                image = capture.grab(region, exclude=self._own_rect)
            except Exception as exc:
                self._queue.put(("error", f"Capture failed: {exc}"))
                time.sleep(0.5)
                continue
            if not forced and last_frame is not None and capture.frame_difference(last_frame, image) < 2.0:
                time.sleep(0.2)
                continue
            last_frame = image
            last_processed = now
            self._last_image = image
            self._last_focus = focus
            try:
                lines = ocr.recognize(image)
                item = tooltip.parse(lines, focus)
                self._queue.put(("ocr", item, lines, image))
            except Exception as exc:
                self._queue.put(("error", f"OCR failed: {exc}"))
            time.sleep(0.2)

    def _poll(self):
        try:
            while True:
                kind, *payload = self._queue.get_nowait()
                if kind == "ocr":
                    item, lines, image = payload
                    self._last_image = image
                    self._show_ocr(item, lines)
                elif kind == "error":
                    self._set_status(payload[0])
                elif kind == "status":
                    self._set_status(payload[0])
        except queue.Empty:
            pass
        except Exception as exc:
            self._set_status(f"{type(exc).__name__}: {exc}")
        if not self._stop.is_set():
            self.root.after(120, self._poll)

    def _show_ocr(self, item: ShopItem | None, lines):
        if self._editing_name:
            return
        if item is None:
            self._set_status("Text found, but no item tooltip in it. Move over an item and hold still.")
            self._raw_lines([line.text for line in lines])
            return
        self._set_status(f"Read {item.name} ({item.confidence * 100:.0f}% OCR confidence).")
        self.item = item
        self.name_var.set(item.name)
        self._show_item()
        self._lookup()

    def _show_item(self):
        if not self.item:
            self.stats_var.set("Hover an item in your shop or inventory.")
            self._raw_lines([])
            return
        self.qty_var.set(str(self.item.quantity or 1))
        bits = [f"{key}: {value}" for key, value in self.item.display_stats]
        self.stats_var.set("   ".join(bits) if bits else f"{self.item.category or 'item'} · no stats read")
        self._raw_lines(self.item.lines)

    def _raw_lines(self, lines):
        self.raw_text.configure(state="normal")
        self.raw_text.delete("1.0", "end")
        self.raw_text.insert("1.0", "\n".join(lines) if lines else "")
        self.raw_text.configure(state="disabled")

    def _set_editing(self, editing: bool):
        self._editing_name = editing

    def _name_changed(self):
        name = self.name_var.get().strip()
        self._editing_name = False
        if not name:
            return
        self.item = self.item.renamed(name) if self.item else ShopItem(name=name)
        self._show_item()
        self._lookup()

    def _quantity_changed(self):
        text = self.qty_var.get().replace(",", "").strip()
        try:
            quantity = max(1, int(text))
        except ValueError:
            quantity = 1
        self.qty_var.set(str(quantity))
        if self.item:
            self.item.quantity = quantity
            self._lookup()

    def _read_last(self):
        if self._last_image is None:
            self._set_status("Nothing captured yet. Hover an item first.")
            return
        try:
            lines = ocr.recognize(self._last_image)
            self._show_ocr(tooltip.parse(lines, self._last_focus), lines)
        except Exception as exc:
            self._set_status(f"OCR failed: {exc}")

    def _save_capture(self):
        if self._last_image is None:
            self._set_status("Nothing captured yet.")
            return
        try:
            path = capture.save_debug(self._last_image, app_data_dir() / "captures")
        except Exception as exc:
            self._set_status(f"Could not save the capture: {exc}")
            return
        self._set_status(f"Saved {path.name} in the app data folder.")
        self._open_path(path.parent)

    def _open_path(self, path: Path):
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform == "win32":
            import os
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)])

    # --------------------------------------------------------------- prices
    def _lookup(self):
        if not self.item:
            self._clear_prices()
            return
        summary, notices = self.service.lookup(self.item)
        self.price_vars["typical"].set(fmt_mesos(summary.typical))
        self.price_vars["last"].set(fmt_mesos(summary.last))
        self.price_vars["volume"].set(fmt_volume(summary.volume))
        self.price_vars["range"].set(
            f"{fmt_mesos(summary.low)} – {fmt_mesos(summary.high)}"
            if summary.low is not None or summary.high is not None else "—")
        self.price_vars["sources"].set(", ".join(summary.sources) or "none")
        suggested = summary.suggested()
        quantity = max(1, self.item.quantity)
        self._suggested_unit = suggested
        self._suggested_total = suggested * quantity if suggested is not None else None
        self.suggested_var.set(fmt_mesos(suggested) if suggested is not None else "—")
        self.total_var.set(f"Total for {quantity}: {fmt_mesos(self._suggested_total)} mesos"
                           if self._suggested_total is not None and quantity > 1 else "")
        notes = [q.note for q in summary.quotes if q.note]
        if notices:
            notes.extend(notices)
        if not summary.quotes:
            notes.append("No price yet: automatic sources are unavailable. "
                         "Use Set price… or open a site.")
        self.notice_var.set("  ·  ".join(dict.fromkeys(notes))[:220])

    def _clear_prices(self):
        for var in self.price_vars.values():
            var.set("—")
        self.suggested_var.set("—")
        self.total_var.set("")
        self._suggested_unit = self._suggested_total = None
        self.notice_var.set("")

    def _open_source(self, which: str):
        if not self.item:
            self._set_status("Hover or type an item name first.")
            return
        for name, url in site_links(self.item):
            if name == which:
                webbrowser.open(url)
                return

    def _copy_suggested(self):
        quantity = max(1, self.item.quantity) if self.item else 1
        value = self._suggested_total if quantity > 1 else self._suggested_unit
        if value is None:
            return
        text = f"{value:,}"
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._set_status(f"Copied {text} mesos" + (f" for {quantity}." if quantity > 1 else "."))

    def _edit_manual(self):
        if not self.item:
            self._set_status("Hover or type an item name first.")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Manual price")
        dialog.configure(bg=BG)
        dialog.transient(self.root)
        dialog.attributes("-topmost", bool(self.topmost_var.get()))
        body = tk.Frame(dialog, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=14)
        _label(body, self.item.name, size=16, weight="bold").pack(anchor="w")
        if self.item.variant:
            _label(body, self.item.variant, size=9, color=FAINT, wraplength=430).pack(anchor="w", pady=(0, 4))
        _label(body, "For your own pricing notes. Values are per unit.", size=9,
               color=FAINT).pack(anchor="w", pady=(0, 8))

        current = self.manual_store.quote(self.item)
        fields = [
            ("typical", "Typical / median sold per unit (e.g. 1.2m)"),
            ("last", "Last sold"),
            ("volume", "24h sales / volume (a count)"),
            ("low", "Low"),
            ("high", "High"),
        ]
        entries = {}
        for key, title in fields:
            _label(body, title, size=10, color=DIM).pack(anchor="w", pady=(6, 0))
            entry = tk.Entry(body, font=(FONT, 12), bg=CARD, fg=FG, insertbackground=FG,
                             relief="flat", highlightthickness=1, highlightbackground=CARD_2,
                             highlightcolor=ACCENT)
            entry.pack(fill="x", pady=(2, 0))
            if current:
                value = getattr(current, key)
                if value is not None:
                    entry.insert(0, f"{value:,}")
            entries[key] = entry

        def save():
            values = {key: _entry_value(entry, key == "volume") for key, entry in entries.items()}
            self.manual_store.put(self.item, **values)
            dialog.destroy()
            self._lookup()
            self._set_status("Manual price saved on this computer.")

        buttons = tk.Frame(body, bg=BG)
        buttons.pack(fill="x", pady=(14, 0))
        _button(buttons, "Save", save, kind="primary").pack(side="right")
        _button(buttons, "Cancel", dialog.destroy).pack(side="right", padx=(0, 6))

    def _close(self):
        self._stop.set()
        self.root.destroy()


def _entry_value(entry: tk.Entry, count: bool) -> int | None:
    text = entry.get().strip()
    return parse_count(text) if count else parse_mesos(text)


def main():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"Could not open the window: {exc}")
        return
    ShopPriceApp(root)
    root.mainloop()
