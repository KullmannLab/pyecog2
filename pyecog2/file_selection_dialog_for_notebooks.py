from PyQt5.QtWidgets import QFileDialog, QApplication

'''
You need to find what you wrote before in these things?
'''
def get_app():
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    return app

def select_path(folders_only=True):
    app = get_app()
    dialog = QFileDialog()
    dialog.setWindowTitle('Select a path')
    if folders_only:
        dialog.setFileMode(QFileDialog.DirectoryOnly)
    dialog.setOption(QFileDialog.DontUseNativeDialog, True)
    dialog.setOption(QFileDialog.ShowDirsOnly, False);
    if dialog.exec():
        path = dialog.selectedFiles()[0]
    app.exec()
    return path

select_path()
