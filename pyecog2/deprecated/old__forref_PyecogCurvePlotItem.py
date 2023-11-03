import sys
import os
import bisect
import traceback
import time

import numpy as np
import pandas as pd
import pickle as p

from PySide6 import QtGui, QtWidgets#,# uic
from PySide6.QtCore import QThread, Signal, Qt, QRect, QTimer
from scipy import signal, stats
import pyqtgraph as pg
import inspect
import h5py

def throw_error(error_text = None):
    msgBox = QtWidgets.QMessageBox()
    if error_text is None:
        msgBox.setText('Error caught! \n'+str(traceback.format_exc(1)))
    else:
        msgBox.setText('Error caught! \n'+str(error_text))
    msgBox.exec()
    return 0

os.path

class HDF5PlotCurveItem(pg.PlotCurveItem):
    """
    Create a subclass of PlotCurveItem for displaying a very large
    data set from an HDF5 file that does not neccesarilly fit in memory.

    The basic approach is to override PlotCurveItem.viewRangeChanged such that it
    reads only the portion of the HDF5 data that is necessary to display the visible
    portion of the data. This is further downsampled to reduce the number of samples
    being displayed.

    A more clever implementation of this class would employ some kind of caching
    to avoid re-reading the entire visible waveform at every update.
    """
    def __init__(self, main_gui_obj,viewbox = None, *args, **kwds):
        self.hdf5 = None
        self.hdf5_filtered_data = None
        self.time = None
        self.fs = None
        self.vb = viewbox
        self.limit = 20000 # downsample_limit # maximum number of samples to be plotted, 10000 orginally
        self.display_filter = None
        self.hp_cutoff = None
        self.lp_cutoff = None
        self.main_gui_obj = main_gui_obj
        #self.main_gui_obj.downsample_spinbox.valueChanged.connect(self.downsample_spinbox_change)

        self.fft_plot = None
        pg.PlotCurveItem.__init__(self, *args, **kwds)
        if pg.CONFIG_OPTIONS['background'] == 'w':
            self.pen = (0,0,0, 0.1)
        else:
            self.pen = (255,255,255)

    def keyPressEvent(self, event):
        ''' this doesnt work, change key press to correct it.'''
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()
        else:
            pass

    def setHDF5(self, data, time, fs):
        self.hdf5 = data
        self.time = time
        self.fs = fs
        #print(data.shape, time.shape)
        #try:
        #    assert(self.hdf5.shape == self.time.shape)
        #except Exception:
        #    throw_error()
        #print ( self.hdf5.shape, self.time.shape)
        self.updateHDF5Plot()

    def display_filter_update(self):
        self.wipe_filtered_data()
        self.get_display_filter_settings()
        self.updateHDF5Plot()
        pass

    def get_display_filter_settings(self):
        self.hp_cutoff = self.main_gui_obj.hp_filter_freq.value()
        self.lp_cutoff = self.main_gui_obj.lp_filter_freq.value()
        self.hp_toggle = self.main_gui_obj.checkbox_hp_filter.isChecked()
        self.lp_toggle = self.main_gui_obj.checkbox_lp_filter.isChecked()
        self.display_filter =  self.hp_toggle + self.lp_toggle > 0

    def wipe_filtered_data(self):
        self.hdf5_filtered_data = None

    def filter(self, cutoff, data, type):
        '''

        Args:
            cutoff: corner freq in hz
            data:
            type: 'lowpass' of 'highpass'

        Returns:

        '''
        nyq = 0.5 * self.fs
        cutoff_decimal = cutoff / nyq
        if cutoff_decimal > 1:
            if type == 'lowpass':
                self.main_gui_obj.lp_filter_freq.setValue(nyq)
            elif type == 'highpass':
                self.main_gui_obj.hp_filter_freq.setValue(nyq)

        b, a = signal.butter(2, cutoff_decimal, type, analog=False)
        filtered_data = signal.filtfilt(b, a, data)
        return filtered_data

    def viewRangeChanged(self):
        self.updateHDF5Plot()

    def downsample_spinbox_change(self):
        self.set_downsample_limit()
        self.updateHDF5Plot()

    def set_downsample_limit(self):
        spinbox_val = self.main_gui_obj.downsample_spinbox.value()
        self.limit = spinbox_val *1000
        # this is the number of datapoints to show

    def get_data_window_for_fft(self,x,start,stop):
        x = x[start:stop]
        i = int(2 ** np.floor(np.log2(x.shape[0])))
        print(i, x.shape[0], x.shape[0]-i)
        return x[:i]


    def calc_fft(self,x,start,stop):
        x = self.get_data_window_for_fft(x,start,stop)
        fft_result = np.fft.rfft(x)
        freqs = np.fft.rfftfreq(x.shape[0], d=1 / self.fs)
        return fft_result, freqs


    def plot_fft(self, x, t, start,stop):
        # here get fft and plot on the subplot that will exist
        try:
            fft_result, freqs = self.calc_fft(x,start,stop)
        except Exception:
            throw_error()
            return 0
        try:
            # self.fft_plot.curve.setData(t[start:stop],x[start:stop])
            self.main_gui_obj.fft_plot.curve.setData(freqs,np.abs(fft_result))
        except Exception:
            #self.fft_plot.curve = self.fft_plot.plot(t[start:stop],x[start:stop],pen = (255,255,255))
            self.main_gui_obj.fft_plot.curve = self.main_gui_obj.fft_plot.plot(freqs,np.abs(fft_result),pen = (0,0,0))

    def updateHDF5Plot(self):
        if self.hdf5 is None:
            self.setData([])
            return 0


        if self.display_filter:
            if self.hdf5_filtered_data is None:
                self.hdf5_filtered_data = self.hdf5
                if self.hp_toggle:
                    try:
                        self.hdf5_filtered_data = self.filter(self.hp_cutoff,
                                                              self.hdf5_filtered_data,
                                                              'highpass')
                    except Exception:
                        throw_error()

                if self.lp_toggle:
                    try:
                        self.hdf5_filtered_data = self.filter(self.lp_cutoff,
                                                              self.hdf5_filtered_data,
                                                              'lowpass')
                    except Exception:
                        throw_error()

            hdf5data = self.hdf5_filtered_data

        else:
            hdf5data = self.hdf5
            #print('Shapes:', hdf5data.shape, self.time.shape)

        # Determine what data range must be read from HDF5
        xrange = [i*self.fs for i in self.vb.viewRange()[0]]
        start = max(0,int(xrange[0])-1)
        stop = min(len(hdf5data), int(xrange[1]+2))
        if stop-start < 1:
            print('didnt update')
            return 0

        #if self.main_gui_obj.show_fft_checkbox.isChecked():
            #self.plot_fft(self.hdf5, self.time, start, stop)
        # Decide by how much we should downsample
        ds = int((stop-start) / self.limit) + 1
        #print(ds, ' x downsample')
        if ds == 1:
            # Small enough to display with no intervention.
            visible_y = hdf5data[start:stop]
            visible_x = self.time[start:stop]
            scale = 1
        else:
            # Here convert data into a down-sampled array suitable for visualizing.
            # Must do this piecewise to limit memory usage.
            samples = (1+(stop-start) // ds)
            #print(stop, start, stop-start)
            #print(samples, 'samples')
            visible_y = np.zeros(samples*2, dtype=hdf5data.dtype)
            visible_x = np.zeros(samples*2, dtype=self.time.dtype)
            sourcePtr = start
            targetPtr = 0
            try:
                # read data in chunks of ~1M samples
                chunkSize = (1000000//ds) * ds
                while sourcePtr < stop-1:
                    #print('Shapes:',hdf5data.shape, self.time.shape)
                    chunk = hdf5data[sourcePtr:min(stop,sourcePtr+chunkSize)]
                    chunk_x = self.time[sourcePtr:min(stop,sourcePtr+chunkSize)]
                    sourcePtr += len(chunk)
                    #print('y,x shape',chunk.shape, chunk_x.shape)

                    # reshape chunk to be integral multiple of ds
                    chunk = chunk[:(len(chunk)//ds) * ds].reshape(len(chunk)//ds, ds)
                    chunk_x = chunk_x[:(len(chunk_x)//ds) * ds].reshape(len(chunk_x)//ds, ds)

                    # compute max and min
                    #chunkMax = chunk.max(axis=1)
                    #chunkMin = chunk.min(axis=1)

                    mx_inds = np.argmax(chunk, axis=1)
                    mi_inds = np.argmin(chunk, axis=1)
                    row_inds = np.arange(chunk.shape[0])

                    chunkMax = chunk[row_inds, mx_inds]
                    chunkMin = chunk[row_inds, mi_inds]

                    #print(chunk_x.shape, row_inds, mx_inds)
                    chunkMax_x = chunk_x[row_inds, mx_inds]
                    chunkMin_x = chunk_x[row_inds, mi_inds]

                    # interleave min and max into plot data to preserve envelope shape
                    visible_y[targetPtr:targetPtr+chunk.shape[0]*2:2] = chunkMin
                    visible_y[1+targetPtr:1+targetPtr+chunk.shape[0]*2:2] = chunkMax
                    visible_x[targetPtr:targetPtr+chunk_x.shape[0]*2:2] = chunkMin_x
                    visible_x[1+targetPtr:1+targetPtr+chunk_x.shape[0]*2:2] = chunkMax_x

                    targetPtr += chunk.shape[0]*2

                visible_x = visible_x[:targetPtr]
                visible_y = visible_y[:targetPtr]
                #print('**** now downsampling')
                #print(visible_y.shape, visible_x.shape)
                scale = ds * 0.5
            except Exception:
                throw_error()
                return 0
            # TODO: setPos, scale, resetTransform methods... scale?
        self.setData(visible_x, visible_y, pen=self.pen) # update the plot
        #self.setPos(start, 0) # shift to match starting index ### Had comment out to stop it breaking... when limit is >0?!
        self.resetTransform()
        #self.scale(scale, 1)  # scale to match downsampling
