import os
from PyQt5 import QtGui, QtCore, QtWidgets
import numpy as np
import json
from pyecog2.ProjectClass import create_metafile_from_h5, load_metadata_file
import pkg_resources


# rename module to be filetree model?
# maybe split file into one that has nodes seperately

class TreeModel(QtCore.QAbstractItemModel):
    # hmmm not sure best but lets roll with it
    # sends an array of data and their sampling freq in hz
    # maybe memmap is better?
    plot_node_signal = QtCore.pyqtSignal(np.ndarray)
    #plot_node_signal = QtCore.pyqtSignal()
    '''
    Naming convention (not right at the moment)
    lowerUpper is overidded modules
    lower_upper is custom methods
    '''
    print('Building File Tree...')
    sortRole = QtCore.Qt.UserRole
    filterRole = QtCore.Qt.UserRole + 1 # not sure if this is best for cols?
    prepare_for_plot_role = QtCore.Qt.UserRole + 2

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
        #print('Parent is ', parent_node)
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
        if index.column() ==0:
            return self.get_node(index).flags()
        return QtCore.Qt.ItemIsEnabled| QtCore.Qt.ItemIsSelectable # | QtCore.Qt.ItemIsEditable
        # we dont want them to be editable (at the moment)

    def headerData(self, section, orientation,role):
        if role == QtCore.Qt.DisplayRole:
            if section == 0:
                return 'File list'
            if section == 1:
                return 'Properties'

    # def doubleClicked(self,index):
    #     print('Doublecklicked....', index)

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

        if role == TreeModel.prepare_for_plot_role:
            if hasattr(node, 'prepare_for_plot'):
                range = node.prepare_for_plot()
                print('Emmiting plot_node_signal with range:',range)
                if range is not None:
                    self.plot_node_signal.emit(range)


        if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
            if index.column() == 0:
                return node.name.split(os.path.sep)[-1]
            else:
                return node.type_info()

        if role == QtCore.Qt.DecorationRole:
            if index.column() == 0:
                icon_file_prefix = pkg_resources.resource_filename('pyecog2', 'icons/')
                if isinstance(node, DirectoryNode):
                    return QtGui.QIcon(icon_file_prefix+'folder.png')
                if isinstance(node, HDF5FileNode):
                    return QtGui.QIcon(icon_file_prefix+'wave.png')
                if isinstance(node, LieteNode):
                    return QtGui.QIcon(icon_file_prefix+'wave.png')
                if isinstance(node, AnimalNode):
                    return QtGui.QIcon(icon_file_prefix+'laboratory-mouse.png')
                if isinstance(node, ProjectNode):
                    return QtGui.QIcon(icon_file_prefix+'research.png')
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

class Node(QtWidgets.QTreeWidgetItem):
    '''Represents item of data in tree model'''
    def __init__(self,name,parent=None, path=None):
        QtWidgets.QTreeWidgetItem.__init__(self)
        # self.setFlags(self.flags())
        self.name = name
        if path is None:
            self.path = name
        else:
            self.path = path
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
        full_path = self.path
        node = self
        while True:
            if node.parent is None:
                break
            node = node.parent
            full_path = os.path.join(node.path, full_path)

        return full_path

class DirectoryNode(Node):
    '''presume this should be always listening to a folder? (ideally)
    # maybe make this a FOLDER node
    '''
    def __init__(self, name, parent=None, path=None):
        super(DirectoryNode, self).__init__(name,parent,path)
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
    def __init__(self, name, parent=None,path=None):
        super(FileNode, self).__init__(name,parent,path)
        self.name = name

    def type_info(self):
        return 'Non-Data File'

