"""Entry point: builds Model, View, Controller and starts the PyQt6 main loop."""
import sys
from PyQt6.QtWidgets import QApplication

from controller import Controller
from model import Model
from view import View

def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  
    
    model = Model()
    view = View()
    controller = Controller(model, view)  # noqa: F841
    
    view.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
