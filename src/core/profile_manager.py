import json
import uuid
from pathlib import Path
from typing import List, Optional

from src.utils.constants import PROFILES_DIR, ACTION_NONE, DISPLAY_CLOCK


class ButtonConfig:
    def __init__(self):
        self.action_type: str = ACTION_NONE
        self.action_data: dict = {}
        self.label: str = ""

    def to_dict(self) -> dict:
        return {"action_type": self.action_type, "action_data": self.action_data, "label": self.label}

    @classmethod
    def from_dict(cls, d: dict) -> "ButtonConfig":
        c = cls()
        c.action_type = d.get("action_type", ACTION_NONE)
        c.action_data = d.get("action_data", {})
        c.label = d.get("label", "")
        return c


class EncoderConfig:
    def __init__(self):
        self.cw = ButtonConfig()
        self.ccw = ButtonConfig()
        self.push = ButtonConfig()

    def to_dict(self) -> dict:
        return {"cw": self.cw.to_dict(), "ccw": self.ccw.to_dict(), "push": self.push.to_dict()}

    @classmethod
    def from_dict(cls, d: dict) -> "EncoderConfig":
        c = cls()
        c.cw = ButtonConfig.from_dict(d.get("cw", {}))
        c.ccw = ButtonConfig.from_dict(d.get("ccw", {}))
        c.push = ButtonConfig.from_dict(d.get("push", {}))
        return c


class ModuleConfig:
    def __init__(
        self,
        module_id: str = "",
        module_type: str = "slave",
        name: str = "",
        button_count: int = 0,
        encoder_count: int = 0,
        has_display: bool = False,
    ):
        self.module_id = module_id
        self.module_type = module_type
        self.name = name or f"Modül ({module_id})"
        self.button_count = button_count
        self.encoder_count = encoder_count
        self.has_display = has_display
        self.buttons: List[ButtonConfig] = [ButtonConfig() for _ in range(button_count)]
        self.encoders: List[EncoderConfig] = [EncoderConfig() for _ in range(encoder_count)]
        self.display_mode: str = DISPLAY_CLOCK
        self.display_custom_text: str = ""

    def to_dict(self) -> dict:
        return {
            "module_id": self.module_id,
            "module_type": self.module_type,
            "name": self.name,
            "button_count": self.button_count,
            "encoder_count": self.encoder_count,
            "has_display": self.has_display,
            "buttons": [b.to_dict() for b in self.buttons],
            "encoders": [e.to_dict() for e in self.encoders],
            "display_mode": self.display_mode,
            "display_custom_text": self.display_custom_text,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ModuleConfig":
        c = cls(
            module_id=d.get("module_id", ""),
            module_type=d.get("module_type", "slave"),
            name=d.get("name", ""),
            button_count=d.get("button_count", 0),
            encoder_count=d.get("encoder_count", 0),
            has_display=d.get("has_display", False),
        )
        saved_buttons = d.get("buttons", [])
        for i, btn in enumerate(saved_buttons):
            if i < len(c.buttons):
                c.buttons[i] = ButtonConfig.from_dict(btn)
        saved_encoders = d.get("encoders", [])
        for i, enc in enumerate(saved_encoders):
            if i < len(c.encoders):
                c.encoders[i] = EncoderConfig.from_dict(enc)
        c.display_mode = d.get("display_mode", DISPLAY_CLOCK)
        c.display_custom_text = d.get("display_custom_text", "")
        return c


class Profile:
    def __init__(self, name: str = "Yeni Profil"):
        self.id: str = str(uuid.uuid4())
        self.name: str = name
        self.modules: List[ModuleConfig] = []

    def get_module(self, module_id: str) -> Optional[ModuleConfig]:
        for m in self.modules:
            if m.module_id == module_id:
                return m
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "modules": [m.to_dict() for m in self.modules],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        p = cls(name=d.get("name", "Profil"))
        p.id = d.get("id", str(uuid.uuid4()))
        p.modules = [ModuleConfig.from_dict(m) for m in d.get("modules", [])]
        return p

    def to_esp_config(self) -> dict:
        """Serialize to the JSON format sent to ESP32."""
        return {
            "cmd": "config",
            "profile_name": self.name,
            "modules": [
                {
                    "id": mod.module_id,
                    "buttons": [
                        {"type": b.action_type, **b.action_data, "label": b.label}
                        for b in mod.buttons
                    ],
                    "encoders": [
                        {
                            "cw": {"type": e.cw.action_type, **e.cw.action_data},
                            "ccw": {"type": e.ccw.action_type, **e.ccw.action_data},
                            "push": {"type": e.push.action_type, **e.push.action_data},
                        }
                        for e in mod.encoders
                    ],
                    "display": {"mode": mod.display_mode, "text": mod.display_custom_text},
                }
                for mod in self.modules
            ],
        }


class ProfileManager:
    def __init__(self):
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        self.profiles: List[Profile] = []
        self.active_profile_id: Optional[str] = None
        self._load_all()

    def _load_all(self):
        self.profiles = []
        for f in sorted(PROFILES_DIR.glob("*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    self.profiles.append(Profile.from_dict(json.load(fp)))
            except Exception:
                pass
        if not self.profiles:
            default = Profile("Varsayılan")
            self.profiles.append(default)
            self.save_profile(default)
        if not self.active_profile_id or not self.get_profile(self.active_profile_id):
            self.active_profile_id = self.profiles[0].id

    def save_profile(self, profile: Profile):
        path = PROFILES_DIR / f"{profile.id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)

    def delete_profile(self, profile_id: str):
        path = PROFILES_DIR / f"{profile_id}.json"
        if path.exists():
            path.unlink()
        self.profiles = [p for p in self.profiles if p.id != profile_id]
        if not self.profiles:
            self._load_all()
        elif self.active_profile_id == profile_id:
            self.active_profile_id = self.profiles[0].id

    def new_profile(self, name: str = "Yeni Profil") -> Profile:
        profile = Profile(name)
        self.profiles.append(profile)
        self.save_profile(profile)
        return profile

    def duplicate_profile(self, profile_id: str) -> Optional[Profile]:
        src = self.get_profile(profile_id)
        if not src:
            return None
        new_p = Profile.from_dict(src.to_dict())
        new_p.id = str(uuid.uuid4())
        new_p.name = src.name + " (Kopya)"
        self.profiles.append(new_p)
        self.save_profile(new_p)
        return new_p

    def get_profile(self, profile_id: str) -> Optional[Profile]:
        for p in self.profiles:
            if p.id == profile_id:
                return p
        return None

    def get_active_profile(self) -> Optional[Profile]:
        return self.get_profile(self.active_profile_id) or (self.profiles[0] if self.profiles else None)
