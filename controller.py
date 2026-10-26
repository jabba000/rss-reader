"""Controller layer: wires Model and View together.

Imports no Tk widgets. Reacts to key/select events from the View, mutates the
Model and tells the View what to display. Network I/O runs in worker threads;
results come back through a queue polled from the Tk main loop (Tk itself is
never touched from another thread).
"""
from __future__ import annotations

import queue
import threading
import webbrowser
from typing import Optional

from model import Feed, Model, Source
from view import READER, SOURCES, TITLES, View

SCROLL_LINES = 3
FETCH_DEBOUNCE_MS = 200  # avoids a download per feed while holding j/k
POLL_MS = 100

HELP = (
    "MiniRSS\n\n"
    "j / ↓ — down (scroll in the reading area)\n"
    "k / ↑ — up\n"
    "h / ← — focus the panel on the left\n"
    "l / → — focus the panel on the right\n"
    "g / G — top / bottom\n"
    "a — add a feed\n"
    "d — delete the selected feed\n"
    "r — refresh the feed\n"
    "o — open the article in a browser\n"
    "q — quit\n"
)


class Controller:
    def __init__(self, model: Model, view: View) -> None:
        self.model = model
        self.view = view

        self.entries = []                     # entries of the feed on screen
        self._shown_url: Optional[str] = None  # url of the feed on screen
        self._inflight: set[str] = set()
        self._results: queue.Queue = queue.Queue()
        self._fetch_job: Optional[str] = None

        view.set_key_handler(self.on_key)
        view.set_select_handler(self.on_select)

        self._refresh_sources(0 if model.sources else None)
        view.focus_pane(SOURCES)
        self._on_source_changed()
        view.after(POLL_MS, self._poll_results)

    # ------------------------------------------------------------ input ---
    def on_key(self, key: str) -> bool:
        pane = self.view.focused_pane
        if key in ("j", "down"):
            self._move(+1)
        elif key in ("k", "up"):
            self._move(-1)
        elif key in ("h", "left"):
            self.view.focus_pane(max(pane - 1, SOURCES))
        elif key in ("l", "right"):
            self.view.focus_pane(min(pane + 1, READER))
        elif key == "g":
            self._edge(top=True)
        elif key == "G":
            self._edge(top=False)
        elif key == "a":
            self.view.after(0, self._add_source)  # leave the key event first
        elif key == "d":
            self._delete_source()
        elif key == "r":
            self._refresh_current()
        elif key == "o":
            self._open_link()
        elif key == "q":
            self.view.quit()
        else:
            return False
        return True

    def on_select(self, pane: int) -> None:
        """Selection changed by mouse click."""
        if pane == SOURCES:
            self._on_source_changed()
        elif pane == TITLES:
            idx = self.view.selected_index(TITLES)
            if idx is not None:
                self._show_entry(idx)

    # -------------------------------------------------------- navigation ---
    def _move(self, delta: int) -> None:
        pane = self.view.focused_pane
        if pane == READER:
            self.view.scroll_reader(delta * SCROLL_LINES)
            return
        cur = self.view.selected_index(pane)
        self._select_in_pane(pane, 0 if cur is None else cur + delta)

    def _edge(self, top: bool) -> None:
        pane = self.view.focused_pane
        if pane == READER:
            self.view.scroll_reader_to(top)
        else:
            self._select_in_pane(pane, 0 if top else 10**9)

    def _select_in_pane(self, pane: int, index: int) -> None:
        count = len(self.model.sources) if pane == SOURCES else len(self.entries)
        if count == 0:
            return
        index = max(0, min(index, count - 1))
        if index == self.view.selected_index(pane):
            return
        self.view.select(pane, index)
        if pane == SOURCES:
            self._on_source_changed()
        else:
            self._show_entry(index)

    # ----------------------------------------------------------- actions ---
    def _add_source(self) -> None:
        raw = self.view.ask_text("Add feed URL")
        if not raw:
            return
        try:
            idx = self.model.add_source(raw)
        except ValueError as exc:
            self.view.set_status(str(exc))
            return
        self._refresh_sources(idx)
        self._on_source_changed()
        self._check_save()

    def _delete_source(self) -> None:
        idx = self.view.selected_index(SOURCES)
        if idx is None:
            return
        removed = self.model.remove_source(idx)
        remaining = len(self.model.sources)
        self._refresh_sources(min(idx, remaining - 1) if remaining else None)
        self._on_source_changed()
        if not self._check_save():
            self.view.set_status(f"Removed {removed.label}")

    def _refresh_current(self) -> None:
        src = self._current_source()
        if src is not None:
            self.view.set_status(f"Refreshing {src.label}…")
            self._start_fetch(src.url)

    def _open_link(self) -> None:
        idx = self.view.selected_index(TITLES)
        if idx is None or idx >= len(self.entries):
            return
        link = self.entries[idx].link
        if link:
            webbrowser.open(link)

    # ------------------------------------------------------ view updates ---
    def _current_source(self) -> Optional[Source]:
        idx = self.view.selected_index(SOURCES)
        if idx is None or idx >= len(self.model.sources):
            return None
        return self.model.sources[idx]

    def _current_link(self) -> Optional[str]:
        idx = self.view.selected_index(TITLES)
        if idx is None or idx >= len(self.entries):
            return None
        return self.entries[idx].link

    def _refresh_sources(self, select: Optional[int]) -> None:
        self.view.set_sources([s.label for s in self.model.sources], select)

    def _on_source_changed(self) -> None:
        if self._fetch_job is not None:
            self.view.after_cancel(self._fetch_job)
            self._fetch_job = None
        self.entries = []
        self._shown_url = None
        src = self._current_source()
        if src is None:
            self.view.set_titles([])
            self.view.show_message(HELP)
            self.view.set_status("")
            return
        feed = self.model.cached_feed(src.url)
        if feed is not None:
            self._show_feed(src.url, feed)
            return
        self.view.set_titles([])
        self.view.show_message("Loading…")
        self.view.set_status(f"Loading {src.url}")
        self._fetch_job = self.view.after(
            FETCH_DEBOUNCE_MS, lambda url=src.url: self._debounced_fetch(url)
        )

    def _debounced_fetch(self, url: str) -> None:
        self._fetch_job = None
        self._start_fetch(url)

    def _show_feed(self, url: str, feed: Feed, keep_link: Optional[str] = None) -> None:
        self.entries = feed.entries
        self._shown_url = url
        self.view.set_titles([e.title for e in feed.entries])
        name = feed.title or url
        if not feed.entries:
            self.view.show_message("This feed has no entries.")
            self.view.set_status(name)
            return
        idx = next(
            (i for i, e in enumerate(feed.entries) if keep_link and e.link == keep_link),
            0,
        )
        self.view.select(TITLES, idx)
        self._show_entry(idx)
        self.view.set_status(f"{name} — {len(feed.entries)} items")

    def _show_entry(self, idx: int) -> None:
        if 0 <= idx < len(self.entries):
            e = self.entries[idx]
            self.view.show_article(e.title, e.published, e.link, e.body)

    def _check_save(self) -> bool:
        if self.model.save_error:
            self.view.set_status(f"Cannot write sources.json: {self.model.save_error}")
            return True
        return False

    # ----------------------------------------------------------- network ---
    def _start_fetch(self, url: str) -> None:
        if url in self._inflight:
            return
        self._inflight.add(url)
        threading.Thread(target=self._worker, args=(url,), daemon=True).start()

    def _worker(self, url: str) -> None:
        try:
            result = (url, self.model.fetch_feed(url), None)
        except Exception as exc:  # network, parsing, anything
            result = (url, None, str(exc) or exc.__class__.__name__)
        self._results.put(result)

    def _poll_results(self) -> None:
        try:
            while True:
                url, feed, error = self._results.get_nowait()
                self._inflight.discard(url)
                self._on_fetched(url, feed, error)
        except queue.Empty:
            pass
        self.view.after(POLL_MS, self._poll_results)

    def _on_fetched(self, url: str, feed: Optional[Feed], error: Optional[str]) -> None:
        current = self._current_source()
        is_current = current is not None and current.url == url

        if error is not None or feed is None:
            if is_current:
                self.view.set_status(f"Error: {error}")
                if self.model.cached_feed(url) is None:
                    self.view.show_message(
                        f"Could not load this feed.\n\n{error}\n\nPress r to retry."
                    )
            return

        keep = self._current_link() if is_current and self._shown_url == url else None
        self.model.store_feed(url, feed)
        self._refresh_sources(self.view.selected_index(SOURCES))
        if is_current:
            self._show_feed(url, feed, keep)
        self._check_save()
