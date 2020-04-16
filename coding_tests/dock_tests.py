from PyQt5.QtWidgets import QMainWindow, QApplication, QDockWidget, QListWidget, QTextEdit
import sys
from PyQt5.QtGui import QIcon
from PyQt5 import QtGui
from PyQt5.QtCore import Qt, QSettings, QByteArray
 
 
 
 
 
class DockDialog(QMainWindow):
    def __init__(self):
        super().__init__()
        self.title = "PyQt5 StackedWidget"
        self.top = 200
        self.left = 500
        self.width = 400
        self.height = 300
        self.setWindowIcon(QtGui.QIcon("icon.png"))
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.createDockWidget()
        self.settings = QSettings("UCL","WPT")
        self.settings.beginGroup("MainWindow")
        self.restoreGeometry(self.settings.value("windowGeometry", type=QByteArray))
        self.restoreState(self.settings.value("windowState", type=QByteArray))
        self.show()
 
    def createDockWidget(self):
        menubar = self.menuBar()
        file = menubar.addMenu("File")
        file.addAction("New")
        file.addAction("Save")
        file.addAction("Close")
        self.dock = QDockWidget("Dockable", self)
        self.listWiget = QListWidget()
        list = ["Python", "C++", "Java", "C#"]
        self.listWiget.addItems(list)
        self.dock.setWidget(self.listWiget)
        self.dock.setFloating(False)
        self.dock.setObjectName("DockableList")
        self.setCentralWidget(QTextEdit())
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)

    def closeEvent(self, event):
        print('closing')
        settings = QSettings("UCL","WPT")
        settings.beginGroup("MainWindow")
        windowGeometry = self.saveGeometry()
        settings.setValue("windowGeometry", windowGeometry)
        windowState = self.saveState()
        settings.setValue("windowState", windowState)
        settings.endGroup()
        self.saveState()
 
App = QApplication(sys.argv)
window = DockDialog()
sys.exit(App.exec())

#
# # method
# def saveAppState(self):
#     settings = QtCore.QSettings("Friture", "Friture")
#
#     settings.beginGroup("Docks")
#     self.dockmanager.saveState(settings)
#     settings.endGroup()
#
#     settings.beginGroup("CentralWidget")
#     self.centralwidget.saveState(settings)
#     settings.endGroup()
#
#     settings.beginGroup("MainWindow")
#     windowGeometry = self.saveGeometry()
#     settings.setValue("windowGeometry", windowGeometry)
#     windowState = self.saveState()
#     settings.setValue("windowState", windowState)
#     settings.endGroup()
#
#     settings.beginGroup("AudioBackend")
#     self.settings_dialog.saveState(settings)
#     settings.endGroup()
#
#
# # method
# def restoreAppState(self):
#     settings = QtCore.QSettings("Friture", "Friture")
#
#     settings.beginGroup("Docks")
#     self.dockmanager.restoreState(settings)
#     settings.endGroup()
#
#     settings.beginGroup("CentralWidget")
#     self.centralwidget.restoreState(settings)
#     settings.endGroup()
#
#     settings.beginGroup("MainWindow")
#     self.restoreGeometry(settings.value("windowGeometry", type=QtCore.QByteArray))
#     self.restoreState(settings.value("windowState", type=QtCore.QByteArray))
#     settings.endGroup()
#
#     settings.beginGroup("AudioBackend")
#     self.settings_dialog.restoreState(settings)
#     settings.endGroup()


