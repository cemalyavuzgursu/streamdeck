from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.profile_manager import ButtonConfig, EncoderConfig, ModuleConfig
from src.ui.module_widget import OLEDPreviewWidget
from src.utils.constants import (
    ACTION_APP,
    ACTION_LABELS,
    ACTION_MACRO,
    ACTION_MEDIA,
    ACTION_NONE,
    ACTION_PROFILE_SWITCH,
    ACTION_SHORTCUT,
    DISPLAY_CLOCK,
    DISPLAY_CUSTOM,
    DISPLAY_MODES,
    MEDIA_ACTIONS,
)


# ─────────────────────────── Key capture ──────────────────────────────────────

class KeyCaptureEdit(QLineEdit):
    """Captures a keyboard shortcut on key press."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Kısayolu girin veya buraya tıklayıp tuşlara basın…")
        self.setReadOnly(False)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return

        mods = event.modifiers()
        parts = []
        if mods & Qt.ControlModifier:
            parts.append("ctrl")
        if mods & Qt.AltModifier:
            parts.append("alt")
        if mods & Qt.ShiftModifier:
            parts.append("shift")
        if mods & Qt.MetaModifier:
            parts.append("win")

        name = self._key_name(key)
        if name:
            parts.append(name)

        if parts:
            self.setText("+".join(parts))

    @staticmethod
    def _key_name(key: int) -> str:
        _MAP = {
            Qt.Key_Escape: "esc",
            Qt.Key_Tab: "tab",
            Qt.Key_Return: "enter",
            Qt.Key_Backspace: "backspace",
            Qt.Key_Delete: "delete",
            Qt.Key_Insert: "insert",
            Qt.Key_Home: "home",
            Qt.Key_End: "end",
            Qt.Key_PageUp: "pageup",
            Qt.Key_PageDown: "pagedown",
            Qt.Key_Left: "left",
            Qt.Key_Right: "right",
            Qt.Key_Up: "up",
            Qt.Key_Down: "down",
            Qt.Key_Space: "space",
            Qt.Key_Print: "printscreen",
            Qt.Key_Pause: "pause",
            Qt.Key_CapsLock: "capslock",
            Qt.Key_NumLock: "numlock",
            **{Qt.Key_F1 + i: f"f{i + 1}" for i in range(24)},
        }
        if key in _MAP:
            return _MAP[key]
        if 32 <= key <= 126:
            return chr(key).lower()
        return ""


# ─────────────────────────── Per-action widgets ───────────────────────────────

class ActionConfigWidget(QWidget):
    """Dynamic widget showing configuration for the selected action type."""

    def __init__(self, profiles=None, parent=None):
        super().__init__(parent)
        self._profiles = profiles or []
        self._current_type = ACTION_NONE

        self._pages: dict = {}
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        # Build one page per action type
        self._pages[ACTION_NONE] = self._page_none()
        self._pages[ACTION_SHORTCUT] = self._page_shortcut()
        self._pages[ACTION_MEDIA] = self._page_media()
        self._pages[ACTION_APP] = self._page_app()
        self._pages[ACTION_MACRO] = self._page_macro()
        self._pages[ACTION_PROFILE_SWITCH] = self._page_profile()

        for page in self._pages.values():
            self._layout.addWidget(page)
            page.hide()

    def show_type(self, action_type: str):
        for t, page in self._pages.items():
            page.setVisible(t == action_type)
        self._current_type = action_type

    def load(self, config: ButtonConfig):
        self.show_type(config.action_type)
        ad = config.action_data

        if config.action_type == ACTION_SHORTCUT:
            self._shortcut_edit.setText(ad.get("keys", ""))
        elif config.action_type == ACTION_MEDIA:
            idx = self._media_combo.findData(ad.get("action", ""))
            self._media_combo.setCurrentIndex(max(0, idx))
        elif config.action_type == ACTION_APP:
            self._app_edit.setText(ad.get("path", ""))
            self._app_args_edit.setText(ad.get("args", ""))
        elif config.action_type == ACTION_MACRO:
            self._macro_edit.setPlainText(ad.get("sequence", ""))
        elif config.action_type == ACTION_PROFILE_SWITCH:
            pid = ad.get("profile_id", "")
            idx = self._profile_combo.findData(pid)
            self._profile_combo.setCurrentIndex(max(0, idx))

    def save(self, config: ButtonConfig):
        config.action_type = self._current_type
        config.action_data = {}

        if self._current_type == ACTION_SHORTCUT:
            config.action_data["keys"] = self._shortcut_edit.text().strip()
        elif self._current_type == ACTION_MEDIA:
            config.action_data["action"] = self._media_combo.currentData()
        elif self._current_type == ACTION_APP:
            config.action_data["path"] = self._app_edit.text().strip()
            config.action_data["args"] = self._app_args_edit.text().strip()
        elif self._current_type == ACTION_MACRO:
            config.action_data["sequence"] = self._macro_edit.toPlainText().strip()
        elif self._current_type == ACTION_PROFILE_SWITCH:
            config.action_data["profile_id"] = self._profile_combo.currentData() or ""

    # ── Page builders ─────────────────────────────────────────────────────────

    def _page_none(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lbl = QLabel("Bu tuşa herhangi bir işlem atanmayacak.")
        lbl.setStyleSheet("color:#6c7086;font-style:italic;")
        lay.addWidget(lbl)
        return w

    def _page_shortcut(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(0, 0, 0, 0)
        self._shortcut_edit = KeyCaptureEdit()
        form.addRow("Kısayol:", self._shortcut_edit)
        hint = QLabel("Örnek: ctrl+c  |  win+d  |  ctrl+shift+esc")
        hint.setStyleSheet("color:#6c7086;font-size:11px;")
        form.addRow("", hint)
        return w

    def _page_media(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(0, 0, 0, 0)
        self._media_combo = QComboBox()
        for key, label in MEDIA_ACTIONS.items():
            self._media_combo.addItem(label, key)
        form.addRow("Medya:", self._media_combo)
        return w

    def _page_app(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self._app_edit = QLineEdit()
        self._app_edit.setPlaceholderText("Uygulama yolu…")
        browse_btn = QPushButton("Gözat")
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(self._browse_app)
        row.addWidget(self._app_edit)
        row.addWidget(browse_btn)
        form.addRow("Yol:", row)
        self._app_args_edit = QLineEdit()
        self._app_args_edit.setPlaceholderText("İsteğe bağlı argümanlar")
        form.addRow("Argümanlar:", self._app_args_edit)
        return w

    def _page_macro(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        self._macro_edit = QPlainTextEdit()
        self._macro_edit.setFixedHeight(100)
        self._macro_edit.setPlaceholderText(
            "Her satıra bir tuş:\nctrl+c\nwait:200\nctrl+v"
        )
        lay.addWidget(QLabel("Makro dizisi:"))
        lay.addWidget(self._macro_edit)
        hint = QLabel("Desteklenen: tuş adları, wait:ms, type:metin")
        hint.setStyleSheet("color:#6c7086;font-size:11px;")
        lay.addWidget(hint)
        return w

    def _page_profile(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(0, 0, 0, 0)
        self._profile_combo = QComboBox()
        self._refresh_profiles()
        form.addRow("Profil:", self._profile_combo)
        return w

    def _refresh_profiles(self):
        self._profile_combo.clear()
        for p in self._profiles:
            self._profile_combo.addItem(p.name, p.id)

    def set_profiles(self, profiles):
        self._profiles = profiles
        self._refresh_profiles()

    def _browse_app(self):
        path, _ = QFileDialog.getOpenFileName(self, "Uygulama Seç", "", "Uygulamalar (*.exe *.bat *.cmd);;Tümü (*)")
        if path:
            self._app_edit.setText(path)


# ─────────────────────────── Button assign dialog ─────────────────────────────

class ButtonAssignDialog(QDialog):
    def __init__(self, config: ButtonConfig, title: str = "Buton Ata", profiles=None, parent=None):
        super().__init__(parent)
        self._config = ButtonConfig.from_dict(config.to_dict())  # work on a copy
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self._build_ui(profiles or [])

    def _build_ui(self, profiles):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        # Label
        form = QFormLayout()
        self._label_edit = QLineEdit(self._config.label)
        self._label_edit.setPlaceholderText("Tuş etiketi (isteğe bağlı)")
        form.addRow("Etiket:", self._label_edit)
        lay.addLayout(form)

        # Action type
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Eylem tipi:"))
        self._type_combo = QComboBox()
        for key, label in ACTION_LABELS.items():
            self._type_combo.addItem(label, key)
        idx = self._type_combo.findData(self._config.action_type)
        self._type_combo.setCurrentIndex(max(0, idx))
        type_row.addWidget(self._type_combo)
        type_row.addStretch()
        lay.addLayout(type_row)

        # Action config area
        group = QGroupBox("Ayarlar")
        g_lay = QVBoxLayout(group)
        self._action_widget = ActionConfigWidget(profiles)
        g_lay.addWidget(self._action_widget)
        lay.addWidget(group)

        self._action_widget.load(self._config)
        self._type_combo.currentIndexChanged.connect(
            lambda: self._action_widget.show_type(self._type_combo.currentData())
        )

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        ok_btn = btns.button(QDialogButtonBox.Ok)
        ok_btn.setObjectName("primary")
        lay.addWidget(btns)

    def _accept(self):
        self._config.label = self._label_edit.text().strip()
        self._config.action_type = self._type_combo.currentData()
        self._action_widget.save(self._config)
        self.accept()

    def result_config(self) -> ButtonConfig:
        return self._config


# ─────────────────────────── Encoder assign dialog ────────────────────────────

class EncoderAssignDialog(QDialog):
    def __init__(self, config: EncoderConfig, index: int, profiles=None, parent=None):
        super().__init__(parent)
        self._config = EncoderConfig.from_dict(config.to_dict())
        self.setWindowTitle(f"Encoder {index + 1} Ata")
        self.setMinimumWidth(440)
        self._build_ui(profiles or [])

    def _build_ui(self, profiles):
        lay = QVBoxLayout(self)
        tabs = QTabWidget()

        self._tabs_data = {}
        for key, label in [("cw", "◄► CW (Saat Yönü)"), ("ccw", "◄ CCW (Ters)"), ("push", "● Push")]:
            tab = QWidget()
            t_lay = QVBoxLayout(tab)

            cfg = getattr(self._config, key)
            form = QFormLayout()
            lbl_edit = QLineEdit(cfg.label)
            lbl_edit.setPlaceholderText("Etiket")
            form.addRow("Etiket:", lbl_edit)
            t_lay.addLayout(form)

            type_row = QHBoxLayout()
            type_row.addWidget(QLabel("Eylem:"))
            combo = QComboBox()
            for k, v in ACTION_LABELS.items():
                combo.addItem(v, k)
            combo.setCurrentIndex(max(0, combo.findData(cfg.action_type)))
            type_row.addWidget(combo)
            type_row.addStretch()
            t_lay.addLayout(type_row)

            grp = QGroupBox("Ayarlar")
            g_lay = QVBoxLayout(grp)
            action_w = ActionConfigWidget(profiles)
            action_w.load(cfg)
            g_lay.addWidget(action_w)
            t_lay.addWidget(grp)

            combo.currentIndexChanged.connect(
                lambda _, aw=action_w, cb=combo: aw.show_type(cb.currentData())
            )

            tabs.addTab(tab, label)
            self._tabs_data[key] = (combo, lbl_edit, action_w)

        lay.addWidget(tabs)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Ok).setObjectName("primary")
        lay.addWidget(btns)

    def _accept(self):
        for key, (combo, lbl_edit, action_w) in self._tabs_data.items():
            cfg = getattr(self._config, key)
            cfg.label = lbl_edit.text().strip()
            cfg.action_type = combo.currentData()
            action_w.save(cfg)
        self.accept()

    def result_config(self) -> EncoderConfig:
        return self._config


# ─────────────────────────── Display settings dialog ─────────────────────────

class DisplaySettingsDialog(QDialog):
    def __init__(self, module_config: ModuleConfig, profile_name: str = "", parent=None):
        super().__init__(parent)
        self._config = module_config
        self.setWindowTitle(f"Ekran Ayarları – {module_config.name}")
        self.setMinimumWidth(380)
        self._build_ui(profile_name)

    def _build_ui(self, profile_name: str):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        form = QFormLayout()
        self._mode_combo = QComboBox()
        for key, label in DISPLAY_MODES.items():
            self._mode_combo.addItem(label, key)
        idx = self._mode_combo.findData(self._config.display_mode)
        self._mode_combo.setCurrentIndex(max(0, idx))
        form.addRow("Gösterim:", self._mode_combo)

        self._text_edit = QLineEdit(self._config.display_custom_text)
        self._text_edit.setPlaceholderText("Özel metin…")
        self._text_edit.setEnabled(self._config.display_mode == DISPLAY_CUSTOM)
        form.addRow("Özel metin:", self._text_edit)
        lay.addLayout(form)

        self._preview = OLEDPreviewWidget(
            mode=self._config.display_mode,
            custom_text=self._config.display_custom_text,
            profile_name=profile_name or "Profil",
        )
        preview_row = QHBoxLayout()
        preview_row.addWidget(QLabel("Önizleme:"))
        preview_row.addWidget(self._preview)
        preview_row.addStretch()
        lay.addLayout(preview_row)

        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._text_edit.textChanged.connect(self._on_text_changed)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Ok).setObjectName("primary")
        lay.addWidget(btns)

    def _on_mode_changed(self):
        mode = self._mode_combo.currentData()
        self._text_edit.setEnabled(mode == DISPLAY_CUSTOM)
        self._preview.update_settings(mode, self._text_edit.text())

    def _on_text_changed(self, text: str):
        self._preview.update_settings(self._mode_combo.currentData(), text)

    def _accept(self):
        self._config.display_mode = self._mode_combo.currentData()
        self._config.display_custom_text = self._text_edit.text().strip()
        self.accept()
