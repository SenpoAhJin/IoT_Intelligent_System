# PHASE 2B-2: DASHBOARD-CONTROLLED GAME LIFECYCLE IMPLEMENTATION

**Status:** ✅ COMPLETE  
**Date:** 2024-12-21  
**Commit:** fdb278a  

---

## EXECUTIVE SUMMARY

Phase 2B-2 successfully implements the complete dashboard-controlled game lifecycle infrastructure:

✅ **Dashboard controls integrated** - START GAME and FINISH GAME buttons now send commands to backend  
✅ **Backend command endpoints** - Three new API endpoints for game control  
✅ **Serial Gateway command transport** - Commands forwarded to ESP32 via serial  
✅ **Command acknowledgment protocol** - Full command lifecycle tracking with timeout detection  
✅ **All existing tests pass** - 33/33 tests successful, no regressions  

**CRITICAL:** ESP32 firmware does NOT yet handle these commands. This phase prepares the infrastructure only. Firmware integration is Phase 3.

---

## IMPLEMENTATION DETAILS

### PHASE 2: Dashboard Control

**File:** `dashboard/index.html`

**Changes:**
1. Updated `handleStartGame()` to call `POST /api/game/start`
2. Updated `handleFinishGame()` to call `POST /api/game/finish`
3. Added 6 game control states:
   - `WAITING` - Ready for new game, START GAME enabled
   - `STARTING` - Command pending, button disabled
   - `RUNNING` - Game active, FINISH GAME enabled
   - `FINISHING` - Command pending, button disabled
   - `FINISHED` - Game complete, NEW GAME enabled
   - `ERROR` - Error state with clear message, return to WAITING
4. Added `pendingCommand` tracking with request_id
5. Added `checkCommandTimeout()` for 7-second timeout
6. Added `handleCommandAck()` to process acknowledgments from SSE
7. Integrated command ACK handling in `handleLiveEvent()`
8. Removed integration pending notice
9. Enabled START/FINISH buttons by default

**UI State Machine:**
```
WAITING → [Click START] → STARTING → [ACK received] → [run_start event] → RUNNING
RUNNING → [Click FINISH] → FINISHING → [ACK received] → [run_finish event] → FINISHED
FINISHED → [3 seconds] → WAITING
ERROR → [Manual recovery] → WAITING
```

**Error Handling:**
- Command timeout (7 seconds): "Command timeout - ESP32 not responding"
- Already running: "Game already in progress"
- No active game: "No active game to finish"
- MQTT not connected: "MQTT broker not connected"
- Command rejected: Displays rejection reason from firmware

---

### PHASE 3: Backend Command Endpoints

**File:** `backend/app/main.py`

**New Endpoints:**

#### POST /api/game/start
```python
@app.post("/api/game/start")
async def start_game(device_id: str = "aquabuzz-001", player_id: str = "guest", db: Session = Depends(get_db))
```

**Flow:**
1. Validate no active game exists
2. Validate no pending commands
3. Create GameCommand record (status="pending")
4. Publish to MQTT topic `aquabuzz/commands/{device_id}`
5. Update status to "sent"
6. Return `{request_id, status}`

**Error Codes:**
- 400: Game already in progress
- 409: Command already pending
- 503: MQTT not connected or publish failed

#### POST /api/game/finish
```python
@app.post("/api/game/finish")
async def finish_game(device_id: str = "aquabuzz-001", db: Session = Depends(get_db))
```

**Flow:**
1. Validate active game exists
2. Validate no pending commands
3. Create GameCommand record with run_uid
4. Publish to MQTT
5. Update status to "sent"
6. Return `{request_id, status, run_uid}`

**Error Codes:**
- 400: No active game to finish
- 409: Command already pending
- 503: MQTT not connected or publish failed

#### GET /api/game/status
```python
@app.get("/api/game/status")
async def game_status(device_id: str = "aquabuzz-001", db: Session = Depends(get_db))
```

**Returns:**
```json
{
  "device_id": "aquabuzz-001",
  "device_online": true,
  "active_run": {
    "run_uid": "aquabuzz-001-1-5",
    "run_id": 123,
    "player_id": "guest",
    "started_at": "2024-12-21T10:30:00",
    "hits": 2
  },
  "pending_command": {
    "request_id": "req-a1b2c3d4",
    "command": "start",
    "status": "sent",
    "requested_at": "2024-12-21T10:29:58",
    "sent_at": "2024-12-21T10:29:58"
  }
}
```

**New Functions:**

