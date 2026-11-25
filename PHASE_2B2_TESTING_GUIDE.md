# PHASE 2B-2: GAME CONTROL TESTING GUIDE

**Complete step-by-step testing instructions for validating dashboard game control functionality**

---

## PREREQUISITES

### Hardware Required
- ✅ ESP32 Dev Module
- ✅ USB cable (ESP32 to computer)
- ✅ Assembled AquaBuzz maze with sensors
- ✅ Windows PC with VS Code and Arduino IDE

### Software Required
- ✅ Python 3.8+ with virtual environment
- ✅ Arduino IDE with ESP32 board support
- ✅ MQTT broker (test.mosquitto.org or local)
- ✅ Modern web browser (Chrome, Firefox, Edge)

### Installation Verification
```powershell
# Check Python
python --version  # Should be 3.8+

# Check virtual environment
.\.venv\Scripts\Activate
python -c "import fastapi, paho.mqtt.client"  # Should not error

# Check Arduino IDE
# Open Arduino IDE > Tools > Board > ESP32 Dev Module should be listed
```

---

## TESTING PHASES

### PHASE 1: CODE VERIFICATION (No Hardware)

#### Step 1.1: Backend API Tests

```powershell
# Navigate to project root
cd "c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS"

# Activate virtual environment
.\.venv\Scripts\Activate

# Start backend
cd backend
uvicorn app.main:app --reload
```

Expected output:
```
INFO:     Started server process
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**In a new PowerShell window:**
```powershell
cd "c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS"
.\scripts\test-game-control.ps1
```

Expected results:
```
✓ GET /api/health
✓ GET /api/game/status
✓ POST /api/game/start
✓ Duplicate start correctly rejected
✓ Finish without game correctly rejected
```

**Success Criteria:**
- All API tests pass
- Duplicate commands rejected
- Error messages meaningful

---

#### Step 1.2: Dashboard Load Test

1. Open browser to: `http://localhost:8000/`
2. Open browser DevTools (F12)
3. Check Console for errors

**Expected:**
```
[Dashboard] Initializing...
[Dashboard] Initialization complete
[SSE] Connecting to live events stream...
[SSE] ✓ Connected to live events stream
```

**Success Criteria:**
- Dashboard loads without errors
- SSE connection established
- Game controls visible
- Shows "WAITING" state

---

### PHASE 2: FIRMWARE VERIFICATION (Serial Monitor Only)

#### Step 2.1: Upload Firmware

1. Open Arduino IDE
2. File > Open > `firmware/aquabuzz_connected/aquabuzz_connected.ino`
3. Tools > Board > ESP32 Dev Module
4. Tools > Port > (Select your ESP32 port, e.g., COM3)
5. Upload (Ctrl+U)

**Expected output:**
```
Connecting....
Writing at 0x00001000...
...
Hard resetting via RTS pin...
```

**Success Criteria:**
- Upload completes without errors
- No compilation errors

---

#### Step 2.2: Test Legacy Commands

1. Open Serial Monitor (Ctrl+Shift+M)
2. Set baud rate: **115200**
3. Set line ending: **Newline**

**Test 'r' command:**
```
Input: r
Expected output:
{"info":"reset"}
```

**Test 's' command:**
```
Input: s
Expected output:
{"info":"summary","run":0,"state":"WAITING","hits":0,"wifi":"...","mqtt":"..."}
```

**Test 'b' command:**
```
Input: b
Expected output:
{"info":"buzzer_test"}
[Buzzer should beep twice]
```

**Success Criteria:**
- All legacy commands work
- JSON responses received
- Buzzer responds to 'b' command

---

#### Step 2.3: Test JSON Command Parsing

**Test START command (manual):**
```
Input: {"cmd":"start","cmd_id":"test-1","t":1234567890,"player_id":"test"}\n
```

Expected output:
```json
{"run":1,"event":"run_start","t_ms":0,"esp32_ts_ms":...}
{"cmd":"ack","cmd_id":"test-1","status":"ok"}
```

