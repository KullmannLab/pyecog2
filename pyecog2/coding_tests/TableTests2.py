from pyecog2.annotation_table_widget import AnnotationTableWidget
from PySide6 import QtCore, QtWidgets
import numpy as np
from pyecog2.annotations_module import AnnotationElement, AnnotationPage

app = QtWidgets.QApplication([])

data = np.array([
    (1, 1.6, 'x'),
    (3, 5.4, 'y'),
    (8, 12.5, 'z'),
    (443, 1e-12, 'w'),
], dtype=[('Column 1', int), ('Column 2', float), ('Column 3', object)])

annotations = AnnotationPage(list=[AnnotationElement(label='seizure', start=1, end=10),
                                                           AnnotationElement(label='seizure', start=14, end=22),
                                                           AnnotationElement(label='spike', start=23, end=25),
                                                           AnnotationElement(label='artefact', start=26, end=26.5)]*10)

print(annotations)
w = AnnotationTableWidget(annotations, editable=True)
w.show()
w.resize(500, 500)

## Start Qt event loop unless running in interactive mode or using pyside.
if __name__ == '__main__':
    import sys

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtWidgets.QApplication.instance().exec()
