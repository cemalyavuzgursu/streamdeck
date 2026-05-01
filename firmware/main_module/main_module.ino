/*
 * MacroPad — Ana Modül Firmware (ESP32-C3 Super Mini)
 *
 * Donanım:
 *   - 6× mekanik buton: GPIO 0, 1, 3, 4, 10, 21 → GND
 *   - SSD1306 OLED 128×64, I2C: SDA=GPIO5, SCL=GPIO6
 *
 * Mimari:
 *   ESP32-C3'ün USB Serial/JTAG controller'ı sadece CDC destekler,
 *   USB-HID yok. Bu yüzden firmware buton olaylarını JSON olarak
 *   PC'ye gönderir; aksiyonların gerçekleştirilmesi (klavye basışı,
 *   uygulama açma, profil değiştirme) PC tarafındaki MacroPad uygu-
 *   lamasının görevidir.
 *
 * Arduino IDE ayarları:
 *   - Board: ESP32C3 Dev Module
 *   - USB CDC On Boot: Enabled
 *   - Diğer ayarlar varsayılan kalabilir
 *
 * Kütüphaneler (Library Manager):
 *   - ArduinoJson
 *   - U8g2
 */

#include <Arduino.h>
#include <Wire.h>
#include <U8g2lib.h>
#include <ArduinoJson.h>

// ─────────────── Pin map ───────────────
constexpr uint8_t BTN_COUNT = 6;
constexpr uint8_t BTN_PINS[BTN_COUNT] = {0, 1, 3, 4, 10, 21};
constexpr uint8_t I2C_SDA = 5;
constexpr uint8_t I2C_SCL = 6;

// ─────────────── Globals ───────────────
U8G2_SSD1306_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);

String profileName = "Hazır";
bool btnState[BTN_COUNT] = {false};
unsigned long btnDebounce[BTN_COUNT] = {0};
constexpr unsigned long DEBOUNCE_MS = 30;

// ─────────────── OLED ───────────────
void drawScreen(const String& bottom = "USB connected") {
  oled.clearBuffer();
  oled.setFont(u8g2_font_helvB12_tf);
  oled.drawStr(2, 16, "MacroPad");
  oled.setFont(u8g2_font_helvR10_tf);
  oled.drawStr(2, 36, profileName.c_str());
  oled.setFont(u8g2_font_5x7_tf);
  oled.drawStr(2, 60, bottom.c_str());
  oled.sendBuffer();
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

void sendButtonEvent(int idx, bool pressed) {
  StaticJsonDocument<128> doc;
  doc["type"] = "button_event";
  doc["module_id"] = "main";
  doc["index"] = idx;
  doc["pressed"] = pressed;
  serializeJson(doc, Serial);
  Serial.println();
}

void handleConfig(JsonVariant root) {
  profileName = String((const char*)(root["profile_name"] | "Profil"));
  drawScreen("config OK");
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
      sendButtonEvent(i, pressed);
      if (pressed) drawScreen("btn " + String(i + 1));
    }
  }

  delay(2);
}
