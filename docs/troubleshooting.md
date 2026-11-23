# AquaBuzz Troubleshooting Guide

## Hardware Issues

### Buzzer Doesn't Sound

**Symptoms**: No audio feedback when touching maze wire

**Checks**:
1. Send `b` command over serial - should hear two beeps
2. Check MOSFET wiring:
   - Signal wire on GPIO 26
   - VCC connected to 5V
   - GND connected to ESP32 GND
3. Check buzzer polarity:
   - Positive to 5V
   - Negative to MOSFET OUT terminal
4. Test with multimeter: GPIO 26 should read ~3.3V when HIGH

**Solution**: Most commonly a loose connection on the MOSFET signal wire.

---

### Run Finishes Instantly

**Symptoms**:
- Every run completes in <500ms
- Serial warning: `{"warn":"finish_and_maze_both_low"}`
- Backend anomaly: `too_fast`

**Cause**: Finish pad is electrically connected to maze wire

**Check**: Use multimeter continuity mode between maze wire and finish pad
- Should show OPEN (no beep)
- If CONTINUITY (beeps), they're connected

**Solution**: Physically separate finish pad from maze wire, ensure no touching points

---

### First Touch Doesn't Start Run

**Symptoms**: Touching maze wire does nothing

**Checks**:
1. Wait 5 seconds after previous run (lockout period)
2. Confirm ring is grounded (connected to ESP32 GND)
3. Check GPIO 27 connection to maze wire
4. Test with multimeter: GPIO 27 should read ~3.3V when not touching, ~0V when ring touches wire

**Solution**: Usually a loose ground connection on the ring.

---

### Finish Pad Doesn't Work

**Symptoms**: Can't complete run, touching finish does nothing

**Checks**:
1. GPIO 33 connection to finish pad
2. Finish pad is conductive metal
3. Ring is properly grounded
4. Finish pad is NOT touching maze wire

**Solution**: Check wiring, ensure finish pad is a conductive surface.

---

## Firmware Issues

### ESP32 Won't Flash

**Symptoms**: Upload fails in Arduino IDE

**Checks**:
1. Correct board selected: **Tools > Board > ESP32 Dev Module**
2. Correct port selected: Check **Tools > Port**
3. Driver installed: CP2102 or CH340 USB-to-serial chip
4. Hold **BOOT** button during upload

**Solution**: Install driver, try different USB cable, press BOOT button.

---

### Compile Errors

**Error**: `secrets.h: No such file or directory`

**Solution**: 
```bash
cp firmware/secrets.example.h firmware/secrets.h
# Edit secrets.h with your credentials
```

**Error**: `WiFi.h: No such file or directory`

