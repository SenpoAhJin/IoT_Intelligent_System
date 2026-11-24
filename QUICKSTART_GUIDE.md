# AQUABUZZ QUICKSTART GUIDE

## SYSTEM STARTUP (3 COMMANDS)

### 1. Start Everything
```powershell
cd "C:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS"
.\scripts\rise.ps1
```

This starts:
- FastAPI Backend (port 8000)
- Serial Gateway (auto-detects ESP32)
- Dashboard (port 3000-3002)
- Opens browser automatically

### 2. Stop Everything
```powershell
.\scripts\rise-stop.ps1
```

### 3. Check Status
```powershell
# View health endpoint
curl http://localhost:8000/api/health

# Or open in browser
start http://localhost:8000/docs
```

---

## ACCESSING THE SYSTEM

### Dashboard
- **URL:** Browser opens automatically, or visit:
  - http://localhost:3000 (first try)
  - http://localhost:3001 (if 3000 in use)
  - http://localhost:3002 (if 3001 in use)
  - http://localhost:8080 (if 3002 in use)

### API Documentation
- **Swagger UI:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/api/health
- **Recent Runs:** http://localhost:8000/api/runs?limit=10
- **Leaderboard:** http://localhost:8000/api/leaderboard?limit=10
- **Players:** http://localhost:8000/api/players

---

## ESP32 SETUP

### Option 1: Use Existing Firmware (aquabuzz_connected)
The firmware at `firmware/aquabuzz_connected/aquabuzz_connected.ino` has already been fixed.

**To Upload:**
1. Open Arduino IDE
2. File → Open → Select `aquabuzz_connected.ino`
3. Tools → Board → ESP32 Dev Module
4. Tools → Port → Select your COM port
5. Upload

### Option 2: Configure WiFi (Optional - Currently Disabled)
If you want ESP32 to publish directly to MQTT instead of using USB serial:

1. Edit `firmware/aquabuzz_connected/secrets.h`
2. Set your WiFi credentials
3. Uncomment MQTT publish calls in .ino file
4. Upload

**Current Setup:** USB Serial Gateway (no WiFi needed)

---

## TESTING THE SYSTEM

### Test Without Hardware (Simulated Events)
```powershell
# Run integration tests
cd scripts
..\.venv\Scripts\python.exe test-full-flow.py
```

### Test With Hardware (Physical ESP32)
1. Upload firmware to ESP32
2. Connect ESP32 via USB
3. Run `rise.ps1`
4. Watch gateway terminal for "ESP32 found on COM#"
5. Touch maze wire → buzzer should sound
6. Complete a run from start to finish
7. Check dashboard for results

---

## GAMEPLAY FLOW

### How to Play
1. **Start Run:** Touch maze wire while NOT touching finish
2. **During Run:** 
   - Buzzer sounds when touching maze
   - System counts hits and durations
3. **Finish Run:** Touch finish pad
4. **View Results:** Check dashboard

### Scoring
- **Score = Time + (Hits × Penalty)**
- Default Penalty: 2000ms per hit
- Lower score = better performance

### Reset
- Send 'r' command via serial monitor
- Or wait 5 seconds after finish

---

## TROUBLESHOOTING

### Backend Won't Start
```powershell
# Check if port 8000 is in use
netstat -ano | findstr :8000

# Kill process if needed
taskkill /PID <process_id> /F

# Try again
.\scripts\rise.ps1
```

### ESP32 Not Detected
1. Check USB cable (must support data)
2. Install CP210x or CH340 drivers
3. Check Device Manager for COM port
4. Try different USB port
5. Set explicit COM port:
   ```powershell
   $env:COM_PORT = "COM3"
   .\scripts\rise.ps1
   ```

### Dashboard Not Loading
1. Check backend is running: http://localhost:8000/api/health
2. Check browser console for errors (F12)
3. Try different port: http://localhost:3001
4. Clear browser cache

### No Events Received
1. Check serial gateway terminal for ESP32 connection
2. Check backend terminal for MQTT connection
3. Verify COM port in gateway logs
4. Send 's' command via serial monitor (should show summary)

### Database Issues
```powershell
# Reset database (WARNING: Deletes all data)
cd backend
Remove-Item aquabuzz.db
..\.venv\Scripts\python.exe -c "from app.db import init_db; init_db()"
```

---

## MONITORING LOGS

