#!/usr/bin/env python

import sys
import os
import json
import numpy as np
import sounddevice as sd
import vlc

from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QLabel, QComboBox, QSlider, QGroupBox, QListWidget, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
import pyqtgraph as pg


REMEMBERED_FILE = "remembered_files.json"


class AudioCapture(QThread):
    data_ready = pyqtSignal(np.ndarray)

    def __init__(self, device=None):
        super().__init__()
        self.stream = None
        self.running = False
        self.device = device

    def run(self):
        self.running = True

        def callback(indata, frames, time, status):
            if status:
                print(status)
            if self.running:
                data = indata[:, 0]
                self.data_ready.emit(data.copy())

        self.stream = sd.InputStream(
            channels=1,
            samplerate=44100,
            callback=callback,
            blocksize=1024,
            device=self.device
        )
        self.stream.start()

    def stop(self):
        self.running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()


class AudioPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt5 Audio Player with Real Visualizer")
        self.setGeometry(200, 200, 800, 600)

        # VLC
        self.instance = vlc.Instance()
        self.player_main = self.instance.media_player_new()
        self.player_secondary = self.instance.media_player_new()
        self.media = None
        self.output_device_1 = None
        self.output_device_2 = None

        # Layouts
        main_layout = QVBoxLayout()

        # Top label
        self.file_label = QLabel("No file loaded")
        self.file_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.file_label)

        # Visualizer
        self.plot = pg.PlotWidget()
        self.curve = self.plot.plot(pen='aqua')
        self.plot.setYRange(-1, 1)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.hideAxis('bottom')
        self.plot.hideAxis('left')
        main_layout.addWidget(self.plot)

        # Seek slider
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderReleased.connect(self.seek_audio)
        main_layout.addWidget(self.seek_slider)

        # Controls below waveform
        control_layout = QHBoxLayout()

        self.open_button = QPushButton("📂")
        self.open_button.clicked.connect(self.open_file)
        control_layout.addWidget(self.open_button)

        self.remember_button = QPushButton("💾")
        self.remember_button.clicked.connect(self.save_remembered_file)
        control_layout.addWidget(self.remember_button)

        self.play_button = QPushButton("▶️")
        self.play_button.clicked.connect(self.play_audio)
        control_layout.addWidget(self.play_button)

        self.pause_button = QPushButton("⏸️")
        self.pause_button.clicked.connect(self.pause_audio)
        control_layout.addWidget(self.pause_button)

        self.stop_button = QPushButton("⏹️")
        self.stop_button.clicked.connect(self.stop_audio)
        control_layout.addWidget(self.stop_button)

        main_layout.addLayout(control_layout)

        # Output/Volume
        device_layout = QHBoxLayout()
        output_group = QGroupBox("Audio Outputs")
        output_layout = QVBoxLayout()

        self.output_combo_1 = QComboBox()
        self.output_combo_2 = QComboBox()

        self.output_combo_1.currentIndexChanged.connect(self.set_outputs)
        self.output_combo_2.currentIndexChanged.connect(self.set_outputs)

        self.volume_slider_1 = QSlider(Qt.Horizontal)
        self.volume_slider_2 = QSlider(Qt.Horizontal)
        self.volume_slider_1.setRange(0, 100)
        self.volume_slider_2.setRange(0, 100)
        self.volume_slider_1.setValue(75)
        self.volume_slider_2.setValue(75)
        self.volume_slider_1.valueChanged.connect(self.update_volume)
        self.volume_slider_2.valueChanged.connect(self.update_volume)

        output_layout.addWidget(QLabel("Primary Output"))
        output_layout.addWidget(self.output_combo_1)
        output_layout.addWidget(QLabel("Volume"))
        output_layout.addWidget(self.volume_slider_1)

        output_layout.addWidget(QLabel("Secondary Output"))
        output_layout.addWidget(self.output_combo_2)
        output_layout.addWidget(QLabel("Volume"))
        output_layout.addWidget(self.volume_slider_2)

        output_group.setLayout(output_layout)
        device_layout.addWidget(output_group)

        # Remembered files
        self.remembered_list = QListWidget()
        self.remembered_list.itemClicked.connect(self.load_remembered_file)
        self.load_remembered_files()
        device_layout.addWidget(self.remembered_list)

        main_layout.addLayout(device_layout)
        self.setLayout(main_layout)

        # Output setup
        self.populate_audio_outputs()

        # Timer
        self.timer = QTimer()
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_seek_slider)

        # Waveform capture
        self.capture = AudioCapture()
        self.capture.data_ready.connect(self.update_visualizer)

    def populate_audio_outputs(self):
        self.output_combo_1.clear()
        self.output_combo_2.clear()
        devices = []
        outputs = self.player_main.audio_output_device_enum()
        if outputs:
            current = outputs
            while current:
                name = current.contents.device
                description = current.contents.description
                if name and description:
                    decoded = (name.decode(), description.decode())
                    devices.append(decoded)
                current = current.contents.next
        for name, desc in devices:
            label = f"{desc} ({name})"
            self.output_combo_1.addItem(label, name)
            self.output_combo_2.addItem(label, name)

    def set_outputs(self):
        self.output_device_1 = self.output_combo_1.currentData()
        self.output_device_2 = self.output_combo_2.currentData()
        if self.output_device_1:
            self.player_main.audio_output_device_set(None, self.output_device_1)
        if self.output_device_2:
            self.player_secondary.audio_output_device_set(None, self.output_device_2)
        self.update_volume()

    def update_volume(self):
        v1 = self.volume_slider_1.value()
        v2 = self.volume_slider_2.value()
        self.player_main.audio_set_volume(v1)
        self.player_secondary.audio_set_volume(v2)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Audio", "", "Audio Files (*.mp3 *.wav)")
        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path):
        self.file_label.setText(os.path.basename(file_path))
        self.media = self.instance.media_new(file_path)
        self.player_main.set_media(self.media)
        self.media_clone = self.instance.media_new(file_path)
        self.player_secondary.set_media(self.media_clone)

    def play_audio(self):
        self.set_outputs()
        self.update_volume()
        self.player_main.play()
        self.player_secondary.play()
        self.timer.start()
        if not self.capture.isRunning():
            self.capture.start()

    def pause_audio(self):
        self.player_main.pause()
        self.player_secondary.pause()

    def stop_audio(self):
        self.player_main.stop()
        self.player_secondary.stop()
        self.timer.stop()
        self.capture.stop()
        self.curve.setData(np.zeros(1024))

    def update_visualizer(self, data):
        self.curve.setData(data)

    def update_seek_slider(self):
        length = self.player_main.get_length()
        if length > 0:
            pos = self.player_main.get_time()
            value = int((pos / length) * 1000)
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(value)
            self.seek_slider.blockSignals(False)

    def seek_audio(self):
        length = self.player_main.get_length()
        if length > 0:
            percent = self.seek_slider.value() / 1000
            new_time = int(length * percent)
            self.player_main.set_time(new_time)
            self.player_secondary.set_time(new_time)

    def save_remembered_file(self):
        if not self.media:
            return
        mrl = self.media.get_mrl().replace("file://", "")
        if not os.path.isfile(mrl):
            return
        remembered = self.get_remembered()
        if mrl not in remembered:
            remembered.append(mrl)
            with open(REMEMBERED_FILE, "w") as f:
                json.dump(remembered, f)
            self.remembered_list.addItem(mrl)

    def get_remembered(self):
        if os.path.exists(REMEMBERED_FILE):
            with open(REMEMBERED_FILE, "r") as f:
                return json.load(f)
        return []

    def load_remembered_files(self):
        for f in self.get_remembered():
            self.remembered_list.addItem(f)

    def load_remembered_file(self, item):
        self.load_file(item.text())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudioPlayer()
    window.show()
    sys.exit(app.exec_())
