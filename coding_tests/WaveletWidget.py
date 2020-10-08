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

# Interpret image data as row-major instead of col-major
pg.setConfigOptions(imageAxisOrder='row-major')


def morlet_wavelet(input_signal, dt=1, R=7, freq_interval=()):
    Ns = len(input_signal)
    try:
        minf = max(freq_interval[0], R / (Ns * dt))  # avoid wavelets with COI longer than the signal
    except:
        minf = R / (Ns * dt)
    try:
        maxf = min(freq_interval[1], .5 / dt)  # avoid wavelets above the Nyquist frequency
    except:
        maxf = .5 / dt
    try:
        Nf = freq_interval[2]
    except:
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

        # self.p3 = self.addPlot()
        # self.p3.setMaximumWidth(250)
        # self.resize(800, 800)
        self.main_model = main_model
        self.setWindowTitle("Wavelet Analysis")
        self.p1 = self.addPlot()
        self.img = pg.ImageItem()
        # log_axis = LogAxis(orientation='left')
        self.p1.addItem(self.img) #, axisItems = {'left': log_axis})
        self.p1.setLogMode(y=True)

        # # Custom ROI for selecting an image region
        # self.roi = pg.ROI([0, 10], [60, 50])
        # self.roi.addScaleHandle([0.5, 1], [0.5, 0])
        # self.roi.addScaleHandle([0.5, 0], [0.5, 1])
        # self.roi.addScaleHandle([0, 0.5], [1, 0.5])
        # self.roi.addScaleHandle([1, 0.5], [0, 0.5])
        # self.p1.addItem(self.roi)
        # self.roi.setZValue(10)  # make sure ROI is drawn above image
        #
        # self.roi.sigRegionChanged.connect(self.updatePlot)

        # Isocurve drawing
        # self.iso = pg.IsocurveItem(level=0.8, pen='g')
        # self.iso.setParentItem(self.img)
        # self.iso.setZValue(5)

        # Contrast/color control
        self.hist = pg.HistogramLUTItem()
        self.hist.setImageItem(self.img)
        self.addItem(self.hist)
        self.hist.axis.setLabel( text = 'Amplitude', units = 'Log<sub>10</sub> V')
        self.hist.gradient.loadPreset('viridis')

        # Draggable line for setting isocurve level
        self.isoLine = pg.InfiniteLine(angle=0, movable=True, pen='g')
        self.hist.vb.addItem(self.isoLine)
        self.hist.vb.setMouseEnabled(y=False) # makes user interaction a little easier
        self.isoLine.setValue(0.8)
        self.isoLine.setZValue(1000) # bring iso line above contrast controls

        self.isoLine.sigDragged.connect(self.updateIsocurve)

        # Another plot area for displaying ROI data
        # self.nextRow()
        # self.nextColumn()
        # self.p2 = self.addPlot(colspan=1)
        # self.p2.setMaximumHeight(250)
        # self.resize(800, 800)

        # Generate image data
        self.update_data()
        self.vb = self.img.getViewBox()
        self.p1.setLabel('left', 'Frequency', units = 'Hz')
        self.p1.setLabel('bottom', 'Time', units = 's')

        self.hist.setLevels(self.data.min(), self.data.max())
        self.main_model.sigWindowChanged.connect(self.update_data)

        # build isocurves from smoothed data
        # iso.setData(pg.gaussianFilter(data, (2, 2)))
        # self.iso.setData(self.data)

        # set position and scale of image


    #     # zoom to fit imageo
    #     self.p2.setLabel('left', 'Frequency', units = 'Hz')
    #     self.p2.setLabel('bottom', 'Time', units = 's')
    #     self.p2.autoRange()
    #
    # # Callbacks for handling user interaction
    # def updatePlot(self):
    #     if self.isVisible():
    #         selected = self.roi.getArrayRegion(self.data, self.img)
    #         self.p2.plot(selected.mean(axis=0), clear=True)
    #         self.p3.plot(selected.mean(axis=1),selected.range(), clear=True)

    #
    def updateIsocurve(self):
        self.update_data()
        # self.iso.setLevel(self.isoLine.value())

    def update_data(self):
        self.data = np.zeros((1,1))
        if self.isVisible():
            if self.main_model is None:
                data = np.random.randn(300*250)
                data[200:800] += np.sin(np.arange(600)*10)
                time = np.arange(300*250)/250
                print('random data')
            else:
                data, time = self.main_model.project.get_data_from_range(self.main_model.window)

            print('Wavelet data shape:',data.shape)
            dt = (time[1]-time[0])
            self.wav , self.coi, vf = morlet_wavelet(data.ravel(),dt = dt ,R=14,freq_interval = (1,125,100))
            self.data = np.log(np.abs(self.wav)+.001)
            self.img.setImage(self.data*(1-self.coi))
            self.img.resetTransform()
            ymin = np.log10(vf[0])
            ymax = np.log10(vf[-1])
            self.img.translate(0,ymin)
            self.img.scale(dt,(ymax-ymin)/self.data.shape[0])
            self.vb.setLimits(xMin=0, xMax=self.data.shape[1]*dt, yMin=ymin, yMax=ymax)
            self.show()
            print('Updated Wavelet')



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