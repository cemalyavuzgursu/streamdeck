import json
from typing import List, Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QAction,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QPlainTextEdit,
)

from src.core.device_manager import DeviceManager, ModuleInfo
from src.core.firmware_flasher import FirmwareFlasher
from src.core.profile_manager import ModuleConfig, Profile, ProfileManager
from src.core.updater import Updater
from src.ui.module_widget import ModuleWidget
from src.ui.profile_editor import (
    ButtonAssignDialog,
    DisplaySettingsDialog,
    EncoderAssignDialog,
)
from src.utils.constants import APP_NAME, APP_VERSION, STYLE_DARK


# ─────────────────────────── Add module dialog ────────────────────────────────

class AddModuleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modül Ekle")
        self.setMinimumWidth(320)
        lay = QVBoxLayout(self)
        form = QFormLayout()

        self._name_edit = __import__("PyQt5.QtWidgets", fromlist=["QLineEdit"]).QLineEdit()
        self._name_edit.setPlaceholderText("ör. Sağ Modül")
        form.addRow("İsim:", self._name_edit)

        self._btn_spin = QSpinBox()
        self._btn_spin.setRange(0, 32)
        self._btn_spin.setValue(4)
        form.addRow("Buton sayısı:", self._btn_spin)

        self._enc_spin = QSpinBox()
        self._enc_spin.setRange(0, 8)
        self._enc_spin.setValue(0)
        form.addRow("Encoder sayısı:", self._enc_spin)

        self._display_cb = QCheckBox("OLED Ekran var")
        form.addRow("", self._display_cb)
        lay.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Ok).setObjectName("primary")
        lay.addWidget(btns)

    def get_config(self) -> ModuleConfig:
        import uuid
        mid = str(uuid.uuid4())[:8]
        name = self._name_edit.text().strip() or f"Modül {mid}"
        return ModuleConfig(
            module_id=mid,
            module_type="slave",
            name=name,
            button_count=self._btn_spin.value(),
            encoder_count=self._enc_spin.value(),
            has_display=self._display_cb.isChecked(),
        )


# ─────────────────────────── Flash firmware dialog ───────────────────────────

class FlashDialog(QDialog):
    def __init__(self, port: str, parent=None):
        super().__init__(parent)
        self._port = port
        self.setWindowTitle("Firmware Güncelle")
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        source_grp = QGroupBox("Firmware Kaynağı")
        s_lay = QVBoxLayout(source_grp)

        self._from_github_btn = QPushButton("🌐  GitHub'dan Son Sürümü İndir ve Flash'la")
        self._from_github_btn.setObjectName("primary")
        self._from_github_btn.clicked.connect(lambda: self._start_flash(from_github=True))
        s_lay.addWidget(self._from_github_btn)

        local_row = QHBoxLayout()
        self._local_path = __import__("PyQt5.QtWidgets", fromlist=["QLineEdit"]).QLineEdit()
        self._local_path.setPlaceholderText("Yerel .bin dosyası…")
        browse = QPushButton("Gözat")
        browse.setFixedWidth(70)
        browse.clicked.connect(self._browse)
        local_row.addWidget(self._local_path)
        local_row.addWidget(browse)
        s_lay.addLayout(local_row)

        flash_local = QPushButton("⚡  Seçili Dosyayı Flash'la")
        flash_local.clicked.connect(lambda: self._start_flash(from_github=False))
        s_lay.addWidget(flash_local)
        lay.addWidget(source_grp)

        self._status_lbl = QLabel("Hazır.")
        self._status_lbl.setStyleSheet("color:#6c7086;")
        lay.addWidget(self._status_lbl)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(120)
        self._log.setStyleSheet(
            "QPlainTextEdit{background:#0d0d1a;color:#a6e3a1;font-family:Consolas;font-size:11px;}"
        )
        lay.addWidget(self._log)

        self._close_btn = QPushButton("Kapat")
        self._close_btn.clicked.connect(self.accept)
        lay.addWidget(self._close_btn, 0, Qt.AlignRight)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Firmware Seç", "", "Binary (*.bin)")
        if path:
            self._local_path.setText(path)

    def _start_flash(self, from_github: bool):
        self._from_github_btn.setEnabled(False)
        self._log.clear()
        bin_path = None if from_github else self._local_path.text().strip()

        self._flasher = FirmwareFlasher(self._port, bin_path=bin_path, from_github=from_github)
        self._flasher.progress.connect(self._on_progress)
        self._flasher.log_line.connect(self._log.appendPlainText)
        self._flasher.finished.connect(self._on_finished)
        self._flasher.start()

    def _on_progress(self, msg: str):
        self._status_lbl.setText(msg)
        self._log.appendPlainText(msg)

    def _on_finished(self, ok: bool, msg: str):
        self._from_github_btn.setEnabled(True)
        color = "#a6e3a1" if ok else "#f38ba8"
        self._status_lbl.setStyleSheet(f"color:{color};font-weight:bold;")
        self._status_lbl.setText(msg)
        self._log.appendPlainText(f"\n{'✓' if ok else '✗'} {msg}")


