# -*- coding: utf-8 -*-
"""
Wavelet widget for EEG signals in pyecog
"""

import pyqtgraph as pg
from PySide2 import QtCore, QtGui
from PySide2.QtWidgets import QApplication, QWidget
from PySide2.QtCore import QRunnable, Slot, QThreadPool
import numpy as np
import scipy.signal as sg
from timeit import default_timer as timer
import traceback, inspect, sys
from pyecog2.pyecog_plot_item import PyecogCursorItem
import colorsys
import multiprocessing as mp

# Interpret image data as row-major instead of col-major
pg.setConfigOptions(imageAxisOrder='row-major')
hues = np.linspace(0,1,256)

hues = np.linspace(0,1,7)
colors = [tuple([*colorsys.hsv_to_rgb(h,1,255),255]) for h in hues]
hsvcolormap = pg.ColorMap(hues,colors)

# @jit(parallel=True)
def morlet_wavelet(input_signal, dt=1, R=7, freq_interval=(), progress_signal = None, kill_switch = None, multi_proc = True):
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

    if multi_proc:
        def par_sgconvolve(input):
            N, signal = input
            wave = sg.morlet(N, w=R, s=1, complete=0) / N * np.pi * 2  # Normalize de amplitude returned by sg.morlet
            return sg.oaconvolve(signal, wave, mode='same')

        n_cores = max(int(np.ceil(mp.cpu_count()/4))-1,1)
        print(f'Wavelet using multiproc with {n_cores} cores')
        for k0 in range(0,Nf,n_cores):
            input_signal_list = [input_signal]*n_cores
            if kill_switch[0]:
                break
            k_list = list(range(k0,min(k0+n_cores,Nf)))
            N_list = (2 * R / vf[k_list[0]:k_list[-1]] / dt).astyoe(int)
            arg_list = zip(N_list,input_signal_list)
            with mp.Pool(n_cores)as p:
                batch = p.map(par_sgconvolve,arg_list)
            result[k_list[0]:k_list[-1], :]
            if progress_signal is not None:
                progress_signal.emit(int(100*k_list[-1]/Nf))

    else:
        for k in range(Nf):
            if kill_switch[0]:
                break
            N = int(2 * R / vf[k] / dt)  # Compute size of the wavelet: 2 standard deviations
            wave = sg.morlet(N, w=R, s=1, complete=0) / N * np.pi * 2   # Normalize de amplitude returned by sg.morlet
            # result[k, :] = sg.fftconvolve(input_signal, wave, mode='same')
            result[k, :] = sg.oaconvolve(input_signal, wave, mode='same')
            if progress_signal is not None:
                progress_signal.emit(int(100*k/Nf))

    mask = np.zeros(result.shape)

    Nlist = (.5 * R / vf / dt).astype('int')  # 3 sigma COI
    for k in range(len(Nlist)):
        mask[k, :Nlist[k]] = np.nan
        mask[k, -Nlist[k]:] = np.nan

    return (result, mask, vf, kill_switch)


def par_fftconvolve(input):
    if len(input) == 5:  # no cross wave
        dt, R, v, N, signal_f = input  # compute cross-wavelet
    elif len(input) == 6:
        dt, R, v, N, signal_f, cross_signalf = input

    env = 2 * np.exp(-(np.arange(N) / N / dt - v) ** 2 / (2 * (v / R) ** 2))  # / np.pi
    if len(input) == 5:
        return np.fft.ifft(signal_f * env)
    else:
        return (np.fft.ifft(signal_f * env), np.fft.ifft(cross_signalf * env))

