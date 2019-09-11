# pyecog2


Changes to pyqtgraph
---------------------
Contains a copy of pyqtgraph with some changes.
These are due to time constraints... should probably have subclassed. Also this list is no doubt
incomplete

    Added an extra signal to pg.ViewBox to allow the PairedGraphicsView
    class to connect the top plot with the bottom.
    sigMouseLeftClick = QtCore.Signal(object)

    in....
    ```
    def mouseClickEvent(self, ev):
        ... # added below
        if ev.button() == QtCore.Qt.LeftButton:
            ev.accept()
            self.sigMouseLeftClick.emit(ev)
    ```

    Augmented the wheelEvent method to scale plotlineitems
    ```
    def wheelEvent(self,ev, axis):
        # JC added
    if ev.modifiers() == QtCore.Qt.ShiftModifier:
        #self.yscale_data *= s[1]
        for child in self.childGroup.childItems()[:]:
            if hasattr(child, 'accept_mousewheel_transformations'):
                m_old = child.transform()
                m = QtGui.QTransform()
                m.scale(1, m_old.m22()*s[1])
                child.setTransform(m)
        ev.accept()
    ```
