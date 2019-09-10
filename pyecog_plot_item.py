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

    def __init__(self, x, y, fs, viewbox, *args, **kwds):
        '''
        Todo: I really dont like passining in the viewbox
        This should be assigned instead when they get added to the plot
        '''
        self.yscale_data =1
        self.x = x # initially
        self.y = y
        self.fs = fs
        self.parent_viewbox = viewbox
        self.n_display_points = 10000 # this should be horizontal resolution of screen
        super().__init__(*args, **kwds)
        self.resetTransform()


    def viewRangeChanged(self):
        self.setData_with_envelope()

    def set_pen(self):
        pass

    def set_data(self, x, y,fs):
        self.x  = x # todo this needs to be compat with memmap
        self.y  = y
        self.fs = fs

        self.setData_with_envelope()


    def setData_with_envelope(self):
        '''# todo clean up e.g. var names x y'''
        if self.x is None:
            self.setData([])
            return 0

        x_range = [i*self.fs for i in self.parent_viewbox.viewRange()[0]]
        start = max(0,int(x_range[0])-1)
        stop  = min(len(self.x), int(x_range[1]+2))
        if stop-start < 1:
            print('didnt update')
            return 0

        # Decide by how much we should downsample
        ds = int((stop-start) / self.n_display_points) + 1
        if ds == 1:
            # Small enough to display with no intervention.
            visible_y = self.x[start:stop]
            visible_x = self.y[start:stop]
            scale = 1
        else:
            # Here convert data into a down-sampled array suitable for visualizing.
            # Must do this piecewise to limit memory usage.
            samples = (1+(stop-start) // ds)
            visible_y = np.zeros(samples*2, dtype=self.x.dtype)
            visible_x = np.zeros(samples*2, dtype=self.y.dtype)
            sourcePtr = start
            targetPtr = 0
            try:
                # read data in chunks of ~1M samples
                chunkSize = (1000000//ds) * ds
                while sourcePtr < stop-1:
                    #print('Shapes:',hdf5data.shape, self.time.shape)
                    chunk   = self.x[sourcePtr:min(stop,sourcePtr+chunkSize)]
                    chunk_x = self.y[sourcePtr:min(stop,sourcePtr+chunkSize)]
                    sourcePtr += len(chunk)
                    #print('y,x shape',chunk.shape, chunk_x.shape)

                    # reshape chunk to be integral multiple of ds
                    chunk   = chunk[:(len(chunk)//ds) * ds].reshape(len(chunk)//ds, ds)
                    chunk_x = chunk_x[:(len(chunk_x)//ds) * ds].reshape(len(chunk_x)//ds, ds)

                    # compute max and min
                    #chunkMax = chunk.max(axis=1)
                    #chunkMin = chunk.min(axis=1)

                    mx_inds = np.argmax(chunk_x, axis=1)
                    mi_inds = np.argmin(chunk_x, axis=1)
                    row_inds = np.arange(chunk_x.shape[0])

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
            except:
                throw_error()
                return 0
        #print(visible_x.shape, visible_y.shape)
        #print(visible_x)
        # maybe be parent item?
        self.setData(y=visible_x*self.yscale_data*self.parent_viewbox.yscale_data,
         x=visible_y, pen=(0,0,0,100),antialias=False) # update the plot
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
