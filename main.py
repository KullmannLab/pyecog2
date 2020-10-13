from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import QMenuBar, QGridLayout, QApplication, QWidget, QPlainTextEdit, QDockWidget, QMainWindow, QFileDialog
from PyQt5.QtCore import Qt, QSettings, QByteArray, QObject
import sys, os
import webbrowser
from coding_tests.VideoPlayer import VideoWindow
from coding_tests.AnnotationParameterTree import AnnotationParameterTee
from coding_tests.FFT import FFTwindow
from coding_tests.WaveletWidget import WaveletWindow
import numpy as np
import pyqtgraph_copy.pyqtgraph as pg

from tree_model_and_nodes import FileTreeProxyModel, TreeModel, FileNode, DirectoryNode
from paired_graphics_view import PairedGraphicsView
from tree_widget import FileTreeElement
from annotations_module import AnnotationElement, AnnotationPage
from annotation_table_widget import AnnotationTableWidget
from ProjectClass import Project, Animal

#
class MainModel(QObject):
    sigTimeChanged      = QtCore.Signal(object)
    sigWindowChanged    = QtCore.Signal(object)

    def __init__(self):
        super().__init__()
        self.data_eeg = np.array([])
        self.time_range = np.array([0,0])
        self.data_acc = np.array([])
        self.time_position = 0
        self.time_position_emited = self.time_position
        self.window = [0, 0]
        self.filenames_dict = {'eeg': '', 'meta' : '', 'anno': '', 'acc': ''}
        self.file_meta_dict = {}
        self.annotations = AnnotationPage()
        self.project = Project(self)

    def set_time_position(self, pos):
        self.time_position = pos
        # print('Current Time:', pos)
        if abs(pos - self.time_position_emited) > .01: # only emit signal if time_position actually changed
            self.time_position_emited = pos
            self.sigTimeChanged.emit(pos)
            print('Current Time emited:', pos)

    def set_window_pos(self, pos):
        if pos != self.window:
            self.window = pos
            self.sigWindowChanged.emit(pos)
            print('Window changesd to:', pos)

    # I think this became obsolete after implementing the Project Class.
    def update_eeg_range(self,x_range):
        print('Updating data range...')
        if x_range[0]<self.time_range[0]:
            dilated_x_range = np.array([x_range[0]-1,x_range[1]+1])  # dilate x_range to avoid too much repetitive loads in edge cases
            dilated_x_range = np.array([x_range[0],x_range[1]])  # dilate x_range to avoid too much repetitive loads in edge cases
            self.data_eeg, self.time_range = self.project.current_animal.get_data_from_range(dilated_x_range)



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

        # Populate Main window with widgets
        # self.createDockWidget()
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

        try:
            settings = QSettings("PyEcog","PyEcog")
            settings.beginGroup("ProjectSettings")
            fname = settings.value("ProjectFileName")
            print('Loading Projet:', fname)
            self.main_model.project.load_from_json(fname)
            # self.main_model.project.load_from_json('/home/mfpleite/Shared/ele_data/proj.pyecog')
            print(self.main_model.project.__dict__)
            self.tree_element.set_rootnode_from_project(self.main_model.project)
        except Exception as e:
            print('ERROR in tree build')
            print(e)

        self.dock_list['Text'] = QDockWidget("Text", self)
        self.dock_list['Text'].setWidget(QPlainTextEdit())
        self.dock_list['Text'].setObjectName("Text")

        self.dock_list['Annotations Table'] = QDockWidget("Annotations Table", self)
        self.dock_list['Annotations Table'].setWidget(AnnotationTableWidget(self.main_model.annotations))
        self.dock_list['Annotations Table'].setObjectName("Annotations Table")
        self.dock_list['Annotations Table'].setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)

        self.dock_list['Annotation Parameter Tree'] = QDockWidget("Annotation Parameter Tree", self)
        self.dock_list['Annotation Parameter Tree'].setWidget(AnnotationParameterTee(self.main_model.annotations))
        self.dock_list['Annotation Parameter Tree'].setObjectName("Annotation Parameter Tree")
        self.dock_list['Annotation Parameter Tree'].setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)

        self.video_element = VideoWindow(project=self.main_model.project)
        self.dock_list['Video'] = QDockWidget("Video", self)
        self.dock_list['Video'].setWidget(self.video_element)
        self.dock_list['Video'].setObjectName("Video")
        self.dock_list['Video'].setFloating(True)
        self.dock_list['Video'].hide()
        self.video_element.mediaPlayer.setNotifyInterval(40) # 25 fps
        # Video units are in miliseconds, pyecog units are in seconds
        self.video_element.sigTimeChanged.connect(self.main_model.set_time_position)
        self.main_model.sigTimeChanged.connect(self.video_element.setGlobalPosition)

        self.dock_list['FFT'] = QDockWidget("FFT", self)
        self.dock_list['FFT'].setWidget(FFTwindow(self.main_model))
        self.dock_list['FFT'].setObjectName("FFT")
        self.dock_list['FFT'].hide()

        self.dock_list['Wavelet'] = QDockWidget("Wavelet", self)
        self.dock_list['Wavelet'].setWidget(WaveletWindow(self.main_model))
        self.dock_list['Wavelet'].setObjectName("Wavelet")
        self.dock_list['Wavelet'].hide()

        self.setCentralWidget(self.paired_graphics_view.splitter)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_list['File Tree'])
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_list['Annotation Parameter Tree'])
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_list['Annotations Table'])
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_list['Text'])
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_list['FFT'])
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_list['Wavelet'])


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

    def new_project(self):
        self.main_model.project = Project(self.main_model)
        self.tree_element.set_rootnode_from_project(self.main_model.project)

    def load_project(self):
        dialog = QFileDialog()
        dialog.setWindowTitle('Load Project ...')
        dialog.setFileMode(QFileDialog.AnyFile)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setNameFilter('*.pyecog')
        if dialog.exec():
            fname = dialog.selectedFiles()[0]
            print(fname)
            self.main_model.project.load_from_json(fname)
            self.tree_element.set_rootnode_from_project(self.main_model.project)

    def save(self):
        print('save action triggered')
        fname = self.main_model.project.project_file
        if not os.path.isfile(fname):
            self.save_as()
        else:
            print('Saving project to:', fname)
            self.main_model.project.save_to_json(fname)

    def save_as(self):
        dialog = QFileDialog()
        dialog.setWindowTitle('Save as ...')
        dialog.setFileMode(QFileDialog.AnyFile)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setNameFilter('*.pyecog')
        if dialog.exec():
            fname = dialog.selectedFiles()[0]
            print(fname)
            self.main_model.project.project_file = fname
            print('Saving project to:', self.main_model.project.project_file)
            self.main_model.project.save_to_json(fname)

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

    def open_fft_window(self):
        self.dock_list['FFT'].show()
        self.dock_list['FFT'].widget().updateData()
        self.show()

    def open_wavelet_window(self):
        self.dock_list['Wavelet'].show()
        self.dock_list['Wavelet'].widget().update_data()
        self.show()


    def build_menubar(self):
        self.menu_bar = self.menuBar()

        # FILE section
        self.menu_file = self.menu_bar.addMenu("File")
        self.action_new_project     = self.menu_file.addAction("New Project")
        self.action_load_project    = self.menu_file.addAction("Load Project")
        self.action_save       = self.menu_file.addAction("Save")
        self.action_save.setShortcut('Ctrl+S')
        self.action_save_as       = self.menu_file.addAction("Save as...")
        self.action_save_as.setShortcut('Ctrl+Shift+S')
        self.menu_file.addSeparator()
        self.action_load_general    = self.menu_file.addAction("(Tempory) Load directory")
        self.action_load_h5    = self.menu_file.addAction("Load h5 directory")
        self.action_load_liete = self.menu_file.addAction("Load leite directory")
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
        self.action_new_project.triggered.connect(self.new_project)
        self.action_load_project.triggered.connect(self.load_project)
        self.action_load_general.triggered.connect(self.load_general)
        self.action_load_h5.triggered.connect(self.load_h5_directory)
        self.action_load_liete.triggered.connect(self.load_liete_directory)
        self.action_save.triggered.connect(self.save)
        self.action_save_as.triggered.connect(self.save_as)
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
        self.action_open_fft_window.triggered.connect(self.open_fft_window)

        self.action_open_morlet_window = self.menu_tools.addAction("Morlet Wavelet Transform")
        self.action_open_morlet_window.triggered.connect(self.open_wavelet_window)

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

        settings.beginGroup("ProjectSettings")
        settings.setValue("ProjectFileName", self.main_model.project.project_file)
        settings.endGroup()
        #
        # for dock_name in self.dock_list.keys():
        #     settings.beginGroup(dock_name)
        #     settings.setValue("windowGeometry", self.dock_list[dock_name].saveGeometry())
        #     # settings.setValue("windowState", self.dock_list[dock_name].saveState())
        #     settings.endGroup()

        self.saveState()

    def keyPressEvent(self, evt):
        print('Key press captured by Main', evt.key())
        if evt.key() == QtCore.Qt.Key_Space:
            print('Space pressed')
            self.video_element.play()
            return

        if evt.key() == QtCore.Qt.Key_Delete:
            self.main_model.annotations.delete_annotation(self.main_model.annotations.focused_annotation)
            return

        numbered_keys = [QtCore.Qt.Key_1,QtCore.Qt.Key_2,QtCore.Qt.Key_3,QtCore.Qt.Key_4,QtCore.Qt.Key_5,
                         QtCore.Qt.Key_6,QtCore.Qt.Key_7,QtCore.Qt.Key_8,QtCore.Qt.Key_9,QtCore.Qt.Key_0]

        for i in range(len(self.main_model.annotations.labels)):
            if evt.key() == numbered_keys[i]:
                print(i+1,'pressed')
                if self.main_model.annotations.focused_annotation is None:
                    new_annotation = AnnotationElement(label = self.main_model.annotations.labels[i],
                                                       start = self.main_model.window[0],
                                                       end = self.main_model.window[1],
                                                       notes = '')
                    self.main_model.annotations.add_annotation(new_annotation)
                    self.main_model.annotations.focusOnAnnotation(new_annotation)
                else:
                    annotation = self.main_model.annotations.focused_annotation
                    annotation.setLabel(self.main_model.annotations.labels[i])
                    # a bit of a pity that this signal cannot be emited by the anotation
                    self.main_model.annotations.sigLabelsChanged.emit(self.main_model.annotations.labels[i])
                    self.main_model.annotations.focusOnAnnotation(annotation)
                return

if __name__ == '__main__':

    app = QApplication(sys.argv)
    screen = MainWindow()
    screen.get_available_screen()
    screen.show()
    sys.exit(app.exec_())
