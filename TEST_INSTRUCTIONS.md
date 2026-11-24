# AquaBuzz Physical Testing - Step-by-Step Guide

## Overview
This guide walks you through testing the complete AquaBuzz system ONE STEP AT A TIME.
After each step, verify the result before moving to the next.

---

## Step 1: Start the System

**Action:**
```powershell
.\scripts\rise.ps1
```

**What to expect:**
- Three service windows open (Backend, Gateway, Dashboard)
- Browser opens automatically showing the dashboard
- Console shows green "Startup Complete" message

**Success criteria:**
- Backend API shows "healthy" status
- Gateway shows "auto-detecting ESP32"
- Dashboard displays "Waiting for data..."

**If something fails:**
- Check error message in console
- Run `.\scripts\rise-stop.ps1` and try again
- Verify ports 8000 and 3000 are not in use

---

## Step 2: Connect the ESP32

**Action:**
- Plug ESP32 into your laptop via USB cable
- Watch the Serial Gateway window

**What to expect:**
- Gateway window shows "Connected to ESP32 on COM3" (or similar)
- Messages like "Device connected and ready"

**Success criteria:**
- Gateway stops showing "searching for ports"
- No repeated connection errors

**If ESP32 not detected:**
- Unplug ESP32, wait 3 seconds, plug back in
- Check Device Manager for COM port (should show "USB-SERIAL CH340")
- Verify firmware is uploaded to ESP32

---

## Step 3: Verify Initial Connection

**Action:**
Open another PowerShell window and run:
```powershell
Invoke-WebRequest http://localhost:8000/api/health | ConvertFrom-Json
```

**What to expect:**
```json
{
  "status": "healthy",
  "mqtt_connected": true,
  "database": "connected"
}
```

**Success criteria:**
- `mqtt_connected` is `true`
- Status is "healthy"

**If MQTT not connected:**
- Wait 10 more seconds and try again (MQTT can be slow)
- Check internet connection
- Gateway will auto-reconnect

---

## Step 4: Touch the Maze (First Contact)

**Action:**
- With the ESP32 powered and connected
- Touch the wire/probe to the metal maze track
- Watch BOTH the Serial Gateway window AND the dashboard

**What to expect in Gateway window:**
```
{"event":"run_start","run_uid":"abc123...","timestamp":12345}
{"event":"hit_start","run_uid":"abc123...","hit_no":1,"start_ms":100}
```

**What to expect in Dashboard:**
- Run counter increases
- Status shows "In Progress"
- Hit counter starts at 0

**Success criteria:**
- Gateway publishes JSON events
- Dashboard updates in real-time
- No "connection lost" errors

**If nothing happens:**
- Check ESP32 power LED (should be on)
- Check Serial Gateway shows active connection
- Try unplugging/replugging ESP32

---

## Step 5: Complete One Full Game

**Action:**
- Navigate the wire through the entire maze WITHOUT touching
- Or make 1-2 deliberate touches, then finish
- Finish the maze completely

**What to expect as you play:**
- Each touch triggers a buzzer beep
- Gateway shows `hit_start` and `hit_end` events
- Dashboard updates hits in real-time

**What to expect when you finish:**
- Final `run_finish` event in Gateway window
- Dashboard shows completed run with:
  - Final time
  - Total hits count
  - Total contact time
  - Score calculated

**Success criteria:**
- Dashboard "Individual Hits" section shows each hit with duration
- Aggregate stats (Total Hits, Total Contact) match the individual hits
- If you had 2 hits of 50ms each, Total Contact should show ~100ms

**CRITICAL CHECK:**
If Individual Hits shows "Hit #1: 289ms" but Total Hits = 0, THE BUG STILL EXISTS.
This should be IMPOSSIBLE with the fix.

---

## Step 6: Verify Data Consistency

**Action:**
In a PowerShell window, check the database:
```powershell
cd backend
..\.venv\Scripts\python.exe -c "from app.db import SessionLocal; from app.models import Run, Hit; db = SessionLocal(); run = db.query(Run).order_by(Run.id.desc()).first(); hits = db.query(Hit).filter(Hit.run_uid == run.run_uid).all(); print(f'Run hits: {run.hits}'); print(f'Hit records: {len(hits)}'); print(f'Run total_contact_ms: {run.total_contact_ms}'); print(f'Sum of hit durations: {sum(h.duration_ms for h in hits)}'); db.close()"
```

**What to expect:**
```
Run hits: 2
Hit records: 2
Run total_contact_ms: 150
Sum of hit durations: 150
```

**Success criteria:**
- `Run hits` equals `Hit records` count
- `Run total_contact_ms` equals sum of individual hit durations
- Numbers match what dashboard displayed

