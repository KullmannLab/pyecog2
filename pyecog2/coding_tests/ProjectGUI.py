import sys
from PySide2 import QtGui, QtCore
from PySide2.QtWidgets import QGridLayout, QApplication, QWidget, QMainWindow, QTextBrowser, QPushButton, QFileDialog

from pyecog2.ProjectClass import Animal
# from ..ProjectClass import Animal
# from main import MainModel

from pyqtgraph.parametertree import Parameter
from pyecog2.coding_tests.pyecogParameterTree import PyecogParameterTree,PyecogGroupParameter
from pyecog2.coding_tests.WaveletWidget import Worker

class OutputWrapper(QtCore.QObject):
    outputWritten = QtCore.Signal(object, object)

    def __init__(self, parent, stdout=True):
        QtCore.QObject.__init__(self, parent)
        if stdout:
            self._stream = sys.stdout
            sys.stdout = self
        else:
            self._stream = sys.stderr
            sys.stderr = self
        self._stdout = stdout

    def write(self, text):
        self._stream.write(text)
        self.outputWritten.emit(text, self._stdout)

    def __getattr__(self, name):
        return getattr(self._stream, name)

    def __del__(self):
        try:
            if self._stdout:
                sys.stdout = self._stream
            else:
                sys.stderr = self._stream
        except AttributeError:
            pass

class ScalableGroup(PyecogGroupParameter):
    def __init__(self, **opts):
        opts['type'] = 'group'
        opts['addText'] = "Add"
        opts['addList'] = ['New Animal']
        PyecogGroupParameter.__init__(self, **opts)

    def addNew(self, typ, n=None):
        if n is None:
            n = (len(self.childs) + 1)
        try:
            self.addChild(Animal2Parameter(Animal(id='Animal '+str(n))))
        except Exception:
            print('Animal with name','Animal '+str(n+1),'already exists. Trying to add animal with name:','Animal '+str(n+1))
            self.addNew(typ,n+1)

def Animal2Parameter(animal):
    return {'name': animal.id,
            'type': 'group',
            'renamable': False,
            'removable': True,
            'children' : [
                {'name': 'new id',
                 'type': 'str',
                 'value': animal.id},
                {'name':'EEG directory',
                    'type': 'str',
                    'value': animal.eeg_folder},
                {'name': 'Video directory',
                    'type': 'str',
                    'value': animal.video_folder}
            ]}


def Parameter2Animal(parameter):
    pass

