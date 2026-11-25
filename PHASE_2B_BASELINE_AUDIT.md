# PHASE 2B: BASELINE AUDIT REPORT

**Date:** November 25, 2026  
**Phase:** 2B - Dashboard-Controlled Game Lifecycle Integration  
**Status:** Baseline Audit Complete (READ-ONLY)

---

## EXECUTIVE SUMMARY

This audit establishes the current working baseline before Phase 2B implementation. The system is operational with Phase 2A dashboard UI prepared. This report identifies what must be preserved, what requires modification, and the implementation sequence.

### Current System Status

✅ **Operational Components:**
- Backend API running (FastAPI + Uvicorn)
- MQTT Broker connected (test.mosquitto.org)
- Serial Gateway operational
- Dashboard accessible (Phase 2A UI prepared)
- Database operational (SQLite)
- ESP32 firmware functional (v1.0, hardware-triggered)

⚠️ **Known Issues to Address:**
- SSE `ERR_INCOMPLETE_CHUNKED_ENCODING` (intermittent)
- Dashboard run selection race conditions
- Hardware-triggered game start (must replace with dashboard control)
- No dashboard command infrastructure

---

## 1. GIT STATUS

### Current Branch
```
latency-optimization-investigation
```

### Modified Files (Not Committed)
```
M dashboard/index.html          # Phase 2A game control UI
M scripts/rise.ps1              # RISE startup improvements
M scripts/rise-stop.ps1         # RISE shutdown improvements
M QUICKSTART_GUIDE.md           # Documentation updates
M START_HERE.md                 # Documentation updates
```

### Untracked Files (Documentation)
```
?? PHASE_1_*.md                 # Phase 1 implementation reports
?? PHASE_2A_*.md                # Phase 2A documentation
?? RISE_SYSTEM_COMPLETE.md      # RISE documentation
?? .aquabuzz-processes.json     # Process tracking
?? dashboard/index.html.backup-* # Backups
```

### Action Required
- Preserve existing modifications
- Do not auto-commit changes
- Create new backups before Phase 2B modifications

---

## 2. BACKEND ARCHITECTURE

### File: `backend/app/main.py` (643 lines)

#### Key Routes Identified

**Health and Status:**
- `GET /` - Root endpoint
- `GET /api/health` - System health check

**Data Retrieval:**
- `GET /api/runs` - List runs (supports pagination, player filter)
- `GET /api/runs/{run_id}` - Single run with hit details
- `GET /api/players` - Player statistics
- `GET /api/leaderboard` - Top scores

**Real-Time:**
- `GET /api/live` - **SSE endpoint** (requires investigation)

**Intelligence:**
- `GET /api/insights/{player_id}` - AI-generated insights
- `POST /api/game/config` - Push difficulty config

**Missing (Required for Phase 2B):**
- ❌ `POST /api/game/start` - Start game command
- ❌ `POST /api/game/finish` - Finish game command

#### SSE Implementation (Lines 435-477)

**Current Design:**
```python
sse_clients = []  # Global list

@app.get("/api/live")
async def live_events():
    client_queue = queue.Queue(maxsize=100)
    sse_clients.append(client_queue)
    
    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        asyncio.to_thread(client_queue.get, timeout=30),
                        timeout=31.0
                    )
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield f": keep-alive\n\n"
        except asyncio.CancelledError:
            print("[SSE] Client disconnected")
        finally:
            if client_queue in sse_clients:
                sse_clients.remove(client_queue)
    
    return StreamingResponse(event_generator(), ...)
```

**Identified Issues:**
1. **Blocking Queue in Async Context:** `queue.Queue` + `asyncio.to_thread`
2. **No Event IDs:** Cannot track/replay missed events
3. **Queue Overflow:** No explicit handling of full queue
4. **Multiple Clients:** Race condition in list modification
5. **Cancellation:** May leave orphaned threads

**Requires Fix:** Yes (Phase 1 of Phase 2B)

