from PyQt5 import QtGui, QtWidgets, QtCore
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QRect, QTimer
from scipy import signal, stats
import pyqtgraph_copy.pyqtgraph as pg
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
        self.yscale_data = 1
        self.y = y
        self.fs = fs
        self.parent_viewbox = viewbox
        self.pen = (0, 0, 0, 100)
        self.n_display_points = 5000  # this should be horizontal resolution of window
        super().__init__(*args, **kwds)
        self.resetTransform()
        self.setZValue(1)

    def viewRangeChanged(self):
        self.setData_with_envelope()

    def set_pen(self, pen):
        self.pen = pen

    def set_data(self, y, fs):
        self.y = y
        self.fs = fs
        self.setData_with_envelope()

    def setData_with_envelope(self):
        '''# todo clean up e.g. var names x y'''
        # print('set data')
        if self.y is None:
            self.setData([], 1)
            return 0

        x_range = [i * self.fs for i in self.parent_viewbox.viewRange()[0]]
        # print(x_range)
        start = max(0, int(x_range[0]) - 1)
        stop = min(len(self.y), int(x_range[1] + 2))
        # print(start, stop)
        if stop - start < 1:
            # print('pyecog plotcurve item didnt update')
            return 0

        # Decide by how much we should downsample
        ds = int((stop - start) / self.n_display_points) + 1
        if ds == 1:
            # Small enough to display with no intervention.
            visible_data = self.y[start:stop]
            visible_time = np.linspace(start / self.fs, stop / self.fs, len(visible_data))  # visible_time[:targetPtr]
            # print(start, stop)

        else:
            # Here convert data into a down-sampled array suitable for visualizing.
            # Must do this piecewise to limit memory usage.
            samples = (1 + (stop - start) // ds)
            visible_data = np.zeros(samples * 2, dtype=self.y.dtype)
            sourcePtr = start
            targetPtr = 0
            try:
                # read data in chunks of ~1M samples
                chunkSize = (1e6 // ds) * ds
                while sourcePtr < stop - 1:
                    # print('Shapes:',hdf5data.shape, self.time.shape)
                    # chunk   = self.x[sourcePtr:min(stop,sourcePtr+chunkSize)]
                    chunk_data = self.y[sourcePtr:min(stop, sourcePtr + chunkSize)]
                    sourcePtr += chunkSize
                    # print('y,x shape',chunk.shape, chunk_data.shape)

                    # reshape chunk to be integer multiple of ds
                    chunk_data = chunk_data[:(len(chunk_data) // ds) * ds].reshape(len(chunk_data) // ds, ds)

                    # compute max and min
                    # chunkMax = chunk.max(axis=1)
                    # chunkMin = chunk.min(axis=1)

                    mx_inds = np.argmax(chunk_data, axis=1)
                    mi_inds = np.argmin(chunk_data, axis=1)
                    row_inds = np.arange(chunk_data.shape[0])

                    # chunkMax = chunk[row_inds, mx_inds]
                    # chunkMin = chunk[row_inds, mi_inds]

                    # print(chunk_data.shape, row_inds, mx_inds)
                    chunkMax_x = chunk_data[row_inds, mx_inds]
                    chunkMin_x = chunk_data[row_inds, mi_inds]

                    # interleave min and max into plot data to preserve envelope shape
                    # visible_time[targetPtr:targetPtr+chunk.shape[0]*2:2] = chunkMin
                    # visible_time[1+targetPtr:1+targetPtr+chunk.shape[0]*2:2] = chunkMax
                    visible_data[targetPtr:targetPtr + chunk_data.shape[0] * 2:2] = chunkMin_x
                    visible_data[1 + targetPtr:1 + targetPtr + chunk_data.shape[0] * 2:2] = chunkMax_x

                    targetPtr += chunk_data.shape[0] * 2

                visible_data = visible_data[:targetPtr]
                visible_time = np.linspace(start / self.fs, stop / self.fs,
                                           len(visible_data))  # visible_time[:targetPtr]
                # print('**** now downsampling')
                # print(visible_time.shape, visible_data.shape)
                scale = ds * 0.5
            except:
                throw_error()
                return 0

        self.setData(y=visible_data, x=visible_time, pen=self.pen, antialias=True)  # update the plot
        # self.resetTransform()

    def itemChange(self, *args):
        # here we may try to match?/ pair
        #    print('ive changed')
        # print(args)
        #    print('I should pass on ')
        return super().itemChange(*args)

    def mousePressEvent(self, ev):
        ''' #todo forget difference between this and the click and drag evnets belwo '''
        if self.clickable:
            # print('ive been cliked')
            # super(pg.PlotCurveItem,self).mousePressEvent(ev)
            ev.ignore()
        else:
            ev.ignore()

    def mouseClickEvent(self, ev):
        # print('mouseClickEvent plotcurveitem')
        pass

    def mouseDragEvent(self, ev):
        # print('mouseDragEvent plotcurveitem')
        pass

    def hoverEvent(self, ev):
        if self.clickable:
            # print('hoverEvent sent')
            clickfocus = ev.acceptClicks(Qt.LeftButton)
            # print(clickfocus)
            dragfocus = ev.acceptDrags(Qt.LeftButton)
            # print(dragfocus)
            # print('change colour!')
            # print('is this focus?')


class PyecogLinearRegionItem(pg.LinearRegionItem):
    '''
    Class to be used to plot annotations and current window
    '''
    sigRemoveRequested = QtCore.pyqtSignal(object)
    def __init__(self, values=(0, 1), orientation='vertical', brush=None, pen=None,
                 hoverBrush=None, hoverPen=None, movable=True, bounds=None,
                 span=(0, 1), swapMode='sort',label = '', id = None, removable=True):

        pg.LinearRegionItem.__init__(self, values=values, orientation=orientation, brush=brush, pen=pen,
                                     hoverBrush=hoverBrush, hoverPen=hoverPen, movable=movable, bounds=bounds,
                                     span=span, swapMode=swapMode)

        self.lines[0].setZValue(101) # ML: hack to have lines above areas
        self.lines[1].setZValue(101)
        self.label = label # Label of the annotation
        self.id = id # field to identify corresponding annotation in the annotations object
        label_text = pg.TextItem(label, anchor=(0, -1), color= pen.color())
        label_text.setParentItem(self.lines[0])
        self.removable = removable
        self.menu = None
        self.setAcceptedMouseButtons(self.acceptedMouseButtons() | QtCore.Qt.RightButton)
        self.setZValue(0.1)

    def checkRemoveHandle(self, handle):
        ## This is used when displaying a Handle's context menu to determine
        ## whether removing is allowed.
        ## Subclasses may wish to override this to disable the menu entry.
        ## Note: by default, handles are not user-removable even if this method returns True.
        return self.removable

    def contextMenuEnabled(self):
        return True

    def raiseContextMenu(self, ev):
        if not self.contextMenuEnabled():
            return
        menu = self.getMenu()
        menu = self.scene().addParentContextMenus(self, menu, ev)
        pos = ev.screenPos()
        menu.popup(QtCore.QPoint(pos.x(), pos.y()))

    def getMenu(self):
        if self.menu is None:
            self.menu = QtGui.QMenu()
            self.menu.setTitle("Annotations")
            remAct = QtGui.QAction("Remove annotation", self.menu)
            remAct.triggered.connect(self.removeClicked)
            self.menu.addAction(remAct)
            self.menu.remAct = remAct
        return self.menu

    def removeClicked(self):
        ## Send remove event only after we have exited the menu event handler
        QtCore.QTimer.singleShot(0, lambda: self.sigRemoveRequested.emit(self))

    # Redefine move methods to only allow lines to move horizontally (hence keeping label vertically anchored)
    def lineMoved(self, i):
        if self.blockLineSignal:
            return

        # lines swapped
        if self.lines[0].value() > self.lines[1].value():
            if self.swapMode == 'block':
                self.lines[i].setValue(self.lines[1 - i].value())
            elif self.swapMode == 'push':
                self.lines[1 - i].setValue(self.lines[i].value())

        for i, l in enumerate(self.lines):
            pos = l.pos()
            pos.setY(0)
            l.setPos(pos)

        self.prepareGeometryChange()
        self.sigRegionChanged.emit(self)

    def mouseDragEvent(self, ev):
        if not self.movable or int(ev.button() & QtCore.Qt.LeftButton) == 0:
            return
        ev.accept()

        if ev.isStart():
            bdp = ev.buttonDownPos()
            self.cursorOffsets = [l.pos() - bdp for l in self.lines]
            self.startPositions = [l.pos() for l in self.lines]
            self.moving = True

        if not self.moving:
            return

        self.lines[0].blockSignals(True)  # only want to update once
        for i, l in enumerate(self.lines):
            pos = self.cursorOffsets[i] + ev.pos()
            pos.setY(0)
            l.setPos(pos)
        self.lines[0].blockSignals(False)
        self.prepareGeometryChange()

        if ev.isFinish():
            self.moving = False
            self.sigRegionChangeFinished.emit(self)
        else:
            self.sigRegionChanged.emit(self)

    def mouseClickEvent(self, ev):
        if self.moving and ev.button() == QtCore.Qt.RightButton:
            ev.accept()
            for i, l in enumerate(self.lines):
                l.setPos(self.startPositions[i])
            self.moving = False
            self.sigRegionChanged.emit(self)
            self.sigRegionChangeFinished.emit(self)
        elif ev.button() == QtCore.Qt.RightButton and self.contextMenuEnabled():
            self.raiseContextMenu(ev)
            ev.accept()
        else:
            ev.ignore()

class PyecogCursorItem(pg.InfiniteLine):
    def __init__(self, pos=None, angle=90, pen=None, movable=True, bounds=None,
                 hoverPen=None, label=None, labelOpts=None, span=(0, 1), markers=None,
                 name=None):
        if pen is None:
            pen = pg.functions.mkPen(color=(192, 32, 32,192), width=3)
        if hoverPen is None:
            hoverPen = pg.functions.mkPen(color=(192, 32, 32, 255), width=3)

        pg.InfiniteLine.__init__(self, pos=pos, angle=angle, pen=pen, movable=movable, bounds=bounds,
                 hoverPen=hoverPen, label=label, labelOpts=labelOpts, span=span, markers=markers,
                 name=name)

        self.setZValue(102)  # Hack to make it above all else



