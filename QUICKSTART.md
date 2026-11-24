# AquaBuzz Quick Start Guide

Get the AquaBuzz system running in 3 simple steps.

---

## Prerequisites

✅ Python virtual environment at `.venv/`  
✅ Dependencies installed: `pip install -r backend/requirements.txt`  
✅ Internet connection (for MQTT broker)  
✅ ESP32 with aquabuzz_core.ino firmware (optional for full testing)

---

## Step 1: Start the System

Open PowerShell in the project directory:

```powershell
cd "C:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS"
.\scripts\rise.ps1
```

This will start:
- FastAPI Backend (port 8000)
- Serial Gateway (auto-detects ESP32)
- Dashboard HTTP Server (port 3000)

**Expected Output:**
```
==================================================
    AquaBuzz Startup Complete
==================================================

Services Running:
  Backend API: http://localhost:8000 (PID: xxxx)
  Serial Gateway: USB Serial → MQTT (PID: xxxx)
  Dashboard: http://localhost:3000 (PID: xxxx)
  MQTT Broker: test.mosquitto.org:1883 (public)
```

---

## Step 2: Open the Dashboard

Your browser should open automatically to: **http://localhost:3000**

If not, open it manually.

### What You'll See:

**System Health Card:**
- Backend Status: 🟢 healthy
- MQTT Broker: 🟢 Connected
- ESP32 Device: 🔴 Not Connected (until you plug in ESP32)
- Active Runs: 0
- Completed Runs: X
- Total Players: X

**Leaderboard:**
- Top 5 fastest completion times

**Recent Runs:**
- Last 5 game sessions with hits and duration

**Players:**
- All registered players with skill levels and stats

---

## Step 3: Connect ESP32 (Optional)

### Upload Firmware
1. Open Arduino IDE
2. Load `firmware/aquabuzz_core/aquabuzz_core.ino`
3. Select ESP32 board and COM port
4. Upload

### Connect via USB
1. Plug ESP32 into laptop via USB cable
2. Watch the **Serial Gateway** window
3. You should see:
   ```
   [Serial] Found potential ESP32 on COM3: USB-SERIAL CH340
   [Serial] ✓ Connected to ESP32 on COM3
   [MQTT] ✓ Connected to test.mosquitto.org:1883
   ```

### Verify Dashboard Updates
1. Refresh dashboard (or wait 5 seconds for auto-refresh)
2. ESP32 Device status should change to: 🟢 Online
3. Device ID should appear: `aquabuzz-001`

---

## Testing the Game

### Manual Test (Without Hardware)
You can publish test events directly to MQTT:

```powershell
# In a new PowerShell window
cd backend
..\.venv\Scripts\python

# Then in Python:
import paho.mqtt.publish as publish
import json
import time

# Test heartbeat
publish.single(
    "aquabuzz/aquabuzz-001/heartbeat",
    json.dumps({"device_id": "aquabuzz-001", "uptime_s": 60}),
    hostname="test.mosquitto.org"
)

# Test game start
publish.single(
    "aquabuzz/aquabuzz-001/events",
    json.dumps({
        "event": "run_start",
        "device_id": "aquabuzz-001",
        "player_id": "test_player",
        "run_uid": "test_run_123",
        "run_no": 1,
        "t_ms": 0
    }),
    hostname="test.mosquitto.org"
)

# Test game finish
publish.single(
    "aquabuzz/aquabuzz-001/events",
    json.dumps({
        "event": "run_finish",
        "device_id": "aquabuzz-001",
        "player_id": "test_player",
        "run_uid": "test_run_123",
        "run_no": 1,
        "t_ms": 15000,
        "hits": 3,
        "total_contact_ms": 450,
        "longest_hit_ms": 200,
        "hit_penalty_ms": 2000,
        "score": 21000
    }),
    hostname="test.mosquitto.org"
)
```

Watch the dashboard update automatically!

### With ESP32 Hardware
1. Touch wire loop with wand to trigger hits
2. Navigate through maze
3. Complete maze to finish run
4. Dashboard updates automatically with:
   - New run in Recent Runs
   - Updated player stats
   - Leaderboard position (if top 5)

---

## Stop the System

```powershell
.\scripts\rise-stop.ps1
```

This cleanly stops all AquaBuzz services.

---

## Troubleshooting

### Backend won't start
- Check port 8000 is not in use: `Get-NetTCPConnection -LocalPort 8000`
- Check virtual environment: `.venv\Scripts\python --version`

### MQTT not connecting
- Check internet connection
- Verify test.mosquitto.org is accessible: `Test-Connection test.mosquitto.org`
- Try a different network if behind firewall

### ESP32 not detected
- Check USB cable is data-capable (not charge-only)
- Install CH340 or CP2102 drivers if needed
- Check Device Manager for COM port
- Try a different USB port

### Dashboard not loading
- Check port 3000 is available
- Check backend is running: http://localhost:8000/api/health
- Clear browser cache
- Try a different browser

### "Module not found" errors
```powershell
cd backend
..\.venv\Scripts\pip install -r requirements.txt
```

---

## Quick Commands

| Task | Command |
|------|---------|
| Start system | `.\scripts\rise.ps1` |
| Stop system | `.\scripts\rise-stop.ps1` |
| Test system | `.\scripts\quick-test.ps1` |
| View backend logs | Check terminal with uvicorn output |
| View gateway logs | Check terminal with Serial Gateway output |
| Reset database | Delete `backend/aquabuzz.db` and restart |

---

## URLs

- **Dashboard**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **API Health**: http://localhost:8000/api/health
- **Leaderboard API**: http://localhost:8000/api/leaderboard
- **Runs API**: http://localhost:8000/api/runs
- **Players API**: http://localhost:8000/api/players

---

## Architecture Diagram

```
┌─────────────┐
│   ESP32     │ ← Touch sensor maze
│  (USB)      │
└──────┬──────┘
       │ 115200 baud JSON
┌──────▼──────────────────────┐
│  Laptop                     │
│  ┌────────────────────┐     │
│  │ Serial Gateway     │     │  Auto-detects
│  │ (Python)           │     │  COM port
│  └────────┬───────────┘     │
│           │                 │
│  Any WiFi connection OK     │
└───────────┼─────────────────┘
            │ MQTT
┌───────────▼──────────────┐
│ test.mosquitto.org:1883  │  Public broker
└───────────┬──────────────┘
            │
┌───────────▼────────────┐
│  FastAPI Backend       │  Processes events
│  (Python/SQLite)       │  Intelligence modules
└───────────┬────────────┘
            │
┌───────────▼────────────┐
│  Dashboard (Browser)   │  Real-time updates
│  HTML/JavaScript       │  Auto-refresh 5s
└────────────────────────┘
```

---

## Next Steps

1. ✅ System is running
2. ✅ Dashboard is accessible
3. ⏳ Connect ESP32 via USB
4. ⏳ Play the maze game
5. ⏳ View statistics and leaderboard
6. ⏳ Explore intelligence insights

---

## Support

For detailed implementation information, see: **IMPLEMENTATION_REPORT.md**

For architecture details, see: **docs/architecture.md**

For troubleshooting, see: **docs/troubleshooting.md**

---

**Have fun with AquaBuzz! 🎮⚡**
