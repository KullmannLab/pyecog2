import sys, os, glob
from datetime import datetime
from PyQt5 import QtGui, QtCore
from PyQt5.QtWidgets import QGridLayout, QApplication, QWidget, QMainWindow, QTextBrowser, QPushButton, QFileDialog, QProgressBar

from pyqtgraph.parametertree import Parameter, ParameterTree
from pyecog2.ndf_converter import NdfFile, DataHandler
from pyecog2.coding_tests.WaveletWidget import Worker
from pyecog2.coding_tests.pyecogParameterTree import PyecogParameterTree,PyecogGroupParameter
from pyecog2.feature_extractor import FeatureExtractor
from pyecog2.classifier import GaussianClassifier
from collections import OrderedDict

class OutputWrapper(QtCore.QObject):
    outputWritten = QtCore.pyqtSignal(object, object)

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

def Animal2Parameter(animal):
    return {'name': animal.id,
            'type': 'group',
            'renamable': False,
            'removable': False,
            'children' : [
                {'name': 'Video directory',
                    'type': 'str',
                    'value': animal.video_folder}
            ]}


def Parameter2Animal(parameter):
    pass

class ClassifierWindow(QMainWindow):
    def __init__(self,project = None,parent = None):
        QMainWindow.__init__(self,parent = parent)
        widget = QWidget(self)
        layout = QGridLayout(widget)
        self.title ='Classifier Editor'
        self.setWindowTitle(self.title)
        self.project = project
        # if self.project is None:
        #     self.project = Project(main_model=MainModel())
        #     self.project.add_animal(Animal(id='0'))
        self.setCentralWidget(widget)
        self.terminal = QTextBrowser(self)
        self._err_color = QtCore.Qt.red
        self.button = QPushButton('Update', self)
        self.button.clicked.connect(self.update_project_settings)

        self.animal_dict = [Animal2Parameter(animal) for animal in self.project.animal_list]
        print(self.animal_dict)
        all_labels = self.project.get_all_labels()
        #set([l for a in self.project.animal_list for l in a.annotations.labels if not l.startswith('(auto)') ])
        self.params = [
            {'name': 'Global Settings','type':'group','children':[
                {'name': 'Lablels to train',
                 'type': 'group',
                 'children': [{'name': l, 'type': 'bool', 'value': True} for l in all_labels]
                 },
                {'name': 'Lablels to annotate',
                 'type': 'group',
                 'children': [{'name': l, 'type': 'bool', 'value': True} for l in all_labels]
                 },
                {'name': 'Train global classifier','type': 'action', 'children':[
                    {'name': 'Training Progress', 'type': 'float', 'readonly': True, 'value': 0, 'suffix': '%'}
                ]},
                {'name': 'Auto-generate Annotations with global classifier', 'type': 'action', 'children': [
                    {'name': 'Annotation Progress', 'type': 'float', 'readonly': True, 'value': 0, 'suffix': '%'}
                ]}
            ]},
            {'name': 'Animal Settings', 'type': 'group', 'expanded': False, 'children': [
                {'name': animal.id, 'type': 'group','children':[
                    {'name': 'Use animal for global classifier', 'type': 'bool', 'value': True},
                    {'name': 'Train animal-specific classifier', 'type': 'action','children':[
                        {'name': 'Training Progress', 'type': 'float', 'readonly': True, 'value': 0,'suffix':'%'}]},
                    {'name': 'Auto-generate Annotations with animal-specific classifier', 'type': 'action','children':[
                        {'name': 'Annotation Progress', 'type': 'float', 'readonly': True, 'value': 0, 'suffix': '%'}]},
                    {'name': 'Auto-generate Annotations with global classifier', 'type': 'action','children':[
                        {'name': 'Annotation Progress', 'type': 'float', 'readonly': True, 'value': 0, 'suffix': '%'}]},
                ]}
                for animal in self.project.animal_list]
                 },
            ]

        ## Create tree of Parameter objects
        self.p = Parameter.create(name='params', type='group', children=self.params)
        # self.p.param('Global Settings','Project Title').sigValueChanged.connect(self.setProjectTitle)
        # self.p.param('Global Settings', 'Update project from root folders').sigActivated.connect(self.update_project_from_roots)
        # self.p.param('Global Settings', 'Select EEG root directory','EEG root directory:').sigValueChanged.connect(
        #     self.setEEGFolder)
        # self.p.param('Global Settings', 'Select EEG root directory').sigActivated.connect(
        #     self.selectEEGFolder)
        # self.p.param('Global Settings', 'Select Video root directory','Video root directory:').sigValueChanged.connect(
        #     self.setVideoFolder)
        # self.p.param('Global Settings', 'Select Video root directory').sigActivated.connect(
        #     self.selectVideoFolder)

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
    window = ClassifierWindow()
    window.setGeometry(500, 300, 300, 200)
    window.show()
    sys.exit(app.exec_())