**Test FINISH command:**
```
Input: {"cmd":"finish","cmd_id":"test-2","t":1234567891}\n
```

Expected output:
```json
{"run":1,"event":"run_finish",...}
{"cmd":"ack","cmd_id":"test-2","status":"ok"}
```

**Test Invalid Command:**
```
Input: {"cmd":"invalid","cmd_id":"test-3","t":1234567892}\n
```

Expected output:
```json
{"cmd":"ack","cmd_id":"test-3","status":"error","reason":"invalid_command"}
```

**Success Criteria:**
- JSON commands parsed correctly
- ACK messages sent
- Error handling works

---

### PHASE 3: INTEGRATED SYSTEM TESTING (Full Stack)

#### Step 3.1: Start All Services

**Terminal 1 - Backend:**
```powershell
cd backend
..\..\.venv\Scripts\Activate
uvicorn app.main:app --reload
```

**Terminal 2 - Serial Gateway:**
```powershell
cd backend
..\..\.venv\Scripts\Activate
python serial_gateway.py
```

Expected output:
```
[Serial] Connected to ESP32 on COM3
[MQTT] Connected to test.mosquitto.org:1883
[Heartbeat] Thread started
[Command] Worker thread started
```

**Terminal 3 - Dashboard:**
```
Open browser: http://localhost:8000/
```

**Success Criteria:**
- All three services running
- No connection errors
- Dashboard shows device online

---

#### Step 3.2: Test Remote START GAME

**Procedure:**
1. Ensure ESP32 is in WAITING state
2. Click "START GAME" button on dashboard

**Expected Behavior:**

| Timeline | Dashboard | Serial Monitor | Backend |
|----------|-----------|----------------|---------|
| T+0ms | Button click | - | - |
| T+10ms | Shows "STARTING..." | - | POST /api/game/start |
| T+50ms | - | Receives JSON cmd | Gateway sends command |
| T+60ms | - | Prints run_start event | - |
| T+70ms | - | Prints ACK | - |
| T+100ms | Shows "RUNNING" | - | SSE broadcasts event |
| T+100ms+ | Timer counting | Game in progress | Active run tracked |

**Serial Monitor Expected:**
```json
{"run":1,"event":"run_start","t_ms":0,"esp32_ts_ms":...}
{"cmd":"ack","cmd_id":"start-...","status":"ok"}
```

**Dashboard Expected:**
- Immediate transition to "STARTING"
- Then to "RUNNING" within 1 second
- Elapsed timer starts
- FINISH GAME button appears
- START GAME button hidden

**Success Criteria:**
- ✅ Game actually starts on ESP32
- ✅ Dashboard shows RUNNING state
- ✅ Timer counting up
- ✅ No duplicate commands sent
- ✅ Total latency < 200ms

---

#### Step 3.3: Test Remote FINISH GAME

**Procedure:**
1. Ensure game is RUNNING (from Step 3.2)
2. Click "FINISH GAME" button

**Expected Behavior:**

| Timeline | Dashboard | Serial Monitor | Backend |
|----------|-----------|----------------|---------|
| T+0ms | Button click | - | - |
| T+10ms | Shows "FINISHING..." | - | POST /api/game/finish |
| T+50ms | - | Receives JSON cmd | Gateway sends command |
| T+60ms | - | Closes active hit | - |
| T+65ms | - | Prints run_finish | - |
| T+70ms | - | Prints ACK | - |
| T+100ms | Shows "FINISHED" | - | SSE broadcasts event |
| T+100ms+ | Shows final score | Game ended | Run completed |

**Serial Monitor Expected:**
```json
[If hit active: {"run":1,"event":"hit_end",...}]
{"run":1,"event":"run_finish","t_ms":...,"hits":...,"score":...}
{"cmd":"ack","cmd_id":"finish-...","status":"ok"}
```

**Dashboard Expected:**
- Immediate transition to "FINISHING"
- Then to "FINISHED" with score
- Final metrics displayed
- "START NEW GAME" button appears