#### Event Broadcasting (Line 377)

```python
def broadcast_event(event: dict):
    """Broadcast event to all SSE clients."""
    for client_queue in sse_clients:
        try:
            client_queue.put_nowait(event)
        except queue.Full:
            print(f"[SSE] Queue full for client, event dropped")
```

**Issue:** Events silently dropped on queue full

#### MQTT Event Handler (Line 91)

```python
def handle_mqtt_event(event: dict):
    # Processes run_start, hit_start, hit_end, run_finish
    # Persists to database
    # Broadcasts to SSE clients
    # Triggers intelligence analysis
```

**Status:** Operational, must preserve

---

## 3. MQTT CLIENT

### File: `backend/app/mqtt_client.py` (113 lines)

**Class:** `MQTTEventIngester`

**Configuration:**
- Broker: test.mosquitto.org:1883
- Topics: `aquabuzz/+/events`, `aquabuzz/+/heartbeat`
- Client ID: `aquabuzz-backend`

**Key Methods:**
- `start()` - Connect and subscribe (background thread)
- `publish(topic, payload)` - Publish message (QoS 1)
- `set_event_handler(handler)` - Set callback

**Event Flow:**
```
ESP32 → Serial → Gateway → MQTT Publish → MQTT Client → handle_mqtt_event
```

**Status:** Operational, must preserve

**Phase 2B Extension Required:**
- Gateway needs to subscribe to command topics
- Backend needs to publish commands to gateway

---

## 4. SERIAL GATEWAY

### File: `backend/serial_gateway.py` (565 lines)

**Class:** `SerialGateway`

**Current Responsibilities:**
1. Auto-detect ESP32 COM port
2. Read serial events from ESP32
3. Normalize events (add run_uid, device_id, timestamps)
4. Publish events to MQTT broker
5. Maintain heartbeat

**Key Methods:**
- `find_esp32_port()` - Auto-detect COM port
- `connect_serial()` - Establish USB serial connection
- `connect_mqtt()` - Connect to MQTT broker
- `parse_line(line)` - Parse JSON events from serial
- `normalize_event(raw_event)` - Add metadata
- `publish_event(event_data)` - Forward to MQTT
- `generate_run_uid(run_no)` - Create run UID

**Event Formats Recognized:**
- `run_start` - Game started
- `hit_start` - Contact detected
- `hit_end` - Contact released
- `run_finish` - Game completed
- `run_cancel` - Game cancelled

**Current Flow:**
```
ESP32 Serial → parse_line → normalize_event → publish_event → MQTT
```

**Phase 2B Extension Required:**
1. Subscribe to MQTT command topics
2. Receive start/finish commands from backend
3. Send commands to ESP32 via Serial
4. Wait for ESP32 acknowledgment
5. Report command success/failure

**Current Serial Commands (ESP32 accepts):**
- `'r'` - Reset/cancel run
- `'s'` - Request status summary
- `'b'` - Buzzer test

**New Commands Needed:**
- Start game command
- Finish game command
- Command acknowledgment protocol

---

## 5. ESP32 FIRMWARE

### File: `firmware/aquabuzz_connected/aquabuzz_connected.ino` (600+ lines)

**Hardware:**
- ESP32 Dev Module
- PIN_MAZE = 27 (contact detection)
- PIN_FINISH = 33 (finish pad)
- PIN_BUZZER = 26 (MOSFET-controlled)

**Current Game States:**
```cpp
enum GameState {
  WAITING,
  RUNNING,
  FINISHED
};
```

**Current Game Flow (Hardware-Triggered):**

1. **WAITING:**
   - ESP32 powered on
   - Waiting for maze contact

2. **Touch Maze → RUNNING:**
   ```cpp
   void onMazePressed() {
     if (state == WAITING) {
       runNo++;
       runUid = generate_uid();
       runStartMs = now;
       state = RUNNING;
       queuePrint("{\"event\":\"run_start\",... }");
     }
   }
   ```

