"""View layer: PyQt6 widgets only. No knowledge of the Model."""
from __future__ import annotations

from html import escape as html_escape
from typing import Callable, Optional

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QInputDialog,
    QListWidget,
    QMainWindow,
    QSplitter,
    QTextBrowser,
)

SOURCES, TITLES, READER = 0, 1, 2
APP_TITLE = "MiniRSS"
TEXT_COLOR = "#d7dae0"
MUTED_COLOR = "#8a94a6"
LINK_COLOR = "#6ab0f3"


class View(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._key_handler: Optional[Callable[[str], bool]] = None
        self._select_handler: Optional[Callable[[int], None]] = None
        self._current_pane = SOURCES
        self._timers: dict[int, QTimer] = {}
        self._timer_counter = 0
        self._build()

    def _build(self) -> None:
        self.setStyleSheet("""
            QMainWindow {
                background-color: #14161a;
            }
            QSplitter::handle {
                background-color: #1b1e24;
            }
            QListWidget {
                background-color: #1b1e24;
                color: #d7dae0;
                selection-background-color: #2d4f7c;
                selection-color: #ffffff;
                border: 2px solid #1b1e24;
                padding: 4px;
            }
            QListWidget:focus {
                border: 2px solid #4c9aff;
            }
            QTextBrowser {
                background-color: #1b1e24;
                color: #d7dae0;
                border: 2px solid #1b1e24;
                padding: 10px;
            }
            QTextBrowser:focus {
                border: 2px solid #4c9aff;
            }
        """)

        self.setWindowTitle(APP_TITLE)
        self.resize(1000, 600)
        self.setMinimumSize(640, 320)

        paned = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(paned)

        self.sources = QListWidget()
        self.titles = QListWidget()
        self.reader = QTextBrowser()
        self.reader.setOpenLinks(False)
        for widget in (self.sources, self.titles, self.reader):
            widget.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
        self.sources.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.titles.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )

        paned.addWidget(self.sources)
        paned.addWidget(self.titles)
        paned.addWidget(self.reader)
        paned.setSizes([190, 340, 470])
        self._panes = (self.sources, self.titles, self.reader)

        self.sources.currentRowChanged.connect(
            lambda _: self._on_listbox_select(SOURCES)
        )
        self.titles.currentRowChanged.connect(
            lambda _: self._on_listbox_select(TITLES)
        )

        self._install_vim_shortcuts()
        self.sources.setFocus()
        self._current_pane = SOURCES

    # ----------------------------------------------------- shortcuts ---
    def _install_vim_shortcuts(self) -> None:
        for widget in self._panes:
            widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.FocusIn:
            for i, widget in enumerate(self._panes):
                if widget is obj:
                    self._current_pane = i
                    break
        elif event.type() == QEvent.Type.KeyPress:
            key = self._key_from_event(event)
            if key is not None and self._key_handler is not None:
                if self._key_handler(key):
                    return True
        return super().eventFilter(obj, event)

    @staticmethod
    def _key_from_event(event: QKeyEvent) -> Optional[str]:
        special = {
            Qt.Key.Key_Up: "up",
            Qt.Key.Key_Down: "down",
            Qt.Key.Key_Left: "left",
            Qt.Key.Key_Right: "right",
        }
        if event.key() in special:
            return special[event.key()]
        text = event.text()
        if text and len(text) == 1 and text.isprintable():
            return text
        return None

    def _on_listbox_select(self, pane: int) -> None:
        if self._select_handler is not None:
            self._select_handler(pane)

    # ---------------------------------------------------- handlers ---
    def set_key_handler(self, handler: Callable[[str], bool]) -> None:
        self._key_handler = handler

    def set_select_handler(self, handler: Callable[[int], None]) -> None:
        self._select_handler = handler

    @property
    def focused_pane(self) -> int:
        return self._current_pane

    def focus_pane(self, pane: int) -> None:
        if 0 <= pane < len(self._panes):
            self._current_pane = pane
            self._panes[pane].setFocus()

    # -------------------------------------------------- data updates ---
    def set_sources(self, labels: list[str], select: Optional[int]) -> None:
        self.sources.blockSignals(True)
        try:
            self.sources.clear()
            self.sources.addItems(labels)
            if select is not None and 0 <= select < len(labels):
                self.sources.setCurrentRow(select)
        finally:
            self.sources.blockSignals(False)

    def set_titles(self, titles: list[str]) -> None:
        self.titles.blockSignals(True)
        try:
            self.titles.clear()
            self.titles.addItems(titles)
        finally:
            self.titles.blockSignals(False)

    def selected_index(self, pane: int) -> Optional[int]:
        if pane == READER:
            return None
        row = self._panes[pane].currentRow()
        return row if row >= 0 else None

    def select(self, pane: int, index: int) -> None:
        if pane == READER:
            return
        widget = self._panes[pane]
        widget.blockSignals(True)
        try:
            widget.setCurrentRow(index)
        finally:
            widget.blockSignals(False)

    # ------------------------------------------------------- content ---
    def show_message(self, text: str) -> None:
        escaped = html_escape(text).replace("\n", "<br>")
        self.reader.setHtml(
            f'<div style="color:{TEXT_COLOR};">{escaped}</div>'
        )

    def show_article(
        self, title: str, published: str, link: str, body: str
    ) -> None:
        parts = [f'<div style="color:{TEXT_COLOR};">']
        if title:
            parts.append(f"<h2>{html_escape(title)}</h2>")
        meta: list[str] = []
        if published:
            meta.append(html_escape(published))
        if link:
            href = html_escape(link, quote=True)
            meta.append(
                f'<a style="color:{LINK_COLOR};" '
                f'href="{href}">{html_escape(link)}</a>'
            )
        if meta:
            parts.append(
                f'<p style="color:{MUTED_COLOR};">'
                f'{" &middot; ".join(meta)}</p>'
            )
        body_html = html_escape(body).replace("\n", "<br>")
        parts.append(f"<p>{body_html}</p>")
        parts.append("</div>")
        self.reader.setHtml("".join(parts))

    def set_status(self, text: str) -> None:
        self.statusBar().showMessage(text)

    # ----------------------------------------------------- scrolling ---
    def scroll_reader(self, delta: int) -> None:
        bar = self.reader.verticalScrollBar()
        step = self.reader.fontMetrics().lineSpacing()
        bar.setValue(bar.value() + delta * step)

    def scroll_reader_to(self, top: bool) -> None:
        bar = self.reader.verticalScrollBar()
        bar.setValue(bar.minimum() if top else bar.maximum())

    # ------------------------------------------------------- dialogs ---
    def ask_text(self, prompt: str) -> Optional[str]:
        text, ok = QInputDialog.getText(self, APP_TITLE, prompt)
        return text if ok and text else None

    # -------------------------------------------------------- timers ---
    def after(self, ms: int, callback: Callable[[], None]) -> int:
        self._timer_counter += 1
        job_id = self._timer_counter
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(
            lambda jid=job_id: self._fire(jid, callback)
        )
        timer.start(ms)
        self._timers[job_id] = timer
        return job_id

    def _fire(self, job_id: int, callback: Callable[[], None]) -> None:
        timer = self._timers.pop(job_id, None)
        if timer is not None:
            timer.deleteLater()
        callback()

    def after_cancel(self, job_id: int) -> None:
        timer = self._timers.pop(job_id, None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()

    def quit(self) -> None:
        self.close()
