import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QProgressBar
from PySide6.QtCore import Qt


class Example(QMainWindow):

    def __init__(self):
        super().__init__()

        self.pbar = QProgressBar(self)
        self.pbar.setGeometry(30, 40, 200, 25)
        self.pbar.setValue(50)

        self.setWindowTitle("QT Progressbar Example")
        self.setGeometry(32, 32, 320, 200)
        self.show()

        self.timer = QTimer()
        self.timer.timeout.connect(self.handleTimer)
        self.timer.start(1000)

    def handleTimer(self):
        value = self.pbar.value()
        if value < 100:
            value = value + 1
            self.pbar.setValue(value)
        else:
            self.timer.stop()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = Example()
    sys.exit(app.exec())