3. **RUNNING:**
   - Every maze contact = hit
   - Buzzer activates immediately
   - Hits recorded

4. **Touch Finish Pad → FINISHED:**
   ```cpp
   void onFinishPressed() {
     if (state == RUNNING) {
       runEndMs = now;
       state = FINISHED;
       // Calculate stats
       queuePrint("{\"event\":\"run_finish\",... }");
       state = WAITING;
     }
   }
   ```

**Critical Functions:**
- `driveBuzzerNow()` - Immediate buzzer response (must preserve)
- `updateContacts()` - Debouncing (20ms)
- `onMazePressed()` - **Currently starts game** (must modify)
- `onMazeReleased()` - Tracks hit duration
- `onFinishPressed()` - **Currently finishes game** (must modify)
- `handleSerialCommand()` - Processes incoming serial commands

**Phase 2B Required Changes:**

**WAITING State:**
- Maze contact must NOT start game
- Must accept START command from serial
- Send start acknowledgment

**RUNNING State:**
- Maze contact = hit (preserve)
- Buzzer immediate (preserve)
- Must accept FINISH command from serial

**FINISHED State:**
- Send final stats (preserve)
- Return to WAITING

**New Serial Protocol Needed:**
```
Incoming:
  CMD:START_GAME
  CMD:FINISH_GAME

Outgoing:
  ACK:GAME_STARTED
  ACK:GAME_FINISHED
```

---

## 6. DASHBOARD

### File: `dashboard/index.html` (48.5 KB after Phase 2A)

**Phase 2A Additions (Prepared but Disabled):**
- Game Control card
- START GAME button (green, disabled)
- FINISH GAME button (red, hidden)
- NEW GAME button (blue, hidden)
- Game metrics display
- Final score display
- Integration notice

**JavaScript State Variables:**
```javascript
let gameControlState = 'WAITING';  // WAITING | RUNNING | FINISHED
let gameControlMetrics = { ... };
let gameControlTimer = null;
let activeRunUid = null;
let displayedRunUid = null;
```

**Prepared Functions (Not Active):**
- `handleStartGame()` - Shows alert (Phase 2A)
- `handleFinishGame()` - Shows alert (Phase 2A)
- `updateGameControls(state, metrics)` - UI state machine
- `startGameControlTimer()` - Elapsed time display
- `updateGameMetricsDisplay(metrics)` - Update metrics
- `handleGameStateUpdate(event)` - Future SSE handler
- `syncGameControlWithActiveRun()` - Sync with active run

**SSE Connection:**
```javascript
let eventSource = null;
let useSseUpdates = true;

function connectSSE() {
    eventSource = new EventSource(`${API_BASE}/api/live`);
    eventSource.onmessage = (event) => {
        handleLiveEvent(JSON.parse(event.data));
    };
}

function handleLiveEvent(event) {
    if (event.event === 'run_start') {
        activeRunUid = event.run_uid;
        displayedRunUid = event.run_uid;
    } else if (event.event === 'run_finish') {
        activeRunUid = null;
    }
    loadData();
}
```

**Identified Issues:**
1. `loadRecentRuns()` sometimes selects wrong run
2. Race condition between SSE-triggered and manual refresh
3. Stale API responses can overwrite newer data
4. Browser refresh loses active run state

**Phase 2B Required:**
1. Enable control buttons
2. Implement actual API calls
3. Fix run selection logic
4. Fix race conditions
5. Add error handling
6. Remove integration notice after verification

---

## 7. DATABASE SCHEMA

### Models (SQLAlchemy)

**Player Table:**
- `id` (String, PK) - player_id
- `name` (String)
- `created_at`, `last_seen` (DateTime)

**Device Table:**
- `id` (String, PK) - device_id
- `name` (String)
- `last_heartbeat` (DateTime)

