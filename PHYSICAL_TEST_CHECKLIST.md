# AQUABUZZ PHYSICAL HARDWARE TEST CHECKLIST

**Purpose:** Verify the complete system works with physical ESP32 hardware  
**Date:** November 25, 2026  
**Prerequisites:** Software fixes applied and tested  

---

## PRE-TEST SETUP

### ☐ 1. Hardware Connections

**ESP32 Connections:**
- [ ] Maze wire → GPIO 27 (PIN_MAZE)
- [ ] Finish pad → GPIO 33 (PIN_FINISH)
- [ ] Buzzer → GPIO 26 (PIN_BUZZER)
- [ ] Ground connections verified
- [ ] USB cable connected to computer (data-capable cable)
- [ ] ESP32 powered on (LED indicator)

**Expected:** ESP32 should be recognized as CH340 USB-Serial device on COM3

### ☐ 2. Firmware Upload

```
1. Open Arduino IDE
2. File → Open → firmware/aquabuzz_connected/aquabuzz_connected.ino
3. Tools → Board → ESP32 Dev Module
4. Tools → Port → COM3 (USB-SERIAL CH340)
5. Upload
```

**Expected:** "Done uploading" message, no errors

### ☐ 3. Start System

```powershell
cd "C:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS"
.\scripts\rise.ps1
```

**Expected Output:**
```
Launching FastAPI with uvicorn...
  Backend started (PID: XXXXX)
  Backend ready on port 8000
  MQTT Status: CONNECTED to test.mosquitto.org

Launching serial gateway...
  Serial Gateway started (PID: XXXXX)
  Gateway will auto-detect ESP32 COM port

Launching dashboard on port XXXX...
  Dashboard started (PID: XXXXX)
  Dashboard ready on port XXXX
```

**Browser should open automatically to dashboard**

---

## PHASE 1: CONNECTION VERIFICATION

### ☐ 4. Check Serial Gateway Connection

**In Serial Gateway Terminal Window:**
Look for:
```
[Serial] Found potential ESP32 on COM3
[Serial] Connected to ESP32 on COM3
[Gateway] Session ID: XXXXXXXX
```

**If NOT found:**
- Check USB cable (must be data cable, not charge-only)
- Check Device Manager: Ports (COM & LPT) should show "USB-SERIAL CH340 (COM3)"
- Try different USB port
- Restart serial gateway

### ☐ 5. Check Backend MQTT Connection

**In Backend Terminal Window:**
Look for:
```
[API] Database initialized
[API] MQTT client started
[MQTT] Connected to test.mosquitto.org:1883
[MQTT] Subscribed to aquabuzz/+/events and heartbeats
```

**If NOT connected:**
- Check internet connection
- Check firewall settings
- Wait 10 seconds for retry

### ☐ 6. Check Dashboard

**Open:** http://localhost:3000 (or auto-opened browser)

**Verify Display Shows:**
- [ ] "Backend API: Online"
- [ ] "MQTT Broker: Connected"
- [ ] "Device aquabuzz-001: Online" or "Waiting..."
- [ ] "Games Playing: 0"

**If backend shows offline:**
- Try http://localhost:8000/api/health in another browser tab
- Check if backend process is running

---

## PHASE 2: SENSOR TESTING

### ☐ 7. Test Buzzer Response

**Action:** Touch maze wire with hand  
**Expected:** Buzzer sounds immediately

**Verify:**
- [ ] Buzzer activates when touching maze wire
- [ ] Buzzer stops when releasing maze wire
- [ ] Buzzer response is immediate (< 100ms perceived delay)

**If buzzer doesn't work:**
- Check buzzer wiring (GPIO 26, GND)
- Check buzzer polarity
- Send 'b' command via Serial Monitor to test buzzer directly

### ☐ 8. Test Finish Detection

**Action:** Touch finish pad

**Expected in Serial Monitor (115200 baud):**
```json
{"info":"aquabuzz_connected_v1","boot":1,"device":"aquabuzz-001"}
```

**If no serial output:**
- Check Serial Monitor baud rate (115200)
- Check USB connection
- Press ESP32 reset button
- Check for boot messages

---

## PHASE 3: GAMEPLAY TEST - PERFECT RUN

### ☐ 9. Play Perfect Run (Zero Hits)

**Instructions:**
1. Do NOT touch maze wire
2. Touch finish pad

**Check Serial Monitor:**
```json
{"run":1,"event":"run_start","t_ms":0}
{"run":1,"event":"run_finish","t_ms":XXXX,"hits":0,"total_contact_ms":0,"longest_hit_ms":0,"hit_penalty_ms":2000,"score":XXXX}
```

**Check Backend Log:**
```
[MQTT] Created run: aquabuzz-001-...
[MQTT] Run finished: aquabuzz-001-...
  Duration: XXXXms
  Hits (from DB): 0 (firmware sent: 0)
  Total Contact (from DB): 0ms (firmware sent: 0ms)
  Score (recalculated): XXXXms (firmware sent: XXXXms)
```