**Success Criteria:**
- ✅ Game finishes on ESP32
- ✅ Score calculated correctly
- ✅ Dashboard shows final metrics
- ✅ Active hit closed properly
- ✅ Total latency < 200ms

---

#### Step 3.4: Test Physical Maze Controls

**Test Physical START:**
1. Ensure WAITING state
2. Touch maze wire with wand

**Expected:**
- Game starts normally
- Same as remote start behavior
- Dashboard updates to RUNNING

**Test Physical FINISH:**
1. Game must be RUNNING
2. Touch finish contact

**Expected:**
- Game finishes with score
- Same as remote finish
- Dashboard shows FINISHED

**Success Criteria:**
- ✅ Physical controls unchanged
- ✅ Scoring same as before
- ✅ Dashboard synchronizes correctly

---

#### Step 3.5: Test Error Conditions

**Test: START while Running**
1. Start a game (remote or physical)
2. Click START GAME again

**Expected:**
- Backend rejects with 400 error
- Dashboard shows error message
- No duplicate game created

**Test: FINISH without Game**
1. Ensure WAITING state
2. Click FINISH GAME

**Expected:**
- Backend rejects with 400 error
- Dashboard shows "No active game"
- ESP32 rejects with error ACK

**Test: Disconnected ESP32**
1. Unplug ESP32 USB cable
2. Click START GAME

**Expected:**
- Command sent to backend
- Gateway cannot send to serial
- Timeout after 7 seconds
- Dashboard shows timeout error

**Test: Reconnection**
1. Plug ESP32 back in
2. Wait for gateway reconnection (~5-10s)
3. Click START GAME

**Expected:**
- Gateway reconnects automatically
- Command sent successfully
- Game starts normally

**Success Criteria:**
- ✅ All error cases handled gracefully
- ✅ Meaningful error messages
- ✅ Automatic reconnection works
- ✅ No crashes or hangs

---

#### Step 3.6: Test Duplicate Click Protection

**Procedure:**
1. Ensure WAITING state
2. Click START GAME 5 times rapidly (spam click)

**Expected:**
- Only 1 command sent
- Subsequent clicks ignored
- Console shows "Duplicate click ignored"
- Only 1 game created

**Success Criteria:**
- ✅ Click lock prevents duplicates
- ✅ No race conditions
- ✅ Single game instance

---

#### Step 3.7: Test State Synchronization

**Test: Browser Refresh During Game**
1. Start a game remotely
2. Refresh browser (F5)

**Expected:**
- Dashboard recovers active run state
- Shows RUNNING status
- Timer continues (approximate time)
- Can finish game

**Test: Multiple Browser Tabs**
1. Open dashboard in 2 browser tabs
2. Start game in Tab 1

**Expected:**
- Both tabs show RUNNING
- Both synchronized via SSE
- Finish in either tab works

**Success Criteria:**
- ✅ State recovery works
- ✅ Multi-tab synchronization
- ✅ No duplicate command issues

---

### PHASE 4: PERFORMANCE MEASUREMENT

#### Step 4.1: Measure End-to-End Latency

**Procedure:**
1. Open browser DevTools Console
2. Click START GAME
3. Watch timestamps in console

**Measurement Points:**
```javascript
[GameControl] START GAME requested        // T0
[GameControl] START command sent          // T1 (API response)
[SSE] Received command_ack                // T2 (ACK from ESP32)
[SSE] Received run_start                  // T3 (Game actually started)
[GameControl] Syncing with active run     // T4 (UI updated)
```

**Target Latencies:**
- T1 - T0: < 50ms (Dashboard → Backend)
- T2 - T1: < 100ms (Backend → ESP32 → ACK)
- T3 - T1: < 150ms (Backend → ESP32 → Event)
- T4 - T0: < 200ms (Total end-to-end)

**Success Criteria:**
- ✅ Total latency < 200ms
- ✅ No blocking operations
- ✅ Consistent timing across runs

---

#### Step 4.2: Command Throughput Test

**Procedure:**
1. Run 10 START/FINISH cycles
2. Measure time for each cycle
3. Check for degradation

