# pyecog2


Changes to pyqtgraph
---------------------
Contains a copy of pyqtgraph with some changes.
These are due to time constraints... should probably have subclassed.

    Added an extra signal to pg.ViewBox to allow the PairedGraphicsView
    class to connect the top plot with the bottom.
    sigMouseLeftClick = QtCore.Signal(object)

    in....
    def mouseClickEvent(self, ev):
        ... # added below
        if ev.button() == QtCore.Qt.LeftButton:
            ev.accept()
            self.sigMouseLeftClick.emit(ev)
