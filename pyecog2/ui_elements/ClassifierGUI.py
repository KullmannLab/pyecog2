import sys, os
from PySide2 import QtCore
from PySide2.QtWidgets import QGridLayout, QApplication, QWidget, QMainWindow, QPushButton, QFileDialog

from pyqtgraph.parametertree import Parameter
from pyecog2.ui_elements.pyecogParameterTree import PyecogParameterTree
from pyecog2.classifier import ProjectClassifier
from pyecog2.feature_extractor import FeatureExtractor
from pyecog2.ProjectClass import Project
from pyecog2.ui_elements.WaveletWidget import Worker
from pyqtgraph.console import ConsoleWidget
import numpy as np
import json


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

def FeatureExtractor2Parameter(feature_extractor):
    return {'name': 'Features to use', 'type': 'group', 'expanded': False, 'children': [
             {'name': feature_label, 'type': 'bool', 'value':True}
             for feature_label in feature_extractor.settings['feature_labels']]
           }

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
        self.feature_extractor = FeatureExtractor()
        classifier_dir = self.project.project_file + '_classifier' if project is not None else ''
        if os.path.isfile(os.path.join(classifier_dir, '_feature_extractor.json')):
            self.feature_extractor.load_settings(os.path.join(classifier_dir, '_feature_extractor.json'))
        if os.path.isfile(os.path.join(classifier_dir, '_imported.npz')):
            self.imported_classifier_dir = os.path.join(classifier_dir, '_imported.npz')
        else:
            self.imported_classifier_dir = ''
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
                {'name': 'Import Classifier', 'type': 'action', 'children': [
                    {'name': 'Use imported classifier:', 'type': 'bool', 'value': os.path.isfile(self.imported_classifier_dir)}]},
                {'name': 'Lablels to train',
                 'type': 'group',
                 'children': [{'name': l, 'type': 'bool', 'value': False} for l in all_labels]
                 },
                {'name': 'Homogenize ticked labels across project', 'type': 'action'},
                {'name': 'Lablels to annotate',
                 'type': 'group',
                 'children': [{'name': l, 'type': 'bool', 'value': False} for l in all_labels]
                 },
                {'name': 'Automatic annotation settings',
                 'type': 'group',
                 'children': [{'name': 'Annotation threshold probability', 'type': 'float', 'value': 0.5,'bounds':[0,1],'dec': True},
                              {'name': 'Outlier threshold factor', 'type': 'float', 'value': 1,'bounds':[0,np.inf],'dec': True, 'min_step':1},
                              {'name': 'maximum number of annotations', 'type': 'int', 'value': 100},
                              {'name': 'Use Viterbi (only allows observed transitions - EXPERIMENTAL)', 'type': 'bool', 'value': False} ]
                 },
                FeatureExtractor2Parameter(self.feature_extractor)
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
                    {'name': 'Use animal for global classifier', 'type': 'bool', 'value': False},
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
            {'name': 'Run for all Animals', 'type': 'group', 'expanded': True, 'children': [
                {'name': 'Train animal-specific classifiers', 'type': 'action', 'children': [
                    {'name': 'Training Progress', 'type': 'float', 'readonly': True, 'value': 0, 'suffix': '%'}]},
                {'name': 'Auto-generate Annotations with global classifier', 'type': 'action',
                  'children': [
                      {'name': 'Annotation Progress', 'type': 'float', 'readonly': True, 'value': 0, 'suffix': '%'}]}]}
            ]

        ## Create tree of Parameter objects
        self.p = Parameter.create(name='params', type='group', children=self.params)
        # self.p.param(
        #     'Global Settings', 'Assimilate global classifier from individual animals'
        #     ).sigActivated.connect(self.classifier.assimilate_global_classifier)
        self.p.param(
            'Global Settings', 'Homogenize ticked labels across project'
            ).sigActivated.connect(self.homogenize_labels)

        self.p.param(
            'Global Settings', 'Import Classifier'
            ).sigActivated.connect(self.import_classifier)

        self.p.param(
            'Run for all Animals', 'Train animal-specific classifiers'
            ).sigActivated.connect(self.train_all)
        self.p.param(
            'Run for all Animals', 'Auto-generate Annotations with global classifier'
            ).sigActivated.connect(self.run_all)

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

        self.project.main_model.annotations.sigLabelsChanged.connect(self.updateLabels)
        self.project.main_model.sigProjectChanged.connect(self.update_settings)
        self.threadpool = QtCore.QThreadPool()
        self.dfrmt = '%Y-%m-%d %H:%M:%S'  # Format to use in date elements

        self.restoreState()

    def getLables2Annotate(self):
        all_labels = self.project.get_all_labels()
        return [label for label in all_labels if self.p.param('Global Settings', 'Lablels to annotate', label).value()]

    def getLables2train(self):
        all_labels = self.project.get_all_labels()
        return [label for label in all_labels if self.p.param('Global Settings', 'Lablels to train', label).value()]

    def getAnimals2use(self):
        all_ids = self.project.get_all_animal_ids()
        return [a for a in all_ids if self.p.param('Animal Settings', a, 'Use animal for global classifier').value()]

    def getFeatures2use(self):
        return np.array([self.p.param('Global Settings','Features to use', f).value() for f in self.feature_extractor.settings['feature_labels']])

    def updateLabels(self):
        self.classifier = ProjectClassifier(self.project)
        all_labels = self.project.get_all_labels()
        previous_lables = [p.name() for p in self.p.param('Global Settings', 'Lablels to train').children()]
        for label in all_labels:
            if label not in previous_lables:
                self.p.param('Global Settings', 'Lablels to train').addChild({'name': label, 'type': 'bool', 'value': False})
                self.p.param('Global Settings', 'Lablels to annotate').addChild({'name': label, 'type': 'bool', 'value': False})
        for label in previous_lables:
            if label not in all_labels:
                self.p.param('Global Settings', 'Lablels to train').removeChild(self.p.param('Global Settings', 'Lablels to train',label))
                self.p.param('Global Settings', 'Lablels to annotate').removeChild(self.p.param('Global Settings', 'Lablels to annotate',label))

    def updateAnimals(self):
        all_animals = [a.id for a in self.project.animal_list]
        previous_animals = [p.name() for p in self.p.param('Animal Settings').children()]
        for a in all_animals:
            if a not in previous_animals:
                self.p.param('Animal Settings').addChild({'name': a, 'type': 'group', 'children': [
                {'name': 'Use animal for global classifier', 'type': 'bool', 'value': False},
                {'name': 'Train animal-specific classifier', 'type': 'action', 'children': [
                    {'name': 'Training Progress', 'type': 'float', 'readonly': True, 'suffix': '%',
                     'value': 100 * (self.classifier.animal_classifier_dict[a].blank_npoints > 0)}]},
                {'name': 'Auto-generate Annotations with animal-specific classifier', 'type': 'action', 'children': [
                    {'name': 'Annotation Progress', 'type': 'float', 'readonly': True, 'value': 0, 'suffix': '%'}]},
                {'name': 'Auto-generate Annotations with global classifier', 'type': 'action', 'children': [
                    {'name': 'Annotation Progress', 'type': 'float', 'readonly': True, 'value': 0, 'suffix': '%'}]},
                ]})

                pbar = self.p.param('Animal Settings', a, 'Train animal-specific classifier',
                                    'Training Progress')
                self.p.param(
                    'Animal Settings', a, 'Train animal-specific classifier'
                ).sigActivated.connect(self.trainClassifierGenerator(a, pbar))

                pbar = self.p.param('Animal Settings', a,
                                    'Auto-generate Annotations with animal-specific classifier', 'Annotation Progress')
                self.p.param(
                    'Animal Settings', a, 'Auto-generate Annotations with animal-specific classifier'
                ).sigActivated.connect(self.runAnimalClassifierGenerator(a, pbar))

                pbar = self.p.param('Animal Settings', a, 'Auto-generate Annotations with global classifier',
                                    'Annotation Progress')
                self.p.param(
                    'Animal Settings', a, 'Auto-generate Annotations with global classifier'
                ).sigActivated.connect(self.runGlobalClassifierGenerator(a, pbar))

        for a in previous_animals:
            if a not in all_animals:
                self.p.param('Animal Settings').removeChild(a)

    def update_settings(self):
        self.saveState()
        self.updateLabels()
        self.updateAnimals()
        self.restoreState()


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

    def import_classifier(self):
        dialog = QFileDialog(parent=self)
        dialog.setWindowTitle('Import Classifier file ...')
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setNameFilter('*.npz')
        if dialog.exec():
            fname = dialog.selectedFiles()[0]
        else:
            return
        self.classifier.import_classifier(fname)
        self.classifier.save()

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
        worker = Worker(self.classifier.train_animal,animal_id,pbar,self.getLables2train(), self.getFeatures2use())
        self.threadpool.start(worker)
        return 1, 1

    def runAnimalClassifierGenerator(self,animal_id,pbar=None):
        return lambda: self.runAnimalClassifier(animal_id,pbar)

    def train_all(self):
        print('Training all animals')
        pbar = self.p.param('Run for all Animals', 'Train animal-specific classifiers','Training Progress')
        pbar.setValue(0.1)
        animal_id_list = [a.id for a in self.project.animal_list]
        for i, a in enumerate(animal_id_list):
            pbar_i = self.p.param('Animal Settings', a, 'Train animal-specific classifier','Training Progress')
            self.trainClassifier(a,pbar_i)
            pbar.setValue(int((i+1)/len(animal_id_list)*100))

    def run_all(self):
        print('Classifying all animals')
        pbar = self.p.param('Run for all Animals','Auto-generate Annotations with global classifier' ,'Annotation Progress')
        pbar.setValue(0.1)
        animal_id_list = [a.id for a in self.project.animal_list]
        for i, a in enumerate(animal_id_list):
            pbar_i = self.p.param('Animal Settings', a, 'Auto-generate Annotations with global classifier','Annotation Progress')
            self.runGlobalClassifier(a,pbar_i)
            pbar.setValue(int((i+1)/len(animal_id_list)*100))


    def runAnimalClassifier(self,animal_id,pbar=None):
        animal = self.project.get_animal(animal_id)
        print('Classifying', animal_id)
        prob_th = self.p.param('Global Settings','Automatic annotation settings', 'Annotation threshold probability').value()
        outlier_th = self.p.param('Global Settings','Automatic annotation settings', 'Outlier threshold factor').value()
        max_anno = self.p.param('Global Settings','Automatic annotation settings', 'maximum number of annotations').value()
        viterbi = self.p.param('Global Settings','Automatic annotation settings', 'Use Viterbi (only allows observed transitions - EXPERIMENTAL)').value()
        worker = Worker(self.classifier.animal_classifier_dict[animal_id].classify_animal,
                        animal,pbar,max_annotations=max_anno, prob_th=prob_th,outlier_th =outlier_th,
                        labels2annotate = self.getLables2Annotate(),viterbi=viterbi)
        worker.signals.finished.connect(self.updateAnnotationTables)
        self.threadpool.start(worker)
        return 1, 1

    def runGlobalClassifierGenerator(self, animal_id,pbar=None):
        return lambda: self.runGlobalClassifier(animal_id,pbar)

    def runGlobalClassifier(self, animal_id,pbar=None):
        self.classifier.assimilate_global_classifier(labels2train=self.getLables2train(), animals2use=self.getAnimals2use(), features2use=self.getFeatures2use())
        print('Labeling', animal_id)
        animal = self.project.get_animal(animal_id)
        prob_th = self.p.param('Global Settings','Automatic annotation settings', 'Annotation threshold probability').value()
        outlier_th = self.p.param('Global Settings','Automatic annotation settings', 'Outlier threshold factor').value()
        max_anno = self.p.param('Global Settings','Automatic annotation settings', 'maximum number of annotations').value()
        viterbi = self.p.param('Global Settings','Automatic annotation settings', 'Use Viterbi (only allows observed transitions - EXPERIMENTAL)').value()
        worker = Worker(self.classifier.classify_animal_with_global, animal, pbar, max_annotations=max_anno,
                        prob_th=prob_th,outlier_th =outlier_th, labels2annotate = self.getLables2Annotate(),viterbi=viterbi)
        worker.signals.finished.connect(self.updateAnnotationTables)
        self.threadpool.start(worker)
        return 1, 1

    def updateAnnotationTables(self):
        print('Worker Finished, emitting LabelsChanged signal')
        self.project.main_model.annotations.sigLabelsChanged.emit('')

    def saveState(self):
        classifier_dir = self.project.project_file + '_classifier'
        if not os.path.isdir(classifier_dir):
            os.mkdir(classifier_dir)

        fname = os.path.join(classifier_dir, 'classifier_gui_state.json')
        with open(fname, 'w') as json_file:
            s = self.p.saveState()
            json.dump(s, json_file, indent=2)

    def restoreState(self):
        classifier_dir = self.project.project_file + '_classifier'
        fname = os.path.join(classifier_dir, 'classifier_gui_state.json')
        if not os.path.isfile(fname):
             return
        with open(fname, 'r') as json_file:
            s = json.load(json_file)
        self.p.restoreState(s,addChildren=False,removeChildren=False)

    def closeEvent(self,evnet):
        self.saveState()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ClassifierWindow()
    window.setGeometry(500, 300, 300, 200)
    window.show()
    sys.exit(app.exec_())