**Run Table:**
- `id` (Integer, PK, autoincrement)
- `run_uid` (String, unique, indexed) - **Authoritative identifier**
- `device_id` (FK)
- `player_id` (FK)
- `run_no` (Integer)
- `started_at`, `finished_at` (DateTime)
- `duration_ms` (Integer)
- `hits`, `total_contact_ms`, `longest_hit_ms` (Integer)
- `hit_penalty_ms` (Integer, default 2000)
- `score` (Integer)
- `status` (String: "started", "finished", "cancelled")

**Hit Table:**
- `id` (Integer, PK, autoincrement)
- `run_uid` (FK)
- `hit_no` (Integer)
- `start_ms` (Integer) - ms from run start
- `duration_ms` (Integer)

**Current Run UID Generation:**
```python
# In Serial Gateway:
def generate_run_uid(self, run_no: int) -> str:
    return f"{DEVICE_ID}-{self.boot_count}-{run_no}"
```

**Status:** Schema is correct, no changes required

---

## 8. SCORING FORMULA

### Current Implementation

**Firmware (aquabuzz_connected.ino):**
```cpp
int scoredHits = max(0, hitCount - freeHits);
unsigned long score = totalTimeMs + (scoredHits * hitPenaltyMs);
```

**Default Values:**
- `hitPenaltyMs = 2000` (2 seconds per hit)
- `freeHits = 0` (no free hits)

**Formula:**
```
score = duration_ms + (max(0, hits - freeHits) * hit_penalty_ms)
```

**Status:** Correct, must preserve

---

## 9. EVENT VOCABULARY

### Current Events (ESP32 → Serial → MQTT → Backend)

**run_start:**
```json
{
  "event": "run_start",
  "run": 1,
  "t_ms": 0,
  "esp32_ts_ms": 123456
}
```

**hit_start:**
```json
{
  "event": "hit_start",
  "run": 1,
  "hit": 1,
  "t_ms": 1234,
  "esp32_ts_ms": 124690
}
```

**hit_end:**
```json
{
  "event": "hit_end",
  "run": 1,
  "hit": 1,
  "t_ms": 1284,
  "dur_ms": 50,
  "esp32_ts_ms": 124740
}
```

**run_finish:**
```json
{
  "event": "run_finish",
  "run": 1,
  "t_ms": 12340,
  "hits": 3,
  "total_contact_ms": 150,
  "longest_hit_ms": 60,
  "hit_penalty_ms": 2000,
  "score": 18340,
  "esp32_ts_ms": 135796
}
```

**Status:** Must preserve for backward compatibility

**New Events Needed (Phase 2B):**
- `game_start_ack` - ESP32 confirms start
- `game_finish_ack` - ESP32 confirms finish
- `command_error` - Command failed

---

## 10. TESTING INFRASTRUCTURE

### Existing Tests

**Backend Tests:**
- `backend/tests/test_anomalies.py`
- `backend/tests/test_behavior.py`
- `backend/tests/test_classifier.py`

**Integration Tests:**
- `scripts/test-system.ps1` - System health tests
- `scripts/test-integration.ps1`
- `scripts/test-full-flow.py`

**Manual Tests:**
- Phase 2A visual test checklist

**Status:** Need to add SSE reliability tests and game control tests

---

## 11. IDENTIFIED DEFECTS

### SSE Reliability (`ERR_INCOMPLETE_CHUNKED_ENCODING`)

**Symptoms:**
- Intermittent browser error
- Dashboard loses connection
- Events may be missed

**Suspected Causes:**
1. Blocking queue in async context
2. Client disconnection during event delivery
3. Queue overflow
4. CancelledError handling
5. No event replay mechanism

**Investigation Required:** Yes (Phase 1 of Phase 2B)

### Dashboard Run Selection

**Issue:** Sometimes displays wrong run after game finishes

**Root Cause:**
```javascript
// Incorrect fallback:
runToDisplay = data.find(r => r.status === 'finished');
// May select an older finished run instead of the most recent one
```

