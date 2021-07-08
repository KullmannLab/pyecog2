from PySide2 import QtGui, QtWidgets, QtCore
from PySide2.QtCore import QThread, Signal, Qt, QRect, QTimer
from scipy import signal, stats
# import pyqtgraph_copy.pyqtgraph as pg
import pyqtgraph as pg
import numpy as np
from scipy import signal
from pyecog2.ProjectClass import intervals_overlap

class PyecogPlotCurveItem(pg.PlotCurveItem):
    ''' Hmm seems like you need the graphics scene subcalss of pyqtgraph
    for how they get all trhe drags
    also there is the  vewbox presumeableig that handles stuff - view? plotitme.?#

    also maybe the downsampling in plotitem?
    '''

    def __init__(self, project, channel, viewbox, pen=None, *args, **kwds):
        '''
        Todo: I really dont like passining in the viewbox
        This should be assigned instead when they get added to the plot
        '''
        self.accept_mousewheel_transformations = True
        # self.yscale_data = 1
        self.project = project
        self.channel = channel
        self.parent_viewbox = viewbox
        if pen is None:
            self.pen = pg.mkPen(pg.getConfigOption('foreground')) #(1, 1, 1, 100)
            color = self.pen.color()
            rgb = color.getRgb()
            color.setRgb(int(rgb[0]*255/100),int(rgb[1]*255/100),int(rgb[2]*255/100),100)
            self.pen.setColor(color)
        else:
            self.pen = pen

        self.n_display_points = viewbox.width  # 5000  # this should be horizontal resolution of window
        super().__init__(*args, **kwds)
        self.resetTransform()
        self.setZValue(1)
        self.previous_args = [[[0,0],[0,0]],-1,0]

    def viewRangeChanged(self):
        # Re-compute data envlope and plot:
        self.setData_with_envelope()

    def set_pen(self, pen):
        self.pen = pen

    def set_data(self, project, channel,):
        self.project = project
        self.channel = channel
        self.setData_with_envelope()

    def setData_with_envelope(self):
        n = self.n_display_points()*2
        #check if arguments have changed since last call:
        # new_args = [self.parent_viewbox.viewRange()[0], self.channel, n]
        new_args = [self.parent_viewbox.viewRange(), self.channel, n]
        if new_args == self.previous_args:
            # print('setData_with_envlope: arguments did not change since last call')
            return
        # print('displaying n points', n)
        # print('new n, previous n:',new_args[-1], self.previous_args[-1])
        if self.parent_viewbox.viewRange()[1][0]-2 < self.channel < self.parent_viewbox.viewRange()[1][1]+2: # Avoid plotting channels out of view
            newXRange = new_args[0][0]
            previousXRange = self.previous_args[0][0]
            if newXRange[1]-newXRange[0] != previousXRange[1]-previousXRange[0] or \
                    new_args[-1] != self.previous_args[-1] or \
                    not intervals_overlap(newXRange,previousXRange) or \
                    True: # THIS CODE IS NOT WORKING YET, SO SKIPPING progresive grabs
                # Grab completely new set of data if zoom changed or n_envelope changed or Xranges do not overlap
                self.visible_data, self.visible_time = self.project.get_data_from_range(newXRange, self.channel,
                                                                                        n_envelope=n, for_plot = True)
            else: # NEVER REACHED - THIS CODE IS NOT WORKING YET, SO SKIPPING progresive grabs
                # Grab only the data that changed
                # ds = (newXRange[1]-newXRange[0])/n
                previousXRange = [self.visible_time[0], self.visible_time[-1]]
                ds = self.visible_time[1]-self.visible_time[0]
                if ds==0:
                    self.visible_time[2] - self.visible_time[0]

                if newXRange[1]>previousXRange[1]:
                    n_new_points = int(((newXRange[1]-self.visible_time[-1])*n)/(newXRange[1]-newXRange[0]))
                    print('npoints', n_new_points)
                    if n_new_points>0:
                        # grab data to append
                        visible_data, visible_time = self.project.get_data_from_range([previousXRange[1]+ds, newXRange[1]+ds],
                                                                                      self.channel, n_envelope=n_new_points, for_plot=True)
                        try:
                            print(self.visible_data.shape,visible_data.shape)
                            print('visible times',self.visible_time[-1],visible_time[0])
                            print('delta visible times',visible_time[0]-self.visible_time[-1],ds)
                        except:
                            pass
                        if len(visible_data):
                            self.visible_data = np.concatenate((self.visible_data[len(visible_data):],visible_data))
                            self.visible_time = np.concatenate((self.visible_time[len(visible_time):],visible_time))
                else:
                    # grab data to prepend
                    n_new_points = int(((self.visible_time[0]-newXRange[0])*n)/(newXRange[1]-newXRange[0]))
                    print('npoints', n_new_points)
                    if n_new_points>0:
                        visible_data, visible_time = self.project.get_data_from_range([newXRange[0], previousXRange[0]-ds],
                                                                                      self.channel, n_envelope=n_new_points, for_plot=True)
                        try:
                            print(self.visible_data.shape,visible_data.shape)
                            print('visible times',self.visible_time[0],visible_time[-1])
                            print('delta visible times',visible_time[-1]-self.visible_time[0],ds)
                        except:
                            pass
                        if len(visible_data):
                            self.visible_data = np.concatenate((visible_data,self.visible_data[:-len(visible_data)]))
                            self.visible_time = np.concatenate((visible_time,self.visible_time[:-len(visible_time)]))

            if self.project.filter_settings[0]: # apply LP filter only for plots
                fs = 2/(self.visible_time[2]-self.visible_time[0])
                nyq = 0.5 * fs[0]
                hpcutoff = min(max(self.project.filter_settings[1] / nyq, 0.001), .5)
                visible_data = self.visible_data - np.mean(self.visible_data)
                lpcutoff = min(max(self.project.filter_settings[2] / nyq, 0.001), 1)
                # for some reason the bandpass butterworth filter is very unstable
                if lpcutoff<.99:  # don't apply filter if LP cutoff freqquency is above nyquist freq.
                    # if self.verbose: print('applying LP filter to display data:', filter_settings, fs, nyq, lpcutoff)
                    b, a = signal.butter(2, lpcutoff, 'lowpass', analog=False)
                    visible_data = signal.filtfilt(b, a, visible_data,axis =0,method='gust')
                if hpcutoff > .001: # don't apply filter if HP cutoff frequency too low.
                    # if self.verbose: print('applying HP filter to display data:', filter_settings, fs, nyq, hpcutoff)
                    b, a = signal.butter(2, hpcutoff, 'highpass', analog=False)
                    visible_data = signal.filtfilt(b, a, visible_data,axis =0,method='gust')
            else:
                visible_data = self.visible_data
        else: # channel not visible
            self.visible_data = np.zeros(2)
            visible_data = self.visible_data
            self.visible_time = np.zeros(2)
            new_args[-1] = 0 # force reset on next plot

        # print('visible data shape:',visible_data.shape)
        self.setData(y=visible_data.ravel(), x=self.visible_time.ravel(), pen=self.pen)  # update the plot
        # self.resetTransform()
        self.previous_args = new_args

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
    sigRemoveRequested = QtCore.Signal(object)
    sigClicked = QtCore.Signal(object)

    def __init__(self, values=(0, 1), orientation='vertical', brush=None, pen=None,
                 hoverBrush=None, hoverPen=None, movable=True, bounds=None,
                 span=(0, 1), swapMode='sort',label = '', id = None, removable=True, channel_range = None,movable_lines = False):

        # pg.LinearRegionItem.__init__(self, values=values, orientation=orientation, brush=brush, pen=pen,
        #                              hoverBrush=hoverBrush, hoverPen=hoverPen, movable=movable, bounds=bounds,
        #                              span=span, swapMode=swapMode)

        # Copied from pg.LinearRegionItem to avoid creation of infinite lines, and made to be only vertical
        pg.GraphicsObject.__init__(self)
        self.orientation = orientation
        self.bounds = QtCore.QRectF()
        self.blockLineSignal = False
        self.moving = False
        self.mouseHovering = False
        self.span = span
        self.swapMode = swapMode
        self._bounds = None

        lineKwds = dict(
            movable=movable or movable_lines,
            bounds=bounds,
            span=span,
            pen=pen,
            hoverPen=hoverPen,
        )
        if channel_range is not None:
            self.channel_range = [min(channel_range) - .5, max(channel_range) + .5]
        else:
            self.channel_range = None

        self.lines = []
        self.setMovable(movable) # pg setMovable overides line movable arguments, so doing it before lines
        self.lines = [
            PyecogInfiniteLine(QtCore.QPointF(values[0], 0), angle=90, yrange=self.channel_range, **lineKwds),
            PyecogInfiniteLine(QtCore.QPointF(values[1], 0), angle=90, yrange=self.channel_range, **lineKwds)]

        for l in self.lines:
            l.setParentItem(self)
            l.sigPositionChangeFinished.connect(self.lineMoveFinished)
            l.setZValue(101)
        self.lines[0].sigPositionChanged.connect(lambda: self.lineMoved(0))
        self.lines[1].sigPositionChanged.connect(lambda: self.lineMoved(1))

        if brush is None:
            brush = QtGui.QBrush(QtGui.QColor(0, 0, 255, 50))
        self.setBrush(brush)

        if hoverBrush is None:
            c = self.brush.color()
            c.setAlpha(min(c.alpha() * 2, 255))
            hoverBrush = pg.functions.mkBrush(c)
        self.setHoverBrush(hoverBrush)
        # self.label = label  # Label of the annotation
        self.id = id  # field to identify corresponding annotation in the annotations object
        self.label_text = pg.TextItem(label, anchor=(0, 0), color=pen.color())
        self.label_text.setParentItem(self.lines[0])
        self.label_text.updateTextPos()
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
        modifiers = ev.modifiers()
        if modifiers == QtCore.Qt.ShiftModifier:
            ev.ignore()
            return
        self.sigClicked.emit(ev)
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

    # Only plot over relevant channels
    def boundingRect(self):
        br = self.viewRect()  # bounds of containing ViewBox mapped to local coords.
        rng = self.getRegion()
        if self.orientation in ('vertical', PyecogLinearRegionItem.Vertical):
            br.setLeft(rng[0])
            br.setRight(rng[1])
            length = br.height()
            if self.channel_range is None:
                br.setBottom(br.top() + length * self.span[1])
                br.setTop(br.top() + length * self.span[0])
            else:
                # print('bottom original arg = ', br.top() + length * self.span[1])
                # print(self.channel_range[0]-.5)
                # print('top original arg = ', br.top() + length * self.span[0])
                # print(self.channel_range[1]+.5)
                br.setBottom(min(br.top() + length * self.span[1], self.channel_range[1])) # For some reason Top and bottom are switched in pyqtgraph code
                br.setTop(max(br.top() + length * self.span[0], self.channel_range[0]))


        else:
            br.setTop(rng[0])
            br.setBottom(rng[1])
            length = br.width()
            br.setRight(br.left() + length * self.span[1])
            br.setLeft(br.left() + length * self.span[0])

        br = br.normalized()

        if self._bounds != br:
            self._bounds = br
            self.prepareGeometryChange()

        return br

    def update_fields(self,pos,label,color_brush,color_pen):
        self.setRegion(pos)
        self.label_text.setText(label)
        self.label_text.setColor(pg.functions.mkColor(color_pen))
        self.brush.setColor(pg.functions.mkColor(color_brush))
        self.lines[0].pen.setColor(pg.functions.mkColor(color_pen))
        self.lines[1].pen.setColor(pg.functions.mkColor(color_pen))
        self.update()


