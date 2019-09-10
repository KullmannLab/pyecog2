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
    This is pyqgraph implementation of plotting windows.
    This should be focused on working, not particularly elegant.
    '''
    def build_splitter(self):
        # Todo might need to paqss a size in here
        self.splitter  = QtWidgets.QSplitter(parent=None)
        self.splitter.resize(680, 400) # Todo currently not sure about this
        self.splitter.setOrientation(QtCore.Qt.Vertical)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                           QtWidgets.QSizePolicy.Expanding)
        self.splitter.setSizePolicy(sizePolicy)

    def __init__(self):
        # todo clean this method up!
        self.build_splitter()

        overview_layout_widget  = pg.GraphicsLayoutWidget()
        self.overview_plot = overview_layout_widget.addPlot()
        #self.overview_plot.showAxis('left', show=False)
        self.overview_plot.setLabel('bottom', text='Time', units='')

        # this doesnt work (getting the scroll)
        #overview_layout_widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        insetview_layout_widget  = pg.GraphicsLayoutWidget()
        self.insetview_plot = insetview_layout_widget.addPlot()
        #self.insetview_plot.showAxis('left', show=False)
        self.insetview_plot.showGrid(x=True,y=True, alpha=0.1)
        self.insetview_plot.setLabel('bottom', text='Time',
                                     units='s')
        self.insetview_plot.setXRange(20,40) #hacky
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

        # todo make better fix this shit!
        self.overviewlines_dict = {
            'x_min':pg.InfiniteLine(x_range[0],     angle=90, pen=pen, hoverPen=pen),
            'x_max':pg.InfiniteLine(x_range[1]*100, angle=90,pen=pen, hoverPen=pen),

            'y_min':pg.InfiniteLine(y_range[0], angle=0,pen=pen, hoverPen=pen),
            'y_max':pg.InfiniteLine(y_range[1], angle=0,pen=pen, hoverPen=pen)
        }
        for k in self.overviewlines_dict.keys():
            self.overviewlines_dict[k].setZValue(100) # high z values drawn on top
            self.overview_plot.addItem(self.overviewlines_dict[k])

        # here we will store the plot items in nested dict form
        # {"1" : {'inset': obj,'overview':obj }
        # will be used for an ugly hack to snchonize across plots
        self.channel_plotitem_dict = {}

    def set_scenes_plot_data(self, arr, fs, pens=None):
        '''
        # Not entirely clear the differences between this and
        set_plotitem_data is snesnible

        arr - ndarray of shape (n datapoints, channels)
        fs  - sampling frequency
        pens - a list of len channels containing pens
        '''
        # we need to calculate scales here if channel dict is none
        scale = 1
        self.overview_plot.vb.yscale_data = 0.001
        self.insetview_plot.vb.yscale_data = 0.001
        x = np.linspace(0,arr.shape[0]/fs, arr.shape[0])
        for i in range(arr.shape[1]):
            if pens is None:
                pen = pg.mkPen('k')
            else:
                pen = pen[i]
            y = arr[:, i]
            self.set_plotitem_data(x, y, fs, pen, i, scale)
        #self.clear_unused_channels() # to implement, not sure the best way

        self.test_children()

    def test_children(self):
        print('Enter here debugging code!')
        vbo = self.overview_plot.vb
        vbi = self.insetview_plot.vb
        print(vbo.childGroup.boundingRect())
        child_group = vbo.childGroup
        print(child_group.childItems())
        print(vbo.childrenBounds())

    def set_plotitem_data(self, x, y, fs, pen, index, init_scale):
        '''
        If the

        If the index exists within the plotitem dict we just set the data, else create
        or delete from the dict. (#todo)

        init_scale is the initial scaling of the channels

        '''
        # todo stop using the vb have it added automatically when add the item to plot
        if index not in self.channel_plotitem_dict.keys():
            self.channel_plotitem_dict[index] = {}
            self.channel_plotitem_dict[index]['overview'] = PyecogPlotCurveItem(x, y, fs,viewbox=self.overview_plot.vb)
            self.channel_plotitem_dict[index]['insetview'] = PyecogPlotCurveItem(x, y, fs,viewbox=self.insetview_plot.vb)
            self.channel_plotitem_dict[index]['overview'].setY(index)
            self.channel_plotitem_dict[index]['insetview'].setY(index)
            #self.channel_plotitem_dict[index]['overview'].setScale(0.1)
            #self.channel_plotitem_dict[index]['transform'] = self.channel_plotitem_dict[index]['insetview'].transform()
            mat = self.channel_plotitem_dict[index]['overview'].transform()

            #print(self.channel_plotitem_dict[index]['overview'].ItemIgnoresTransformations)
            #print(QtWidgets.QGraphicsItem.ItemIgnoresTransformations)
            #print()
            #print(mat.m22())
            m = QtGui.QTransform()
            m.scale(1, 0.01)
            mat = mat.scale(1,0.01)
            #print(mat.m22())
            #self.channel_plotitem_dict[index]['overview'].setTransform(m)
            #mat = self.channel_plotitem_dict[index]['overview'].transform()
            #print(mat.m22())
            #self.channel_plotitem_dict[index]['overview'].setTransform(mat)
            #print(self.channel_plotitem_dict[index]['transform'])
            #self.channel_plotitem_dict[index]['overview'].setTransform(self.channel_plotitem_dict[index]['transform'].scale(1,0.001))

            #self.channel_plotitem_dict[index]['overview'].setScale(1, 0.1)
            #self.channel_plotitem_dict[index]['insetview'].setScale(1,init_scale)
            self.overview_plot.addItem(self.channel_plotitem_dict[index]['overview'])
            self.insetview_plot.addItem(self.channel_plotitem_dict[index]['insetview'])
            trans = self.channel_plotitem_dict[index]['overview'].viewTransform()
            #print(trans, trans.m22(), trans.m23())
            #print(self.channel_plotitem_dict[index]['overview'].parentItem())
            child_group = self.overview_plot.vb.childGroup
            #print(child_group.childItems())
            #print(child_group.transform().m11())

        self.channel_plotitem_dict[index]['overview'].set_data(x,y,fs)
        self.channel_plotitem_dict[index]['insetview'].set_data(x,y,fs)


        #plot_curve_item.setClickable(True, width=-1)
        #plot_curve_item.setFlags(QtWidgets.QGraphicsItem.ItemIsMovable);
        #plot_curve_item.setFlags(QtWidgets.QGraphicsItem.ItemIsSelectable);
        #self.insetview_plot.addItem(plot_curve_item)


        # ultimately these guys should inherit from qgraphicsobject
        # therefore xChanged signal should be being emiilted
        #plot_curve_item.xChanged.connect(self.graphics_object_xchanged)

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









