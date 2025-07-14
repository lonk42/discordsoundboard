#!/usr/bin/env python

import sys
import os
import vlc
import yaml
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QSlider, QComboBox, QGroupBox, QListWidget, QInputDialog
)
from PyQt5.QtCore import Qt, QTimer

CONFIG_FILE = "config.yaml"

class DiscordSoundBoard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Discord Sound Board")
        self.setGeometry(200, 200, 900, 500)

        self.instance = vlc.Instance()
        self.player_main = self.instance.media_player_new()
        self.player_secondary = self.instance.media_player_new()
        self.media = None
        self.current_file = None
        self.start_pos = None
        self.end_pos = None

        self.config = self.load_config()

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.file_label = QLabel("No audio loaded")
        self.file_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.file_label)

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setFixedHeight(16)
        self.seek_slider.setStyleSheet("QSlider::groove:horizontal { height: 8px; background: #ddd; } QSlider::handle:horizontal { width: 12px; }")
        self.seek_slider.sliderReleased.connect(self.seek_audio)
        layout.addWidget(self.seek_slider)

        # Audio Controls
        audio_controls = QHBoxLayout()
        self.play_pause_button = QPushButton("Play")
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        audio_controls.addWidget(self.play_pause_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_audio)
        audio_controls.addWidget(self.stop_button)
        
        layout.addLayout(audio_controls)

        # Middle Content
        middle = QHBoxLayout()

        # Saved Presets
        self.preset_list = QVBoxLayout()
        self.preset_buttons = []
        middle.addLayout(self.preset_list, 1)

        # Preset Controls
        preset_controls_layout = QVBoxLayout()
        preset_controls_row1_layout = QHBoxLayout()
        self.load_button = QPushButton("Open File")
        self.load_button.clicked.connect(self.load_file_dialog)
        preset_controls_row1_layout.addWidget(self.load_button)

        self.save_preset_button = QPushButton("Save Preset")
        self.save_preset_button.clicked.connect(self.save_preset)
        preset_controls_row1_layout.addWidget(self.save_preset_button)
        preset_controls_layout.addLayout(preset_controls_row1_layout)

        preset_controls_row2_layout = QHBoxLayout()
        self.set_start_button = QPushButton("Set Start")
        self.set_start_button.clicked.connect(self.set_start)
        preset_controls_row2_layout.addWidget(self.set_start_button)

        self.set_end_button = QPushButton("Set End")
        self.set_end_button.clicked.connect(self.set_end)
        preset_controls_row2_layout.addWidget(self.set_end_button)
        preset_controls_layout.addLayout(preset_controls_row2_layout)

        middle.addLayout(preset_controls_layout)

        layout.addLayout(middle)

        # Bottom
        bottom_layout = QHBoxLayout()

        # Outputs
        outputs = QHBoxLayout()
        output_row1 = QHBoxLayout()
        output_row1.addWidget(QLabel("Primary:"))
        self.output_combo_1 = QComboBox()
        output_row1.addWidget(self.output_combo_1)
        outputs.addLayout(output_row1)

        self.volume_slider_1 = QSlider(Qt.Horizontal)
        self.volume_slider_1.setRange(0, 100)
        self.volume_slider_1.valueChanged.connect(self.update_volume)
        outputs.addWidget(self.volume_slider_1)

        output_row2 = QHBoxLayout()
        output_row2.addWidget(QLabel("Secondary:"))
        self.output_combo_2 = QComboBox()
        output_row2.addWidget(self.output_combo_2)
        outputs.addLayout(output_row2)

        self.volume_slider_2 = QSlider(Qt.Horizontal)
        self.volume_slider_2.setRange(0, 100)
        self.volume_slider_2.valueChanged.connect(self.update_volume)
        outputs.addWidget(self.volume_slider_2)

        bottom_layout.addLayout(outputs, 2)
        layout.addLayout(bottom_layout)

        self.timer = QTimer()
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.update_seek_slider)

        self.populate_audio_outputs()
        self.restore_settings()
        self.render_presets()

    def populate_audio_outputs(self):
        self.output_combo_1.clear()
        self.output_combo_2.clear()
        devices = []
        outputs = self.player_main.audio_output_device_enum()
        if outputs:
            current = outputs
            while current:
                name = current.contents.device
                desc = current.contents.description
                if name and desc:
                    devices.append((name.decode(), desc.decode()))
                current = current.contents.next
        for name, desc in devices:
            self.output_combo_1.addItem(name, name)
            self.output_combo_2.addItem(name, name)

    def set_outputs(self):
        d1 = self.output_combo_1.currentData()
        d2 = self.output_combo_2.currentData()
        if d1:
            self.player_main.audio_output_device_set(None, d1)
        if d2:
            self.player_secondary.audio_output_device_set(None, d2)
        self.update_volume()
        self.save_config()

    def update_volume(self):
        self.player_main.audio_set_volume(self.volume_slider_1.value())
        self.player_secondary.audio_set_volume(self.volume_slider_2.value())
        self.save_config()

    def load_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Audio", "", "Audio Files (*.mp3 *.wav)")
        if path:
            self.load_file(path)

    def load_file(self, path):
        self.current_file = path
        self.file_label.setText(os.path.basename(path))
        self.media = self.instance.media_new(path)
        self.player_main.set_media(self.media)
        self.player_secondary.set_media(self.instance.media_new(path))

    def toggle_play_pause(self):
        if self.player_main.is_playing():
            self.player_main.pause()
            self.player_secondary.pause()
            self.play_pause_button.setText("Play")
        else:
            self.set_outputs()
            self.update_volume()
            self.player_main.play()
            self.player_secondary.play()
            self.timer.start()
            self.play_pause_button.setText("Pause")

    def stop_audio(self):
        self.player_main.stop()
        self.player_secondary.stop()
        self.timer.stop()
        self.play_pause_button.setText("Play")

    def update_seek_slider(self):
        length = self.player_main.get_length()
        pos = self.player_main.get_time()
        if length > 0:
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(int((pos / length) * 1000))
            self.seek_slider.blockSignals(False)
            if self.end_pos and pos >= self.end_pos:
                self.stop_audio()

    def seek_audio(self):
        length = self.player_main.get_length()
        if length > 0:
            t = int((self.seek_slider.value() / 1000) * length)
            self.player_main.set_time(t)
            self.player_secondary.set_time(t)

    def set_start(self):
        self.start_pos = self.player_main.get_time()
        self.set_start_button.setText(f"Start: {self.start_pos // 1000}s")

    def set_end(self):
        self.end_pos = self.player_main.get_time()
        self.set_end_button.setText(f"End: {self.end_pos // 1000}s")

    def save_preset(self):
        if not self.current_file or self.start_pos is None or self.end_pos is None:
            return
        name, ok = QInputDialog.getText(self, "Preset Name", "Enter preset name:")
        if ok and name:
            self.config.setdefault("presets", {})[name] = {
                "file": self.current_file,
                "start": self.start_pos,
                "end": self.end_pos
            }
            self.save_config()
            self.render_presets()

    def render_presets(self):
        for i in reversed(range(self.preset_list.count())):
            self.preset_list.itemAt(i).widget().setParent(None)
        for name, data in self.config.get("presets", {}).items():
            button = QPushButton(name)
            button.clicked.connect(lambda _, d=data: self.play_preset(d))
            self.preset_list.addWidget(button)

    def play_preset(self, preset):
        self.load_file(preset["file"])
        self.start_pos = preset["start"]
        self.end_pos = preset["end"]
        self.player_main.play()
        self.player_secondary.play()
        self.player_main.set_time(self.start_pos)
        self.player_secondary.set_time(self.start_pos)
        self.timer.start()
        self.play_pause_button.setText("Pause")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return yaml.safe_load(f) or {}
        return {}

    def save_config(self):
        self.config["settings"] = {
            "output_device_1": self.output_combo_1.currentData(),
            "output_device_2": self.output_combo_2.currentData(),
            "volume_1": self.volume_slider_1.value(),
            "volume_2": self.volume_slider_2.value()
        }
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(self.config, f)

    def restore_settings(self):
        s = self.config.get("settings", {})
        for i in range(self.output_combo_1.count()):
            if self.output_combo_1.itemData(i) == s.get("output_device_1"):
                self.output_combo_1.setCurrentIndex(i)
        for i in range(self.output_combo_2.count()):
            if self.output_combo_2.itemData(i) == s.get("output_device_2"):
                self.output_combo_2.setCurrentIndex(i)
        self.volume_slider_1.setValue(s.get("volume_1", 75))
        self.volume_slider_2.setValue(s.get("volume_2", 75))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DiscordSoundBoard()
    window.show()
    sys.exit(app.exec_())