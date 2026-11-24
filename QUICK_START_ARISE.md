# WireBuzz `arise` - Quick Installation & Usage

## 🚀 Installation (3 Steps)

### Step 1: Run the Installer

```powershell
.\scripts\install-arise-command.ps1
```

**What it does**:
- Adds `arise` function to your PowerShell profile
- Preserves existing profile content
- Makes the command available in all future PowerShell sessions

**Expected output**:
```
============================================
  WIREBUZZ ARISE COMMAND INSTALLER
============================================

[OK] Found arise.ps1
    Location: C:\Users\Alord\...\scripts\arise.ps1

PowerShell Profile: C:\Users\Alord\Documents\WindowsPowerShell\profile.ps1

[i] Profile exists
[OK] arise function added

To use in THIS terminal: . $PROFILE
To use in NEW terminals: Just open a new PowerShell
```

### Step 2: Reload Your Profile (Current Terminal Only)

```powershell
. $PROFILE
```

**Note**: New PowerShell windows will automatically have `arise` available.

### Step 3: Verify Installation

```powershell
Get-Command arise
```

**Expected output**:
```
CommandType     Name                                               Version    Source
-----------     ----                                               -------    ------
Function        arise
```

---

## 🎮 Usage

### Start All WireBuzz Services

```powershell
arise
```

**What happens**:
1. ✅ Validates your environment
2. ✅ Starts Mosquitto MQTT Broker (port 1883)
3. ✅ Starts FastAPI Backend (port 8000)
4. ✅ Starts Dashboard Server (port 3000)
5. ✅ Verifies all services are healthy
6. ✅ Opens browser tabs automatically

**Expected result**:
- Three new PowerShell windows appear:
  - **WIREBUZZ - MQTT BROKER** (Mosquitto logs)
  - **WIREBUZZ - FASTAPI BACKEND** (FastAPI logs)
  - **WIREBUZZ - DASHBOARD** (HTTP server logs)
- Three browser tabs open:
  - Dashboard: http://localhost:3000
  - API Docs: http://localhost:8000/docs
  - Health: http://localhost:8000/api/health

### Options

```powershell
# Skip browser opening
arise -SkipBrowser

# Show detailed logs
arise -Verbose

# Both
arise -SkipBrowser -Verbose
```

---

## 🧪 Testing

### Test 1: First Run

```powershell
arise
```

**Expected**: All services start, browser opens.

### Test 2: Idempotency (Run Again)

```powershell
arise
```

**Expected**: 
```
[OK] Mosquitto already running on port 1883 (PID: 12345)
[OK] Backend already running on port 8000
[OK] Dashboard already running on port 3000
```

No duplicate processes created!

### Test 3: Generate Sample Data

```powershell
.\.venv\Scripts\python.exe tools\simulator.py --runs 20 --players 2
```

**Expected**: Dashboard updates with simulated gameplay data.

---

## 🛑 Stopping Services

### Close All Services

Close the three service PowerShell windows.

### Stop Individual Services

```powershell
# Stop Mosquitto
Get-Process mosquitto | Stop-Process

# Stop Backend
$pid = (Get-NetTCPConnection -LocalPort 8000).OwningProcess
Stop-Process -Id $pid

# Stop Dashboard
$pid = (Get-NetTCPConnection -LocalPort 3000).OwningProcess
Stop-Process -Id $pid
```

---

## 🔧 Troubleshooting

### "arise : The term 'arise' is not recognized"

**Solution**: Reload profile
```powershell
. $PROFILE
```

### "Could not find WireBuzz project root"

**Solution**: Navigate to project directory
```powershell
cd "C:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS"
```

### "Python virtual environment not found"

**Solution**: Create and install dependencies
```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r backend\requirements.txt
```

### "Mosquitto not found"

**Solution**: Install Mosquitto from https://mosquitto.org/download/

Or edit `scripts/arise.ps1` line 8 if installed elsewhere:
```powershell
$MOSQUITTO_EXE = "C:\Your\Path\mosquitto.exe"
```

### Port Already in Use

**Find what's using it**:
```powershell
Get-NetTCPConnection -LocalPort 1883 -State Listen  # MQTT
Get-NetTCPConnection -LocalPort 8000 -State Listen  # Backend
Get-NetTCPConnection -LocalPort 3000 -State Listen  # Dashboard
```

**Stop the process**:
```powershell
Stop-Process -Id <PID>
```

---

## 📚 Documentation

- **Quick Reference**: `scripts/README.md`
- **Comprehensive Guide**: `docs/arise-command.md`
- **Implementation Report**: `ARISE_IMPLEMENTATION_REPORT.md`
- **WireBuzz Docs**: `docs/troubleshooting.md`

---

## ✅ Your Workflow Now

### Before:
```powershell
# Terminal 1
cd backend
..\.venv\Scripts\activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2  
& "C:\Program Files\mosquitto\mosquitto.exe" -c mosquitto.conf -v

# Terminal 3
.\.venv\Scripts\python.exe -m http.server 3000 --directory dashboard

# Then manually open browser tabs...
```

**Time**: 3-5 minutes, error-prone

### After:
```powershell
arise
```

**Time**: 10-20 seconds, automated

---

## 🎉 You're Done!

Your WireBuzz system is now a single-command startup away.

**Happy testing!** 🚀