# ─────────────────────────── Main window ─────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._profile_manager = ProfileManager()
        self._device_manager = DeviceManager(self)
        self._updater = Updater(self)
        self._module_widgets: List[ModuleWidget] = []

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(900, 620)
        self.resize(1100, 700)
        self.setStyleSheet(STYLE_DARK)

        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_status_bar()
        self._connect_signals()
        self._refresh_profile_list()
        self._load_active_profile_modules()

        QTimer.singleShot(1500, self._updater.check_for_updates)
        QTimer.singleShot(200, self._refresh_ports)

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()
        mb.setNativeMenuBar(False)

        file_m = mb.addMenu("Dosya")
        file_m.addAction("Profil İçe Aktar…", self._import_profile)
        file_m.addAction("Profil Dışa Aktar…", self._export_profile)
        file_m.addSeparator()
        file_m.addAction("Çıkış", self.close)

        device_m = mb.addMenu("Cihaz")
        device_m.addAction("Konfigürasyonu Gönder", self._send_config)
        device_m.addAction("Modülleri Yenile", self._refresh_modules)
        device_m.addSeparator()
        device_m.addAction("Firmware Güncelle…", self._open_flash_dialog)

        help_m = mb.addMenu("Yardım")
        help_m.addAction("Güncellemeleri Kontrol Et", self._check_updates)
        help_m.addAction("Hakkında", self._show_about)

    def _build_toolbar(self):
        tb = QToolBar("Ana Araç Çubuğu")
        tb.setMovable(False)
        self.addToolBar(tb)

        # Port selector
        tb.addWidget(QLabel(" Port: "))
        self._port_combo = QComboBox()
        self._port_combo.setMinimumWidth(130)
        self._port_combo.setToolTip("Seri port")
        tb.addWidget(self._port_combo)

        self._refresh_ports_btn = QPushButton("↻")
        self._refresh_ports_btn.setFixedWidth(32)
        self._refresh_ports_btn.setToolTip("Portları Tara")
        self._refresh_ports_btn.clicked.connect(self._refresh_ports)
        tb.addWidget(self._refresh_ports_btn)

        self._connect_btn = QPushButton("Bağlan")
        self._connect_btn.setObjectName("primary")
        self._connect_btn.setFixedWidth(90)
        self._connect_btn.clicked.connect(self._toggle_connection)
        tb.addWidget(self._connect_btn)

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color:#585b70;font-size:16px;")
        self._status_dot.setToolTip("Bağlı değil")
        tb.addWidget(self._status_dot)

        tb.addSeparator()

        send_btn = QPushButton("⬆ Cihaza Gönder")
        send_btn.setObjectName("success")
        send_btn.clicked.connect(self._send_config)
        tb.addWidget(send_btn)

        tb.addSeparator()
        tb.addWidget(QLabel("  Profil: "))
        self._profile_tb_combo = QComboBox()
        self._profile_tb_combo.setMinimumWidth(140)
        self._profile_tb_combo.currentIndexChanged.connect(self._on_profile_tb_changed)
        tb.addWidget(self._profile_tb_combo)

    def _build_central(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        main_lay = QHBoxLayout(central)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)

        # ── Left: Profile panel ──────────────────────────────────
        left_panel = QWidget()
        left_panel.setFixedWidth(220)
        left_panel.setStyleSheet("background-color:#181825;")
        l_lay = QVBoxLayout(left_panel)
        l_lay.setContentsMargins(8, 10, 8, 10)
        l_lay.setSpacing(8)

        prof_header = QHBoxLayout()
        prof_title = QLabel("Profiller")
        prof_title.setStyleSheet("font-weight:bold;font-size:14px;color:#89b4fa;")
        prof_header.addWidget(prof_title)
        prof_header.addStretch()

        add_prof_btn = QPushButton("+")
        add_prof_btn.setFixedSize(26, 26)
        add_prof_btn.setToolTip("Yeni Profil")
        add_prof_btn.setStyleSheet(
            "QPushButton{background:#313244;color:#a6e3a1;border-radius:6px;font-weight:bold;font-size:14px;border:none;}"
            "QPushButton:hover{background:#45475a;}"
        )
        add_prof_btn.clicked.connect(self._new_profile)
        prof_header.addWidget(add_prof_btn)
        l_lay.addLayout(prof_header)

        self._profile_list = QListWidget()
        self._profile_list.setDragDropMode(QListWidget.InternalMove)
        self._profile_list.itemClicked.connect(self._on_profile_selected)
        l_lay.addWidget(self._profile_list)

        prof_btns = QHBoxLayout()
        for txt, tip, slot, obj in [
            ("✎", "Yeniden Adlandır", self._rename_profile, None),
            ("⧉", "Kopyala", self._duplicate_profile, None),
            ("✕", "Sil", self._delete_profile, "danger"),
        ]:
            b = QPushButton(txt)
            b.setFixedSize(36, 28)
            b.setToolTip(tip)
            if obj:
                b.setObjectName(obj)
            b.clicked.connect(slot)
            prof_btns.addWidget(b)
        l_lay.addLayout(prof_btns)

        # ── Module add/sync buttons ──────────────────────────────
        l_lay.addWidget(self._hsep())
        mod_title = QLabel("Modüller")
        mod_title.setStyleSheet("font-weight:bold;font-size:13px;color:#89b4fa;")
        l_lay.addWidget(mod_title)

        add_mod_btn = QPushButton("+ Modül Ekle")
        add_mod_btn.clicked.connect(self._add_module_manual)
        l_lay.addWidget(add_mod_btn)

        sync_btn = QPushButton("⟳ Cihazdan Al")
        sync_btn.clicked.connect(self._refresh_modules)
        l_lay.addWidget(sync_btn)

        splitter.addWidget(left_panel)

        # ── Right: Module scroll area ────────────────────────────
        right_panel = QWidget()
        right_panel.setStyleSheet("background-color:#1e1e2e;")
        r_lay = QVBoxLayout(right_panel)
        r_lay.setContentsMargins(12, 12, 12, 12)
        r_lay.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")

        self._modules_container = QWidget()
        self._modules_container.setStyleSheet("background:transparent;")
        self._modules_layout = QVBoxLayout(self._modules_container)
        self._modules_layout.setContentsMargins(0, 0, 8, 0)
        self._modules_layout.setSpacing(10)
        self._modules_layout.addStretch()
        scroll.setWidget(self._modules_container)
        r_lay.addWidget(scroll)

        splitter.addWidget(right_panel)
        splitter.setSizes([220, 880])
        main_lay.addWidget(splitter)

    def _build_status_bar(self):
        sb = self.statusBar()
        self._conn_status_lbl = QLabel("Bağlı değil")
        self._conn_status_lbl.setStyleSheet("color:#6c7086;padding:0 8px;")
        sb.addPermanentWidget(self._conn_status_lbl)

        ver_lbl = QLabel(f"v{APP_VERSION}")
        ver_lbl.setStyleSheet("color:#45475a;padding:0 8px;")
        sb.addPermanentWidget(ver_lbl)

    def _connect_signals(self):
        dm = self._device_manager
        dm.connection_changed.connect(self._on_connection_changed)
        dm.modules_updated.connect(self._on_modules_from_device)
        dm.error_occurred.connect(self._on_device_error)
        dm.config_sent.connect(lambda: self.statusBar().showMessage("Konfigürasyon gönderildi ✓", 3000))

        u = self._updater
        u.update_available.connect(self._on_update_available)
        u.error_occurred.connect(lambda e: self.statusBar().showMessage(f"Güncelleme hatası: {e}", 4000))

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _hsep():
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color:#313244;")
        return sep

    def _current_profile(self) -> Optional[Profile]:
        return self._profile_manager.get_active_profile()

    # ── Profile management ────────────────────────────────────────────────────

    def _refresh_profile_list(self):
        self._profile_list.clear()
        self._profile_tb_combo.blockSignals(True)
        self._profile_tb_combo.clear()
        active_id = self._profile_manager.active_profile_id

        for p in self._profile_manager.profiles:
            item = QListWidgetItem(p.name)
            item.setData(Qt.UserRole, p.id)
            self._profile_list.addItem(item)
            self._profile_tb_combo.addItem(p.name, p.id)
            if p.id == active_id:
                self._profile_list.setCurrentItem(item)
                idx = self._profile_tb_combo.count() - 1
                self._profile_tb_combo.setCurrentIndex(idx)

        self._profile_tb_combo.blockSignals(False)

    def _new_profile(self):
        name, ok = QInputDialog.getText(self, "Yeni Profil", "Profil adı:")
        if ok and name.strip():
            p = self._profile_manager.new_profile(name.strip())
            self._profile_manager.active_profile_id = p.id
            self._refresh_profile_list()
            self._load_active_profile_modules()

    def _rename_profile(self):
        p = self._current_profile()
        if not p:
            return
        name, ok = QInputDialog.getText(self, "Yeniden Adlandır", "Yeni ad:", text=p.name)
        if ok and name.strip():
            p.name = name.strip()
            self._profile_manager.save_profile(p)
            self._refresh_profile_list()

    def _duplicate_profile(self):
        p = self._current_profile()
        if not p:
            return
        new_p = self._profile_manager.duplicate_profile(p.id)
        if new_p:
            self._profile_manager.active_profile_id = new_p.id
            self._refresh_profile_list()
            self._load_active_profile_modules()

    def _delete_profile(self):
        p = self._current_profile()
        if not p:
            return
        if len(self._profile_manager.profiles) <= 1:
            QMessageBox.warning(self, "Uyarı", "En az bir profil olmalı.")
            return
        ans = QMessageBox.question(
            self, "Sil", f"'{p.name}' profilini silmek istediğinizden emin misiniz?"
        )
        if ans == QMessageBox.Yes:
            self._profile_manager.delete_profile(p.id)
            self._refresh_profile_list()
            self._load_active_profile_modules()

    def _on_profile_selected(self, item: QListWidgetItem):
        pid = item.data(Qt.UserRole)
        self._profile_manager.active_profile_id = pid
        self._profile_tb_combo.blockSignals(True)
        idx = self._profile_tb_combo.findData(pid)
        if idx >= 0:
            self._profile_tb_combo.setCurrentIndex(idx)
        self._profile_tb_combo.blockSignals(False)
        self._load_active_profile_modules()

    def _on_profile_tb_changed(self, _):
        pid = self._profile_tb_combo.currentData()
        if pid:
            self._profile_manager.active_profile_id = pid
            for i in range(self._profile_list.count()):
                item = self._profile_list.item(i)
                if item.data(Qt.UserRole) == pid:
                    self._profile_list.setCurrentItem(item)
                    break
            self._load_active_profile_modules()

    # ── Module UI ─────────────────────────────────────────────────────────────

    def _load_active_profile_modules(self):
        self._clear_module_widgets()
        p = self._current_profile()
        if p:
            for mc in p.modules:
                self._add_module_widget(mc)

    def _clear_module_widgets(self):
        for w in self._module_widgets:
            self._modules_layout.removeWidget(w)
            w.deleteLater()
        self._module_widgets.clear()

    def _add_module_widget(self, mc: ModuleConfig):
        w = ModuleWidget(mc)
        w.button_clicked.connect(self._on_button_clicked)
        w.encoder_cw_clicked.connect(lambda cfg, i: self._open_encoder_dialog(cfg, i))
        w.encoder_ccw_clicked.connect(lambda cfg, i: self._open_encoder_dialog(cfg, i))
        w.encoder_push_clicked.connect(lambda cfg, i: self._open_encoder_dialog(cfg, i))
        w.display_settings_clicked.connect(self._on_display_settings)
        w.move_up_clicked.connect(self._move_module_up)
        w.move_down_clicked.connect(self._move_module_down)

        # Remove trailing stretch, insert widget, re-add stretch
        count = self._modules_layout.count()
        if count > 0:
            last = self._modules_layout.itemAt(count - 1)
            if last and last.spacerItem():
                self._modules_layout.takeAt(count - 1)
        self._modules_layout.addWidget(w)
        self._modules_layout.addStretch()
        self._module_widgets.append(w)

    def _add_module_manual(self):
        dlg = AddModuleDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            mc = dlg.get_config()
            p = self._current_profile()
            if p:
                p.modules.append(mc)
                self._profile_manager.save_profile(p)
                self._add_module_widget(mc)

    def _move_module_up(self, mc: ModuleConfig):
        p = self._current_profile()
        if not p:
            return
        idx = next((i for i, m in enumerate(p.modules) if m.module_id == mc.module_id), -1)
        if idx > 0:
            p.modules[idx], p.modules[idx - 1] = p.modules[idx - 1], p.modules[idx]
            self._profile_manager.save_profile(p)
            self._load_active_profile_modules()

    def _move_module_down(self, mc: ModuleConfig):
        p = self._current_profile()
        if not p:
            return
        idx = next((i for i, m in enumerate(p.modules) if m.module_id == mc.module_id), -1)
        if 0 <= idx < len(p.modules) - 1:
            p.modules[idx], p.modules[idx + 1] = p.modules[idx + 1], p.modules[idx]
            self._profile_manager.save_profile(p)
            self._load_active_profile_modules()

    # ── Editor dialogs ────────────────────────────────────────────────────────

    def _on_button_clicked(self, mc: ModuleConfig, index: int):
        btn_cfg = mc.buttons[index]
        dlg = ButtonAssignDialog(
            btn_cfg,
            title=f"{mc.name} – K{index + 1}",
            profiles=self._profile_manager.profiles,
            parent=self,
        )
        if dlg.exec_() == QDialog.Accepted:
            mc.buttons[index] = dlg.result_config()
            p = self._current_profile()
            if p:
                self._profile_manager.save_profile(p)
            self._find_widget(mc).refresh()

    def _open_encoder_dialog(self, mc: ModuleConfig, index: int):
        enc_cfg = mc.encoders[index]
        dlg = EncoderAssignDialog(
            enc_cfg,
            index=index,
            profiles=self._profile_manager.profiles,
            parent=self,
        )
        if dlg.exec_() == QDialog.Accepted:
            mc.encoders[index] = dlg.result_config()
            p = self._current_profile()
            if p:
                self._profile_manager.save_profile(p)
            self._find_widget(mc).refresh()

    def _on_display_settings(self, mc: ModuleConfig):
        p = self._current_profile()
        dlg = DisplaySettingsDialog(mc, profile_name=p.name if p else "", parent=self)
        if dlg.exec_() == QDialog.Accepted:
            if p:
                self._profile_manager.save_profile(p)
            self._find_widget(mc).refresh()

    def _find_widget(self, mc: ModuleConfig) -> Optional[ModuleWidget]:
        return next((w for w in self._module_widgets if w.config.module_id == mc.module_id), None)

    # ── Device ────────────────────────────────────────────────────────────────

    def _refresh_ports(self):
        ports = self._device_manager.list_ports()
        current = self._port_combo.currentText()
        self._port_combo.clear()
        for p in ports:
            self._port_combo.addItem(p)
        if current in ports:
            self._port_combo.setCurrentText(current)
        if not ports:
            self._port_combo.addItem("(port yok)")

    def _toggle_connection(self):
        if self._device_manager.is_connected:
            self._device_manager.disconnect()
        else:
            port = self._port_combo.currentText()
            if port and port != "(port yok)":
                self._device_manager.connect(port)
            else:
                QMessageBox.warning(self, "Hata", "Lütfen önce bir seri port seçin.")

    def _on_connection_changed(self, connected: bool, port: str):
        if connected:
            self._connect_btn.setText("Kes")
            self._status_dot.setStyleSheet("color:#a6e3a1;font-size:16px;")
            self._status_dot.setToolTip(f"Bağlı: {port}")
            self._conn_status_lbl.setText(f"Bağlı: {port}")
            self._conn_status_lbl.setStyleSheet("color:#a6e3a1;padding:0 8px;")
        else:
            self._connect_btn.setText("Bağlan")
            self._status_dot.setStyleSheet("color:#585b70;font-size:16px;")
            self._status_dot.setToolTip("Bağlı değil")
            self._conn_status_lbl.setText("Bağlı değil")
            self._conn_status_lbl.setStyleSheet("color:#6c7086;padding:0 8px;")
            self._refresh_ports()

    def _on_modules_from_device(self, modules: List[ModuleInfo]):
        p = self._current_profile()
        if not p:
            return

        # Merge device modules into profile
        existing_ids = {m.module_id for m in p.modules}
        for mi in modules:
            if mi.module_id not in existing_ids:
                p.modules.append(
                    ModuleConfig(
                        module_id=mi.module_id,
                        module_type=mi.module_type,
                        name=mi.name,
                        button_count=mi.button_count,
                        encoder_count=mi.encoder_count,
                        has_display=mi.has_display,
                    )
                )
        self._profile_manager.save_profile(p)
        self._load_active_profile_modules()
        self.statusBar().showMessage(f"{len(modules)} modül algılandı ✓", 3000)

    def _on_device_error(self, msg: str):
        self.statusBar().showMessage(f"Cihaz hatası: {msg}", 5000)

    def _refresh_modules(self):
        if self._device_manager.is_connected:
            self._device_manager.refresh_modules()
        else:
            self.statusBar().showMessage("Cihaz bağlı değil.", 2000)

    def _send_config(self):
        p = self._current_profile()
        if not p:
            return
        if not self._device_manager.is_connected:
            QMessageBox.warning(self, "Bağlantı Yok", "ESP32 bağlı değil.")
            return
        self._device_manager.send_config(p.to_esp_config())

    def _open_flash_dialog(self):
        port = self._device_manager.current_port or self._port_combo.currentText()
        if not port or port == "(port yok)":
            QMessageBox.warning(self, "Port Yok", "Lütfen önce bir seri port seçin.")
            return
        FlashDialog(port, self).exec_()

    # ── Import / Export ───────────────────────────────────────────────────────

    def _import_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, "Profil İçe Aktar", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            from src.core.profile_manager import Profile
            import uuid
            p = Profile.from_dict(data)
            p.id = str(uuid.uuid4())
            self._profile_manager.profiles.append(p)
            self._profile_manager.save_profile(p)
            self._profile_manager.active_profile_id = p.id
            self._refresh_profile_list()
            self._load_active_profile_modules()
            QMessageBox.information(self, "Başarılı", f"'{p.name}' profili içe aktarıldı.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Profil içe aktarılamadı:\n{e}")

    def _export_profile(self):
        p = self._current_profile()
        if not p:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Profil Dışa Aktar", f"{p.name}.json", "JSON (*.json)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(p.to_dict(), f, ensure_ascii=False, indent=2)
        QMessageBox.information(self, "Başarılı", f"Profil '{path}' olarak kaydedildi.")

    # ── Updater ───────────────────────────────────────────────────────────────

    def _check_updates(self):
        self.statusBar().showMessage("Güncellemeler kontrol ediliyor…")
        self._updater.check_for_updates()

    def _on_update_available(self, version: str, url: str, notes: str):
        self.statusBar().showMessage(f"Yeni sürüm: v{version}", 5000)
        msg = QMessageBox(self)
        msg.setWindowTitle("Güncelleme Mevcut")
        msg.setIcon(QMessageBox.Information)
        msg.setText(f"<b>v{version}</b> sürümü mevcut.")
        if notes:
            msg.setDetailedText(notes)
        msg.setInformativeText("Şimdi indirip güncellemek ister misiniz?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if msg.exec_() == QMessageBox.Yes and url:
            self._start_download(url)

    def _start_download(self, url: str):
        self.statusBar().showMessage("İndiriliyor…")
        self._dl_progress = QProgressBar()
        self._dl_progress.setFixedWidth(200)
        self.statusBar().addPermanentWidget(self._dl_progress)
        self._updater.download_progress.connect(self._dl_progress.setValue)
        self._updater.download_finished.connect(self._on_download_done)
        self._updater.download_update(url)

    def _on_download_done(self, path: str):
        self.statusBar().showMessage("İndirme tamamlandı. Yeniden başlatılıyor…", 2000)
        self._updater.apply_update(path)

    # ── About ─────────────────────────────────────────────────────────────────

    def _show_about(self):
        QMessageBox.about(
            self,
            "Hakkında",
            f"<b>{APP_NAME}</b><br>"
            f"Sürüm: {APP_VERSION}<br><br>"
            "ESP32-C3 tabanlı modüler makropad<br>"
            "yapılandırma uygulaması.<br><br>"
            "PyQt5 + pyserial ile geliştirildi.",
        )
