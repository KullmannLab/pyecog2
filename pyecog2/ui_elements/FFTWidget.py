
from scipy.signal import stft
from PySide2 import QtGui, QtCore
from PySide2.QtWidgets import QApplication, QWidget
import sys
import numpy as np
import pyqtgraph as pg
import logging
logger = logging.getLogger(__name__)

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


class FFTWindowItem(pg.PlotWidget):
    def __init__(self,main_model):
        super().__init__(name='FFT')
        self.main_model = main_model
        self.p1 = self.plot()
        self.p1.setPen(self.main_model.color_settings['pen'])
        self.setBackground(self.main_model.color_settings['brush'])
        self.setXRange(0,100)
        self.setLabel('left', 'Amplitude', units = 'V')
        self.setLabel('bottom', 'Frequency', units = 'Hz')
        self.showGrid(x=True, y=True, alpha=0.15)
        self.channel = 0
        self.nfft =1024
        self.main_model.sigWindowChanged.connect(self.updateData)

    def updateData(self):
        if self.isVisible():
            self.p1.setPen(self.main_model.color_settings['pen'])
            self.setBackground(self.main_model.color_settings['brush'])
            # print('window', self.main_model.window)
            if self.main_model.window[1]-self.main_model.window[0] > 3600:
                logger.warning('Window too large to compute FFT (>3600s)')
                self.setLabel('bottom', 'Window too large to compute Wavelet (>3600s)')
                return
            data, time = self.main_model.project.get_data_from_range(self.main_model.window,channel = self.channel)
            if len(data) < 10:
                return
            # N = int(2**np.ceil(np.log2(len(data))))
            # dataf = np.fft.rfft(data.T,N)/N
            # vf = np.fft.rfftfreq(N)*1/(time[1]-time[0])
            vf,t,z = stft(data.T,fs = 1/(time[10]-time[9]),nperseg=self.nfft/4,nfft=self.nfft,detrend='linear') # avoid time edge values
            dataf = np.mean(np.abs(z),axis=-1).ravel()
            # print('FFT: data shape:',data.shape,'FFT: dataf shape:',dataf.shape,'vf shape:',vf.shape,'z shape:',z.shape)
            # self.p1.setData(x = vf, y = np.abs(dataf[0]))
            self.p1.setData(x = vf+vf[1], y = 2*np.abs(dataf))
            self.setLabel('bottom', 'Frequency', units = 'Hz')
            # self.setLimits(xMin=vf[0],xMax=vf[-1],yMin=min(0,min(np.abs(dataf))),yMax = 1.1*max(dataf))
            logger.info('Updated FFT')
            # print('Reg Entropy:',reg_entropy(dataf))

    def setNfft(self,nfft):
        self.nfft = int(2**nfft)
        logger.info(f'FFT nfft set to {self.nfft}')
        self.updateData()

    def setChannel(self,c):
        self.channel = int(c)
        logger.info(f'FFT channel set to {c}')
        self.updateData()


class FFTwindow(QWidget):
    def __init__(self, main_model = None):
        QWidget.__init__(self)
        self.main_model = main_model
        self.layout = QtGui.QGridLayout()
        self.setLayout(self.layout)
        self.fft_item = FFTWindowItem(main_model)

        self.controls_widget = QWidget()
        self.controls_layout = QtGui.QGridLayout()
        self.controls_widget.setLayout(self.controls_layout)
        self.channel_spin = pg.SpinBox(value=0,bounds=[0,None], int=True, minStep=1, step=1,compactHeight=False)
        self.channel_spin.valueChanged.connect(self.fft_item.setChannel)
        self.nfft_spin = pg.SpinBox(value=10, bounds=[6, 16],step=1,int=True,compactHeight=False)
        self.nfft_spin.valueChanged.connect(self.fft_item.setNfft)
        self.controls_layout.addWidget(QtGui.QLabel('Channel'),0,0)
        self.controls_layout.addWidget(self.channel_spin,0,1,)
        self.controls_layout.addWidget(QtGui.QLabel('Nfft points 2^'),0,2)
        self.controls_layout.addWidget(self.nfft_spin,0,3)

        self.layout.addWidget(self.controls_widget,1,0)
        self.layout.addWidget(self.fft_item,0,0)
