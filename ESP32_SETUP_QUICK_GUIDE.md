# ESP32 Quick Setup Guide - Public MQTT

## 1. Enable Mobile Hotspot on Your Phone

- **Android**: Settings → Network & Internet → Hotspot & Tethering → WiFi Hotspot
- **iPhone**: Settings → Personal Hotspot → Allow Others to Join

**Note your:**
- Hotspot Name (SSID)
- Hotspot Password

## 2. Update ESP32 Firmware Configuration

Edit: `firmware/aquabuzz_connected/secrets.h`

Replace:
```cpp
#define WIFI_SSID "YourPhoneHotspotName"
#define WIFI_PASSWORD "YourHotspotPassword"
```

With your actual hotspot credentials.

**Keep these unchanged:**
```cpp
#define MQTT_BROKER "test.mosquitto.org"
#define MQTT_PORT 1883
#define DEVICE_ID "aquabuzz-001"
```

## 3. Upload Firmware

1. Open Arduino IDE
2. File → Open → `firmware/aquabuzz_connected/aquabuzz_connected.ino`
3. Tools → Board → ESP32 Dev Module
4. Tools → Port → (Select your ESP32's COM port)
5. Click Upload button (→)
6. Wait for "Done uploading"

## 4. Verify Connection

1. Open Serial Monitor (Ctrl+Shift+M)
2. Set baud rate to **115200**
3. Reset ESP32 (press reset button)

**Expected output:**
```json
{"info":"aquabuzz_connected_v1","boot":1,"device":"aquabuzz-001"}
{"wifi":"connecting"}
{"wifi":"connected","ip":"192.168.x.x"}
{"mqtt":"connected"}
```

✅ If you see `{"mqtt":"connected"}`, ESP32 is ready!

## 5. Connect Laptop to Same Hotspot

Your laptop must be on the **same mobile hotspot** as the ESP32 for `rise` to work.

## 6. Start AquaBuzz Backend

Open PowerShell:
```powershell
rise
```

Check backend health:
```powershell
curl http://localhost:8000/api/health
```

Look for `"mqtt_connected": true`

## Troubleshooting

### ESP32 won't connect to WiFi
- Verify hotspot SSID and password in `secrets.h`
- Check hotspot is enabled
- Try restarting hotspot

### ESP32 won't connect to MQTT
- Check phone has cellular data
- Verify `test.mosquitto.org` is reachable
- Wait 30 seconds after WiFi connects

### Backend shows `mqtt_connected: false`
- Wait 10-20 seconds (initial connection)
- Check laptop has internet (mobile hotspot)
- Verify `.env` has `MQTT_BROKER_HOST=test.mosquitto.org`

### No heartbeats received
- Check ESP32 Serial Monitor shows `{"mqtt":"connected"}`
- Wait 10 seconds for first heartbeat
- Verify backend logs (should show MQTT messages)

## Quick Commands

```powershell
# Start AquaBuzz
rise

# Check health
curl http://localhost:8000/api/health

# Stop AquaBuzz
rise-stop
```

## Need Help?

Check full documentation: `AquaBuzz_Public_MQTT_Migration_Guide.md`
