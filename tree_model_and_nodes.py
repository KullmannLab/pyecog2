import sys, os
from PyQt5 import QtGui, QtCore, QtWidgets, uic
import h5py

# rename module to be filetree model?
# maybe split file into one that has nodes seperately

class TreeModel(QtCore.QAbstractItemModel):
    '''
    Naming convention (not right at the moment)
    lowerUpper is overidded modules
    lower_upper is custom methods
    '''
    sortRole = QtCore.Qt.UserRole
    filterRole = QtCore.Qt.UserRole + 1 # not sure if this is best for cols?

    def __init__(self, root, parent=None):
        super(TreeModel, self).__init__(parent)
        self.root_node = root

    def get_node(self, index):
        if index.isValid():
            node = index.internalPointer()
            if node:
                return node
        return self.root_node

    def parent(self, index):
        '''
        Required function
        Returns QModelIndex Obj associated parent of given QModelIndex'''
        node = self.get_node(index)
        parent_node = node.parent
        if parent_node == self.root_node:
            # return empty index as root has no parent
            return QtCore.QModelIndex()
        # if not root use method from QAbstractItemModel
        # row? not sure middle, last is object returned by internalPointer()
        # As is 0 only builds a hierachical strucure in first column...
        return self.createIndex(parent_node.row(),0,parent_node)

    def index(self, row, column, parent):
        '''
        Required function
        returns a child at row, column of parent'''
        parent_node = self.get_node(parent)

        child_item = parent_node.get_child(row)
        if child_item:
            return self.createIndex(row,column,child_item)
        else: # return empty index if doesnt exist
            return QtCore.QmodelIndex()

    # these xxxCount methods take QmodelIndex as input
    # and output ints
    def rowCount(self,parent):
        '''returns the amount of children an item has'''
        if not parent.isValid():
            return self.root_node.child_count()
        else:
            return parent.internalPointer().child_count()

    def columnCount(self,parent):
        return 2

    def flags(self,index):
        return QtCore.Qt.ItemIsEnabled| QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable

    def headerData(self, section, orientation,role):
        if role == QtCore.Qt.DisplayRole:
            if section == 0:
                return 'File list'
            if section == 1:
                return 'Properties'

    def setData(self,index,value,role=QtCore.Qt.EditRole):
        '''
        TODO: We might want to overwrite this for the select...?
        Args:
            index: QModelIndex
            value: QVariant
            role: int(flag?)
        '''
        if index.isValid():
            if role == QtCore.Qt.EditRole:
                node = index.internalPointer()
                node.set_name(value)

                return True
        return False

    def data(self, index, role):
        '''returns sometyhing that the view wants to display'''
        if not index.isValid():
            return None # not sure here what this is...
        node = index.internalPointer()

        if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
            if index.column() == 0:
                return node.name
            else:
                return node.type_info()

        if role == QtCore.Qt.DecorationRole:
            if index.column() == 0:
                if isinstance(node, DirectoryNode):
                    return QtGui.QIcon('icons/folder.png')

                if isinstance(node, FileNode):
                    pass #return pass

        if role == QtCore.Qt.ToolTipRole:
            return node.get_full_path()

        if role == TreeModel.filterRole:
            return node.name

        if role == TreeModel.sortRole: # will this ever be dif index for sort?
            if index.column() == 0:
                return node.name
            if index.column() == 1:
                return node.type_info()

    def insert_rows(self, position, rows, parent=QtCore.QModelIndex()):
        '''int int QmodelIndex'''
        parent_node = self.get_node(parent)
        self.beginInsertRows(parent, position, position+rows-1)
        #rows is a count, not index, hence -1 emit signal that is handled by the views
        for i in range(rows):
            #print(self.columnCount)
            child_node = Node('Untitled:')
            # loc lets you enlarge by setting on non existent key...
            success = parent_node.insert_child(position,child_node)
            # same postion and keeps pushiong items downwards
        self.endInsertRows()# emit signal that is handled by the views
        return success
    def remove_rows(self, position, rows, parent=QtCore.QModelIndex()):
        '''int int QmodelIndex'''
        parent_node = self.get_node(parent)
        self.beginRemoveRows(parent, position, position+rows-1)
        #rows is a count, not index, hence -1 emit signal that is handled by the views

        for i in range(rows):
            #print(self.columnCount)
            success = parent_node.remove_child(position)
            # same postion and keeps pushiong items downwards
        self.endRemoveRows()# emit signal that is handled by the views
        return success

