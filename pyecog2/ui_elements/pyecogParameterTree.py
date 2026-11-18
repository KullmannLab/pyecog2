from PySide6 import QtGui, QtCore
from pyqtgraph.parametertree import ParameterTree
from pyqtgraph.parametertree.parameterTypes import GroupParameter, GroupParameterItem, registerParameterType

class PyecogParameterTree(ParameterTree):
    def __init__(self,*args,**kwargs):
        ParameterTree.__init__(self,*args,**kwargs)

class PyecogGroupParameterItem(GroupParameterItem):
    def __init__(self,*args,**kwargs):
        GroupParameterItem.__init__(self,*args,**kwargs)

    def updateDepth(self, depth):
        ## Change item's appearance based on its depth in the tree
        ## This allows highest-level groups to be displayed more prominently.
        if depth == 0:
            for c in [0,1]:
                self.setBackground(c, QtGui.QBrush(QtGui.QColor(35, 39, 41)))
                # self.setBackground(c, QtGui.QBrush(QtGui.QColor(0, 0, 0)))
                self.setForeground(c, QtGui.QBrush(QtGui.QColor(64, 192, 231)))
                font = self.font(c)
                font.setBold(True)
                font.setPointSize(font.pointSize()+1)
                self.setFont(c, font)
                self.setSizeHint(0, QtCore.QSize(0, 25))
        else:
            for c in [0,1]:
                self.setBackground(c, QtGui.QBrush(QtGui.QColor(35, 39, 41)))
                # self.setBackground(c, QtGui.QBrush(QtGui.QColor(0, 0, 0)))
                self.setForeground(c, QtGui.QBrush(QtGui.QColor(250, 250, 250)))
                # self.setForeground(c, QtGui.QBrush(QtGui.QColor(124, 124, 124)))
                font = self.font(c)
                font.setBold(True)
                #font.setPointSize(font.pointSize()+1)
                self.setFont(c, font)
                self.setSizeHint(0, QtCore.QSize(0, 20))

class PyecogGroupParameter(GroupParameter):
    itemClass = PyecogGroupParameterItem
    def __init__(self,*args,**kwargs):
        GroupParameter.__init__(self,*args,**kwargs)


registerParameterType('group', PyecogGroupParameter, override=True) # Override original pyqtgraph group parameter type