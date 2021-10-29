import sys, os, glob
from datetime import datetime
from PySide2 import QtGui, QtCore
from PySide2.QtWidgets import QGridLayout, QApplication, QWidget, QMainWindow, QTextBrowser, QPushButton, QFileDialog, \
    QProgressBar, QCheckBox

from pyqtgraph.parametertree import Parameter, ParameterTree
from pyecog2.ndf_converter import NdfFile, DataHandler
from pyecog2.coding_tests.WaveletWidget import Worker
from pyecog2.coding_tests.pyecogParameterTree import PyecogParameterTree,PyecogGroupParameter
from pyecog2.feature_extractor import FeatureExtractor,reg_entropy,powerf,rfft_band_power,powerf
from collections import OrderedDict

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
        opts['addList'] = ['New Feature']
        PyecogGroupParameter.__init__(self, **opts)

    def addNew(self, typ):
        self.addChild({'name': 'feature label',
                       'type': 'str',
                       'renamable': True,
                       'removable': True,
                       'value': 'lambda x: np.std(x)'})

class ScalableGroupF(ScalableGroup):
    def addNew(self, typ):
        self.addChild({'name': 'power 1Hz to 4Hz',
                       'type': 'str',
                       'renamable': True,
                       'removable': True,
                       'value': 'lambda f: powerf(1, 4)'})

class ScalableGroupM(PyecogGroupParameter):
    def __init__(self, **opts):
        opts['type'] = 'group'
        opts['addText'] = "Add"
        opts['addList'] = ['New Module']
        PyecogGroupParameter.__init__(self, **opts)

    def addNew(self, typ):
        self.addChild({'name': 'module',
                       'type': 'str',
                       'renamable': True,
                       'removable': True,
                       'value': 'alias'})

def settings2params(settings):
    ntimefuncs = len(settings['feature_time_functions'])
    return [
            {'name': 'Feature Extractor Settings','type':'group','children':
                [
                {'name': 'Window settings','type':'group','children':[
                    {'name': 'Type:', 'type': 'list','value':settings['window'],
                     'values': ['rectangular','triang','blackman','hamming','hann',
                                                                 'bartlett','flattop','parzen','bohman','blackmanharris',
                                                                 'nuttall','barthann']},
                    {'name':'Length (s):','type':'float','value': settings['window_length']},
                    {'name': 'Overlap ratio:', 'type': 'float', 'value': settings['overlap']}]},
                ScalableGroup(name='Features in time domain',children = [
                    {'name': label, 'renamable': True, 'removable': True, 'type': 'str', 'value': func}
                    for label,func in zip(settings['feature_labels'][:ntimefuncs], settings['feature_time_functions'])]),
                ScalableGroupF(name='Features in frequency domain', children=[
                    {'name': label, 'renamable': True, 'removable': True, 'type': 'str', 'value': func}
                    for label,func in zip(settings['feature_labels'][ntimefuncs:], settings['feature_freq_functions'])]),
                ScalableGroupM(name='Module dependencies to import', children=[
                    {'name': module, 'renamable': True,'removable': True, 'type': 'str', 'value': alias}
                    for module, alias in settings['function_module_dependencies']])
                    ]
             }]

def params2settings(params):
    fe_settings_list = params.children()[0].children()
    window_settings = fe_settings_list[0].children()
    feature_time_functions = fe_settings_list[1].children()
    feature_freq_functions = fe_settings_list[2].children()
    function_module_dependencies = fe_settings_list[3].children()
    return OrderedDict(
        window_length=window_settings[1].value(),  # length in seconds for the segments on which to compute features
        overlap=window_settings[2].value(),  # overlap ratio between windows
        window=window_settings[0].value(), # window type
        feature_labels=[f.name() for f in feature_time_functions] + [f.name() for f in feature_freq_functions],
        feature_time_functions=[f.value() for f in feature_time_functions],
        feature_freq_functions=[f.value() for f in feature_freq_functions],
        function_module_dependencies=[(d.name(),d.value()) for d in function_module_dependencies]
        )