**Fix Required:** Proper priority logic (Phase 1)

### Race Conditions

**Issue:** Overlapping API requests can cause stale data to overwrite fresh data

**Current Mitigation:** `lastApiRequestTime` tracking (partial)

**Fix Required:** Better request sequencing (Phase 1)

---

## 12. PRESERVED FUNCTIONALITY

### Must NOT Break

✅ **Hardware:**
- GPIO 27 maze contact detection
- GPIO 26 MOSFET buzzer control
- GPIO 33 finish pad (currently triggers game end)
- Immediate buzzer response (<10ms)
- 20ms debouncing

✅ **Backend:**
- Existing API routes
- Database schema
- MQTT ingestion
- Player management
- Leaderboard calculation
- Intelligence modules
- Historical data

✅ **Dashboard:**
- System health monitoring
- Recent activity
- Top scores
- Player statistics
- Run details
- Hit records
- Responsive layout

✅ **RISE:**
- Startup scripts
- Shutdown scripts
- Process management

---

## 13. PHASE 2B IMPLEMENTATION SEQUENCE

### PHASE 1: SSE RELIABILITY FIX (Estimated: 3-4 hours)

**Tasks:**
1. Investigate SSE `ERR_INCOMPLETE_CHUNKED_ENCODING`
2. Replace blocking queue with async queue
3. Add event IDs for replay
4. Fix client cleanup
5. Add queue overflow handling
6. Fix dashboard run selection
7. Fix race conditions
8. Add SSE tests
9. Test with multiple clients
10. Verify browser refresh recovery

**Deliverable:** Reliable SSE connection with no errors

### PHASE 2: BACKEND GAME CONTROL (Estimated: 2-3 hours)

**Tasks:**
1. Add `POST /api/game/start` endpoint
2. Add `POST /api/game/finish` endpoint
3. Add command validation
4. Add device availability check
5. Add duplicate request protection
6. Add command timeout handling
7. Add structured logging
8. Add backend tests
9. Test endpoints with curl/Postman

**Deliverable:** Backend endpoints ready for gateway integration

### PHASE 3: SERIAL GATEWAY INTEGRATION (Estimated: 2-3 hours)

**Tasks:**
1. Subscribe to command MQTT topics
2. Implement command forwarding to ESP32
3. Implement acknowledgment tracking
4. Add command timeout handling
5. Add error reporting
6. Test command flow without ESP32
7. Test with mock serial responses

**Deliverable:** Gateway ready to send commands to ESP32

### PHASE 4: ESP32 FIRMWARE INTEGRATION (Estimated: 3-4 hours)

**Tasks:**
1. Design serial command protocol
2. Add command parser
3. Modify `onMazePressed()` - remove auto-start
4. Modify `onFinishPressed()` - remove auto-finish
5. Add `handleStartCommand()`
6. Add `handleFinishCommand()`
7. Send acknowledgments
8. Preserve buzzer responsiveness
9. Upload firmware (requires authorization)
10. Test physical hardware

**Deliverable:** ESP32 accepts dashboard commands

### PHASE 5: DASHBOARD ACTIVATION (Estimated: 2-3 hours)

**Tasks:**
1. Enable control buttons
2. Implement API calls
3. Add error handling
4. Add loading states
5. Add success/failure feedback
6. Remove integration notice
7. Test full end-to-end flow
8. Test failure scenarios

**Deliverable:** Fully functional dashboard control

**Total Estimated Duration:** 12-17 hours

---

## 14. ROLLBACK STRATEGY

### Backup Before Each Phase

**Phase 1 (SSE):**
- `backend/app/main.py`
- `dashboard/index.html`

**Phase 2 (Backend):**
- `backend/app/main.py`

**Phase 3 (Gateway):**
- `backend/serial_gateway.py`

**Phase 4 (Firmware):**
- `firmware/aquabuzz_connected/aquabuzz_connected.ino`

