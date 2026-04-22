# MacroPad Configurator

Windows masaüstü uygulaması — ESP32-C3 tabanlı modüler makropad için.

## Özellikler

| Özellik | Detay |
|---|---|
| Modül Yönetimi | Bağlı modülleri otomatik algıla, yukarı/aşağı taşı |
| Buton Atama | Kısayol, medya kontrolü, uygulama aç, makro |
| Encoder Atama | CW / CCW / Push ayrı ayrı |
| OLED Önizleme | Saat, profil adı, ses seviyesi, özel metin |
| Profiller | JSON kaydet/yükle, içe/dışa aktar, kopyala |
| Otomatik Güncelleme | GitHub Releases üzerinden uygulama + firmware |
| Firmware Flash | esptool ile doğrudan ESP32-C3'e yükle |

## Kurulum

```bash
git clone https://github.com/cemalyavuzgursu/streamdeck.git
cd streamdeck
pip install -r requirements.txt
python src/main.py
```

## EXE Olarak Çalıştırma

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name MacroPad src/main.py
# dist/MacroPad.exe hazır
```

## Dizin Yapısı

```
src/
├── main.py                   # Giriş noktası
├── ui/
│   ├── main_window.py        # Ana pencere
│   ├── module_widget.py      # Modül görsel bileşeni
│   └── profile_editor.py     # Buton/encoder atama diyalogları
└── core/
    ├── device_manager.py     # USB seri iletişim
    ├── profile_manager.py    # Profil yönetimi (JSON)
    ├── updater.py            # Otomatik güncelleme
    └── firmware_flasher.py   # esptool firmware flash
```

Ayarlar: `%APPDATA%\MacroPad\`

## ESP32 Seri Protokolü

**PC → ESP32:**
```json
{"cmd": "discover"}
{"cmd": "config", "profile_name": "Gaming", "modules": [...]}
```

**ESP32 → PC:**
```json
{"type": "modules", "modules": [
  {"id": "main", "type": "main", "buttons": 4, "encoders": 1, "display": true},
  {"id": "0x20", "type": "slave", "buttons": 8, "encoders": 0, "display": false, "addr": 32}
]}
```

## GitHub Actions

`v1.2.0` gibi bir etiket push'ladığınızda `.github/workflows/build.yml` otomatik olarak
`MacroPad.exe` derler ve [GitHub Release](https://github.com/cemalyavuzgursu/streamdeck/releases) olarak yayınlar.

```bash
git tag v1.0.0
git push origin v1.0.0
```

## Gereksinimler

- Python 3.10+
- PyQt5
- pyserial
- requests
- esptool (firmware flash için)
