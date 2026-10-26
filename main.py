"""Entry point: builds Model, View, Controller and starts the Tk main loop."""
import sys
import tkinter as tk

from controller import Controller
from model import Model
from view import View


def _enable_hidpi() -> None:
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def main() -> None:
    _enable_hidpi()
    root = tk.Tk()
    model = Model()
    view = View(root)
    controller = Controller(model, view)  # noqa: F841 (kept alive by callbacks)
    root.mainloop()


if __name__ == "__main__":
    main()
