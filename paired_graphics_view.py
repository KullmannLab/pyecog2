import sys
import os
import numpy as np

from PyQt5 import QtGui, QtCore, QtWidgets, uic, Qt
from PyQt5.QtGui import QPainter, QBrush, QPen

# import pyqtgraph as pg
# from .utils import Point, rect_to_range
# from .graphics_view import PyecogGraphicsView
# temp
from datetime import datetime
import pyqtgraph_copy.pyqtgraph as pg
import colorsys

from pyecog_plot_item import PyecogPlotCurveItem, PyecogLinearRegionItem, PyecogCursorItem
from annotations_module import Annotations

pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')


# from .lines import InfiniteOrthogonalLine

# lets get linear region working?y

class PairedGraphicsView():
    '''
    This is pyqgraph implementation of plotting windows.
    This should be focused on working, not particularly elegant.
    '''

    def build_splitter(self):
        # Todo might need to paqss a size in here
        self.splitter = QtWidgets.QSplitter(parent=None)
        self.splitter.resize(680, 400)  # Todo currently not sure about this
        self.splitter.setOrientation(QtCore.Qt.Vertical)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                           QtWidgets.QSizePolicy.Expanding)
        self.splitter.setSizePolicy(sizePolicy)

    def __init__(self, parent=None):
        # todo clean this method up!
        self.parent = parent
        self.build_splitter()
        self.scale = None  # transform on the childitems of plot

        overview_layout_widget = pg.GraphicsLayoutWidget()
        self.overview_plot = overview_layout_widget.addPlot()
        # self.overview_plot.showAxis('left', show=False)
        self.overview_plot.setLabel('bottom', text='Time', units='s')

        # this doesnt work (getting the scroll)
        # overview_layout_widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        insetview_layout_widget = pg.GraphicsLayoutWidget()
        self.insetview_plot = insetview_layout_widget.addPlot()
        # self.insetview_plot.showAxis('left', show=False)
        self.insetview_plot.showGrid(x=True, y=True, alpha=0.1)
        self.insetview_plot.setLabel('bottom', text='Time', units='s')

        # self.insetview_plot.setXRange(0,60) #hacky
        # self.overview_plot.vb.setXRange(0,3600) #hacky
        self.insetview_plot.vb.state['autoRange'] = [False, False]
        self.overview_plot.vb.state['autoRange'] = [False, False]

        self.splitter.addWidget(overview_layout_widget)
        self.splitter.addWidget(insetview_layout_widget)
        self.splitter.setStretchFactor(1, 6)  # make inset view 6 times larger

        self.insetview_plot.sigRangeChanged.connect(self.insetview_range_changed)
        self.overview_plot.vb.sigMouseLeftClick.connect(self.overview_clicked)
        # hacky use of self.vb, but just rolling with it

        x_range, y_range = self.insetview_plot.viewRange()
        pen = pg.mkPen(color=(250, 250, 80), width=2)
        penh = pg.mkPen(color=(100, 100, 250), width=2)

        self.overviewROI = pg.RectROI(pos=(x_range[0], y_range[0]),
                                      size=(x_range[1] - x_range[0], y_range[1] - y_range[0]),
                                      sideScalers=True, pen=penh, rotatable=False, removable=False)
        self.overviewROI.sigRegionChanged.connect(self.overviewROIchanged)
        self.overview_plot.addItem(self.overviewROI)

        # here we will store the plot items in nested dict form
        # {"1" : {'inset': obj,'overview':obj }
        # will be used for an ugly hack to snchonize across plots
        self.channel_plotitem_dict = {}
        self.main_model = parent.main_model


    def set_scenes_plot_channel_data(self, arr, fs, pens=None):
        '''
        # Not entirely clear the differences between this and
        set_plotitem_data is snesnible

        arr - ndarray of shape (n datapoints, channels)
        fs  - sampling frequency
        pens - a list of len channels containing pens
        '''
        # we need to handle if channel not seen before
        # 6 std devations
        print('Items to delete')
        print(self.overview_plot.items)
        self.overview_plot.clear()
        self.overview_plot.addItem(self.overviewROI) # put back the overview box
        print('Items after delete')
        print(self.overview_plot.items)
        self.insetview_plot.clear()


        if self.scale is None:  # running for the first time
            self.scale = 1 / (6 * np.mean(np.std(arr, axis=0, keepdims=True), axis=1))
            self.insetview_plot.vb.setYRange(-2, arr.shape[1] + 1)
            self.overview_plot.vb.setYRange(-2, arr.shape[1] + 1)
            self.insetview_plot.vb.setXRange(0, min(30, arr.shape[0] / fs))

        for i in range(arr.shape[1]):
            if pens is None:
                pen = pg.mkPen('k')
            else:
                pen = pen[i]
            y = arr[:, i]
            self.set_plotitem_channel_data(y, fs, pen, i, self.scale)
        # self.clear_unused_channels() # to implement, not sure the best way
        # self.test_children()

        # prevent scrolling past 0 and end of data
        self.insetview_plot.vb.setLimits(xMin=0, xMax=arr.shape[0] / fs)
        self.overview_plot.vb.setLimits(xMin=0, xMax=arr.shape[0] / fs)
        self.overview_plot.vb.setLimits(yMin=-3, yMax=arr.shape[1] + 3)

        self.set_scenes_plot_annotations_data(self.main_model.annotations)
        # FOR DEBUGGING ONLY:
        self.set_scene_window([30, 32])
        self.set_scene_cursor()

    def set_plotitem_channel_data(self, y, fs, pen, index, init_scale):
        '''
        If the index exists within the plotitem dict we just set the data, else create
        or delete from the dict. (#todo)

        init_scale is the initial scaling of the channels. Set transform
        '''
        # todo stop passing the vb to construction have it added automatically when add the item to plot
        if True: # index not in self.channel_plotitem_dict.keys(): # This was used before we were clearing the scenes upon file loading
            self.channel_plotitem_dict[index] = {}
            self.channel_plotitem_dict[index]['overview'] = PyecogPlotCurveItem(y, fs,
                                                                                viewbox=self.overview_plot.vb)
            self.channel_plotitem_dict[index]['insetview'] = PyecogPlotCurveItem(y, fs,
                                                                                 viewbox=self.insetview_plot.vb)
            self.channel_plotitem_dict[index]['overview'].setY(index)
            self.channel_plotitem_dict[index]['insetview'].setY(index)
            m = QtGui.QTransform().scale(1, init_scale)
            self.channel_plotitem_dict[index]['overview'].setTransform(m)
            self.channel_plotitem_dict[index]['insetview'].setTransform(m)
            self.overview_plot.addItem(self.channel_plotitem_dict[index]['overview'])
            self.insetview_plot.addItem(self.channel_plotitem_dict[index]['insetview'])

        self.channel_plotitem_dict[index]['overview'].set_data(y, fs)
        self.channel_plotitem_dict[index]['insetview'].set_data(y, fs)
        self.overview_plot.vb.setXRange(0, y.shape[0] / fs, padding=0)

    def set_scenes_plot_annotations_data(self, annotations):
        '''
        :param annotations: an annotations object
        :return: None
        '''
        n = max(len(annotations.labels), 6)  # variable to give n different colors to different types of labels

        # Auxiliary functions that return functions with fixed parameters that can be used to connect to signals
        def function_generator_link_annotaions(annotation_object, annotation_graph):
            return lambda: annotation_object.setPos(annotation_graph.getRegion())

        def function_generator_link_annotaions_to_graphs(annotation_object, annotation_graph):
            return lambda: annotation_object.setPos(annotation_graph.getRegion())

        def function_generator_link_graphs(annotation_graph_a, annotation_graph_b):
            return lambda: annotation_graph_b.setRegion(annotation_graph_a.getRegion())

        for bi, label in enumerate(annotations.labels):
            color = tuple(np.array(
                colorsys.hls_to_rgb(bi / n, .5, .9)) * 255)  # circle hue with constant luminosity an saturation
            brush = pg.functions.mkBrush(color=(*color, 25))
            pen = pg.functions.mkPen(color=(*color, 200))
            for i, annotation in enumerate(annotations.get_all_with_label(label)):
                annotation_graph_o = PyecogLinearRegionItem((annotation.getStart(),annotation.getEnd()), pen=pen,
                                                            brush=brush, movable=False, id=(label, i))
                annotation_graph_o.setZValue(-1)
                annotation_graph_i = PyecogLinearRegionItem((annotation.getStart(),annotation.getEnd()), pen=pen,
                                                            brush=brush, swapMode='push', label=label, id=(label, i))
                annotation_graph_i.setZValue(-1)
                annotation_graph_i.sigRegionChangeFinished.connect(function_generator_link_annotaions(annotation, annotation_graph_i))
                annotation_graph_i.sigRegionChangeFinished.connect(function_generator_link_graphs(annotation_graph_i, annotation_graph_o))
                self.overview_plot.addItem(annotation_graph_o)
                self.insetview_plot.addItem(annotation_graph_i)
                # annotation.sigAnnotationElementDeleted.connect() # todo
                # annotation.sigAnnotationElementChanged.connect()

    def set_scene_cursor(self):
        cursor_o = PyecogCursorItem(pos=0)
        cursor_i = PyecogCursorItem(pos=0)
        # Should these connections be made in the main window code?
        cursor_i.sigPositionChanged.connect(lambda: self.main_model.set_time_position_from_graphs(cursor_i.getXPos()))
        cursor_i.sigPositionChanged.connect(lambda: cursor_o.setPos(cursor_i.getPos()))
        cursor_o.sigPositionChanged.connect(lambda: cursor_i.setPos(cursor_o.getPos()))
        self.main_model.sigTimeChangedGraph.connect(lambda: cursor_i.setPos(self.main_model.time_position))
        self.main_model.sigTimeChangedGraph.connect(lambda: cursor_o.setPos(self.main_model.time_position))
        self.overview_plot.addItem(cursor_o)
        self.insetview_plot.addItem(cursor_i)


    def set_scene_window(self, window):
        brush = pg.functions.mkBrush(color=(0, 0, 0, 10))
        window_item_o = pg.LinearRegionItem(window, brush=brush,movable=False)
        self.overview_plot.addItem(window_item_o)
        window_item_i = pg.LinearRegionItem(window, brush=brush)
        window_item_i.setZValue(-0.1) # Bellow traces, but above annotations
        self.insetview_plot.addItem(window_item_i)
        window_item_i.sigRegionChangeFinished.connect(lambda: window_item_o.setRegion(window_item_i.getRegion()))
        window_item_i.sigRegionChangeFinished.connect(lambda: self.main_model.set_window_pos(window_item_i.getRegion()))
        self.main_model.sigWindowChanged.connect(window_item_i.setRegion)

    def graphics_object_xchanged(self):
        print('xChanged grahics object')

    def overviewROIchanged(self):
        state = self.overviewROI.getState()
        self.insetview_plot.setRange(xRange=(state['pos'][0], state['pos'][0] + state['size'][0]),
                                     yRange=(state['pos'][1], state['pos'][1] + state['size'][1]),
                                     padding=0)

    def overview_clicked(self, ev_pos):
        '''
        ev pos is postion in 'scene' coords of mouse click
        '''
        # print('hit', ev_pos)
        # print(event, event.pos())
        center = ev_pos
        xmin, xmax = self.insetview_plot.viewRange()[0]
        ymin, ymax = self.insetview_plot.viewRange()[1]
        # print(ymin, ymax, center.y())
        x_range = xmax - xmin
        y_range = ymax - ymin
        new_xrange = (center.x() - x_range / 2, center.x() + x_range / 2)
        # new_xrange = new_xrange - new_xrange

        new_yrange = (center.y() - y_range / 2, center.y() + y_range / 2)

        print(new_xrange)
        self.insetview_plot.setRange(xRange=new_xrange,
                                     yRange=new_yrange,
                                     padding=0)

    def insetview_range_changed(self, mask):
        '''connected to signal from insetview_plot'''
        x_range, y_range = self.insetview_plot.viewRange()
        self.overviewROI.setPos((x_range[0], y_range[0]))
        self.overviewROI.setSize((x_range[1] - x_range[0], y_range[1] - y_range[0]))
