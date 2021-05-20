import sys, os, glob
from datetime import datetime
from PyQt5 import QtGui, QtCore
from PyQt5.QtWidgets import QGridLayout, QApplication, QWidget, QMainWindow, QTextBrowser, QPushButton, QFileDialog, \
    QProgressBar

from pyqtgraph.parametertree import Parameter, ParameterTree
from pyecog2.ndf_converter import NdfFile, DataHandler
from pyecog2.coding_tests.WaveletWidget import Worker
from pyecog2.coding_tests.pyecogParameterTree import PyecogParameterTree,PyecogGroupParameter
from pyecog2.feature_extractor import FeatureExtractor
from pyecog2.classifier import GaussianClassifier, ProjectClassifier
from pyecog2.ProjectClass import Project
from pyecog2.coding_tests.WaveletWidget import Worker
from collections import OrderedDict
from pyqtgraph.console import ConsoleWidget

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
        if project is None:
            project = Project()
        self.project = project
        self.classifier = ProjectClassifier(project)
        # if self.project is None:
        #     self.project = Project(main_model=MainModel())
        #     self.project.add_animal(Animal(id='0'))
        self.setCentralWidget(widget)
        self.terminal = ConsoleWidget(namespace={'self':self}) # QTextBrowser(self)
        self._err_color = QtCore.Qt.red
        self.button = QPushButton('Update', self)
        self.button.clicked.connect(self.update_settings)
        self.threadpool = QtCore.QThreadPool()

        all_labels = self.project.get_all_labels()
        #set([l for a in self.project.animal_list for l in a.annotations.labels if not l.startswith('(auto)') ])
        self.params = [
            {'name': 'Global Settings','type':'group','children':[
                {'name': 'Lablels to train',
                 'type': 'group',
                 'children': [{'name': l, 'type': 'bool', 'value': True} for l in all_labels]
                 },
                {'name': 'Homogenize ticked labels across project', 'type': 'action'},
                {'name': 'Lablels to annotate',
                 'type': 'group',
                 'children': [{'name': l, 'type': 'bool', 'value': True} for l in all_labels]
                 },
                # {'name': 'Assimilate global classifier from individual animals', 'type': 'action'},
                # {'name': 'Train global classifier','type': 'action', 'children':[
                #     {'name': 'Training Progress', 'type': 'float', 'readonly': True, 'value': 0, 'suffix': '%'}
                # ]},
                # {'name': 'Auto-generate Annotations with global classifier', 'type': 'action', 'children': [
                #     {'name': 'Annotation Progress', 'type': 'float', 'readonly': True, 'value': 0, 'suffix': '%'}
                # ]}
            ]},
            {'name': 'Animal Settings', 'type': 'group', 'expanded': True, 'children': [
                {'name': animal, 'type': 'group','children':[
                    {'name': 'Use animal for global classifier', 'type': 'bool', 'value': True},
                    {'name': 'Train animal-specific classifier', 'type': 'action','children':[
                        {'name': 'Training Progress', 'type': 'float', 'readonly': True, 'suffix':'%',
                         'value': 100*(self.classifier.animal_classifier_dict[animal].blank_npoints>0)}]},
                    {'name': 'Auto-generate Annotations with animal-specific classifier', 'type': 'action','children':[
                        {'name': 'Annotation Progress', 'type': 'float', 'readonly': True, 'value': 0, 'suffix': '%'}]},
                    {'name': 'Auto-generate Annotations with global classifier', 'type': 'action','children':[
                        {'name': 'Annotation Progress', 'type': 'float', 'readonly': True, 'value': 0, 'suffix': '%'}]},
                ]}
                for animal in self.classifier.animal_classifier_dict.keys()]
                 },
            ]

        ## Create tree of Parameter objects
        self.p = Parameter.create(name='params', type='group', children=self.params)
        # self.p.param(
        #     'Global Settings', 'Assimilate global classifier from individual animals'
        #     ).sigActivated.connect(self.classifier.assimilate_global_classifier)
        self.p.param(
            'Global Settings', 'Homogenize ticked labels across project'
            ).sigActivated.connect(self.homogenize_labels)

        for animal_id in self.classifier.animal_classifier_dict.keys():
            pbar = self.p.param('Animal Settings',animal_id,'Train animal-specific classifier', 'Training Progress')
            self.p.param(
                'Animal Settings',animal_id,'Train animal-specific classifier'
                        ).sigActivated.connect(self.trainClassifierGenerator(animal_id, pbar))

            pbar = self.p.param('Animal Settings', animal_id,'Auto-generate Annotations with animal-specific classifier', 'Annotation Progress')
            self.p.param(
                'Animal Settings',animal_id,'Auto-generate Annotations with animal-specific classifier'
                        ).sigActivated.connect(self.runAnimalClassifierGenerator(animal_id,pbar))

            pbar = self.p.param('Animal Settings', animal_id,'Auto-generate Annotations with global classifier', 'Annotation Progress')
            self.p.param(
                'Animal Settings',animal_id,'Auto-generate Annotations with global classifier'
                        ).sigActivated.connect(self.runGlobalClassifierGenerator(animal_id,pbar))

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

    def getLables2Annotate(self):
        all_labels = self.project.get_all_labels()
        return [label for label in all_labels if self.p.param('Global Settings', 'Lablels to annotate', label).value()]

    def getLables2train(self):
        all_labels = self.project.get_all_labels()
        return [label for label in all_labels if self.p.param('Global Settings', 'Lablels to train', label).value()]

    def homogenize_labels(self):
        labels = self.getLables2train()
        for animal in self.project.animal_list:
            annotation_page = animal.annotations
            for label in annotation_page.labels:
                if label not in labels:  # only copy labels that are ticked to train
                    continue
                for animal2 in self.project.animal_list:
                    if label not in animal2.annotations.labels:
                        animal2.annotations.add_label(label,annotation_page.label_color_dict[label])
                    else:
                        animal2.annotations.label_color_dict[label] = annotation_page.label_color_dict[label] # if annotation exists copy color

    def handleOutput(self, text, stdout):
        # color = self.terminal.textColor()
        # self.terminal.setTextColor(color if stdout else self._err_color)
        # self.terminal.moveCursor(QtGui.QTextCursor.End)
        # self.terminal.insertPlainText(text)
        # self.terminal.setTextColor(color)
        self.terminal.write(text)

    def trainClassifierGenerator(self,animal_id,pbar=None):
        return lambda: self.trainClassifier(animal_id,pbar)

    def trainClassifier(self,animal_id,pbar=None):
        print('Training', animal_id)
        if pbar is not None:
            pbar.setValue(0.1)
        worker = Worker(self.classifier.train_animal,animal_id,pbar,self.getLables2train())
        self.threadpool.start(worker)
        return 1, 1

    def runAnimalClassifierGenerator(self,animal_id,pbar=None):
        return lambda: self.runAnimalClassifier(animal_id,pbar)

    def runAnimalClassifier(self,animal_id,pbar=None):
        animal = self.project.get_animal(animal_id)
        print('Classifying', animal_id)
        worker = Worker(self.classifier.animal_classifier_dict[animal_id].classify_animal,
                        animal,pbar,max_annotations=100, labels2annotate = self.getLables2Annotate())
        self.threadpool.start(worker)
        return 1, 1

    def runGlobalClassifierGenerator(self, animal_id,pbar=None):
        return lambda: self.runGlobalClassifier(animal_id,pbar)

    def runGlobalClassifier(self, animal_id,pbar=None):
        self.classifier.assimilate_global_classifier(labels2train=self.getLables2train())
        print('Labeling', animal_id)
        animal = self.project.get_animal(animal_id)
        worker = Worker(self.classifier.classify_animal_with_global, animal, pbar, max_annotations=100,
                        labels2annotate = self.getLables2Annotate())
        self.threadpool.start(worker)
        return 1, 1

    def update_settings(self):
        pass

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ClassifierWindow()
    window.setGeometry(500, 300, 300, 200)
    window.show()
    sys.exit(app.exec_())