**If numbers don't match:**
- THE FIX DID NOT WORK
- Check backend/app/main.py line ~160 (hit aggregation code)
- Backend may need restart

---

## Step 7: Test Multiple Runs

**Action:**
- Play the game 2-3 more times
- Vary the number of hits (0 hits, 2 hits, 5 hits)
- Check dashboard after each run

**What to expect:**
- Run history shows all completed runs
- Each run has correct individual and aggregate data
- Dashboard doesn't show stale data from previous runs

**Success criteria:**
- Dashboard updates for each new run
- History table shows increasing run IDs
- No runs with "Total Hits: 0" when individual hits exist

---

## Step 8: Stop the System

**Action:**
```powershell
.\scripts\rise-stop.ps1
```

**What to expect:**
- All three service windows close
- Console shows "Stopped: 3 service(s)"
- Process tracker file removed

**Success criteria:**
- No error messages
- All PowerShell windows close cleanly

---

## Quick Reference Commands

### Check system health
```powershell
Invoke-WebRequest http://localhost:8000/api/health | ConvertFrom-Json
```

### View latest run from database
```powershell
cd backend
..\.venv\Scripts\python.exe -c "from app.db import SessionLocal; from app.models import Run; db = SessionLocal(); run = db.query(Run).order_by(Run.id.desc()).first(); print(f'Run UID: {run.run_uid}'); print(f'Hits: {run.hits}'); print(f'Contact: {run.total_contact_ms}ms'); print(f'Score: {run.score}'); db.close()"
```

### View individual hits for latest run
```powershell
cd backend
..\.venv\Scripts\python.exe -c "from app.db import SessionLocal; from app.models import Run, Hit; db = SessionLocal(); run = db.query(Run).order_by(Run.id.desc()).first(); hits = db.query(Hit).filter(Hit.run_uid == run.run_uid).all(); [print(f'Hit #{h.hit_no}: {h.duration_ms}ms') for h in hits]; db.close()"
```

### Restart just the backend (if you modify code)
```powershell
# Stop everything
.\scripts\rise-stop.ps1

# Start again
.\scripts\rise.ps1
```

---

## Common Issues and Solutions

### "Gateway can't find ESP32"
**Solution:** 
- Check Device Manager for COM port
- Unplug/replug ESP32
- Verify correct firmware uploaded

### "Dashboard shows 0 hits but I saw individual hits"
**Solution:**
- THIS IS THE BUG WE FIXED
- Verify you're running the latest backend code
- Check backend/app/main.py has the hit aggregation fix
- Restart backend

### "MQTT not connected"
**Solution:**
- Wait 10-15 seconds (public MQTT can be slow)
- Check internet connection
- Gateway will auto-reconnect

### "Port 8000 already in use"
**Solution:**
```powershell
# Find what's using it
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
# Stop AquaBuzz services
.\scripts\rise-stop.ps1
```

### "Dashboard not updating"
**Solution:**
- Hard refresh browser (Ctrl+F5)
- Check browser console for errors (F12)
- Verify backend health endpoint responds

---

## Success Indicators

✅ **System is working correctly when:**
1. ESP32 connects automatically to Gateway
2. Each physical touch triggers hit events
3. Dashboard updates in real-time during gameplay
4. Individual hits list matches aggregate statistics
5. Total Hits count equals number of hit records displayed
6. Total Contact Time equals sum of individual hit durations
7. Score calculation makes sense (Duration + Penalty × Hits)

❌ **System has problems when:**
1. Gateway keeps searching for ESP32 after plugin
2. No events appear when touching maze
3. Dashboard shows "Total Hits: 0" with individual hits listed
4. Individual hit durations don't sum to total contact time
5. Browser shows "connection failed" errors
6. Backend health check fails

---

## What Each Component Does

**Backend (Port 8000):**
- Receives events from MQTT
- Stores data in SQLite database
- Calculates aggregate statistics from Hit table
- Serves API for dashboard

**Serial Gateway:**
- Reads JSON from ESP32 via USB
- Adds run_uid to events
- Publishes to MQTT broker
- Auto-reconnects if connection lost

**Dashboard (Port 3000+):**
- Displays real-time game data
- Shows run history
- Visualizes individual hits
- Fetches data from Backend API

**ESP32 Firmware:**
- Detects wire-to-maze touches
- Sounds buzzer on contact
- Sends JSON events via USB serial
- No WiFi configuration needed

---

## Next Steps After Testing

If all tests pass:
1. System is fully functional
2. Hit aggregation bug is confirmed fixed
3. Ready for demonstration or deployment

If tests fail at a specific step:
1. Note which step failed
2. Copy the error message
3. Check the "Common Issues" section above
4. Report specific failure with error details

---

**Last Updated:** November 24, 2026  
**Testing Time:** ~10 minutes for complete verification
