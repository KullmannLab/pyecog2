import sys
import os
import numpy as np

from PyQt5 import QtGui, QtCore, QtWidgets, uic, Qt
from PyQt5.QtGui import QPainter, QBrush, QPen

#import pyqtgraph as pg
#from .utils import Point, rect_to_range
#from .graphics_view import PyecogGraphicsView
# temp
from datetime import datetime
import pyqtgraph_copy.pyqtgraph as pg

from pyecog_plot_item import PyecogPlotCurveItem

pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
#from .lines import InfiniteOrthogonalLine

# lets get linear region working?y

class PairedGraphicsView():
    '''
    This is pure pyqgraph implementation... quick and dirty...

    Added an extra signal to pg.ViewBox:
    sigMouseLeftClick = QtCore.Signal(object)

    in....
    def mouseClickEvent(self, ev):
        ... # added below
        if ev.button() == QtCore.Qt.LeftButton:
            ev.accept()
            self.sigMouseLeftClick.emit(ev)
    '''
    def build_splitter(self):
        self.splitter  = QtWidgets.QSplitter(parent=None)
        # might need a size here...
        self.splitter.resize(680, 400)
        self.splitter.setOrientation(QtCore.Qt.Vertical)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                   QtWidgets.QSizePolicy.Expanding)
        self.splitter.setSizePolicy(sizePolicy)

    def __init__(self):

        self.build_splitter()

        overview_layout_widget  = pg.GraphicsLayoutWidget()
        self.overview_plot = overview_layout_widget.addPlot()
        # this doesnt work (getting the scroll)
        #overview_layout_widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        insetview_layout_widget  = pg.GraphicsLayoutWidget()
        self.insetview_plot = insetview_layout_widget.addPlot()

        # prevent scrolling past 0
        self.insetview_plot.vb.setLimits(xMin = 0)
        self.overview_plot.vb.setLimits(xMin = 0)

        # prevent scrolling past 3600 THIS IS A TERRIBLE HARDCODE # todo
        self.insetview_plot.vb.setLimits(xMax = 3600)
        self.overview_plot.vb.setLimits(xMax = 3600)

        self.splitter.addWidget(overview_layout_widget)
        self.splitter.addWidget(insetview_layout_widget)

        self.insetview_plot.sigRangeChanged.connect(self.insetview_range_changed)
        self.overview_plot.vb.sigMouseLeftClick.connect(self.overview_clicked)
        # hacky use of self.vb, but just rolling with it

        x_range, y_range = self.insetview_plot.viewRange()
        pen = pg.mkPen(color=(200, 200, 100), width=2)

        self.overviewlines_dict = {
            'x_min':pg.InfiniteLine(x_range[0], angle=90, pen=pen, hoverPen=pen),
            'x_max':pg.InfiniteLine(x_range[1]*100, angle=90,pen=pen, hoverPen=pen),

            'y_min':pg.InfiniteLine(y_range[0], angle=0,pen=pen, hoverPen=pen),
            'y_max':pg.InfiniteLine(y_range[1], angle=0,pen=pen, hoverPen=pen)
        }
        for k in self.overviewlines_dict.keys():
            self.overviewlines_dict[k].setZValue(100) # high z values drawn on top
            self.overview_plot.addItem(self.overviewlines_dict[k])

    def update_scenes(self, arr, fs):
        print("ive been sent data to plot....")
        print(arr.shape, fs)

    def make_and_add_item(self, x, y, pen):
        '''
        takes x y data and pen and adds ti the two plots
        '''
        # you might need to send in the data here?
        # add a copy to b
        # will be able to create a correspondance between the objects added to both?
        # hopefully
        plot_curve_item = PyecogPlotCurveItem(x=x,y=y, pen=pen)
        #plot_curve_item.setFlags(QtWidgets.QGraphicsItem.ItemIsMovable);
        self.overview_plot.addItem(plot_curve_item)
        plot_curve_item = PyecogPlotCurveItem(x=x,y=y, pen=pen)
        #plot_curve_item.setClickable(True, width=-1)
        #plot_curve_item.setFlags(QtWidgets.QGraphicsItem.ItemIsMovable);
        #plot_curve_item.setFlags(QtWidgets.QGraphicsItem.ItemIsSelectable);
        self.insetview_plot.addItem(plot_curve_item)
        self.insetview_plot.setXRange(20,40) #hacky

        # ultimately these guys should inherit from qgraphicsobject
        # therefore xChanged signal should be being emiilted
        plot_curve_item.xChanged.connect(self.graphics_object_xchanged)

    def graphics_object_xchanged(self):
        print('xChanged grahics object')


    def overview_clicked(self, ev_pos):
        '''
        ev pos is postion in 'scene' coords of mouse click
        '''
        #print('hit', ev_pos)
        #print(event, event.pos())
        center = ev_pos
        xmin, xmax = self.insetview_plot.viewRange()[0]
        ymin, ymax = self.insetview_plot.viewRange()[1]
        #print(ymin, ymax, center.y())
        x_range = xmax-xmin
        y_range = ymax-ymin
        new_xrange = (center.x()-x_range/2, center.x()+x_range/2)
        new_yrange = (center.y()-y_range/2, center.y()+y_range/2)
        #print(new_yrange)
        self.insetview_plot.setRange(xRange = new_xrange,
                                     yRange = new_yrange,
                                     padding=0)



    def insetview_range_changed(self, mask):
        '''connected to signal from insetview_plot'''
        x_range, y_range = self.insetview_plot.viewRange()
        self.overviewlines_dict['x_min'].setPos(x_range[0])
        self.overviewlines_dict['x_max'].setPos(x_range[1])
        self.overviewlines_dict['y_min'].setPos(y_range[0])
        self.overviewlines_dict['y_max'].setPos(y_range[1])









