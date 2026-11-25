# PHASE 1 CHECKLIST: PROTECT & BASELINE

**Purpose:** Create safety backup and establish performance baseline  
**Status:** Ready to execute  
**Estimated Time:** 15-20 minutes

---

## ☑️ QUICK CHECKLIST

```
[ ] 1. Create backup Git tag
[ ] 2. Connect ESP32 via USB
[ ] 3. Enable latency logging
[ ] 4. Start system (rise)
[ ] 5. Verify health (verify-startup.ps1)
[ ] 6. Play maze and collect data
[ ] 7. Analyze latency measurements
[ ] 8. Determine if optimization is needed
```

---

## STEP 1: CREATE BACKUP TAG (5 minutes)

### Why?
This creates a rollback point if optimization breaks something.

### Commands:

```powershell
# Navigate to project
cd "c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS"

# Create annotated tag
git tag -a "v1.0-baseline-before-optimization" -m "Working baseline: 26 tests pass, SSE ready, latency instrumentation present"

# Push to remote (optional but recommended)
git push origin v1.0-baseline-before-optimization

# Verify tag created
git tag -l -n1
```

### Expected Output:
```
v1.0-baseline-before-optimization Working baseline: 26 tests pass, SSE ready, latency instrumentation present
```

✅ **Checkpoint:** Tag created successfully

---

## STEP 2: CONNECT ESP32 (1 minute)

### Physical Setup:
1. Locate ESP32 device
2. Connect USB cable to ESP32
3. Plug USB into laptop
4. Wait for Windows driver installation (if first time)

### Verify Connection:

```powershell
# List COM ports
Get-WmiObject Win32_SerialPort | Select-Object DeviceID, Description
```

### Expected Output (example):
```
DeviceID Description
-------- -----------
COM4     Silicon Labs CP210x USB to UART Bridge
```

✅ **Checkpoint:** ESP32 appears in COM port list

---

## STEP 3: ENABLE LATENCY LOGGING (2 minutes)

### Backend Configuration:

**Edit:** `backend\.env`

**Change this line:**
```env
LOG_LEVEL=INFO
```

**To:**
```env
LOG_LEVEL=DEBUG
```

**Save the file.**

### Gateway Configuration:

**Open PowerShell and run:**
```powershell
$env:GATEWAY_VERBOSE = "1"
```

✅ **Checkpoint:** Logging enabled

---

## STEP 4: START SYSTEM (3 minutes)

### Start All Services:

```powershell
rise
```

### Expected Output:
```
==================================================
    AquaBuzz Startup Complete
==================================================

Services Running:
  Backend API: http://localhost:8000 (PID: XXXXX)
  Serial Gateway: USB Serial to MQTT (PID: XXXXX)
  Dashboard: http://localhost:3000 (PID: XXXXX)
  MQTT Broker: test.mosquitto.org:1883 (public)

...

To stop all services, run: rise-stop
```

### Watch Serial Gateway Window:
Look for:
```
[Serial] Found potential ESP32 on COM4: ...
[Serial] Connected to ESP32 on COM4
[MQTT] Connected to test.mosquitto.org:1883
[Heartbeat] Published (serial: true, mqtt: true)
```

✅ **Checkpoint:** All services started, ESP32 connected

---

## STEP 5: VERIFY HEALTH (2 minutes)

### Run Verification Script:

```powershell
.\scripts\verify-startup.ps1
```

### Expected Output:
```
==================================================
    AquaBuzz Startup Verification
==================================================

[Test 1] Checking Backend API health...
  [PASS] Backend is healthy
  [PASS] MQTT is connected

[Test 2] Checking Backend API endpoints...
  [PASS] Runs endpoint responding

[Test 3] Checking Dashboard server...
  [PASS] Dashboard running on port 3000

[Test 4] Checking process tracking...
  [PASS] Process tracker exists
    - backend: RUNNING
    - gateway: RUNNING
    - dashboard: RUNNING

[Test 5] Verifying critical hit aggregation fix...
  [PASS] All fix components verified

[Test 6] Checking database connectivity...
  [PASS] Database file exists

==================================================
    All Checks Passed!
==================================================

System Status: READY FOR TESTING

Dashboard URL: http://localhost:3000
API Docs: http://localhost:8000/docs
```

