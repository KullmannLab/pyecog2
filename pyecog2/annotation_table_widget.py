from PySide2 import QtGui, QtCore, QtWidgets
from pyecog2.annotations_module import AnnotationPage
from datetime import datetime
import numpy as np
from timeit import default_timer as timer

basestring = str
asUnicode = str


# __all__ = ['TableWidget']

def date_fmt(item):
    return datetime.utcfromtimestamp(item.value).strftime('%Y-%m-%d %H:%M:%S')

def confidence_fromat(item):
    return str(item.value)

def _defersort(fn):
    def defersort(self, *args, **kwds):
        # may be called recursively; only the first call needs to block sorting
        setSorting = False
        if self._sorting is None:
            self._sorting = self.isSortingEnabled()
            setSorting = True
            self.setSortingEnabled(False)
        try:
            return fn(self, *args, **kwds)
        finally:
            if setSorting:
                self.setSortingEnabled(self._sorting)
                self._sorting = None

    return defersort


class AnnotationTableWidget(QtWidgets.QTableWidget):
    """Extends QTableWidget with some useful functions for automatic data handling
    and copy / export context menu. Can automatically format and display a variety
    of data types (see :func:`setData() <pyqtgraph.TableWidget.setData>` for more
    information.QtWidgets.QTableWidgetok
    """

    def __init__(self, annotationsPage=AnnotationPage(), parent=None, *args, **kwds):
        """
        All positional arguments are passed to QTableWidget.__init__().

        ===================== =================================================
        **Keyword Arguments**
        editable              (bool) If True, cells in the table can be edited
                              by the user. Default is False.
        sortable              (bool) If True, the table may be soted by
                              clicking on column headers. Note that this also
                              causes rows to appear initially shuffled until
                              a sort column is selected. Default is True.
                              *(added in version 0.9.9)*
        ===================== =================================================
        """

        QtWidgets.QTableWidget.__init__(self, *args)
        self.connections_list = []
        self.setWindowTitle('Annotations Table')
        self.itemClass = AnnotationTableWidgetItem
        self.setVerticalScrollMode(self.ScrollPerPixel)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ContiguousSelection)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        self.clear()

        kwds.setdefault('sortable', True)
        kwds.setdefault('editable', True)
        self.setEditable(kwds.pop('editable'))
        self.setSortingEnabled(kwds.pop('sortable'))

        if len(kwds) > 0:
            raise TypeError("Invalid keyword arguments '%s'" % kwds.keys())

        self._sorting = None  # used when temporarily disabling sorting

        # self._formats = {None: None}  # stores per-column formats and entire table format
        self._formats = {None: None,
                         1: date_fmt,
                         2: date_fmt,
                         3: confidence_fromat}  # stores per-column formats and entire table format

        self.sortModes = {}  # stores per-column sort mode
        self.table_paused = False  # to use when doing batch updates e.g. deleting all annotation with a given label
        self.itemChanged.connect(self.handleItemChanged)

        self.contextMenu = QtWidgets.QMenu()
        self.contextMenu.addAction('Copy Selection').triggered.connect(self.copySel)
        self.contextMenu.addAction('Copy All').triggered.connect(self.copyAll)
        self.contextMenu.addAction('Save Selection').triggered.connect(self.saveSel)
        self.contextMenu.addAction('Save All').triggered.connect(self.saveAll)
        self.parent = parent
        self.annotationsPage = annotationsPage
        self.setData(annotationsPage.annotations_list)
        self.annotationsPage.sigFocusOnAnnotation.connect(
            self.selectAnnotation)  # connect function to select annotation
        self.currentItemChanged.connect(self.my_item_clicekd)
        self.annotationsPage.sigAnnotationAdded.connect(self.appendData)
        self.annotationsPage.sigLabelsChanged.connect(lambda: self.setData(annotationsPage.annotations_list))
        self.annotationsPage.sigPauseTable.connect(self.pauseTable)

    def pauseTable(self, b=False):
        self.table_paused = b

    def my_item_clicekd(self, item):
        if item is not None:
            self.annotationsPage.focusOnAnnotation(item.annotation)
        else:
            # self.annotationsPage.focusOnAnnotation(None) # This Creates circularities because the funciton is called on currentItemChamged and not click
            pass

    def updateRowColor(self, r):
        alpha = 125
        bgcolor = self.annotationsPage.label_color_dict[self.item(r, 0).text()]
        for k in range(self.columnCount()):
            self.item(r, k).setBackground(QtGui.QBrush(QtGui.QColor(*bgcolor, alpha)))

    def updateTableColor(self):
        for i in range(self.rowCount()):
            self.updateRowColor(i)

    def clear(self):
        """Clear all contents from the table."""
        # QtWidgets.QTableWidget.clearContents(self)
        QtWidgets.QTableWidget.clear(self)
        # self.verticalHeadersSet = False
        # self.horizontalHeadersSet = False

        # uplug all connections
        for connection in self.connections_list:
            connection[0].sigAnnotationElementChanged.disconnect(connection[1])
        self.connections_list.clear()
        self.items = []
        self.setRowCount(0)
        # self.setColumnCount(0)
        # self.sortModes = {}

    def setData(self, data):
        """Set the data displayed in the table.
        Allowed formats are:

        * numpy arrays
        * numpy record arrays
        * metaarrays
        * list-of-lists  [[1,2,3], [4,5,6]]
        * dict-of-lists  {'x': [1,2,3], 'y': [4,5,6]}
        * list-of-dicts  [{'x': 1, 'y': 4}, {'x': 2, 'y': 5}, ...]
        """
        start_t = timer()
        print('Annotations Table widget Set Data called. Annotations page length:',
              len(self.annotationsPage.annotations_list),
              'row count:', self.rowCount())
        ranges = self.selectedRanges()
        self.clear()
        self.appendData(data)
        self.resizeColumnsToContents()
        if len(ranges) > 0:
            self.setRangeSelected(ranges[0], True)
        items = self.selectedItems()
        if len(items) > 0:
            self.setCurrentItem(items[0])
        print('Annotations Table widget Set Data ran in', timer() - start_t, 'seconds')

    @_defersort
    def appendData(self, annotaion_list):
        """
        Add new rows to the table.

        See :func:`setData() <pyqtgraph.TableWidget.setData>` for accepted
        data types.
        """
        if type(annotaion_list) is not list:
            annotaion_list = [annotaion_list]  # Allow to receive lists or single annotations as inputs as well

        startRow = self.rowCount()
        self.setColumnCount(5)  # ['Label', 'Start', 'End', 'Confidence', 'Notes']
        self.setHorizontalHeaderLabels(['Label', 'Start', 'End', 'Confidence', 'Notes'])
        self.horizontalHeadersSet = True
        r = startRow

        for annotation in annotaion_list:
            self.setRow(r, annotation, [i[0] for i in annotation.element_dict.items()])
            # annotation.sigAnnotationElementChanged.connect(self.updateTableColor)
            annotation.sigAnnotationElementDeleted.connect(lambda: self.myremoveRow(r))
            for c in range(self.columnCount()):
                item = self.item(r, c)
                f = self.function_generator_link(item)
                self.connections_list.append((annotation, f))
                annotation.sigAnnotationElementChanged.connect(f)
            r += 1

        if (self._sorting and self.horizontalHeadersSet and
                self.horizontalHeader().sortIndicatorSection() >= self.columnCount()):
            self.sortByColumn(1, QtCore.Qt.AscendingOrder)

        self.updateTableColor()

    # @staticmethod
    def function_generator_link(self,table_item):
        return lambda: table_item.update_value_from_annotation(self.annotationsPage)

    def myremoveRow(self, r):
        # couldn't figure out any other way apart from reseting all the data
        # plus when reseting the table, for some reason the annotations are not fully removed
        if self.table_paused:
            print('Table paused: skiping deleting annotation and reseting table data...', r, '(', self.rowCount(), ')')
            return
        print('Deleting annotation and reseting table data...', r, '(', self.rowCount(), ')')
        if len(self.annotationsPage.annotations_list) < self.rowCount():
            self.setData(self.annotationsPage.annotations_list)
        else:
            print('Nothing to delete')
        print('Finnished rebuilding Annotations Table')

    def removeSelection(self):
        annotations_to_remove = list(set([item.annotation for item in self.selectedItems()]))
        self.annotationsPage.history_is_paused = True  # Avoid filling history with all the deletion steps - slightly unelegant to do this here
        self.pauseTable(True)
        for annotation in annotations_to_remove:
            print('Removing annotation:', annotation.getLabel(), annotation.getPos())
            self.annotationsPage.delete_annotation(annotation)
        self.pauseTable(False)
        self.setData(self.annotationsPage.annotations_list)
        self.annotationsPage.history_is_paused = False
        self.annotationsPage.cache_to_history()

    def changeSelectionLabel(self, label):
        annotations_to_change = list(set([item.annotation for item in self.selectedItems()]))
        self.annotationsPage.history_is_paused = True  # Avoid filling history with all the deletion steps - slightly unelegant to do this here
        for annotation in annotations_to_change:
            print('changing annotation label', annotation.getLabel(), annotation.getPos())
            annotation.setLabel(label)
            # annotation.setConfidence(float('inf'))  # not convenient because of annotation jumps if ordered by confidence
        # a bit of a pity that this signal cannot be emited by the anotationPage
        # self.annotationsPage.sigLabelsChanged.emit(label)  # this signal should not be emitted
        self.annotationsPage.history_is_paused = False
        self.annotationsPage.cache_to_history()

    def setEditable(self, editable=True):
        self.editable = editable
        for item in self.items:
            item.setEditable(editable)

    def setFormat(self, format, column=None):
        """
        Specify the default text formatting for the entire table, or for a
        single column if *column* is specified.

        If a string is specified, it is used as a format string for converting
        float values (and all other types are converted using str). If a
        function is specified, it will be called with the item as its only
        argument and must return a string. Setting format = None causes the
        default formatter to be used instead.

        Added in version 0.9.9.

        """
        if format is not None and not isinstance(format, basestring) and not callable(format):
            raise ValueError("Format argument must string, callable, or None. (got %s)" % format)

        self._formats[column] = format

        if column is None:
            # update format of all items that do not have a column format
            # specified
            for c in range(self.columnCount()):
                if self._formats.get(c, None) is None:
                    for r in range(self.rowCount()):
                        item = self.item(r, c)
                        if item is None:
                            continue
                        item.setFormat(format)
        else:
            # set all items in the column to use this format, or the default
            # table format if None was specified.
            if format is None:
                format = self._formats[None]
            for r in range(self.rowCount()):
                item = self.item(r, column)
                if item is None:
                    continue
                item.setFormat(format)

    def iteratorFn(self, data):
        ## Return 1) a function that will provide an iterator for data and 2) a list of header strings
        if isinstance(data, list) or isinstance(data, tuple):
            return lambda d: d.__iter__(), None
        elif isinstance(data, dict):
            return lambda d: iter(d.values()), list(map(str, data.keys()))
        elif (hasattr(data, 'implements') and data.implements('MetaArray')):
            if data.axisHasColumns(0):
                header = [asUnicode(data.columnName(0, i)) for i in range(data.shape[0])]
            elif data.axisHasValues(0):
                header = list(map(asUnicode, data.xvals(0)))
            else:
                header = None
            return self.iterFirstAxis, header
        elif isinstance(data, np.ndarray):
            return self.iterFirstAxis, None
        elif isinstance(data, np.void):
            return self.iterate, list(map(asUnicode, data.dtype.names))
        elif data is None:
            return (None, None)
        elif np.isscalar(data):
            return self.iterateScalar, None
        else:
            msg = "Don't know how to iterate over data type: {!s}".format(type(data))
            raise TypeError(msg)

    def iterFirstAxis(self, data):
        for i in range(data.shape[0]):
            yield data[i]

    def iterate(self, data):
        # for numpy.void, which can be iterated but mysteriously
        # has no __iter__ (??)
        for x in data:
            yield x

    def iterateScalar(self, data):
        yield data

    def appendRow(self, data):
        self.appendData([data])

    @_defersort
    def addRow(self, vals):
        row = self.rowCount()
        self.setRowCount(row + 1)
        self.setRow(row, vals)

    @_defersort
    def setRow(self, row, annotation, keys):
        if row > self.rowCount() - 1:
            self.setRowCount(row + 1)
        for col in range(len(keys)):
            key = keys[col]
            item = self.itemClass(annotation, key, row)
            if key != 'label':
                item.setEditable(self.editable)

            sortMode = self.sortModes.get(col, None)
            if sortMode is not None:
                item.setSortMode(sortMode)
            format = self._formats.get(col, self._formats[None])
            item.setFormat(format)
            self.items.append(item)
            self.setItem(row, col, item)
            # item.setValue(val)  # Required--the text-change callback is invoked
            # when we call setItem.

    def setSortMode(self, column, mode):
        """
        Set the mode used to sort *column*.

        ============== ========================================================
        **Sort Modes**
        value          Compares item.value if available; falls back to text
                       comparison.
        text           Compares item.text()
        index          Compares by the order in which items were inserted.
        ============== ========================================================

        Added in version 0.9.9
        """
        for r in range(self.rowCount()):
            item = self.item(r, column)
            if hasattr(item, 'setSortMode'):
                item.setSortMode(mode)
        self.sortModes[column] = mode

    def sizeHint(self):
        # based on http://stackoverflow.com/a/7195443/54056
        width = sum(self.columnWidth(i) for i in range(self.columnCount()))
        width += self.verticalHeader().sizeHint().width()
        width += self.verticalScrollBar().sizeHint().width()
        width += self.frameWidth() * 2
        height = sum(self.rowHeight(i) for i in range(self.rowCount()))
        height += self.verticalHeader().sizeHint().height()
        height += self.horizontalScrollBar().sizeHint().height()
        return QtCore.QSize(width, height)

    def serialize(self, useSelection=False):
        """Convert entire table (or just selected area) into tab-separated text values"""
        if useSelection:
            selection = self.selectedRanges()[0]
            rows = list(range(selection.topRow(),
                              selection.bottomRow() + 1))
            columns = list(range(selection.leftColumn(),
                                 selection.rightColumn() + 1))
        else:
            rows = list(range(self.rowCount()))
            columns = list(range(self.columnCount()))

        data = []
        if self.horizontalHeadersSet:
            row = []
            if self.verticalHeadersSet:
                row.append(asUnicode(''))

            for c in columns:
                row.append(asUnicode(self.horizontalHeaderItem(c).text()))
            data.append(row)

        for r in rows:
            row = []
            if self.verticalHeadersSet:
                row.append(asUnicode(self.verticalHeaderItem(r).text()))
            for c in columns:
                item = self.item(r, c)
                if item is not None:
                    row.append(asUnicode(item.value))
                else:
                    row.append(asUnicode(''))
            data.append(row)

        s = ''
        for row in data:
            s += ('\t'.join(row) + '\n')
        return s

    def copySel(self):
        """Copy selected data to clipboard."""
        QtWidgets.QApplication.clipboard().setText(self.serialize(useSelection=True))

    def copyAll(self):
        """Copy all data to clipboard."""
        QtWidgets.QApplication.clipboard().setText(self.serialize(useSelection=False))

    def saveSel(self):
        """Save selected data to file."""
        self.save(self.serialize(useSelection=True))

    def saveAll(self):
        """Save all data to file."""
        self.save(self.serialize(useSelection=False))

    def save(self, data):
        fileName = QtWidgets.QFileDialog.getSaveFileName(self, "Save As..", "", "Tab-separated values (*.tsv)")
        if isinstance(fileName, tuple):
            fileName = fileName[0]  # Qt4/5 API difference
        if fileName == '':
            return
        open(str(fileName), 'w').write(data)

    def contextMenuEvent(self, ev):
        self.contextMenu.popup(ev.globalPos())

    def keyPressEvent(self, ev):
        print('Key press captured by Table', ev.key())
        if ev.key() == QtCore.Qt.Key_C and ev.modifiers() == QtCore.Qt.ControlModifier:
            ev.accept()
            self.copySel()
            return
        # # Now follows a very dirty piece of code because QTableWidget handles kyepresses in very inconsistent ways
        numbered_keys = [QtCore.Qt.Key_1, QtCore.Qt.Key_2, QtCore.Qt.Key_3, QtCore.Qt.Key_4, QtCore.Qt.Key_5,
                         QtCore.Qt.Key_6, QtCore.Qt.Key_7, QtCore.Qt.Key_8, QtCore.Qt.Key_9, QtCore.Qt.Key_0]

        for i in range(len(numbered_keys)):
            if ev.key() == numbered_keys[i]:
                print(i + 1, 'pressed')
                self.parent.keyPressEvent(ev)
                # if self.annotationsPage.focused_annotation is not None:
                #     self.changeSelectionLabel(self.annotationsPage.labels[i])
                return

        if ev.key() == QtCore.Qt.Key_Space:  # pass spacebar presses to main window -  implementation is a bit naughty...
            if self.parent is not None:
                print('passing to main window')
                self.parent.keyPressEvent(ev)

        if ev.key() == QtCore.Qt.Key_Delete:
            # self.main_model.annotations.delete_annotation(self.main_model.annotations.focused_annotation)
            self.removeSelection()

        QtWidgets.QTableWidget.keyPressEvent(self, ev)

    def handleItemChanged(self, item):
        item.itemChanged()

    def selectAnnotation(self, annotation):
        if annotation is None:
            self.clearSelection()  # clear selection if no annotation is found
            return
        for r in range(self.rowCount()):
            if self.item(r, 0).annotation == annotation:
                c = 0
                try:
                    c = self.selectedRanges()[
                        0].leftColumn()  # Keep the same column selected if there is already a selection
                except Exception:
                    pass
                self.setCurrentCell(r, c)


