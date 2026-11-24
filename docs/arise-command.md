# WireBuzz `arise` Command Documentation

## Overview

The `arise` command is a one-command startup system for the WireBuzz Intelligent IoT Project. It automatically starts and health-checks all required services.

## Quick Start

```powershell
# From the WireBuzz project directory
arise
```

That's it! All services will start, health checks will run, and your browser will open automatically.

## Installation

### Step 1: Install the Command

From the WireBuzz project root, run:

```powershell
.\scripts\install-arise-command.ps1
```

The installer will:
- Add the `arise` function to your PowerShell profile
- Preserve any existing profile contents
- Offer to reload the profile immediately

### Step 2: Reload Your Profile (Current Terminal)

If you want to use `arise` in your current terminal without opening a new one:

```powershell
. $PROFILE
```

### Step 3: Use in New Terminals

The `arise` command is now available in all new PowerShell sessions.

## What `arise` Does

1. **Validates Prerequisites**
   - Checks for required project files
   - Verifies Python virtual environment exists
   - Validates Mosquitto installation
   - Confirms backend dependencies are installed

2. **Starts Mosquitto MQTT Broker**
   - Checks if already running (reuses if so)
   - Launches in a separate visible terminal window
   - Verifies port 1883 is listening
   - Uses the project's `mosquitto.conf`

3. **Starts FastAPI Backend**
   - Checks if already running (reuses if so)
   - Launches using the `.venv` Python interpreter
   - Waits for health endpoint to respond
   - Verifies MQTT connection is established
   - Runs in a separate visible terminal window

4. **Starts Dashboard HTTP Server**
   - Checks if already running (reuses if so)
   - Serves the dashboard on port 3000
   - Verifies HTTP responses
   - Runs in a separate visible terminal window

5. **Opens Browser Tabs**
   - Dashboard: http://localhost:3000
   - API Documentation: http://localhost:8000/docs
   - Health Endpoint: http://localhost:8000/api/health

6. **Displays Status Report**
   - Shows which services are running
   - Reports any failures with diagnostic information
   - Provides access URLs

## Command Options

### Standard Usage

```powershell
arise
```

Starts all services and opens browser tabs.

### Skip Browser Opening

```powershell
arise -SkipBrowser
```

Starts all services but does NOT open browser tabs.

### Verbose Mode

```powershell
arise -Verbose
```

Shows detailed startup logs including:
- Service window launch details
- Health check retry attempts
- Port checking operations

### Combined Options

```powershell
arise -SkipBrowser -Verbose
```

## Service Windows

Each service runs in its own PowerShell window with a descriptive title:

- **WIREBUZZ - MQTT BROKER**: Mosquitto logs
- **WIREBUZZ - FASTAPI BACKEND**: FastAPI/Uvicorn logs
- **WIREBUZZ - DASHBOARD**: HTTP server logs

You can monitor logs in real-time for troubleshooting.

## Idempotency

Running `arise` multiple times is safe:

- If Mosquitto is already running → reuses it
- If FastAPI is already running → reuses it
- If Dashboard is already running → reuses it

No duplicate services will be created.

## Troubleshooting

### "Could not find WireBuzz project root"

**Problem**: You're not in the correct directory.

**Solution**: Navigate to the WireBuzz project root:

```powershell
cd "C:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS"
arise
```

### "Python virtual environment not found"

**Problem**: The `.venv` directory doesn't exist.

**Solution**: Create and activate the virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r backend\requirements.txt
arise
```

### "Backend dependencies not installed"

**Problem**: Required Python packages are missing.

**Solution**: Install dependencies:

```powershell
.\.venv\Scripts\pip install -r backend\requirements.txt
arise
```

### "Mosquitto not found"

**Problem**: Mosquitto is not installed or not at the expected path.

**Solution**: 

1. Download from: https://mosquitto.org/download/
2. Install to `C:\Program Files\mosquitto\`
3. Or edit `scripts/arise.ps1` to update the path

### "Port 1883 occupied"

**Problem**: Another process is using the MQTT port.

**Solution**: Find and stop the conflicting process:

```powershell
Get-NetTCPConnection -LocalPort 1883 -State Listen
# Note the PID, then:
Stop-Process -Id <PID>
arise
```

### "Port 8000 occupied"

**Problem**: Another process is using the backend port.

**Solution**: Either stop the other service, or change the backend port in `arise.ps1`:

```powershell
$BACKEND_PORT = 8001  # Change this line
```

### "Backend failed to respond to health checks"

**Problem**: Backend started but isn't responding.

**Solution**:

1. Check the **WIREBUZZ - FASTAPI BACKEND** window for errors
2. Common issues:
   - Database initialization error
   - Import errors (missing dependencies)
   - MQTT connection failure

### "MQTT Backend Connection" shows warning

**Problem**: Backend started but couldn't connect to MQTT.

**Solution**:

1. Verify Mosquitto is running
2. Check the **WIREBUZZ - MQTT BROKER** window for errors
3. Verify `mosquitto.conf` allows local connections

### arise command not found

**Problem**: Profile not loaded or installation incomplete.

**Solution**:

```powershell
# Reload profile
. $PROFILE

