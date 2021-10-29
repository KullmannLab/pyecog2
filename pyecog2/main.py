import os

os.environ['QT_MULTIMEDIA_PREFERRED_PLUGINS'] = 'windowsmediafoundation'
import sys
import webbrowser

import numpy as np
from PySide2 import QtCore, QtGui
from PySide2.QtGui import QPalette, QColor
from PySide2.QtCore import Qt, QSettings, QByteArray, QObject
from PySide2.QtWidgets import QApplication, QPlainTextEdit, QTextEdit, QTextBrowser, QDockWidget, QMainWindow, \
    QFileDialog, QMessageBox

from pyecog2.ProjectClass import Project, Animal, MainModel
from pyecog2.annotation_table_widget import AnnotationTableWidget
from pyecog2.annotations_module import AnnotationElement, AnnotationPage
from pyecog2.coding_tests.AnnotationParameterTree import AnnotationParameterTee
from pyecog2.coding_tests.FFT import FFTwindow
from pyecog2.coding_tests.ProjectGUI import ProjectEditWindow
from pyecog2.coding_tests.VideoPlayer import VideoWindow
from pyecog2.coding_tests.WaveletWidget import WaveletWindow
from pyecog2.coding_tests.convert_ndf_folder_gui import NDFConverterWindow
from pyecog2.coding_tests.FeatureExtractorGUI import FeatureExtractorWindow
from pyecog2.coding_tests.ClassifierGUI import ClassifierWindow
from pyecog2.paired_graphics_view import PairedGraphicsView
from pyecog2.tree_widget import FileTreeElement
from pyecog2.coding_tests.plot_controls import PlotControls
from datetime import datetime
import pyqtgraph as pg
from pyqtgraph.console import ConsoleWidget
import pkg_resources
from pyecog2 import license
from multiprocessing import freeze_support

