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

from . import __version__, browser, capture, catalog, ocr, quantity, tooltip
from .model import ShopItem
from .pricing import app_data_dir, site_links

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
    button = tk.Label(parent, text=text, font=(FONT, 10, "bold"), bg=button_bg, fg=foreground,
                      padx=8, pady=5, cursor="pointinghand")
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
        self.root.geometry("480x430")
        self.root.minsize(420, 360)

        self.item: ShopItem | None = None
        self._editing_name = False
        self._last_image = None
        self._last_focus = None
        self._last_cursor: tuple[tuple[float, float], float] | None = None
        self._own_rect = None
        self._game_rect = None
        self._watching = threading.Event()
        self._force_read = threading.Event()
        self._stop = threading.Event()
        self._queue: queue.Queue = queue.Queue()
        self._last_browser_item = ""
        self._candidate_name = ""
        self._candidate_count = 0
        self._candidate_item = None
        self._candidate_window = None
        self._browser_anchor = None
        self._browser_lock = threading.Lock()
        self._browser_generation = 0
        self._startup_positioned = False

        self._build()
        self._apply_topmost()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(100, self._poll)
        self.root.after(500, self._track_own_rect)
        self.root.after(250, self._position_next_to_game)

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
        outer.pack(fill="both", expand=True, padx=12, pady=10)

        _label(outer, "Shop Price Helper", size=18, weight="bold").pack(anchor="w")
        _label(outer, "Hover an inventory item to search MesoWatch.",
               size=10, color=DIM).pack(anchor="w", pady=(0, 6))

        self.status_var = tk.StringVar(value="Starting…")
        _label(outer, textvariable=self.status_var, size=11, color=ACCENT,
               wraplength=440).pack(anchor="w", pady=(0, 6))

        watch_row = tk.Frame(outer, bg=BG)
        watch_row.pack(fill="x", pady=(0, 7))
        self.watch_btn = _button(watch_row, "Start watching", self._toggle_watch, kind="primary")
        self.watch_btn.pack(side="left")
        _button(watch_row, "Read last", self._read_last).pack(side="left", padx=(8, 0))
        _button(watch_row, "Save", self._save_capture).pack(side="left", padx=(8, 0))

        # ---- item card
        item_card = tk.Frame(outer, bg=CARD)
        item_card.pack(fill="x", pady=(0, 7))
        inner = tk.Frame(item_card, bg=CARD)
        inner.pack(fill="x", padx=10, pady=9)
        _label(inner, "ITEM", size=10, color=ACCENT, weight="bold", bg=CARD).pack(anchor="w")

        self.name_var = tk.StringVar()
        self.name_entry = tk.Entry(inner, textvariable=self.name_var, font=(FONT, 15, "bold"),
                                   bg=CARD, fg=FG, insertbackground=FG, relief="flat",
                                   highlightthickness=1, highlightbackground=CARD_2,
                                   highlightcolor=ACCENT)
        self.name_entry.pack(fill="x", pady=(3, 4))
        self.name_entry.bind("<FocusIn>", lambda _e: self._set_editing(True))
        self.name_entry.bind("<FocusOut>", lambda _e: self._name_changed())
        self.name_entry.bind("<Return>", lambda _e: self._name_changed())

        self.stats_var = tk.StringVar(value="Hover an item in your inventory.")
        _label(inner, textvariable=self.stats_var, size=11, color=DIM, bg=CARD,
               wraplength=520).pack(anchor="w")
        self.description_var = tk.StringVar(value="")
        _label(inner, textvariable=self.description_var, size=10, color=FAINT, bg=CARD,
               wraplength=520).pack(anchor="w", pady=(4, 0))

        qty_row = tk.Frame(inner, bg=CARD)
        qty_row.pack(fill="x", pady=(4, 0))
        _label(qty_row, "Quantity", size=10, color=FAINT, bg=CARD).pack(side="left")
        self.qty_var = tk.StringVar(value="1")
        self.qty_entry = tk.Entry(qty_row, textvariable=self.qty_var, width=8,
                                  font=(FONT, 12), bg=CARD_2, fg=FG, insertbackground=FG,
                                  relief="flat", highlightthickness=1, highlightbackground=CARD_2,
                                  highlightcolor=ACCENT)
        self.qty_entry.pack(side="left", padx=(8, 0))
        _label(qty_row, "auto-read from the hovered slot", size=9, color=FAINT, bg=CARD).pack(
            side="left", padx=(8, 0))
        self.qty_entry.bind("<Return>", lambda _e: self._quantity_changed())
        self.qty_entry.bind("<FocusOut>", lambda _e: self._quantity_changed())

        self.raw_text = tk.Text(inner, height=2, width=1, font=("Menlo", 9), bg=CARD_2, fg=DIM,
                                bd=0, relief="flat", wrap="word", padx=8, pady=6)
        self.raw_text.pack(fill="x", pady=(5, 0))
        self.raw_text.configure(state="disabled")

        # ---- footer
        footer = tk.Frame(outer, bg=BG)
        footer.pack(fill="x", pady=(0, 0))
        _label(footer, "MesoWatch browser search only. No site pages are copied.",
               size=9, color=FAINT, wraplength=250).pack(side="left")
        _button(footer, "Retry search",
                lambda: self._open_source("MesoWatch")).pack(side="right")
        _button(footer, "Chrome setup", self._enable_chrome_search).pack(side="right")
        _button(footer, "Screen access", self._ask_screen).pack(side="right")
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

    def _enable_chrome_search(self):
        try:
            browser.open_chrome_automation_settings()
        except browser.BrowserAutomationUnavailable as exc:
            self._set_status(str(exc))
            return
        self._set_status(
            "In Chrome's macOS menu bar, choose Develop → Allow JavaScript from Apple Events, then retry."
        )

    # -------------------------------------------------------------- capture
    def _track_own_rect(self):
        try:
            x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
            self._own_rect = (x, y, x + self.root.winfo_width(), y + self.root.winfo_height())
        except tk.TclError:
            return
        self.root.after(500, self._track_own_rect)

    def _position_next_to_game(self):
        """Place the compact helper beside MapleStory once at startup."""
        if self._startup_positioned or self._stop.is_set():
            return
        try:
            game = next(
                (window for window in capture.on_screen_windows()
                 if capture.is_game_window(window)),
                None,
            )
            if game is None:
                self.root.after(500, self._position_next_to_game)
                return
            self.root.update_idletasks()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            gap = 12
            margin = 12
            right_space = screen_width - (game.left + game.width) - gap - margin
            left_space = game.left - gap - margin
            if right_space >= 320:
                left = game.left + game.width + gap
                width = min(width, right_space)
                top = max(margin, min(game.top, screen_height - height - margin))
            elif left_space >= 320:
                width = min(width, left_space)
                left = game.left - gap - width
                top = max(margin, min(game.top, screen_height - height - margin))
            else:
                # There is no full-width side beside the game. Keep the
                # helper visible and aligned with the game's top edge rather
                # than allowing a negative x coordinate.
                width = min(width, max(320, screen_width - 2 * margin))
                left = max(margin, screen_width - width - margin)
                top = max(margin, screen_height - height - margin)
            height = min(height, max(300, screen_height - top - margin))
            self.root.geometry(f"{width}x{height}+{max(margin, left)}+{top}")
            self._startup_positioned = True
        except tk.TclError:
            return

    def _watch_loop(self):
        last_pos = None
        stable_since = 0.0
        last_frame = None
        last_ocr_frame = None
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
            if not capture.point_in_rect(pos, capture.inventory_rect(window)):
                note = "Move the cursor over an inventory item."
                if note != last_note:
                    self._queue.put(("status", note))
                    last_note = note
                last_pos = None
                last_frame = None
                last_ocr_frame = None
                time.sleep(0.15)
                continue
            window_id = (window.number, window.pid)
            note = f"Watching {window.owner} · {window.title}".strip(" ·")
            self._game_rect = (
                window.left,
                window.top,
                window.left + window.width,
                window.top + window.height,
            )
            if note != last_note:
                self._queue.put(("status", note))
                last_note = note
            now = time.monotonic()
            forced = self._force_read.is_set()
            if forced:
                self._force_read.clear()
            elif last_pos is None or abs(pos[0] - last_pos[0]) + abs(pos[1] - last_pos[1]) > 3:
                last_pos, stable_since, last_frame, last_ocr_frame = pos, now, None, None
                continue
            elif now - stable_since < 0.15 or now - last_processed < 0.20:
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
            last_frame = image
            last_processed = now
            scale_x = image.width / region["width"]
            scale_y = image.height / region["height"]
            cursor_px = ((pos[0] - region["left"]) * scale_x,
                         (pos[1] - region["top"]) * scale_y)
            self._last_image = image
            self._last_focus = focus
            self._last_cursor = (cursor_px, (scale_x + scale_y) / 2)
            try:
                ocr_image, ocr_focus = capture.crop_for_ocr(image, cursor_px)
                if (not forced and last_ocr_frame is not None
                        and capture.frame_difference(last_ocr_frame, ocr_image) < 2.0):
                    time.sleep(0.15)
                    continue
                lines = ocr.recognize(ocr_image)
                item = tooltip.parse(lines, ocr_focus)
                # Do not mark an unreadable frame as complete. Vision can
                # transiently miss a tooltip while MapleStory is repainting
                # it; retrying the same hover is preferable to waiting for
                # the user to move away and back.
                if item is None:
                    time.sleep(0.08)
                    continue
                last_ocr_frame = ocr_image
                self._apply_screen_quantity(item, image)
                # OCR can take long enough for the cursor to move to another
                # slot. Never let a result for the old hover replace the new
                # item in the UI.
                current_pos = capture.mouse_position()
                current_window = (
                    capture.window_under_cursor(*current_pos)
                    if current_pos is not None else None
                )
                if current_pos is not None and (
                    abs(current_pos[0] - pos[0]) > 3 or abs(current_pos[1] - pos[1]) > 3
                ):
                    continue
                if current_window is None or (
                    current_window.number, current_window.pid
                ) != window_id:
                    continue
                self._queue.put(("ocr", pos, window_id, item, lines, image))
            except Exception as exc:
                self._queue.put(("error", f"OCR failed: {exc}"))
            time.sleep(0.2)

    def _apply_screen_quantity(self, item: ShopItem | None, image) -> None:
        """Fill the stack count from the hovered slot when the tooltip doesn't say it."""
        if item is None or item.quantity > 1 or self._last_cursor is None:
            return
        cursor_px, scale = self._last_cursor
        count = quantity.read_count(image, cursor_px, scale)
        if count is not None:
            item.quantity = count

    def _poll(self):
        latest_ocr = None
        try:
            while True:
                kind, *payload = self._queue.get_nowait()
                if kind == "ocr":
                    latest_ocr = payload
                elif kind == "error":
                    self._set_status(payload[0])
                elif kind == "status":
                    self._set_status(payload[0])
                elif kind == "validated":
                    item, canonical_name = payload
                    if item is self.item:
                        self.name_var.set(canonical_name)
                        self._set_status(f"Confirmed {canonical_name} locally; opening MesoWatch…")
                elif kind == "validation_status":
                    item, status = payload
                    if item is self.item:
                        self._set_status(status)
                elif kind == "validation_failed":
                    item, error = payload
                    if item is self.item:
                        self._set_status(
                            f"{item.name} was not found in the local item database ({error}); "
                            "MesoWatch was not opened."
                        )
                elif kind == "browser":
                    item, error = payload
                    if item is not self.item:
                        continue
                    if error is None:
                        self._set_status(f"Opened and selected {item.name} in MesoWatch.")
                    else:
                        try:
                            self.root.clipboard_clear()
                            self.root.clipboard_append(item.name)
                        except tk.TclError:
                            self._set_status(f"MesoWatch search failed: {error}")
                        else:
                            self._set_status(
                                f"MesoWatch search failed ({error}). "
                                f"Copied {item.name}; paste it into the existing Search box."
                            )
        except queue.Empty:
            pass
        except Exception as exc:
            self._set_status(f"{type(exc).__name__}: {exc}")
        if latest_ocr is not None:
            captured_pos, window_id, item, lines, image = latest_ocr
            current_pos = capture.mouse_position()
            current_window = (
                capture.window_under_cursor(*current_pos)
                if current_pos is not None else None
            )
            if current_pos is None or (
                abs(current_pos[0] - captured_pos[0]) <= 3
                and abs(current_pos[1] - captured_pos[1]) <= 3
                and current_window is not None
                and (current_window.number, current_window.pid) == window_id
            ):
                self._last_image = image
                self._show_ocr(item, lines)
        if not self._stop.is_set():
            self.root.after(120, self._poll)

    def _show_ocr(self, item: ShopItem | None, lines):
        if self._editing_name:
            return
        if item is None:
            self._candidate_name = ""
            self._candidate_count = 0
            self._candidate_item = None
            self._candidate_window = None
            self.item = None
            self._last_browser_item = ""
            self._show_item()
            self._set_status("Text found, but no item tooltip in it. Move over an item and hold still.")
            self._raw_lines([line.text for line in lines])
            return
        # OCR often changes punctuation or drops a character between frames.
        # Resolve that noise against the local catalog before deciding whether
        # this is a new hover target, so switching slots cannot get stuck in
        # the previous item's confirmation state.
        catalog_item = catalog.lookup(item.name)
        if catalog_item is not None:
            item = item.renamed(catalog_item.name)
            item.category = item.category or catalog_item.category.casefold()
        else:
            self._candidate_name = ""
            self._candidate_count = 0
            self._candidate_item = None
            self._set_status(f"Checking item name: {item.name}…")
            self._raw_lines(item.lines)
            return
        current_window = capture.window_under_cursor(*capture.mouse_position()) if capture.mouse_position() else None
        window_id = (
            (current_window.number, current_window.pid)
            if current_window is not None else None
        )
        if window_id != self._candidate_window:
            self._candidate_name = ""
            self._candidate_count = 0
            self._candidate_item = None
            self._candidate_window = window_id
        candidate_key = catalog_item.name
        if candidate_key == self._candidate_name:
            self._candidate_count += 1
        else:
            self._candidate_name = candidate_key
            self._candidate_count = 1
            self._candidate_item = item
        self._raw_lines(item.lines)
        # The local catalog is a strong second signal. Requiring another OCR
        # frame makes fast inventory changes feel stuck, especially for simple
        # drops such as Firewood that have no stat lines.
        if self._candidate_count < 1:
            self._set_status(f"Confirming {item.name}…")
            return
        item = self._candidate_item or item
        stack = f" · stack {item.quantity}" if item.quantity > 1 else ""
        self._set_status(f"Read {item.name}{stack} ({item.confidence * 100:.0f}% OCR confidence).")
        self.item = item
        self.name_var.set(item.name)
        self._show_item()
        if item.name != self._last_browser_item:
            self._last_browser_item = item.name
            self._open_source("MesoWatch")

    def _show_item(self):
        if not self.item:
            self.name_var.set("")
            self.qty_var.set("1")
            self.stats_var.set("Hover an item in your inventory.")
            self.description_var.set("")
            self._raw_lines([])
            return
        self.qty_var.set(str(self.item.quantity or 1))
        bits = [f"{key}: {value}" for key, value in self.item.display_stats]
        self.stats_var.set("   ".join(bits) if bits else
                           (f"{self.item.category or 'item'} · no weapon stats read"
                            if self.item.category == "weapon" else ""))
        self.description_var.set(self.item.description)
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

    def _quantity_changed(self):
        text = self.qty_var.get().replace(",", "").strip()
        try:
            quantity = max(1, int(text))
        except ValueError:
            quantity = 1
        self.qty_var.set(str(quantity))
        if self.item:
            self.item.quantity = quantity

    def _read_last(self):
        if self._last_image is None:
            self._set_status("Nothing captured yet. Hover an item first.")
            return
        try:
            lines = ocr.recognize(self._last_image)
            item = tooltip.parse(lines, self._last_focus)
            self._apply_screen_quantity(item, self._last_image)
            self._show_ocr(item, lines)
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

    def _open_source(self, which: str):
        if not self.item:
            self._set_status("Hover or type an item name first.")
            return
        for name, url in site_links(self.item):
            if name == which:
                if name == "MesoWatch":
                    item = self.item
                    self._browser_generation += 1
                    browser_generation = self._browser_generation
                    self._set_status(f"Opening MesoWatch for {item.name}…")
                    anchor = self._own_rect
                    game_rect = self._game_rect
                    screen_size = (
                        self.root.winfo_screenwidth(),
                        self.root.winfo_screenheight(),
                    )
                    should_position_browser = (
                        anchor is not None and anchor != self._browser_anchor
                    )
                    if should_position_browser:
                        self._browser_anchor = anchor

                    def search() -> None:
                        try:
                            self._queue.put(("validation_status", item, "Checking local item database…"))
                            match = catalog.lookup(item.name)
                            if match is None:
                                raise ValueError("item name was not found in the local database")
                            canonical_name = match.name
                            self._queue.put(("validated", item, canonical_name))
                            with self._browser_lock:
                                # A previous AppleScript call may still be
                                # finishing. Do not let it overwrite the
                                # newest hovered item in Chrome.
                                if browser_generation != self._browser_generation:
                                    return
                                browser.search_mesowatch(
                                    canonical_name,
                                    anchor=anchor if should_position_browser else None,
                                    screen_size=screen_size if should_position_browser else None,
                                    avoid_rect=game_rect if should_position_browser else None,
                                )
                        except (browser.BrowserAutomationUnavailable, ValueError) as exc:
                            self._queue.put(("validation_failed", item, str(exc)))
                        else:
                            self._queue.put(("browser", item, None))

                    threading.Thread(target=search, daemon=True).start()
                else:
                    webbrowser.open(url)
                if name == "Cozy Market":
                    try:
                        self.root.clipboard_clear()
                        self.root.clipboard_append(self.item.name)
                        self._set_status("Opened Cozy Market. Item name copied — paste it in Search.")
                    except tk.TclError:
                        self._set_status("Opened Cozy Market. Type the item name in Search.")
                return

    def _close(self):
        self._stop.set()
        self.root.destroy()


def main():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"Could not open the window: {exc}")
        return
    ShopPriceApp(root)
    root.mainloop()
