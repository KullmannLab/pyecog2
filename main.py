from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QMenuBar, QGridLayout, QApplication, QWidget, QPlainTextEdit
from PyQt5.QtWidgets import QFileDialog
import sys, os
import numpy as np
import pyqtgraph_copy.pyqtgraph as pg

from tree_model_and_nodes import FileTreeProxyModel, TreeModel, FileNode, DirectoryNode
from paired_graphics_view import PairedGraphicsView
from tree_widget import FileTreeElement
#
class MainWindow(QWidget):
    '''
    basicvally handles the combination of the the threeemenu bar and the paired view

    Most of the code here is for setting up the geometry of the gui and the
    menubar stuff
    '''
    def __init__(self):
        super().__init__()
        layout = QGridLayout()
        self.setLayout(layout)

        # create elements of the main window
        self.build_menubar()
        self.paired_graphics_view = PairedGraphicsView()
        self.tree_element = FileTreeElement(parent=self)
        # note we pass in the

        # make horizontal splitter to hold the filetree view and plots
        splitter_h   = QtWidgets.QSplitter(parent=None)
        splitter_h.addWidget(self.tree_element.widget)
        splitter_h.addWidget(self.paired_graphics_view.splitter)

        layout.setMenuBar(self.menu_bar)
        layout.addWidget(splitter_h, 0, 0)

        ########################################################
        # Below here we have code for debugging and development

        #root_folder = self.tree_element.get_default_folder()
        #folder = '/media/jonathan/DATA/seizure_data/gabrielle/All_DATA/EEG DATA CRISPRa Kcna1 2018/4_CRISP Oct-Nov 2018/CRISPRa_h5s BASELINE'
        #folder = '/media/jonathan/DATA/seizure_data/gabrielle/All_DATA/EEG DATA CRISPRa Kcna1 2018/4_CRISP Oct-Nov 2018'

        #self.tree_element.set_rootnode_from_folder(folder, filetype_restriction = '.h5')

        #self.tree_element.set_rootnode_from_folder(os.getcwd())
        #testing automatic selection
        #self.tree_element.tree_view.setRootIndex()
        #index = self.tree_element.tree_view.currentIndex()
        #index = self.tree_element.model.createIndex(0,0)
        #self.tree_element.tree_view.setTreePosition(0)
        #index = QtCore.QModelIndex()
        #self.tree_element.tree_view.setCurrentIndex(index)

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
        self.tree_element.set_rootnode_from_folder(selected_directory)

    def select_directory(self, label_text='Select a directory'):
        '''
        Method launches a dialog allow user to select a directory
        '''
        dialog = QFileDialog()
        dialog.setWindowTitle(label_text)
        dialog.setFileMode(QFileDialog.DirectoryOnly)
        # we might want to set home directory using settings
        # for now rely on default behaviour
        '''
        home = os.path.expanduser("~") # default, if no settings available
        dialog.setDirectory(home)
        '''
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.ShowDirsOnly, False);
        dialog.exec()
        return dialog.selectedFiles()[0]

    def reload_plot(self):
        #print('reload')
        index = self.tree_element.tree_view.currentIndex()
        self.tree_element.model.data(index, TreeModel.prepare_for_plot_role)
        full_xrange = self.paired_graphics_view.overview_plot.vb.viewRange()[0][1]
        #print(full_xrange)
        xmin,xmax = self.paired_graphics_view.insetview_plot.vb.viewRange()[0]
        x_range=xmax-xmin
        if full_xrange > x_range:
            #print('called set xrange')
            self.paired_graphics_view.insetview_plot.vb.setXRange(full_xrange-x_range,full_xrange, padding=0)


    def load_live_recording(self):
        '''
        This should just change the graphics view/ file node to keep
        reloading?
        '''
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.reload_plot)
        if self.actionLiveUpdate.isChecked():
            self.timer.start(100)



    def build_menubar(self):
        self.menu_bar = QMenuBar()

        self.menu_file = self.menu_bar.addMenu("File")
        self.action_load_general    = self.menu_file.addAction("(Tempory) Load directory")
        self.action_load_h5    = self.menu_file.addAction("Load h5 directory")
        self.action_load_liete = self.menu_file.addAction("Load leite directory")
        self.action_save       = self.menu_file.addAction("Save")
        self.menu_file.addSeparator()
        self.actionLiveUpdate  = self.menu_file.addAction("Live Recording")
        self.actionLiveUpdate.setCheckable(True)
        self.actionLiveUpdate.toggled.connect(self.load_live_recording)
        self.actionLiveUpdate.setChecked(False)
        #self.live_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_L), self)
        #self.live_shortcut.connect()
        self.actionLiveUpdate.setShortcut('Ctrl+L')

        self.menu_file.addSeparator()
        self.action_quit       = self.menu_file.addAction("Quit")

        self.action_load_general.triggered.connect(self.load_general)
        self.action_load_h5.triggered.connect(self.load_h5_directory)
        self.action_load_liete.triggered.connect(self.load_liete_directory)
        self.action_save.triggered.connect(self.save)
        self.action_quit.triggered.connect(self.close)
        self.actionLiveUpdate.triggered.connect(self.load_live_recording)

        self.menu_help = self.menu_bar.addMenu("Help")
        self.menu_bar.setNativeMenuBar(False)

        #self.menubar.addMenu("Edit")
        #self.menubar.addMenu("View")


if __name__ == '__main__':

    app = QApplication(sys.argv)
    screen = MainWindow()
    screen.get_available_screen()
    screen.show()
    sys.exit(app.exec_())
