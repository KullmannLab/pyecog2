


from PyQt5 import QtGui, QtCore
from PyQt5.QtWidgets import QApplication
import sys
import numpy as np
import pyqtgraph_copy.pyqtgraph as pg
from scipy.signal import stft

pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')

def reg_entropy(fdata):
    # regularized entropy of spectral data
    # fdata comes from rfft
    fdata_x_f = np.abs(fdata)*np.arange(2,len(fdata)+2)
    # print('fdata shape:',fdata_x_f.shape)
    fdata_x_f = fdata_x_f+1e-9*np.max(fdata_x_f)
    fdata_x_f = fdata_x_f/np.sum(fdata_x_f)
    return np.sum(fdata_x_f*np.log(fdata_x_f))


class FFTwindow(pg.PlotWidget):
    def __init__(self,main_model):
        super().__init__(name='FFT')
        self.main_model = main_model
        self.p1 = self.plot()
        self.p1.setPen((0, 0, 0))
        self.setXRange(0,100)
        self.setLabel('left', 'Amplitude', units = 'a.u.')
        self.setLabel('bottom', 'Frequency', units = 'Hz')
        self.showGrid(x=True, y=True, alpha=0.15)
        self.main_model.sigWindowChanged.connect(self.updateData)

    def updateData(self):
        if self.isVisible():
            print('window', self.main_model.window)
            data, time = self.main_model.project.get_data_from_range(self.main_model.window)
            if len(data) < 10:
                return
            N = int(2**np.ceil(np.log2(len(data))))
            # dataf = np.fft.rfft(data.T,N)/N
            # vf = np.fft.rfftfreq(N)*1/(time[1]-time[0])
            vf,t,z = stft(data.T,fs = 1/(time[10]-time[9]),nfft=1024) # avoid time edge values
            dataf = np.mean(np.abs(z),axis=-1).ravel()
            print('FFT: data shape:',data.shape,'FFT: dataf shape:',dataf.shape,'vf shape:',vf.shape,'z shape:',z.shape)
            # self.p1.setData(x = vf, y = np.abs(dataf[0]))
            self.p1.setData(x = vf, y = np.abs(dataf))
            # self.setLimits(xMin=vf[0],xMax=vf[-1],yMin=min(0,min(np.abs(dataf))),yMax = 1.1*max(dataf))
            print('Updated FFT')
            # print('Reg Entropy:',reg_entropy(dataf))

