# AquaBuzz Serial Gateway - Quick Start Guide

## ⚡ 3-Step Startup

```powershell
# 1. Navigate to project
cd "C:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS"

# 2. Start services
.\scripts\rise.ps1

# 3. Play the game!
# Touch wire to start → Navigate maze → Touch finish pad
```

---

## ✅ What's New

### Enhanced Serial Gateway v2

**Event Normalization:**
- ✅ Automatically adds `device_id`, `player_id`, `run_uid`
- ✅ Generates unique run identifiers
- ✅ Maintains run state throughout game

**Heartbeat Publishing:**
- ✅ Publishes every 10 seconds to `aquabuzz/aquabuzz-001/heartbeat`
- ✅ Dashboard shows online/offline status correctly
- ✅ Backend detects device within 30 seconds

**Network Independence:**
- ✅ Works with any WiFi network
- ✅ Auto-reconnects when internet returns
- ✅ Supports mobile hotspot

**COM Port Detection:**
- ✅ Auto-detects ESP32 on COM3 (USB-SERIAL CH340)
- ✅ Manual override available: `$env:COM_PORT="COM3"`

---

## 📡 Architecture

```
ESP32 (COM3) → Gateway → MQTT → Backend → Dashboard
```

**What Changed:**
- Gateway now normalizes ESP32 events
- Gateway publishes heartbeats
- Backend processes complete events
- Dashboard shows device status

**What Stayed the Same:**
- ✅ ESP32 firmware unchanged
- ✅ Game mechanics identical
- ✅ Sensor wiring unchanged
- ✅ Buzzer behavior unchanged

---

## 🎮 Testing Your Game

### 1. Start Services

```powershell
.\scripts\rise.ps1
```

**Expected Output:**
```
Starting FastAPI Backend...
  Backend ready on port 8000
Starting Serial-to-MQTT Gateway...
  Serial Gateway started (PID: xxxx)
Starting Dashboard HTTP Server...
  Dashboard ready on port 3000
```

### 2. Verify Connection

**Gateway Terminal Should Show:**
```
[Serial] Found potential ESP32 on COM3
[Serial] Connected to ESP32 on COM3
[MQTT] Connected to test.mosquitto.org:1883
[Gateway] Session ID: a1b2c3d4
[Heartbeat] Published (serial: true, mqtt: true)
```

### 3. Check Dashboard

Open http://localhost:3000

**Should Display:**
- Device aquabuzz-001: 🟢 Online
- Last heartbeat: (recent timestamp)
- Backend: 🟢 healthy
- MQTT: 🟢 Connected

### 4. Play Game

1. **Start:** Touch maze wire
   - Gateway shows: `[Gateway] Started run: aquabuzz-001-a1b2c3d4-1`

2. **During:** Touch wire = hit detected
   - Gateway shows: `[MQTT] Published event: hit_start`
   - Gateway shows: `[MQTT] Published event: hit_end`

3. **Finish:** Touch finish pad
   - Gateway shows: `[Gateway] Completed run: aquabuzz-001-a1b2c3d4-1`
   - Dashboard shows new run in "Recent Runs"

---

## 📊 Expected Events

### Run Start (Touch Wire)
```
[Serial] Raw: {"run":1,"event":"run_start","t_ms":0}
[Gateway] Started run: aquabuzz-001-a1b2c3d4-1
[Gateway] Normalized: {"device_id":"aquabuzz-001","player_id":"guest",...}
[MQTT] Published event: run_start
```

### Hit Detection (Touch During Game)
```
[Serial] Raw: {"run":1,"event":"hit_start","hit":1,"t_ms":1234}
[MQTT] Published event: hit_start

[Serial] Raw: {"run":1,"event":"hit_end","hit":1,"t_ms":1534,"dur_ms":300}
[MQTT] Published event: hit_end
```

### Run Finish (Touch Finish Pad)
```
[Serial] Raw: {"run":1,"event":"run_finish","t_ms":15000,"hits":3,...}
[Gateway] Completed run: aquabuzz-001-a1b2c3d4-1
[MQTT] Published event: run_finish
```

---

## 🔧 Configuration

### Environment Variables

