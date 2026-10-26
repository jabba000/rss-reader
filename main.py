"""Entry point: builds Model, View, Controller and starts the PyQt6 main loop."""
import os
import signal
import sys


def _configure_webengine() -> None:
    """Silence Chromium's attempts to use the host's Chrome profile, NVIDIA
    VA-API, and Flatpak-namespaced paths before QApplication is created.

    QtWebEngine reads these environment variables once at import time.
    """
    flags = [
        "--disable-gpu",
        "--disable-gpu-compositing",
        "--disable-software-rasterizer",
        "--disable-features=VaapiVideoDecoder,WebRtcUsePipeWire",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-breakpad",
        "--log-level=3",
    ]
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(flags)

    # Isolate Chromium's profile from any host Chrome / Flatpak installations.
    cache_root = os.path.join(
        os.path.expanduser("~"), ".cache", "minirss", "webengine"
    )
    os.makedirs(cache_root, exist_ok=True)
    os.environ["XDG_CONFIG_HOME"] = os.path.join(cache_root, "config")
    os.environ["XDG_CACHE_HOME"] = os.path.join(cache_root, "cache")
    os.environ["XDG_DATA_HOME"] = os.path.join(cache_root, "data")
    for sub in ("config", "cache", "data"):
        os.makedirs(os.path.join(cache_root, sub), exist_ok=True)

    # Belt-and-braces: QtWebEngine's own sandbox toggle.
    os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"

    # Silence the "Read channel unstable from CHROME_VERSION_EXTRA" warning.
    os.environ.pop("CHROME_VERSION_EXTRA", None)

    # Force Qt Quick into software mode (NVIDIA + QtWebEngine = pain otherwise).
    os.environ["QT_QUICK_BACKEND"] = "software"


def main() -> None:
    # Let Ctrl-C terminate the process instead of unwinding through a
    # QTimer slot inside Qt's event loop.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    _configure_webengine()

    # Import only after the environment is ready: importing QtWebEngine
    # snapshots the variables above.
    from PyQt6.QtWidgets import QApplication
    from controller import Controller
    from model import Model
    from view import View

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    model = Model()
    view = View()
    controller = Controller(model, view)  # noqa: F841

    view.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
