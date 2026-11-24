# WireBuzz Quick Start - `rise` Command

## 🚀 First-Time Installation (One Time Only)

```powershell
# 1. Navigate to your WireBuzz project
cd "c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS"

# 2. Run the installer
.\scripts\install-rise-command.ps1

# 3. Reload your PowerShell profile
. $PROFILE
```

**Done!** You're ready to use `rise`.

---

## 📅 Daily Usage

### Start Everything
```powershell
rise
```

That's it! The command will:
- ✅ Start Mosquitto MQTT broker
- ✅ Start FastAPI backend
- ✅ Start Dashboard server
- ✅ Open browser with dashboard and API docs

### Stop Everything
```powershell
rise-stop
```

---

## 🔍 What You'll See

After running `rise`, you'll see:

1. **Three terminal windows open:**
   - Mosquitto MQTT Broker (port 1883)
   - FastAPI Backend (port 8000)  
   - Dashboard Server (port 3000-3002 or 8080-8081)

2. **Three browser tabs open:**
   - Dashboard: `http://127.0.0.1:<PORT>`
   - API Docs: `http://127.0.0.1:8000/docs`
   - Health Check: `http://127.0.0.1:8000/api/health`

3. **Status report in your terminal:**
```
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
```

---

## ⚠️ Important Notes

1. **Your `arise` command is safe** - The installer preserves your existing `arise` command for the other project.

2. **Services are reused** - Running `rise` twice won't create duplicates. It detects and reuses healthy services.

3. **Dynamic ports** - If port 3000 is busy, the dashboard automatically uses 3001, 3002, 8080, or 8081.

4. **Process tracking** - `rise-stop` only stops services started by `rise`, never unrelated processes.

---

## 🐛 Quick Troubleshooting

### "rise : The term 'rise' is not recognized"
```powershell
# Reload your profile
. $PROFILE
```

### "Port 8000 already in use"
```powershell
# Stop existing WireBuzz services
rise-stop

# Or manually check what's using it
Get-NetTCPConnection -LocalPort 8000 -State Listen
```

### "MQTT broker failed to start"
```powershell
# Check if Mosquitto is installed
Test-Path "C:\Program Files\mosquitto\mosquitto.exe"
```

---

## 📚 More Information

For detailed documentation, see: `RISE_COMMAND_GUIDE.md`

---

**You're all set! Just type `rise` and start testing.** 🎮