**Phase 5 (Dashboard):**
- `dashboard/index.html`

### Rollback Commands

```powershell
# Stop system
rise-stop

# Restore backup
Copy-Item <backup-file> <original-file>

# Restart system
rise
```

### ESP32 Firmware Rollback

Keep backup `.ino` file and use Arduino IDE to reflash if needed.

---

## 15. RISK ASSESSMENT

### High Risk

🔴 **ESP32 Firmware Modification**
- Risk: Breaks existing game functionality
- Mitigation: Thorough testing, preserve buzzer responsiveness
- Rollback: Reflash backup firmware

🔴 **SSE Implementation Change**
- Risk: Breaks real-time updates
- Mitigation: Keep polling fallback, test with multiple clients
- Rollback: Restore `main.py`

### Medium Risk

🟡 **Serial Gateway Extension**
- Risk: Breaks event forwarding
- Mitigation: Preserve existing read loop, add command handling separately
- Rollback: Restore `serial_gateway.py`

🟡 **Dashboard Control Activation**
- Risk: UI becomes unresponsive
- Mitigation: Add loading states, error handling
- Rollback: Restore `index.html`

### Low Risk

🟢 **Backend Endpoint Addition**
- Risk: Minimal (new endpoints only)
- Mitigation: Existing routes unaffected
- Rollback: Remove new endpoints

---

## 16. SUCCESS CRITERIA

### Functional Requirements

- [ ] Dashboard START GAME button enabled and functional
- [ ] ESP32 starts game on command (no maze touch required)
- [ ] Game enters RUNNING state
- [ ] Maze contact records hits (not game start)
- [ ] Buzzer responds immediately (<10ms)
- [ ] Multiple hits supported
- [ ] Dashboard FINISH GAME button enabled and functional
- [ ] ESP32 finalizes game on command
- [ ] Final metrics persisted correctly
- [ ] NEW GAME works
- [ ] Historical records preserved

### Technical Requirements

- [ ] SSE reliable (no `ERR_INCOMPLETE_CHUNKED_ENCODING`)
- [ ] SSE delivers all events
- [ ] Browser refresh recovers state
- [ ] No race conditions
- [ ] Correct run selection
- [ ] Commands acknowledged
- [ ] Command timeouts handled
- [ ] Error messages clear
- [ ] All existing API routes work
- [ ] All automated tests pass

### Performance Requirements

- [ ] Buzzer latency unchanged (<10ms)
- [ ] Dashboard latency <100ms
- [ ] SSE latency <200ms
- [ ] No new memory leaks

---

## 17. NEXT STEPS

### Immediate Actions

1. ✅ Baseline audit complete (this document)
2. ⏳ Begin Phase 1: SSE reliability investigation
3. ⏳ Create SSE test suite
4. ⏳ Fix identified SSE issues
5. ⏳ Verify SSE reliability before proceeding

### Phase Gate Decisions

**After Phase 1:**
- SSE must be reliable before proceeding to Phase 2
- Dashboard must correctly display active run
- No race conditions

**After Phase 3:**
- Backend and gateway must pass command tests
- Do not proceed to firmware without working backend

**After Phase 4:**
- Firmware must be tested on physical hardware
- Buzzer responsiveness must be verified
- Existing game flow must work

**Final Gate:**
- Complete end-to-end physical testing
- All acceptance criteria met
- Documentation complete

---

## BASELINE AUDIT STATUS: ✅ COMPLETE

**Recommendation:** Proceed to Phase 1 (SSE Reliability Fix)

**Current System:** Operational, ready for incremental enhancement

**Risk Level:** Medium (manageable with careful implementation)

**Estimated Timeline:** 12-17 hours total (5 phases)

---

**Audit Completed By:** Senior IoT Systems Architect  
**Date:** November 25, 2026  
**Next Phase:** Phase 2B-1 (SSE Reliability Investigation)