class ProjectEditWindow(QMainWindow):
    def __init__(self,project = None,parent = None):
        QMainWindow.__init__(self,parent = parent)
        widget = QWidget(self)
        layout = QGridLayout(widget)
        self.title ='Project Editor'
        self.setWindowTitle(self.title)
        self.project = project
        # if self.project is None:
        #     self.project = Project(main_model=MainModel())
        #     self.project.add_animal(Animal(id='0'))
        self.setCentralWidget(widget)
        self.terminal = QTextBrowser(self)
        self._err_color = QtCore.Qt.red
        self.folder2convert = ''
        self.button = QPushButton('Update Project Settings from Animal List', self)
        self.button.clicked.connect(self.update_project_settings)

        self.animal_dict = [Animal2Parameter(animal) for animal in self.project.animal_list]
        print(self.animal_dict)

        self.params = [
            {'name': 'Global Settings','type':'group','children':[
                {'name': 'Project Title', 'type': 'str', 'value': self.project.title},
                # {'name': 'Project file','type':'action','children':[
                    {'name':'Project file:','type':'str','value': self.project.project_file},
                # ]},
                {'name': 'Select EEG root directory','type':'action','children':[
                    {'name':'EEG root directory:','type':'str','value': self.project.eeg_root_folder}
                ]},
                {'name': 'Select Video root directory', 'type': 'action', 'children': [
                    {'name': 'Video root directory:', 'type': 'str', 'value': self.project.video_root_folder}
                ]},
                {'name': ' ', 'type': 'str','vlue':' '},
                {'name': 'Update project from root folders', 'type': 'action'},
                {'name': '  ', 'type': 'str','vlue':' '},
            ]},
            ScalableGroup(name='Animal list:', children=self.animal_dict)]

        ## Create tree of Parameter objects
        self.p = Parameter.create(name='params', type='group', children=self.params)
        self.p.param('Global Settings','Project Title').sigValueChanged.connect(self.setProjectTitle)
        self.p.param('Global Settings', 'Update project from root folders').sigActivated.connect(self.update_project_from_roots)
        self.p.param('Global Settings', 'Select EEG root directory','EEG root directory:').sigValueChanged.connect(
            self.setEEGFolder)
        self.p.param('Global Settings', 'Select EEG root directory').sigActivated.connect(
            self.selectEEGFolder)
        self.p.param('Global Settings', 'Select Video root directory','Video root directory:').sigValueChanged.connect(
            self.setVideoFolder)
        self.p.param('Global Settings', 'Select Video root directory').sigActivated.connect(
            self.selectVideoFolder)

        self.t = PyecogParameterTree()
        self.t.setParameters(self.p, showTop=False)
        self.t.headerItem().setHidden(True)

        layout.addWidget(self.t)
        layout.setRowStretch(0,10)
        layout.setRowMinimumHeight(0,400)
        layout.setColumnMinimumWidth(0,600)
        layout.addWidget(self.button)
        layout.addWidget(self.terminal)
        layout.setRowMinimumHeight(2,300)
        stdout = OutputWrapper(self, True)
        stdout.outputWritten.connect(self.handleOutput)
        stderr = OutputWrapper(self, False)
        stderr.outputWritten.connect(self.handleOutput)

        self.threadpool = QtCore.QThreadPool()

        self.dfrmt = '%Y-%m-%d %H:%M:%S'  # Format to use in date elements

    def handleOutput(self, text, stdout):
        color = self.terminal.textColor()
        self.terminal.setTextColor(color if stdout else self._err_color)
        self.terminal.moveCursor(QtGui.QTextCursor.End)
        self.terminal.insertPlainText(text)
        self.terminal.setTextColor(color)

    def selectEEGFolder(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle('Select EEG directory')
        dialog.setFileMode(QFileDialog.DirectoryOnly)
        # dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        if dialog.exec():
            self.p.param('Global Settings', 'Select EEG root directory','EEG root directory:').setValue(dialog.selectedFiles()[0])
        else:
            sys.stderr.write('No folder selected\n')

    def setEEGFolder(self, eeg_root_folder_param):
        pass  # Currently we are only accepting changes when clicking the Update button
        # self.project.eeg_root_folder = eeg_root_folder.value(0)

    def selectVideoFolder(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle('Select EEG directory')
        dialog.setFileMode(QFileDialog.DirectoryOnly)
        # dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        if dialog.exec():
            self.p.param('Global Settings', 'Select Video root directory','Video root directory:').setValue(dialog.selectedFiles()[0])
        else:
            sys.stderr.write('No folder selected\n')


    def setProjectTitle(self, eeg_root_folder_param):
        print('Changing project title to:',eeg_root_folder_param.value())
        self.project.setTitle(eeg_root_folder_param.value())


    def setVideoFolder(self, eeg_root_folder_param):
        pass  # Currently we are only accepting changes when clicking the Update button
        # self.project.eeg_root_folder = eeg_root_folder.value(0)

    def update_project_settings(self):
        animal_param_list = self.p.param('Animal list:').getValues()
        old_animal_list = [a.id for a in self.project.animal_list]
        deleted_animals = list(set(old_animal_list)-set(animal_param_list))

        for a in deleted_animals:
            print('Deleting animal with id',a)
            self.project.delete_animal(a)

        for p in animal_param_list:
            animal = self.project.get_animal(p)
            id = self.p.param('Animal list:',p,'new id').value()
            eeg_dir = self.p.param('Animal list:',p,'EEG directory').value()
            video_dir = self.p.param('Animal list:',p,'Video directory').value()
            self.p.param('Animal list:',p).setName(id)
            if animal is None:
                print('Adding new animal with id', id)
                self.project.add_animal(Animal(id=id,eeg_folder=eeg_dir,video_folder=video_dir))
            else:
                print('Updating animal with id', id)
                animal.update_eeg_folder(eeg_dir)
                animal.update_video_folder(video_dir)
        print('Project update finished')


    def update_project_from_roots(self):
        self.project.eeg_root_folder = self.p.param('Global Settings', 'Select EEG root directory','EEG root directory:').value()
        self.project.video_root_folder = self.p.param('Global Settings', 'Select Video root directory','Video root directory:').value()
        print('Updating project from root directories...')
        print('processing', self.project.eeg_root_folder)
        self.project.update_project_from_root_directories()

        # update animal list in GUI
        self.animal_dict = [Animal2Parameter(animal) for animal in self.project.animal_list]
        self.p.param('Animal list:').clearChildren()
        self.p.param('Animal list:').addChildren(self.animal_dict)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ProjectEditWindow()
    window.setGeometry(500, 300, 300, 200)
    window.show()
    sys.exit(app.exec_())