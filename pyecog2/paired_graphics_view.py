import sys
import os
import numpy as np
import time
from datetime import datetime
from PySide2 import QtGui, QtCore, QtWidgets  # , uic, Qt
from PySide2.QtGui import QPainter, QBrush, QPen

from datetime import datetime
# import pyqtgraph_copy.pyqtgraph as pg
import pyqtgraph as pg
import colorsys

from pyecog2.pyecog_plot_item import PyecogPlotCurveItem, PyecogLinearRegionItem, PyecogCursorItem
from pyqtgraph import functions as fn
from pyqtgraph.Point import Point
from timeit import default_timer as timer
from pyecog2.ProjectClass import intervals_overlap
from pyecog2.annotations_module import i_spaced_nfold


# Function to overide pyqtgraph ViewBox wheel events
def wheelEvent(self, ev, axis=None):
    if axis in (0, 1):
        mask = [False, False]
        mask[axis] = self.state['mouseEnabled'][axis]
    else:
        mask = self.state['mouseEnabled'][:]
    s = 1.02 ** (ev.delta() * self.state['wheelScaleFactor'])  # actual scaling factor
    s = [(None if m is False else s) for m in mask]
    center = Point(fn.invertQTransform(self.childGroup.transform()).map(ev.pos()))
    # JC added
    if ev.modifiers() == QtCore.Qt.ShiftModifier and s[0] is not None and s[1] is not None:
        for child in self.childGroup.childItems()[:]:
            if hasattr(child, 'accept_mousewheel_transformations'):
                m_old = child.transform()
                m = QtGui.QTransform()
                m.scale(1, m_old.m22() / s[1])
                child.setTransform(m)
        ev.accept()
        child_group_transformation = self.childGroup.transform()
        return

    if ev.modifiers() == QtCore.Qt.AltModifier and s[0] is not None and s[1] is not None:
        for child in self.childGroup.childItems()[:]:
            if hasattr(child, 'accept_mousewheel_transformations'):
                m_old = child.transform()
                m = QtGui.QTransform()
                if round(child.y()) == round(center.y()):
                    m.scale(1, m_old.m22() / s[1])
                    child.setTransform(m)
        ev.accept()
        child_group_transformation = self.childGroup.transform()
        return
    self._resetTarget()
    self.scaleBy(s, center)
    ev.accept()
    self.sigRangeChangedManually.emit(mask)


def wheelEventWrapper(s):
    def wrappedWheelEvent(ev, axis=None):
        return wheelEvent(s, ev, axis=axis)

    return wrappedWheelEvent


