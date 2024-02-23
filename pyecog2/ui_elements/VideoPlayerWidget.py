# PyQt5 Video player
import os
os.environ['QT_MULTIMEDIA_PREFERRED_PLUGINS'] = 'windowsmediafoundation'
from PySide6.QtCore import QDir, Qt, QUrl, Signal, QTimer
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel, QInputDialog,
        QPushButton, QSizePolicy, QSlider, QStyle, QVBoxLayout, QWidget)
from PySide6.QtWidgets import QMainWindow,QWidget, QPushButton
from PySide6.QtGui import QIcon
import sys
import time
import numpy as np

import logging
logger = logging.getLogger(__name__)

import pkg_resources
clock_icon_file = pkg_resources.resource_filename('pyecog2', 'icons/wall-clock.png')
play_icon_file = pkg_resources.resource_filename('pyecog2', 'icons/play.png')
pause_icon_file = pkg_resources.resource_filename('pyecog2', 'icons/pause.png')

class VideoWindow(QWidget):
    sigTimeChanged = Signal(object)

    def __init__(self, main_model=None, parent=None):
        super(VideoWindow, self).__init__(parent)
        self.main_model = main_model
        self.setWindowTitle("Video")
        self.mediaPlayer = QMediaPlayer() #None, QMediaPlayer.VideoSurface)
        self.last_position = 0
        self.position_on_new_file = 0
        self.duration = -1
        self.waiting_for_file = False
        self.media_state_before_file_transition = self.mediaPlayer.playbackState()
        self.video_time_offset = 0.0

        self.play_icon = QIcon(play_icon_file)
        self.clock_icon = QIcon(clock_icon_file)
        self.pause_icon = QIcon(pause_icon_file)

        videoWidget = QVideoWidget()
        self.videoWidget = videoWidget
        self.playButton = QPushButton()
        self.playButton.setEnabled(False)
        self.playButton.setIcon(self.play_icon)
        self.playButton.clicked.connect(self.play)

        self.timeOffsetButton = QPushButton()
        self.timeOffsetButton.setIcon(self.clock_icon)
        self.timeOffsetButton.clicked.connect(self.setTimeOffset)

        self.positionSlider = QSlider(Qt.Horizontal)
        self.positionSlider.setRange(0, 0)
        self.positionSlider.sliderMoved.connect(self.setPosition)

        self.errorLabel = QLabel()
        self.errorLabel.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Maximum)

        # Create layouts to place inside widget
        controlLayout = QHBoxLayout()
        controlLayout.setContentsMargins(0, 0, 0, 0)
        controlLayout.addWidget(self.timeOffsetButton)
        controlLayout.addWidget(self.playButton)
        controlLayout.addWidget(self.positionSlider)

        layout = QVBoxLayout()
        layout.addWidget(videoWidget)
        layout.addLayout(controlLayout)
        layout.addWidget(self.errorLabel)   # Hide error Label

        # Set widget to contain window contents
        self.setLayout(layout)

        self.mediaPlayer.setVideoOutput(videoWidget)
        self.mediaPlayer.playbackStateChanged.connect(self.mediaStateChanged)
        self.mediaPlayer.positionChanged.connect(self.positionChanged)
        self.mediaPlayer.durationChanged.connect(self.durationChanged)
        self.mediaPlayer.mediaStatusChanged.connect(self.mediaStatusChanged)
        self.mediaPlayer.errorOccurred.connect(self.handleError)
        # self.mediaPlayer.setNotifyInterval(40) # 25 fps - This was used with PySide2 - checking if still needed with Pyside6

        self.timer = QTimer()
        self.timer.timeout.connect(self.positionChanged(self.mediaPlayer.position()))

        # Connect main model time changes to videa seek
        if self.main_model is not None:
            self.sigTimeChanged.connect(self.main_model.set_time_position)
            self.main_model.sigTimeChanged.connect(self.setGlobalPosition)

        if self.main_model is None:
            self.current_time_range = [0,0]
            self.current_file = ''
            # self.mediaPlayer.setSource(QMediaContent(QUrl.fromLocalFile(self.current_file)))
            # self.playButton.setEnabled(True)
            # self.mediaPlayer.play()
        elif self.main_model.project.current_animal.video_files:
            self.current_file = self.main_model.project.current_animal.video_files[0]
            self.current_time_range = [self.main_model.project.current_animal.video_init_time[0],
                                   self.main_model.project.current_animal.video_init_time[0] + self.main_model.project.current_animal.video_duration[0]]
            self.mediaPlayer.setSource(QUrl.fromLocalFile(self.current_file))
            self.playButton.setEnabled(True)
        else:
            self.current_file = ''
            self.current_time_range = [0,0]

    def setTimeOffset(self):
        offset, okpressed = QInputDialog.getDouble(self,'Video time offset',
                                                   'Offset video time position (seconds)',
                                                   value = self.video_time_offset)
        if okpressed:
            self.video_time_offset = offset
            current_position = self.current_time_range[0] + self.last_position/1000
            self.setGlobalPosition(0)
            self.setGlobalPosition(current_position)


    def openFile(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Open Movie",
                QDir.homePath())

        if fileName != '':
            self.mediaPlayer.setSource(QUrl.fromLocalFile(fileName))
            self.playButton.setEnabled(True)

    def exitCall(self):
        sys.exit(app.exec())

    def play(self):
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlayingState:
            self.mediaPlayer.pause()
            self.timer.stop()
            logger.info("Video player: pausing")
        else:
            self.last_position -= 1  # take one millisecond to last position so that first position update is not skipped
            self.mediaPlayer.play()
            self.timer.start(40) # 40 ms inter frame interval
            logger.info("Video player: playing")

    def mediaStateChanged(self, state):
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlayingState:
            self.playButton.setIcon(self.pause_icon)
        else:
            self.playButton.setIcon(self.play_icon)

    def positionChanged(self, position):
        # Connected to video player
        # print('positionChanged',position,self.last_position,self.waiting_for_file,self.duration,self.current_time_range)
        # if self.duration == -1:
        #     print('positionChanged: no file - duration ==-1')
        #     return
        # if self.waiting_for_file:
        #     print('positionChanged: Waiting to load file')
        #     return
        # if position == 0:
        #     print('positionChanged: avoiding setting positions to 0')
        #     return
        if position == 0 or self.waiting_for_file or self.duration == -1 or position == self.last_position:
            # avoid position changes on file transitions or repeated signals on same position
            logger.info(f'Video player skiping position update {(position == 0 , self.waiting_for_file , self.duration == -1 , position == self.last_position)}')
            return
        if position < self.duration-40:  # avoid time changes when switching files
            self.last_position = position
            self.positionSlider.setValue(position)
            self.sigTimeChanged.emit(position/1000 + self.current_time_range[0])
        else: # position is at the end of file - try to switch to next file
            pos = self.current_time_range[1] + .04
            logger.info(f'Trying to jump to next file {self.current_time_range[1], self.duration, pos}')
            self.setGlobalPosition(pos)

    def durationChanged(self, duration):
        # print('duration changed',duration)
        self.duration = duration
        self.positionSlider.setRange(0, duration)
        self.mediaPlayer.setPosition(self.position_on_new_file) # if duration changes avoid the position going back to 0

    def setPosition(self, position):
        # connected to slider
        # print('setPosition',position)
        self.mediaPlayer.setPosition(position) #  milliseconds since the beginning of the media

    def setGlobalPosition(self, pos):
        # Connected to project main model sigTimeChanged
        # open the right media
        # print('VideoPlayer setGlobalPosition')
        if self.current_time_range[0] <= pos <= self.current_time_range[1]: # correct file opened
            position = int((pos-self.current_time_range[0])*1000)
            if self.mediaPlayer.playbackState() == QMediaPlayer.PlayingState and abs(position-self.last_position)<200:
                # skip position setting by signal of main model to ensure smooth video plaback
                return
            # go to correct relative position
            self.mediaPlayer.setPosition(position)  # UNIX time
            return
        else:
            logger.info(f'searching for video file {self.main_model.project.current_animal.id, len(self.main_model.project.current_animal.video_files)}')
            for i, file in enumerate(self.main_model.project.current_animal.video_files): # search for file to open
                arange = [self.main_model.project.current_animal.video_init_time[i] + self.video_time_offset,
                          self.main_model.project.current_animal.video_init_time[i] + self.main_model.project.current_animal.video_duration[i]
                          + self.video_time_offset]
                # print((arange[0], pos, arange[1]),(arange[0] <= pos <= arange[1]))
                if (arange[0] <= pos <= arange[1]):
                    logger.info(f'Changing video file: {file}')
                    self.current_file = file
                    self.errorLabel.setText("File: " + self.current_file)
                    self.current_time_range = arange
                    self.waiting_for_file = True
                    self.media_state_before_file_transition = self.mediaPlayer.playbackState()
                    self.mediaPlayer.stop()
                    position = (pos-self.current_time_range[0])*1000
                    self.position_on_new_file = int(position)
                    # print('Changing position_on_new_file: ', self.position_on_new_file,pos)
                    self.mediaPlayer.setSource(QUrl.fromLocalFile(file))
                    self.playButton.setEnabled(True)
                    # self.duration = (arange[1]-arange[0])*1000
                    return
        logger.info(f'No video file found for current position {pos}')
        self.errorLabel.setText('No video file found for current position ' + str(pos))
        self.mediaPlayer.stop()
        self.mediaPlayer.setSource(QUrl())
        self.current_file = ''
        self.current_time_range = [0, 0]
        # self.duration = 0
        self.playButton.setEnabled(False)
        self.positionSlider.setRange(0, 0)
        self.positionSlider.setValue(0)

    def mediaStatusChanged(self,status):
        if self.waiting_for_file:
            if self.mediaPlayer.mediaStatus() == QMediaPlayer.LoadedMedia:
                self.waiting_for_file = False
                # print('finished loading file')
                # self.mediaPlayer.stop()
                self.duration = self.mediaPlayer.duration()
                self.mediaPlayer.setPosition(self.position_on_new_file)
                self.mediaPlayer.play()
                time.sleep(.05)
                # if not self.media_state_before_file_transition == QMediaPlayer.PlayingState:
                #     self.mediaPlayer.pause()
                self.mediaPlayer.pause()
                if self.media_state_before_file_transition == QMediaPlayer.PlayingState:
                    logger.info("resuming play state")
                    self.mediaPlayer.play()
                # print('finished setting position on new file')


    def handleError(self):
        # self.playButton.setEnabled(False)
        self.errorLabel.setText("Error: " + self.mediaPlayer.errorString())
        logger.info("Video - Error: " + self.mediaPlayer.errorString())


if __name__ == '__main__':
    app = QApplication(sys.argv)
    player = VideoWindow()
    player.resize(640, 480)
    player.show()
    sys.exit(app.exec())