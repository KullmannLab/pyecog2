import os
import sys
import webbrowser

import numpy as np
from PyQt5 import QtCore, QtGui
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt, QSettings, QByteArray, QObject
from PyQt5.QtWidgets import QApplication, QPlainTextEdit, QTextEdit, QDockWidget, QMainWindow, QFileDialog

from pyecog2.ProjectClass import Project, Animal
from pyecog2.annotation_table_widget import AnnotationTableWidget
from pyecog2.annotations_module import AnnotationElement, AnnotationPage
from pyecog2.coding_tests.AnnotationParameterTree import AnnotationParameterTee
from pyecog2.coding_tests.FFT import FFTwindow
from pyecog2.coding_tests.ProjectGUI import ProjectEditWindow
from pyecog2.coding_tests.VideoPlayer import VideoWindow
from pyecog2.coding_tests.WaveletWidget import WaveletWindow
from pyecog2.coding_tests.convert_ndf_folder_gui import NDFConverterWindow
from pyecog2.paired_graphics_view import PairedGraphicsView
from pyecog2.tree_model_and_nodes import TreeModel
from pyecog2.tree_widget import FileTreeElement
from pyecog2.coding_tests.plot_controls import PlotControls

#
class MainModel(QObject):
    sigTimeChanged      = QtCore.Signal(object)
    sigWindowChanged    = QtCore.Signal(object)
    sigProjectChanged   = QtCore.Signal()

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

    def update_filter_settings(self):
        pass

    def update_xrange_settings(self,xrange):
        pass

