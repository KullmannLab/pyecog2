# PyQt5 Video player
#!/usr/bin/env python
from PyQt5.QtCore import QDir, Qt, QUrl, pyqtSignal
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel,
        QPushButton, QSizePolicy, QSlider, QStyle, QVBoxLayout, QWidget)
from PyQt5.QtWidgets import QMainWindow,QWidget, QPushButton, QAction
from PyQt5.QtGui import QIcon
import sys
import time

class VideoWindow(QWidget):
    sigTimeChanged = pyqtSignal(object)

    def __init__(self, project=None, parent=None):
        super(VideoWindow, self).__init__(parent)
        self.project = project
        self.setWindowTitle("Video")
        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.last_position = 0

        videoWidget = QVideoWidget()
        self.videoWidget = videoWidget
        self.playButton = QPushButton()
        self.playButton.setEnabled(False)
        self.playButton.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.playButton.clicked.connect(self.play)

        self.positionSlider = QSlider(Qt.Horizontal)
        self.positionSlider.setRange(0, 0)
        self.positionSlider.sliderMoved.connect(self.setPosition)

        self.errorLabel = QLabel()
        self.errorLabel.setSizePolicy(QSizePolicy.Preferred,
                QSizePolicy.Maximum)

        # Create layouts to place inside widget
        controlLayout = QHBoxLayout()
        controlLayout.setContentsMargins(0, 0, 0, 0)
        controlLayout.addWidget(self.playButton)
        controlLayout.addWidget(self.positionSlider)

        layout = QVBoxLayout()
        layout.addWidget(videoWidget)
        layout.addLayout(controlLayout)
        # layout.addWidget(self.errorLabel)   # Hide error Label

        # Set widget to contain window contents
        self.setLayout(layout)

        self.mediaPlayer.setVideoOutput(videoWidget)
        self.mediaPlayer.stateChanged.connect(self.mediaStateChanged)
        self.mediaPlayer.positionChanged.connect(self.positionChanged)
        self.mediaPlayer.durationChanged.connect(self.durationChanged)
        self.mediaPlayer.error.connect(self.handleError)

        if self.project.current_animal.video_files:
            self.current_file = self.project.current_animal.video_files[0]
            self.current_time_range = [self.project.current_animal.video_init_time[0],
                                   self.project.current_animal.video_init_time[0] + self.project.current_animal.video_duration[0]]
            self.mediaPlayer.setMedia(QMediaContent(QUrl.fromLocalFile(self.current_file)))
            self.playButton.setEnabled(True)
        else:
            self.current_file = ''
            self.current_time_range = [0,0]


    def openFile(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Open Movie",
                QDir.homePath())

        if fileName != '':
            self.mediaPlayer.setMedia(
                    QMediaContent(QUrl.fromLocalFile(fileName)))
            self.playButton.setEnabled(True)

    def exitCall(self):
        sys.exit(app.exec_())

    def play(self):
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.mediaPlayer.pause()
        else:
            self.mediaPlayer.play()

    def mediaStateChanged(self, state):
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.playButton.setIcon(
                    self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.playButton.setIcon(
                    self.style().standardIcon(QStyle.SP_MediaPlay))

    def positionChanged(self, position):
        self.last_position = position
        if self.current_time_range[0] != 0 and position != 0:  # avoid time changes when switching files
            self.positionSlider.setValue(position)
            self.sigTimeChanged.emit(position/1000 + self.current_time_range[0])

    def durationChanged(self, duration):
        self.positionSlider.setRange(0, duration)

    def setPosition(self, position):
        self.mediaPlayer.setPosition(position) #  milliseconds since the beginning of the media

    def setGlobalPosition(self, pos):
        # open the right media
        if self.current_time_range[0] <= pos <= self.current_time_range[1]:
            position = (pos-self.current_time_range[0])*1000
            if self.mediaPlayer.state() == QMediaPlayer.PlayingState and abs(position-self.last_position)<200:
                # skip position setting to ensure smooth video plaback
                return
            # go to correct relative position
            self.mediaPlayer.setPosition(position)  # UNIX time
            return
        else:
            for i, file in enumerate(self.project.current_animal.video_files):
                arange = [self.project.current_animal.video_init_time[i],
                          self.project.current_animal.video_init_time[i] + self.project.current_animal.video_duration[i]]
                if (arange[0] <= pos <= arange[1]):
                    print('Changing video file: ', file)
                    self.current_file = file
                    self.current_time_range = arange
                    self.mediaPlayer.setMedia(QMediaContent(QUrl.fromLocalFile(file)))
                    self.playButton.setEnabled(True)
                    position = (pos-self.current_time_range[0])*1000
                    self.mediaPlayer.setPosition(position)
                    # Hack to make the player display the video instead of an black frame
                    self.play()
                    time.sleep(.04)
                    self.play()
                    return
        print('no video file found for current position')
        self.mediaPlayer.setMedia(QMediaContent())
        self.current_file = ''
        self.current_time_range = [0, 0]
        self.playButton.setEnabled(False)
        self.positionSlider.setRange(0, 0)
        self.positionSlider.setValue(0)


    def handleError(self):
        self.playButton.setEnabled(False)
        self.errorLabel.setText("Error: " + self.mediaPlayer.errorString())
        print("Video - Error: " + self.mediaPlayer.errorString())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    player = VideoWindow()
    player.resize(640, 480)
    player.show()
    sys.exit(app.exec_())