class FeatureExtractorWindow(QMainWindow):
    def __init__(self, project=None, parent=None):
        QMainWindow.__init__(self, parent=parent)
        widget = QWidget(self)
        layout = QGridLayout(widget)
        self.title = 'Feature Extractor'
        self.setWindowTitle(self.title)
        self.project = project
        self.feature_extractor = FeatureExtractor()
        classifier_dir = self.project.project_file + '_classifier' if project is not None else ''
        if os.path.isfile(os.path.join(classifier_dir, '_feature_extractor.json')):
            self.feature_extractor.load_settings(os.path.join(classifier_dir, '_feature_extractor.json'))
        self.setCentralWidget(widget)
        self.terminal = QTextBrowser(self)
        self._err_color = QtCore.Qt.red
        self.button0 = QPushButton('Import Settings File', self)
        self.button0.clicked.connect(self.loadSettingsFile)
        self.button1 = QPushButton('Set Project feature Extractor', self)
        self.button1.clicked.connect(self.setProjectFeatureExtraction)
        self.button2 = QPushButton('Extract!', self)
        self.button2.clicked.connect(self.runFeatureExtraction)
        self.re_write = QCheckBox('Force file re-write')
        self.button3 = QPushButton('Export Settings File', self)
        self.button3.clicked.connect(self.exportSettingsFile)
        self.progressBar0 = QProgressBar()
        self.progressBar0.setFormat('Animals: %p%')
        self.progressBar1 = QProgressBar()
        self.progressBar1.setFormat('Files: %p%')
        self.t = PyecogParameterTree()
        self.updateTreeFromSettings()

        layout.addWidget(self.button0)
        layout.addWidget(self.t)
        layout.setRowStretch(1,10)
        layout.setRowMinimumHeight(1,400)
        layout.setColumnMinimumWidth(0,600)
        layout.addWidget(self.button1)
        extract_widget = QWidget()
        extract_layout = QGridLayout(extract_widget)
        extract_layout.addWidget(self.button2,0,0)
        extract_layout.addWidget(self.re_write,0,1)
        layout.addWidget(extract_widget)
        layout.addWidget(self.button3)
        layout.addWidget(self.progressBar0)
        layout.addWidget(self.progressBar1)
        layout.addWidget(self.terminal)
        layout.setRowMinimumHeight(7,300)
        stdout = OutputWrapper(self, True)
        stdout.outputWritten.connect(self.handleOutput)
        stderr = OutputWrapper(self, False)
        stderr.outputWritten.connect(self.handleOutput)

        self.threadpool = QtCore.QThreadPool()

        self.dfrmt = '%Y-%m-%d %H:%M:%S'  # Format to use in date elements

    def updateTreeFromSettings(self):
        self.params = settings2params(self.feature_extractor.settings)
        ## Create tree of Parameter objects
        self.p = Parameter.create(name='params', type='group', children=self.params)
        self.t.setParameters(self.p, showTop=False)
        self.t.headerItem().setHidden(True)

    def loadSettingsFile(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle('Select Feature Etractor Settings file ...')
        dialog.setFileMode(QFileDialog.ExistingFile)
        # dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setNameFilter('*.json')
        if dialog.exec():
            fname = dialog.selectedFiles()[0]
            self.feature_extractor.load_settings(fname)
            self.updateTreeFromSettings()
            print('loaded', fname)

    def exportSettingsFile(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle('Select Feature Etractor Settings file ...')
        dialog.setFileMode(QFileDialog.AnyFile)
        # dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setNameFilter('*.json')
        if dialog.exec():
            fname = dialog.selectedFiles()[0]
            if not fname.endswith(('.json')):
                fname = fname + '.json'
            self.feature_extractor.save_settings(fname)
            print('saved settings as', fname)


    def handleOutput(self, text, stdout):
        color = self.terminal.textColor()
        self.terminal.setTextColor(color if stdout else self._err_color)
        self.terminal.moveCursor(QtGui.QTextCursor.End)
        self.terminal.insertPlainText(text)
        self.terminal.setTextColor(color)

    def setProjectFeatureExtraction(self):
        self.feature_extractor.update_from_settings(params2settings(self.p))
        classifier_dir = self.project.project_file + '_classifier'
        if not os.path.isdir(classifier_dir):
            os.mkdir(classifier_dir)
        self.feature_extractor.save_settings(os.path.join(classifier_dir, '_feature_extractor.json'))
        print(self.feature_extractor.settings)

    def runFeatureExtraction(self):
        self.setProjectFeatureExtraction()
        print('Starting feature extraction...')
        classifier_dir = self.project.project_file + '_classifier'
        if not os.path.isdir(classifier_dir):
            os.mkdir(classifier_dir)
        self.feature_extractor.save_settings(os.path.join(classifier_dir, '_feature_extractor.json'))
        print('Starting FE worker')
        worker = Worker(self.extractFeatures)
        self.progressBar0.setValue(0.1)
        self.progressBar1.setValue(0.1)
        self.threadpool.start(worker)

    def extractFeatures(self):
        for i,animal in enumerate(self.project.animal_list):
            print(' calling feature_extractor.extract_features_from_animal')
            self.feature_extractor.extract_features_from_animal(animal, re_write = self.re_write.isChecked(), n_cores = -1,
                                                                progress_bar = self.progressBar1)
            self.progressBar0.setValue((100*(i+1))//len(self.project.animal_list))
        print('Finnished extracting features')
        return (1, 1)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = FeatureExtractorWindow()
    window.setGeometry(500, 300, 300, 200)
    window.show()
    sys.exit(app.exec_())