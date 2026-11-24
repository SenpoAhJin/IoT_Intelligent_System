# WireBuzz One-Command Startup Guide

## Overview

The `rise` command provides one-command startup automation for the entire WireBuzz Intelligent IoT System. Instead of manually starting Mosquitto, FastAPI, and the dashboard server, simply type `rise` and everything starts automatically.

## Features

✅ **Automatic Service Discovery** - Detects and reuses already-running services  
✅ **Health Verification** - Tests each component before declaring success  
✅ **Dynamic Port Selection** - Automatically finds available ports for the dashboard  
✅ **Process Tracking** - Safely stops only WireBuzz-owned processes  
✅ **Visible Terminals** - Each service runs in its own window with live logs  
✅ **Browser Automation** - Automatically opens dashboard and API docs  
✅ **Safety First** - Never overwrites the existing `arise` command  

---

## Installation

### Step 1: Install the Commands

Open PowerShell in your WireBuzz project directory and run:

```powershell
.\scripts\install-rise-command.ps1
```

This will:
- Verify all required scripts exist
- Check for naming conflicts
- Add `rise` and `rise-stop` functions to your PowerShell profile
- Preserve your existing `arise` and `rest` commands

### Step 2: Reload Your Profile

After installation, either:

**Option A:** Reload the current session
```powershell
. $PROFILE
```

**Option B:** Open a new PowerShell window (recommended)

---

## Daily Usage

### Starting WireBuzz

Navigate to your project directory and run:

```powershell
rise
```

The system will:
1. ✅ Validate project structure
2. ✅ Start/detect Mosquitto MQTT broker (port 1883)
3. ✅ Start/detect FastAPI backend (port 8000)
4. ✅ Start dashboard server (dynamic port: 3000, 3001, 3002, 8080, or 8081)
5. ✅ Verify MQTT connectivity
6. ✅ Open browser tabs:
   - Dashboard
   - API Documentation (`/docs`)
   - Health endpoint (`/api/health`)

### Stopping WireBuzz

To gracefully stop all WireBuzz services:

```powershell
rise-stop
```

This will:
- Stop only processes started by `rise`
- Verify process ownership before stopping
- Preserve other services on the same ports
- Display a shutdown summary

---

## What Gets Started

### 1. Mosquitto MQTT Broker
- **Port:** 1883
- **Window Title:** (Mosquitto native window)
- **Configuration:** Uses `mosquitto.conf` from project root
- **Reuse Logic:** If port 1883 is already in use, tests connectivity and reuses if healthy

### 2. FastAPI Backend
- **Port:** 8000
- **Window Title:** "WIREBUZZ — FASTAPI BACKEND"
- **Working Directory:** `backend/`
- **Command:** `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- **Health Check:** `http://127.0.0.1:8000/api/health`
- **Reuse Logic:** If port 8000 is already in use, tests health endpoint and reuses if responding

### 3. Dashboard Server
- **Port:** Dynamically selected (3000 → 3001 → 3002 → 8080 → 8081)
- **Window Title:** "WIREBUZZ — DASHBOARD SERVER"
- **Working Directory:** `dashboard/`
- **Command:** `python -m http.server <PORT> --bind 127.0.0.1`
- **Port Selection:** Tries each port in order, verifies it can actually bind

---

## Port Conflict Resolution

### Dashboard Port Selection

The startup script tries ports in this order:

1. **3000** (preferred)
2. **3001**
3. **3002**
4. **8080**
5. **8081**

The first available port that can successfully bind is selected automatically.

### Troubleshooting Port Issues

If all dashboard ports are occupied:

```powershell
# Check what's using the ports
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in @(3000, 3001, 3002, 8080, 8081) } | Format-Table LocalAddress, LocalPort, State, OwningProcess
```

To find what process owns a specific PID:
```powershell
Get-Process -Id <PID>
```

To stop a specific process:
```powershell
Stop-Process -Id <PID>
```

---

## Validation Checks

