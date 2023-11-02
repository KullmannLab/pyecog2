import sys
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

class Window(QMainWindow):
    def __init__(self, parent=None):
        super(Window, self).__init__(parent)

        self.centralWindow_ = QFrame() 
        self.setCentralWidget(None)

        self.CreateWidgets()
        self.readSettings()

    def CreateWidgets(self):        
        self.toolbar = self.addToolBar('Toolbar')
        self.toolbar.setMovable(False)    

        exitA = QAction(QIcon('Images/gj.png'), 'Exit', self)
        exitA.setShortcut('Ctrl+Q')
        exitA.setStatusTip('Exit application')
        exitA.triggered.connect(self.close)   
        self.toolbar.addAction(exitA)

        openDock_ = QAction(QIcon('Images/gj.png'), 'Open', self)
        openDock_.setShortcut('Ctrl+E')
        openDock_.setStatusTip('Open Dock')
        openDock_.triggered.connect(self.OpenDockWindow)   
        self.toolbar.addAction(openDock_)

        self.setWindowTitle("We do not sow")
        self.showFullScreen()

        self.firstDock_ = Dock(self, 'First')
        self.firstDock_.setObjectName('First')
        self.addDockWidget(Qt.LeftDockWidgetArea, self.firstDock_)     

        self.secondDock_ = Dock(self, 'Second')
        self.firstDock_.setObjectName('Second')
        self.addDockWidget(Qt.LeftDockWidgetArea, self.secondDock_)

        self.thirdDock_ = Dock(self, 'Third')
        self.thirdDock_.setObjectName('Third')
        self.splitDockWidget(self.firstDock_, self.thirdDock_, Qt.Horizontal)

        self.fDock_ = Dock(self, 'Fourth')
        self.fDock_.setObjectName('Fourth')
        self.splitDockWidget(self.firstDock_, self.fDock_, Qt.Horizontal)

        self.fiDock_ = Dock(self, 'Fifth')
        self.fiDock_.setObjectName('Fifth')
        self.splitDockWidget(self.firstDock_, self.fiDock_, Qt.Vertical)

        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)

    def OpenDockWindow(self):
        dock_ = Dock((self.frameGeometry().width() / 2), self.firstDock_)

        self.addDockWidget(Qt.RightDockWidgetArea, dock_)
        self.tabifyDockWidget(self.secondDock_, dock_)

    def closeEvent(self, event):
        print('closing')
        settings = QSettings()
        settings.setValue('geometry',self.saveGeometry())
        settings.setValue('windowState',self.saveState())
        super(Window, self).closeEvent(event)

    def readSettings(self):
        settings = QSettings()
        self.restoreGeometry(settings.value("geometry"))
        self.restoreState(settings.value("windowState"))

class Dock(QDockWidget):
    def __init__(self, title, parent=None):
        super(Dock, self).__init__(parent)

        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea | Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable )

def main():
    app = QApplication(sys.argv)
    app.setOrganizationDomain('ltd')
    app.setOrganizationName('Alg')
    w = Window()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()