class PairedGraphicsView():
    '''
    This is pyqtgraph implementation of plotting windows.
    This should be focused on working, not particularly elegant.
    '''

    def build_splitter(self):
        # Todo might need to paqss a size in here
        self.splitter = QtWidgets.QSplitter(parent=None)
        # self.splitter.resize(680, 400)  # Todo currently not sure about this
        self.splitter.setOrientation(QtCore.Qt.Vertical)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                           QtWidgets.QSizePolicy.Expanding)
        self.splitter.setSizePolicy(sizePolicy)
        # self.splitter.setChildrenCollapsible(False)

    def __init__(self, parent=None):
        # todo clean this method up!
        self.parent = parent
        self.build_splitter()
        self.scale = None  # transform on the childitems of plot

        self.main_model = parent.main_model
        self.main_pen = self.main_model.color_settings['pen']
        self.main_brush = self.main_model.color_settings['brush']

        self.inset_annotations = []
        self.overview_annotations = []
        self.plotted_annotations = []

        self.animalid = None

        timeline_layout_widget = pg.GraphicsLayoutWidget()
        timeline_date_axis = pg.DateAxisItem(orientation='bottom')
        timeline_date_axis.autoSIPrefix = False
        self.timeline_plot = timeline_layout_widget.addPlot(axisItems={'bottom': timeline_date_axis})
        self.timeline_plot.showAxis('left', show=False)
        # self.timeline_plot.showAxis('bottom', show=False)
        # self.overview_plot.setLabel('bottom', text='Time', units='s')
        # self.timeline_plot.setLabel('top', units=None)
        self.timeline_plot.showGrid(x=True, y=False, alpha=.5)
        self.timeline_plot_items = []

        overview_layout_widget = pg.GraphicsLayoutWidget()
        overview_date_axis = DateAxis(orientation='bottom', label_date=False)
        self.overview_plot = overview_layout_widget.addPlot(axisItems={'bottom': overview_date_axis})
        # self.overview_plot.showAxis('left', show=False)
        # self.overview_plot.setLabel('bottom', text='Time', units='s')
        self.overview_plot.setLabel('bottom', units=None)

        # this doesnt work (getting the scroll)
        overview_layout_widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        insetview_layout_widget = pg.GraphicsLayoutWidget()
        insetview_date_axis = DateAxis(orientation='bottom', label_date=False)
        self.insetview_plot = insetview_layout_widget.addPlot(axisItems={'bottom': insetview_date_axis})
        # self.insetview_plot.showAxis('left', show=False)
        self.insetview_plot.showGrid(x=True, y=True, alpha=0.15)
        # self.insetview_plot.setLabel('bottom', text='Time', units='s')
        self.insetview_plot.setLabel('bottom', units=None)

        self.insetview_plot.vb.state['autoRange'] = [False, False]
        self.overview_plot.vb.state['autoRange'] = [False, False]
        self.timeline_plot.vb.state['autoRange'] = [False, False]

        self.splitter.addWidget(timeline_layout_widget)
        self.splitter.addWidget(overview_layout_widget)
        self.splitter.addWidget(insetview_layout_widget)
        print('setting splitter sizes')
        self.splitter.setSizes([150, 500, 500])
        # self.splitter.setStretchFactor(1, 6)  # make inset view 6 times larger

        self.insetview_plot.sigRangeChanged.connect(self.insetview_range_changed)
        self.overview_plot.sigRangeChanged.connect(self.overview_range_changed)
        self.insetview_plot.vb.scene().sigMouseClicked.connect(
            self.inset_clicked)  # Get original mouseclick signal with modifiers
        self.overview_plot.vb.scene().sigMouseClicked.connect(self.overview_clicked)
        self.timeline_plot.vb.scene().sigMouseClicked.connect(self.timeline_clicked)
        # hacky use of self.vb, but just rolling with it
        self.is_setting_window_position = False
        self.is_setting_ROI_position = False
        self.set_timeline_cursor()

        x_range, y_range = self.insetview_plot.viewRange()

        pen = pg.mkPen(color=(44, 133, 160, 192), width=2)
        # pen = pg.mkPen(color=(64, 192, 231, 255), width=2)
        # pen = pg.mkPen(color=(44, 133, 242,192), width=2)
        # penh = pg.mkPen(color=(211, 122, 95,255), width=2)

        self.overviewROI = pg.RectROI(pos=(x_range[0], y_range[0]),
                                      size=(x_range[1] - x_range[0], y_range[1] - y_range[0]),
                                      sideScalers=False, pen=pen, rotatable=False, removable=False)
        self.overviewROI.sigRegionChanged.connect(self.overviewROIchanged)
        self.overview_plot.addItem(self.overviewROI)

        self.inset_annotations = []
        self.overview_annotations = []
        # here we will store the plot items in nested dict form
        # {"1" : {'inset': obj,'overview':obj }
        # will be used for an ugly hack to snchonize across plots
        self.channel_plotitem_dict = {}
        self.main_model.annotations.sigAnnotationAdded.connect(self.add_annotaion_plot)
        self.main_model.annotations.sigLabelsChanged.connect(
            lambda: self.set_scenes_plot_annotations_data(self.main_model.annotations))

        # now overide the viewbox wheel event to allow shift wheel to zoom
        self.overview_plot.vb.wheelEvent = wheelEventWrapper(self.overview_plot.vb)
        self.insetview_plot.vb.wheelEvent = wheelEventWrapper(self.insetview_plot.vb)
        self.updateFilterSettings()

    def set_scenes_plot_channel_data(self, overview_range=None, pens=None, force_reset=False):
        '''
        # Not entirely clear the differences between this and
        set_plotitem_data is sensible
        pens - a list of len channels containing pens
        '''
        start_t = timer()
        self.splitter.widget(0).setBackgroundBrush(self.main_brush)
        self.splitter.widget(1).setBackgroundBrush(self.main_brush)
        self.splitter.widget(2).setBackgroundBrush(self.main_brush)

        if overview_range is None:
            overview_range, y_range = self.overview_plot.viewRange()
        self.overview_plot.setXRange(*overview_range, padding=0)
        self.insetview_plot.vb.setXRange(overview_range[0],
                                         overview_range[0] + min(30, overview_range[1] - overview_range[0]), padding=0)

        if self.animalid == self.main_model.project.current_animal.id and not force_reset:  # running for the first time
            print('Same animal:', self.animalid)
            return

        self.animalid = self.main_model.project.current_animal.id
        if self.animalid is None: # No animal is currently selected to plot
            return

        # we need to handle if channel not seen before
        # 6 std devations
        print('Items to delete')
        print(self.overview_plot.items)
        self.overview_plot.clear()
        print('Items after delete')
        print(self.overview_plot.items)
        self.insetview_plot.clear()
        # print(overview_range)

        end_t = timer()
        print('Paired graphics view init finished in', end_t - start_t, 'seconds')
        start_t = end_t
        # if self.scale is None:  # running for the first time
        if True:  # running for the first time
            print('Getting data to compute plot scale factors for new animal', self.animalid)
            arr, tarr = self.main_model.project.get_data_from_range(overview_range,
                                                                    n_envelope=1000)  # self.overview_plot.vb.viewRange()[0]) wierd behaviour here because vb.viewRange() range is not updated
            # print(arr.shape, tarr.shape)
            if len(arr.shape) < 2:
                return
            self.n_channels = arr.shape[1]
            self.scale = 1 / (8 * np.mean(np.std(arr, axis=0, keepdims=True), axis=1))
            self.overview_plot.vb.setYRange(-2, arr.shape[1] + 1)
            self.insetview_plot.vb.setYRange(-2, arr.shape[1] + 1)
            self.timeline_plot.setTitle('<p style="font-size:large"> Animal: ' + self.animalid + '</b>')
            end_t = timer()

        end_t = timer()
        print('Paired graphics view scale computation finished in', end_t - start_t, 'seconds')
        start_t = end_t

        if self.n_channels > 1:
            # color = [(*tuple(np.array(colorsys.hls_to_rgb(i_spaced_nfold(int(i*self.n_channels/8)%self.n_channels+1,self.n_channels), .4, .8)) * 255), 230)
            #          for i in range(self.n_channels)]
            # color = [(*tuple(np.array(colorsys.hsv_to_rgb(i_spaced_nfold(int(i*self.n_channels/8)%self.n_channels+1,self.n_channels),.8,.9)) * 255), 230)
            #          for i in range(self.n_channels)]
            # pens = [pg.mkPen(color=
            #                  color[i])
            #         for i in range(self.n_channels)]

            pens = [
                pg.mkPen(color=(214, 39, 40, 130)),
                pg.mkPen(color=(31, 119, 180, 130)),
                pg.mkPen(color=(44, 160, 44, 130)),
                pg.mkPen(color=(148, 103, 189, 130))]

            # pens=None

        for i in range(self.n_channels):
            if pens is None:
                pen = self.main_pen
            else:
                pen = pens[i % len(pens)]

            print('Setting plotitem channel data')
            self.set_plotitem_channel_data(pen, i, self.scale)

        end_t = timer()
        print('Paired graphics view plot channels finnished in', end_t - start_t, 'seconds')
        start_t = end_t

        print('settng up extra plot parameters...')
        # prevent scrolling past 0 and end of data
        # self.insetview_plot.vb.setLimits(xMin=0, xMax=arr.shape[0] / fs)
        self.overview_plot.vb.setLimits(maxXRange=3600)
        self.insetview_plot.vb.setLimits(maxXRange=3600)
        self.overview_plot.vb.setLimits(yMin=-3, yMax=self.n_channels + 3)
        max_range = self.main_model.project.current_animal.get_animal_time_range()
        print('Project time range:', max_range)
        self.overview_plot.vb.setLimits(xMin=max_range[0], xMax=max_range[1])
        self.insetview_plot.vb.setLimits(xMin=max_range[0], xMax=max_range[1])
        self.overview_plot.addItem(self.overviewROI)  # put back the overview box

        # Updating timeline plots
        self.timeline_plot.vb.setLimits(xMin=max_range[0], xMax=max_range[1], yMin=0, yMax=1, minYRange=1)
        self.timeline_plot.setRange(xRange=max_range, yRange=[0, 1])
        eeg_times = np.empty(2 * len(self.main_model.project.current_animal.eeg_init_time))
        eeg_times[0::2] = self.main_model.project.current_animal.eeg_init_time
        eeg_times[1::2] = eeg_times[0::2] + self.main_model.project.current_animal.eeg_duration
        vid_times = np.empty(2 * len(self.main_model.project.current_animal.video_init_time))
        vid_times[0::2] = self.main_model.project.current_animal.video_init_time
        vid_times[1::2] = vid_times[0::2] + self.main_model.project.current_animal.video_duration
        pen_eeg = pg.functions.mkPen(color=self.main_pen.color(), width=4)
        pen_vid = pg.functions.mkPen(color=(64, 192, 231, 127), width=2)
        for item in self.timeline_plot_items:  # remove previous lines without removing cursonr
            self.timeline_plot.removeItem(item)
        eeg_files_line = pg.PlotCurveItem(eeg_times, 0 * eeg_times + .5, connect='pairs', pen=pen_eeg)
        vid_files_line = pg.PlotCurveItem(vid_times, 0 * vid_times + .25, connect='pairs', pen=pen_vid)
        self.timeline_plot_items = [eeg_files_line, vid_files_line]
        self.timeline_plot.addItem(eeg_files_line)
        self.timeline_plot.addItem(vid_files_line)
        label = 'Start: ' + time.strftime('%H:%M:%S %b %d, %Y', time.localtime(max_range[0])) + \
                '; - End: ' + time.strftime('%H:%M:%S %b %d, %Y', time.localtime(max_range[1]))
        self.timeline_plot.setLabel(axis='bottom', text=label)

        self.set_scenes_plot_annotations_data(self.main_model.annotations, self.overview_plot.viewRange)
        self.main_model.annotations.sigFocusOnAnnotation.connect(self.set_focus_on_annotation)
        self.set_scene_window(self.main_model.window)
        self.set_scene_cursor()

        end_t = timer()
        print('Paired graphics view plot annotations + etc. in', end_t - start_t, 'seconds')

    def set_plotitem_channel_data(self, pen, index, init_scale):
        '''
        If the index exists within the plotitem dict we just set the data, else create
        or delete from the dict. (#todo)

        init_scale is the initial scaling of the channels. Set transform
        '''
        # todo stop passing the vb to construction have it added automatically when add the item to plot
        if True:  # index not in self.channel_plotitem_dict.keys(): # This was used before we were clearing the scenes upon file loading
            self.channel_plotitem_dict[index] = {}
            self.channel_plotitem_dict[index]['overview'] = PyecogPlotCurveItem(self.main_model.project, index,
                                                                                viewbox=self.overview_plot.vb, pen=pen)
            self.channel_plotitem_dict[index]['insetview'] = PyecogPlotCurveItem(self.main_model.project, index,
                                                                                 viewbox=self.insetview_plot.vb,
                                                                                 pen=pen)
            self.channel_plotitem_dict[index]['overview'].setY(index)
            self.channel_plotitem_dict[index]['insetview'].setY(index)
            m = QtGui.QTransform().scale(1, init_scale)
            self.channel_plotitem_dict[index]['overview'].setTransform(m)
            self.channel_plotitem_dict[index]['insetview'].setTransform(m)
            self.overview_plot.addItem(self.channel_plotitem_dict[index]['overview'])
            self.insetview_plot.addItem(self.channel_plotitem_dict[index]['insetview'])

        # self.channel_plotitem_dict[index]['overview'].set_data(y, fs)
        # self.channel_plotitem_dict[index]['insetview'].set_data(y, fs)
        # self.overview_plot.vb.setXRange(t0, t0 + y.shape[0]/fs, padding=0)
        # self.insetview_plot.vb.setXRange(t0, t0 + min(30, y.shape[0] / fs))

    # The following static methods are auxiliary functions to link several annotation related signals:
    # @staticmethod
    def function_generator_link_annotaions_to_graphs(self, annotation_object, annotation_graph):
        return lambda: annotation_graph.update_fields(annotation_object.getPos(),
                                                      annotation_object.getLabel(),
                                                      (*self.main_model.annotations.label_color_dict[
                                                          annotation_object.getLabel()], 25),
                                                      (*self.main_model.annotations.label_color_dict[
                                                          annotation_object.getLabel()], 200)
                                                      )

    @staticmethod
    def function_generator_link_graphs_to_annotations(annotation_object, annotation_graph):
        return lambda: annotation_object.setPos(annotation_graph.getRegion())

    @staticmethod
    def function_generator_link_graphs(annotation_graph_a, annotation_graph_b):
        return lambda: annotation_graph_b.setRegion(annotation_graph_a.getRegion())

    @staticmethod
    def function_generator_link_click(annotationpage, annotation_object):
        return lambda: annotationpage.focusOnAnnotation(annotation_object)

    def add_annotaion_plot(self, annotation):
        color = self.main_model.annotations.label_color_dict[
            annotation.getLabel()]  # circle hue with constant luminosity an saturation
        brush = pg.functions.mkBrush(color=(*color, 25))
        pen = pg.functions.mkPen(color=(*color, 200))
        channel_range = self.main_model.annotations.label_channel_range_dict[annotation.getLabel()]
        annotation_graph_o = PyecogLinearRegionItem((annotation.getStart(), annotation.getEnd()), pen=pen,
                                                    brush=brush, movable=False, id=None, channel_range=channel_range)
        annotation_graph_o.setZValue(-1)
        annotation_graph_i = PyecogLinearRegionItem((annotation.getStart(), annotation.getEnd()), pen=pen,
                                                    brush=brush, swapMode='push', label=annotation.getLabel(), id=None,
                                                    channel_range=channel_range, movable=False, movable_lines=True)

        annotation_graph_i.sigRegionChangeFinished.connect(
            self.function_generator_link_graphs_to_annotations(annotation, annotation_graph_i))
        annotation_graph_i.sigRegionChangeFinished.connect(
            self.function_generator_link_graphs(annotation_graph_i, annotation_graph_o))
        annotation_graph_i.sigClicked.connect(
            self.function_generator_link_click(self.main_model.annotations, annotation))
        annotation.sigAnnotationElementChanged.connect(
            self.function_generator_link_annotaions_to_graphs(annotation, annotation_graph_i))
        self.overview_plot.addItem(annotation_graph_o)
        self.insetview_plot.addItem(annotation_graph_i)
        self.inset_annotations.append(annotation_graph_i)  # lists to easily keep track of annotations
        self.overview_annotations.append(annotation_graph_o)
        self.plotted_annotations.append(annotation)

        annotation.sigAnnotationElementDeleted.connect(lambda: self.insetview_plot.removeItem(annotation_graph_i))
        annotation.sigAnnotationElementDeleted.connect(lambda: self.overview_plot.removeItem(annotation_graph_o))
        annotation.sigAnnotationElementDeleted.connect(lambda: self.plotted_annotations.remove(annotation))

    def set_scenes_plot_annotations_data(self, annotations, reset=True, pos=None):
        '''
        :param annotations: an annotations object
        :return: None
        '''
        if pos is None:
            pos, _ = self.overview_plot.viewRange()
        if reset:  # Clear existing annotations
            for item in self.inset_annotations:
                self.insetview_plot.removeItem(item)
            for item in self.overview_annotations:
                self.overview_plot.removeItem(item)
            self.plotted_annotations.clear()
        else:
            n = len(self.overview_annotations)
            for i in range(n):
                a = self.overview_annotations[n - i - 1]
                if intervals_overlap(pos, a.pos()):
                    self.overview_plot.removeItem(a)
                    b = self.inset_annotations[n - i - 1]
                    self.insetview_plot.removeItem(b)
                    del self.overview_annotations[n - i - 1]
                    del self.inset_annotations[n - i - 1]
                    n -= 1

        # Add annotation plots
        for annotation in annotations.annotations_list:
            if intervals_overlap(annotation.getPos(), pos) and annotation not in self.plotted_annotations:
                print('annotation.getpos , pos:', (annotation.getPos(), pos))
                self.add_annotaion_plot(annotation)

    def set_focus_on_annotation(self, annotation):
        if annotation is None:
            return
        state = self.overviewROI.getState()
        annotation_pos = annotation.getPos()
        self.main_model.set_time_position(annotation_pos[0] - 0.9)
        self.main_model.set_window_pos([annotation_pos[0] - 1, annotation_pos[1] + 1])
        if annotation_pos[0] > state['pos'][0] and annotation_pos[1] < state['pos'][0] + state['size'][0]:
            return  # skip if annotation is already completely in the plot area

        state['pos'][0] = annotation_pos[0] - .25 * (
        state['size'][0])  # put start of annotation in first quarter of screen
        self.insetview_plot.setRange(xRange=(state['pos'][0], state['pos'][0] + state['size'][0]),
                                     yRange=(state['pos'][1], state['pos'][1] + state['size'][1]),
                                     padding=0)

        xmin, xmax = self.overview_plot.viewRange()[0]
        x_range = xmax - xmin
        if annotation_pos[1] - annotation_pos[0] < 0.8 * x_range:
            new_xrange = ((annotation_pos[1] + annotation_pos[0] - x_range) / 2,
                          (annotation_pos[1] + annotation_pos[0] + x_range) / 2)
        else:
            new_xrange = (annotation_pos[0] - x_range * .1, annotation_pos[0] + x_range * .9)
        self.overview_plot.setRange(xRange=new_xrange, padding=0)

    def set_scene_cursor(self):
        cursor_o = PyecogCursorItem(pos=0)
        cursor_i = PyecogCursorItem(pos=0)
        # Should these connections be made in the main window code?
        cursor_i.sigPositionChanged.connect(lambda: self.main_model.set_time_position(cursor_i.getXPos()))
        cursor_o.sigPositionChanged.connect(lambda: self.main_model.set_time_position(cursor_o.getXPos()))
        # cursor_i.sigPositionChanged.connect(lambda: cursor_o.setPos(cursor_i.getPos()))
        # cursor_o.sigPositionChanged.connect(lambda: cursor_i.setPos(cursor_o.getPos()))
        self.main_model.sigTimeChanged.connect(lambda: cursor_i.setPos(self.main_model.time_position))
        self.main_model.sigTimeChanged.connect(lambda: cursor_o.setPos(self.main_model.time_position))
        self.overview_plot.addItem(cursor_o)
        self.insetview_plot.addItem(cursor_i)

    def set_timeline_cursor(self):
        self.timeline_cursor = PyecogCursorItem(pos=0)
        self.timeline_cursor.sigPositionChanged.connect(
            lambda: self.set_overview_center_position(self.timeline_cursor.getXPos()))
        self.timeline_plot.addItem(self.timeline_cursor)
        # cursor_i.sigPositionChanged.connect(lambda: self.main_model.set_time_position(cursor_i.getXPos()))
        # cursor_i.sigPositionChanged.connect(lambda: cursor_o.setPos(cursor_i.getPos()))
        # cursor_o.sigPositionChanged.connect(lambda: cursor_i.setPos(cursor_o.getPos()))
        # self.main_model.sigTimeChanged.connect(lambda: cursor_i.setPos(self.main_model.time_position))
        # self.main_model.sigTimeChanged.connect(lambda: cursor_o.setPos(self.main_model.time_position))
        # self.overview_plot.addItem(cursor_o)
        # self.insetview_plot.addItem(cursor_i)

    def set_scene_window(self, window):
        color = self.main_pen.color()
        color.setAlpha(15)
        brush = pg.functions.mkBrush(color)
        pen = self.main_pen
        # brush = pg.functions.mkBrush(color=(1, 1, 1, 10))
        # pen = pg.functions.mkPen(color=(1, 1, 1, 200))
        # window_item_o = pg.LinearRegionItem(window, brush=brush,movable=False)
        window_item_o = PyecogLinearRegionItem(window, pen=pen, brush=brush, movable=False, id=None)
        self.overview_plot.addItem(window_item_o)
        # window_item_i = pg.LinearRegionItem(window, brush=brush)
        window_item_i = PyecogLinearRegionItem(window, pen=pen, brush=brush, movable=True, id=None)
        window_item_i.setZValue(-2)  # Bellow traces 0 and annotations -1
        self.insetview_plot.addItem(window_item_i)
        window_item_i.sigRegionChangeFinished.connect(lambda: window_item_o.setRegion(window_item_i.getRegion()))
        window_item_i.sigRegionChangeFinished.connect(lambda: self.main_model.set_window_pos(window_item_i.getRegion()))
        # window_item_i.sigRegionChangeFinished.connect(lambda: self.main_model.annotations.focusOnAnnotation(None))
        # window_item_i.sigRegionChangeFinished.connect(lambda: self.main_model.set_time_position(self.main_model.window[0]-1))
        # window_item_i.sigClicked.connect(lambda: self.main_model.annotations.focusOnAnnotation(None))
        # window_item_i.sigClicked.connect(lambda: self.main_model.set_time_position(self.main_model.window[0]-1))
        self.main_model.sigWindowChanged.connect(window_item_i.setRegion)

    def graphics_object_xchanged(self):
        print('xChanged graphics object')

    def overviewROIchanged(self):
        state = self.overviewROI.getState()
        self.insetview_plot.setRange(xRange=(state['pos'][0], state['pos'][0] + state['size'][0]),
                                     yRange=(state['pos'][1], state['pos'][1] + state['size'][1]),
                                     padding=0)

    def timeline_clicked(self, ev):
        '''
        ev pos is postion in 'scene' coords of mouse click
        '''
        # print('hit', ev_pos)
        # print(event, event.pos())
        modifiers = ev.modifiers()
        pos = self.timeline_plot.vb.mapSceneToView(ev.scenePos())
        self.set_overview_center_position(pos.x())
        if modifiers == QtCore.Qt.ControlModifier:
            # self.main_model.annotations.focusOnAnnotation(None)
            self.main_model.set_time_position(pos.x())

    def set_overview_center_position(self, pos):
        xmin, xmax = self.overview_plot.viewRange()[0]
        x_range = xmax - xmin
        print(x_range, pos)
        new_xrange = (pos - x_range / 2, pos + x_range / 2)
        print(new_xrange)
        self.overview_plot.setRange(xRange=new_xrange,
                                    padding=0, )

    def overview_clicked(self, ev):
        '''
        ev pos is postion in 'scene' coords of mouse click
        '''
        # print('hit', ev_pos)
        # print(event, event.pos())
        pos = self.overview_plot.vb.mapSceneToView(ev.scenePos())
        modifiers = ev.modifiers()
        if modifiers == QtCore.Qt.ShiftModifier:  # Setting ROI with two clicks
            if not self.is_setting_ROI_position:
                self.is_setting_ROI_position = pos  # save position of first click
                return
            else:
                pos0 = self.is_setting_ROI_position
                new_xrange = (min(pos0.x(), pos.x()), max(pos0.x(), pos.x()))
                new_yrange = (min(pos0.y(), pos.y()), max(pos0.y(), pos.y()))
                print('old range:', self.insetview_plot.viewRange()[0], 'new range:', new_xrange)
                self.is_setting_ROI_position = False  # clear position of first shift+click
                self.overviewROI.setPos((new_xrange[0], new_yrange[0]))
                self.overviewROI.setSize((new_xrange[1] - new_xrange[0], new_yrange[1] - new_yrange[0]))
                self.insetview_plot.setRange(xRange=new_xrange,
                                             yRange=new_yrange,
                                             padding=0)
                return
        self.is_setting_ROI_position = False  # clear position of any shift+click, and center inset view in click
        center = pos
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
                                     padding=0, )

        if modifiers == QtCore.Qt.ControlModifier:
            # self.main_model.annotations.focusOnAnnotation(None)
            self.main_model.set_time_position(pos.x())

    def inset_clicked(self, ev):
        pos = self.insetview_plot.vb.mapSceneToView(ev.scenePos())
        print('insetclicked ', pos)
        print('modifiers:', ev.modifiers())
        modifiers = ev.modifiers()
        if modifiers == QtCore.Qt.ShiftModifier:
            self.main_model.annotations.focusOnAnnotation(None)
            if not self.is_setting_window_position:
                self.main_model.set_window_pos([pos.x(), pos.x()])
                self.is_setting_window_position = True  # pos.x()
                return
            else:
                current_pos = self.main_model.window
                self.main_model.set_window_pos([current_pos[0], pos.x()])
        self.is_setting_window_position = False

        if modifiers == QtCore.Qt.ControlModifier:
            # self.main_model.annotations.focusOnAnnotation(None)
            self.main_model.set_time_position(pos.x())

        if modifiers == QtCore.Qt.AltModifier:
            self.show


    def overview_range_changed(self, mask=None):
        x_range, _ = self.overview_plot.viewRange()
        self.set_scenes_plot_annotations_data(self.main_model.annotations, reset=False, pos=x_range)
        self.timeline_cursor.setPos(np.mean(x_range))
        # self.insetview_plot.removeItem(annotation_graph_i)

    def insetview_range_changed(self, mask=None):
        '''connected to signal from insetview_plot'''
        x_range, y_range = self.insetview_plot.viewRange()
        self.overviewROI.setPos((x_range[0], y_range[0]))
        self.overviewROI.setSize((x_range[1] - x_range[0], y_range[1] - y_range[0]))

        ox_range, oy_range = self.overview_plot.viewRange()  # scroll the overview if the inset is on the edge
        if x_range[0] < ox_range[0]:
            self.overview_plot.vb.setXRange(x_range[0], x_range[0] + ox_range[1] - ox_range[0], padding=0)
        elif x_range[1] > ox_range[1]:
            self.overview_plot.vb.setXRange(x_range[1] - (ox_range[1] - ox_range[0]), x_range[1], padding=0)

    def insetview_page_left(self):
        xmin, xmax = self.insetview_plot.viewRange()[0]
        x_range = xmax - xmin
        new_xrange = (xmin - x_range, xmin)
        print(new_xrange)
        self.insetview_plot.setRange(xRange=new_xrange, padding=0)

    def insetview_page_right(self):
        xmin, xmax = self.insetview_plot.viewRange()[0]
        x_range = xmax - xmin
        new_xrange = (xmax, xmax + x_range)
        print(new_xrange)
        self.insetview_plot.setRange(xRange=new_xrange, padding=0)

    def insetview_set_xrange(self, x_range):
        xmin, xmax = self.insetview_plot.viewRange()[0]
        centre = (xmax + xmin) / 2
        new_xrange = (centre - x_range / 2, centre + x_range / 2)
        print(new_xrange)
        self.insetview_plot.setRange(xRange=new_xrange, padding=0)

    def overview_set_xrange(self, x_range):
        xmin, xmax = self.overview_plot.viewRange()[0]
        centre = (xmax + xmin) / 2
        new_xrange = (centre - x_range / 2, centre + x_range / 2)
        print(new_xrange)
        self.overview_plot.setRange(xRange=new_xrange, padding=0)

    def overview_page_left(self):
        xmin, xmax = self.overview_plot.viewRange()[0]
        x_range = xmax - xmin
        new_xrange = (xmin - x_range, xmin)
        print(new_xrange)
        self.overview_plot.setRange(xRange=new_xrange, padding=0)

    def overview_page_right(self):
        xmin, xmax = self.overview_plot.viewRange()[0]
        x_range = xmax - xmin
        new_xrange = (xmax, xmax + x_range)
        print(new_xrange)
        self.overview_plot.setRange(xRange=new_xrange, padding=0)

    def updateFilterSettings(self, settings=(False, 0, 1e6)):
        self.apply_filter = settings[0]
        self.highpass_frequency = settings[1]
        self.lowpass_frequency = settings[1]
        self.main_model.project.updateFilterSettings(settings)
        xmin, xmax = self.insetview_plot.viewRange()[0]
        self.insetview_plot.setRange(xRange=(0.9 * xmin + 0.1 * xmax, 0.1 * xmin + 0.9 * xmax),
                                     padding=0)  # just to update the plots
        self.insetview_plot.setRange(xRange=(xmin, xmax), padding=0)
        xmin, xmax = self.overview_plot.viewRange()[0]
        self.overview_plot.setRange(xRange=(0.9 * xmin + 0.1 * xmax, 0.1 * xmin + 0.9 * xmax),
                                    padding=0)  # just to update the plots
        self.overview_plot.setRange(xRange=(xmin, xmax), padding=0)


