import sys
from PySide6 import QtCore
from PySide6.QtWidgets import QDialog, QWidget, QApplication, QPushButton, QTreeView, QHBoxLayout, QVBoxLayout, QAbstractItemView
from PySide6.QtGui import QStandardItem,QStandardItemModel
import sys
import copy
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QSettings, QByteArray

import json
import glob
from collections import OrderedDict
fname = glob.glob('../../Notebooks/*meta')[0]
with open(fname,'r') as metafile:
    meta_data = OrderedDict(json.load(metafile))


class TestDialog(QDialog):
    def __init__(self, data):

        super(TestDialog, self).__init__()

        self.data = copy.deepcopy(data)

        # Layout
        btOk = QPushButton("OK")
        btCancel = QPushButton("Cancel")
        self.tree = QTreeView()
        hbox = QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(btOk)
        hbox.addWidget(btCancel)
        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addWidget(self.tree)
        self.setLayout(vbox)
        self.setGeometry(300, 300, 600, 400)

        # Button signals
        btCancel.clicked.connect(self.reject)
        btOk.clicked.connect(self.accept)

        # Tree view
        self.tree.setModel(QStandardItemModel())
        self.tree.setAlternatingRowColors(True)
        self.tree.setSortingEnabled(True)
        self.tree.setHeaderHidden(False)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectItems)

        self.tree.model().setHorizontalHeaderLabels(['Parameter', 'Value'])

        for x in self.data:
            if not self.data[x]:
                continue
            parent = QStandardItem(x)
            parent.setFlags(QtCore.Qt.NoItemFlags)
            for y in self.data[x]:
                value = self.data[x][y]
                child0 = QStandardItem(y)
                child0.setFlags(QtCore.Qt.NoItemFlags |
                                QtCore.Qt.ItemIsEnabled)
                child1 = QStandardItem(repr(value))
                child1.setFlags(QtCore.Qt.ItemIsEnabled |
                                QtCore.Qt.ItemIsEditable |
                                ~ QtCore.Qt.ItemIsSelectable)
                parent.appendRow([child0, child1])
            self.tree.model().appendRow(parent)

        self.tree.expandAll()
        self.tree.model().itemChanged.connect(self.handleItemChanged)

    def get_data(self):
        return self.data

    def handleItemChanged(self, item):
        parent = self.data[item.parent().text()]
        key = item.parent().child(item.row(), 0).text()
        parent[key] = eval(item.text())


class Example(QWidget):

    def __init__(self):

        super(Example, self).__init__()

        btn = QPushButton('Button', self)
        btn.resize(btn.sizeHint())
        btn.clicked.connect(self.show_dialog)

        # A set example with an integer and a string parameters
        # self.data['example1'] = {}
        # self.data['example1']['int'] = 14
        # self.data['example1']['str'] = 'asdf'
        # A set example with a float and other non-conventional type
        # self.data['example2'] = {}
        # self.data['example2']['float'] = 1.2
        # self.data['example2']['other'] = Other(4, 8)

        # self.data = meta_data

    def show_dialog(self):
        meta_data['test_dict'] = {'test': 0}
        self.data = {}
        # This example will be hiddmeta_dataen (has no parameter-value pair)
        self.data['example0'] = meta_data  # {}

        dialog = TestDialog(self.data)
        accepted = dialog.exec()
        if not accepted:
            return
        self.data = copy.deepcopy(dialog.get_data())
        print(self.data)


if __name__ == '__main__':

    app = QApplication(sys.argv)
    ex = Example()
    ex.show()
    sys.exit(app.exec())