The startup script validates:

- ✅ Project directory exists
- ✅ Python virtual environment (`.venv`) exists
- ✅ Python executable (`.venv\Scripts\python.exe`) exists
- ✅ Backend main file (`backend\app\main.py`) exists
- ✅ Dashboard index file (`dashboard\index.html`) exists
- ✅ Mosquitto executable (`C:\Program Files\mosquitto\mosquitto.exe`) exists

If any validation fails, the script stops immediately with a clear error message.

---

## Process Tracking

WireBuzz maintains a process tracking file:

**Location:** `.wirebuzz-processes.json`

This file stores:
- Process IDs (PIDs)
- Port numbers
- Service URLs
- Start timestamps

The `rise-stop` command uses this file to safely stop only WireBuzz-owned processes.

**Safety Features:**
- Verifies process still exists before stopping
- Confirms process owns the expected port
- Never stops processes that don't match the tracked PID + port combination

---

## Service Health Verification

### MQTT Broker
- Tests connectivity using `mosquitto_pub` if available
- Verifies port 1883 is listening
- Checks process is responding

### FastAPI Backend
- HTTP GET to `/api/health`
- Verifies JSON response contains expected fields
- Checks `mqtt_connected` status
- Waits up to 20 seconds for startup

### Dashboard
- HTTP GET to dashboard URL
- Verifies HTTP 200 response
- Waits up to 10 seconds for startup

---

## Terminal Windows

Three visible PowerShell windows are created:

### Window 1: MQTT Broker
- Shows Mosquitto verbose logs
- Displays connection events
- Shows topic subscriptions/publishes

### Window 2: FastAPI Backend  
- Shows Uvicorn startup logs
- Displays API requests
- Shows MQTT connection status
- Shows intelligence processing logs

### Window 3: Dashboard Server
- Shows HTTP server logs
- Displays file serving activity
- Shows client requests

**Tip:** Keep these windows visible to monitor real-time activity and troubleshoot issues.

---

## Startup Output Example

```
========================================
  WIREBUZZ STARTUP — VALIDATION
========================================

[12:34:56] [STEP]    Checking project directory...
[12:34:56] [OK]      Project directory found: c:\Users\Alord\...\Intelligent_System_IS
[12:34:56] [STEP]    Checking Python virtual environment...
[12:34:56] [OK]      Virtual environment found
[12:34:56] [STEP]    Checking Python executable...
[12:34:56] [OK]      Python found: Python 3.12.10
[12:34:56] [STEP]    Checking backend files...
[12:34:56] [OK]      Backend main.py found
[12:34:56] [STEP]    Checking dashboard files...
[12:34:56] [OK]      Dashboard index.html found
[12:34:56] [STEP]    Checking Mosquitto...
[12:34:56] [OK]      Mosquitto executable found

[12:34:57] [OK]      All validations passed!

========================================
  STARTING MOSQUITTO MQTT BROKER
========================================

[12:34:58] [STEP]    Starting new Mosquitto broker...
[12:34:58] [OK]      Mosquitto started (PID: 15234)
[12:34:58] [STEP]    Waiting for MQTT broker to be ready...
[12:35:00] [OK]      MQTT broker is ready on port 1883

========================================
  STARTING FASTAPI BACKEND
========================================

[12:35:00] [STEP]    Starting FastAPI backend...
[12:35:00] [OK]      FastAPI started (PID: 15236)
[12:35:00] [STEP]    Waiting for FastAPI to be ready...
..........
[12:35:10] [OK]      FastAPI backend is ready
[12:35:10] [OK]      Backend MQTT connection verified

========================================
  STARTING DASHBOARD SERVER
========================================

[12:35:10] [STEP]    Finding available port for dashboard...
[12:35:10] [INFO]    Port 3000 in use by PID 29636, trying next...
[12:35:10] [OK]      Port 3001 is available and bindable
[12:35:10] [STEP]    Starting dashboard server on port 3001...
[12:35:10] [OK]      Dashboard server started (PID: 15238)
[12:35:10] [STEP]    Waiting for dashboard to be ready...
...
[12:35:13] [OK]      Dashboard server is ready at http://127.0.0.1:3001

========================================
  OPENING BROWSER
========================================

[12:35:13] [STEP]    Opening dashboard...
[12:35:14] [STEP]    Opening API documentation...
[12:35:15] [STEP]    Opening health endpoint...

========================================
             WIREBUZZ SYSTEM
========================================

[OK] Project Directory
[OK] Python Virtual Environment
[OK] Python Dependencies
[OK] Mosquitto Broker (PID: 15234)
[OK] MQTT Port 1883
[OK] FastAPI Backend (PID: 15236)
[OK] SQLite Database
[OK] Backend MQTT Connection
[OK] Dashboard Server (PID: 15238)
[OK] Dashboard HTTP Response

----------------------------------------

DASHBOARD: http://127.0.0.1:3001
API DOCS:  http://127.0.0.1:8000/docs
HEALTH:    http://127.0.0.1:8000/api/health

----------------------------------------

WIREBUZZ IS READY FOR TESTING.

To stop services, run: rise-stop

========================================
```