class Node:
    '''Represents item of data in tree model'''
    def __init__(self,name,parent=None):
        self.name = name
        self.parent = parent
        self.children = []

        if parent is not None:
            parent.add_child(self)

    #property decorator thing here?
    def set_name(self,value):
        self.name=value

    def row(self):
        '''Returns index of this node in the parents children list
        Maybe change the method name?!
        '''
        if self.parent is not None:
            return self.parent.children.index(self)

    def add_child(self, child):
        self.children.append(child)

    def insert_child(self, position,child):
        if position <0 or position > len(self.children):
            return False
        self.children.insert(position,child)
        child.parent = self
        return True

    def remove_child(self, position):
        if position <0 or position > len(self.children):
            return False
        child = self.children.pop(position)
        child.parent = None
        return True

    def get_child(self, index):
        '''this might be pointless method'''
        return self.children[index]

    def child_count(self):
        '''method might be pointless...?'''
        return len(self.children)

    def __repr__(self):
        return self.log()

    def log(self, tab_level=-1):
        '''method used for printing children nodes to terminal, call on root'''
        output = ""
        tab_level+=1
        for i in range(tab_level):
            output +='\t'
        output += self.name + '\n'
        for child in self.children:
            output += child.log(tab_level)
        tab_level-=1
        return output

    def type_info(self):
        return 'BASE_NODE'

    # could make this a property
    def get_full_path(self):
        ''' Constructs fullpath from parent names'''
        full_path = self.name
        node = self
        while True:
            if node.parent is None:
                break
            node = node.parent
            full_path = os.path.join(node.name, full_path)

        return full_path

class DirectoryNode(Node):
    '''presume this should be always listening to a folder? (ideally)

    # maybe mnake this a FOLDER node
    '''
    def __init__(self, name, parent=None):
        super(DirectoryNode, self).__init__(name,parent)

        self.name = name

    def set_name(self, value):
        full_path = self.get_full_path()
        new_full_path = os.path.join(os.path.split(full_path)[0], value)
        os.rename(full_path, new_full_path)
        self.name = value

    def type_info(self):
        return 'Directory'

class FileNode(Node):
    '''This might end up being powerful... like an actual proxy around a file () but cant write?'''
    def __init__(self, name, parent=None):
        super(FileNode, self).__init__(name,parent)
        self.name = name
        # gonna have to do something clever here/ or in the
        # def make_rootnode_from_folder(self, root_folder):
        if self.name.endswith('.h5'):
            self.build_channel_children()
        #self.full_name = name
        # have to get fullname for chain of nodes?
        #self.fullname_have_to_grab_from_chaning

    def build_channel_children(self):
        '''currently set for just h5 files!'''
        self.full_path = self.get_full_path()
        #print('attempting to convert ', self.full_path)
        try:
            tids = eval('['+self.full_path.split('[')[1].split(']')[0]+']')
            for tid in tids:
                child_node = ChannelNode(tid, parent=self)
        except IndexError:
            print('h5 with no children detected:', self.full_path)

    def type_info(self):
        return 'File'

class ChannelNode(Node):
    '''Again,seems like we need to change how this is used...
    This might end up being powerful... like an actual proxy around a file () but cant write?'''
    def __init__(self, name, parent=None):
        super(ChannelNode, self).__init__(name,parent)
        self.name = name
    def type_info(self):
        return 'Channel'


class FileTreeProxyModel(QtCore.QAbstractProxyModel):
    '''Reimplement some of the virtual methods? '''
    def __init__(self):
        super(FileTreeProxyModel,self).__init__()