#### handle_command_ack()
Processes acknowledgments from Serial Gateway:
```python
def handle_command_ack(ack_event: dict, db: Session):
    # Update GameCommand status to "acknowledged" or "rejected"
    # Broadcast ACK to dashboard via SSE
```

#### detect_command_timeouts()
Detects commands that exceed 5-second timeout:
```python
def detect_command_timeouts(db: Session, timeout_seconds: int = 5):
    # Find commands sent > 5 seconds ago without acknowledgment
    # Mark as "timeout", set error_reason
```

**Database Model Added:**

**File:** `backend/app/models.py`

```python
class GameCommand(Base):
    __tablename__ = "game_commands"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String, unique=True, nullable=False, index=True)
    device_id = Column(String, ForeignKey("devices.id"), nullable=False)
    command = Column(String, nullable=False)  # "start", "finish"
    
    # Lifecycle timestamps
    requested_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    
    # Status: "pending", "sent", "acknowledged", "timeout", "rejected"
    status = Column(String, default="pending")
    
    # Metadata
    player_id = Column(String, nullable=True)
    run_uid = Column(String, nullable=True)
    error_reason = Column(String, nullable=True)
```

**MQTT Integration:**

**File:** `backend/app/mqtt_client.py`

Updated `_on_connect()` to subscribe to acknowledgment topics:
```python
client.subscribe("aquabuzz/+/ack")
```

**Topic Structure:**
- `aquabuzz/{device_id}/events` - Game events (existing)
- `aquabuzz/{device_id}/heartbeat` - Device health (existing)
- `aquabuzz/{device_id}/ack` - Command acknowledgments (NEW)
- `aquabuzz/commands/{device_id}` - Commands to device (NEW)

---

### PHASE 4: Serial Gateway Command Transport

**File:** `backend/serial_gateway.py`

**New Attributes in `__init__`:**
```python
self.command_queue = queue.Queue(maxsize=10)  # Command transmission queue
self.pending_commands = {}  # cmd_id → {sent_at, timeout, command, request_id}
self.command_timeout_seconds = 5.0
```

**New Methods:**

#### queue_command()
```python
def queue_command(self, command_data: dict):
    """Queue command from MQTT for serial transmission"""
    self.command_queue.put_nowait(command_data)
```

#### send_command()
```python
def send_command(self, command_data: dict):
    """
    Send command to ESP32 via serial.
    Format: {"cmd":"start","t":1234567890}\n
    """
    serial_cmd = {
        "cmd": command_data['command'],
        "t": command_data['timestamp']
    }
    self.serial_port.write(json.dumps(serial_cmd).encode('utf-8') + b'\n')
    
    # Track for acknowledgment
    cmd_id = f"{command_data['command']}-{command_data['timestamp']}"
    self.pending_commands[cmd_id] = {...}
```

#### handle_command_acknowledgment()
```python
def handle_command_acknowledgment(self, ack_data: dict):
    """
    Process ACK from ESP32.
    Expected: {"cmd":"ack","cmd_id":"start-1234567890","status":"ok"}
    """
    cmd_id = ack_data.get("cmd_id")
    # Remove from pending, publish to backend
    self.publish_command_ack(...)
```

#### publish_command_ack()
```python
def publish_command_ack(self, request_id: str, command: str, status: str, error_reason: str = ""):
    """
    Publish ACK to backend via MQTT.
    Topic: aquabuzz/{device_id}/ack
    """
```

#### check_command_timeouts()
```python
def check_command_timeouts(self):
    """Check for commands without ACK after 5 seconds"""
    for cmd_id, cmd_info in self.pending_commands.items():
        if now - cmd_info["sent_at"] > cmd_info["timeout"]:
            self.publish_command_ack(..., status="timeout", ...)
```

**MQTT Integration:**

Updated `setup_mqtt()` to add message handler:
```python
self.mqtt_client.on_message = self._on_mqtt_message
```

New callback `_on_mqtt_message()`:
```python
def _on_mqtt_message(self, client, userdata, msg):
    """Handle incoming commands from backend"""
    if f"/commands/{self.device_id}" in msg.topic:
        command_data = json.loads(msg.payload.decode('utf-8'))
        self.queue_command(command_data)
```

Updated `_on_mqtt_connect()` to subscribe:
```python
command_topic = f"aquabuzz/commands/{self.device_id}"
client.subscribe(command_topic, qos=1)
```

**Read Loop Integration:**

Added to `read_serial_loop()`:
```python
# After serial read section
# Process command queue (non-blocking)
while not self.command_queue.empty():
    command_data = self.command_queue.get_nowait()
    self.send_command(command_data)

# Check for command timeouts
self.check_command_timeouts()
```