class AnnotationTableWidgetItem(QtWidgets.QTableWidgetItem):
    def __init__(self, annotation, key, index, format=None):
        QtWidgets.QTableWidgetItem.__init__(self, '')
        self._blockValueChange = False
        self._format = None
        self._defaultFormat = '%4.2f'
        self.sortMode = 'value'
        self.index = index
        flags = QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
        self.setFlags(flags)
        self.annotation = annotation
        self.key = key
        self.setValue(annotation.element_dict[key])
        self.setFormat(format)

    def update_value_from_annotation(self,annotation_page):
        # print('updating table item', self.index,self.key,self.value)
        alpha = 125
        bgcolor = annotation_page.label_color_dict[self.annotation.getLabel()]
        self.setBackground(QtGui.QBrush(QtGui.QColor(*bgcolor, alpha)))
        if self.value != self.annotation.element_dict[self.key]:
            self.setValue(self.annotation.element_dict[self.key])


    def setEditable(self, editable):
        """
        Set whether this item is user-editable.
        """
        if editable:
            self.setFlags(self.flags() | QtCore.Qt.ItemIsEditable)
        else:
            self.setFlags(self.flags() & ~QtCore.Qt.ItemIsEditable)

    def setSortMode(self, mode):
        """
        Set the mode used to sort this item against others in its column.

        ============== ========================================================
        **Sort Modes**
        value          Compares item.value if available; falls back to text
                       comparison.
        text           Compares item.text()
        index          Compares by the order in which items were inserted.
        ============== ========================================================
        """
        modes = ('value', 'text', 'index', None)
        if mode not in modes:
            raise ValueError('Sort mode must be one of %s' % str(modes))
        self.sortMode = mode

    def setFormat(self, fmt):
        """Define the conversion from item value to displayed text.

        If a string is specified, it is used as a format string for converting
        float values (and all other types are converted using str). If a
        function is specified, it will be called with the item as its only
        argument and must return a string.

        Added in version 0.9.9.
        """
        if fmt is not None and not isinstance(fmt, basestring) and not callable(fmt):
            raise ValueError("Format argument must string, callable, or None. (got %s)" % fmt)
        self._format = fmt
        self._updateText()

    def _updateText(self):
        self._blockValueChange = True
        try:
            self._text = self.format()
            self.setText(self._text)
        finally:
            self._blockValueChange = False

    def setValue(self, value):
        self.value = value
        if self.value != self.annotation.element_dict[self.key]:
            self.annotation.setKey(self.key, value)
            # print('setting new value:', type(value),value)
        self._updateText()

    def itemChanged(self):
        """Called when the data of this item has changed."""
        if self.text() != self._text:
            self.textChanged()

    def textChanged(self):
        """Called when this item's text has changed for any reason."""
        print('TextChanged was called')
        self._text = self.text()

        if self._blockValueChange:
            # text change was result of value or format change; do not
            # propagate.
            print('skiped set value')
            return

        try:
            self.setValue(type(self.value)(self.text()))
            # self.value = type(self.value)(self.text())
        except ValueError:
            # self.value = str(self.text())
            self._updateText()
            print('error changing value ')

    def format(self):
        if callable(self._format):
            return self._format(self)
        if isinstance(self.value, (float, np.floating)):
            if self._format is None:
                return self._defaultFormat % self.value
            else:
                return self._format % self.value
        else:
            return str(self.value)

    def __lt__(self, other):
        if self.sortMode == 'index' and hasattr(other, 'index'):
            return self.index < other.index
        if self.sortMode == 'value' and hasattr(other, 'value'):
            return self.value < other.value
        else:
            return self.text() < other.text()
