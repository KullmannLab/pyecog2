from PyQt5 import QtGui, QtWidgets, QtCore

import sys
import os
import numpy as np
import pandas as pd
import pickle as p

from PyQt5 import QtGui, QtWidgets, QtCore#,# uic
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QRect, QTimer

import pyqtgraph_copy.pyqtgraph as pg

from paired_graphics_view import PairedGraphicsView
from tree_model_and_nodes import FileTreeProxyModel, TreeModel, FileNode, DirectoryNode


def build_menubar():
    pass

class FileTreeElement():
    '''
    Might need to rename class, but basically a class to represent the filetree
    browser part of the gui. It will include the menu bar
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

        #tree_view.setGeometry(0,0, size.width()*0.25, size.height()*0.5)

        tree_layout = QtWidgets.QVBoxLayout()
        #tree_layout.addWidget(menu_bar, 0)
        tree_layout.addWidget(filter_widget)
        tree_layout.addWidget(tree_view)

        self.tree_layout = tree_layout

        #self.main_widget = QtWidgets.QWidget()
        #self.main_widget.setGeometry(0,0, size.width()*0.25, size.height()*0.5)
        #self.main_widget.setLayout(tree_layout)
        #self.main_widget.menu_bar = menu_bar

        #elf.main_window = QtWidgets.QMainWindow()

        #self.main_window.setCentralWidget(self.main_widget)
        #self.main_window.setMenuBar(menu_bar)
        #menu_bar.show()


        # ok so gonna have to have a build data structure here....
        root_folder = self.get_default_folder()
        self.root_node = self.make_rootnode_from_folder(root_folder)
        model = TreeModel(self.root_node, parent=None)
        tree_view.setModel(model)

        pass

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

def build_filetree_widget():
    '''
    returns widget containing the filetree
    '''

    ### initally you should check if there is a default folder
    print('go')

def build_paired_graphics_view():
    pass

    #maybe this should be a class?

    #gwegwg

# will eventually move this
class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        'file_tree = FileTreeElement()
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

        menu_bar  = QtWidgets.QMenuBar();
        #menu_bar.setNativeMenuBar(False)
        file_menu = QtWidgets.QMenu("File")
        menu_bar.addMenu(file_menu)
        file_menu.addAction("Load Directory")
        file_menu.addAction("Set Default Folder")

        layout.addWidget(menu_bar, 0, 0)

if __name__ == '__main__':

    app = QtWidgets.QApplication(sys.argv)
    screen = app.primaryScreen()
    print('Screen: %s' % screen.name())
    size = screen.size()
    print('Size: %d x %d' % (size.width(), size.height()))
    rect = screen.availableGeometry()
    print('Available: %d x %d' % (rect.width(), rect.height()))


    #splitter_h
    window = MainWindow()
    window.show()
    #window.setGeometry(0,0, size.width()*0.25, size.height()*0.5)


    #main_window = QtWidgets.QMainWindow()

    #splitter_h = QtWidgets.QSplitter(parent=None)
    #splitter_h.addWidget(window)
    #splitter_h.show()

    sys.exit(app.exec_())
    print('closed')