```powershell
# Device identifier
$env:DEVICE_ID="aquabuzz-001"

# Default player
$env:DEFAULT_PLAYER_ID="guest"

# Explicit COM port (optional)
$env:COM_PORT="COM3"

# Then start
.\scripts\rise.ps1
```

### Change Player Name

```powershell
$env:DEFAULT_PLAYER_ID="Alice"
.\scripts\rise.ps1
```

All subsequent games will be recorded under player "Alice"

---

## 🧪 Testing Commands

### Quick Test
```powershell
.\scripts\test-integration.ps1
```

### Backend Health
```powershell
Invoke-RestMethod -Uri 'http://localhost:8000/api/health'
```

### Recent Runs
```powershell
Invoke-RestMethod -Uri 'http://localhost:8000/api/runs?limit=5'
```

### Leaderboard
```powershell
Invoke-RestMethod -Uri 'http://localhost:8000/api/leaderboard'
```

---

## ❌ Troubleshooting

### Gateway Can't Find ESP32

**Problem:** `[Serial] No ESP32 found`

**Solutions:**
1. Check USB cable (must be data cable, not charge-only)
2. Verify COM3 in Device Manager
3. Close Arduino IDE Serial Monitor
4. Set explicit port: `$env:COM_PORT="COM3"`

### Device Shows Offline

**Problem:** Dashboard shows red offline indicator

**Solutions:**
1. Check gateway terminal for heartbeat messages
2. Verify MQTT connection: `[MQTT] Connected`
3. Restart gateway if needed

### Events Not Appearing

**Problem:** Game runs but dashboard doesn't update

**Solutions:**
1. Verify gateway shows "Published event" messages
2. Check backend terminal for MQTT connection
3. Test backend health endpoint
4. Refresh dashboard manually

### Port Already in Use

**Problem:** `Port 8000 already in use`

**Solution:**
```powershell
.\scripts\rise-stop.ps1  # Stop existing services
.\scripts\rise.ps1        # Start fresh
```

---

## 🛑 Stopping Services

```powershell
.\scripts\rise-stop.ps1
```

**Expected:**
```
Stopping backend (PID: xxxx, Port: 8000)...
  Stopped backend
Stopping gateway (PID: xxxx, Port: N/A)...
  Stopped gateway
Stopping dashboard (PID: xxxx, Port: 3000)...
  Stopped dashboard
```

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `backend/serial_gateway.py` | Enhanced gateway with normalization |
| `firmware/aquabuzz_core/aquabuzz_core.ino` | ESP32 firmware (unchanged) |
| `scripts/rise.ps1` | Start all services |
| `scripts/rise-stop.ps1` | Stop all services |
| `scripts/test-integration.ps1` | Integration tests |
| `dashboard/index.html` | Web dashboard |

---

## 📖 Documentation

- **Complete Report:** `USB_SERIAL_INTEGRATION_REPORT.md`
- **Implementation:** `IMPLEMENTATION_REPORT.md`
- **Rise Repair:** `RISE_REPAIR_REPORT.md`
- **This Guide:** `SERIAL_GATEWAY_QUICK_START.md`

---

## ✨ What Works Now

✅ ESP32 connects via USB (no WiFi needed)  
✅ Gateway normalizes all events automatically  
✅ Heartbeat published every 10 seconds  
✅ Dashboard shows real device status  
✅ All game events recorded in database  
✅ Intelligence analysis triggered automatically  
✅ Works across WiFi network changes  
✅ Auto-reconnection on disconnect  
✅ Player assignment (default: guest)  
✅ Unique run IDs for every game  

---

## 🎯 Success Criteria

**After running `rise`:**

1. ✅ Gateway terminal shows: `Connected to ESP32 on COM3`
2. ✅ Gateway terminal shows: `Connected to test.mosquitto.org:1883`
3. ✅ Gateway terminal shows: `Heartbeat Published`
4. ✅ Dashboard shows: aquabuzz-001 🟢 Online
5. ✅ Touch wire → Run record created
6. ✅ Touch finish → Run completed with stats
7. ✅ Dashboard updates automatically

**When all criteria met: System is working perfectly! 🚀**

---

**Last Updated:** November 24, 2026  
**Status:** Production Ready ✅  
**Firmware Version:** aquabuzz_core v6 (unchanged)  
**Gateway Version:** v2 (enhanced)
