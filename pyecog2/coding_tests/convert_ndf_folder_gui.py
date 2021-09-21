import sys, os, glob
from datetime import datetime
from PySide2 import QtGui, QtCore
from PySide2.QtWidgets import QGridLayout, QApplication, QWidget, QMainWindow, QTextBrowser, QPushButton, QFileDialog

from pyqtgraph.parametertree import Parameter, ParameterTree
from pyecog2.ndf_converter import NdfFile, DataHandler
from pyecog2.coding_tests.WaveletWidget import Worker
from pyecog2.coding_tests.pyecogParameterTree import PyecogParameterTree,PyecogGroupParameter


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
        opts['addList'] = ['New Animal']  # ,'yellow','magenta','cyan']
        PyecogGroupParameter.__init__(self, **opts)

    def addNew(self, typ,n=None):
        if n is None:
            n = (len(self.childs) + 1)
        try:
            self.addChild(
                dict(name= 'Animal '+str(n), type='str', value='[tid],auto', removable=True,
                     renamable=True))
        except Exception:
            self.addNew(typ,n+1)



class NDFConverterWindow(QMainWindow):
    def __init__(self,parent = None):
        QMainWindow.__init__(self,parent = parent)
        self.settings = None
        if hasattr(parent.main_model.project,'ndf_converter_settings'): # For backwards compatibility
            self.settings = parent.main_model.project.ndf_converter_settings
        if self.settings is None:
            self.settings = {'NDFdir': os.getcwd(),
                             'H5dir': os.getcwd(),
                             'start': '0001-01-01 00:00:00',
                             'end': '9999-01-01 00:00:00',
                             'AnimalDictList':[{'id': 'Animal 1',
                                                'tidfs': '[0],auto'}]
                             }
            parent.main_model.project.ndf_converter_settings = self.settings

        widget = QWidget(self)
        layout = QGridLayout(widget)
        self.title = "NDF converter"
        self.setWindowTitle(self.title)
        self.setCentralWidget(widget)
        self.terminal = QTextBrowser(self)
        self._err_color = QtCore.Qt.red
        self.folder2convert = self.settings['NDFdir']
        self.destination_folder = self.settings['H5dir']
        self.button3 = QPushButton('Convert Files!', self)
        self.button3.clicked.connect(self.runConvertFiles)

        self.animal_dict = [{'name': a['id'],
                                'type': 'str',
                                'value': a['tidfs'] ,
                                'renamable': True,
                                'removable': True} for a in self.settings['AnimalDictList']]
        self.params = [
            {'name': 'Directories','type':'group','children':[
                {'name': 'Select NDF directory','type':'action','children':[
                    {'name':'NDF directory:','type':'str','value': self.folder2convert}
                ]},
                {'name': 'Select Destination directory', 'type': 'action', 'children': [
                    {'name': 'Destination directory:', 'type': 'str', 'value': self.destination_folder }
                ]},
                {'name': 'Update fields from directories', 'type': 'action'}
            ]},
            {'name': 'Date Range', 'type': 'group', 'children': [
                {'name': 'Start', 'type': 'str', 'value': self.settings['start'] },
                {'name': 'End', 'type': 'str', 'value': self.settings['end']},
                ]},
            ScalableGroup(name='Animal id: [TID1,TID2,...],fs', children=self.animal_dict)]

        ## Create tree of Parameter objects
        self.p = Parameter.create(name='params', type='group', children=self.params)
        self.p.param('Directories', 'Select NDF directory').sigActivated.connect(self.selectNDFFolder)
        self.p.param('Directories', 'Select NDF directory','NDF directory:').sigValueChanged.connect(self.setNDFFolder)
        self.p.param('Directories', 'Select Destination directory').sigActivated.connect(self.selectDestinationFolder)
        self.p.param('Directories', 'Select Destination directory', 'Destination directory:').sigValueChanged.connect(
            self.setDestinationFolder)
        self.p.param('Directories', 'Update fields from directories').sigActivated.connect(self.updateFieldsFromDirectories)

        self.t = PyecogParameterTree()
        self.t.setParameters(self.p, showTop=False)
        self.t.headerItem().setHidden(True)

        layout.addWidget(self.t)
        layout.setRowStretch(0,10)
        layout.setRowMinimumHeight(0,400)
        layout.setColumnMinimumWidth(0,600)
        layout.addWidget(self.button3)
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

    def selectNDFFolder(self):
        dialog = QFileDialog(self)
        dialog.setDirectory(self.folder2convert)
        dialog.setWindowTitle('Select NDF directory')
        dialog.setFileMode(QFileDialog.DirectoryOnly)
        # dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        if dialog.exec():
            self.p.param('Directories','Select NDF directory','NDF directory:').setValue(dialog.selectedFiles()[0])
        else:
            sys.stderr.write('No folder selected\n')

    def setNDFFolder(self, folder2convertParam):
        self.folder2convert = folder2convertParam.value()

    def updateFieldsFromDirectories(self):
        print('Inspecting',self.folder2convert)
        ndf_files = glob.glob(self.folder2convert + os.path.sep + '*.ndf')
        ndf_files.sort()
        print('Converting folder:', self.folder2convert)
        print('There are', len(ndf_files), ' *.ndf files to convert...')
        if len(ndf_files) == 0:
            print('Folder does not have *.ndf files to convert!')
            return

        start_timestamp = int(os.path.split(ndf_files[0])[-1][1:-4])
        end_timestamp = int(os.path.split(ndf_files[-1])[-1][1:-4])
        self.p.param('Date Range','Start').setValue(datetime.fromtimestamp(start_timestamp).strftime(self.dfrmt))
        self.p.param('Date Range','End').setValue(datetime.fromtimestamp(end_timestamp).strftime(self.dfrmt))
        print('testing file',ndf_files[0])
        test_file = NdfFile(ndf_files[0])
        test_file.read_file_metadata()
        test_file.get_valid_tids_and_fs()
        print('Found TIDs', test_file.tid_set, ' valid in first file (there might be more in other files)')
        self.animal_dict.clear()
        for i, id in enumerate(test_file.tid_set):
            self.animal_dict.append({'name': 'Animal ' + str(i+1),
                                     'type': 'str',
                                     'value': '[' + str(id) + '],' + str(test_file.tid_to_fs_dict[id]) ,
                                     'renamable': True,
                                     'removable': True})

        self.p.param('Animal id: [TID1,TID2,...],fs').clearChildren()
        self.p.param('Animal id: [TID1,TID2,...],fs').addChildren(self.animal_dict)


    def selectDestinationFolder(self):
        dialog = QFileDialog(self)
        dialog.setDirectory(self.destination_folder)
        dialog.setWindowTitle('Select Destination directory')
        dialog.setFileMode(QFileDialog.DirectoryOnly)
        # dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        if dialog.exec():
            self.p.param('Directories',
                         'Select Destination directory',
                         'Destination directory:').setValue(dialog.selectedFiles()[0])

    def setDestinationFolder(self,destinationFolderParam):
        self.destination_folder = destinationFolderParam.value()
        print('Saving files to folder:', self.destination_folder)

    def runConvertFiles(self):
        worker = Worker(self.convertFiles)
        print('Starting file conversion...')
        self.threadpool.start(worker)

    def convertFiles(self):
        start_string = self.p.param('Date Range', 'Start').value()
        start_file_name = 'M' + str(int(datetime.strptime(start_string, self.dfrmt).timestamp())) + '.ndf'
        end_string = self.p.param('Date Range', 'End').value()
        end_file_name = 'M' + str(int(datetime.strptime(end_string, self.dfrmt).timestamp())) + '.ndf'

        self.folder2convert = os.path.normpath(self.folder2convert)
        self.destination_folder = os.path.normpath(self.destination_folder)
        self.settings['NDFdir'] = self.folder2convert
        self.settings['H5dir'] = self.destination_folder
        self.settings['start'] = start_string
        self.settings['end'] = end_string
        self.settings['AnimalDictList'] = [{'id': a.name(),
                                             'tidfs': a.value()} for a in self.p.param('Animal id: [TID1,TID2,...],fs').children()]

        self.files2convert = [os.path.join(self.folder2convert, f) for f in os.listdir(self.folder2convert)
                              if (start_file_name <= f <= end_file_name)]
        print(len(self.files2convert), 'files between:', start_file_name, 'and', end_file_name)
        for a in self.p.param('Animal id: [TID1,TID2,...],fs').children():
            dh = DataHandler()
            print('***\n Starting to convert', a.name(), a.value(),'\n***')
            tidfs = a.value().split(']')
            tids = tidfs[0]+']'
            if len(tidfs)>1:
                fs = tidfs[1][1:] # remove the coma
            else:
                fs = 'auto'
            animal_destination_folder = self.destination_folder + os.sep + a.name()
            if not os.path.isdir(self.destination_folder):
                os.mkdir(self.destination_folder)
            if not os.path.isdir(animal_destination_folder):
                os.mkdir(animal_destination_folder)
            dh.convert_ndf_directory_to_h5(self.files2convert,tids=tids,save_dir=animal_destination_folder,fs=fs)
        return (1,1) # wavelet worker expects to emit tuple when done...





if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = NDFConverterWindow()
    window.setGeometry(500, 300, 300, 200)
    window.show()
    sys.exit(app.exec_())