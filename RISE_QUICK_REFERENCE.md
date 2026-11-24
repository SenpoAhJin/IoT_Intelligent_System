# AquaBuzz RISE - Quick Reference Card

## ✅ REPAIR STATUS: COMPLETE

Both `rise.ps1` and `rise-stop.ps1` have been completely repaired with **ZERO PARSER ERRORS**.

---

## 🚀 START THE SYSTEM

```powershell
cd "C:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS"
.\scripts\rise.ps1
```

**What it does:**
1. Validates project requirements
2. Checks internet connectivity
3. Starts FastAPI Backend (port 8000)
4. Starts Serial Gateway (USB to MQTT)
5. Starts Dashboard (port 3000+)
6. Opens browser automatically

**Expected Time:** 30-60 seconds

---

## 🛑 STOP THE SYSTEM

```powershell
.\scripts\rise-stop.ps1
```

**What it does:**
1. Stops tracked AquaBuzz processes
2. Protects ForgeMind processes (never touches them)
3. Removes process tracker file
4. Shows summary of stopped services

**Expected Time:** 2-5 seconds

---

## 🔍 WHAT WAS FIXED

### Problem:
- **Unicode characters** (✓, →) caused parser errors
- **Line 356-357** had corrupted encoding
- **Variable conflicts** with PowerShell reserved `$PID`

### Solution:
- ✅ All Unicode replaced with ASCII ([OK], ->)
- ✅ Renamed variables ($BackendProcessId not $BackendPid)
- ✅ Added ForgeMind process protection
- ✅ Enhanced duplicate process detection
- ✅ Improved error messages

### Result:
```
rise.ps1: NO PARSER ERRORS ✅
rise-stop.ps1: NO PARSER ERRORS ✅
```

---

## 🎯 KEY FEATURES

### Smart Backend Reuse
- Detects existing AquaBuzz backend
- Tests `/api/health` endpoint
- Reuses if healthy (no duplicates)
- Rejects if port owned by ForgeMind

### Gateway Protection
- Checks for existing gateway process
- Doesn't start duplicates
- Continues if script missing
- Waits for ESP32 connection

### Dashboard Flexibility
- Tries ports: 3000, 3001, 3002, 8080, 8081
- Reuses existing dashboard if detected
- Auto-selects first available port
- Shows selected port in console

---

## 🔧 TROUBLESHOOTING

### "Port 8000 is occupied"
**Solution:** Stop conflicting process first
```powershell
# Check what's using port 8000
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
# Stop specific PID
Stop-Process -Id <PID>
# Then run rise again
```

### "Dashboard not accessible"
**Check:** What port was actually used?
```powershell
# Look for dashboard port in console output
# Or check process tracker
Get-Content .aquabuzz-processes.json | ConvertFrom-Json
```

### "Gateway not starting"
**Check:** Is serial_gateway.py present?
```powershell
Test-Path backend\serial_gateway.py
# If missing, gateway will be skipped (backend/dashboard still start)
```

---

## 📊 VALIDATION COMMANDS

### Check Backend Health
```powershell
Invoke-RestMethod -Uri 'http://localhost:8000/api/health'
```

### Check Dashboard
```powershell
Invoke-WebRequest -Uri 'http://localhost:3000' -UseBasicParsing
```

### Check Running Processes
```powershell
Get-Content .aquabuzz-processes.json | ConvertFrom-Json
```

### Check MQTT Connectivity
```powershell
Test-Connection test.mosquitto.org
```

---

## 📁 KEY FILES

| File | Purpose | Status |
|------|---------|--------|
| `scripts/rise.ps1` | Startup script | ✅ Repaired |
| `scripts/rise-stop.ps1` | Shutdown script | ✅ Repaired |
| `.aquabuzz-processes.json` | Process tracker | Auto-generated |
| `backend/.env` | Configuration | Existing |
| `backend/serial_gateway.py` | USB gateway | Existing |
| `dashboard/index.html` | Dashboard | Existing |

---

## 🔒 SAFETY FEATURES

### ForgeMind Protection
- **NEVER** terminates ForgeMind processes
- Checks command line for `arise`, `rest`, `ForgeMind`
- Throws error if ForgeMind owns required port

### Process Verification
- Checks process name AND command line
- Verifies AquaBuzz ownership before terminating
- Skips unknown processes (reports details)

### Graceful Degradation
- Backend failure doesn't block gateway/dashboard
- Gateway missing doesn't block backend/dashboard
- Dashboard port conflict tries alternate ports