class LieteNode(Node):
    def __init__(self, name, parent=None,path=None):
        super(LieteNode, self).__init__(name,parent,path)
        self.name = name
        self.metadata = None
        self.old_memmap_shape = None

    def prepare_for_plot(self):
        self.load_metadata()
        t0 = self.metadata['start_timestamp_unix']
        duration = self.metadata['duration']
        self.parent.parent.project.set_current_animal(self.parent.animal)
        return np.array([t0, t0+duration])

    def load_metadata(self):
        '''Demo file creation notebook'''
        meta_filepath = '.'.join(self.get_full_path().split('.')[:-1]) + '.meta'
        self.metadata = load_metadata_file(meta_filepath)

    def type_info(self):
        return 'bin DataFile'

class HDF5FileNode(Node):
    def __init__(self, name, parent=None,path=None):
        super(HDF5FileNode, self).__init__(name,parent,path)
        self.name = name
        # meta_filepath = self.get_full_path()[:-3] + '.meta' # no longer necessary as we are now checking this at file load time
        # if not os.path.isfile(meta_filepath):
        #     create_metafile_from_h5(self.get_full_path())

    def prepare_for_plot(self):
        '''maybe change name?'''
        self.load_metadata()
        t0 = self.metadata['start_timestamp_unix']
        duration = self.metadata['duration']
        self.parent.parent.project.set_current_animal(self.parent.animal)
        return np.array([t0, t0+duration])

    def load_metadata(self):
        '''Demo file creation notebook'''
        meta_filepath = '.'.join(self.get_full_path().split('.')[:-1]) + '.meta'
        self.metadata = load_metadata_file(meta_filepath)

    def type_info(self):
        return 'HDF5 File'

class ChannelNode(Node):
    '''Again,seems like we need to change how this is used...
    This might end up being powerful... like an actual proxy around a file () but cant write?'''
    def __init__(self, name, parent=None):
        super(ChannelNode, self).__init__(name,parent)
        self.name = name

    def type_info(self):
        return 'Channel'

class AnimalNode(Node):
    '''

    '''
    def __init__(self, animal, parent=None,path=''):
        super(AnimalNode, self).__init__(str(animal.id),parent=parent,path=path)
        self.animal = animal
        print('Adding animal:',animal.id)
        self.setFlags(QtCore.Qt.ItemIsEnabled| QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable)
        if animal.eeg_files: # Assuming all files for a given animal are of a given type to speed-up start-up process
            file = animal.eeg_files[0]
        else:
            file=''
        if os.path.isfile(os.path.join(self.get_full_path(), file)[:-4] + 'h5'):
            data_format = 'h5'
        else:
            data_format = 'bin'
        for file in sorted(animal.eeg_files):
            # metadata = load_metadata_file(os.path.join(self.get_full_path(),file))
            # data_format = metadata['data_format']
            if data_format == 'h5':
                HDF5FileNode(file[:-4]+'h5',parent=self) # replace .meta for .h5 to get the h5 file name
            else:
                LieteNode(file[:-4]+'bin',parent=self) # replace .meta for .bin to get the binary file name

    def set_name(self, value):
        self.name = str(value)
        self.animal.id = value

    def type_info(self):
        return 'Animal: ' + self.name

    def prepare_for_plot(self):
        # plot the earliest file
        children = self.children
        if children:
            child = min(children, key=lambda a: a.name)
            return child.prepare_for_plot()

class ProjectNode(Node):
    '''

    '''
    def __init__(self, project, parent=None):
        super(ProjectNode, self).__init__(str(project.title), parent=parent, path='')
        self.project = project
        self.setFlags(QtCore.Qt.ItemIsEnabled| QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable)
        self.name = project.title
        for animal in self.project.animal_list:
            AnimalNode(animal, parent=self)

    def set_name(self, value):
        self.name = str(value)
        self.project.title = value

    def type_info(self):
        return 'Project: ' + self.name


class FileTreeProxyModel(QtCore.QAbstractProxyModel):
    '''Reimplement some of the virtual methods? '''
    def __init__(self):
        super(FileTreeProxyModel,self).__init__()


