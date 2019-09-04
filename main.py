from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QMenuBar, QGridLayout, QApplication, QWidget, QPlainTextEdit
from PyQt5.QtWidgets import QFileDialog
import sys, os
import numpy as np
import pyqtgraph_copy.pyqtgraph as pg

from tree_model_and_nodes import FileTreeProxyModel, TreeModel, FileNode, DirectoryNode
from paired_graphics_view import PairedGraphicsView
from tree_widget import FileTreeElement

class MainWindow(QWidget):
    '''
    basicvally handles the combination of the the threeemenu bar and the paired view

    Most of the code here is for setting up the geometry of the gui and the
    menubar stuff
    '''
    def __init__(self):
        QWidget.__init__(self)
        layout = QGridLayout()
        self.setLayout(layout)

        # create menu
        self.build_menubar()
        layout.setMenuBar(self.menu_bar)

        # make horizontal splitter to hold the filetree view and plots
        splitter_h   = QtWidgets.QSplitter(parent=None)
        layout.addWidget(splitter_h, 0, 0)

        self.tree_element = FileTreeElement()
        splitter_h.addWidget(self.tree_element.widget)

        # the code here should be attached to a loading part when select a file
        fs=40
        colours= ['r', 'g', 'b']
        self.paired_graphics_view = PairedGraphicsView()
        for i in range(3):
            y = np.random.normal(size=3600*fs) + i*10
            x = np.linspace(0,3600,y.shape[0])
            pen = pg.mkPen(colours[i])
            self.paired_graphics_view.make_and_add_item(x=x,y=y, pen=pen)

        splitter_h.addWidget(self.paired_graphics_view.splitter)

        self.tree_element.model.plot_node_signal.connect(self.paired_graphics_view.update_scenes)

    def get_available_screen(self):
        app = QApplication.instance()
        screen = app.primaryScreen()
        print('Screen: %s' % screen.name())
        size = screen.size()
        print('Size: %d x %d' % (size.width(), size.height()))
        rect = screen.availableGeometry()
        print('Available: %d x %d' % (rect.width(), rect.height()))

    def load_h5_directory(self):
        print('0penening only folders with h5 files')
        selected_directory = self.select_directory()
        self.tree_element.set_rootnode_from_folder(selected_directory,'.h5')

    def load_liete_directory(self):
        print('Load new file types...')

    def save(self):
        print('save action triggered')

    def load_general(self):
        selected_directory = self.select_directory()
        print(selected_directory)
        self.tree_element.set_rootnode_from_folder(selected_directory)

    def select_directory(self, label_text='Select a directory'):
        dialog = QFileDialog()
        dialog.setWindowTitle(label_text)
        dialog.setFileMode(QFileDialog.DirectoryOnly)
        #home = os.path.expanduser("~") # this here we grabe the temp root
        #dialog.setDirectory(home)
        #i think default behaviour is better... only do this if a default folder
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.ShowDirsOnly, False);
        dialog.exec()
        return dialog.selectedFiles()[0]

    def build_menubar(self):
        self.menu_bar = QMenuBar()

        self.menu_file = self.menu_bar.addMenu("File")
        self.action_load_general    = self.menu_file.addAction("Temp load all files")
        self.action_load_h5    = self.menu_file.addAction("Load h5 directory")
        self.action_load_liete = self.menu_file.addAction("Load liete directory")
        self.action_save       = self.menu_file.addAction("Save")
        self.menu_file.addSeparator()
        self.action_quit       = self.menu_file.addAction("Quit")

        self.action_load_general.triggered.connect(self.load_general)
        self.action_load_h5.triggered.connect(self.load_h5_directory)
        self.action_load_liete.triggered.connect(self.load_liete_directory)
        self.action_save.triggered.connect(self.save)
        self.action_quit.triggered.connect(self.close)

        self.menu_help = self.menu_bar.addMenu("Help")

        #self.menubar.addMenu("Edit")
        #self.menubar.addMenu("View")


if __name__ == '__main__':

    app = QApplication(sys.argv)
    screen = MainWindow()
    screen.get_available_screen()
    screen.show()
    sys.exit(app.exec_())