**Check Dashboard (refresh or wait 3 seconds):**
- [ ] Recent Activity shows new run
- [ ] Total Hits: 0
- [ ] Total Contact Time: 0.00s
- [ ] Score equals duration
- [ ] Individual Hits: Empty or "Perfect run - no hits!"

**✅ PASS if:** All zeros match, dashboard updates

---

## PHASE 4: GAMEPLAY TEST - SINGLE HIT

### ☐ 10. Play Single Hit Run

**Instructions:**
1. Touch maze wire briefly (< 1 second)
2. Release maze wire
3. Touch finish pad

**Check Serial Monitor:**
```json
{"run":2,"event":"run_start","t_ms":0}
{"run":2,"event":"hit_start","hit":1,"t_ms":XXXX}
{"run":2,"event":"hit_end","hit":1,"t_ms":YYYY,"dur_ms":ZZZ}
{"run":2,"event":"run_finish","t_ms":TTTT,"hits":1,"total_contact_ms":ZZZ,"longest_hit_ms":ZZZ,...}
```

**Record These Values:**
- Duration of contact: _____ ms (from dur_ms)
- Total run time: _____ ms (from t_ms in run_finish)

**Check Backend Log:**
```
[MQTT] Hit 1 started for run aquabuzz-001-...
[MQTT] Hit 1 completed: ZZZms
[MQTT] Run finished: aquabuzz-001-...
  Hits (from DB): 1 (firmware sent: 1)
  Total Contact (from DB): ZZZms (firmware sent: ZZZms)
```

**CRITICAL VERIFICATION:**

Compare these three sources - THEY MUST ALL MATCH:
1. ESP32 Serial: `dur_ms=ZZZ`
2. Backend Log: `Total Contact (from DB): ZZZms`
3. Dashboard: `Total Contact Time: Z.ZZs`

**Check Dashboard:**
- [ ] Total Hits: 1
- [ ] Total Contact Time: matches ZZZ ms from serial
- [ ] Individual Hits shows Hit #1 with duration = ZZZ ms
- [ ] Score = Duration + (1 × 2000ms penalty)

**✅ PASS if:** 
- Dashboard aggregate stats match individual hit duration
- Backend log shows firmware and DB values match

**❌ FAIL if:**
- Dashboard shows "Total Hits: 0" but Individual Hits shows Hit #1
- Backend log shows mismatch between firmware and DB values

---

## PHASE 5: GAMEPLAY TEST - MULTIPLE HITS

### ☐ 11. Play Multiple Hits Run

**Instructions:**
1. Touch maze wire → release (hit 1)
2. Touch maze wire → release (hit 2)
3. Touch maze wire → release (hit 3)
4. Touch finish pad

**Check Serial Monitor:**
Should show 3 hit_start and 3 hit_end events

**Record Hit Durations:**
- Hit 1: _____ ms
- Hit 2: _____ ms
- Hit 3: _____ ms
- Total (manual sum): _____ ms

**Check Backend Log:**
```
[MQTT] Hit 1 completed: Xms
[MQTT] Hit 2 completed: Yms
[MQTT] Hit 3 completed: Zms
[MQTT] Run finished:
  Hits (from DB): 3
  Total Contact (from DB): (X+Y+Z)ms
  Longest Hit (from DB): max(X,Y,Z)ms
```

**Check Dashboard:**
- [ ] Total Hits: 3
- [ ] Total Contact Time: sum of all hit durations
- [ ] Longest Hit: duration of longest individual hit
- [ ] Individual Hits section shows all 3 hits
- [ ] Manual sum of displayed durations = Total Contact Time

**✅ PASS if:** Aggregate stats equal sum of individual hits

---

## PHASE 6: EDGE CASE TESTING

### ☐ 12. Finish While Touching (Active Hit)

**Instructions:**
1. Touch maze wire
2. While STILL touching, reach finish pad with other hand
3. Touch finish

**Expected:** Firmware should send hit_end before run_finish

**Check Serial Monitor:**
```json
{"run":X,"event":"hit_start","hit":1,"t_ms":AAA}
{"run":X,"event":"hit_end","hit":1,"t_ms":BBB,"dur_ms":CCC}
{"run":X,"event":"run_finish",...}
```

**Verify:**
- [ ] hit_end event appears BEFORE run_finish
- [ ] Duration is calculated correctly
- [ ] Dashboard shows the final hit

**✅ PASS if:** Final hit is counted and included in aggregates

### ☐ 13. Sequential Games

**Instructions:**
1. Complete game 1
2. Wait 5 seconds
3. Immediately start game 2

**Verify:**
- [ ] Games Playing counter updates correctly
- [ ] Two separate runs in Recent Activity
- [ ] Different run UIDs
- [ ] Player statistics update

**✅ PASS if:** System handles multiple sequential games

---

## PHASE 7: DATA VERIFICATION

### ☐ 14. API Endpoint Verification

**Open in browser:**

```
http://localhost:8000/api/health
```
**Verify:**
- `completed_runs` count increased
- `active_runs` = 0 after game finishes