# Or reinstall
.\scripts\install-arise-command.ps1
```

## Manual Service Management

If you need to stop services:

### Stop All Services

Close the three service terminal windows:
- WIREBUZZ - MQTT BROKER
- WIREBUZZ - FASTAPI BACKEND
- WIREBUZZ - DASHBOARD

### Stop Individual Services

**Mosquitto:**
```powershell
Get-Process mosquitto | Stop-Process
```

**Backend:**
```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process
```

**Dashboard:**
```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 3000).OwningProcess | Stop-Process
```

## Configuration

### Default Ports

Edit `scripts/arise.ps1` to change default ports:

```powershell
$MOSQUITTO_PORT = 1883   # MQTT broker
$BACKEND_PORT = 8000     # FastAPI backend
$DASHBOARD_PORT = 3000   # Dashboard server
```

### Mosquitto Path

If Mosquitto is installed elsewhere:

```powershell
$MOSQUITTO_EXE = "C:\Custom\Path\mosquitto.exe"
```

### Timeouts

Adjust health check behavior:

```powershell
$STARTUP_TIMEOUT = 30         # Overall timeout
$HEALTH_CHECK_RETRIES = 10    # Number of retries
$HEALTH_CHECK_DELAY = 2       # Seconds between retries
```

## Security Considerations

### MQTT Broker Configuration

The default `mosquitto.conf` allows anonymous connections on `localhost:1883`:

```
listener 1883
allow_anonymous true
```

**For local development**: This is acceptable.

**For ESP32 network access**: 
- If your ESP32 is on the same local network, this works
- Do NOT expose port 1883 to the internet without authentication

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

### Backend API Access

The backend binds to `127.0.0.1` (localhost only) by default. This prevents external network access.

To allow network access (e.g., for mobile dashboard):

Edit `arise.ps1`:
```powershell
$backendCmd = "& '$pythonExe' -m uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT"
```

**Warning**: Only do this on trusted networks.

## Advanced Usage

### Running Individual Services

If you only want to start one service:

**Mosquitto Only:**
```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -c mosquitto.conf -v
```

**Backend Only:**
```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Dashboard Only:**
```powershell
.\.venv\Scripts\python.exe -m http.server 3000 --directory dashboard --bind 127.0.0.1
```

### Testing with Simulator

After starting services with `arise`, generate test data:

```powershell
# In a new terminal
.\.venv\Scripts\python.exe tools\simulator.py --runs 50 --players 3
```

Watch the dashboard update in real-time.

### Database Management

**Location**: `backend/aquabuzz.db`

**View data**:
```powershell
# Using Python
.\.venv\Scripts\python.exe
>>> import sqlite3
>>> conn = sqlite3.connect('backend/aquabuzz.db')
>>> cursor = conn.cursor()
>>> cursor.execute("SELECT * FROM players")
>>> cursor.fetchall()
```

**Reset database**:
```powershell
Remove-Item backend\aquabuzz.db
arise  # Database recreates automatically
```

## Uninstallation

To remove the `arise` command:

1. Open your PowerShell profile:
```powershell
notepad $PROFILE
```

2. Find and delete the section between:
```powershell
# ============================================================================
# WIREBUZZ ARISE COMMAND
```
and
```powershell
# ============================================================================
```

3. Save and reload:
```powershell
. $PROFILE
```

## Comparison with Docker

This system replaces Docker Compose for local development on Windows:

| Feature | `arise` | Docker Compose |
|---------|---------|----------------|
| Setup | Native Windows | Requires Docker Desktop |
| Logs | Separate visible windows | `docker compose logs` |
| Restart | Close windows & rerun | `docker compose restart` |
| Resource usage | Lower (native) | Higher (containers) |
| Edit & reload | Instant | Rebuild containers |
| Debugging | Easier (native Python) | Container isolation |

Both are valid approaches. Use `arise` for rapid local development.

## Status Indicators

The startup report uses these indicators:

- `[✓]` **Green**: Service healthy and verified
- `[✗]` **Red**: Service failed to start
- `[!]` **Yellow**: Service started but with warnings
- `[→]` **Cyan**: Action in progress
- `[i]` **Gray**: Informational message

## Support

For issues or improvements:

1. Check the service terminal windows for error logs
2. Run with `-Verbose` flag for detailed diagnostics
3. Consult `docs/troubleshooting.md` for common issues
4. Verify prerequisites with the validation output

## Version History

- **1.0.0** (2024-11-24): Initial release
  - Mosquitto auto-start with health checks
  - FastAPI backend with MQTT verification
  - Dashboard HTTP server
  - Automatic browser launching
  - Idempotent service reuse
  - PowerShell profile integration

---

**Project**: WireBuzz Intelligent IoT System  
**Documentation**: arise-command.md  
**Last Updated**: 2024-11-24