class PyecogCursorItem(pg.InfiniteLine):
    def __init__(self, pos=None, angle=90, pen=None, movable=True, bounds=None,
                 hoverPen=None, label=None, labelOpts=None, span=(0, 1), markers=None,
                 name=None):
        if pen is None:
            # pen = pg.functions.mkPen(color=(192, 32, 32,192), width=3)
            pen = pg.functions.mkPen(color=(64, 192, 231, 192), width=3)
        if hoverPen is None:
            hoverPen = pg.functions.mkPen(color=(64, 192, 231, 255), width=3)

        pg.InfiniteLine.__init__(self, pos=pos, angle=angle, pen=pen, movable=movable, bounds=bounds,
                 hoverPen=hoverPen, label=label, labelOpts=labelOpts, span=span, markers=markers,
                 name=name)

        self.setZValue(102)  # Hack to make it above all else


class PyecogInfiniteLine(pg.InfiniteLine):
    def __init__(self, pos=None, angle=90, pen=None, movable=False, bounds=None,
                 hoverPen=None, label=None, labelOpts=None, span=(0, 1), markers=None,
                 name=None, yrange=None):
        pg.InfiniteLine.__init__(self, pos=pos, angle=angle, pen=pen, movable=movable, bounds=bounds,
                                 hoverPen=hoverPen, label=label, labelOpts=labelOpts, span=span, markers=markers,
                                 name=name)
        self.yrange = yrange

    def _computeBoundingRect(self):
        #br = UIGraphicsItem.boundingRect(self)
        vr = self.viewRect()  # bounds of containing ViewBox mapped to local coords.
        if vr is None:
            return QtCore.QRectF()

        ## add a 4-pixel radius around the line for mouse interaction.

        px = self.pixelLength(direction=pg.Point(1,0), ortho=True)  ## get pixel length orthogonal to the line
        if px is None:
            px = 0
        pw = max(self.pen.width() / 2, self.hoverPen.width() / 2)
        w = max(4, self._maxMarkerSize + pw) + 1
        w = w * px
        br = QtCore.QRectF(vr)
        br.setBottom(-w)
        br.setTop(w)

        length = br.width()
        left = br.left() + length * self.span[0]
        right = br.left() + length * self.span[1]
        if self.yrange is not None:
            left = max(left, self.yrange[0])
            right = min(right, self.yrange[1])
        br.setLeft(left)
        br.setRight(right)
        br = br.normalized()

        vs = self.getViewBox().size()

        if self._bounds != br or self._lastViewSize != vs:
            self._bounds = br
            self._lastViewSize = vs
            self.prepareGeometryChange()

        self._endPoints = (left, right)
        self._lastViewRect = vr

        return self._bounds