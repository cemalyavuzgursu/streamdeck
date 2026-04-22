import math
from datetime import datetime
from typing import Optional

from PyQt5.QtCore import QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.profile_manager import ButtonConfig, EncoderConfig, ModuleConfig
from src.utils.constants import (
    ACTION_LABELS,
    ACTION_NONE,
    DISPLAY_CLOCK,
    DISPLAY_CUSTOM,
    DISPLAY_MODES,
    DISPLAY_PROFILE,
    DISPLAY_VOLUME,
)


class ButtonKeyWidget(QPushButton):
    """Single clickable key in a module."""

    def __init__(self, config: ButtonConfig, index: int, parent=None):
        super().__init__(parent)
        self._config = config
        self._index = index
        self.setFixedSize(62, 56)
        self.setCursor(Qt.PointingHandCursor)
        self._refresh()

    def _refresh(self):
        assigned = self._config.action_type != ACTION_NONE
        label = self._config.label or f"K{self._index + 1}"
        label = label[:9] if len(label) <= 9 else label[:8] + "…"
        self.setText(label)
        if assigned:
            self.setStyleSheet(
                "QPushButton{"
                "background:#89b4fa;color:#1e1e2e;font-weight:bold;font-size:10px;"
                "border-radius:10px;border:2px solid #b4d0ff;}"
                "QPushButton:hover{background:#b4d0ff;}"
                "QPushButton:pressed{background:#74a8e8;}"
            )
            action_short = ACTION_LABELS.get(self._config.action_type, "")
            self.setToolTip(f"{label}\n{action_short}")
        else:
            self.setStyleSheet(
                "QPushButton{"
                "background:#313244;color:#6c7086;font-size:10px;"
                "border-radius:10px;border:2px solid #45475a;}"
                "QPushButton:hover{background:#45475a;color:#cdd6f4;}"
                "QPushButton:pressed{background:#585b70;}"
            )
            self.setToolTip(f"K{self._index + 1} – Atanmamış")

    def update_config(self, config: ButtonConfig):
        self._config = config
        self._refresh()