---

## Troubleshooting

### "rise : The term 'rise' is not recognized"

**Cause:** PowerShell profile not loaded or commands not installed.

**Solution:**
```powershell
# Reload profile
. $PROFILE

# Or reinstall commands
.\scripts\install-rise-command.ps1
```

### "Port 8000 already in use"

**Cause:** Another process is using the backend port.

**Solution:**
```powershell
# Find what's using port 8000
Get-NetTCPConnection -LocalPort 8000 -State Listen

# If it's an old WireBuzz instance, stop it
rise-stop

# If it's something else, stop that process or change the port
```

### "No available ports found"

**Cause:** All dashboard ports (3000-3002, 8080-8081) are occupied.

**Solution:**
```powershell
# Check what's using the ports
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in @(3000, 3001, 3002, 8080, 8081) }

# Stop unnecessary processes or add more ports to the candidate list in rise.ps1
```

### "MQTT broker failed to start"

**Cause:** Mosquitto executable not found or configuration issue.

**Solution:**
1. Verify Mosquitto is installed: `Test-Path "C:\Program Files\mosquitto\mosquitto.exe"`
2. Check `mosquitto.conf` is valid
3. Try starting Mosquitto manually to see error messages

### "Backend MQTT not connected"

**Cause:** Backend started but couldn't connect to MQTT broker.

**Solution:**
1. Check if Mosquitto is actually running
2. Verify port 1883 is accessible
3. Check backend logs in its terminal window
4. Verify firewall isn't blocking localhost connections

### Services won't stop with rise-stop

**Cause:** Process tracker file missing or processes were started manually.

**Solution:**
```powershell
# Manually find and stop WireBuzz processes
Get-Process | Where-Object { $_.ProcessName -in @("python", "mosquitto") }

# Stop specific PIDs
Stop-Process -Id <PID>
```

---

## Advanced Configuration

### Changing Dashboard Port Preferences

Edit `scripts\rise.ps1` and modify the `$DASHBOARD_PORTS` array:

```powershell
$DASHBOARD_PORTS = @(3000, 3001, 3002, 8080, 8081, 5000, 5001)
```

### Changing Backend Port

Edit `scripts\rise.ps1` and modify:

```powershell
$API_PORT = 8000  # Change to your preferred port
```

Also update the backend startup command if needed.

### Using a Different MQTT Broker

If you want to connect to a remote MQTT broker instead of starting Mosquitto locally:

1. Set environment variables before running `rise`:
   ```powershell
   $env:MQTT_BROKER_HOST = "mqtt.example.com"
   $env:MQTT_BROKER_PORT = "1883"
   ```

2. Or edit the backend's `.env` file

3. Comment out the MQTT startup section in `rise.ps1`

---

