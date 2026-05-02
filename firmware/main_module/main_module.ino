/*
 * MacroPad — Ana Modül Firmware (ESP32-C3 Super Mini)
 *
 * Donanım:
 *   - 6× mekanik buton: kullanıcının pin map'ine göre (BTN_PINS)
 *   - SSD1306 OLED 128×64, I2C: SDA=GPIO5, SCL=GPIO6
 *
 * Mimari:
 *   ESP32-C3'ün USB Serial/JTAG controller'ı sadece CDC destekler,
 *   USB-HID yok. Bu yüzden firmware buton olaylarını JSON olarak
 *   PC'ye gönderir; aksiyonların gerçekleştirilmesi PC tarafındaki
 *   MacroPad uygulamasının görevidir.
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
// Sıra: Buton 1, 2, 3, 4, 5, 6 → fiziksel olarak hangi GPIO'ya lehimliyse
constexpr uint8_t BTN_PINS[BTN_COUNT] = {10, 20, 21, 4, 1, 0};
constexpr uint8_t I2C_SDA = 5;
constexpr uint8_t I2C_SCL = 6;

// ─────────────── Display modes (uygulama ile uyumlu) ───────────────
constexpr const char* MODE_CLOCK   = "clock";
constexpr const char* MODE_PROFILE = "profile_name";
constexpr const char* MODE_VOLUME  = "volume";
constexpr const char* MODE_CUSTOM  = "custom_text";

// ─────────────── Globals ───────────────
U8G2_SSD1306_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);

String profileName  = "Hazır";
String displayMode  = MODE_PROFILE;   // varsayılan
String customText   = "";
String clockTime    = "--:--";
String clockDate    = "";
int    volumeLevel  = -1;             // -1 = bilinmiyor

bool btnState[BTN_COUNT] = {false};
unsigned long btnDebounce[BTN_COUNT] = {0};
constexpr unsigned long DEBOUNCE_MS = 30;
unsigned long lastDraw = 0;
unsigned long lastRx = 0;          // millis() when last JSON command arrived
uint16_t      rxCount = 0;         // total commands received since boot
String        lastCmd = "-";       // last cmd field successfully parsed
String        lastErr = "";        // last parse error (truncated)
String        lastRaw = "";        // first 30 chars of last bad input

// ─────────────── OLED ───────────────
void drawClock() {
  oled.clearBuffer();
  oled.setFont(u8g2_font_logisoso32_tn);
  int w = oled.getStrWidth(clockTime.c_str());
  oled.drawStr((128 - w) / 2, 44, clockTime.c_str());
  if (clockDate.length()) {
    oled.setFont(u8g2_font_5x7_tf);
    int w2 = oled.getStrWidth(clockDate.c_str());
    oled.drawStr((128 - w2) / 2, 60, clockDate.c_str());
  }
}

void drawProfile() {
  oled.clearBuffer();
  oled.setFont(u8g2_font_5x7_tf);
  oled.drawStr(2, 10, "AKTIF PROFIL");
  oled.setFont(u8g2_font_helvB14_tf);
  int w = oled.getStrWidth(profileName.c_str());
  if (w > 124) w = 124;
  oled.drawStr((128 - w) / 2, 36, profileName.c_str());
  oled.setFont(u8g2_font_4x6_tf);
  // DEBUG: parsed display_mode + last received cmd + first chars of
  // any invalid line. Tells us at a glance which message broke.
  String l1 = String("mode=") + displayMode + "  last=" + lastCmd;
  oled.drawStr(2, 50, l1.c_str());
  if (lastErr.length()) {
    String l2 = String("err:") + lastErr + " " + lastRaw;
    oled.drawStr(2, 60, l2.substring(0, 32).c_str());
  } else {
    oled.drawStr(2, 60, "USB connected");
  }
}

void drawVolume() {
  oled.clearBuffer();
  oled.setFont(u8g2_font_5x7_tf);
  oled.drawStr(2, 10, "SES SEVIYESI");
  int v = (volumeLevel < 0) ? 0 : (volumeLevel > 100 ? 100 : volumeLevel);
  // Bar
  oled.drawFrame(8, 28, 112, 16);
  int fill = (v * 110) / 100;
  oled.drawBox(9, 29, fill, 14);
  // Yüzde
  String pct = (volumeLevel < 0 ? String("?") : String(v)) + "%";
  oled.setFont(u8g2_font_helvR10_tf);
  int w = oled.getStrWidth(pct.c_str());
  oled.drawStr((128 - w) / 2, 60, pct.c_str());
}

void drawCustom() {
  oled.clearBuffer();
  oled.setFont(u8g2_font_helvR10_tf);
  // Basit kelime kırma — uzun metin için 2 satır
  String t = customText.length() ? customText : "(boş)";
  int w = oled.getStrWidth(t.c_str());
  if (w <= 124) {
    oled.drawStr((128 - w) / 2, 40, t.c_str());
  } else {
    int mid = t.length() / 2;
    int sp = t.indexOf(' ', mid - 5);
    if (sp < 0 || sp > mid + 10) sp = mid;
    String l1 = t.substring(0, sp);
    String l2 = t.substring(sp + (t[sp] == ' ' ? 1 : 0));
    int w1 = oled.getStrWidth(l1.c_str());
    int w2 = oled.getStrWidth(l2.c_str());
    oled.drawStr((128 - w1) / 2, 30, l1.c_str());
    oled.drawStr((128 - w2) / 2, 52, l2.c_str());
  }
}

void drawRxIndicator() {
  // Top-right corner: solid dot for ~300ms after each received command,
  // plus a tiny RX counter in the corner. If you press "Cihaza Gönder"
  // and nothing changes here, the firmware never received the message.
  if (millis() - lastRx < 300) {
    oled.drawDisc(122, 4, 3);
  } else {
    oled.drawCircle(122, 4, 3);
  }
  oled.setFont(u8g2_font_4x6_tf);
  String c = "RX " + String(rxCount);
  int w = oled.getStrWidth(c.c_str());
  oled.drawStr(115 - w, 7, c.c_str());
}

void drawScreen() {
  if (displayMode == MODE_CLOCK)        drawClock();
  else if (displayMode == MODE_VOLUME)  drawVolume();
  else if (displayMode == MODE_CUSTOM)  drawCustom();
  else                                  drawProfile();
  drawRxIndicator();
  oled.sendBuffer();
  lastDraw = millis();
}

void drawBootScreen(const String& bottom) {
  oled.clearBuffer();
  oled.setFont(u8g2_font_helvB12_tf);
  oled.drawStr(2, 16, "MacroPad");
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
  JsonArray modules = root["modules"];
  for (JsonObject mod : modules) {
    String mid = String((const char*)(mod["module_id"] | ""));
    if (mid != "main") continue;
    // Always read; default falls through if the field is missing.
    String newMode = String((const char*)(mod["display_mode"] | ""));
    if (newMode.length()) displayMode = newMode;
    String newCustom = String((const char*)(mod["display_custom_text"] | ""));
    customText = newCustom;
  }
  drawScreen();
}

void handleClock(JsonVariant root) {
  clockTime = String((const char*)(root["time"] | "--:--"));
  clockDate = String((const char*)(root["date"] | ""));
  if (displayMode == MODE_CLOCK) drawScreen();
}

void handleVolume(JsonVariant root) {
  volumeLevel = (int)(root["level"] | -1);
  if (displayMode == MODE_VOLUME) drawScreen();
}

void handleLine(const String& line) {
  DynamicJsonDocument doc(8192);
  DeserializationError err = deserializeJson(doc, line);
  if (err) {
    lastErr = String(err.c_str()).substring(0, 12);
    lastRaw = line.substring(0, 30);
    drawScreen();
    return;
  }
  lastErr = "";
  lastRaw = "";
  String cmd = String((const char*)(doc["cmd"] | ""));
  lastCmd = cmd;
  lastRx = millis();
  rxCount++;
  if      (cmd == "discover") sendModules();
  else if (cmd == "config")   handleConfig(doc.as<JsonVariant>());
  else if (cmd == "clock")    handleClock(doc.as<JsonVariant>());
  else if (cmd == "volume")   handleVolume(doc.as<JsonVariant>());
  drawScreen();
}

// ─────────────── Setup / Loop ───────────────
void setup() {
  for (int i = 0; i < BTN_COUNT; i++) pinMode(BTN_PINS[i], INPUT_PULLUP);

  Wire.begin(I2C_SDA, I2C_SCL);
  oled.begin();

  Serial.begin(115200);
  unsigned long t0 = millis();
  while (!Serial && (millis() - t0) < 1500) delay(10);

  drawBootScreen("Ready");
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
    }
  }

  // Saat modunda dakika değişimi yakalamak için ekranı 5 saniyede bir çiz.
  // Ayrıca RX dot'unun sönmesini sağlamak için son komuttan ~400ms sonra
  // bir ekstra çizim yap.
  if (displayMode == MODE_CLOCK && (now - lastDraw) > 5000) {
    drawScreen();
  } else if (lastRx && (now - lastRx) > 350 && (now - lastDraw) > 350) {
    drawScreen();
  }

  delay(2);
}