class DateAxis(pg.AxisItem):
    def __init__(self, label_date=True, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label_date = label_date

    def tickStrings(self, values, scale, spacing):
        strns = []
        rng = self.range[1] - self.range[0]  # max(values)-min(values)
        # if rng < 120:
        #    return pg.AxisItem.tickStrings(self, values, scale, spacing)
        if rng <= 2:
            string = '%H:%M:%S.%f'
            label1 = '%b %d -'
            label2 = ' %b %d, %Y'
        elif rng < 3600 * 24:
            string = '%H:%M:%S'
            label1 = '%b %d -'
            label2 = ' %b %d, %Y'
        elif rng >= 3600 * 24 and rng < 3600 * 24 * 30:
            string = '%d'
            label1 = '%b - '
            label2 = '%b, %Y'
        elif rng >= 3600 * 24 * 30 and rng < 3600 * 24 * 30 * 24:
            string = '%b'
            label1 = '%Y -'
            label2 = ' %Y'
        elif rng >= 3600 * 24 * 30 * 24:
            string = '%Y'
            label1 = ''
            label2 = ''

        for x in values:
            try:
                strns.append(datetime.strftime(datetime.fromtimestamp(x), string))
            except ValueError:  ## Windows can't handle dates before 1970
                strns.append('err')
        try:
            label = time.strftime(label1, time.localtime(min(values))) + time.strftime(label2,
                                                                                       time.localtime(max(values)))
        except ValueError:
            label = ''
        self.autoSIPrefix = False
        if self.label_date:
            self.setLabel(text=label, units=None)
        return strns
