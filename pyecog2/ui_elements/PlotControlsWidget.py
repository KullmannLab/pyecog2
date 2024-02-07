import pyqtgraph as pg
from PySide6 import QtCore
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget, QCheckBox, QPushButton, QMainWindow, QGridLayout, QTableView, QLabel
from PySide6.QtCore import QRunnable, Slot, QThreadPool
import numpy as np
import scipy.signal as sg
from timeit import default_timer as timer
import traceback, inspect, sys
import logging
logger = logging.getLogger(__name__)

class TableModel(QtCore.QAbstractTableModel):
    def __init__(self, data):
        super(TableModel, self).__init__()
        self._data = data

    def data(self, index, role):
        if role == Qt.DisplayRole:
            # Note: self._data[index.row()][index.column()] will also work
            value = self._data[index.row(), index.column()]
            if value == 0:
                value = int(value)
            return str(value)

    def setData(self, index, value, role):
        if role == Qt.EditRole:
            self._data[index.row()][index.column()] = bool(value)
            return True

    def rowCount(self, index):
        return self._data.shape[0]

    def columnCount(self, index):
        return self._data.shape[1]

    def flags(self, index):
        return Qt.ItemIsSelectable|Qt.ItemIsEnabled|Qt.ItemIsEditable

class MontageEditorWindow(QMainWindow):
    def __init__(self, main_model):
        super().__init__()

        self.table = QTableView()
        montage_matrix = np.identity(main_model.project.file_buffer.get_nchannels())
        self.model = TableModel(montage_matrix)
        self.table.setModel(self.model)

        self.setCentralWidget(self.table)
        self.setWindowTitle('PyEcog Montage Editor')
        self.show()


class PlotControls(QWidget):
    sigUpdateFilter = QtCore.Signal(tuple)
    sigUpdateXrange_i = QtCore.Signal(float)
    sigUpdateXrange_o = QtCore.Signal(float)
    def __init__(self, main_model = None):
        self.main_model = main_model
        QWidget.__init__(self)
        self.layout = QGridLayout()
        self.setLayout(self.layout)
        self.filter_controls_widget = QWidget()
        self.filter_controls_layout = QGridLayout()
        self.filter_controls_widget.setLayout(self.filter_controls_layout)
        self.range_controls_widget = QWidget()
        self.range_controls_layout = QGridLayout()
        self.range_controls_widget.setLayout(self.range_controls_layout)

        self.filter_check = QCheckBox('Apply filter')
        self.filter_check.stateChanged.connect(self.update_filter)
        self.hp_spin = pg.SpinBox(value=.001,bounds=[0,None],step=1,compactHeight=False,dec=True) #, int=True, minStep=1, step=1)
        self.hp_spin.valueChanged.connect(self.update_filter)
        self.lp_spin = pg.SpinBox(value=1000,bounds=[0,None],step=1,compactHeight=False,dec=True) #, int=True, minStep=1, step=1)
        self.lp_spin.valueChanged.connect(self.update_filter)

        self.filter_controls_layout.addWidget(self.filter_check,0,0)
        self.filter_controls_layout.addWidget(QLabel('High pass frequency (Hz)'),1,0)
        self.filter_controls_layout.addWidget(self.hp_spin,1,1)
        self.filter_controls_layout.addWidget(QLabel('Low pass frequency (Hz)'),2,0)
        self.filter_controls_layout.addWidget(self.lp_spin,2,1)
        self.layout.addWidget(self.filter_controls_widget,0,0)

        self.Xrange_spin_o = pg.SpinBox(value=3600.0, bounds=[0, 3600],step=.1,compactHeight=False,dec=True)
        self.Xrange_spin_o.valueChanged.connect(self.update_Xrange_o)
        self.range_controls_layout.addWidget(QLabel('Overview X range (s)'),0,0)
        self.range_controls_layout.addWidget(self.Xrange_spin_o,0,1)

        self.Xrange_spin_i = pg.SpinBox(value=30.0, bounds=[0, 3600],step=.1,compactHeight=False,dec=True)
        self.Xrange_spin_i.valueChanged.connect(self.update_Xrange_i)
        self.range_controls_layout.addWidget(QLabel('Inset X range (s)'),1,0)
        self.range_controls_layout.addWidget(self.Xrange_spin_i,1,1)
        self.layout.addWidget(self.range_controls_widget,1,0)

        self.channel_selector_butotn = QPushButton('Montage Editor', self)
        self.channel_selector_butotn.clicked.connect(self.launch_montage_editor)
        self.layout.addWidget(self.channel_selector_butotn,2,0)



    def update_filter(self):
        # logger.info(f'Plot controls {self.filter_check.checkState()>0} {self.hp_spin.value()} {self.lp_spin.value()}')
        self.sigUpdateFilter.emit((self.filter_check.isChecked(),self.hp_spin.value(),self.lp_spin.value()))
        return

    def update_Xrange_o(self):
        logger.info(f'Xrange overview value: {self.Xrange_spin_o.value()}')
        self.sigUpdateXrange_o.emit((self.Xrange_spin_o.value()))
        return

    def update_Xrange_i(self):
        logger.info(f'Xrange inset value: {self.Xrange_spin_i.value()}')
        self.sigUpdateXrange_i.emit((self.Xrange_spin_i.value()))
        return

    def launch_montage_editor(self):
        self.channel_selector = MontageEditorWindow(self.main_model)
        self.channel_selector.show()

    def set_values(self,filter):
        pass

if __name__ == '__main__':
    import sys
    # if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
    app = QApplication(sys.argv)
    w = PlotControls()
    w.show()
    sys.exit(app.exec())

#
# if __name__ == '__main__':
#     app = QApplication(sys.argv)
#     player = VideoWindow()
#     player.resize(640, 480)
#     player.show()
#     sys.exit(app.exec())