**Solution**: Install ESP32 board support in Arduino IDE:
- File > Preferences > Additional Boards Manager URLs:
- Add: `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
- Tools > Board > Boards Manager > Search "ESP32" > Install

**Error**: `PubSubClient.h: No such file or directory`

**Solution**: Install library:
- Sketch > Include Library > Manage Libraries
- Search "PubSubClient" by Nick O'Leary
- Install

---

### WiFi Won't Connect

**Symptoms**: Serial shows `{"wifi":"failed"}`

**Checks**:
1. Verify credentials in `secrets.h`:
   ```cpp
   #define WIFI_SSID "your-network-name"
   #define WIFI_PASSWORD "your-password"
   ```
2. Check 2.4GHz network (ESP32 doesn't support 5GHz)
3. Check signal strength (move closer to router)
4. Try different network

**Debug**: Open serial monitor at 115200 baud to see connection attempts

---

### MQTT Won't Connect

**Symptoms**: WiFi connects but `{"mqtt":"connected"}` never appears

**Checks**:
1. Verify MQTT broker is running:
   ```bash
   docker compose ps
   # Should show aquabuzz-mqtt as "running"
   ```
2. Check broker IP in `secrets.h`:
   ```cpp
   #define MQTT_BROKER "192.168.1.100"  // Your laptop/server IP
   ```
3. Test broker from command line:
   ```bash
   mosquitto_sub -h localhost -t 'test' -v
   # Should connect without error
   ```
4. Check firewall (allow port 1883)

**Solution**: Most commonly wrong broker IP. Use `ipconfig` (Windows) or `ifconfig` (Mac/Linux) to find your machine's IP.

---

## Backend Issues

### Backend Won't Start

**Error**: `ModuleNotFoundError: No module named 'fastapi'`

**Solution**:
```bash
cd backend
pip install -r requirements.txt
```

**Error**: `sqlite3.OperationalError: unable to open database file`

**Solution**: Create data directory:
```bash
mkdir -p backend/data
```

**Error**: Port 8000 already in use

**Solution**: Stop other process or change port:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

---

### MQTT Events Not Reaching Backend

**Symptoms**: Device publishes events but backend doesn't receive them

**Debug**:
1. Subscribe manually to verify events:
   ```bash
   mosquitto_sub -h localhost -t 'aquabuzz/#' -v
   # Trigger a run on device
   # Should see JSON events appear
   ```

2. Check backend MQTT configuration in `.env`:
   ```
   MQTT_BROKER_HOST=localhost
   MQTT_BROKER_PORT=1883
   ```

3. Check backend logs for MQTT connection:
   ```bash
   # Should see: [MQTT] Connected to localhost:1883
   ```

**Solution**: Usually broker host mismatch. Use `localhost` if backend and broker are on same machine, or IP address if separate.

---

### Database Errors

**Error**: `sqlalchemy.exc.OperationalError: no such table: runs`

**Solution**: Database not initialized. Backend should auto-create tables on first run.
```bash
# Delete and restart to force recreation
rm backend/aquabuzz.db
# Restart backend
```

**Error**: `sqlite3.OperationalError: database is locked`

**Solution**: Another process has database open. Stop all backend instances, restart.

---

## Dashboard Issues

### Dashboard Shows "Could not connect to backend"

**Checks**:
1. Backend is running: visit http://localhost:8000/api/health
2. CORS is configured: Check `.env`:
   ```
   CORS_ORIGINS=http://localhost:3000,http://localhost:8000
   ```
3. Browser console (F12) for specific error

**Solution**: Ensure backend is running and accessible.

---

### Dashboard Shows No Data

**Checks**:
1. Backend has received runs: http://localhost:8000/api/runs
2. MQTT connection: Check health endpoint
3. Device is publishing: Use `mosquitto_sub` to verify

**Solution**: Trigger test run with simulator:
```bash
python tools/simulator.py --runs 10
```

---

## Docker Issues

### docker compose up Fails

**Error**: `port is already allocated`

**Solution**: Stop conflicting container or change port in `docker-compose.yml`

**Error**: `no such file or directory: mosquitto.conf`

**Solution**: Ensure `mosquitto.conf` exists in project root

**Error**: `Cannot connect to the Docker daemon`

**Solution**: Start Docker Desktop

---

### Backend Container Keeps Restarting

**Debug**:
```bash
docker compose logs backend
```

**Common causes**:
- Python syntax error
- Missing environment variable
- Database permission error

**Solution**: Fix error shown in logs, then `docker compose restart backend`

---

## Performance Issues

### Buzzer Latency

**Symptoms**: Noticeable delay between touch and sound

**Cause**: Blocking call in `loop()` or task priority issue

**Check**: Verify `driveBuzzerNow()` is first line of `loop()`:
```cpp
void loop() {
  driveBuzzerNow();  // MUST be first
  // ...
}
```

**Solution**: Never add delays or blocking operations to `loop()`

---

### MQTT Event Delays

**Symptoms**: Events arrive seconds late at backend

**Checks**:
1. Network latency: Ping broker from device network
2. Queue overflow: Increase `MQTT_QUEUE_SIZE` if many dropped events
3. MQTT broker load: Check broker CPU usage

**Note**: 1-2 second delays are normal and acceptable for this system.

---

## Intelligence Issues

### Skill Classification Always "beginner"

**Cause**: ML model not trained, using rule-based fallback

**Solution**: Generate training data:
```bash
python tools/simulator.py --runs 100 --fast
# Wait for backend to process
# Model will train automatically when >30 runs exist
```

---

### Anomaly False Positives

**Symptom**: Normal runs flagged as anomalies

**Common**:
- `too_fast` on very skilled players → Lower threshold in `anomalies.py`
- `excessive_hits` on complex mazes → Increase threshold

**Solution**: Tune anomaly thresholds in `backend/intelligence/anomalies.py`

---

## Diagnostic Commands

### Serial Commands (ESP32)
- `r` - Reset current run
- `s` - Print status summary
- `b` - Buzzer test (two beeps)

### MQTT Commands
```bash
# Subscribe to all device events
mosquitto_sub -h localhost -t 'aquabuzz/#' -v

# Set player
mosquitto_pub -h localhost -t 'aquabuzz/aquabuzz-001/player' -m '"bob"'

# Push config
mosquitto_pub -h localhost -t 'aquabuzz/aquabuzz-001/config' \
  -m '{"hit_penalty_ms":3000,"free_hits":0,"time_limit_ms":null,"fast_time_ms":null}'
```

### API Testing
```bash
# Health check
curl http://localhost:8000/api/health

# Recent runs
curl http://localhost:8000/api/runs?limit=5

# Leaderboard
curl http://localhost:8000/api/leaderboard

# Player insights
curl http://localhost:8000/api/insights/alice
```

---

## Getting Help

If you're still stuck:

1. **Check logs**:
   - ESP32: Serial monitor at 115200 baud
   - Backend: Console output or `docker compose logs backend`
   - Broker: `docker compose logs mqtt`

2. **Verify setup**:
   - Follow wiring diagram exactly
   - Confirm all dependencies installed
   - Use exact pin numbers specified

3. **Test isolation**:
   - Test firmware alone (no network)
   - Test backend alone (use simulator)
   - Test each component separately

4. **Known working state**:
   - Flash firmware v6 core first
   - Confirm game works without network
   - Add IoT features incrementally

5. **GitHub Issues**:
   - Report bugs with logs and steps to reproduce
   - Include hardware details and software versions
