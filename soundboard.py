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
        self.player_primary = self.instance.media_player_new()
        self.player_primary_mute = False
        self.player_secondary = self.instance.media_player_new()
        self.player_secondary_mute = False
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
        self.seek_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 8px;
                background: #ccc;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #444;
                border: 1px solid #888;
                width: 14px;
                margin: -6px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #4da6ff;
                border-radius: 4px;
            }
        """)
        self.seek_slider.sliderPressed.connect(self.pause_updates)
        self.seek_slider.sliderReleased.connect(self.seek_audio)
        layout.addWidget(self.seek_slider)

        audio_controls = QHBoxLayout()
        self.play_pause_button = QPushButton("Play")
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        audio_controls.addWidget(self.play_pause_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_audio)
        audio_controls.addWidget(self.stop_button)

        layout.addLayout(audio_controls)

        middle = QHBoxLayout()
        self.preset_list = QVBoxLayout()
        self.preset_buttons = []
        middle.addLayout(self.preset_list, 1)

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

      
        # Bottom layout setup
        bottom_layout = QHBoxLayout()

        # Primary output box
        primary_box = QVBoxLayout()
        primary_row = QHBoxLayout()
        self.primary_label = QLabel("Primary:")
        self.primary_label.setStyleSheet("color: green;")
        primary_row.addWidget(self.primary_label)

        self.mute_button_primary = QPushButton("Mute")
        self.mute_button_primary.setCheckable(True)
        self.mute_button_primary.toggled.connect(self.toggle_mute_primary)
        primary_row.addWidget(self.mute_button_primary)
        self.player_primary.audio_set_mute(self.player_primary_mute)

        self.output_combo_primary = QComboBox()
        primary_row.addWidget(self.output_combo_primary)
        primary_box.addLayout(primary_row)

        self.volume_slider_primary = QSlider(Qt.Horizontal)
        self.volume_slider_primary.setRange(0, 100)
        self.volume_slider_primary.valueChanged.connect(self.update_outputs)
        primary_box.addWidget(self.volume_slider_primary)

        # Secondary output box
        secondary_box = QVBoxLayout()
        secondary_row = QHBoxLayout()
        self.secondary_label = QLabel("Secondary:")
        self.secondary_label.setStyleSheet("color: green;")
        secondary_row.addWidget(self.secondary_label)

        self.mute_button_secondary = QPushButton("Mute")
        self.mute_button_secondary.setCheckable(True)
        self.mute_button_secondary.toggled.connect(self.toggle_mute_secondary)
        secondary_row.addWidget(self.mute_button_secondary)
        self.player_secondary.audio_set_mute(self.player_secondary_mute)

        self.output_combo_secondary = QComboBox()
        secondary_row.addWidget(self.output_combo_secondary)
        secondary_box.addLayout(secondary_row)

        self.volume_slider_secondary = QSlider(Qt.Horizontal)
        self.volume_slider_secondary.setRange(0, 100)
        self.volume_slider_secondary.valueChanged.connect(self.update_outputs)
        secondary_box.addWidget(self.volume_slider_secondary)

        bottom_layout.addLayout(primary_box)
        bottom_layout.addLayout(secondary_box)
        layout.addLayout(bottom_layout)

        self.timer = QTimer()
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.update_seek_slider)

        self.populate_audio_output_combos()
        self.restore_settings()

        # We need to call these after retoring settings on intialize
        self.output_combo_primary.currentIndexChanged.connect(self.update_outputs)
        self.output_combo_secondary.currentIndexChanged.connect(self.update_outputs)
        self.mute_button_secondary.setChecked(True)

        self.render_presets()

    def pause_updates(self):
        self.timer.stop()

    def toggle_mute_primary(self, checked):
        self.player_primary_mute = checked
        self.update_outputs()

    def toggle_mute_secondary(self, checked):
        self.player_secondary_mute = checked
        self.update_outputs()

    def populate_audio_output_combos(self):
        self.output_combo_primary.clear()
        self.output_combo_secondary.clear()
        devices = []
        outputs = self.player_primary.audio_output_device_enum()
        if outputs:
            current = outputs
            while current:
                name = current.contents.device
                desc = current.contents.description
                if name and desc:
                    devices.append((name.decode(), desc.decode()))
                current = current.contents.next
        for name, desc in devices:
            self.output_combo_primary.addItem(name, name)
            self.output_combo_secondary.addItem(name, name)

    def update_outputs(self):
        print("Updating outputs")

        # Primary output
        primary_output = self.output_combo_primary.currentData()
        if primary_output:
            self.player_primary.audio_output_device_set(None, primary_output)

        self.player_primary.audio_set_volume(self.volume_slider_primary.value())
        self.player_primary.audio_set_mute(self.player_primary_mute)
        self.primary_label.setStyleSheet("color: orange;" if self.player_primary_mute else "color: green;")

        # Secondary output
        secondary_output = self.output_combo_secondary.currentData()
        if secondary_output:
            self.player_secondary.audio_output_device_set(None, secondary_output)

        self.player_secondary.audio_set_volume(self.volume_slider_secondary.value())
        self.player_secondary.audio_set_mute(self.player_secondary_mute)
        self.secondary_label.setStyleSheet("color: orange;" if self.player_secondary_mute else "color: green;")

        self.save_config()

    def load_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Audio", "", "Audio Files (*.mp3 *.wav)")
        if path:
            self.load_file(path)

    def load_file(self, path):
        self.current_file = path
        self.file_label.setText(os.path.basename(path))
        self.media = self.instance.media_new(path)
        self.player_primary.set_media(self.media)
        self.player_secondary.set_media(self.instance.media_new(path))

    def toggle_play_pause(self):
        if self.player_primary.is_playing():
            self.player_primary.pause()
            self.player_secondary.pause()
            self.play_pause_button.setText("Play")
        else:
            self.player_primary.play()
            self.player_secondary.play()
            self.timer.start()
            self.play_pause_button.setText("Pause")

    def stop_audio(self):
        self.player_primary.stop()
        self.player_secondary.stop()
        self.timer.stop()
        self.play_pause_button.setText("Play")

    def update_seek_slider(self):
        length = self.player_primary.get_length()
        pos = self.player_primary.get_time()
        if length > 0:
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(int((pos / length) * 1000))
            self.seek_slider.blockSignals(False)
            if self.end_pos and pos >= self.end_pos:
                self.stop_audio()

    def seek_audio(self):
        length = self.player_primary.get_length()
        if length > 0:
            t = int((self.seek_slider.value() / 1000) * length)
            self.player_primary.set_time(t)
            self.player_secondary.set_time(t)
        self.timer.start()

    def set_start(self):
        self.start_pos = self.player_primary.get_time()
        self.set_start_button.setText(f"Start: {self.start_pos // 1000}s")

    def set_end(self):
        self.end_pos = self.player_primary.get_time()
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
        import random
        colors = ['#FF6666', '#66FF66', '#6666FF', '#FFCC66', '#66CCFF', '#FF99CC', '#CCFF66', '#FF9966']
        for i in reversed(range(self.preset_list.count())):
            self.preset_list.itemAt(i).widget().setParent(None)
        row = None
        for idx, (name, data) in enumerate(self.config.get("presets", {}).items()):
            if idx % 5 == 0:
                row = QHBoxLayout()
                self.preset_list.addLayout(row)
            button = QPushButton(name)
            button.setStyleSheet(f"background-color: {random.choice(colors)}; min-width: 80px; min-height: 40px;")
            button.clicked.connect(lambda _, d=data: self.play_preset(d))
            row.addWidget(button)

    def play_preset(self, preset):
        self.load_file(preset["file"])
        self.start_pos = preset["start"]
        self.end_pos = preset["end"]
        self.player_primary.play()
        self.player_secondary.play()
        self.player_primary.set_time(self.start_pos)
        self.player_secondary.set_time(self.start_pos)
        self.timer.start()
        self.play_pause_button.setText("Pause")
        self.update_outputs()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return yaml.safe_load(f) or {}
        return {}

    def save_config(self):
        self.config["settings"] = {
            "output_device_primary": self.output_combo_primary.currentData(),
            "output_device_secondary": self.output_combo_secondary.currentData(),
            "volume_primary": self.volume_slider_primary.value(),
            "volume_secondary": self.volume_slider_secondary.value()
        }
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(self.config, f)

    def restore_settings(self):
        s = self.config.get("settings", {})
        for i in range(self.output_combo_primary.count()):
            if self.output_combo_primary.itemData(i) == s.get("output_device_primary"):
                self.output_combo_primary.setCurrentIndex(i)
        for i in range(self.output_combo_secondary.count()):
            if self.output_combo_secondary.itemData(i) == s.get("output_device_secondary"):
                self.output_combo_secondary.setCurrentIndex(i)
        self.volume_slider_primary.setValue(s.get("volume_primary", 75))
        self.volume_slider_secondary.setValue(s.get("volume_secondary", 75))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DiscordSoundBoard()
    window.show()
    sys.exit(app.exec_())