Updated serial message parsing to handle ACKs:
```python
elif "cmd" in raw_event and raw_event.get("cmd") == "ack":
    self.handle_command_acknowledgment(raw_event)
```

---

## COMMAND PROTOCOL SPECIFICATION

### Backend → Serial Gateway (MQTT)

**Topic:** `aquabuzz/commands/{device_id}`  
**QoS:** 1

**START Command:**
```json
{
  "command": "start",
  "request_id": "req-a1b2c3d4",
  "player_id": "alice",
  "timestamp": 1703174890
}
```

**FINISH Command:**
```json
{
  "command": "finish",
  "request_id": "req-e5f6g7h8",
  "run_uid": "aquabuzz-001-1-5",
  "timestamp": 1703174920
}
```

### Serial Gateway → ESP32 (Serial)

**Format:** JSON with newline terminator

**START Command:**
```json
{"cmd":"start","t":1703174890}
```

**FINISH Command:**
```json
{"cmd":"finish","t":1703174920}
```

### ESP32 → Serial Gateway (Serial)

**Expected ACK (success):**
```json
{"cmd":"ack","cmd_id":"start-1703174890","status":"ok"}
```

**Expected ACK (error):**
```json
{"cmd":"ack","cmd_id":"start-1703174890","status":"error","reason":"already_running"}
```

**Possible error reasons:**
- `already_running` - Cannot start, game in progress
- `lockout_active` - Cannot start, 5-second lockout after finish
- `not_running` - Cannot finish, no active game

### Serial Gateway → Backend (MQTT)

**Topic:** `aquabuzz/{device_id}/ack`  
**QoS:** 1

**ACK Payload:**
```json
{
  "device_id": "aquabuzz-001",
  "request_id": "req-a1b2c3d4",
  "command": "start",
  "status": "ok",
  "timestamp": 1703174890
}
```

**Error ACK:**
```json
{
  "device_id": "aquabuzz-001",
  "request_id": "req-a1b2c3d4",
  "command": "start",
  "status": "error",
  "error_reason": "already_running",
  "timestamp": 1703174890
}
```

**Timeout ACK:**
```json
{
  "device_id": "aquabuzz-001",
  "request_id": "req-a1b2c3d4",
  "command": "start",
  "status": "timeout",
  "error_reason": "No acknowledgment received within 5s",
  "timestamp": 1703174890
}
```

---

## TESTING RESULTS

### Automated Tests

**Command:** `pytest backend/tests/ -v`

**Results:**
```
============= test session starts =============
collected 33 items

tests/test_anomalies.py::test_too_fast_anomaly PASSED                   [  3%]
tests/test_anomalies.py::test_stuck_contact_anomaly PASSED              [  6%]
tests/test_anomalies.py::test_excessive_hits_anomaly PASSED             [  9%]
tests/test_anomalies.py::test_normal_run_no_anomalies PASSED            [ 12%]
tests/test_behavior.py::test_dragging_behavior PASSED                   [ 15%]
tests/test_behavior.py::test_overshooting_behavior PASSED               [ 18%]
tests/test_behavior.py::test_perfect_run PASSED                         [ 21%]
tests/test_behavior.py::test_behavior_advice PASSED                     [ 24%]
tests/test_classifier.py::test_expert_classification PASSED             [ 27%]
tests/test_classifier.py::test_intermediate_classification PASSED       [ 30%]
tests/test_classifier.py::test_beginner_classification PASSED           [ 33%]
tests/test_difficulty.py::test_increase_difficulty_for_clean_runs PASSED [ 36%]
tests/test_difficulty.py::test_decrease_difficulty_for_struggles PASSED [ 39%]
tests/test_difficulty.py::test_validate_difficulty_config PASSED        [ 42%]
tests/test_features.py::test_extract_features_basic PASSED              [ 45%]
tests/test_features.py::test_extract_features_no_hits PASSED            [ 48%]
tests/test_features.py::test_aggregate_features PASSED                  [ 51%]
tests/test_repairs.py::test_hit_aggregation_from_database PASSED        [ 54%]
tests/test_repairs.py::test_incomplete_hits_excluded PASSED             [ 57%]
tests/test_repairs.py::test_stale_run_detection PASSED                  [ 60%]
tests/test_repairs.py::test_active_runs_exclude_abandoned PASSED        [ 63%]
tests/test_repairs.py::test_duplicate_hit_start_idempotent PASSED       [ 66%]
tests/test_repairs.py::test_duplicate_hit_end_idempotent PASSED         [ 69%]
tests/test_repairs.py::test_duplicate_run_finish_idempotent PASSED      [ 72%]
tests/test_repairs.py::test_duplicate_run_start_idempotent PASSED       [ 75%]
tests/test_repairs.py::test_zero_hits_aggregation PASSED                [ 78%]
tests/test_sse_reliability.py::test_active_run_query_no_active_run PASSED [ 81%]
tests/test_sse_reliability.py::test_active_run_query_with_active_run PASSED [ 84%]
tests/test_sse_reliability.py::test_active_run_ignores_abandoned_runs PASSED [ 87%]
tests/test_sse_reliability.py::test_active_run_only_counts_completed_hits PASSED [ 90%]
tests/test_sse_reliability.py::test_sse_event_broadcasting PASSED       [ 93%]
tests/test_sse_reliability.py::test_sse_full_queue_handling PASSED      [ 96%]
tests/test_sse_reliability.py::test_sse_multiple_events_in_sequence PASSED [100%]

======== 33 passed, 68 warnings in 1.94s ========
```

