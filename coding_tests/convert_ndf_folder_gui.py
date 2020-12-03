import sys, os, glob
from PyQt5 import QtGui, QtCore
from PyQt5.QtWidgets import QMenuBar, QGridLayout, QApplication, QWidget, QPlainTextEdit, QMainWindow, QVBoxLayout, \
    QTextBrowser, QPushButton, QFileDialog


import pyqtgraph_copy.pyqtgraph.parametertree.parameterTypes as pTypes
from pyqtgraph_copy.pyqtgraph.parametertree import Parameter, ParameterTree
from ndf_converter import NdfFile, DataHandler
from coding_tests.WaveletWidget import Worker
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

class ScalableGroup(pTypes.GroupParameter):
    def __init__(self, **opts):
        opts['type'] = 'group'
        opts['addText'] = "Add"
        opts['addList'] = ['New Animal']  # ,'yellow','magenta','cyan']
        pTypes.GroupParameter.__init__(self, **opts)

    def addNew(self, typ):
        n = (len(self.childs) + 1)
        self.addChild(
            dict(name= 'Animal '+str(n), type='str', value='()', removable=True,
                 renamable=True))


class Window(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        widget = QWidget(self)
        layout = QGridLayout(widget)
        self.setCentralWidget(widget)
        self.terminal = QTextBrowser(self)
        self._err_color = QtCore.Qt.red
        self.button = QPushButton('Select NDF folder', self)
        self.button.clicked.connect(self.selectNDFFolder)
        self.folter2convert = ''
        self.button2 = QPushButton('Select destination folder', self)
        self.button2.clicked.connect(self.selectDestinationFolder)
        self.destination_folter = 'same_level'
        self.button3 = QPushButton('Convert Files!', self)
        self.button3.clicked.connect(self.runConvertFiles)

        self.animal_dict = [{'name': 'Animal 0',
                                'type': 'str',
                                'value': '[0]',
                                'renamable': True,
                                'removable': True}]

        self.params = [ScalableGroup(name="Animal id: [TID1,TID2,...]", children=self.animal_dict)]
        ## Create tree of Parameter objects
        self.p = Parameter.create(name='params', type='group', children=self.params)

        self.t = ParameterTree()
        self.t.setParameters(self.p, showTop=False)
        self.t.headerItem().setHidden(True)

        layout.addWidget(self.button)
        layout.addWidget(self.t)
        layout.setRowStretch(1,10)
        layout.setRowMinimumHeight(1,100)
        layout.addWidget(self.button2)
        layout.addWidget(self.button3)
        layout.addWidget(self.terminal)
        stdout = OutputWrapper(self, True)
        stdout.outputWritten.connect(self.handleOutput)
        stderr = OutputWrapper(self, False)
        stderr.outputWritten.connect(self.handleOutput)

        self.threadpool = QtCore.QThreadPool()

    def handleOutput(self, text, stdout):
        color = self.terminal.textColor()
        self.terminal.setTextColor(color if stdout else self._err_color)
        self.terminal.moveCursor(QtGui.QTextCursor.End)
        self.terminal.insertPlainText(text)
        self.terminal.setTextColor(color)

    def selectNDFFolder(self):
        dialog = QFileDialog()
        dialog.setWindowTitle('Select NDF directory')
        dialog.setFileMode(QFileDialog.DirectoryOnly)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        if dialog.exec():
            self.folter2convert = dialog.selectedFiles()[0]
            ndf_files = glob.glob(self.folter2convert + '/*.ndf')
            ndf_files.sort()
            print('Converting folder:',self.folter2convert)
            print('There are',len(ndf_files),' *.ndf files to convert...')
            if len(ndf_files) == 0:
                print('Folder does not have *.ndf files to convert!')
                return
            test_file = NdfFile(ndf_files[0])
            test_file.read_file_metadata()
            test_file.get_valid_tids_and_fs()
            print('Found TIDs',test_file.tid_set,' valid in first file (there might be more in other files)')
            self.animal_dict = []
            for i,id in enumerate(test_file.tid_set):
                self.animal_dict.append({'name': 'Animal '+ str(i),
                                     'type': 'str',
                                     'value': '[' + str(id) + ']',
                                     'renamable': True,
                                     'removable': True})
            self.p.clearChildren()
            self.params = [ScalableGroup(name="Animal id: [TID1,TID2,...] " + self.folter2convert, children=self.animal_dict)]
            self.p.addChildren(self.params)
        else:
            sys.stderr.write('No folder selected\n')

    def selectDestinationFolder(self):
        dialog = QFileDialog()
        dialog.setWindowTitle('Select NDF directory')
        dialog.setFileMode(QFileDialog.DirectoryOnly)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        if dialog.exec():
            self.destination_folter = dialog.selectedFiles()[0]
            print('Saving files to folder:',self.destination_folter)

    def runConvertFiles(self):
        worker = Worker(self.convertFiles)
        print('Starting file conversion...')
        self.threadpool.start(worker)

    def convertFiles(self):
        dh = DataHandler()
        for a in self.animal_dict:
            print('***\n Starting to convert', a['name'], a['value'],'\n***')
            tids = a['value']
            dh.convert_ndf_directory_to_h5(self.folter2convert,tids=tids,save_dir=self.destination_folter)
        return (1,1) # wavelet worker expects to emit tuple when done...





if __name__ == '__main__':

    app = QApplication(sys.argv)
    window = Window()
    window.setGeometry(500, 300, 300, 200)
    window.show()
    sys.exit(app.exec_())