class MainWindow(QMainWindow):
    '''
    basically handles the combination of the the tree menu bar and the paired view

    Most of the code here is for setting up the geometry of the gui and the
    menu bar stuff
    '''

    def __init__(self, app_handle=None):
        super().__init__()
        self.app_handle = app_handle
        if os.name == 'posix':
            pyecog_string = '🇵 🇾 🇪 🇨 🇴 🇬'
        else:
            pyecog_string = 'PyEcog'
        print('\n', pyecog_string, '\n')
        print(os.getcwd())
        # Initialize Main Window geometry
        # self.title = "ℙ𝕪𝔼𝕔𝕠𝕘"
        self.title = pyecog_string
        (size, rect) = self.get_available_screen()
        icon_file = pkg_resources.resource_filename('pyecog2', 'icons/icon.png')
        print('ICON:', icon_file)
        self.setWindowIcon(QtGui.QIcon(icon_file))
        self.app_handle.setWindowIcon(QtGui.QIcon(icon_file))
        self.setWindowTitle(self.title)
        self.setGeometry(0, 0, size.width(), size.height())
        # self.setWindowFlags(QtCore.Qt.FramelessWindowHint) # fooling around
        # self.setWindowFlags(QtCore.Qt.CustomizeWindowHint| QtCore.Qt.Tool)
        # self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.main_model = MainModel()
        self.autosave_timer = QtCore.QTimer()
        self.autosave_timer.timeout.connect(self.auto_save)
        self.live_recording_timer = QtCore.QTimer()
        self.live_recording_timer.timeout.connect(self.reload_plot)

        self.check_license()

        # Populate Main window with widgets
        # self.createDockWidget()
        self.dock_list = {}
        self.paired_graphics_view = PairedGraphicsView(parent=self)

        self.tree_element = FileTreeElement(parent=self)
        self.main_model.sigProjectChanged.connect(
            lambda: self.tree_element.set_rootnode_from_project(self.main_model.project))
        self.dock_list['File Tree'] = QDockWidget("File Tree", self)
        self.dock_list['File Tree'].setWidget(self.tree_element.widget)
        self.dock_list['File Tree'].setFloating(False)
        self.dock_list['File Tree'].setObjectName("File Tree")
        self.dock_list['File Tree'].setAllowedAreas(
            Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea | Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
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
        self.text_edit = QTextBrowser()
        hints_file = pkg_resources.resource_filename('pyecog2', 'HelperHints.md')
        # text = open('HelperHints.md').read()
        print('hints file:', hints_file)
        text = open(hints_file).read()
        text = text.replace('icons/banner_small.png',
                            pkg_resources.resource_filename('pyecog2', 'icons/banner_small.png'))
        self.text_edit.setMarkdown(text)
        self.dock_list['Hints'].setWidget(self.text_edit)
        self.dock_list['Hints'].setObjectName("Hints")
        # self.dock_list['Hints'].setFloating(False)
        # self.dock_list['Hints'].setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)

        self.annotation_table = AnnotationTableWidget(self.main_model.annotations,
                                                      self)  # passing self as parent in position 2
        self.dock_list['Annotations Table'] = QDockWidget("Annotations Table", self)
        self.dock_list['Annotations Table'].setWidget(self.annotation_table)
        self.dock_list['Annotations Table'].setObjectName("Annotations Table")
        self.dock_list['Annotations Table'].setFeatures(QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)

        self.annotation_parameter_tree = AnnotationParameterTee(self.main_model.annotations)
        self.dock_list['Annotation Parameter Tree'] = QDockWidget("Annotation Parameter Tree", self)
        self.dock_list['Annotation Parameter Tree'].setWidget(self.annotation_parameter_tree)
        self.dock_list['Annotation Parameter Tree'].setObjectName("Annotation Parameter Tree")
        self.dock_list['Annotation Parameter Tree'].setFeatures(
            QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetMovable)

        self.video_element = VideoWindow(main_model=self.main_model)
        self.dock_list['Video'] = QDockWidget("Video", self)
        self.dock_list['Video'].setWidget(self.video_element)
        self.dock_list['Video'].setObjectName("Video")
        # self.dock_list['Video'].setFloating(True)
        # self.dock_list['Video'].hide()

        self.dock_list['FFT'] = QDockWidget("FFT", self)
        self.dock_list['FFT'].setWidget(FFTwindow(self.main_model))
        self.dock_list['FFT'].setObjectName("FFT")
        # self.dock_list['FFT'].hide()

        self.dock_list['Wavelet'] = QDockWidget("Wavelet", self)
        self.dock_list['Wavelet'].setWidget(WaveletWindow(self.main_model))
        self.dock_list['Wavelet'].setObjectName("Wavelet")
        # self.dock_list['Wavelet'].hide()

        self.dock_list['Console'] = QDockWidget("Console", self)
        self.dock_list['Console'].setWidget(ConsoleWidget(namespace={'MainWindow': self}))
        self.dock_list['Console'].setObjectName("Console")
        self.dock_list['Console'].hide()

        self.build_menubar()

        self.setCentralWidget(self.paired_graphics_view.splitter)

        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_list['Console'])
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_list['File Tree'])
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_list['Hints'])
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_list['Plot Controls'])
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_list['Video'])
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_list['Annotation Parameter Tree'])
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_list['Annotations Table'])
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_list['FFT'])
        self.setCorner(Qt.BottomLeftCorner, Qt.LeftDockWidgetArea)
        self.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_list['Wavelet'])
        # self.tabifyDockWidget(self.dock_list['Hints'], self.dock_list['File Tree'])
        self.resizeDocks([self.dock_list['File Tree'], self.dock_list['Hints'], self.dock_list['Plot Controls'],
                          self.dock_list['Video']], [350, 100, 100, 300], Qt.Vertical)
        self.resizeDocks([self.dock_list['Wavelet']], [400], Qt.Vertical)
        self.resizeDocks([self.dock_list['Video']], [400], Qt.Vertical)
        self.resizeDocks([self.dock_list['Video']], [400], Qt.Horizontal)
        self.resizeDocks([self.dock_list['FFT']], [400], Qt.Vertical)
        self.resizeDocks([self.dock_list['FFT']], [400], Qt.Horizontal)

        settings = QSettings("PyEcog", "PyEcog")
        settings.beginGroup("StandardMainWindow")
        settings.setValue("windowGeometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        settings.setValue("darkMode", False)
        settings.setValue("autoSave", True)
        settings.endGroup()

        self.settings = QSettings("PyEcog", "PyEcog")
        print("Reading GUI configurations from: " + self.settings.fileName())
        self.settings.beginGroup("MainWindow")
        # print(self.settings.value("windowGeometry", type=QByteArray))
        try:
            self.restoreGeometry(self.settings.value("windowGeometry"))
        except Exception as e:
            print('Error restoring geometry')
            print(e)
        try:
            self.restoreState(self.settings.value("windowState"))
        except Exception as e:
            print('Error restiring state')
            print(e)

        self.action_darkmode.setChecked(self.settings.value("darkMode", type=bool))
        self.toggle_darkmode()  # pre toggle darkmode to make sure project loading dialogs are made with the correct color pallete
        try:
            settings = QSettings("PyEcog", "PyEcog")
            settings.beginGroup("ProjectSettings")
            fname = settings.value("ProjectFileName")
            self.show()
            if fname.endswith('.pyecog'):
                print('Loading last opened Project:', fname)
                self.load_project(fname)
            else:
                print('Loading last opened directory:', fname)
                self.load_directory(fname)
        except Exception as e:
            print('ERROR in tree build')
            print(e)

        self.action_darkmode.setChecked(self.settings.value("darkMode", type=bool))
        self.toggle_darkmode()  # toggle again darkmode just to make sure the wavelet window and FFT are updated as well
        self.action_autosave.setChecked(self.settings.value("autoSave", type=bool))
        self.toggle_auto_save()


    def check_license(self):
        # Check if license is valid
        license_is_valid = False
        try:
            if license.verify_license_file():
                license_is_valid = True
            else:
                msg = QMessageBox(parent=self)
                msg.setIcon(QMessageBox.Information)
                msg.setText("Your license seems to be invalid. Do you have an activated PyEcogLicense.txt file?")
                msg.setWindowTitle("Invalid License")
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                retval = msg.exec_()
                if retval == QMessageBox.No:
                    msg2 = QMessageBox(parent=self)
                    msg2.setIcon(QMessageBox.Information)
                    msg2.setText("Would you like to create a new PyEcog License file?")
                    msg2.setWindowTitle("Generate new License")
                    msg2.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                    retval = msg2.exec_()
                    if retval == QMessageBox.Yes:
                        dialog2 = QFileDialog(parent=self)
                        dialog2.setWindowTitle('Choose a directory to ssave PyEcogLicense.txt...')
                        # dialog2.setFileMode(QFileDialog.DirectoryOnly)
                        dialog2.setAcceptMode(QFileDialog.AcceptSave)
                        dialog2.selectFile(('PyEcogLicense.txt'))
                        if dialog2.exec():
                            file_name = dialog2.selectedFiles()[0]
                            if not file_name.endswith('.txt'):
                                file_name = file_name + '.txt'
                            location = license.copy_license_to_folder(file_name)
                            msg3 = QMessageBox(parent=self)
                            msg3.setIcon(QMessageBox.Information)
                            msg3.setText(
                                "Please email this file to marco.leite.11@ucl.ac.uk for activation and restart the application once you have the activated license file")
                            msg3.setDetailedText("File location:" + location)
                            msg3.setWindowTitle("Generate new License")
                            msg3.setStandardButtons(QMessageBox.Ok)
                            msg3.exec_()
                else: # there is a valid license somewhere
                    dialog = QFileDialog(parent=self)
                    dialog.setWindowTitle('Load License ...')
                    dialog.setFileMode(QFileDialog.ExistingFile)
                    # dialog.setOption(QFileDialog.DontUseNativeDialog, True)
                    dialog.setAcceptMode(QFileDialog.AcceptOpen)
                    dialog.setNameFilter('*.txt')
                    if dialog.exec():
                        fname = dialog.selectedFiles()[0]
                    license.copy_activated_license(fname)
                    if license.verify_license_file():
                        license_is_valid = True
        finally:
            # If license is not yet validated close
            if not license_is_valid:
                self.close()
                sys.exit()

    def get_available_screen(self):
        app = QApplication.instance()
        screen = app.primaryScreen()
        print('Screen: %s' % screen.name())
        size = screen.size()
        print('Size: %d x %d' % (size.width(), size.height()))
        rect = screen.availableGeometry()
        print('Available: %d x %d' % (rect.width(), rect.height()))
        return (size, rect)

    def reset_geometry(self):
        self.settings = QSettings("PyEcog", "PyEcog")
        # print("reading cofigurations from: " + self.settings.fileName())
        self.settings.beginGroup("StandardMainWindow")
        # print(self.settings.value("windowGeometry", type=QByteArray))
        self.restoreGeometry(self.settings.value("windowGeometry"))
        self.restoreState(self.settings.value("windowState"))
        self.action_darkmode.setChecked(self.settings.value("darkMode", type=bool))
        self.toggle_darkmode()
        self.show()

    def load_directory(self, dirname=None):
        license.update_license_reg_file()
        print('Openening folder')
        if type(dirname) != str:
            dirname = self.select_directory()
        # temp_animal = Animal(id='-', eeg_folder=dirname)
        temp_project = Project(self.main_model, eeg_data_folder=dirname, title=dirname, project_file=dirname)
        # temp_project.add_animal(temp_animal)
        temp_project.set_temp_project_from_folder(dirname)
        self.tree_element.set_rootnode_from_project(temp_project)
        self.main_model.project = temp_project

    def new_project(self):
        license.update_license_reg_file()
        self.main_model.project.__init__(main_model=self.main_model)  # = Project(self.main_model)
        self.tree_element.set_rootnode_from_project(self.main_model.project)

    def load_project(self, fname=None):
        license.update_license_reg_file()
        if type(fname) is not str:
            dialog = QFileDialog(parent=self)
            dialog.setWindowTitle('Load Project ...')
            dialog.setFileMode(QFileDialog.ExistingFile)
            # dialog.setOption(QFileDialog.DontUseNativeDialog, True)
            dialog.setAcceptMode(QFileDialog.AcceptOpen)
            dialog.setNameFilter('*.pyecog')
            if dialog.exec():
                fname = dialog.selectedFiles()[0]

        if type(fname) is str:
            print('load_project:Loading:', fname)
            if os.path.isfile(fname + '_autosave'):
                last_file_modification = os.path.getmtime(fname)
                last_autosave_modification = os.path.getmtime(fname + '_autosave')
                if last_autosave_modification > last_file_modification:
                    msg = QMessageBox(parent=self)
                    msg.setIcon(QMessageBox.Information)
                    msg.setText("A more recently modified autosave file exists, do you want to load it instead?")
                    msg.setDetailedText("File name:" + fname +
                                        "\nLast autosave file modification: " +
                                        datetime.fromtimestamp(last_autosave_modification).isoformat(sep=' ') +
                                        "\nLast project file modification: " +
                                        datetime.fromtimestamp(last_file_modification).isoformat(
                                            sep=' ')
                                        )
                    msg.setWindowTitle("Load autosave")
                    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                    retval = msg.exec_()
                    if retval == QMessageBox.Yes:
                        fname = fname + '_autosave'

            self.main_model.project.load_from_json(fname)
            self.tree_element.set_rootnode_from_project(self.main_model.project)
            if self.main_model.project.current_animal.eeg_init_time:
                init_time = np.min(self.main_model.project.current_animal.eeg_init_time)
            else:
                init_time = 0
            plot_range = np.array([init_time, init_time + 3600])
            print('trying to plot ', plot_range)
            self.paired_graphics_view.set_scenes_plot_channel_data(plot_range,force_reset=True)
            self.main_model.set_time_position(init_time)
            self.main_model.set_window_pos([init_time, init_time])

        self.toggle_auto_save()

    def save(self):
        print('save action triggered')
        license.update_license_reg_file()
        fname = self.main_model.project.project_file
        if not os.path.isfile(fname):
            self.save_as()
        else:
            print('Saving project to:', fname)
            self.main_model.project.save_to_json(fname)
        self.toggle_auto_save()

    def save_as(self):
        license.update_license_reg_file()
        dialog = QFileDialog(parent=self)
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
        self.toggle_auto_save()

    def auto_save(self):
        license.update_license_reg_file()
        # print('autosave_save action triggered')
        fname = self.main_model.project.project_file
        if not os.path.isfile(fname):
            print('warning - project file does not exist yet')
        elif fname.endswith('.pyecog'):
            print('Auto saving project to:', fname + '_autosave')
            self.main_model.project.save_to_json(fname + '_autosave')
        else:
            print('project filename not in *.pyecog')

    def toggle_auto_save(self):
        if self.action_autosave.isChecked():
            self.autosave_timer.start(60000)  # autosave every minute
        else:
            self.autosave_timer.stop()

    def toggle_fullscreen(self):
        if self.action_fullscreen.isChecked():
            self.showFullScreen()
        else:
            self.showNormal()

    def toggle_darkmode(self):
        if self.action_darkmode.isChecked():
            print('Setting Dark Mode')
            # Fusion dark palette adapted from https://gist.github.com/QuantumCD/6245215.
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.WindowText, Qt.white)
            # palette.setColor(QPalette.Base, QColor(25, 25, 25)) # too Dark
            palette.setColor(QPalette.Base, QColor(35, 39, 41))
            # palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.AlternateBase, QColor(45, 50, 53))
            palette.setColor(QPalette.ToolTipBase, Qt.black)
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, Qt.black)
            self.app_handle.setPalette(palette)
            self.main_model.color_settings['pen'].setColor(QColor(255, 255, 255, 100))
            self.main_model.color_settings['brush'].setColor(QColor(0, 0, 0, 255))
        else:
            print('Setting Light Mode')
            palette = QPalette()
            self.app_handle.setPalette(palette)
            self.main_model.color_settings['pen'].setColor(QColor(0, 0, 0, 100))
            self.main_model.color_settings['brush'].setColor(QColor(255, 255, 255, 255))

        self.paired_graphics_view.set_scenes_plot_channel_data(force_reset=True)
        self.main_model.sigWindowChanged.emit(self.main_model.window)

    def select_directory(self, label_text='Select a directory'):
        '''
        Method launches a dialog allow user to select a directory
        '''
        dialog = QFileDialog(parent=self)
        dialog.setWindowTitle(label_text)
        dialog.setFileMode(QFileDialog.DirectoryOnly)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        # we might want to set home directory using settings
        # for now rely on default behaviour
        # home = os.path.expanduser("~") # default, if no settings available
        # dialog.setDirectory(home)
        # dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.ShowDirsOnly, False)
        if dialog.exec():
            return dialog.selectedFiles()[0]
        else:
            return ''

    def reload_plot(self):
        # print('reload')
        xmin, xmax = self.paired_graphics_view.insetview_plot.vb.viewRange()[0]
        x_range = xmax - xmin
        # index = self.tree_element.tree_view.currentIndex()
        # self.tree_element.model.data(index, TreeModel.prepare_for_plot_role)
        self.main_model.project.file_buffer.clear_buffer()
        self.main_model.project.file_buffer.get_data_from_range([xmin, xmax], n_envelope=10, channel=0)
        buffer_x_max = self.main_model.project.file_buffer.get_t_max_for_live_plot()
        # print(full_xrange)
        print('reload_plot', buffer_x_max, xmax)
        if buffer_x_max > xmax:
            # print('called set xrange')
            self.paired_graphics_view.insetview_plot.vb.setXRange(buffer_x_max - x_range, buffer_x_max, padding=0)

    def load_live_recording(self):
        if self.actionLiveUpdate.isChecked():
            self.live_recording_timer.start(100)
        else:
            self.live_recording_timer.stop()

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

    def open_console_window(self):
        self.dock_list['Console'].show()
        self.show()

    def openNDFconverter(self):
        print('opening NDF converter')
        self.ndf_converter = NDFConverterWindow(parent=self)
        self.ndf_converter.show()

    def openProjectEditor(self):
        print('opening Project Editor')
        self.projectEditor = ProjectEditWindow(self.main_model.project, parent=self)
        self.projectEditor.show()

    def openFeatureExtractor(self):
        self.featureExtractorWindow = FeatureExtractorWindow(self.main_model.project, parent=self)
        self.featureExtractorWindow.show()

    def openClassifier(self):
        if hasattr(self, 'ClassifierWindow'):
            self.ClassifierWindow.setWindowState(
                (self.ClassifierWindow.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
            self.ClassifierWindow.raise_()
            # self.ClassifierWindow.update_fields()
            self.ClassifierWindow.show()
            return
        self.ClassifierWindow = ClassifierWindow(self.main_model.project, parent=self)
        geometry = self.ClassifierWindow.geometry()
        geometry.setHeight(self.geometry().height())
        self.ClassifierWindow.setGeometry(geometry)
        self.ClassifierWindow.show()

    def export_annotations(self):
        dialog = QFileDialog(parent=self)
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

    # def reset_video(self):
    #     self.video_element.reset()
    #     self.video_element.sigTimeChanged.connect(self.main_model.set_time_position)
    #     self.main_model.sigTimeChanged.connect(self.video_element.setGlobalPosition)

    def build_menubar(self):
        self.menu_bar = self.menuBar()

        # FILE section
        self.menu_file = self.menu_bar.addMenu("File")
        self.action_NDF_converter = self.menu_file.addAction("Open NDF converter")
        self.menu_file.addSeparator()
        self.action_load_directory = self.menu_file.addAction("Load directory")
        self.menu_file.addSeparator()
        self.actionLiveUpdate = self.menu_file.addAction("Live Recording")
        self.actionLiveUpdate.setCheckable(True)
        self.actionLiveUpdate.toggled.connect(self.load_live_recording)
        self.actionLiveUpdate.setChecked(False)
        self.actionLiveUpdate.setShortcut('Ctrl+R')

        self.menu_file.addSeparator()
        self.action_quit = self.menu_file.addAction("Quit")
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
        self.action_load_project.setShortcut('Ctrl+L')
        self.action_save = self.menu_project.addAction("Save Project")
        self.action_save.setShortcut('Ctrl+S')
        self.action_save_as = self.menu_project.addAction("Save Project as...")
        self.action_save_as.setShortcut('Ctrl+Shift+S')
        self.action_new_project.triggered.connect(self.new_project)
        self.action_load_project.triggered.connect(self.load_project)
        self.action_save.triggered.connect(self.save)
        self.action_save_as.triggered.connect(self.save_as)
        self.menu_project.addSeparator()
        self.action_autosave = self.menu_project.addAction("Enable autosave")
        self.action_autosave.setCheckable(True)
        self.action_autosave.toggled.connect(self.toggle_auto_save)
        self.action_autosave.setChecked(True)

        # ANNOTATIONS section
        self.menu_annotations = self.menu_bar.addMenu("Annotations")
        self.annotations_undo = self.menu_annotations.addAction("Undo")
        self.annotations_undo.setShortcut('Ctrl+Z')
        self.annotations_undo.triggered.connect(self.main_model.annotations.step_back_in_history)
        self.annotations_redo = self.menu_annotations.addAction("Redo")
        self.annotations_redo.setShortcut('Ctrl+Shift+Z')
        self.annotations_redo.triggered.connect(self.main_model.annotations.step_forward_in_history)
        self.action_export_annotations = self.menu_annotations.addAction("Export to CSV")
        self.action_export_annotations.triggered.connect(self.export_annotations)
        self.action_import_annotations = self.menu_annotations.addAction("Import annotations")
        self.action_import_annotations.setDisabled(True)

        # CLASSIFIER section
        self.menu_classifier = self.menu_bar.addMenu("Classifier")
        self.action_setup_feature_extractor = self.menu_classifier.addAction("Feature Extractor Options")
        self.action_setup_classifier = self.menu_classifier.addAction("Classifier Options")
        self.action_setup_feature_extractor.triggered.connect(self.openFeatureExtractor)
        self.action_setup_classifier.triggered.connect(self.openClassifier)
        # self.action_train_classifier.setDisabled(True)
        # self.action_run_classifier.setDisabled(True)
        # self.action_review_classifications.setDisabled(True)

        # TOOLS section
        self.menu_tools = self.menu_bar.addMenu("Tools")
        self.action_open_video_window = self.menu_tools.addAction("Video")
        self.action_open_video_window.triggered.connect(self.open_video_window)
        # To do
        self.action_open_fft_window = self.menu_tools.addAction("FFT")
        self.action_open_fft_window.triggered.connect(self.open_fft_window)

        self.action_open_morlet_window = self.menu_tools.addAction("Morlet Wavelet Transform")
        self.action_open_morlet_window.triggered.connect(self.open_wavelet_window)

        self.action_open_console_window = self.menu_tools.addAction("Console")
        self.action_open_console_window.triggered.connect(self.open_console_window)

        # HELP section
        self.menu_help = self.menu_bar.addMenu("Help")
        self.action_show_hints = self.menu_help.addAction("Show Hints")
        self.action_show_hints.triggered.connect(self.dock_list['Hints'].show)

        self.action_reset_geometry = self.menu_help.addAction("Reset Main Window layout")
        self.action_reset_geometry.triggered.connect(self.reset_geometry)

        self.action_fullscreen = self.menu_help.addAction("Full Screen")
        self.action_fullscreen.setShortcut('F11')
        self.action_fullscreen.setCheckable(True)
        self.action_fullscreen.toggled.connect(self.toggle_fullscreen)
        self.action_fullscreen.setChecked(False)

        # self.action_reset_video    = self.menu_help.addAction("Reset Video Widget")
        # self.action_reset_video.triggered.connect(self.reset_video)

        self.action_darkmode = self.menu_help.addAction("Dark mode")
        self.action_darkmode.setCheckable(True)
        self.action_darkmode.toggled.connect(self.toggle_darkmode)
        self.action_darkmode.setChecked(False)

        self.menu_help.addSeparator()
        self.action_go_to_git = self.menu_help.addAction("Go to Git Repository")
        self.action_go_to_git.triggered.connect(self.open_git_url)

        self.action_go_to_doc = self.menu_help.addAction("Go to web documentation")
        self.action_go_to_doc.triggered.connect(self.open_docs_url)

        self.menu_bar.setNativeMenuBar(False)

        # self.menubar.addMenu("Edit")
        # self.menubar.addMenu("View")

    def closeEvent(self, event):
        self.auto_save()
        print('closing')
        settings = QSettings("PyEcog", "PyEcog")
        settings.beginGroup("MainWindow")
        settings.setValue("windowGeometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        settings.setValue("darkMode", self.action_darkmode.isChecked())
        settings.setValue("autoSave", self.action_autosave.isChecked())
        settings.endGroup()

        settings.beginGroup("ProjectSettings")
        settings.setValue("ProjectFileName", self.main_model.project.project_file)
        settings.endGroup()
        print('current project filename:', self.main_model.project.project_file)
        # for dock_name in self.dock_list.keys():
        #     settings.beginGroup(dock_name)
        #     settings.setValue("windowGeometry", self.dock_list[dock_name].saveGeometry())
        #     # settings.setValue("windowState", self.dock_list[dock_name].saveState())
        #     settings.endGroup()
        self.saveState()
        print(self.title)
        print('all finished - all data saved successfully - farewell!')

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

        numbered_keys = [QtCore.Qt.Key_1, QtCore.Qt.Key_2, QtCore.Qt.Key_3, QtCore.Qt.Key_4, QtCore.Qt.Key_5,
                         QtCore.Qt.Key_6, QtCore.Qt.Key_7, QtCore.Qt.Key_8, QtCore.Qt.Key_9, QtCore.Qt.Key_0]

        for i in range(len(numbered_keys)):
            if evt.key() == numbered_keys[i]:
                print(i + 1, 'pressed')
                label = self.annotation_parameter_tree.get_label_from_shortcut(i + 1)
                if label is not None:
                    if self.main_model.annotations.focused_annotation is None:
                        print('Adding new annotation')
                        new_annotation = AnnotationElement(label=label,
                                                           start=self.main_model.window[0],
                                                           end=self.main_model.window[1],
                                                           notes='')
                        self.main_model.annotations.add_annotation(new_annotation)
                        self.main_model.annotations.focusOnAnnotation(new_annotation)
                    else:
                        print('Calling annotation_table changeSelectionLabel')
                        self.annotation_table.changeSelectionLabel(label)
                        # annotation = self.main_model.annotations.focused_annotation
                        # annotation.setLabel(self.main_model.annotations.labels[i])
                        # self.main_model.annotations.focusOnAnnotation(annotation)
                    return


def execute():
    os.environ['QT_MULTIMEDIA_PREFERRED_PLUGINS'] = 'windowsmediafoundation'
    app = QApplication(sys.argv)
    app.setApplicationName('PyEcog')
    app.setOrganizationDomain('PyEcog')
    app.setOrganizationName('PyEcog')
    app.setStyle("fusion")
    # Mikail feel free to play about if you feel so inclined :P
    # Now use a palette to switch to dark colors:
    # palette = QPalette()
    # palette.setColor(QPalette.Window, QColor(53, 53, 53))
    # palette.setColor(QPalette.WindowText, Qt.white)
    # # palette.setColor(QPalette.Base, QColor(25, 25, 25))
    # palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    # palette.setColor(QPalette.Base, QColor(35, 39, 41))
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
    # pg.setConfigOption('background', 'k')
    pg.setConfigOption('foreground', 'd')
    pg.setConfigOption('background', 'w')
    # pg.setConfigOption('foreground', 'k')
    pg.setConfigOption('antialias', True)

    pg.setConfigOption('useWeave', True)
    # pg.setConfigOption('useOpenGL', True)

    screen = MainWindow(app_handle=app)
    screen.get_available_screen()
    screen.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    freeze_support()
    execute()
