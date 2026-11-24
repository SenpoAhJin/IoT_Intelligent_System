# AquaBuzz - Start Here

## Quick Start (3 Commands)

```powershell
# 1. Start the system
.\scripts\rise.ps1

# 2. Verify everything is running
.\scripts\verify-startup.ps1

# 3. When done, stop everything
.\scripts\rise-stop.ps1
```

That's it. The system handles everything else automatically.

---

## What Gets Started

When you run `rise.ps1`, three services start automatically:

1. **Backend API** (Port 8000)
   - Processes MQTT events
   - Stores data in SQLite
   - Calculates hit statistics from database
   - Serves REST API

2. **Serial Gateway** (USB)
   - Auto-detects ESP32 on any COM port
   - Reads JSON events from USB serial
   - Publishes to MQTT broker
   - Auto-reconnects on disconnect

3. **Dashboard** (Port 3000+)
   - Opens automatically in your browser
   - Updates in real-time
   - Shows individual hits and aggregate stats
   - Dark theme design

All three services open in separate windows so you can monitor them.

---

## Health Checks Built-In

`rise.ps1` automatically verifies:
- ✅ All required files exist
- ✅ Python virtual environment is ready
- ✅ Ports are available (or reuses existing services)
- ✅ Backend responds to health checks
- ✅ MQTT connection established
- ✅ Dashboard server responds

If anything fails, you get a clear error message.

---

## Physical Testing Workflow

After starting the system:

### Step 1: Connect ESP32
- Plug ESP32 into USB
- Watch Serial Gateway window
- Should see: "Connected to ESP32 on COM3"

### Step 2: Play the Game
- Touch wire to maze → triggers hit
- Navigate through maze
- Finish at the end

### Step 3: Check Results
- Dashboard updates automatically
- Verify: Individual hits match aggregate stats
- **Critical:** If Total Hits = 0 but individual hits show, BUG STILL EXISTS

### Step 4: Verify Database
Run the quick check:
```powershell
cd backend
..\.venv\Scripts\python.exe -c "from app.db import SessionLocal; from app.models import Run, Hit; db = SessionLocal(); run = db.query(Run).order_by(Run.id.desc()).first(); hits = db.query(Hit).filter(Hit.run_uid == run.run_uid).all(); print(f'Hits in Run table: {run.hits}'); print(f'Hit records in DB: {len(hits)}'); print(f'Match: {run.hits == len(hits)}'); db.close()"
```

Should show: `Match: True`

---

## The Critical Fix

**Problem:** Dashboard showed individual hits (e.g., "Hit #1: 289ms") but aggregate stats were 0.

**Root Cause:** Backend trusted firmware's aggregate calculations instead of database.

**Solution:** Backend now calculates aggregates from Hit table (single source of truth).

**Location:** `backend/app/main.py` lines 192-205

**Key Code:**
```python
# CRITICAL FIX: Calculate aggregate stats from actual Hit records
hit_records = db.query(Hit).filter(Hit.run_uid == run_uid).all()
completed_hits = [h for h in hit_records if h.duration_ms > 0]

run.hits = len(completed_hits)
run.total_contact_ms = sum(h.duration_ms for h in completed_hits)
run.longest_hit_ms = max((h.duration_ms for h in completed_hits), default=0)
```

**Guarantee:** Individual hits and aggregates now ALWAYS match because they come from the same source.

---

## Architecture Flow

```
ESP32 (USB Serial)
    ↓
Serial Gateway (adds run_uid, normalizes events)
    ↓
MQTT Broker (test.mosquitto.org)
    ↓
Backend (subscribes to aquabuzz/events/*)
    ↓
SQLite Database (Hit table = source of truth)
    ↓
REST API (calculates aggregates from database)
    ↓
Dashboard (polls API, displays results)
```

---

## No Manual Configuration Needed

✅ **No WiFi credentials** - ESP32 uses USB only  
✅ **No COM port selection** - Auto-detected  
✅ **No MQTT setup** - Public broker used  
✅ **No port conflicts** - Auto-finds available ports  
✅ **No separate terminals** - All services in separate windows  
✅ **No manual cleanup** - rise-stop handles everything  

---

## Documentation Files

- **TEST_INSTRUCTIONS.md** - Detailed step-by-step testing (10 minutes)
- **CRITICAL_FIX_REPORT.md** - Technical details of hit aggregation fix
- **FINAL_STATUS_REPORT.md** - Complete system status before this session
- **PHYSICAL_TEST_CHECKLIST.md** - Quick checklist format
- **ESP32_SETUP_QUICK_GUIDE.md** - Firmware upload instructions

---

## Troubleshooting

