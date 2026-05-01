/*
 * MacroPad — Ana Modül Firmware (ESP32-C3 Super Mini)
 *
 * Donanım:
 *   - ESP32-C3 Super Mini (yerleşik USB CDC + HID üzerinden)
 *   - 6× mekanik buton (GPIO 0, 1, 3, 4, 10, 21 — GND'ye)
 *   - SSD1306 OLED 128×64, I2C (SDA=GPIO5, SCL=GPIO6)
 *
 * Notlar:
 *   - GPIO 9 BOOT butonudur — kullanma!
 *   - GPIO 2, 8 strapping pinleridir — boot sırasında HIGH olmalı
 *
 * Arduino IDE ayarları:
 *   - Board: "ESP32C3 Dev Module"
 *   - USB CDC On Boot: Enabled
 *   - USB Mode: "USB-OTG (TinyUSB)"
 *   - Upload Mode: "USB-OTG CDC (TinyUSB)"
 *   - Flash Size: 4MB
 *
 * Gerekli kütüphaneler (Library Manager):
 *   - ArduinoJson
 *   - U8g2
 */

#include <Arduino.h>
#include <Wire.h>
#include <U8g2lib.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <USB.h>
#include <USBHIDKeyboard.h>
#include <USBHIDConsumerControl.h>

// ─────────────── Pin map ───────────────
constexpr uint8_t BTN_COUNT = 6;
constexpr uint8_t BTN_PINS[BTN_COUNT] = {0, 1, 3, 4, 10, 21};
constexpr uint8_t I2C_SDA = 5;
constexpr uint8_t I2C_SCL = 6;

// ─────────────── Globals ───────────────
USBHIDKeyboard kbd;
USBHIDConsumerControl cc;
U8G2_SSD1306_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);
Preferences prefs;

struct ButtonAction {
  String type = "none";
  String data = "{}";
  String label = "";
};

ButtonAction actions[BTN_COUNT];
String profileName = "Varsayılan";
bool btnState[BTN_COUNT] = {false};
unsigned long btnDebounce[BTN_COUNT] = {0};
constexpr unsigned long DEBOUNCE_MS = 30;

// ─────────────── Persistence ───────────────
void saveConfig() {
  prefs.putString("profile", profileName);
  for (int i = 0; i < BTN_COUNT; i++) {
    String p = "b" + String(i);
    prefs.putString((p + "t").c_str(), actions[i].type);
    prefs.putString((p + "d").c_str(), actions[i].data);
    prefs.putString((p + "l").c_str(), actions[i].label);
  }
}

void loadConfig() {
  profileName = prefs.getString("profile", "Varsayılan");
  for (int i = 0; i < BTN_COUNT; i++) {
    String p = "b" + String(i);
    actions[i].type = prefs.getString((p + "t").c_str(), "none");
    actions[i].data = prefs.getString((p + "d").c_str(), "{}");
    actions[i].label = prefs.getString((p + "l").c_str(), "");
  }
}

// ─────────────── OLED ───────────────
void drawScreen(const String& bottomLine = "") {
  oled.clearBuffer();
  oled.setFont(u8g2_font_helvB12_tf);
  oled.drawStr(2, 16, "MacroPad");
  oled.setFont(u8g2_font_helvR10_tf);
  oled.drawStr(2, 36, profileName.c_str());
  oled.setFont(u8g2_font_5x7_tf);
  oled.drawStr(2, 60, bottomLine.length() ? bottomLine.c_str() : "USB connected");
  oled.sendBuffer();
}

// ─────────────── HID helpers ───────────────
uint8_t keyForToken(const String& tok) {
  if (tok == "esc") return KEY_ESC;
  if (tok == "enter") return KEY_RETURN;
  if (tok == "tab") return KEY_TAB;
  if (tok == "backspace") return KEY_BACKSPACE;
  if (tok == "space") return ' ';
  if (tok == "left") return KEY_LEFT_ARROW;
  if (tok == "right") return KEY_RIGHT_ARROW;
  if (tok == "up") return KEY_UP_ARROW;
  if (tok == "down") return KEY_DOWN_ARROW;
  if (tok == "delete") return KEY_DELETE;
  if (tok == "home") return KEY_HOME;
  if (tok == "end") return KEY_END;
  if (tok == "pageup") return KEY_PAGE_UP;
  if (tok == "pagedown") return KEY_PAGE_DOWN;
  if (tok.startsWith("f") && tok.length() <= 3) {
    int n = tok.substring(1).toInt();
    if (n >= 1 && n <= 12) return KEY_F1 + (n - 1);
  }
  if (tok.length() == 1) return tok[0];
  return 0;
}

void executeShortcut(const String& keys) {
  bool ctrl=false, alt=false, shift=false, gui=false;
  String keyTok;
  int start = 0;
  while (true) {
    int plus = keys.indexOf('+', start);
    String tok = (plus >= 0) ? keys.substring(start, plus) : keys.substring(start);
    tok.toLowerCase();
    tok.trim();
    if (tok == "ctrl") ctrl = true;
    else if (tok == "alt") alt = true;
    else if (tok == "shift") shift = true;
    else if (tok == "win" || tok == "gui" || tok == "cmd") gui = true;
    else keyTok = tok;
    if (plus < 0) break;
    start = plus + 1;
  }
  if (ctrl) kbd.press(KEY_LEFT_CTRL);
  if (alt) kbd.press(KEY_LEFT_ALT);
  if (shift) kbd.press(KEY_LEFT_SHIFT);
  if (gui) kbd.press(KEY_LEFT_GUI);
  uint8_t k = keyForToken(keyTok);
  if (k) kbd.press(k);
  delay(25);
  kbd.releaseAll();
}