## Comparison with Manual Startup

### Manual Method (Old Way)
```powershell
# Terminal 1
cd "C:\Program Files\mosquitto"
.\mosquitto.exe -c "c:\...\mosquitto.conf" -v

# Terminal 2
cd backend
..\\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 3
cd dashboard
..\\.venv\Scripts\python.exe -m http.server 3000 --bind 127.0.0.1

# Browser
# Manually open http://localhost:3000
# Manually open http://localhost:8000/docs
```

**Time:** ~2-3 minutes  
**Terminal Windows:** 3 manual setups  
**Browser:** Manual opening  
**Error Handling:** Manual troubleshooting  

### Automated Method (New Way)
```powershell
rise
```

**Time:** ~15-30 seconds  
**Terminal Windows:** Automatic  
**Browser:** Automatic  
**Error Handling:** Automatic validation and health checks  

---

## Safety Guarantees

### 1. **No Conflicts with `arise`**
The installation script checks for existing `arise` and `rest` commands and preserves them completely.

### 2. **Process Ownership Verification**
`rise-stop` verifies:
- Process ID matches tracked ID
- Process owns the expected port
- Never stops unrelated processes

### 3. **Service Reuse**
Running `rise` twice doesn't create duplicate services:
- Detects existing MQTT broker
- Detects existing backend
- Reuses healthy services

### 4. **Port Safety**
- Tests port binding before declaring it available
- Never assumes a port is free without verification
- Falls back to alternative ports automatically

### 5. **Graceful Degradation**
If a component fails:
- Clear error message
- No partial startup
- Safe to retry after fixing the issue

---

## Testing Checklist

After installation, verify:

- [ ] `rise` command is recognized in new PowerShell windows
- [ ] `rise-stop` command is recognized
- [ ] `arise` command still works (from your other project)
- [ ] First `rise` execution starts all services
- [ ] Second `rise` execution reuses existing services
- [ ] Dashboard opens in browser automatically
- [ ] API docs open in browser automatically
- [ ] Health endpoint shows MQTT connected
- [ ] Terminal windows show live logs
- [ ] `rise-stop` stops all services
- [ ] `.wirebuzz-processes.json` is created/deleted appropriately
- [ ] Port conflict handling works (when 3000 is occupied)

---

## File Locations

| File | Purpose |
|------|---------|
| `scripts/rise.ps1` | Main startup script |
| `scripts/rise-stop.ps1` | Shutdown script |
| `scripts/install-rise-command.ps1` | PowerShell profile installer |
| `.wirebuzz-processes.json` | Process tracking (auto-generated) |
| `$PROFILE` | Your PowerShell profile with commands |

---

## Support

If you encounter issues:

1. **Check the terminal windows** - They show real-time logs
2. **Run health check manually**: `http://127.0.0.1:8000/api/health`
3. **Check process tracker**: `Get-Content .wirebuzz-processes.json | ConvertFrom-Json`
4. **Verify ports**: `Get-NetTCPConnection -State Listen`
5. **Check Python**: `.venv\Scripts\python.exe --version`
6. **Check Mosquitto**: `& "C:\Program Files\mosquitto\mosquitto.exe" --help`

---

## Uninstallation

To remove the `rise` commands:

1. Open your PowerShell profile:
   ```powershell
   notepad $PROFILE
   ```

2. Remove these lines:
   ```powershell
   # WireBuzz Commands
   function rise { & 'c:\...\rise.ps1' }
   function rise-stop { & 'c:\...\rise-stop.ps1' }
   ```

3. Save and reload:
   ```powershell
   . $PROFILE
   ```

The scripts in `scripts/` can remain - they won't run unless called explicitly.

---

## Credits

**Project:** WireBuzz Intelligent IoT System  
**Purpose:** Educational IoT project with intelligent behavior analysis  
**Automation:** One-command startup system  
**Compatibility:** Windows 10/11 with PowerShell  

---

**Happy Testing! 🚀**
