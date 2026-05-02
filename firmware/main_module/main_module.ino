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
String        lastCfgInfo = "";    // diagnostic: what handleConfig saw
uint16_t      lastLineLen = 0;     // length of last received line

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
  oled.drawStr((128 - w) / 2, 32, profileName.c_str());
  oled.setFont(u8g2_font_4x6_tf);
  String l1 = String("mode=") + displayMode + " last=" + lastCmd + " len=" + String(lastLineLen);
  oled.drawStr(2, 46, l1.c_str());
  String l2 = lastCfgInfo.length() ? lastCfgInfo : String("USB connected");
  oled.drawStr(2, 54, l2.c_str());
  if (lastErr.length()) {
    String l3 = String("err:") + lastErr + " " + lastRaw;
    oled.drawStr(2, 62, l3.substring(0, 32).c_str());
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

// Lean OLED-only payload from PC. Replaces the full module-config
// flow which kept hitting InvalidInput parse errors with bigger
// JSON. The firmware no longer needs the action mappings since PC
// dispatches button_events itself.
void handleDisplay(JsonVariant root) {
  profileName = String((const char*)(root["profile_name"] | "Profil"));
  String newMode = String((const char*)(root["display_mode"] | ""));
  String parsedMode = newMode.length() ? newMode : "(empty)";
  if (newMode.length()) displayMode = newMode;
  customText = String((const char*)(root["display_custom_text"] | ""));
  lastCfgInfo = String("disp m=") + parsedMode;
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

// One global doc reused across calls — avoids repeated 8KB allocs
// and keeps memory predictable on a 400KB-RAM chip.
DynamicJsonDocument g_doc(8192);

void handleLine(const char* line, size_t len) {
  lastLineLen = len;
  g_doc.clear();
  DeserializationError err = deserializeJson(g_doc, line, len);
  if (err) {
    lastErr = String(err.c_str()).substring(0, 12);
    // Keep both head and tail of the bad line — lets us see if the
    // start was junk (USB enumeration noise) or the end was truncated.
    String l(line);
    if (l.length() > 30) lastRaw = l.substring(0, 16) + "..." + l.substring(l.length() - 8);
    else lastRaw = l;
    drawScreen();
    return;
  }
  lastErr = "";
  lastRaw = "";
  String cmd = String((const char*)(g_doc["cmd"] | ""));
  lastCmd = cmd;
  lastRx = millis();
  rxCount++;
  if      (cmd == "discover") sendModules();
  else if (cmd == "display")  handleDisplay(g_doc.as<JsonVariant>());
  else if (cmd == "clock")    handleClock(g_doc.as<JsonVariant>());
  else if (cmd == "volume")   handleVolume(g_doc.as<JsonVariant>());
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
  // Char-buffer line accumulator. Replaces the Arduino String version,
  // which fragmented memory and (more importantly) sometimes returned
  // a truncated buffer to deserializeJson — exactly what causes the
  // intermittent "InvalidInput" errors the user has been seeing.
  static char lineBuf[8192];
  static size_t lineLen = 0;
  while (Serial.available()) {
    int rc = Serial.read();
    if (rc < 0) break;
    char c = (char)rc;
    if (c == '\n' || c == '\r') {
      if (lineLen > 0) {
        lineBuf[lineLen] = '\0';
        handleLine(lineBuf, lineLen);
        lineLen = 0;
      }
    } else if (lineLen < sizeof(lineBuf) - 1) {
      lineBuf[lineLen++] = c;
    } else {
      // Overflow — discard the line and reset so we can recover.
      lineLen = 0;
      lastErr = "Overflow";
      lastRaw = "";
      drawScreen();
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
