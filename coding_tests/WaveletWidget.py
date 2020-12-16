# -*- coding: utf-8 -*-
"""
Wavelet widget for EEG signals in pyecog
"""

import pyqtgraph_copy.pyqtgraph as pg
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import QRunnable, pyqtSlot, QThreadPool
import numpy as np
import scipy.signal as sg
from numba import jit
from timeit import default_timer as timer
import traceback, sys, inspect

from paired_graphics_view import DateAxis
# Interpret image data as row-major instead of col-major
pg.setConfigOptions(imageAxisOrder='row-major')

# @jit(parallel=True)
def morlet_wavelet(input_signal, dt=1, R=7, freq_interval=(), progress_signal = None, kill_switch = None):
    if kill_switch is None:
        kill_switch = [False]
    print('morlet_wavelet called')
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
        if kill_switch[0]:
            break
        N = int(2 * R / vf[k] / dt)  # Compute size of the wavelet: 2 standard deviations
        wave = sg.morlet(N, w=R, s=1, complete=0) / N * np.pi * 2  # Normalize de amplitude returned by sg.morlet
        result[k, :] = sg.fftconvolve(input_signal, wave, mode='same')
        if progress_signal is not None:
            progress_signal.emit(int(100*k/Nf))

    mask = np.zeros(result.shape)

    Nlist = (.5 * R / vf / dt).astype('int')  # 3 sigma COI
    for k in range(len(Nlist)):
        mask[k, :Nlist[k]] = np.nan
        mask[k, -Nlist[k]:] = np.nan

    return (result, mask, vf, kill_switch)


def morlet_wavelet_fft(input_signal, dt=1, R=7, freq_interval=(), progress_signal=None, kill_switch=None):
    if kill_switch is None:
        kill_switch = [False]
    print('morlet_wavelet called')
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
    print(Nf, Ns)
    result = np.zeros((Nf, Ns), dtype='complex')
    input_signalf = np.fft.fft(input_signal)
    Ni = len(input_signal)
    for k in range(Nf):
        if kill_switch[0]:
            break
        env = 2 * np.exp(-(np.arange(Ni)/Ni/dt - vf[k]) ** 2 / (2 * (vf[k] / R) ** 2)) / np.pi
        result[k, :] = np.fft.ifft(input_signalf * env)
        if progress_signal is not None:
            progress_signal.emit(int(100 * k / Nf))

    mask = np.zeros(result.shape)

    Nlist = (.5 * R / vf / dt).astype('int')  # 3 sigma COI
    for k in range(len(Nlist)):
        mask[k, :Nlist[k]] = np.nan
        mask[k, -Nlist[k]:] = np.nan

    return (result, mask, vf, kill_switch)

class WorkerSignals(QtCore.QObject):
    finished = QtCore.Signal()
    error = QtCore.Signal(tuple)
    result = QtCore.Signal(tuple)
    progress = QtCore.Signal(int)

class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        s = inspect.signature(fn)
        if 'progress_signal' in s.parameters.keys():
            self.kwargs['progress_signal'] = self.signals.progress

    @pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''

        # Retrieve args/kwargs here; and fire processing using them
        print('worker run called')
        try:
            print('calling worker function')
            result = self.fn(*self.args, **self.kwargs)
        except:
            print('worker Error')
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            print('worker emiting result')
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            print('worker emiting finished')
            self.signals.finished.emit()  # Done