### View Backend Logs
Backend terminal shows:
- `[MQTT] Connected to test.mosquitto.org`
- `[MQTT] Subscribed to aquabuzz/+/events`
- `[MQTT] Created run: aquabuzz-001-...`
- `[MQTT] Hit 1 started`
- `[Intelligence] Analyzed run ...`

### View Gateway Logs
Gateway terminal shows:
- `[Serial] Connected to ESP32 on COM3`
- `[Serial] Raw event: {"run":1,"event":"run_start"}`
- `[Gateway] Started run: aquabuzz-001-...`
- `[MQTT] Published event: run_start`

### View ESP32 Logs
Serial Monitor (115200 baud) shows:
- `{"info":"aquabuzz_connected_v1","boot":1}`
- `{"run":1,"event":"run_start"}`
- `{"run":1,"event":"hit_start","hit":1}`
- `{"run":1,"event":"run_finish","score":12000}`

---

## API ENDPOINTS REFERENCE

### Health & Status
- `GET /api/health` - System health check

### Runs
- `GET /api/runs?limit=50` - Recent runs
- `GET /api/runs/{run_id}` - Run details with hits

### Players
- `GET /api/players` - All players with stats
- `GET /api/insights/{player_id}` - AI insights

### Leaderboard
- `GET /api/leaderboard?limit=10` - Top scores

### Device Config
- `POST /api/devices/{device_id}/config` - Push difficulty settings

---

## ENVIRONMENT VARIABLES

### Backend (.env)
```bash
DATABASE_URL=sqlite:///./aquabuzz.db
MQTT_BROKER_HOST=test.mosquitto.org
MQTT_BROKER_PORT=1883
API_PORT=8000
CORS_ORIGINS=*
```

### Serial Gateway
```bash
DEVICE_ID=aquabuzz-001
DEFAULT_PLAYER_ID=guest
MQTT_BROKER_HOST=test.mosquitto.org
MQTT_BROKER_PORT=1883
COM_PORT=  # Leave empty for auto-detection
```

---

## FILE LOCATIONS

### Firmware
- `firmware/aquabuzz_connected/aquabuzz_connected.ino`
- `firmware/aquabuzz_connected/secrets.h`

### Backend
- `backend/app/main.py` - FastAPI application
- `backend/app/models.py` - Database models
- `backend/serial_gateway.py` - USB serial gateway
- `backend/intelligence/` - AI modules

### Frontend
- `dashboard/index.html` - Live dashboard

### Scripts
- `scripts/rise.ps1` - Start system
- `scripts/rise-stop.ps1` - Stop system
- `scripts/test-full-flow.py` - Integration tests

### Database
- `backend/aquabuzz.db` - SQLite database

---

## COMMON COMMANDS

### Python Virtual Environment
```powershell
# Activate (if needed)
.venv\Scripts\activate

# Install dependencies
pip install -r backend\requirements.txt
```

### Run Backend Directly
```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

### Run Gateway Directly
```powershell
cd backend
..\.venv\Scripts\python.exe serial_gateway.py
```

### Run Dashboard Directly
```powershell
cd dashboard
..\.venv\Scripts\python.exe -m http.server 3000
```

---

## SYSTEM REQUIREMENTS

### Software
- Windows 10/11
- PowerShell 5.1+
- Python 3.11+
- Arduino IDE (for firmware upload)

### Hardware
- ESP32 Dev Module
- USB Cable (data-capable)
- Maze wire and finish pad (physical setup)

### Network
- Internet connection (for public MQTT broker)
- Or configure private MQTT broker

---

## SUCCESS INDICATORS

### ✅ System Running Correctly
- Backend shows `[MQTT] Connected`
- Gateway shows `[Serial] Connected to ESP32 on COM#`
- Dashboard loads and shows system status
- Health endpoint returns `"status": "healthy"`

### ✅ Game Working
- Buzzer sounds on maze contact
- Serial shows event JSON
- Backend logs show received events
- Dashboard updates with new run

### ✅ Data Persistence
- Completed runs visible in dashboard
- API returns run data
- Database contains records
- Leaderboard updates

---

## GETTING HELP

### Check These First
1. Implementation Report: `IMPLEMENTATION_REPORT.md`
2. Architecture Docs: `docs/architecture.md`
3. Troubleshooting: `docs/troubleshooting.md`
4. MQTT Topics: `docs/mqtt-topics.md`

### Debug Mode
Add to .env:
```bash
LOG_LEVEL=DEBUG
```

Restart backend to see detailed logs.

---

**Last Updated:** November 24, 2026  
**Version:** 1.0 - Post-Repair Release