class EncoderWidget(QWidget):
    """Clickable encoder visual (CW / CCW / Push)."""

    cw_clicked = pyqtSignal()
    ccw_clicked = pyqtSignal()
    push_clicked = pyqtSignal()

    def __init__(self, config: EncoderConfig, index: int, parent=None):
        super().__init__(parent)
        self._config = config
        self._index = index
        self.setFixedSize(180, 70)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._btn_ccw = self._make_enc_btn("◄ CCW", "#cba6f7")
        self._btn_push = self._make_enc_btn("●\nPush", "#fab387")
        self._btn_cw = self._make_enc_btn("CW ►", "#cba6f7")

        self._btn_ccw.clicked.connect(self.ccw_clicked)
        self._btn_push.clicked.connect(self.push_clicked)
        self._btn_cw.clicked.connect(self.cw_clicked)

        layout.addWidget(self._btn_ccw)
        layout.addWidget(self._btn_push)
        layout.addWidget(self._btn_cw)
        self._refresh()

    def _make_enc_btn(self, text: str, accent: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(54, 54)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton{{background:#313244;color:{accent};font-size:10px;font-weight:bold;"
            f"border-radius:27px;border:2px solid {accent};}}"
            f"QPushButton:hover{{background:{accent};color:#1e1e2e;}}"
            f"QPushButton:pressed{{background:#585b70;}}"
        )
        return btn

    def _refresh(self):
        def tip(cfg: ButtonConfig, name: str) -> str:
            if cfg.action_type == ACTION_NONE:
                return f"{name} – Atanmamış"
            return f"{name}: {ACTION_LABELS.get(cfg.action_type, cfg.action_type)}"

        self._btn_ccw.setToolTip(tip(self._config.ccw, "CCW"))
        self._btn_push.setToolTip(tip(self._config.push, "Push"))
        self._btn_cw.setToolTip(tip(self._config.cw, "CW"))

    def update_config(self, config: EncoderConfig):
        self._config = config
        self._refresh()


class OLEDPreviewWidget(QWidget):
    """128×64 OLED screen preview scaled to 2×."""

    W, H, SCALE = 128, 64, 2

    def __init__(self, mode: str = DISPLAY_CLOCK, custom_text: str = "", profile_name: str = "Profil", parent=None):
        super().__init__(parent)
        self.mode = mode
        self.custom_text = custom_text
        self.profile_name = profile_name
        self.setFixedSize(self.W * self.SCALE, self.H * self.SCALE)
        self.setToolTip("OLED Ekran Önizleme")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(1000)

    def update_settings(self, mode: str, custom_text: str = "", profile_name: str = ""):
        self.mode = mode
        self.custom_text = custom_text
        if profile_name:
            self.profile_name = profile_name
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.scale(self.SCALE, self.SCALE)

        # Screen background
        p.fillRect(0, 0, self.W, self.H, QColor("#000000"))
        p.setPen(QColor("#ffffff"))

        font_mono = QFont("Consolas", 1)

        if self.mode == DISPLAY_CLOCK:
            font_mono.setPointSize(22)
            font_mono.setBold(True)
            p.setFont(font_mono)
            now = datetime.now().strftime("%H:%M")
            p.drawText(QRect(0, 4, 128, 40), Qt.AlignHCenter | Qt.AlignVCenter, now)
            font_mono.setPointSize(9)
            font_mono.setBold(False)
            p.setFont(font_mono)
            date_str = datetime.now().strftime("%d.%m.%Y")
            p.drawText(QRect(0, 48, 128, 14), Qt.AlignHCenter | Qt.AlignVCenter, date_str)

        elif self.mode == DISPLAY_PROFILE:
            font_mono.setPointSize(8)
            p.setFont(font_mono)
            p.setPen(QColor("#888888"))
            p.drawText(QRect(4, 4, 120, 16), Qt.AlignLeft | Qt.AlignVCenter, "AKTİF PROFİL")
            p.setPen(QColor("#ffffff"))
            font_mono.setPointSize(12)
            font_mono.setBold(True)
            p.setFont(font_mono)
            name = self.profile_name or "---"
            p.drawText(QRect(4, 22, 120, 38), Qt.AlignHCenter | Qt.AlignVCenter, name)

        elif self.mode == DISPLAY_VOLUME:
            font_mono.setPointSize(8)
            p.setFont(font_mono)
            p.setPen(QColor("#888888"))
            p.drawText(QRect(4, 4, 120, 14), Qt.AlignLeft | Qt.AlignVCenter, "SES SEVİYESİ")
            vol = 65
            bar_x, bar_y, bar_h = 4, 24, 18
            bar_full_w = 120
            filled_w = int(bar_full_w * vol / 100)
            p.setPen(Qt.NoPen)
            p.fillRect(bar_x, bar_y, filled_w, bar_h, QColor("#89b4fa"))
            p.setPen(QPen(QColor("#444444"), 1))
            p.drawRect(bar_x, bar_y, bar_full_w, bar_h)
            p.setPen(QColor("#ffffff"))
            font_mono.setPointSize(10)
            font_mono.setBold(True)
            p.setFont(font_mono)
            p.drawText(QRect(4, 46, 120, 16), Qt.AlignHCenter | Qt.AlignVCenter, f"{vol}%")

        elif self.mode == DISPLAY_CUSTOM:
            font_mono.setPointSize(9)
            p.setFont(font_mono)
            text = self.custom_text.strip() or "(boş)"
            p.drawText(QRect(4, 4, 120, 56), Qt.AlignHCenter | Qt.AlignVCenter | Qt.TextWordWrap, text)

        # Screen border
        p.setPen(QPen(QColor("#333333"), 1))
        p.drawRect(0, 0, self.W - 1, self.H - 1)


class ModuleWidget(QFrame):
    """Full visual representation of one macropad module."""

    button_clicked = pyqtSignal(object, int)   # module_config, button_index
    encoder_cw_clicked = pyqtSignal(object, int)
    encoder_ccw_clicked = pyqtSignal(object, int)
    encoder_push_clicked = pyqtSignal(object, int)
    display_settings_clicked = pyqtSignal(object)  # module_config
    move_up_clicked = pyqtSignal(object)
    move_down_clicked = pyqtSignal(object)

    def __init__(self, module_config: ModuleConfig, parent=None):
        super().__init__(parent)
        self._config = module_config
        self._btn_widgets: list = []
        self._enc_widgets: list = []
        self._oled_widget: Optional[OLEDPreviewWidget] = None
        self._build_ui()

    @property
    def config(self) -> ModuleConfig:
        return self._config

    def _build_ui(self):
        self.setFrameShape(QFrame.Box)
        self.setStyleSheet(
            "ModuleWidget{"
            "background-color:#252535;"
            "border:1px solid #45475a;"
            "border-radius:12px;"
            "}"
        )
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(10)

        # ── Header ──────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(6)

        icon_lbl = QLabel("🔌" if self._config.module_type == "main" else "⬡")
        icon_lbl.setStyleSheet("font-size:16px;")
        header.addWidget(icon_lbl)

        name_lbl = QLabel(f"<b>{self._config.name}</b>")
        name_lbl.setStyleSheet("color:#cdd6f4;font-size:13px;")
        header.addWidget(name_lbl)

        info_lbl = QLabel(
            f"  {self._config.button_count} buton"
            + (f" · {self._config.encoder_count} encoder" if self._config.encoder_count else "")
            + (" · OLED" if self._config.has_display else "")
        )
        info_lbl.setStyleSheet("color:#6c7086;font-size:11px;")
        header.addWidget(info_lbl)
        header.addStretch()

        btn_up = QPushButton("▲")
        btn_up.setFixedSize(26, 26)
        btn_up.setToolTip("Yukarı taşı")
        btn_up.setStyleSheet(
            "QPushButton{background:#313244;color:#6c7086;border-radius:5px;border:none;font-size:11px;}"
            "QPushButton:hover{background:#45475a;color:#cdd6f4;}"
        )
        btn_up.clicked.connect(lambda: self.move_up_clicked.emit(self._config))
        header.addWidget(btn_up)

        btn_down = QPushButton("▼")
        btn_down.setFixedSize(26, 26)
        btn_down.setToolTip("Aşağı taşı")
        btn_down.setStyleSheet(
            "QPushButton{background:#313244;color:#6c7086;border-radius:5px;border:none;font-size:11px;}"
            "QPushButton:hover{background:#45475a;color:#cdd6f4;}"
        )
        btn_down.clicked.connect(lambda: self.move_down_clicked.emit(self._config))
        header.addWidget(btn_down)
        root.addLayout(header)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color:#45475a;")
        root.addWidget(div)

        # ── Buttons grid ────────────────────────────────────────
        if self._config.button_count > 0:
            cols = min(4, self._config.button_count)
            grid = QGridLayout()
            grid.setSpacing(6)
            self._btn_widgets = []
            for i, btn_cfg in enumerate(self._config.buttons):
                w = ButtonKeyWidget(btn_cfg, i)
                idx = i
                w.clicked.connect(lambda _=False, ix=idx: self.button_clicked.emit(self._config, ix))
                self._btn_widgets.append(w)
                grid.addWidget(w, i // cols, i % cols)
            root.addLayout(grid)

        # ── Encoders ────────────────────────────────────────────
        if self._config.encoder_count > 0:
            enc_layout = QHBoxLayout()
            enc_layout.setSpacing(10)
            self._enc_widgets = []
            for i, enc_cfg in enumerate(self._config.encoders):
                lbl = QLabel(f"Enc {i + 1}")
                lbl.setStyleSheet("color:#6c7086;font-size:11px;min-width:34px;")
                enc_layout.addWidget(lbl)
                w = EncoderWidget(enc_cfg, i)
                idx = i
                w.cw_clicked.connect(lambda ix=idx: self.encoder_cw_clicked.emit(self._config, ix))
                w.ccw_clicked.connect(lambda ix=idx: self.encoder_ccw_clicked.emit(self._config, ix))
                w.push_clicked.connect(lambda ix=idx: self.encoder_push_clicked.emit(self._config, ix))
                self._enc_widgets.append(w)
                enc_layout.addWidget(w)
            enc_layout.addStretch()
            root.addLayout(enc_layout)

        # ── OLED preview ─────────────────────────────────────────
        if self._config.has_display:
            disp_row = QHBoxLayout()
            disp_row.setSpacing(10)

            self._oled_widget = OLEDPreviewWidget(
                mode=self._config.display_mode,
                custom_text=self._config.display_custom_text,
            )
            disp_row.addWidget(self._oled_widget)
            disp_row.addStretch()

            settings_btn = QPushButton("⚙ Ekran Ayarları")
            settings_btn.setObjectName("primary")
            settings_btn.setFixedHeight(32)
            settings_btn.clicked.connect(lambda: self.display_settings_clicked.emit(self._config))
            disp_row.addWidget(settings_btn, 0, Qt.AlignBottom)
            root.addLayout(disp_row)

    def refresh(self):
        """Refresh all child widgets from the current config."""
        for i, w in enumerate(self._btn_widgets):
            if i < len(self._config.buttons):
                w.update_config(self._config.buttons[i])
        for i, w in enumerate(self._enc_widgets):
            if i < len(self._config.encoders):
                w.update_config(self._config.encoders[i])
        if self._oled_widget:
            self._oled_widget.update_settings(
                self._config.display_mode, self._config.display_custom_text
            )
