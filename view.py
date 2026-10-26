"""View layer: Tkinter widgets only. No knowledge of the Model.

The view reports raw user input to the controller through two callbacks:
    key handler    -> handler(key: str) -> bool   (True = key consumed)
    select handler -> handler(pane: int)          (mouse selection changed)
"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from typing import Callable, Optional, Sequence

SOURCES, TITLES, READER = 0, 1, 2

APP_TITLE = "MiniRSS"

BG = "#14161a"
PANEL = "#1b1e24"
FG = "#d7dae0"
DIM = "#7f8694"
ACCENT = "#4c9aff"
SEL_ACTIVE = "#2d4f7c"
SEL_INACTIVE = "#2b2f38"

_ARROWS = {
    "Up": "up", "KP_Up": "up",
    "Down": "down", "KP_Down": "down",
    "Left": "left", "KP_Left": "left",
    "Right": "right", "KP_Right": "right",
}
_HOTKEYS = frozenset("jkhldaroqgG")
# Same physical keys on a Russian (ЙЦУКЕН) layout, so hotkeys work in any layout.
_CYRILLIC = {
    "о": "j", "л": "k", "р": "h", "д": "l", "в": "d", "ф": "a",
    "к": "r", "щ": "o", "й": "q", "п": "g", "П": "G",
}


def _normalize(event: tk.Event) -> Optional[str]:
    name = _ARROWS.get(event.keysym)
    if name:
        return name
    ch = _CYRILLIC.get(event.char, event.char)
    return ch if ch in _HOTKEYS else None


class View:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._key_handler: Optional[Callable[[str], bool]] = None
        self._select_handler: Optional[Callable[[int], None]] = None
        self._current_pane = SOURCES
        self._build()

    # ------------------------------------------------------------ build ---
    def _build(self) -> None:
        root = self.root
        root.title(APP_TITLE)
        root.geometry("1000x600")
        root.minsize(640, 320)
        root.configure(bg=BG)

        base = tkfont.nametofont("TkDefaultFont")
        self._font_base = base
        self._font_title = base.copy()
        self._font_title.configure(weight="bold", size=int(base.cget("size") * 1.4))

        paned = tk.PanedWindow(
            root, orient="horizontal", bg=BG, bd=0,
            sashwidth=3, sashrelief="flat", opaqueresize=True,
        )
        paned.pack(fill="both", expand=True)

        self.sources = self._make_listbox(paned)
        self.titles = self._make_listbox(paned)
        
        # Виправлення 1: Видалено inactiveselectbackground=SEL_INACTIVE
        self.reader = tk.Text(
            paned, wrap="word", bg=PANEL, fg=FG, bd=0, relief="flat",
            highlightthickness=2, padx=18, pady=14, font=base,
            spacing3=6, cursor="arrow", insertwidth=0, state="disabled",
            selectbackground=SEL_ACTIVE,
        )
        self.reader.tag_configure("title", font=self._font_title,
                                  foreground="#ffffff", spacing3=8)
        self.reader.tag_configure("meta", foreground=DIM)

        paned.add(self.sources, width=190, minsize=100, stretch="never")
        paned.add(self.titles, width=340, minsize=140, stretch="never")
        paned.add(self.reader, minsize=240, stretch="always")

        self._panes = (self.sources, self.titles, self.reader)

        for i, w in enumerate(self._panes):
            w.bindtags((str(root), str(w), w.winfo_class(), "all"))
            w.bind("<FocusIn>", lambda _e, i=i: self._set_pane(i))
            w.bind("<Button-1>", lambda _e, w=w: w.focus_set(), add="+")
        for i in (SOURCES, TITLES):
            self._panes[i].bind(
                "<<ListboxSelect>>", lambda _e, i=i: self._on_listbox_select(i)
            )
        root.bind("<Key>", self._on_key)

        self._paint_focus()
        self.sources.focus_set()

    def _make_listbox(self, parent: tk.Widget) -> tk.Listbox:
        return tk.Listbox(
            parent, exportselection=False, selectmode="browse",
            activestyle="none", bg=PANEL, fg=FG, selectforeground="#ffffff",
            bd=0, relief="flat", highlightthickness=2, font=self._font_base,
        )

    # --------------------------------------------------------- callbacks ---
    def set_key_handler(self, handler: Callable[[str], bool]) -> None:
        self._key_handler = handler

    def set_select_handler(self, handler: Callable[[int], None]) -> None:
        self._select_handler = handler

    def _on_key(self, event: tk.Event) -> Optional[str]:
        if self._key_handler is None or event.state & 0x4:  # leave Ctrl+… alone
            return None
        key = _normalize(event)
        if key and self._key_handler(key):
            return "break"
        return None

    def _on_listbox_select(self, pane: int) -> None:
        if self._select_handler:
            self._select_handler(pane)

    # ------------------------------------------------------------- focus ---
    @property
    def focused_pane(self) -> int:
        return self._current_pane

    def focus_pane(self, pane: int) -> None:
        self._panes[pane].focus_set()
        self._set_pane(pane)

    def _set_pane(self, pane: int) -> None:
        self._current_pane = pane
        self._paint_focus()

    def _paint_focus(self) -> None:
        for i, w in enumerate(self._panes):
            active = i == self._current_pane
            ring = ACCENT if active else PANEL
            w.configure(highlightbackground=ring, highlightcolor=ring)
            # Виправлення 2: Застосовуємо selectbackground до всіх панелей, включно з reader
            w.configure(selectbackground=SEL_ACTIVE if active else SEL_INACTIVE)

    # ------------------------------------------------------------- lists ---
    def set_sources(self, labels: Sequence[str], selected: Optional[int] = None) -> None:
        self._fill(self.sources, labels, selected)

    def set_titles(self, labels: Sequence[str], selected: Optional[int] = None) -> None:
        self._fill(self.titles, labels, selected)

    @staticmethod
    def _fill(lb: tk.Listbox, labels: Sequence[str], selected: Optional[int]) -> None:
        lb.delete(0, "end")
        for label in labels:
            lb.insert("end", label)
        if selected is not None and labels:
            View._select(lb, selected)

    @staticmethod
    def _select(lb: tk.Listbox, index: int) -> None:
        lb.selection_clear(0, "end")
        lb.selection_set(index)
        lb.activate(index)
        lb.see(index)

    def select(self, pane: int, index: int) -> None:
        self._select(self._panes[pane], index)

    def selected_index(self, pane: int) -> Optional[int]:
        w = self._panes[pane]
        if not isinstance(w, tk.Listbox):
            return None
        sel = w.curselection()
        return int(sel[0]) if sel else None

    # ------------------------------------------------------------ reader ---
    def show_message(self, text: str) -> None:
        self._write([(text, "meta")])

    def show_article(self, title: str, published: str, link: str, body: str) -> None:
        meta = "  ·  ".join(p for p in (published, link) if p)
        parts = [(title + "\n", "title")]
        if meta:
            parts.append((meta + "\n\n", "meta"))
        parts.append((body, ""))
        self._write(parts)

    def _write(self, parts: Sequence[tuple[str, str]]) -> None:
        r = self.reader
        r.configure(state="normal")
        r.delete("1.0", "end")
        for text, tag in parts:
            r.insert("end", text, tag) if tag else r.insert("end", text)
        r.configure(state="disabled")
        r.yview_moveto(0.0)

    def scroll_reader(self, lines: int) -> None:
        self.reader.yview_scroll(lines, "units")

    def scroll_reader_to(self, top: bool) -> None:
        self.reader.yview_moveto(0.0 if top else 1.0)

    # ------------------------------------------------------------ window ---
    def set_status(self, text: str) -> None:
        """Status goes into the window title: keeps the UI to three panes."""
        self.root.title(f"{APP_TITLE} — {text}" if text else APP_TITLE)

    def after(self, ms: int, fn: Callable[[], None]) -> str:
        return self.root.after(ms, fn)

    def after_cancel(self, job: str) -> None:
        self.root.after_cancel(job)

    def quit(self) -> None:
        self.root.destroy()

    # ------------------------------------------------------------ dialog ---
    def ask_text(self, title: str) -> Optional[str]:
        """Modal one-line input. Enter confirms, Esc cancels."""
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.configure(bg=BG)
        dlg.transient(self.root)
        dlg.resizable(True, False)

        var = tk.StringVar()
        entry = tk.Entry(
            dlg, textvariable=var, width=58, bg=PANEL, fg=FG,
            insertbackground=FG, relief="flat", font=self._font_base,
            highlightthickness=2, highlightbackground=PANEL, highlightcolor=ACCENT,
            selectbackground=SEL_ACTIVE,
        )
        entry.pack(fill="x", padx=14, pady=14, ipady=4)

        result: dict[str, Optional[str]] = {"value": None}

        def confirm(_e=None) -> None:
            result["value"] = var.get().strip()
            dlg.destroy()

        entry.bind("<Return>", confirm)
        entry.bind("<KP_Enter>", confirm)
        dlg.bind("<Escape>", lambda _e: dlg.destroy())

        dlg.update_idletasks()
        w, h = dlg.winfo_reqwidth(), dlg.winfo_reqheight()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - h) // 3
        
        # Виправлення 3: Коректне форматування координат для багатомоніторних систем
        geom_x = f"+{x}" if x >= 0 else str(x)
        geom_y = f"+{y}" if y >= 0 else str(y)
        dlg.geometry(f"{geom_x}{geom_y}")

        entry.focus_set()
        try:
            dlg.wait_visibility()  # grab fails on X11 if the window isn't mapped yet
            dlg.grab_set()
        except tk.TclError:
            pass
        dlg.wait_window()

        self.focus_pane(self._current_pane)
        return result["value"]
