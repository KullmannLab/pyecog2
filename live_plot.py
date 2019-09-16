import sys
import os
import numpy as np

from PyQt5 import QtGui, QtCore, QtWidgets, uic, Qt
from PyQt5.QtGui import QPainter, QBrush, QPen

#import pyqtgraph as pg
#from .utils import Point, rect_to_range
#from .graphics_view import PyecogGraphicsView
# temp
from datetime import datetime
import pyqtgraph_copy.pyqtgraph as pg

from pyecog_plot_item import PyecogPlotCurveItem



class LiveWindow(QWidget):
    '''

    '''
    def __init__(self, parent, file):
        super(LiveWindow, self).__init__(parent)

        # self.splitter  = QtWidgets.QSplitter(parent=None)
        # self.splitter.resize(680, 400) # Todo currently not sure about this
        # self.splitter.setOrientation(QtCore.Qt.Vertical)
        # sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred,
        #                                    QtWidgets.QSizePolicy.Expanding)
        # self.splitter.setSizePolicy(sizePolicy)

        self.graphics_layout  = pg.GraphicsLayoutWidget()
        self.plot =  self.graphics_layout.addPlot()
        self.plot.setLabel('bottom', text='Time', units='')





    def update_plot(self):
        print('plot')

    def toggle_update():
        timer = pg.QtCore.QTimer()
        timer.timeout.connect(self.update)
        timer.start(50)



