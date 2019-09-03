from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QMenuBar, QGridLayout, QApplication, QWidget, QPlainTextEdit
import sys, os
import numpy as np
import pyqtgraph_copy.pyqtgraph as pg
from tree_model_and_nodes import FileTreeProxyModel, TreeModel, FileNode, DirectoryNode
from paired_graphics_view import PairedGraphicsView


#from tree_widget import FileTreeElement
# will move this maybe?

class FileTreeElement():
    '''
    Might need to rename class, but basically a class to represent the filetree
    browser part of the gui.

    Will not include the menu
    basically will be composed of the tree widget? which is a filterbox and label, plus tree view
    and tree moddel.


    '''
    def __init__(self):

        # initally construct filter elements
        filter_label  = QtWidgets.QLabel("Filter file list:")
        filter_label.setToolTip('Enter string to filter the file tree \nHoping this works \nprobs \\t not though? ')
        filter_line_edit = QtWidgets.QLineEdit(parent=None)
        filter_line_edit.setPlaceholderText('Disabled! e.g. FROM:2018/05/14, TO:2018/07/14, ANNO:1')
        filter_label.setToolTip('Not ready to use yet')
        filter_layout = QtWidgets.QHBoxLayout()
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(filter_line_edit)
        filter_widget = QtWidgets.QWidget()
        filter_widget.setLayout(filter_layout)

        # now the file tree view
        tree_view = QtWidgets.QTreeView()
        tree_view.setSortingEnabled(True) # relies on proxy model

        tree_layout = QtWidgets.QVBoxLayout()
        #tree_layout.addWidget(menu_bar, 0)
        tree_layout.addWidget(filter_widget)
        tree_layout.addWidget(tree_view)

        self.widget = QtWidgets.QWidget()
        self.widget.setLayout(tree_layout)
        #self.tree_layout = tree_layout

        # ok so gonna have to have a build data structure here....
        # will bneed a self
        root_folder = self.get_default_folder()
        self.root_node = self.make_rootnode_from_folder(root_folder)
        model = TreeModel(self.root_node, parent=None)
        tree_view.setModel(model)


    def make_rootnode_from_folder(self, root_folder):
        '''
        Currently you cannot click on them indivdually to get the channels... would be decent
        to double click etc

        # Todo - gonna have to change that right - such that they have subnodes?
        # maybe on the filenode itself...
        '''
        root = DirectoryNode(root_folder)
        name_to_node = {root_folder:root}
        for directory, dirnames, filenames in os.walk(root_folder):
            node = name_to_node[directory]
            for sub_directory in dirnames:
                fullname = os.path.join(directory, sub_directory)
                child_node = DirectoryNode(sub_directory, parent=node)
                name_to_node[fullname] = child_node
            for filename in filenames:
                fullname = os.path.join(directory, filename)
                child_node = FileNode(filename, parent=node)
                name_to_node[fullname] = child_node
        return root


    def get_default_folder(self):
        # normally should have the pickle file here
        folder = '/media/jonathan/DATA/seizure_data/gabrielle/All_DATA/'
        if os.path.exists(folder):
            return folder
        else:
            return os.getcwd()

class MainWindow(QWidget):
    '''
    basicvally handles the combination of the the threeemenu bar and the paired view
    '''
    def __init__(self):
        QWidget.__init__(self)
        layout = QGridLayout()
        self.setLayout(layout)

        # build menu seperately
        # create menu
        self.build_menubar()
        layout.setMenuBar(self.menubar)

        splitter_h   = QtWidgets.QSplitter(parent=None)
        layout.addWidget(splitter_h, 0, 0)

        tree_element = FileTreeElement()

        # the code here should be attached to a loading part right
        fs=40
        colours= ['r', 'g', 'b']
        splitter_v  = QtWidgets.QSplitter(parent=None)
        splitter_v.resize(680, 400)
        splitter_v.setOrientation(QtCore.Qt.Vertical)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                   QtWidgets.QSizePolicy.Expanding)
        splitter_v.setSizePolicy(sizePolicy)
        paired_view = PairedGraphicsView(splitter_v)
        for i in range(3):
            y = np.random.normal(size=3600*fs) + i*10
            x = np.linspace(0,3600,y.shape[0])
            pen = pg.mkPen(colours[i])
            paired_view.make_and_add_item(x=x,y=y, pen=pen)

        splitter_h.addWidget(tree_element.widget)
        splitter_h.addWidget(splitter_v)
        self.submenu_file.triggered["Open"].connect(self.open_menu_called)

    def open_menu_called(self):
        print('0pen')

    def build_menubar(self):
        self.menubar = QMenuBar()
        #layout.addWidget(menubar, 0, 0)
        # call this submenu
        self.submenu_file = self.menubar.addMenu("File")
        self.submenu_file.addAction("New")
        self.submenu_file.addAction("Open")
        self.submenu_file.addAction("Save")
        self.submenu_file.addSeparator()
        self.submenu_file.addAction("Quit")
        self.menubar.addMenu("Edit")
        self.menubar.addMenu("View")
        self.menubar.addMenu("Help")



app = QApplication(sys.argv)
screen = MainWindow()
screen.show()
sys.exit(app.exec_())
