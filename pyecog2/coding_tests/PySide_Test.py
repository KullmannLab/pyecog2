
from PySide6 import QtGui, QtWidgets

# Get entrypoint through which we control underlying Qt framework
app = QtWidgets.QApplication([])

# Qt automatically creates top level application window if you
# instruct it to show() any GUI element
window = QtWidgets.QLabel('Window from label')
window.show()

# IMPORTANT: `window` variable now contains a reference to a top
# level window, and if you lose the variable, the window will be
# destroyed by PySide automatically, e.g. this won't show:
#
#   QLabel('New Window').show()
#
# This is true for other PySide6 objects, so be careful.

# Start Qt/PySide6 application. If we don't show any windows, the
# app would just loop at this point without the means to exit
app.exec()