class MainWindow(QMainWindow):
    '''
    basically handles the combination of the the tree menu bar and the paired view

    Most of the code here is for setting up the geometry of the gui and the
    menu bar stuff
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
        self.main_model.sigProjectChanged.connect(lambda: self.tree_element.set_rootnode_from_project(self.main_model.project))
        self.dock_list['File Tree'] = QDockWidget("File Tree", self)
        self.dock_list['File Tree'].setWidget(self.tree_element.widget)
        self.dock_list['File Tree'].setFloating(False)
        self.dock_list['File Tree'].setObjectName("File Tree")
        self.dock_list['File Tree'].setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea | Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        self.dock_list['File Tree'].setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)

        self.plot_controls = PlotControls(self.main_model)
        self.plot_controls.sigUpdateXrange_i.connect(self.paired_graphics_view.insetview_set_xrange)
        self.plot_controls.sigUpdateXrange_o.connect(self.paired_graphics_view.overview_set_xrange)
        self.plot_controls.sigUpdateFilter.connect(self.paired_graphics_view.updateFilterSettings)
        self.dock_list['Plot Controls'] = QDockWidget("Plot controls", self)
        self.dock_list['Plot Controls'].setWidget(self.plot_controls)
        self.dock_list['Plot Controls'].setFloating(False)
        self.dock_list['Plot Controls'].setObjectName("Plot Controls")
        self.dock_list['Plot Controls'].setAllowedAreas(
            Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea | Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        self.dock_list['Plot Controls'].setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)

        self.dock_list['Hints'] = QDockWidget("Hints", self)
        text_edit = QTextEdit()
        text = open('HelperHints.md').read()
        text_edit.setMarkdown(text)
        self.dock_list['Hints'].setWidget(text_edit)
        self.dock_list['Hints'].setObjectName("Hints")

        self.annotation_table = AnnotationTableWidget(self.main_model.annotations)
        self.dock_list['Annotations Table'] = QDockWidget("Annotations Table", self)
        self.dock_list['Annotations Table'].setWidget(self.annotation_table)
        self.dock_list['Annotations Table'].setObjectName("Annotations Table")
        self.dock_list['Annotations Table'].setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)

        self.annotation_parameter_tree = AnnotationParameterTee(self.main_model.annotations)
        self.dock_list['Annotation Parameter Tree'] = QDockWidget("Annotation Parameter Tree", self)
        self.dock_list['Annotation Parameter Tree'].setWidget(self.annotation_parameter_tree)
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
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_list['Plot Controls'])
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_list['Annotation Parameter Tree'])
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_list['Annotations Table'])
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_list['Hints'])
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_list['Video'])
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_list['Wavelet'])
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_list['FFT'])


        settings = QSettings("PyEcog","PyEcog")
        settings.beginGroup("StandardMainWindow")
        settings.setValue("windowGeometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        settings.endGroup()

        self.settings = QSettings("PyEcog", "PyEcog")
        print("reading configurations from: " + self.settings.fileName())
        self.settings.beginGroup("MainWindow")
        # print(self.settings.value("windowGeometry", type=QByteArray))
        self.restoreGeometry(self.settings.value("windowGeometry", type=QByteArray))
        self.restoreState(self.settings.value("windowState", type=QByteArray))

        try:
            settings = QSettings("PyEcog","PyEcog")
            settings.beginGroup("ProjectSettings")
            fname = settings.value("ProjectFileName")
            print('Loading Project:', fname)
            self.show()
            self.load_project(fname)
            # self.main_model.project.load_from_json(fname)
            # self.main_model.project.load_from_json('/home/mfpleite/Shared/ele_data/proj.pyecog')
            # print(self.main_model.project.__dict__)
            self.tree_element.set_rootnode_from_project(self.main_model.project)
        except Exception as e:
            print('ERROR in tree build')
            print(e)

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

    def load_directory(self):
        print('0penening only folders with h5 files')
        selected_directory = self.select_directory()
        temp_animal = Animal(id='-', eeg_folder=selected_directory)
        temp_project = Project(self.main_model,eeg_data_folder=selected_directory, title=selected_directory)
        temp_project.add_animal(temp_animal)
        self.tree_element.set_rootnode_from_project(temp_project)
        self.main_model.project = temp_project

    def new_project(self):
        self.main_model.project.__init__(main_model=self.main_model)  #= Project(self.main_model)
        self.tree_element.set_rootnode_from_project(self.main_model.project)

    def load_project(self,fname = None):
        if type(fname) is not str:
            dialog = QFileDialog()
            dialog.setWindowTitle('Load Project ...')
            dialog.setFileMode(QFileDialog.AnyFile)
            # dialog.setOption(QFileDialog.DontUseNativeDialog, True)
            dialog.setAcceptMode(QFileDialog.AcceptOpen)
            dialog.setNameFilter('*.pyecog')
            if dialog.exec():
                fname = dialog.selectedFiles()[0]
        if type(fname) is str:
            print(fname)
            self.main_model.project.load_from_json(fname)
            self.tree_element.set_rootnode_from_project(self.main_model.project)
            init_time = min(self.main_model.project.current_animal.eeg_init_time)
            plot_range = np.array([init_time, init_time+3600])
            print('trying to plot ', plot_range)
            self.paired_graphics_view.set_scenes_plot_channel_data(plot_range)
            self.main_model.set_time_position(init_time)
            self.main_model.set_window_pos([init_time,init_time])


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
        dialog.setWindowTitle('Save Project as ...')
        dialog.setFileMode(QFileDialog.AnyFile)
        # dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setNameFilter('*.pyecog')
        if dialog.exec():
            fname = dialog.selectedFiles()[0]
            if not fname.endswith('.pyecog'):
                fname = fname + '.pyecog'
            print(fname)
            self.main_model.project.project_file = fname
            print('Saving project to:', self.main_model.project.project_file)
            self.main_model.project.save_to_json(fname)

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
        # dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.ShowDirsOnly, False)
        dialog.exec()
        return dialog.selectedFiles()[0]

    def reload_plot(self):
        #print('reload')
        xmin,xmax = self.paired_graphics_view.insetview_plot.vb.viewRange()[0]
        x_range = xmax-xmin
        # index = self.tree_element.tree_view.currentIndex()
        # self.tree_element.model.data(index, TreeModel.prepare_for_plot_role)
        self.main_model.project.file_buffer.clear_buffer()
        self.main_model.project.file_buffer.get_data_from_range([xmin,xmax],n_envelope=10,channel=0)
        buffer_x_max = self.main_model.project.file_buffer.get_t_max_for_live_plot()
        #print(full_xrange)
        print('reload_plot',buffer_x_max,xmax)
        if buffer_x_max > xmax:
            #print('called set xrange')
            self.paired_graphics_view.insetview_plot.vb.setXRange(buffer_x_max-x_range,buffer_x_max, padding=0)


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

    def openNDFconverter(self):
        print('opening NDF converter')
        self.ndf_converter = NDFConverterWindow()
        self.ndf_converter.show()

    def openProjectEditor(self):
        print('opening Project Editor')
        self.projectEditor = ProjectEditWindow(self.main_model.project)
        self.projectEditor.show()

    def export_annotations(self):
        dialog = QFileDialog()
        dialog.setWindowTitle('Export annotations as ...')
        dialog.setFileMode(QFileDialog.AnyFile)
        # dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setNameFilter('*.csv')
        if dialog.exec():
            fname = dialog.selectedFiles()[0]
            print(fname)
            print('Exporting annotations to:', fname)
            self.main_model.project.export_annotations(fname)

    def build_menubar(self):
        self.menu_bar = self.menuBar()

        # FILE section
        self.menu_file = self.menu_bar.addMenu("File")
        self.action_NDF_converter     = self.menu_file.addAction("Open NDF converter")
        self.menu_file.addSeparator()
        self.action_load_directory    = self.menu_file.addAction("Load directory")
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
        self.action_NDF_converter.triggered.connect(self.openNDFconverter)
        self.action_load_directory.triggered.connect(self.load_directory)
        self.action_quit.triggered.connect(self.close)
        self.actionLiveUpdate.triggered.connect(self.load_live_recording)

        # PROJECT section
        self.menu_project = self.menu_bar.addMenu("Project")
        self.action_edit_project = self.menu_project.addAction("Edit Project Settings")
        self.action_edit_project.triggered.connect(self.openProjectEditor)

        self.menu_project.addSeparator()
        self.action_new_project = self.menu_project.addAction("New Project")
        self.action_load_project = self.menu_project.addAction("Load Project")
        self.action_save = self.menu_project.addAction("Save Project")
        self.action_save.setShortcut('Ctrl+S')
        self.action_save_as = self.menu_project.addAction("Save Project as...")
        self.action_save_as.setShortcut('Ctrl+Shift+S')
        self.action_new_project.triggered.connect(self.new_project)
        self.action_load_project.triggered.connect(self.load_project)
        self.action_save.triggered.connect(self.save)
        self.action_save_as.triggered.connect(self.save_as)

        # ANNOTATIONS section
        self.menu_annotations = self.menu_bar.addMenu("Annotations")
        self.action_export_annotations = self.menu_annotations.addAction("Export to CSV")
        self.action_export_annotations.triggered.connect(self.export_annotations)
        self.action_import_annotations = self.menu_annotations.addAction("Import annotations")
        self.action_import_annotations.setDisabled(True)

        # CLASSIFIER section
        self.menu_classifier = self.menu_bar.addMenu("Classifier")
        self.action_setup_feature_extractor = self.menu_classifier.addAction("Setup feature extractor")
        self.action_run_feature_extractor = self.menu_classifier.addAction("Run feature extractor")
        self.action_setup_classifier = self.menu_classifier.addAction("Setup classifier")
        self.action_train_classifier = self.menu_classifier.addAction("Train classifier")
        self.action_run_classifier   = self.menu_classifier.addAction("Run classifier")
        self.action_review_classifications   = self.menu_classifier.addAction("Review classifications")
        self.action_setup_feature_extractor.setDisabled(True)
        self.action_run_feature_extractor.setDisabled(True)
        self.action_setup_classifier.setDisabled(True)
        self.action_train_classifier.setDisabled(True)
        self.action_run_classifier.setDisabled(True)
        self.action_review_classifications.setDisabled(True)

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
        self.menu_help.addSeparator()
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
        print('current project filename:',self.main_model.project.project_file)
        # for dock_name in self.dock_list.keys():
        #     settings.beginGroup(dock_name)
        #     settings.setValue("windowGeometry", self.dock_list[dock_name].saveGeometry())
        #     # settings.setValue("windowState", self.dock_list[dock_name].saveState())
        #     settings.endGroup()

        self.saveState()

    def keyPressEvent(self, evt):
        print('Key press captured by Main', evt.key())
        modifiers = evt.modifiers()
        if evt.key() == QtCore.Qt.Key_Space:
            print('Space pressed')
            self.video_element.play()
            return

        if evt.key() == QtCore.Qt.Key_Left:
            if modifiers == QtCore.Qt.ShiftModifier:
                self.paired_graphics_view.overview_page_left()
            else:
                self.paired_graphics_view.insetview_page_left()
            return

        if evt.key() == QtCore.Qt.Key_Right:
            if modifiers == QtCore.Qt.ShiftModifier:
                self.paired_graphics_view.overview_page_right()
            else:
                self.paired_graphics_view.insetview_page_right()
            return

        if evt.key() == QtCore.Qt.Key_Delete:
            # self.main_model.annotations.delete_annotation(self.main_model.annotations.focused_annotation)
            self.annotation_table.removeSelection()
            return

        numbered_keys = [QtCore.Qt.Key_1,QtCore.Qt.Key_2,QtCore.Qt.Key_3,QtCore.Qt.Key_4,QtCore.Qt.Key_5,
                         QtCore.Qt.Key_6,QtCore.Qt.Key_7,QtCore.Qt.Key_8,QtCore.Qt.Key_9,QtCore.Qt.Key_0]

        for i in range(len(numbered_keys)):
            if evt.key() == numbered_keys[i]:
                print(i+1,'pressed')
                label = self.annotation_parameter_tree.get_label_from_shortcut(i + 1)
                if label is not None:
                    if self.main_model.annotations.focused_annotation is None:
                        print('Adding new annotation')
                        new_annotation = AnnotationElement(label = label,
                                                           start = self.main_model.window[0],
                                                           end = self.main_model.window[1],
                                                           notes = '')
                        self.main_model.annotations.add_annotation(new_annotation)
                        self.main_model.annotations.focusOnAnnotation(new_annotation)
                    else:
                        print('Calling annotation_table changeSelectionLabel')
                        self.annotation_table.changeSelectionLabel(label)
                        # annotation = self.main_model.annotations.focused_annotation
                        # annotation.setLabel(self.main_model.annotations.labels[i])
                        # self.main_model.annotations.focusOnAnnotation(annotation)
                    return

if __name__ == '__main__':

    app = QApplication(sys.argv)
    app.setStyle("fusion")
    # Mikail feel free to play about if you feel so inclined :P
    # Now use a palette to switch to dark colors:
    # palette = QPalette()
    # palette.setColor(QPalette.Window, QColor(53, 53, 53))
    # palette.setColor(QPalette.WindowText, Qt.white)
    # palette.setColor(QPalette.Base, QColor(25, 25, 25))
    # palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    # palette.setColor(QPalette.ToolTipBase, Qt.black)
    # palette.setColor(QPalette.ToolTipText, Qt.white)
    # palette.setColor(QPalette.Text, Qt.white)
    # palette.setColor(QPalette.Button, QColor(53, 53, 53))
    # palette.setColor(QPalette.ButtonText, Qt.white)
    # palette.setColor(QPalette.BrightText, Qt.red)
    # palette.setColor(QPalette.Link, QColor(42, 130, 218))
    # palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    # palette.setColor(QPalette.HighlightedText, Qt.black)
    # app.setPalette(palette)

    screen = MainWindow()
    screen.get_available_screen()
    screen.show()
    sys.exit(app.exec_())
