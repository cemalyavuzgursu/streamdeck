# MacroPad Firmware

ESP32-C3 Super Mini için ana modül firmware'i. USB HID klavye + medya kontrolü olarak çalışır; PC tarafındaki MacroPad uygulaması ile USB CDC üzerinden JSON protokolü konuşur.

## 1. Arduino IDE Kurulumu

1. **Arduino IDE 2.x** indir → https://www.arduino.cc/en/software
2. **File → Preferences → Additional Boards Manager URLs** kısmına ekle:
   ```
   https://espressif.github.io/arduino-esp32/package_esp32_index.json
   ```
3. **Tools → Board → Boards Manager** → "esp32" ara → **esp32 by Espressif Systems** son sürümü kur (2.0.14+ veya 3.x)

## 2. Kütüphaneler

**Sketch → Include Library → Manage Libraries** üzerinden kur:

| Kütüphane | Yazar |
|---|---|
| **ArduinoJson** | Benoit Blanchon |
| **U8g2** | oliver |

## 3. Board Ayarları

ESP32-C3 Super Mini'yi USB-C ile bağla, sonra Tools menüsünden:

| Ayar | Değer |
|---|---|
| Board | **ESP32C3 Dev Module** |
| USB CDC On Boot | **Enabled** |
| USB Mode | **USB-OTG (TinyUSB)** |
| Upload Mode | **USB-OTG CDC (TinyUSB)** |
| CPU Frequency | 160 MHz |
| Flash Size | 4MB |
| Partition Scheme | Default 4MB with spiffs |
| Port | Liste açıldığında **COMx — ESP32-C3** olarak gözüken port |

> Eğer port görünmüyorsa: BOOT butonunu basılı tutarken USB'yi tak (yeşil LED yanıyorsa hâlâ basılı tut), sonra IDE'de port listesini yenile.

## 4. İlk Yükleme

1. `firmware/main_module/main_module.ino` dosyasını Arduino IDE'de aç
2. **Sketch → Verify** (✓) — derleme hatasız mı kontrol et
3. **Sketch → Upload** (→) — yükle

İlk seferinde Arduino IDE muhtemelen "auto-reset" yapamaz çünkü Super Mini'de DTR/RTS hardware reset devresi yok. Bu durumda upload başlamadan **BOOT butonunu basılı tut**, IDE "Connecting..." dediğinde bırak.

Yükleme bittiğinde OLED'de "MacroPad" yazısı görmen lazım.

## 5. PC'den Bağlantı

1. MacroPad uygulamasını aç
2. Port dropdown'da **COMx — ESP32-C3** otomatik seçili gelir
3. **Bağlan**'a bas
4. Canvas'ta otomatik olarak "Ana Modül · 6 btn · OLED" çıkmalı (Discovery)
5. Butonlardan birini seç, kısayol ata, **↑ Cihaza Gönder**'e bas
6. Fiziksel butona bas → atadığın kısayol gerçekleşmeli

## 6. Pin Map (donanım bağlantısı)

```
ESP32-C3 Super Mini:

  GPIO 0  ── Buton 1 ── GND
  GPIO 1  ── Buton 2 ── GND
  GPIO 3  ── Buton 3 ── GND
  GPIO 4  ── Buton 4 ── GND
  GPIO 10 ── Buton 5 ── GND
  GPIO 21 ── Buton 6 ── GND

  GPIO 5  ── OLED SDA (+ TCA9548A SDA)
  GPIO 6  ── OLED SCL (+ TCA9548A SCL)

  GPIO 7  ── (rezerve: slave INT)
  GPIO 9  ── BOOT butonu — KULLANMA
  GPIO 2, 8 ── strapping pinleri — boot anında HIGH olmalı
```

> Butonlar internal pull-up ile okunur — diyot/external direnç gerekmez.

## 7. Sorun Giderme

| Belirti | Çözüm |
|---|---|
| OLED bir şey göstermiyor | I2C adresini doğrula (varsayılan 0x3C). `Wire.begin(5, 6)` çağrısı doğru pinlerde mi? OLED 3.3V mı 5V mı kontrol et. |
| Butonlar çalışmıyor | Multimetre ile butona basınca ilgili GPIO'nun GND'ye düştüğünü doğrula. |
| Yükleme "Failed to connect" | BOOT'u basılı tut, yükle, tamamlanınca bırak. |
| App "Bağlantı kesildi" diyor | Firmware yüklü değil — ROM bootloader stabil USB CDC vermez. Önce firmware'i yükle. |
| Klavye Türkçe karakter yazmıyor | Windows klavye dilini İngiliz yapıp test et. Türkçe karakterler için ayrı bir mapping gerekir (gelecek sürümde). |

## 8. Slave Modüller (gelecek)

Bu firmware **sadece ana modül** için yazıldı. Slave modüller eklendiğinde:

1. Slave PCB'sinde MCP23017 var (I2C adres 0x20-0x27)
2. Ana firmware'e I2C tarama döngüsü eklenecek (her 50ms)
3. Slave butonlarına basıldığında MCP23017 INT pini düşer → master ana firmware uyanır → ilgili butonun aksiyonu tetiklenir
4. Discovery cevabına slave modüller eklenecek

Slave protokol kodu hazır olduğunda `firmware/main_module/` içine `slave_scan.ino` modülü olarak eklenecek.
