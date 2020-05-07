from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QMenuBar, QGridLayout, QApplication, QWidget, QPlainTextEdit, QDockWidget, QMainWindow, QFileDialog
from PyQt5.QtCore import Qt, QSettings, QByteArray, QObject
import sys, os
import webbrowser
from coding_tests.VideoPlayer import VideoWindow
import numpy as np
import pyqtgraph_copy.pyqtgraph as pg

from tree_model_and_nodes import FileTreeProxyModel, TreeModel, FileNode, DirectoryNode
from paired_graphics_view import PairedGraphicsView
from tree_widget import FileTreeElement
from annotations_module import Annotations
#
class MainModel(QObject):

    sigTimeChanged = QtCore.Signal(object)
    def __init__(self):
        super().__init__()
        self.data_eeg = np.array([])
        self.data_acc = np.array([])
        self.time_position = 0
        self.time_window = [0,0]
        self.filenames_dict = {'eeg': '', 'meta' : '', 'anno': '', 'acc': ''}
        self.file_meta_dict = {}
        self.annotations = Annotations()

    def set_time_position(self, pos):
        if pos != self.pos: # only emit signal if time_position actually changed
            self.sigTimeChanged.emit(self)
            self.time_position = pos
            print('Current Time:', pos)



class MainWindow(QMainWindow):
    '''
    basicvally handles the combination of the the three menu bar and the paired view

    Most of the code here is for setting up the geometry of the gui and the
    menubar stuff
    '''
    def __init__(self):
        super().__init__()

        # Initialize Main Window geometry
        self.title = "PyEcog Main"
        (size, rect) = self.get_available_screen()
        self.setWindowIcon(QtGui.QIcon("icon.png"))
        self.setWindowTitle(self.title)
        self.setGeometry(0, 0, size.width(), size.height())

        self.main_model = MainModel()
        # Just for testing purpouses
        self.main_model.annotations = Annotations({'seizure': [[1, 10], [13, 15]],
                                             'spike': [[11, 12], [15, 16]],
                                             'artefact': [[24, 28]]})

        # Populate Main window with widgets
        # self.createDockWidget()y
        self.build_menubar()
        self.dock_list = {}
        self.paired_graphics_view = PairedGraphicsView(parent=self)

        self.tree_element = FileTreeElement(parent=self)
        self.dock_list['File Tree'] = QDockWidget("File Tree", self)
        self.dock_list['File Tree'].setWidget(self.tree_element.widget)
        self.dock_list['File Tree'].setFloating(False)
        self.dock_list['File Tree'].setObjectName("File Tree")
        self.dock_list['File Tree'].setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea | Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        self.dock_list['File Tree'].setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)

        self.dock_list['Text'] = QDockWidget("Text", self)
        self.dock_list['Text'].setWidget(QPlainTextEdit())
        self.dock_list['Text'].setObjectName("Text")

        self.dock_list['Video'] = QDockWidget("Video", self)
        self.dock_list['Video'].setWidget(VideoWindow())
        self.dock_list['Video'].setObjectName("Video")
        self.dock_list['Video'].setFloating(True)
        self.dock_list['Video'].hide()

        self.setCentralWidget(self.paired_graphics_view.splitter)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_list['File Tree'])
        self.addDockWidget(Qt.LeftDockWidgetArea,self.dock_list['Text'])

        # Clear this after sorting out how to beter save workspaces
        try:
            self.tree_element.set_rootnode_from_folder('/home/mfpleite/PycharmProjects/pyecog2/Notebooks', '.h5')
        except:
            pass

        settings = QSettings("PyEcog","PyEcog")
        settings.beginGroup("StandardMainWindow")
        settings.setValue("windowGeometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        settings.endGroup()

        self.settings = QSettings("PyEcog", "PyEcog")
        print("reading cofigurations from: " + self.settings.fileName())
        self.settings.beginGroup("MainWindow")
        # print(self.settings.value("windowGeometry", type=QByteArray))
        self.restoreGeometry(self.settings.value("windowGeometry", type=QByteArray))
        self.restoreState(self.settings.value("windowState", type=QByteArray))
        #
        # for dock_name in self.dock_list.keys(): # This is unessecary, because restoreState of the parent window already works
        #     self.settings.beginGroup(dock_name)
        #     self.dock_list[dock_name].restoreGeometry(self.settings.value("windowGeometry", type=QByteArray))
        #     # self.dock_list[dock_name].restoreState(self.settings.value("windowState", type=QByteArray))

        # self.show()


        ########################################################
        # Below here we have code for debugging and development

        #root_folder = self.tree_element.get_default_folder()
        #folder = '/media/jonathan/DATA/seizure_data/gabrielle/All_DATA/EEG DATA CRISPRa Kcna1 2018/4_CRISP Oct-Nov 2018/CRISPRa_h5s BASELINE'
        #folder = '/media/jonathan/DATA/seizure_data/gabrielle/All_DATA/EEG DATA CRISPRa Kcna1 2018/4_CRISP Oct-Nov 2018'

        #self.tree_element.set_rootnode_from_folder(folder, filetype_restriction = '.h5')

        #self.tree_element.set_rootnode_from_folder(os.getcwd())
        #testing automatic selection
        #self.tree_element.tree_view.setRootIndex()
        #index = self.tree_element.tree_view.currentIndex()
        #index = self.tree_element.model.createIndex(0,0)
        #self.tree_element.tree_view.setTreePosition(0)
        #index = QtCore.QModelIndex()
        #self.tree_element.tree_view.setCurrentIndex(index)

    def get_available_screen(self):
        app = QApplication.instance()
        screen = app.primaryScreen()
        print('Screen: %s' % screen.name())
        size = screen.size()
        print('Size: %d x %d' % (size.width(), size.height()))
        rect = screen.availableGeometry()
        print('Available: %d x %d' % (rect.width(), rect.height()))
        return (size,rect)

    def reset_geometry(self):
        self.settings = QSettings("PyEcog", "PyEcog")
        # print("reading cofigurations from: " + self.settings.fileName())
        self.settings.beginGroup("StandardMainWindow")
        print(self.settings.value("windowGeometry", type=QByteArray))
        self.restoreGeometry(self.settings.value("windowGeometry", type=QByteArray))
        self.restoreState(self.settings.value("windowState", type=QByteArray))
        self.show()

    def load_h5_directory(self):
        print('0penening only folders with h5 files')
        selected_directory = self.select_directory()
        self.tree_element.set_rootnode_from_folder(selected_directory,'.h5')

    def load_liete_directory(self):
        print('Load new file types...')

    def save(self):
        print('save action triggered')

    def load_general(self):
        selected_directory = self.select_directory()
        self.tree_element.set_rootnode_from_folder(selected_directory)

    def select_directory(self, label_text='Select a directory'):
        '''
        Method launches a dialog allow user to select a directory
        '''
        dialog = QFileDialog()
        dialog.setWindowTitle(label_text)
        dialog.setFileMode(QFileDialog.DirectoryOnly)
        # we might want to set home directory using settings
        # for now rely on default behaviour
        '''
        home = os.path.expanduser("~") # default, if no settings available
        dialog.setDirectory(home)
        '''
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.ShowDirsOnly, False)
        dialog.exec()
        return dialog.selectedFiles()[0]

    def reload_plot(self):
        #print('reload')
        index = self.tree_element.tree_view.currentIndex()
        self.tree_element.model.data(index, TreeModel.prepare_for_plot_role)
        full_xrange = self.paired_graphics_view.overview_plot.vb.viewRange()[0][1]
        #print(full_xrange)
        xmin,xmax = self.paired_graphics_view.insetview_plot.vb.viewRange()[0]
        x_range=xmax-xmin
        if full_xrange > x_range:
            #print('called set xrange')
            self.paired_graphics_view.insetview_plot.vb.setXRange(full_xrange-x_range,full_xrange, padding=0)


    def load_live_recording(self):
        '''
        This should just change the graphics view/ file node to keep
        reloading?
        '''
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.reload_plot)
        if self.actionLiveUpdate.isChecked():
            self.timer.start(100)

    def open_git_url(self):
        webbrowser.open('https://github.com/KullmannLab/pyecog2')

    def open_docs_url(self):
        webbrowser.open('https://jcornford.github.io/pyecog_docs/')

    def open_video_window(self):
        self.dock_list['Video'].show()
        self.show()

    def build_menubar(self):
        self.menu_bar = self.menuBar()

        # FILE section
        self.menu_file = self.menu_bar.addMenu("File")
        self.action_load_general    = self.menu_file.addAction("(Tempory) Load directory")
        self.action_load_h5    = self.menu_file.addAction("Load h5 directory")
        self.action_load_liete = self.menu_file.addAction("Load leite directory")
        self.action_save       = self.menu_file.addAction("Save")
        self.menu_file.addSeparator()
        self.actionLiveUpdate  = self.menu_file.addAction("Live Recording")
        self.actionLiveUpdate.setCheckable(True)
        self.actionLiveUpdate.toggled.connect(self.load_live_recording)
        self.actionLiveUpdate.setChecked(False)
        #self.live_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_L), self)
        #self.live_shortcut.connect()
        self.actionLiveUpdate.setShortcut('Ctrl+L')

        self.menu_file.addSeparator()
        self.action_quit       = self.menu_file.addAction("Quit")
        self.action_load_general.triggered.connect(self.load_general)
        self.action_load_h5.triggered.connect(self.load_h5_directory)
        self.action_load_liete.triggered.connect(self.load_liete_directory)
        self.action_save.triggered.connect(self.save)
        self.action_quit.triggered.connect(self.close)
        self.actionLiveUpdate.triggered.connect(self.load_live_recording)

        # ANNOTATIONS section
        self.menu_annotations = self.menu_bar.addMenu("Annotations")
        self.action_save_annotations = self.menu_annotations.addAction("Save annotations")
        self.action_export_annotations = self.menu_annotations.addAction("Export annotations")
        self.action_import_annotations = self.menu_annotations.addAction("Import annotations")

        # CLASSIFIER section
        self.menu_classifier = self.menu_bar.addMenu("Classifier")
        self.action_setup_feature_extractor = self.menu_classifier.addAction("Setup feature extractor")
        self.action_setup_classifier = self.menu_classifier.addAction("Setup classifier")
        self.action_train_classifier = self.menu_classifier.addAction("Train classifier")
        self.action_run_classifier   = self.menu_classifier.addAction("Run classifier")
        self.action_review_classifications   = self.menu_classifier.addAction("Review classifications")

        # TOOLS section
        self.menu_tools = self.menu_bar.addMenu("Tools")
        self.action_open_video_window = self.menu_tools.addAction("Video")
        self.action_open_video_window.triggered.connect(self.open_video_window)
        # To do
        self.action_open_fft_window = self.menu_tools.addAction("FFT")
        self.action_open_morlet_window = self.menu_tools.addAction("Morlet Wavelet Transform")

        # HELP section
        self.menu_help = self.menu_bar.addMenu("Help")
        self.action_reset_geometry    = self.menu_help.addAction("Reset Main Window layout")
        self.action_reset_geometry.triggered.connect(self.reset_geometry)

        self.action_go_to_git = self.menu_help.addAction("Go to Git Repository")
        self.action_go_to_git.triggered.connect(self.open_git_url)

        self.action_go_to_doc = self.menu_help.addAction("Go to web documentation")
        self.action_go_to_doc.triggered.connect(self.open_docs_url)

        self.menu_bar.setNativeMenuBar(False)

        #self.menubar.addMenu("Edit")
        #self.menubar.addMenu("View")

    def closeEvent(self, event):
        print('closing')
        settings = QSettings("PyEcog","PyEcog")
        settings.beginGroup("MainWindow")
        settings.setValue("windowGeometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        settings.endGroup()
        #
        # for dock_name in self.dock_list.keys():
        #     settings.beginGroup(dock_name)
        #     settings.setValue("windowGeometry", self.dock_list[dock_name].saveGeometry())
        #     # settings.setValue("windowState", self.dock_list[dock_name].saveState())
        #     settings.endGroup()

        self.saveState()

if __name__ == '__main__':

    app = QApplication(sys.argv)
    screen = MainWindow()
    screen.get_available_screen()
    screen.show()
    sys.exit(app.exec_())
