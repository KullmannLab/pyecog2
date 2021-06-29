import sys
import os
import numpy as np

from PySide2 import QtWidgets, QtCore#,# uic

import pyqtgraph_copy.pyqtgraph as pg


from pyecog2.paired_graphics_view import PairedGraphicsView
from pyecog2.tree_model_and_nodes import FileTreeProxyModel, TreeModel, FileNode, DirectoryNode

pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

# initially we also want to include the code that detects resolution

app = QtWidgets.QApplication(sys.argv)
screen = app.primaryScreen()
print('Screen: %s' % screen.name())
size = screen.size()
print('Size: %d x %d' % (size.width(), size.height()))
rect = screen.availableGeometry()
print('Available: %d x %d' % (rect.width(), rect.height()))

# and use the resioltuon!

# now clunkly combine in this script
target_folder = '/media/jonathan/DATA/seizure_data/gabrielle/All_DATA/'
root = os.walk(target_folder, topdown=True) #root, dirs,file
print(root)
root = DirectoryNode(target_folder)
name_to_node = {target_folder:root}
for directory, dirnames, filenames in os.walk(target_folder):
    node = name_to_node[directory]
    for sub_directory in dirnames:
        fullname = os.path.join(directory, sub_directory)
        child_node = DirectoryNode(sub_directory, parent=node)
        name_to_node[fullname] = child_node

    for filename in filenames:
        fullname = os.path.join(directory, filename)
        child_node = FileNode(filename, parent=node)
        name_to_node[fullname] = child_node

##################
# init build tree
splitter_h = QtWidgets.QSplitter(parent=None)

filterbox_widget = QtWidgets.QWidget()

filterbox_layout = QtWidgets.QHBoxLayout()
filterbox_label  = QtWidgets.QLabel("Filter file list:")
filterbox_label.setToolTip('Enter string to filter the file tree \nHoping this works \nprons\
\t not though? ')
filter_line_edit = QtWidgets.QLineEdit(parent=None)
filter_line_edit.setPlaceholderText('e.g. FROM:2018/05/14, TO:2018/07/14, ANNO:1')
filterbox_layout.addWidget(filterbox_label)
filterbox_layout.addWidget(filter_line_edit)
# can you put a tool tip here? hovering tells you whats possible?
# str matches, .xxx is a file? probs not useful, and FROM:2018/10/11 etc
filterbox_widget.setLayout(filterbox_layout)
tree_view = QtWidgets.QTreeView()
tree_view.setSortingEnabled(True) # relies on proxy model

tree_window = QtWidgets.QWidget()
tree_window.setGeometry(0,0, size.width()*0.25, size.height()*0.5)
tree_layout = QtWidgets.QVBoxLayout()

menu_bar = QtWidgets.QMenuBar();
file_menu = QtWidgets.QMenu("File")
menu_bar.addMenu(file_menu)
file_menu.addAction("Load Directory")
file_menu.addAction("Set Default Folder")
tree_layout.setMenuBar(menu_bar)

tree_layout.addWidget(filterbox_widget)
tree_layout.addWidget(tree_view)
tree_window.setLayout(tree_layout)
#tree_window.show()
splitter_h.addWidget(tree_window)

'''VIEW < ---- > PROXY MODEL <-----> MODEL <------> DATA'''
model = TreeModel(root,parent=None)
proxy_model = QtCore.QSortFilterProxyModel() # will have to subclass this...
proxy_model.setSourceModel(model)
proxy_model.setDynamicSortFilter(True)
proxy_model.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
# this has set filter role and display role. If dont set defualts to the display role
proxy_model.setSortRole(TreeModel.sortRole)
proxy_model.setFilterRole(TreeModel.filterRole)
proxy_model.setFilterKeyColumn(0) # diff col for filter role
# https://doc.qt.io/qt-5/qsortfilterproxymodel.html#sorting
# basically reimplement the lessThan and the data you get from each column?
# the data model seems a little shitty... complexity verses the datframe? hmm
# but basicall connext up the cols to to data?
#
tree_view.setModel(proxy_model)
filter_line_edit.textChanged.connect(proxy_model.setFilterRegExp)

#insert_index = model.index(0,0,QtCore.QModelIndex())
#model.insert_rows(3,5, parent=insert_index) # should fail loundly!
#model.remove_rows(0,5)
test_proxy = FileTreeProxyModel()

# build the graphics part
# this shoulw be a ffunction or class
splitter_v  = QtWidgets.QSplitter(parent=None)
splitter_h.addWidget(splitter_v)
splitter_v.resize(680, 400)
splitter_v.setOrientation(QtCore.Qt.Vertical)
sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                   QtWidgets.QSizePolicy.Expanding)
splitter_v.setSizePolicy(sizePolicy)
#splitter_v.show()
splitter_h.show()


# the code here should be attached to a loading part right
fs=40
colours= ['r', 'g', 'b']
paired_view = PairedGraphicsView(splitter_v)
for i in range(3):
    y = np.random.normal(size=3600*fs) + i*10
    x = np.linspace(0,3600,y.shape[0])
    pen = pg.mkPen(colours[i])
    paired_view.make_and_add_item(x=x,y=y, pen=pen)

sys.exit(app.exec_())