void executeMedia(const String& action) {
  uint16_t code = 0;
  if (action == "play_pause") code = 0xCD;
  else if (action == "next_track") code = 0xB5;
  else if (action == "prev_track") code = 0xB6;
  else if (action == "stop") code = 0xB7;
  else if (action == "volume_up") code = 0xE9;
  else if (action == "volume_down") code = 0xEA;
  else if (action == "mute") code = 0xE2;
  if (!code) return;
  cc.press(code);
  delay(25);
  cc.release();
}

void executeMacro(const String& sequence) {
  // Lines: "ctrl+c" / "wait:200" / "type:Hello"
  int start = 0;
  while (start < (int)sequence.length()) {
    int nl = sequence.indexOf('\n', start);
    String line = (nl >= 0) ? sequence.substring(start, nl) : sequence.substring(start);
    line.trim();
    if (line.startsWith("wait:")) {
      delay(line.substring(5).toInt());
    } else if (line.startsWith("type:")) {
      kbd.print(line.substring(5));
    } else if (line.length()) {
      executeShortcut(line);
    }
    if (nl < 0) break;
    start = nl + 1;
  }
}

void executeAction(int idx) {
  if (idx < 0 || idx >= BTN_COUNT) return;
  ButtonAction& a = actions[idx];
  drawScreen("→ " + (a.label.length() ? a.label : a.type));

  StaticJsonDocument<512> data;
  deserializeJson(data, a.data);

  if (a.type == "shortcut") {
    const char* keys = data["keys"];
    if (keys) executeShortcut(String(keys));
  } else if (a.type == "media") {
    const char* act = data["action"];
    if (act) executeMedia(String(act));
  } else if (a.type == "macro") {
    const char* seq = data["sequence"];
    if (seq) executeMacro(String(seq));
  }
  // app_launch ve profile_switch host (PC) tarafında yorumlanır.
}

// ─────────────── Protocol ───────────────
void sendModules() {
  StaticJsonDocument<256> doc;
  doc["type"] = "modules";
  JsonArray arr = doc.createNestedArray("modules");
  JsonObject m = arr.createNestedObject();
  m["id"] = "main";
  m["type"] = "main";
  m["name"] = "Ana Modül";
  m["buttons"] = BTN_COUNT;
  m["encoders"] = 0;
  m["display"] = true;
  serializeJson(doc, Serial);
  Serial.println();
}

void handleConfig(JsonVariant root) {
  profileName = String((const char*)(root["profile_name"] | "Profil"));
  JsonArray modules = root["modules"];
  for (JsonObject mod : modules) {
    String mid = String((const char*)(mod["module_id"] | ""));
    if (mid != "main") continue;
    JsonArray btns = mod["buttons"];
    int n = min((int)btns.size(), (int)BTN_COUNT);
    for (int i = 0; i < n; i++) {
      actions[i].type = String((const char*)(btns[i]["action_type"] | "none"));
      actions[i].label = String((const char*)(btns[i]["label"] | ""));
      String dataStr;
      JsonVariant ad = btns[i]["action_data"];
      if (ad.is<JsonObject>()) {
        serializeJson(ad, dataStr);
      } else {
        dataStr = "{}";
      }
      actions[i].data = dataStr;
    }
  }
  saveConfig();
  drawScreen("config saved");
}

void handleLine(const String& line) {
  StaticJsonDocument<2048> doc;
  if (deserializeJson(doc, line) != DeserializationError::Ok) return;
  String cmd = String((const char*)(doc["cmd"] | ""));
  if (cmd == "discover") sendModules();
  else if (cmd == "config") handleConfig(doc.as<JsonVariant>());
}

// ─────────────── Setup / Loop ───────────────
void setup() {
  for (int i = 0; i < BTN_COUNT; i++) pinMode(BTN_PINS[i], INPUT_PULLUP);

  Wire.begin(I2C_SDA, I2C_SCL);
  oled.begin();

  prefs.begin("macropad", false);
  loadConfig();

  USB.begin();
  kbd.begin();
  cc.begin();

  Serial.begin(115200);
  unsigned long t0 = millis();
  while (!Serial && (millis() - t0) < 1500) delay(10);

  drawScreen("Ready");
}

void loop() {
  // Serial line buffer
  static String buf;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (buf.length()) handleLine(buf);
      buf = "";
    } else if (buf.length() < 4096) {
      buf += c;
    }
  }

  // Buton tarama (debounce)
  unsigned long now = millis();
  for (int i = 0; i < BTN_COUNT; i++) {
    bool pressed = !digitalRead(BTN_PINS[i]);
    if (pressed != btnState[i] && (now - btnDebounce[i]) > DEBOUNCE_MS) {
      btnDebounce[i] = now;
      btnState[i] = pressed;
      if (pressed) executeAction(i);
    }
  }

  delay(2);
}
