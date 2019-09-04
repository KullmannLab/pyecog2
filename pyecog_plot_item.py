from PyQt5 import QtGui, QtWidgets#,# uic
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QRect, QTimer
from scipy import signal, stats
import pyqtgraph as pg

class PyecogPlotCurveItem(pg.PlotCurveItem):

    ''' Hmm seems like you need the graphics scene subcalss of pyqtgraph
    for how they get all trhe drags
    also there is the  vewbox presumeableig that handles stuff - view? plotitme.?#

    also maybe the downsampling in plotitem?
    '''

    def init(self, *args):
        super(pg.PlotCurveItem, self).__init__(args)

    def mousePressEvent(self, ev):
        ''' forget difference between this and the click and drag evnets belwo '''
        if self.clickable:
            #print('ive been cliked')
            #super(pg.PlotCurveItem,self).mousePressEvent(ev)
            ev.ignore()
        else:
            ev.ignore()

    def mouseClickEvent(self, ev):
        print('mouseClickEvent plotcurveitem')
        pass
    def mouseDragEvent(self, ev):
        print('mouseDragEvent plotcurveitem')
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
