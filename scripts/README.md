# WireBuzz `arise` - One-Command Startup

## Quick Start

### 1. Install the Command (One-Time Setup)

From the WireBuzz project root:

```powershell
.\scripts\install-arise-command.ps1
```

This adds the `arise` function to your PowerShell profile.

### 2. Reload Your Profile (Current Terminal Only)

```powershell
. $PROFILE
```

**Note**: New PowerShell windows automatically have the `arise` command available.

### 3. Start WireBuzz

```powershell
arise
```

That's it! All services will start automatically.

## What `arise` Does

1. **Validates** your environment (Python venv, Mosquitto, project structure)
2. **Starts Mosquitto** MQTT broker on port 1883 (or reuses existing)
3. **Starts FastAPI** backend on port 8000 (or reuses existing)
4. **Starts Dashboard** HTTP server on port 3000 (or reuses existing)
5. **Verifies health** of all services with actual HTTP checks
6. **Opens browser** tabs for dashboard, API docs, and health endpoint

## Command Options

```powershell
# Standard usage
arise

# Skip browser opening
arise -SkipBrowser

# Show detailed logs
arise -Verbose

# Combined
arise -SkipBrowser -Verbose
```

## Service Windows

Each service runs in a separate PowerShell window:

- **WIREBUZZ - MQTT BROKER**: Mosquitto logs
- **WIREBUZZ - FASTAPI BACKEND**: FastAPI/Uvicorn logs  
- **WIREBUZZ - DASHBOARD**: HTTP server logs

You can see real-time logs for troubleshooting.

## Idempotent Operation

Running `arise` multiple times is safe:

- Detects already-running services
- Reuses existing processes
- Never creates duplicates

## URLs After Startup

- **Dashboard**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

## Troubleshooting

### "Could not find WireBuzz project root"

You're not in the correct directory.

**Solution**:
```powershell
cd "C:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS"
arise
```

### "Python virtual environment not found"

The `.venv` doesn't exist.

**Solution**:
```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r backend\requirements.txt
arise
```

### "Backend dependencies not installed"

**Solution**:
```powershell
.\.venv\Scripts\pip install -r backend\requirements.txt
arise
```

### "Mosquitto not found"

**Solution**: Install Mosquitto from https://mosquitto.org/download/ to `C:\Program Files\mosquitto\`

Or edit `scripts/arise.ps1` line 8 to point to your Mosquitto installation.

### Port Already in Use

If another application occupies a required port:

**Find what's using the port**:
```powershell
Get-NetTCPConnection -LocalPort 1883 -State Listen  # MQTT
Get-NetTCPConnection -LocalPort 8000 -State Listen  # Backend
Get-NetTCPConnection -LocalPort 3000 -State Listen  # Dashboard
```

**Stop the process**:
```powershell
Stop-Process -Id <PID>
```

### Backend Fails Health Checks

Check the **WIREBUZZ - FASTAPI BACKEND** window for error messages.

Common issues:
- Database initialization error
- Missing dependencies
- MQTT connection failure

### MQTT Connection Warning

The backend started but couldn't connect to MQTT.

**Check**:
1. Is Mosquitto running? (Check the MQTT BROKER window)
2. Is `mosquitto.conf` correct?
3. Is port 1883 blocked by firewall?

## Stopping Services

### Close All Services

Close the three service PowerShell windows.

### Stop Individual Services

**Mosquitto**:
```powershell
Get-Process mosquitto | Stop-Process
```

**Backend**:
```powershell
$pid = (Get-NetTCPConnection -LocalPort 8000).OwningProcess
Stop-Process -Id $pid
```

**Dashboard**:
```powershell
$pid = (Get-NetTCPConnection -LocalPort 3000).OwningProcess
Stop-Process -Id $pid
```

## Configuration

### Change Ports

Edit `scripts/arise.ps1`:

