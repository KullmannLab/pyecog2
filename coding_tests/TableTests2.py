from annotation_table_widget import TableWidget
from PyQt5 import QtCore, QtGui
import numpy as np
from annotations_module import AnnotationElement, AnnotationPage

app = QtGui.QApplication([])

w = TableWidget(editable=True)
w.show()
w.resize(500, 500)
w.setWindowTitle('pyqtgraph example: TableWidget')
data = np.array([
    (1, 1.6, 'x'),
    (3, 5.4, 'y'),
    (8, 12.5, 'z'),
    (443, 1e-12, 'w'),
], dtype=[('Column 1', int), ('Column 2', float), ('Column 3', object)])

annotations = AnnotationPage(list=[AnnotationElement(label='seizure', start=1, end=10),
                                                           AnnotationElement(label='seizure', start=14, end=22),
                                                           AnnotationElement(label='spike', start=23, end=25),
                                                           AnnotationElement(label='artefact', start=26, end=26.5)])


data = [annotation.element_dict for annotation in annotations.annotations_list]
print(data)
w.setData(data)
for i in range(w.rowCount()):
    # make bkgd color a bit lighter than normal color
    alpha = 50/255
    color = [value*alpha + 255*(1-alpha) for value in annotations.label_color_dict[w.item(i, 0).text()]]
    for k in range(w.columnCount()):
        w.item(i, k).setBackground(QtGui.QBrush(QtGui.QColor(*color)))



## Start Qt event loop unless running in interactive mode or using pyside.
if __name__ == '__main__':
    import sys

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