def morlet_wavelet_fft(input_signal, dt=1, R=7, freq_interval=(), progress_signal=None, cross_data=None,
                       kill_switch=None, multi_proc = True):
    if kill_switch is None:
        kill_switch = [False]
    # print('morlet_wavelet called')
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
    # print(Nf, Ns)
    result = np.zeros((Nf, Ns), dtype='complex')
    input_signalf = np.fft.fft(input_signal)
    if cross_data is not None:
        result_cross = np.zeros((Nf, Ns), dtype='complex')
        cross_dataf = np.fft.fft(cross_data)
    else:
        result_cross = None

    Ni = len(input_signal)

    if multi_proc:
        n_cores = max(int(np.ceil(mp.cpu_count()/4))-1,1)
        print(f'Wavelet using multiproc with {n_cores} cores')
        for k0 in range(0,Nf,n_cores):
            input_signal_list = [input_signalf]*n_cores
            if cross_data is not None:
                input_cross_signal_list = [cross_dataf]*n_cores
            if kill_switch[0]:
                break
            k_list = list(range(k0,min(k0+n_cores,Nf)))
            dt_list = [dt] * len(k_list)
            R_list = [R] * len(k_list)
            v_list = vf[k_list[0]:k_list[-1]+1]
            N_list = [Ni] * len(k_list)
            if cross_data is None:
                arg_list = list(zip(dt_list,R_list,v_list,N_list,input_signal_list))
            else:
                arg_list = list(zip(v_list,N_list,input_signal_list,input_cross_signal_list))

            print(f'Wabelet processing klist:{k_list}',end=' ')
            with mp.Pool(n_cores)as p:
                batch = p.map(par_fftconvolve,arg_list)
                if cross_data is not None:
                    batch, batchcross = zip(*batch)
            result[k_list[0]:k_list[-1]+1, :] = batch
            print(np.sum(np.abs(batch),axis=1),end='')
            if cross_data is not None:
                result_cross[k_list[0]:k_list[-1]+1, :] = batchcross

            if progress_signal is not None:
                progress_signal.emit(int(100*k_list[-1]/Nf))
            print('done')
    else:
        for k in range(Nf):
            if kill_switch[0]:
                break
            env = 2 * np.exp(-(np.arange(Ni)/Ni/dt - vf[k]) ** 2 / (2 * (vf[k] / R) ** 2)) #/ np.pi
            result[k, :] = np.fft.ifft(input_signalf * env)
            if cross_data is not None:
                result_cross[k, :] = np.fft.ifft(cross_dataf * env)
            if progress_signal is not None:
                progress_signal.emit(int(100 * k / Nf))

    mask = np.zeros(result.shape)
    Nlist = (.5 * R / vf / dt).astype('int')  # 2 sigma COI
    for k in range(len(Nlist)):
        mask[k, :Nlist[k]] = np.nan
        mask[k, -Nlist[k]:] = np.nan

    return (result, mask, vf, kill_switch, result_cross)

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

    @Slot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''
        import sys
        # Retrieve args/kwargs here; and fire processing using them
        # print('worker run called')
        try:
            # print('calling worker function')
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            # print('worker Error')
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            # print('worker emiting result')
            if type(result) is not tuple:
                result = (1,1)
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            # print('worker emiting finished')
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
        self.cursor = PyecogCursorItem(pos=0)
        self.main_model.sigTimeChanged.connect(lambda: self.cursor.setPos(self.main_model.time_position - self.main_model.window[0]))
        self.cursor.sigPositionChanged.connect(lambda: self.main_model.set_time_position(self.cursor.getXPos()+ self.main_model.window[0]))
        self.p1.addItem(self.cursor)

        self.channel = 0
        self.R = 14
        self.cross_channel = -1
        self.setBackground(self.main_model.color_settings['brush'])

        # Contrast/color control
        self.hist = pg.HistogramLUTItem()
        self.hist.setImageItem(self.img)
        self.addItem(self.hist)
        self.hist.axis.setLabel( text = 'Amplitude', units = 'Log<sub>10</sub> a.u.')
        self.hist.gradient.loadPreset('viridis')
        self.hist_levels = None
        self.hist_levels_cross = None
        self.last_plot_was_cross = False
        self.last_plot_was_wave = False
        self.hist.vb.enableAutoRange(self.hist.vb.XYAxes,enable=.99)
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

    def setCrossChannel(self,c):
        self.cross_channel = int(c)
        print('Wavlet cross channel set to ',c)
        self.update_data()

    def update_data(self):
        for s in self.thread_killswitch_list:  # Stop all previous wavelet computations
            s[0] = True
            # print('Killswitch list:',self.thread_killswitch_list)
        self.data = np.array([[1, 0], [0, 1]])
        self.start_t = timer()

        if self.isVisible():
            self.setBackground(self.main_model.color_settings['brush'])
            if self.main_model is None:
                data = np.random.randn(300*250)
                data[200:800] += np.sin(np.arange(600)*10)
                time = np.arange(300*250)/250
                print('random data')
            else:
                if self.main_model.window[1] - self.main_model.window[0] > 3600:
                    print('Window too large to compute Wavelet (>3600s)')
                    self.p1.setLabel('bottom', 'Window too large to compute Wavelet (>3600s)')
                    return
                # print('window' , self.main_model.window)
                data, time = self.main_model.project.get_data_from_range(self.main_model.window,channel = self.channel)
                if len(data) <= 10:
                    return
                if self.cross_channel!=-1 and self.cross_channel != self.channel:
                    cross_data,_ = self.main_model.project.get_data_from_range(self.main_model.window,channel = self.cross_channel)
                    cross_data = cross_data.ravel()
                    if len(cross_data) != len(data):
                        return
                else:
                    cross_data = None

            # save levels from colorbar
            if self.last_plot_was_wave:
                if self.hist_levels is not None:
                    # print('updating hist_levels',self.hist_levels )
                    self.hist_levels = self.hist.getLevels()
                    # print('updataed hist_levels',self.hist_levels )
            elif self.last_plot_was_cross:
                if self.hist_levels_cross is not None:
                    # print('updating hist_levels_cross',self.hist_levels_cross )
                    self.hist_levels_cross = self.hist.getLevels()
                    # print('updataed hist_levels_cross',self.hist_levels_cross)
            # print('Wavelet data shape:',data.shape)
            self.last_plot_was_wave = False
            self.last_plot_was_cross = False
            self.img.setImage(self.data*0)
            # if self.hist_levels is not None: # Mantain levels from previous view if they exist
            #     self.hist.setLevels(*self.hist_levels)
            self.p1.setLabel('bottom', 'Computing Wavelet tranform...', units='')
            self.show()
            # print('Computing Wavelet...')
            if len(time.shape)==1:
                self.dt = (time[10]-time[9])  # avoid time edge values
            else:
                self.dt = (time[10] - time[9])[0]
            s = [False]
            self.thread_killswitch_list.append(s)
            # print('Killswitch list:',self.thread_killswitch_list)
            worker = Worker(morlet_wavelet_fft, data.ravel(),dt = self.dt ,R=self.R,freq_interval = (1,2/self.dt),
                            cross_data = cross_data, kill_switch=s)
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
        # print('updating wavelet result...')
        self.wav, self.coi, vf, ks, self.cross_wav = tuple
        for i, s in enumerate(self.thread_killswitch_list): # clean up killswitch list
            if s is ks:
                del self.thread_killswitch_list[i]
                print(self.thread_killswitch_list)
        if ks[0]:  # If the task was killed do not update the plot
            # print('Wavelet process killed: not ploting data')
            # print('Killswitch list:', self.thread_killswitch_list)
            return
        if self.cross_wav is not None: # plotting cross wavelet
            self.last_plot_was_cross = True
            cross_wav = self.wav*np.conj(self.cross_wav)
            # self.value = np.log10(np.abs(cross_wav)+1)/2
            self.value = np.log10(np.sqrt(np.abs(cross_wav))+1.001)
            maxvalue = np.max(self.value)
            self.data = hsvcolormap.map((np.angle(cross_wav)/(2*np.pi))%1)/256
            # self.data = np.apply_along_axis(lambda x:colorsys.hsv_to_rgb(*x), 0,  #apply function over 0th axis
            #     np.array([np.angle(cross_wav)/(2*np.pi)%1, # hue
            #               np.ones(self.wav.shape), # saturation
            #               value-minvalue]))  # temporary value
            # self.data = np.moveaxis(self.data,0,-1) +minvalue
            print('data shape',self.data.shape)
            self.img.setImage(self.data*((self.value + self.coi)[:,:,np.newaxis]), # *(value[:,:,np.newaxis]),
                              autoLevels=False)
            # hsvim = plt.cm.hsv(np.angle(result) / 2 / np.pi + .5)
            # intensity = np.abs(result)[:, :, np.newaxis]

            self.hist.gradient.loadPreset('spectrum')
            self.hist.axis.setLabel( text = 'Hue: Phase (0 - 360<sup>o</sup>) <br> Saturation: Log Coherence', units = 'V')
            if self.hist_levels_cross is None:
                self.hist_levels_cross = [0,maxvalue]
                # self.hist.setLevels(*self.hist_levels_cross)

        else:  # plotting normal wavelet
            self.last_plot_was_wave = True
            self.data = np.log10(np.abs(self.wav)+1e-9)  # +1e-3
            self.img.setImage(self.data + self.coi)
            self.hist.gradient.loadPreset('viridis')
            self.hist.axis.setLabel(text='Amplitude', units='Log<sub>10</sub> V')

        self.img.resetTransform()
        ymin = np.log10(vf[0])
        ymax = np.log10(vf[-1])
        self.img.translate(0,ymin)
        self.img.scale(self.dt,(ymax-ymin)/self.data.shape[0])
        self.vb.setLimits(xMin=0, xMax=self.data.shape[1]*self.dt, yMin=ymin, yMax=ymax)
        self.vb.setRange(xRange=[0,self.data.shape[1]*self.dt])
        self.p1.setLabel('bottom', 'Time', units='s')
        if self.cross_wav is None:
            if self.hist_levels is not None:  # Mantain levels from previous standard wavelet view if they exist
                self.hist.setLevels(*self.hist_levels)
            else:
                self.hist.autoHistogramRange()
                self.hist_levels = self.hist.getLevels()
        else:
            if self.hist_levels_cross is not None:  # Mantain levels from previous cross-wavelet view if they exist
                self.hist.setLevels(*self.hist_levels_cross)
            else:
                self.hist.autoHistogramRange()
                self.hist_levels_cross = self.hist.getLevels()

        self.cursor.setPos(self.main_model.time_position - self.main_model.window[0])
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
        self.channel_spin = pg.SpinBox(value=0,bounds=[0,None], int=True, minStep=1, step=1,compactHeight=False)
        self.channel_spin.valueChanged.connect(self.wavelet_item.setChannel)
        self.cross_channel_spin = pg.SpinBox(value=-1,bounds=[-1,None], int=True, minStep=1, step=1,compactHeight=False)
        self.cross_channel_spin.valueChanged.connect(self.wavelet_item.setCrossChannel)
        self.R_spin = pg.SpinBox(value=14.0, bounds=[5, None],step=1,compactHeight=False)
        self.R_spin.valueChanged.connect(self.wavelet_item.setR)
        self.controls_layout.addWidget(QtGui.QLabel('Channel'),0,0)
        self.controls_layout.addWidget(self.channel_spin,0,1,)
        self.controls_layout.addWidget(QtGui.QLabel('Wavelet factor R'),0,2)
        self.controls_layout.addWidget(self.R_spin,0,3)
        self.controls_layout.addWidget(QtGui.QLabel('Cross wavelet Channel'),0,4)
        self.controls_layout.addWidget(self.cross_channel_spin,0,5)

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