**Expected:**
- Consistent latency across all cycles
- No memory leaks
- No connection failures

**Success Criteria:**
- ✅ All 10 cycles complete
- ✅ No performance degradation
- ✅ All commands acknowledged

---

## TROUBLESHOOTING GUIDE

### Issue: Firmware Won't Upload

**Symptoms:** "Failed to connect to ESP32"

**Solutions:**
1. Hold BOOT button while uploading
2. Check USB cable (try different cable)
3. Verify COM port in Tools > Port
4. Try lower upload speed: Tools > Upload Speed > 115200

---

### Issue: Serial Gateway Won't Connect

**Symptoms:** "No ESP32 found"

**Solutions:**
1. Check ESP32 is plugged in
2. Close Arduino Serial Monitor (can't share port)
3. Verify COM port: `COM_PORT=COM3` in .env
4. Try explicit port: `python serial_gateway.py` (will auto-detect)

---

### Issue: Dashboard Shows "No Connection"

**Symptoms:** Dashboard offline, SSE fails

**Solutions:**
1. Check backend is running: http://localhost:8000/api/health
2. Clear browser cache
3. Check firewall/antivirus
4. Try different browser

---

### Issue: Commands Timeout

**Symptoms:** Dashboard shows "Command timeout"

**Solutions:**
1. Check Serial Gateway running
2. Check MQTT broker accessible
3. Verify ESP32 serial output (is it receiving?)
4. Check cmd_id mismatch (gateway vs firmware)

---

### Issue: State Desynchronization

**Symptoms:** Dashboard shows wrong state

**Solutions:**
1. Refresh browser
2. Check SSE connection in DevTools
3. Verify active_run recovery logic
4. Check database Run status

---

## TEST RESULTS TEMPLATE

```
PHASE 2B-2 TEST RESULTS
Date: _______________
Tester: _____________

✓ = Pass, ✗ = Fail, ~ = Partial

PHASE 1: CODE VERIFICATION
[ ] API health check
[ ] Game status endpoint
[ ] Start command API
[ ] Finish command API
[ ] Duplicate protection
[ ] Dashboard loads

PHASE 2: FIRMWARE VERIFICATION
[ ] Firmware uploads
[ ] Legacy 'r' command
[ ] Legacy 's' command
[ ] Legacy 'b' command
[ ] JSON START parsing
[ ] JSON FINISH parsing
[ ] Error ACKs

PHASE 3: INTEGRATED TESTING
[ ] Remote START game
[ ] Remote FINISH game
[ ] Physical maze start
[ ] Physical finish
[ ] START while running (error)
[ ] FINISH without game (error)
[ ] ESP32 disconnection
[ ] Reconnection recovery
[ ] Duplicate click protection
[ ] Browser refresh recovery
[ ] Multi-tab sync

PHASE 4: PERFORMANCE
[ ] Latency < 200ms
[ ] 10 cycle throughput
[ ] No degradation

ISSUES FOUND:
_______________________________
_______________________________

OVERALL STATUS: ___________
```

---

## SUCCESS CHECKLIST

✅ **Implementation Complete:**
- [x] ESP32 firmware JSON parser
- [x] Serial Gateway command worker
- [x] Dashboard click protection
- [x] Backend API endpoints
- [x] ACK flow end-to-end

✅ **Testing Complete:**
- [ ] All API tests pass
- [ ] Firmware verification pass
- [ ] Remote START works
- [ ] Remote FINISH works
- [ ] Physical controls work
- [ ] Error handling works
- [ ] Performance targets met

✅ **Documentation Complete:**
- [x] Implementation report
- [x] Testing guide
- [x] Troubleshooting guide
- [x] Manual test script

---

## FINAL SIGN-OFF

**Tested By:** _______________  
**Date:** _______________  
**Hardware Used:** _______________  
**Test Duration:** _______________  

**Result:** ☐ PASS ☐ FAIL ☐ PARTIAL

**Notes:**
_______________________________
_______________________________
_______________________________

---

**END OF TESTING GUIDE**