✅ **Checkpoint:** All health checks pass

---

## STEP 6: COLLECT LATENCY DATA (10 minutes)

### Setup Data Collection:

**Open 3 windows side by side:**

1. **Serial Gateway window** (already open from `rise`)
2. **Browser console** (F12 in dashboard)
3. **Notepad** (for recording observations)

### Play Physical Maze:

**Test 1: Short Game (3 hits)**
1. Start game on physical maze
2. Make 3 deliberate short contacts (~100ms each)
3. Finish game
4. Record observations

**Test 2: Long Contact**
1. Start game
2. Make 1 long deliberate contact (~1000ms)
3. Finish game
4. Record observations

**Test 3: Rapid Hits**
1. Start game
2. Make 5 rapid successive contacts
3. Finish game
4. Record observations

### Data to Collect:

**From Serial Gateway Window:**
```
[Latency] hit_start: serial_read=X.Xms
[Latency] hit_start: mqtt_publish=X.Xms
[Latency] hit_end: serial_read=X.Xms
[Latency] hit_end: mqtt_publish=X.Xms
```

**From Backend Window (if visible):**
```
[Latency] hit_start run-XXX hit-1: db_write=X.Xms, total=X.Xms
[Latency] hit_end run-XXX hit-1: db_write=X.Xms, total=X.Xms
```

**From Browser Console (F12):**
```
[Dashboard] API fetch: X.Xms, render: X.Xms
[SSE] Received hit_start event: ...
[SSE] Received hit_end event: ...
```

**Perceived Latency:**
```
Buzzer response: Immediate / Delayed?
Dashboard update: < 100ms / 100-500ms / > 500ms?
```

### Record in Notepad:

```
TEST 1: Short Game (3 hits)
─────────────────────────────
Buzzer: [Immediate/Delayed]
Dashboard: [Fast/Slow]

Serial Gateway Logs:
[Copy/paste latency lines]

Backend Logs:
[Copy/paste latency lines]

Dashboard Console:
[Copy/paste latency lines]

Perceived total latency: ~XXXms


TEST 2: Long Contact
─────────────────────────────
[Same as above]


TEST 3: Rapid Hits
─────────────────────────────
[Same as above]
```

✅ **Checkpoint:** Latency data collected

---

## STEP 7: ANALYZE MEASUREMENTS (5 minutes)

### Calculate Average Latency:

**Example Calculation:**
```
Stage                    | Average Time
─────────────────────────|─────────────
ESP32 event generation   | ~0ms (immediate)
Serial read              | 5ms
MQTT publish             | 15ms
MQTT delivery (estimate) | 20-50ms (network)
Backend processing       | 25ms
SSE broadcast            | 5-10ms (estimate)
Dashboard receive        | 10-20ms (network)
Dashboard render         | 3ms
─────────────────────────|─────────────
TOTAL ESTIMATED          | 83-128ms
```

### Determine Bottleneck:

**If total latency is:**

**< 100ms:**
- ✅ System is excellent
- Minor polish only
- SSE is likely working well

**100-200ms:**
- ⚠️ Acceptable but could improve
- Identify slowest stage
- Optimize that stage only

**200-500ms:**
- ⚠️ Noticeable delay
- Likely network or polling delay
- Verify SSE is working
- Check MQTT network latency

**> 500ms:**
- ❌ Significant problem
- Dashboard polling may be the issue
- SSE may not be working
- Check dashboard refresh interval

### Identify Primary Bottleneck:

```
[ ] Serial communication (> 50ms per event)
[ ] MQTT delivery (> 100ms)
[ ] Backend processing (> 50ms)
[ ] Database writes (> 20ms)
[ ] Dashboard polling (> 1s refresh)
[ ] SSE not working (falling back to polling)
[ ] Network latency (poor WiFi)
```