```powershell
$MOSQUITTO_PORT = 1883   # Line 10
$BACKEND_PORT = 8000     # Line 11
$DASHBOARD_PORT = 3000   # Line 12
```

### Change Mosquitto Path

Edit `scripts/arise.ps1` line 8:

```powershell
$MOSQUITTO_EXE = "C:\Your\Custom\Path\mosquitto.exe"
```

### Adjust Health Check Timing

Edit `scripts/arise.ps1`:

```powershell
$HEALTH_CHECK_RETRIES = 10   # Line 13
$HEALTH_CHECK_DELAY = 2      # Line 14 (seconds)
```

## Uninstalling

1. Open your PowerShell profile:
```powershell
notepad $PROFILE
```

2. Find and delete the section marked:
```powershell
# WIREBUZZ ARISE COMMAND
```

3. Save and reload:
```powershell
. $PROFILE
```

## Testing After Installation

```powershell
# Test 1: First run
arise

# Test 2: Run again (should reuse services)
arise

# Test 3: With options
arise -SkipBrowser -Verbose

# Test 4: Generate sample data
.\.venv\Scripts\python.exe tools\simulator.py --runs 20 --players 2
```

## Comparison with Manual Startup

### Before `arise`:

```powershell
# Terminal 1
cd backend
..\.venv\Scripts\activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2
& "C:\Program Files\mosquitto\mosquitto.exe" -c mosquitto.conf -v

# Terminal 3
.\.venv\Scripts\python.exe -m http.server 3000 --directory dashboard --bind 127.0.0.1

# Then manually open browser tabs
```

### With `arise`:

```powershell
arise
```

## Security Notes

### MQTT Broker

The default `mosquitto.conf` allows anonymous connections on `localhost:1883`.

**For local development**: This is fine.

**For ESP32 on local network**: Works, but consider adding authentication.

**To add authentication**:

1. Create password file:
```powershell
& "C:\Program Files\mosquitto\mosquitto_passwd.exe" -c mosquitto.passwd username
```

2. Update `mosquitto.conf`:
```
listener 1883
allow_anonymous false
password_file mosquitto.passwd
```

3. Update ESP32 firmware `secrets.h` with credentials

4. Update backend `.env`:
```
MQTT_USERNAME=username
MQTT_PASSWORD=password
```

### Backend API

The backend binds to `127.0.0.1` (localhost only). External network access is blocked.

**To allow network access** (e.g., for mobile dashboard):

Edit `arise.ps1` line 185:
```powershell
$backendCmd = "& '$pythonExe' -m uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT"
```

**Warning**: Only do this on trusted networks.

## Files Created

- `scripts/arise.ps1` - Main startup script
- `scripts/install-arise-command.ps1` - Profile installer
- Adds function to: `$PROFILE` (typically `C:\Users\<username>\Documents\WindowsPowerShell\profile.ps1`)

## Technical Details

### Port Checking

Uses `Get-NetTCPConnection` to detect listening ports.

### Health Verification

- **Mosquitto**: TCP port listening check
- **Backend**: HTTP GET to `/api/health` with 10 retries
- **Dashboard**: HTTP GET to root with 8 retries

### Process Management

Each service runs in a separate `powershell.exe` process with `-NoExit` to keep windows open.

### Error Handling

- `$ErrorActionPreference = "Continue"` - Non-fatal errors don't stop execution
- Individual service failures are reported
- Overall status shows which services succeeded/failed

## Support

For issues:

1. Run with `-Verbose` flag to see detailed logs
2. Check service terminal windows for error messages
3. Verify prerequisites with the validation output
4. Consult `docs/arise-command.md` for comprehensive documentation
5. Check `docs/troubleshooting.md` for WireBuzz-specific issues

## Version

- **Version**: 1.0.0
- **Created**: 2024-11-24
- **Platform**: Windows PowerShell
- **Project**: WireBuzz Intelligent IoT System

---

**You can now start your entire WireBuzz system with one command: `arise`**
