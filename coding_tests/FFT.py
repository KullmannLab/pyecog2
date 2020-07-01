


from PyQt5 import QtGui, QtCore
from PyQt5.QtWidgets import QApplication
import sys
import numpy as np
import pyqtgraph_copy.pyqtgraph as pg


pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

class FFTwindow(pg.PlotWidget):
    def __init__(self,main_model):
        super().__init__(name='FFT')
        self.main_model = main_model
        self.p1 = self.plot()
        self.p1.setPen((0, 0, 0))
        self.setXRange(0,100)
        self.setLabel('left', 'Amplitude', units = 'V')
        self.setLabel('bottom', 'Frequency', units = 'Hz')
        self.showGrid(x=True, y=True, alpha=0.15)
        self.main_model.sigWindowChanged.connect(self.updateData)

    def updateData(self):
        if self.isVisible():
            data = np.random.randn(100)
            vf   = np.arange(100)
            self.p1.setData(x = vf, y = data)
            self.setLimits(xMin=0,xMax=100)
            print('Updated FFT')