class WaveletWindowItem(pg.GraphicsLayoutWidget):
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
        self.channel = 0
        self.R = 14

        # Contrast/color control
        self.hist = pg.HistogramLUTItem()
        self.hist.setImageItem(self.img)
        self.addItem(self.hist)
        self.hist.axis.setLabel( text = 'Amplitude', units = 'Log<sub>10</sub> a.u.')
        self.hist.gradient.loadPreset('viridis')
        self.hist_levels = None
        #
        # self.addItem(QtGui.QLabel("Wavelet factor R"))
        # spin = pg.SpinBox(value=self.R, bounds=[0, None])
        # self.addItem(spin)
        # spin.sigValueChanged.connect(lambda s: self.setR(s.value()))
        #
        # self.addWidget(QtGui.QLabel("Wavelet channel"))
        # spin = pg.SpinBox(value=self.channel, int=True, dec=True, minStep=1, step=1)
        # self.addItem(spin)
        # spin.sigValueChanged.connect(lambda s: self.setChannel(s.value()))



        # Multithread controls
        self.threadpool = QThreadPool()
        self.thread_killswitch_list = []

        # Generate image data
        self.update_data()
        self.vb = self.img.getViewBox()
        self.p1.setLabel('left', 'Frequency', units = 'Hz')
        self.p1.setLabel('bottom', 'Time', units = 's')

        self.hist.setLevels(self.data.min(), self.data.max())
        self.main_model.sigWindowChanged.connect(self.update_data)

    def setR(self,r):
        self.R = r
        print('Waelet R set to',r)
        self.update_data()

    def setChannel(self,c):
        self.channel = int(c)
        print('Wavlet channel set to ',c)
        self.update_data()

    def update_data(self):
        for s in self.thread_killswitch_list:  # Stop all previous wavelet computations
            s[0] = True
            print('Killswitch list:',self.thread_killswitch_list)
        self.data = np.array([[1, 0], [0, 1]])
        self.start_t = timer()
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
                data, time = self.main_model.project.get_data_from_range(self.main_model.window,channel = self.channel)
            if len(data) <= 10 :
                return
            print('Wavelet data shape:',data.shape)
            self.img.setImage(self.data*0)
            if self.hist_levels is not None: # Mantain levels from previous view if they exist
                self.hist.setLevels(*self.hist_levels)
            self.p1.setLabel('bottom', 'Computing Wavelet tranform...', units='s')
            self.show()
            print('Computing Wavelet...')
            self.dt = (time[10]-time[9])     # avoid time edge values
            s = [False]
            self.thread_killswitch_list.append(s)
            print('Killswitch list:',self.thread_killswitch_list)
            worker = Worker(morlet_wavelet_fft, data.ravel(),dt = self.dt ,R=self.R,freq_interval = (1,2/self.dt),
                            kill_switch=s)
            worker.signals.result.connect(self.update_image)
            worker.signals.progress.connect(self.update_progress)
            # Execute: restart threadpool and run worker
            self.threadpool.start(worker)
            # self.wav , self.coi, vf = morlet_wavelet(data.ravel(),dt = dt ,R=14,freq_interval = (1,2/dt,100))

    def update_progress(self,n):
        if n < 100:
            self.p1.setLabel('bottom', 'Computing Wavelet tranform:' + str(n) + '%', units='s')
        else:

            self.p1.setLabel('bottom', 'Time', units='s')

    def update_image(self,tuple):
        print('updating wavelet result...')
        self.wav, self.coi, vf, ks = tuple
        for i, s in enumerate(self.thread_killswitch_list): # clean up killswitch list
            if s is ks:
                del self.thread_killswitch_list[i]
                print(self.thread_killswitch_list)
        if ks[0]:  # If the task was killed do not update the plot
            print('Wavelet process killed: not ploting data')
            print('Killswitch list:', self.thread_killswitch_list)
            return
        self.data = np.log(np.abs(self.wav)+.001)
        self.img.setImage(self.data*(1-self.coi))
        self.img.resetTransform()
        ymin = np.log10(vf[0])
        ymax = np.log10(vf[-1])
        self.img.translate(0,ymin)
        self.img.scale(self.dt,(ymax-ymin)/self.data.shape[0])
        self.vb.setLimits(xMin=0, xMax=self.data.shape[1]*self.dt, yMin=ymin, yMax=ymax)
        self.vb.setRange(xRange=[0,self.data.shape[1]*self.dt])
        self.p1.setLabel('bottom', 'Time', units='s')
        if self.hist_levels is not None:  # Mantain levels from previous view if they exist
            self.hist.setLevels(*self.hist_levels)
        else:
            self.hist_levels = self.hist.getLevels()
        self.show()
        end_t = timer()
        print('Updated Wavelet in ',end_t-self.start_t, 'seconds')


class WaveletWindow(QWidget):
    def __init__(self, main_model = None):
        QWidget.__init__(self)
        self.layout = QtGui.QGridLayout()
        self.setLayout(self.layout)
        self.wavelet_item = WaveletWindowItem(main_model)

        self.controls_widget = QWidget()
        self.controls_layout = QtGui.QGridLayout()
        self.controls_widget.setLayout(self.controls_layout)
        self.channel_spin = pg.SpinBox(value=0,bounds=[0,None], int=True, minStep=1, step=1)
        self.channel_spin.valueChanged.connect(self.wavelet_item.setChannel)
        self.R_spin = pg.SpinBox(value=14.0, bounds=[5, None],step=1)
        self.R_spin.valueChanged.connect(self.wavelet_item.setR)
        self.controls_layout.addWidget(QtGui.QLabel('Channel'),0,0)
        self.controls_layout.addWidget(self.channel_spin,0,1)
        self.controls_layout.addWidget(QtGui.QLabel('Wavelet factor R'),0,2)
        self.controls_layout.addWidget(self.R_spin,0,3)

        self.layout.addWidget(self.controls_widget,1,0)
        self.layout.addWidget(self.wavelet_item,0,0)

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