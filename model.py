"""Model layer: sources.json persistence and RSS fetching/parsing.

Contains no GUI code and knows nothing about the View or the Controller.
"""
from __future__ import annotations

import calendar
import json
import os
import re
import socket
import sys
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import feedparser

APP_NAME = "minirss"
USER_AGENT = "MiniRSS/1.0"

# feedparser has no timeout option; urllib honours the global socket timeout.
socket.setdefaulttimeout(15)


# --------------------------------------------------------------- storage ---
def _app_dir() -> Path:
    """Folder of the .exe / ELF when frozen by PyInstaller, else of this file.

    Do NOT use sys._MEIPASS here: in --onefile mode it is a temp dir that is
    deleted on exit, so sources.json would be lost.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def default_storage_path() -> Path:
    path = _app_dir() / "sources.json"
    if os.access(path if path.exists() else path.parent, os.W_OK):
        return path
    # Install dir is read-only (e.g. Program Files, /usr/bin): use the home dir.
    fallback = Path.home() / f".{APP_NAME}"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback / "sources.json"


# ------------------------------------------------------------- data types ---
@dataclass
class Source:
    url: str
    title: str = ""

    @property
    def label(self) -> str:
        return self.title or re.sub(r"^https?://", "", self.url)


@dataclass
class Entry:
    title: str
    link: str
    published: str
    body: str  # plain text


@dataclass
class Feed:
    title: str
    entries: list[Entry] = field(default_factory=list)


class FeedError(Exception):
    pass


# ------------------------------------------------------- HTML -> plain text ---
_BLOCK = frozenset(
    "p div br hr li tr h1 h2 h3 h4 h5 h6 blockquote pre ul ol table "
    "section article header footer figure".split()
)
_VOID = frozenset(("br", "hr"))
_SKIP = frozenset(("script", "style"))


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip += 1
        elif tag == "li":
            self._parts.append("\n• ")
        elif tag in _BLOCK:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK and tag not in _VOID:
            self._parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(re.sub(r"\s+", " ", data))

    def text(self) -> str:
        text = "".join(self._parts)
        text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def html_to_text(html: str) -> str:
    if not html:
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
        return parser.text()
    except Exception:  # malformed markup: crude fallback
        return re.sub(r"<[^>]+>", "", html).strip()


def _single_line(text: str) -> str:
    return re.sub(r"\s+", " ", html_to_text(text)).strip()


def _format_date(raw) -> str:
    parsed = raw.get("published_parsed") or raw.get("updated_parsed")
    if parsed:
        try:
            return time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(calendar.timegm(parsed))
            )
        except (OverflowError, ValueError, OSError):
            pass
    return raw.get("published") or raw.get("updated") or ""


def _parse_entry(raw) -> Entry:
    title = _single_line(raw.get("title", "")) or "(untitled)"
    content = raw.get("content")
    html = content[0].get("value", "") if content else ""
    if not html:
        html = raw.get("summary") or raw.get("description") or ""
    return Entry(
        title=title,
        link=raw.get("link", ""),
        published=_format_date(raw),
        body=html_to_text(html) or "(no content)",
    )


def normalize_url(raw: str) -> str:
    url = raw.strip()
    if not url:
        raise ValueError("Empty URL")
    if url.lower().startswith("feed://"):
        url = "http://" + url[7:]
    if "://" not in url:
        url = "https://" + url
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"Invalid URL: {raw.strip()}")
    return url


# ------------------------------------------------------------------ model ---
class Model:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else default_storage_path()
        self.sources: list[Source] = []
        self.save_error: str | None = None
        self._cache: dict[str, Feed] = {}
        self.load()

    # -- persistence ------------------------------------------------------
    def load(self) -> None:
        self.sources = []
        if not self.path.exists():
            self.save()
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            try:  # keep the broken file instead of silently overwriting it
                os.replace(self.path, self.path.with_name(self.path.name + ".bak"))
            except OSError:
                pass
            return
        items = data.get("sources", []) if isinstance(data, dict) else data
        if not isinstance(items, list):
            return
        for item in items:
            if isinstance(item, str):
                url, title = item, ""
            elif isinstance(item, dict) and isinstance(item.get("url"), str):
                url, title = item["url"], str(item.get("title") or "")
            else:
                continue
            if url.strip():
                self.sources.append(Source(url.strip(), title))

    def save(self) -> None:
        """Atomic write. Never raises; the outcome is kept in `save_error`."""
        payload = {"sources": [{"url": s.url, "title": s.title} for s in self.sources]}
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            tmp.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            os.replace(tmp, self.path)
            self.save_error = None
        except OSError as exc:
            self.save_error = str(exc)

    # -- sources ----------------------------------------------------------
    def add_source(self, raw_url: str) -> int:
        """Add a feed and return its index (existing index if duplicate).

        Raises ValueError for an invalid URL.
        """
        url = normalize_url(raw_url)
        for i, src in enumerate(self.sources):
            if src.url.lower() == url.lower():
                return i
        self.sources.append(Source(url))
        self.save()
        return len(self.sources) - 1

    def remove_source(self, index: int) -> Source:
        src = self.sources.pop(index)
        self._cache.pop(src.url, None)
        self.save()
        return src

    def _find(self, url: str) -> Source | None:
        return next((s for s in self.sources if s.url == url), None)

    # -- feeds ------------------------------------------------------------
    def cached_feed(self, url: str) -> Feed | None:
        return self._cache.get(url)

    def store_feed(self, url: str, feed: Feed) -> None:
        src = self._find(url)
        if src is None:  # source was deleted while the download was running
            return
        self._cache[url] = feed
        if feed.title and feed.title != src.title:
            src.title = feed.title
            self.save()

    @staticmethod
    def fetch_feed(url: str) -> Feed:
        """Blocking download + parse. Pure function: safe to call from a thread."""
        parsed = feedparser.parse(url, agent=USER_AGENT)
        status = parsed.get("status")
        if isinstance(status, int) and status >= 400:
            raise FeedError(f"HTTP {status}")
        if not parsed.entries and parsed.get("bozo"):
            exc = parsed.get("bozo_exception")
            raise FeedError(str(exc) if exc else "Not a valid feed")
        return Feed(
            title=_single_line(parsed.feed.get("title", "")),
            entries=[_parse_entry(e) for e in parsed.entries],
        )
