# AquaBuzz Intelligent System - Quick Start Guide

## One-Command Startup System

AquaBuzz now features a complete automated startup system. You can start the entire system with a single command.

## Daily Usage

### Starting the System

Open PowerShell (or VS Code's integrated terminal) and type:

```powershell
rise
```

That's it! The system will automatically:
- ✓ Start the FastAPI backend
- ✓ Start the Serial-to-MQTT gateway
- ✓ Start the dashboard server
- ✓ Open your browser to the dashboard
- ✓ Verify all services are healthy
- ✓ Connect to MQTT broker

### Stopping the System

When you're done:

```powershell
rise-stop
```

This safely stops all AquaBuzz services without affecting other applications.

## First-Time Setup

The `rise` and `rise-stop` commands are already registered in your PowerShell profile.

**Verification**: Open a new PowerShell window and type:
```powershell
Get-Command rise
```

If you see the command definition, you're ready to go!

## System Architecture

```
ESP32 (via USB) → Serial Gateway → MQTT Broker → Backend API → Dashboard
```

- **Backend**: FastAPI REST API (Port 8000)
- **Gateway**: Python serial-to-MQTT bridge
- **Dashboard**: HTTP server (Port 3000)
- **MQTT**: Public test.mosquitto.org broker

## Network Independence

✓ No WiFi credentials needed on ESP32  
✓ Works with any laptop WiFi connection  
✓ Gateway auto-reconnects if internet drops  
✓ ESP32 auto-detected via USB (no manual COM port configuration)

## What Happens When You Run `rise`

1. **Validation**: Checks project structure, Python environment, and configuration
2. **Backend**: Starts FastAPI with uvicorn (or reuses if already running)
3. **Gateway**: Starts serial gateway (or reuses if already running)
4. **Dashboard**: Starts HTTP server (or reuses if already running)
5. **Verification**: Confirms all services are healthy
6. **Browser**: Opens dashboard automatically

## Expected Output

```
============================================================
  AQUABUZZ INTELLIGENT SYSTEM - RISE
============================================================

[OK] Project requirements validated
[OK] Internet connectivity verified
[OK] Backend is ready (http://localhost:8000)
[OK] MQTT connected to test.mosquitto.org
[OK] Serial Gateway started
[OK] Dashboard is ready (http://localhost:3000)

============================================================
  AQUABUZZ STARTUP COMPLETE
============================================================

Services Running:
  [OK] Backend API
       http://localhost:8000
       PID: 12345

  [OK] Serial Gateway
       USB Serial to MQTT
       PID: 12346

  [OK] Dashboard
       http://localhost:3000
       PID: 12347

Next Steps:
  1. Connect ESP32 via USB (auto-detected)
  2. Open the maze and start playing
  3. Watch results appear on dashboard

To stop all services:
  rise-stop
```

## Using the System

### 1. Connect ESP32
- Plug ESP32 into USB
- Gateway automatically detects COM port
- Watch gateway window for connection messages

### 2. Play the Game
- Open the physical maze
- Touch and navigate through the maze
- Hits are recorded in real-time

### 3. View Results
- Dashboard updates live via Server-Sent Events (SSE)
- See runs, scores, and hit statistics
- View performance trends and insights

## Troubleshooting

### Services Won't Start

```powershell
rise-stop
rise
```

### Port Conflicts

If port 8000 or 3000 is in use by another application:
1. Stop the conflicting application, OR
2. Modify `scripts/rise.ps1` to use different ports

### ESP32 Not Detected

- Verify ESP32 is plugged in via USB
- Check Device Manager for COM ports
- Gateway will keep trying to connect automatically
- Backend and dashboard still work without ESP32

### MQTT Connection Issues

- MQTT connection may take 10-30 seconds
- Backend will keep retrying automatically
- Gateway buffers events until MQTT connects

### Process Tracker Issues

If processes don't stop cleanly:

```powershell
Remove-Item .aquabuzz-processes.json -Force
rise-stop
rise
```

## Advanced Usage

### Manual Service Management

If you need finer control, you can still start services individually:

```powershell
# Backend only
python -m uvicorn app.main:app --app-dir .\backend --port 8000

# Gateway only
python .\backend\serial_gateway.py

# Dashboard only
python -m http.server 3000 --directory .\dashboard
```

### View Service Status

```powershell
# Check backend health
Invoke-WebRequest http://localhost:8000/api/health | ConvertFrom-Json

# Check running processes
Get-Process -Name python
```

### Configuration

Edit `backend/.env` to customize:
- MQTT broker settings
- Database location
- API port
- Logging level

## Service URLs

- **Dashboard**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

## Important Notes

- The `rise` command is **idempotent** - running it multiple times won't create duplicate services
- Services are tracked in `.aquabuzz-processes.json`
- ForgeMind and other Python projects are **never affected** by `rise-stop`
- ESP32 device remains active after `rise-stop` (it's not controlled by the PC)

## Support

If you encounter issues:
1. Check this guide's troubleshooting section
2. Review `QUICKSTART_GUIDE.md` for detailed technical information
3. Check service logs in their respective terminal windows

---

**You're ready to go! Just type `rise` and start playing.**
