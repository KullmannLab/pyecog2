# -*- coding: utf-8 -*-
"""
Demonstrates common image analysis tools.

Many of the features demonstrated here are already provided by the ImageView
widget, but here we present a lower-level approach that provides finer control
over the user interface.
"""

import pyqtgraph_copy.pyqtgraph as pg
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QApplication
import numpy as np
import scipy.signal as sg
from numba import jit
from timeit import default_timer as timer

from paired_graphics_view import DateAxis
# Interpret image data as row-major instead of col-major
pg.setConfigOptions(imageAxisOrder='row-major')

# @jit(parallel=True)
def morlet_wavelet(input_signal, dt=1, R=7, freq_interval=()):
    Ns = len(input_signal)
    if len(freq_interval) > 0:
        minf = max(freq_interval[0], R / (Ns * dt))  # avoid wavelets with COI longer than the signal
    else:
        minf = R / (Ns * dt)
    if len(freq_interval) > 1:
        maxf = min(freq_interval[1], .5 / dt)  # avoid wavelets above the Nyquist frequency
    else:
        maxf = .5 / dt
    if len(freq_interval) > 2:
            Nf = freq_interval[2]
    else:
        Nf = int(np.ceil(np.log(maxf / minf) / np.log(1 / R + 1)))  # make spacing aproximately equal to sigma f

    alfa = (maxf / minf) ** (1 / Nf) - 1  # According to the expression achived by fn = ((1+1/R)^n)*f0 where 1/R = alfa
    vf = ((1 + alfa) ** np.arange(0, Nf)) * minf
    print(Nf,Ns)
    result = np.zeros((Nf, Ns), dtype='complex')

    for k in range(Nf):
        N = int(2 * R / vf[k] / dt)  # Compute size of the wavelet
        wave = sg.morlet(N, w=R, s=1, complete=0) / N * np.pi * 2  # Normalize de amplitude returned by sg.morlet
        result[k, :] = sg.fftconvolve(input_signal, wave, mode='same')

    mask = np.zeros(result.shape, dtype='bool')

    Nlist = (.5 * R / vf / dt).astype('int')  # 3 sigma COI
    for k in range(len(Nlist)):
        mask[k, :Nlist[k]] = True
        mask[k, -Nlist[k]:] = True

    return result, mask, vf


class WaveletWindow(pg.GraphicsLayoutWidget):
    def __init__(self, main_model = None):
        super().__init__()

        self.main_model = main_model
        self.setWindowTitle("Wavelet Analysis")
        self.p1 = self.addPlot()
        self.img = pg.ImageItem()
        # log_axis = LogAxis(orientation='left')
        self.p1.addItem(self.img, z=-1) #, axisItems = {'left': log_axis})
        self.p1.getAxis('bottom').setZValue(1)
        self.p1.getAxis('left').setZValue(1)
        self.p1.getAxis('top').setZValue(1)
        self.p1.getAxis('right').setZValue(1)
        self.p1.showGrid(x=False, y=True, alpha=1) # Haven't been able to make this work
        self.p1.setLogMode(y=True)

        # Contrast/color control
        self.hist = pg.HistogramLUTItem()
        self.hist.setImageItem(self.img)
        self.addItem(self.hist)
        self.hist.axis.setLabel( text = 'Amplitude', units = 'Log<sub>10</sub> a.u.')
        self.hist.gradient.loadPreset('viridis')
        self.hist_levels = None


        # Generate image data
        self.update_data()
        self.vb = self.img.getViewBox()
        self.p1.setLabel('left', 'Frequency', units = 'Hz')
        self.p1.setLabel('bottom', 'Time', units = 's')

        self.hist.setLevels(self.data.min(), self.data.max())
        self.main_model.sigWindowChanged.connect(self.update_data)

    def update_data(self):
        self.data = np.array([[1, 0], [0, 1]])
        start_t = timer()
        if self.hist_levels is not None:
            self.hist_levels = self.hist.getLevels()
        if self.isVisible():
            if self.main_model is None:
                data = np.random.randn(300*250)
                data[200:800] += np.sin(np.arange(600)*10)
                time = np.arange(300*250)/250
                print('random data')
            else:
                print('window' , self.main_model.window)
                data, time = self.main_model.project.get_data_from_range(self.main_model.window)
            if len(data) <= 10 :
                return
            print('Wavelet data shape:',data.shape)
            # self.img.setImage(self.data)
            # self.show()
            print('Computing Wavelet...')
            dt = (time[10]-time[9])     # avoid time edge values
            self.wav , self.coi, vf = morlet_wavelet(data.ravel(),dt = dt ,R=14,freq_interval = (1,2/dt,100))
            self.data = np.log(np.abs(self.wav)+.001)
            self.img.setImage(self.data*(1-self.coi))
            self.img.resetTransform()
            ymin = np.log10(vf[0])
            ymax = np.log10(vf[-1])
            self.img.translate(0,ymin)
            self.img.scale(dt,(ymax-ymin)/self.data.shape[0])
            self.vb.setLimits(xMin=0, xMax=self.data.shape[1]*dt, yMin=ymin, yMax=ymax)
            self.vb.setRange(xRange=[0,self.data.shape[1]*dt])
            if self.hist_levels is not None: # Mantain levels from previous view if they exist
                self.hist.setLevels(*self.hist_levels)
            else:
                self.hist_levels = self.hist.getLevels()
            self.show()
            end_t = timer()
            print('Updated Wavelet in ',end_t-start_t, 'seconds')



## Start Qt event loop unless running in interactive mode or using pyside.
if __name__ == '__main__':
    import sys
    # if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
    app = QApplication(sys.argv)
    w = WaveletWindow()
    w.show()
    sys.exit(app.exec_())

#
# if __name__ == '__main__':
#     app = QApplication(sys.argv)
#     player = VideoWindow()
#     player.resize(640, 480)
#     player.show()
#     sys.exit(app.exec_())

class LogAxis(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        strns = []
        for x in values:
            strns.append('10<sup>'+str(x) + '</sup>')
        return strns