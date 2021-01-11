from PyQt5 import QtGui, QtWidgets, QtCore
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QRect, QTimer
from scipy import signal, stats
# import pyqtgraph_copy.pyqtgraph as pg
import pyqtgraph as pg
import numpy as np


class PyecogPlotCurveItem(pg.PlotCurveItem):
    ''' Hmm seems like you need the graphics scene subcalss of pyqtgraph
    for how they get all trhe drags
    also there is the  vewbox presumeableig that handles stuff - view? plotitme.?#

    also maybe the downsampling in plotitem?
    '''

    def __init__(self, project, channel, viewbox, *args, **kwds):
        '''
        Todo: I really dont like passining in the viewbox
        This should be assigned instead when they get added to the plot
        '''
        self.accept_mousewheel_transformations = True
        # self.yscale_data = 1
        self.project = project
        self.channel = channel
        self.parent_viewbox = viewbox
        self.pen = (0, 0, 0, 100)
        self.n_display_points = viewbox.width  # 5000  # this should be horizontal resolution of window
        super().__init__(*args, **kwds)
        self.resetTransform()
        self.setZValue(1)
        self.previous_args = None

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
        if self.previous_args is None:
            self.previous_args = new_args
        else:
            if new_args == self.previous_args:
                # print('setData_with_envlope: arguments did not change since last call')
                return
        # print('displaying n points', n)
        if self.parent_viewbox.viewRange()[1][0]-2 < self.channel < self.parent_viewbox.viewRange()[1][1]+2:
            visible_data, visible_time = self.project.get_data_from_range(self.parent_viewbox.viewRange()[0], self.channel,
                                                                          n_envelope=n)
        else:
            visible_data = np.zeros(1)
            visible_time = np.zeros(1)
        # print('visible data shape:',visible_data.shape)
        self.setData(y=visible_data.ravel(), x=visible_time.ravel(), pen=self.pen, antialias=True)  # update the plot
        self.previous_args = new_args
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
    sigClicked = QtCore.pyqtSignal(object)

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