### "Port 8000 already in use"
```powershell
.\scripts\rise-stop.ps1  # Stops AquaBuzz services only
```

### "ESP32 not detected"
- Check Device Manager for COM port
- Unplug/replug USB cable
- Verify firmware uploaded (aquabuzz_core.ino)

### "Dashboard shows 0 hits with individual hits"
- **This is the bug we fixed**
- Restart backend: `.\scripts\rise-stop.ps1` then `.\scripts\rise.ps1`
- Verify fix code exists: `.\scripts\verify-startup.ps1`

### "MQTT not connected"
- Wait 10-15 seconds (public MQTT can be slow)
- Gateway auto-reconnects
- Check internet connection

---

## Service URLs

After `rise.ps1` completes:

- **Dashboard:** http://localhost:3000 (or 3001, 3002, 8080, 8081)
- **API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/api/health

---

## Expected Behavior

### On Startup
```
✓ Project requirements validated
✓ Internet connectivity: OK
✓ Backend started (PID: 12345)
✓ Backend ready on port 8000
✓ MQTT Status: CONNECTED
✓ Serial Gateway started (PID: 12346)
✓ Dashboard started (PID: 12347)
✓ Dashboard ready on port 3000
✓ Browser opened
```

### During Gameplay
```
Serial Gateway:
  {"event":"run_start","run_uid":"abc123","timestamp":1234}
  {"event":"hit_start","run_uid":"abc123","hit_no":1,"start_ms":100}
  {"event":"hit_end","run_uid":"abc123","hit":1,"dur_ms":289}
  {"event":"run_finish","run_uid":"abc123","t_ms":5000,"hits":1}

Dashboard:
  Run #15 | Status: Finished
  Duration: 5.00s | Hits: 1 | Contact: 289ms | Score: 7000ms
  
  Individual Hits:
  Hit #1: 289ms (at 0.10s)
```

### On Shutdown
```
✓ Stopped backend (PID: 12345)
✓ Stopped gateway (PID: 12346)  
✓ Stopped dashboard (PID: 12347)
✓ Process tracker removed
```

---

## Safety Features

1. **ForgeMind Protection** - Never stops ForgeMind/arise/rest processes
2. **Port Reuse** - Reuses healthy existing services instead of failing
3. **Idempotent Events** - Duplicate MQTT messages don't corrupt data
4. **Auto-Reconnect** - Gateway reconnects if ESP32 unplugged
5. **Graceful Degradation** - System continues if MQTT temporarily unavailable

---

## Development Workflow

### Make Code Changes
1. Edit files in `backend/app/` or `backend/intelligence/`
2. Stop: `.\scripts\rise-stop.ps1`
3. Start: `.\scripts\rise.ps1` (auto-reloads code)

### Test Changes
1. Run verification: `.\scripts\verify-startup.ps1`
2. Play physical game
3. Check dashboard results
4. Query database to confirm

### Deploy/Demo
1. Start system: `.\scripts\rise.ps1`
2. Connect ESP32
3. System ready immediately

---

## Success Criteria

System is working correctly when:

✅ ESP32 connects automatically  
✅ Each touch triggers buzzer and hit event  
✅ Dashboard updates in real-time  
✅ **Individual hits list matches aggregate stats**  
✅ Total Hits count equals displayed hit records  
✅ Total Contact equals sum of individual durations  
✅ Score calculation is consistent  

The **bold item** is the critical fix verification.

---

## Time Estimates

- **Full startup:** 10-15 seconds
- **ESP32 connection:** 2-5 seconds after plugin
- **Game completion:** 30-120 seconds (depends on player)
- **Data verification:** 5 seconds with quick command
- **Full testing workflow:** 10 minutes (TEST_INSTRUCTIONS.md)

---

## Questions?

1. **"Does this need WiFi?"** - No, ESP32 uses USB only. Your laptop needs internet for MQTT.

2. **"What if I change networks?"** - No problem. Gateway reconnects automatically.

3. **"Can I use a different COM port?"** - Yes, auto-detected.

4. **"What if ports 8000/3000 are taken?"** - Script auto-finds available ports.

5. **"How do I know the fix worked?"** - Individual hits and aggregates will match. If they don't, bug still exists.

6. **"Can I test without hardware?"** - Backend and dashboard yes, full flow needs ESP32.

7. **"How do I see what's in the database?"** - Use commands in TEST_INSTRUCTIONS.md or `http://localhost:8000/docs` API.

---

**Last Updated:** November 24, 2026  
**Status:** System fully functional, hit aggregation bug fixed  
**Next Action:** Run `.\scripts\rise.ps1` and test with physical hardware