---

## 📈 CURRENT SYSTEM STATUS

### Backend
- **Status:** ✅ Running (healthy)
- **Port:** 8000
- **MQTT:** Connected to test.mosquitto.org
- **Endpoint:** http://localhost:8000/api/health

### Gateway
- **Status:** ⏳ Ready (waiting for rise)
- **Function:** USB Serial → MQTT bridge
- **Note:** Waits for ESP32 on COM port

### Dashboard
- **Status:** ⏳ Ready (waiting for rise)
- **Ports:** 3000, 3001, 3002, 8080, 8081
- **URL:** Auto-selected on startup

---

## 🎮 USAGE WORKFLOW

### First Time Setup
```powershell
# 1. Navigate to project
cd "C:\...\Intelligent_System_IS"

# 2. Start system
.\scripts\rise.ps1

# 3. Wait for browser to open
# Dashboard should appear at http://localhost:3000

# 4. Verify backend health
Invoke-RestMethod -Uri 'http://localhost:8000/api/health'

# 5. Connect ESP32 via USB (optional)
# Gateway will auto-detect COM port
```

### Daily Usage
```powershell
# Start
rise

# Work with system...

# Stop
rise-stop
```

### After System Restart
```powershell
# Clean slate
rise-stop  # (cleans up any stuck processes)
rise       # (fresh start)
```

---

## 📝 PROCESS TRACKING

### Process Tracker Location
`.aquabuzz-processes.json`

### Format
```json
{
  "backend": {
    "pid": 12345,
    "port": 8000,
    "url": "http://localhost:8000",
    "started_at": "2026-11-24T21:30:00"
  },
  "gateway": {
    "pid": 12346,
    "port": 0,
    "url": "USB Serial",
    "started_at": "2026-11-24T21:30:05"
  },
  "dashboard": {
    "pid": 12347,
    "port": 3000,
    "url": "http://localhost:3000",
    "started_at": "2026-11-24T21:30:10"
  }
}
```

### Usage
```powershell
# View tracked processes
Get-Content .aquabuzz-processes.json

# Parse as object
$processes = Get-Content .aquabuzz-processes.json | ConvertFrom-Json

# Access specific service
$processes.backend.pid
```

---

## 🌐 NETWORK ARCHITECTURE

```
┌─────────────┐
│   ESP32     │ (USB Serial, No WiFi needed)
│  Optional   │
└──────┬──────┘
       │ 115200 baud JSON
┌──────▼──────────────────────┐
│  Laptop                     │
│  ┌────────────────────┐     │
│  │ Serial Gateway     │     │
│  │ auto COM detect    │     │
│  └────────┬───────────┘     │
│           │                 │
│  Any WiFi connection OK     │
└───────────┼─────────────────┘
            │ Public MQTT
┌───────────▼──────────────┐
│ test.mosquitto.org:1883  │
└───────────┬──────────────┘
            │
┌───────────▼────────────┐
│  FastAPI Backend       │
│  Port 8000             │
│  SQLite: aquabuzz.db   │
└───────────┬────────────┘
            │
┌───────────▼────────────┐
│  Dashboard             │
│  Port 3000+            │
│  Auto-refresh 5s       │
└────────────────────────┘
```

---

## ✨ WHAT'S NEW

### Enhanced Safety
- ForgeMind process detection
- Command-line based process verification
- Multiple safety checks before termination

### Smart Reuse
- Reuses healthy existing backend
- Reuses existing gateway if running
- Reuses existing dashboard if detected

### Better Diagnostics
- Shows process details on conflicts
- Displays selected dashboard port
- Reports gateway status (waiting for ESP32)
- Clear error messages with solutions

### ASCII Output
- All Unicode characters removed
- Compatible with PowerShell 5.1
- No encoding issues

---

## 📞 SUPPORT

### Full Documentation
- **Repair Report:** `RISE_REPAIR_REPORT.md`
- **Implementation:** `IMPLEMENTATION_REPORT.md`
- **Quick Start:** `QUICKSTART.md`

### Common Issues
1. **Parser Errors:** ✅ FIXED (zero errors now)
2. **Port Conflicts:** ✅ Handled gracefully
3. **Duplicate Processes:** ✅ Prevented with smart reuse
4. **ForgeMind Conflicts:** ✅ Protected automatically

---

**Last Updated:** November 24, 2026  
**Status:** Production Ready ✅  
**Version:** 2.0 (Complete Repair)
