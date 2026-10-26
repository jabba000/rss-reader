  # MiniRSS
  
  **A keyboard-driven, three-pane RSS reader for the terminal generation — built with PyQt6.**

  ![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)
  ![PyQt6](https://img.shields.io/badge/PyQt6-6.5%2B-green?logo=qt&logoColor=white)
  ![feedparser](https://img.shields.io/badge/feedparser-6.0%2B-orange)
  ![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey)
  ![License](https://img.shields.io/badge/license-MIT-brightgreen)

  *Sources · Headlines · Article — all reachable without lifting your hands from `hjkl`.*
</div>

---

## 📑 Table of Contents
- [About the Project](#-about-the-project)
- [Key Features](#-key-features)
- [Tech Stack](#-tech-stack)
- [Getting Started](#-getting-started)
- [Usage](#-usage)
- [Architecture & Concurrency](#-architecture--concurrency)
- [Contributing](#-contributing)
- [License](#-license)

---

## 💡 About the Project
**MiniRSS** is a fast, minimalist desktop RSS reader designed for power users. Built on a strict **MVC** architecture, it provides a dependency-light reading experience with non-blocking background fetches and Vim-style navigation. 

An embedded Chromium browser allows you to read full articles directly within the app, eliminating context switching. MiniRSS relies entirely on a simple, easily editable JSON file for configuration—no complex databases required.

---

## 🚀 Key Features
* **Vim-Style Navigation**: `h`/`l` to move focus between panes, `j`/`k` to move selection. `g` / `G` jumps to the top/bottom.
* **Embedded Browser**: Press `o` on any headline to open the full article inside MiniRSS; `Esc` returns to the reader.
* **Asynchronous Fetching**: Debounced (200 ms) threaded fetches ensure the UI remains fully responsive.
* **Feed Management**: Add (`a`), delete (`d`), or refresh (`r`) feeds on the fly. URLs are auto-normalized.
* **Atomic Persistence**: Your data is saved atomically to `sources.json`, preventing corruption during crashes.
* **Sensible Defaults**: Out-of-the-box dark theme and an informative status bar.

---

## 🛠 Tech Stack
* **Python 3.10+**: Core language.
* **PyQt6 (6.5+)**: View layer and GUI rendering.
* **feedparser (6.0+)**: RSS/Atom feed parsing.
* **PyQt6-WebEngine**: Embedded Chromium browser tab.

---

## 💻 Getting Started

### Prerequisites
Ensure you have **Python 3.10+** and a working Qt platform plugin (X11, Wayland, Cocoa, or Windows) installed.

### Installation
Clone the repository and set up a virtual environment:

```bash
git clone [https://github.com/](https://github.com/)<your-username>/minirss.git
cd minirss

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # On Windows use: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py

```

> **Fallback Behavior**: If `PyQt6-WebEngine` is unavailable (e.g., inside a Flatpak sandbox), MiniRSS gracefully falls back to opening links in your default system browser.

---

## 🕹 Usage

Control the entire application using the following keybindings:

| Key | Action |
| --- | --- |
| `j` / `↓` | Move down |
| `k` / `↑` | Move up |
| `h` / `←` | Focus the pane to the left |
| `l` / `→` | Focus the pane to the right |
| `g` / `G` | Jump to top / bottom |
| `a` | Add a feed |
| `d` | Delete the selected feed |
| `r` | Refresh the current feed |
| `o` | Open the selected article in the embedded browser |
| `Esc` | Leave the browser and return to the reader |
| `q` | Quit |

---

## 🏗 Architecture & Concurrency

MiniRSS enforces a strict boundary between application layers:

* **Model (`model.py`)**: Handles `sources.json` persistence and network fetching. Contains zero Qt imports and is fully testable headless.
* **View (`view.py`)**: Manages Qt widgets and emits raw key/selection events. Unaware of feeds or data processing.
* **Controller (`controller.py`)**: Owns all policy, including debounce timers, background threads, and focus rules.

**Concurrency Model**: Network I/O runs on `threading.Thread(daemon=True)` workers. Results return through a `queue.Queue` drained by a `QTimer` every 100 ms, avoiding cross-thread signal issues.

---

## 🤝 Contributing

Bug reports and pull requests are welcome.

**Development Setup:**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

```

> **Important**: Keep the MVC boundary intact. The Model must not import PyQt6, the View must not import the Model, and the Controller must not import `feedparser` directly.

---

## 📄 License

This project is licensed under the MIT License — see the `LICENSE` file for details.

*Built for people who still believe in RSS.* ⭐ If MiniRSS saved you a browser tab, give the repo a star.