```
http://localhost:8000/api/runs?limit=5
```
**Verify:** Shows last 5 games with correct data

```
http://localhost:8000/api/runs/{id}
```
(Replace {id} with actual run ID from previous call)

**Verify:**
- `hits` field matches number of hit_records
- `total_contact_ms` equals sum of `hit_records[].duration_ms`
- `longest_hit_ms` equals max of `hit_records[].duration_ms`

**✅ PASS if:** API data is internally consistent

---

## PHASE 8: DASHBOARD VALIDATION

### ☐ 15. Complete Dashboard Check

After playing several games, verify:

**System Health Card:**
- [ ] ESP32 device shows "Online"
- [ ] MQTT shows "Connected"
- [ ] Active runs count is correct (0 after games finish)
- [ ] Completed runs count increased

**Live Game Card:**
- [ ] Appears when game is running
- [ ] Shows correct player count
- [ ] Disappears when game finishes

**Top Scores (Leaderboard):**
- [ ] Shows completed runs
- [ ] Sorted by score (ascending)
- [ ] Displays player names
- [ ] Shows hit counts

**Recent Activity:**
- [ ] Lists recent games
- [ ] Status badges correct (Finished/In Progress)
- [ ] Durations displayed
- [ ] Hit counts displayed

**Latest Run Details:**
- [ ] Shows most recent completed run
- [ ] All aggregate stats displayed
- [ ] Individual Hits section populated
- [ ] Aggregate stats match sum of individual hits ⭐ CRITICAL

**Players & Performance:**
- [ ] Lists all players
- [ ] Shows run counts
- [ ] Best/average scores calculated
- [ ] Skill level badges appear

---

## PASS/FAIL CRITERIA

### ✅ SYSTEM PASSES IF:

1. **Connection Works:**
   - ESP32 connects via USB
   - Serial gateway detects ESP32
   - MQTT connects to broker
   - Backend processes events
   - Dashboard displays data

2. **Sensors Work:**
   - Buzzer responds immediately to contact
   - Hits are detected correctly
   - Finish detection works

3. **Data Consistency:** ⭐ MOST IMPORTANT
   - Individual hit durations are correct
   - Total Hits = count of individual hits
   - Total Contact Time = sum of individual hit durations
   - Longest Hit = max of individual hit durations
   - Score calculation is correct
   - Backend log shows firmware and DB values match (or DB is correct if they differ)

4. **Dashboard Accuracy:**
   - No hardcoded/fake data
   - Real-time updates (within 3 seconds)
   - All cards show actual game results

### ❌ SYSTEM FAILS IF:

1. ESP32 doesn't connect or serial gateway can't find it
2. Buzzer doesn't respond to contacts
3. Events don't reach backend
4. **Dashboard shows individual hits but aggregate stats = 0** ← This should be FIXED now
5. Aggregate stats don't match individual hits
6. Dashboard shows stale/cached data

---

## TROUBLESHOOTING

### ESP32 Not Detected
1. Check Device Manager for COM3
2. Install CH340 drivers if needed
3. Try different USB cable
4. Try different USB port
5. Set explicit COM port: `$env:COM_PORT = "COM3"` before running rise.ps1

### No MQTT Connection
1. Check internet connectivity
2. Try: `Test-Connection test.mosquitto.org`
3. Check firewall
4. Wait and retry (backend auto-reconnects)

### Dashboard Not Updating
1. Check if backend is running: http://localhost:8000/api/health
2. Clear browser cache
3. Check browser console (F12) for errors
4. Verify API returns data: http://localhost:8000/api/runs

### Aggregate Stats Still Wrong
⚠️ **This should NOT happen after the fix!**

If it does:
1. Check backend log for "from DB" vs "firmware sent" values
2. If backend shows correct DB values → check dashboard code
3. If backend shows wrong DB values → report as new bug
4. Verify backend is using the FIXED version of main.py

---

## TEST COMPLETION RECORD

**Tester Name:** _________________________  
**Test Date:** _________________________  
**ESP32 Serial Number:** _________________________

### Results:

| Test Phase | Status | Notes |
|------------|--------|-------|
| Connection Verification | ☐ Pass ☐ Fail | |
| Sensor Testing | ☐ Pass ☐ Fail | |
| Perfect Run | ☐ Pass ☐ Fail | |
| Single Hit | ☐ Pass ☐ Fail | |
| Multiple Hits | ☐ Pass ☐ Fail | |
| Edge Cases | ☐ Pass ☐ Fail | |
| API Verification | ☐ Pass ☐ Fail | |
| Dashboard Validation | ☐ Pass ☐ Fail | |

**Overall Result:** ☐ PASS ☐ FAIL

**Critical Data Consistency Check:**

Individual Hit #1 Duration: _____ ms (from dashboard)  
Total Contact Time: _____ ms (from dashboard)  
Do they match? ☐ YES ☐ NO ⭐ MUST BE YES

**Additional Notes:**
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

---

**Test Checklist Version:** 1.0  
**Software Version:** AquaBuzz v1.1 (Post-Critical-Fix)  
**Last Updated:** November 25, 2026