✅ **Checkpoint:** Bottleneck identified

---

## STEP 8: DECIDE NEXT ACTION (1 minute)

### Decision Tree:

**If total latency < 200ms AND SSE is working:**
```
✅ System is performing well
✅ No major optimization needed
→ Document success and close Phase 2
→ Minor polish if desired (Phase 3 optional)
```

**If SSE is NOT working:**
```
⚠️ Dashboard falling back to polling
→ Fix SSE connection issues
→ Verify SSE event handling
→ Test reconnection behavior
```

**If MQTT delivery is slow (> 100ms):**
```
⚠️ Network latency issue
→ Consider local MQTT broker
→ Test with better WiFi connection
→ Check QoS settings
```

**If backend processing is slow (> 50ms):**
```
⚠️ Database or processing bottleneck
→ Profile database queries
→ Consider async operations
→ Optimize event processing
```

**If dashboard polling is the issue:**
```
⚠️ SSE should fix this (but may not be working)
→ Debug SSE connection
→ Verify SSE event handling
→ Fix SSE reconnection
```

✅ **Checkpoint:** Next phase strategy determined

---

## STOPPING THE SYSTEM

### When Done Testing:

```powershell
rise-stop
```

### Expected Output:
```
==================================================
    AquaBuzz Shutdown System
==================================================

Stopping backend (PID: XXXXX, Port: 8000)...
  Stopped backend

Stopping gateway (PID: XXXXX, Port: 0)...
  Stopped gateway

Stopping dashboard (PID: XXXXX, Port: 3000)...
  Stopped dashboard

Process tracker file removed

==================================================
    Shutdown complete
==================================================

Summary:
  Stopped: 3 service(s)
```

---

## ROLLBACK PROCEDURE (If Needed)

### If optimization breaks something:

```powershell
# Check out the backup tag
git checkout v1.0-baseline-before-optimization

# Or reset to tag (if on same branch)
git reset --hard v1.0-baseline-before-optimization

# Restart system
rise
```

---

## TROUBLESHOOTING

### ESP32 Not Detected:

**Check:**
```powershell
# List available COM ports
Get-WmiObject Win32_SerialPort | Select-Object DeviceID, Description

# Try explicit COM port
$env:COM_PORT = "COM4"
rise
```

### Backend Not Starting:

**Check:**
```powershell
# Port conflict?
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue

# Kill conflicting process
Stop-Process -Id <PID> -Force
```

### MQTT Not Connecting:

**Check:**
```powershell
# Internet connectivity
Test-Connection -ComputerName 8.8.8.8 -Count 1

# Try alternative broker
# Edit backend/.env:
#   MQTT_BROKER_HOST=broker.hivemq.com
```

### Dashboard Not Loading:

**Check:**
```powershell
# Dashboard port
# Open browser to: http://localhost:3000
# Or check alternative ports: 3001, 3002, 8080, 8081
```

---

## SUCCESS CRITERIA

### Phase 1 Complete When:

- [x] Backup tag created
- [x] System starts successfully
- [x] All health checks pass
- [x] ESP32 connects and communicates
- [x] Latency measurements collected
- [x] Bottleneck identified (or confirmed fast)
- [x] Next phase strategy determined

### Ready for Phase 2 When:

- [x] Baseline measurements documented
- [x] Optimization targets identified
- [x] Rollback capability verified

---

## NEXT PHASE

### If Optimization Needed:

**Phase 2:** Targeted optimization of identified bottleneck
- Fix SSE issues (if not working)
- Optimize slowest stage
- Re-test after each change
- Maintain rollback capability

### If System Already Fast:

**Phase 2:** Documentation and polish
- Document baseline performance
- Update user guides
- Optional minor improvements
- Declare success

---

**Phase 1 Checklist Complete!**

**When ready to proceed, report your findings:**
- Total measured latency: ___ms
- Primary bottleneck: ___________
- SSE working? Yes / No
- Optimization needed? Yes / No
