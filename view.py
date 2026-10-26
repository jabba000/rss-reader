"""View layer: PyQt6 widgets only. No knowledge of the Model."""
from __future__ import annotations

from html import escape as html_escape
from typing import Callable, Optional

from PyQt6.QtCore import QEvent, Qt, QTimer, QUrl
from PyQt6.QtGui import QKeyEvent, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QInputDialog,
    QListWidget,
    QMainWindow,
    QSplitter,
    QTabWidget,
    QTextBrowser,
)

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    QWebEngineView = None  # type: ignore[assignment,misc]
    HAS_WEBENGINE = False

SOURCES, TITLES, READER = 0, 1, 2
ARTICLE_TAB, BROWSER_TAB = 0, 1
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
        self._previous_pane = SOURCES
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
            QTabWidget::pane {
                border: 2px solid #1b1e24;
            }
            QTabBar::tab {
                background-color: #1b1e24;
                color: #8a94a6;
                padding: 4px 12px;
            }
            QTabBar::tab:selected {
                background-color: #2d4f7c;
                color: #ffffff;
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

        self.tabs = QTabWidget()
        self.tabs.addTab(self.reader, "Article")

        if HAS_WEBENGINE:
            self.browser: Optional[QWebEngineView] = QWebEngineView()
            self.browser.setHtml(
                '<html><body style="background:#1b1e24;color:#d7dae0;'
                'font-family:sans-serif;display:flex;align-items:center;'
                'justify-content:center;height:100vh;margin:0;">'
                '<p>Press <b>o</b> on an article to open it here. '
                'Press <b>Esc</b> to return.</p>'
                '</body></html>'
            )
            self.tabs.addTab(self.browser, "Browser")
        else:
            self.browser = None

        paned.addWidget(self.sources)
        paned.addWidget(self.titles)
        paned.addWidget(self.tabs)
        paned.setSizes([190, 340, 470])
        self._panes = (self.sources, self.titles, self.tabs)

        self.sources.currentRowChanged.connect(
            lambda _: self._on_listbox_select(SOURCES)
        )
        self.titles.currentRowChanged.connect(
            lambda _: self._on_listbox_select(TITLES)
        )

        self._install_input_handlers()
        self.sources.setFocus()
        self._current_pane = SOURCES

    # --------------------------------------------------- input wiring ---
     # --------------------------------------------------- input wiring ---
    def _install_input_handlers(self) -> None:
        for widget in (self.sources, self.titles, self.reader):
            widget.installEventFilter(self)

        self._esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._esc_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._esc_shortcut.activated.connect(self._on_escape_shortcut)

        # Register vi keys on the tab widget with WidgetWithChildrenShortcut so
        # they fire even when focus is inside the embedded browser's render
        # widget, which normally eats key events.
        self._browser_shortcuts: list[QShortcut] = []
        for key in ("j", "k", "h", "l", "g", "G",
                    "a", "d", "r", "o", "q",
                    "t", "1", "2"):
            sc = QShortcut(QKeySequence(key), self.tabs)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(lambda k=key: self._dispatch_key(k))
            self._browser_shortcuts.append(sc)

        app = QApplication.instance()
        if app is not None:
            app.focusChanged.connect(self._on_focus_changed)

    def _dispatch_key(self, key: str) -> None:
        if self._key_handler is not None:
            self._key_handler(key)

    def _on_escape_shortcut(self) -> None:
        self._dispatch_key("escape")

    def _on_focus_changed(self, old, new) -> None:
        if new is None:
            return
        if new is self.sources or self.sources.isAncestorOf(new):
            self._current_pane = SOURCES
        elif new is self.titles or self.titles.isAncestorOf(new):
            self._current_pane = TITLES
        elif new is self.tabs or self.tabs.isAncestorOf(new):
            self._current_pane = READER

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
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

    def set_key_handler(self, handler: Callable[[str], bool]) -> None:
        self._key_handler = handler

    def set_select_handler(self, handler: Callable[[int], None]) -> None:
        self._select_handler = handler

    # ---------------------------------------------------------- focus ---
    @property
    def focused_pane(self) -> int:
        return self._current_pane

    def focus_pane(self, pane: int) -> None:
        if not (0 <= pane < len(self._panes)):
            return
        self._current_pane = pane
        widget = self._panes[pane]
        if widget is self.tabs:
            sub = self.tabs.currentWidget()
            if sub is not None:
                sub.setFocus()
            else:
                self.tabs.setFocus()
        else:
            widget.setFocus()

    # ------------------------------------------------- data updates ---
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

    # ------------------------------------------------ embedded browser ---
    @property
    def in_browser(self) -> bool:
        return HAS_WEBENGINE and self.tabs.currentIndex() == BROWSER_TAB

    def open_in_browser(self, url: str) -> bool:
        if not HAS_WEBENGINE or self.browser is None:
            return False
        self._previous_pane = self._current_pane
        self.browser.setUrl(QUrl(url))
        self.tabs.setCurrentIndex(BROWSER_TAB)
        self.browser.setFocus()
        return True

    # ------------------------------------------------ tab switching ---
    def toggle_tab(self) -> None:
        if self.tabs.count() < 2:
            return
        if self.tabs.currentIndex() == BROWSER_TAB:
            self.show_article_tab()
        else:
            self.show_browser_tab()

    def show_article_tab(self) -> None:
        if self.tabs.count() < 2:
            return
        if self.tabs.currentIndex() == ARTICLE_TAB:
            return
        self.tabs.setCurrentIndex(ARTICLE_TAB)
        self.focus_pane(self._previous_pane)

    def show_browser_tab(self) -> None:
        if not HAS_WEBENGINE or self.tabs.count() < 2:
            return
        if self.tabs.currentIndex() == BROWSER_TAB:
            return
        self._previous_pane = self._current_pane
        self.tabs.setCurrentIndex(BROWSER_TAB)
        if self.browser is not None:
            self.browser.setFocus()
            
    def exit_browser(self) -> None:
        self.show_article_tab()

    # ----------------------------------------------------- scrolling ---
    def scroll_reader(self, delta: int) -> None:
        if self.in_browser and self.browser is not None:
            self.browser.page().runJavaScript(
                f"window.scrollBy(0, {delta * 60});"
            )
            return
        bar = self.reader.verticalScrollBar()
        step = self.reader.fontMetrics().lineSpacing()
        bar.setValue(bar.value() + delta * step)

    def scroll_reader_to(self, top: bool) -> None:
        if self.in_browser and self.browser is not None:
            js = (
                "window.scrollTo(0, 0);"
                if top
                else "window.scrollTo(0, document.body.scrollHeight);"
            )
            self.browser.page().runJavaScript(js)
            return
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
        timer.timeout.connect(lambda jid=job_id: self._fire(jid, callback))
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
