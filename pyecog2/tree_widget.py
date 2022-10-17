from PySide2 import QtGui, QtWidgets, QtCore

import sys
import os
import numpy as np
import pandas as pd
import pickle as p

from PySide2 import QtGui, QtWidgets, QtCore#,# uic
from PySide2.QtCore import QThread, Signal, Qt, QRect, QTimer

# import pyqtgraph_copy.pyqtgraph as pg
import pyqtgraph as pg

from pyecog2.tree_model_and_nodes import FileTreeProxyModel, TreeModel
from pyecog2.tree_model_and_nodes import FileNode, DirectoryNode, ChannelNode, HDF5FileNode, LieteNode, ProjectNode,BuildingNode

import logging
logger = logging.getLogger(__name__)

class FileTreeView(QtWidgets.QTreeView):

    def __init__(self, parent=None):
        #super(FileTreeView, self).__init__(self)
        QtWidgets.QTreeView.__init__(self)
        # self.setSortingEnabled(True) # relies on proxy model

    # def mouseDoubleClickEvent(self, event):
    #     print('double click event')
    #     print(event)
    #     node = self.currentIndex().internalPointer()

    def selectionChanged(self, *args):
        logger.info(f'selection changed {args}')
        super(FileTreeView, self).selectionChanged(*args)
        index = self.currentIndex()
        self.model().data(index, TreeModel.prepare_for_plot_role)

    def setSelection(self, *args):
        logger.info(f'setSelection {args}')
        super(FileTreeView, self).setSelection(*args)

class FileTreeElement():
    '''
    To use when in directory explorer mode

    Might need to rename class, but basically a class to represent the filetree
    browser part of the gui.

    Will not include the menu
    basically will be composed of the tree widget? which is a filterbox and label, plus tree view
    and tree moddel.

    ML: I will expand this class to be able to represent projects as well.


    '''
    def __init__(self, parent=None):

        self.mainwindow_parent = parent # the window holding both this file tree element and the
        # paired graphcis view

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
        self.tree_view = FileTreeView()
        self.model = TreeModel(None, parent=None)

        tree_layout = QtWidgets.QVBoxLayout()
        #tree_layout.addWidget(menu_bar, 0)
        # tree_layout.addWidget(filter_widget)
        tree_layout.addWidget(self.tree_view)

        self.widget = QtWidgets.QWidget()
        self.widget.setLayout(tree_layout)
        #self.tree_layout = tree_layout

    def connect_model_to_parent_paired_graph(self):
        # now it feels we are getting into pretty poor coding
        if self.mainwindow_parent is not None:
            self.model.plot_node_signal.connect(
                # self.mainwindow_parent.paired_graphics_view.overview_plot.setRange)
                self.mainwindow_parent.paired_graphics_view.set_scenes_plot_channel_data)
                # ML: I don't like this, probably best is to have the parent have an update_graphics() method and maybe
                # even an object containng all the info necessary to be comunicated between widgets like filenames,
                # metadata, cursor positions etc

    #def set_live_rootnode(self, filename):
    #    self.root_node = FileNode(filename)
    #    self.model = TreeModel(self.None, parent=None)
        #self.tree_view.setModel(self.model)
        #self.connect_model_to_parent_paired_graph()


    def set_rootnode_from_folder(self, root_folder, filetype_restriction=None):
        '''resets the tree self.model'''
        if filetype_restriction is None:
            self.root_node = self.make_rootnode_from_folder(root_folder)
        elif filetype_restriction.endswith('h5'):
            self.root_node = self.make_h5files_rootnode_from_folder(root_folder)

        self.model = TreeModel(self.root_node, parent=None)
        self.tree_view.setModel(self.model)
        self.connect_model_to_parent_paired_graph()

    def make_h5files_rootnode_from_folder(self, root_folder):
        '''
        Again we need a recursion limit here

        These builders are also a bit obtuse
        '''
        root = DirectoryNode(root_folder)
        name_to_node = {root_folder:root} # create branch node for root directory
        for directory, dirnames, filenames in os.walk(root_folder):
            node = name_to_node[directory] # get branch node for directory
            for sub_directory in dirnames:
                fullname = os.path.join(directory, sub_directory)
                child_node = DirectoryNode(sub_directory, parent=node)
                name_to_node[fullname] = child_node  # create branch node for sub-directory
            for filename in filenames:
                if not filename.endswith('.h5'):
                    continue
                fullname = os.path.join(directory, filename)
                child_node = HDF5FileNode(filename, parent=node)
                try:
                    tids = eval('['+fullname.split('[')[1].split(']')[0]+']')
                    for tid in tids:
                        channel_node = ChannelNode(str(tid), parent=child_node)
                except IndexError:
                    logger.error('H5 file with no children detected: {fullname}')
                name_to_node[fullname] = child_node # this seems un necessary - I think this is only needed for directory branch nodes
        return root

    def make_rootnode_from_folder(self, root_folder):
        '''
        THERE SHOULD BE A RECURSION LIMIT!!!
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
                if filename.endswith('.leite'):
                    child_node = LieteNode(filename, parent=node)
                elif filename.endswith('.h5'):
                    child_node = HDF5FileNode(filename, parent=node)
                    try:
                        tids = eval('['+fullname.split('[')[1].split(']')[0]+']')
                        for tid in tids:
                            channel_node = ChannelNode(str(tid), parent=child_node)
                    except IndexError:
                        logger.error('H5 file with no children detected: {fullname}')
                else:
                    child_node = FileNode(filename, parent=node)
                name_to_node[fullname] = child_node
        return root

    def set_rootnode_from_project(self, project):
        '''resets the tree self.model'''
        self.root_node = DirectoryNode('')
        self.model = TreeModel(self.root_node, parent=None)
        self.tree_view.setModel(self.model)
        # BuildingNode(parent = self.root_node)
        # self.widget.show()
        ProjectNode(project,parent=self.root_node)
        self.connect_model_to_parent_paired_graph()
        self.tree_view.expandToDepth(0)

    def get_default_folder(self):
        # normally should have the pickle file here
        folder = '/home/'
        if os.path.exists(folder):
            return folder
        else:
            return os.getcwd()




if __name__ == '__main__': # OBSOLETE???

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
