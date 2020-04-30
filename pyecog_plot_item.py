from PyQt5 import QtGui, QtWidgets#,# uic
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QRect, QTimer
from scipy import signal, stats
import pyqtgraph as pg
import numpy as np

class PyecogPlotCurveItem(pg.PlotCurveItem):

    ''' Hmm seems like you need the graphics scene subcalss of pyqtgraph
    for how they get all trhe drags
    also there is the  vewbox presumeableig that handles stuff - view? plotitme.?#

    also maybe the downsampling in plotitem?
    '''

    def __init__(self, y, fs, viewbox, *args, **kwds):
        '''
        Todo: I really dont like passining in the viewbox
        This should be assigned instead when they get added to the plot
        '''
        self.accept_mousewheel_transformations = True
        self.yscale_data =1
        self.y = y
        self.fs = fs
        self.parent_viewbox = viewbox
        self.pen = (0,0,0,100)
        self.n_display_points = 5000 # this should be horizontal resolution of window
        super().__init__(*args, **kwds)
        self.resetTransform()

    def viewRangeChanged(self):
        self.setData_with_envelope()

    def set_pen(self, pen):
        self.pen = pen

    def set_data(self, y,fs):
        self.y  = y
        self.fs = fs
        self.setData_with_envelope()

    def setData_with_envelope(self):
        '''# todo clean up e.g. var names x y'''
        #print('set data')
        if self.y is None:
            self.setData([],1)
            return 0

        x_range = [i*self.fs for i in self.parent_viewbox.viewRange()[0]]
        #print(x_range)
        start = max(0,int(x_range[0])-1)
        stop  = min(len(self.y), int(x_range[1]+2))
        #print(start, stop)
        if stop-start < 1:
            #print('pyecog plotcurve item didnt update')
            return 0

        # Decide by how much we should downsample
        ds = int((stop-start) / self.n_display_points) + 1
        if ds == 1:
            # Small enough to display with no intervention.
            visible_data = self.y[start:stop]
            visible_time = np.linspace(start/self.fs, stop/self.fs, len(visible_data))#visible_time[:targetPtr]
            #print(start, stop)

        else:
            # Here convert data into a down-sampled array suitable for visualizing.
            # Must do this piecewise to limit memory usage.
            samples = (1+(stop-start) // ds)
            visible_data = np.zeros(samples*2, dtype=self.y.dtype)
            sourcePtr = start
            targetPtr = 0
            try:
                # read data in chunks of ~1M samples
                chunkSize = (1e6//ds) * ds
                while sourcePtr < stop-1:
                    #print('Shapes:',hdf5data.shape, self.time.shape)
                    #chunk   = self.x[sourcePtr:min(stop,sourcePtr+chunkSize)]
                    chunk_data = self.y[sourcePtr:min(stop,sourcePtr+chunkSize)]
                    sourcePtr += chunkSize
                    #print('y,x shape',chunk.shape, chunk_data.shape)

                    # reshape chunk to be integer multiple of ds
                    chunk_data = chunk_data[:(len(chunk_data)//ds) * ds].reshape(len(chunk_data)//ds, ds)

                    # compute max and min
                    #chunkMax = chunk.max(axis=1)
                    #chunkMin = chunk.min(axis=1)

                    mx_inds = np.argmax(chunk_data, axis=1)
                    mi_inds = np.argmin(chunk_data, axis=1)
                    row_inds = np.arange(chunk_data.shape[0])

                    # chunkMax = chunk[row_inds, mx_inds]
                    # chunkMin = chunk[row_inds, mi_inds]

                    #print(chunk_data.shape, row_inds, mx_inds)
                    chunkMax_x = chunk_data[row_inds, mx_inds]
                    chunkMin_x = chunk_data[row_inds, mi_inds]

                    # interleave min and max into plot data to preserve envelope shape
                    # visible_time[targetPtr:targetPtr+chunk.shape[0]*2:2] = chunkMin
                    # visible_time[1+targetPtr:1+targetPtr+chunk.shape[0]*2:2] = chunkMax
                    visible_data[targetPtr:targetPtr+chunk_data.shape[0]*2:2] = chunkMin_x
                    visible_data[1+targetPtr:1+targetPtr+chunk_data.shape[0]*2:2] = chunkMax_x

                    targetPtr += chunk_data.shape[0]*2

                visible_data = visible_data[:targetPtr]
                visible_time = np.linspace(start/self.fs, stop/self.fs, len(visible_data))#visible_time[:targetPtr]
                #print('**** now downsampling')
                #print(visible_time.shape, visible_data.shape)
                scale = ds * 0.5
            except:
                throw_error()
                return 0

        self.setData(y=visible_data, x=visible_time, pen=self.pen,antialias=True) # update the plot
        #self.resetTransform()

    def itemChange(self, *args):
        # here we may try to match?/ pair
    #    print('ive changed')
        #print(args)
    #    print('I should pass on ')
        return super().itemChange(*args)


    def mousePressEvent(self, ev):
        ''' #todo forget difference between this and the click and drag evnets belwo '''
        if self.clickable:
            #print('ive been cliked')
            #super(pg.PlotCurveItem,self).mousePressEvent(ev)
            ev.ignore()
        else:
            ev.ignore()

    def mouseClickEvent(self, ev):
        #print('mouseClickEvent plotcurveitem')
        pass
    def mouseDragEvent(self, ev):
        #print('mouseDragEvent plotcurveitem')
        pass

    def hoverEvent(self, ev):
        if self.clickable:
            #print('hoverEvent sent')
            clickfocus = ev.acceptClicks(Qt.LeftButton)
            #print(clickfocus)
            dragfocus  = ev.acceptDrags(Qt.LeftButton)
            #print(dragfocus)
            #print('change colour!')
            #print('is this focus?')