✅ **ALL TESTS PASS** - No regressions detected

### Manual Testing Required

**IMPORTANT:** End-to-end testing cannot be performed until ESP32 firmware is updated (Phase 3).

**Current Testing Status:**
- ✅ Dashboard buttons enabled and functional
- ✅ Backend API endpoints respond correctly
- ✅ MQTT command publishing works
- ✅ Serial Gateway queues commands
- ⚠️ **Commands sent to serial but current firmware ignores them**
- ⚠️ **No ACKs received (firmware doesn't understand command protocol)**

**Manual Test Checklist (After Firmware Update):**
1. [ ] Click START GAME → ESP32 starts timer without maze touch
2. [ ] Dashboard shows "STARTING..." → "RUNNING" transition
3. [ ] Live metrics update during game
4. [ ] Click FINISH GAME → ESP32 finalizes game
5. [ ] Dashboard shows "FINISHING..." → "FINISHED" transition
6. [ ] Final score displayed correctly
7. [ ] NEW GAME returns to WAITING
8. [ ] Error handling: START during active game
9. [ ] Error handling: FINISH without active game
10. [ ] Error handling: Command timeout (disconnect ESP32)

---

## SAFETY AND BACKWARD COMPATIBILITY

### Existing Functionality Preserved

✅ **Hardware-triggered game lifecycle still works:**
- Touch maze wire → Game starts (existing firmware behavior)
- Touch finish pad → Game finishes (existing firmware behavior)
- All existing event processing unchanged

✅ **Data pipeline unchanged:**
- Serial Gateway still normalizes events
- MQTT topics unchanged (new command topics added, not replaced)
- Backend event processing identical
- Database schema extended (GameCommand table added)
- SSE broadcasting still works

✅ **Dashboard monitoring intact:**
- Real-time metrics display
- Leaderboard updates
- Player statistics
- Hit tracking
- Intelligence analysis

### Command Protocol Safety

**Current Firmware Behavior:**
- Ignores unknown JSON messages (command protocol not implemented)
- Single-character commands ('r', 's', 'b') still work
- No breaking changes to serial communication

**Command Queue Safety:**
- Non-blocking queue (maxsize=10)
- Failed commands publish error ACK immediately
- Timeout detection prevents hanging commands
- Serial disconnection handled gracefully

**Database Safety:**
- GameCommand table is independent
- No foreign key constraints to Run table
- Failed commands don't affect game records
- Idempotent command validation

---

## NEXT STEPS: PHASE 3 - FIRMWARE INTEGRATION

### ESP32 Firmware Changes Required

**File:** `firmware/aquabuzz_connected/aquabuzz_connected.ino`

**Required Changes:**

1. **Add JSON parsing library:**
```cpp
#include <ArduinoJson.h>
```

2. **Update handleSerialCommand():**
```cpp
void handleSerialCommand() {
    if (Serial.available()) {
        String line = Serial.readStringUntil('\n');
        
        // Try JSON parsing
        StaticJsonDocument<200> doc;
        DeserializationError error = deserializeJson(doc, line);
        
        if (!error) {
            const char* cmd = doc["cmd"];
            long timestamp = doc["t"];
            
            if (strcmp(cmd, "start") == 0) {
                handleDashboardStart(timestamp);
            } 
            else if (strcmp(cmd, "finish") == 0) {
                handleDashboardFinish(timestamp);
            }
        } else {
            // Fall back to single-char commands
            handleLegacyCommand(line[0]);
        }
    }
}
```

3. **Add handleDashboardStart():**
```cpp
void handleDashboardStart(long timestamp) {
    if (state == WAITING && millis() >= finishLockoutUntil) {
        // Start game WITHOUT requiring maze touch
        runNo++;
        runUid = ...;
        runStartMs = millis();
        state = RUNNING;
        
        // Acknowledge
        queuePrint("{\"cmd\":\"ack\",\"cmd_id\":\"start-%ld\",\"status\":\"ok\"}", timestamp);
        
        // Publish run_start
        queuePrint("{\"run\":%d,\"event\":\"run_start\",\"t_ms\":0,...}", runNo);
    } else {
        // Cannot start
        const char* reason = (state == RUNNING) ? "already_running" : "lockout_active";
        queuePrint("{\"cmd\":\"ack\",\"cmd_id\":\"start-%ld\",\"status\":\"error\",\"reason\":\"%s\"}", 
                   timestamp, reason);
    }
}
```

4. **Add handleDashboardFinish():**
```cpp
void handleDashboardFinish(long timestamp) {
    if (state == RUNNING) {
        // Force finish (same logic as onFinishPressed())
        // Close active hit, calculate stats, publish run_finish
        
        // Acknowledge
        queuePrint("{\"cmd\":\"ack\",\"cmd_id\":\"finish-%ld\",\"status\":\"ok\"}", timestamp);
        
        // ... finish game logic ...
    } else {
        queuePrint("{\"cmd\":\"ack\",\"cmd_id\":\"finish-%ld\",\"status\":\"error\",\"reason\":\"not_running\"}", 
                   timestamp);
    }
}
```

### Testing After Firmware Update

1. Upload updated firmware to ESP32
2. Restart Serial Gateway (to establish new session)
3. Restart Backend (to reconnect MQTT)
4. Open Dashboard
5. Run manual test checklist above
6. Verify command acknowledgments in Serial Gateway logs
7. Verify game lifecycle events in backend logs
8. Verify dashboard state transitions

---

## FILE CHANGES SUMMARY

### Modified Files

1. `backend/app/models.py` - Added GameCommand model (+30 lines)
2. `backend/app/db.py` - Import GameCommand in init_db (+1 line)
3. `backend/app/main.py` - Added command endpoints and handlers (+282 lines)
4. `backend/app/mqtt_client.py` - Subscribe to ack topics (+3 lines)
5. `backend/serial_gateway.py` - Command transport infrastructure (+245 lines)
6. `dashboard/index.html` - Integrated game controls (+190 lines)

**Total Changes:** +751 lines added, -56 lines removed

### New Database Tables

- `game_commands` (8 columns: id, request_id, device_id, command, requested_at, sent_at, acknowledged_at, status, player_id, run_uid, error_reason)

### New API Endpoints

- `POST /api/game/start`
- `POST /api/game/finish`
- `GET /api/game/status`

### New MQTT Topics

- Subscribe: `aquabuzz/commands/{device_id}` (backend publishes, gateway receives)
- Publish: `aquabuzz/{device_id}/ack` (gateway publishes, backend receives)

---

## TROUBLESHOOTING

### Dashboard shows "Command timeout"

**Cause:** ESP32 firmware doesn't understand command protocol yet  
**Solution:** Update firmware (Phase 3) or use hardware-triggered game lifecycle

### START GAME button does nothing

**Check:**
1. Browser console for errors
2. Backend logs for API request
3. MQTT broker connectivity
4. Serial Gateway logs for command transmission

### Commands not reaching ESP32

**Check:**
1. Serial Gateway connected to correct COM port
2. MQTT broker running and accessible
3. Backend MQTT client connected
4. Serial Gateway MQTT client connected
5. Command queue not full (maxsize=10)

### GameCommand records stuck in "sent" status

**Cause:** No acknowledgment received from ESP32  
**Expected:** Current firmware doesn't send ACKs  
**Solution:** Update firmware or commands will timeout after 5 seconds

---

## CONCLUSION

Phase 2B-2 is **COMPLETE** and **READY FOR FIRMWARE INTEGRATION**.

**What Works:**
- ✅ Dashboard sends commands to backend
- ✅ Backend creates command records
- ✅ Backend publishes to MQTT
- ✅ Serial Gateway receives commands
- ✅ Serial Gateway writes to serial port
- ✅ Command lifecycle tracking
- ✅ Timeout detection
- ✅ Error handling

**What's Missing:**
- ⚠️ ESP32 firmware command handler
- ⚠️ ESP32 firmware acknowledgment sender

**Next Phase:**
Update ESP32 firmware to complete the command flow and enable full dashboard-controlled game lifecycle.

---

**Prepared by:** Implementation Agent  
**Date:** 2024-12-21  
**Commit:** fdb278a
