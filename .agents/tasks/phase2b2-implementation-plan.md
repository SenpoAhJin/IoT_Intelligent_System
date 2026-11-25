# PHASE 2B-2: END-TO-END GAME CONTROL IMPLEMENTATION PLAN

## EXECUTIVE SUMMARY

**Current State:** Dashboard START/FINISH buttons exist but are non-functional. The ESP32 firmware only supports single-character serial commands ('r', 's', 'b') and cannot process JSON commands from the Serial Gateway.

**Root Cause:** Protocol mismatch between Serial Gateway (sends JSON) and ESP32 firmware (expects single characters). No command acknowledgment mechanism exists.

**Implementation Strategy:** Implement the missing pieces in correct dependency order:
1. ESP32 firmware JSON parser and command handlers
2. Serial Gateway command transmission optimization  
3. Dashboard UI improvements for immediate responsiveness
4. Backend API validation and error handling
5. End-to-end integration testing

---

## CRITICAL FINDING

**PROTOCOL INCOMPATIBILITY DETECTED:**

- **Serial Gateway** (`serial_gateway.py` line ~380): Sends JSON commands like:
  ```json
  {"cmd":"start","t":1234567890}\n
  ```

- **ESP32 Firmware** (`aquabuzz_connected.ino` lines 173-192): Only handles single characters:
  ```cpp
  char cmd = Serial.read();
  if (cmd == 'r') // reset
  if (cmd == 's') // summary
  if (cmd == 'b') // buzzer test
  ```

**Result:** Dashboard commands are silently ignored by ESP32. The gateway sends JSON, but the firmware reads one character at a time and cannot parse JSON.

---

## IMPLEMENTATION PHASES

### PHASE 1: ESP32 FIRMWARE - JSON COMMAND SUPPORT ⚠️ CRITICAL

**Priority:** HIGHEST - This is the blocking issue

**Current Implementation:**
- `handleSerialCommand()` only reads single characters
- No JSON parsing capability
- No command acknowledgment

**Required Changes:**

#### 1.1: Add JSON Command Buffer
```cpp
// Global state
String serialCommandBuffer = "";
const int MAX_COMMAND_LENGTH = 256;
```

#### 1.2: Implement JSON Command Parser
```cpp
void handleSerialCommand() {
  while (Serial.available()) {
    char c = Serial.read();
    
    // Handle legacy single-character commands immediately
    if (serialCommandBuffer.length() == 0 && c != '{') {
      handleLegacyCommand(c);
      continue;
    }
    
    // Build JSON command buffer
    if (c == '\n' || c == '\r') {
      if (serialCommandBuffer.length() > 0) {
        processJsonCommand(serialCommandBuffer);
        serialCommandBuffer = "";
      }
    } else {
      serialCommandBuffer += c;
      if (serialCommandBuffer.length() > MAX_COMMAND_LENGTH) {
        serialCommandBuffer = "";  // Overflow protection
      }
    }
  }
}
```

#### 1.3: Implement START GAME Command Handler
```cpp
void processJsonCommand(String json) {
  // Parse JSON manually (ArduinoJson if available, otherwise simple parsing)
  // Expected: {"cmd":"start","cmd_id":"start-1234567890","t":1234567890,"player_id":"guest"}
  
  String cmd = extractJsonValue(json, "cmd");
  String cmd_id = extractJsonValue(json, "cmd_id");
  String player = extractJsonValue(json, "player_id");
  
  if (cmd == "start") {
    if (state == WAITING && millis() >= finishLockoutUntil) {
      playerId = player.length() > 0 ? player : "guest";
      
      // Execute SAME logic as physical maze start
      runNo++;
      runUid = String(DEVICE_ID) + "-" + String(bootCount) + "-" + String(runNo);
      runStartMs = millis();
      runEndMs = 0;
      hitCount = 0;
      state = RUNNING;
      finishReleased = !finishPressed;
      
      queuePrint("{\"run\":%d,\"event\":\"run_start\",\"t_ms\":0,\"esp32_ts_ms\":%lu}", runNo, millis());
      queuePrint("{\"cmd\":\"ack\",\"cmd_id\":\"%s\",\"status\":\"ok\"}", cmd_id.c_str());
      
    } else {
      String reason = (state != WAITING) ? "already_running" : "finish_lockout";
      queuePrint("{\"cmd\":\"ack\",\"cmd_id\":\"%s\",\"status\":\"error\",\"reason\":\"%s\"}", 
                 cmd_id.c_str(), reason.c_str());
    }
  }
  else if (cmd == "finish") {
    if (state == RUNNING) {
      // Execute SAME logic as physical finish contact
      onFinishPressed();  // This already handles hit closure and scoring
      queuePrint("{\"cmd\":\"ack\",\"cmd_id\":\"%s\",\"status\":\"ok\"}", cmd_id.c_str());
    } else {
      queuePrint("{\"cmd\":\"ack\",\"cmd_id\":\"%s\",\"status\":\"error\",\"reason\":\"no_active_game\"}", 
                 cmd_id.c_str());
    }
  }
}
```

#### 1.4: Helper Function for Simple JSON Parsing
```cpp
String extractJsonValue(String json, String key) {
  String searchKey = "\"" + key + "\":\"";
  int startIdx = json.indexOf(searchKey);
  if (startIdx < 0) {
    // Try numeric value (no quotes)
    searchKey = "\"" + key + "\":";
    startIdx = json.indexOf(searchKey);
    if (startIdx < 0) return "";
    startIdx += searchKey.length();
    int endIdx = json.indexOf(',', startIdx);
    if (endIdx < 0) endIdx = json.indexOf('}', startIdx);
    return json.substring(startIdx, endIdx);
  }
  
  startIdx += searchKey.length();
  int endIdx = json.indexOf('\"', startIdx);
  return json.substring(startIdx, endIdx);
}
```

**Verification:**
- Send `{"cmd":"start","cmd_id":"test-1","t":123,"player_id":"guest"}\n` via serial monitor
- Expect game to start + ACK response
- Verify 'r', 's', 'b' still work

---

### PHASE 2: SERIAL GATEWAY - COMMAND OPTIMIZATION

**Current Issues:**
- Command processing happens inside 1-second serial read timeout loop
- No dedicated command transmission thread
- Command queue exists but processing is delayed

**Required Changes:**

#### 2.1: Add Dedicated Command Worker Thread
```python
def __init__(self):
    # ... existing init ...
    self.command_thread = None
    
def command_worker_loop(self):
    """Dedicated thread for immediate command transmission."""
    print("[Command] Worker thread started")
    
    while self.running:
        try:
            # Block with timeout for clean shutdown
            command_data = self.command_queue.get(timeout=0.5)
            
            if command_data:
                # Generate cmd_id for acknowledgment tracking
                cmd_id = f"{command_data['command']}-{command_data['timestamp']}"
                
                # Build serial command with cmd_id
                serial_cmd = {
                    "cmd": command_data['command'],
                    "cmd_id": cmd_id,
                    "t": command_data['timestamp']
                }
                
                if command_data.get('player_id'):
                    serial_cmd['player_id'] = command_data['player_id']
                
                # Send immediately
                if self.serial_port and self.serial_port.is_open:
                    cmd_json = json.dumps(serial_cmd) + "\n"
                    self.serial_port.write(cmd_json.encode('utf-8'))
                    print(f"[Command] Sent: {cmd_json.strip()}")
                    
                    # Track for acknowledgment
                    self.pending_commands[cmd_id] = {
                        "sent_at": time.time(),
                        "timeout": self.command_timeout_seconds,
                        "command": command_data,
                        "request_id": command_data['request_id']
                    }
                else:
                    self.publish_command_ack(
                        command_data['request_id'],
                        command_data['command'],
                        "error",
                        "Serial port not connected"
                    )
                    
        except queue.Empty:
            continue
        except Exception as e:
            print(f"[Command] Worker error: {e}")
    
    print("[Command] Worker thread stopped")
```

#### 2.2: Start Command Thread in run()
```python
def run(self):
    # ... after MQTT and Serial connect ...
    
    # Start command worker thread
    self.command_thread = threading.Thread(target=self.command_worker_loop, daemon=True)
    self.command_thread.start()
    
    # ... rest of run() ...
```

#### 2.3: Update read_serial_loop() to Remove Command Processing
```python
def read_serial_loop(self):
    while self.running:
        # ... serial reading logic ...
        
        # REMOVED: command queue processing (now in dedicated thread)
        # KEEP: check_command_timeouts()
        
        self.check_command_timeouts()
        time.sleep(0.01)
```

**Verification:**
- Send command via MQTT
- Measure time from MQTT receipt to serial transmission
- Target: <10ms latency

---

### PHASE 3: DASHBOARD UI - IMMEDIATE RESPONSIVENESS

**Current Issues:**
- No click debouncing on START/FINISH buttons
- State transitions happen on command send, not on actual events
- No timeout handling for failed commands

**Required Changes:**

#### 3.1: Add Click Lock and Immediate UI Feedback
```javascript
let commandClickLock = false;

async function handleStartGame() {
    if (commandClickLock || pendingCommand) {
        console.log('[GameControl] Duplicate click ignored');
        return;
    }
    
    // Immediate click lock
    commandClickLock = true;
    
    // Immediate UI update
    updateGameControls('STARTING');
    
    try {
        const response = await fetch(`${API_BASE}/game/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                device_id: 'aquabuzz-001',
                player_id: 'guest'
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to start game');
        }
        
        const result = await response.json();
        
        // Track pending command
        pendingCommand = {
            request_id: result.request_id,
            command: 'start',
            timestamp: Date.now()
        };
        
        // Set timeout
        setTimeout(() => checkCommandTimeout(), 7000);
        
    } catch (error) {
        updateGameControls('ERROR', { error: error.message });
        showAlert(`Failed to start game: ${error.message}`, 'error');
    } finally {
        // Release click lock after a delay
        setTimeout(() => { commandClickLock = false; }, 500);
    }
}
```

#### 3.2: Fix State Synchronization
```javascript
function handleCommandAck(event) {
    // event = {event: "command_ack", request_id, command, status, device_id}
    
    if (!pendingCommand || pendingCommand.request_id !== event.request_id) {
        return;  // Not our command
    }
    
    console.log(`[GameControl] ACK received: ${event.status} for ${event.command}`);
    
    if (event.status === 'ok') {
        // Command successful, but don't transition yet
        // Wait for actual run_start/run_finish event
        console.log('[GameControl] Waiting for game event...');
    } else {
        // Command failed
        updateGameControls('ERROR', { 
            error: `Command ${event.command} ${event.status}` 
        });
        showAlert(`Command failed: ${event.status}`, 'error');
        pendingCommand = null;
    }
}

function syncGameControlWithActiveRun() {
    // DON'T query backend /api/game/status here
    // Use SSE event-driven state only
    
    if (activeRunUid) {
        // Game is running
        if (gameControlState !== 'RUNNING' && gameControlState !== 'FINISHING') {
            updateGameControls('RUNNING', { startTime: Date.now() });
        }
    } else {
        // No active game
        if (gameControlState === 'RUNNING' || gameControlState === 'STARTING') {
            updateGameControls('FINISHED');
        } else if (gameControlState !== 'FINISHED') {
            updateGameControls('WAITING');
        }
    }
}
```

**Verification:**
- Click START rapidly 5 times
- Verify only 1 command is sent
- Verify UI shows STARTING immediately
- Verify UI transitions to RUNNING on run_start event (not on command ACK)

---

### PHASE 4: BACKEND API - VALIDATION & ERROR HANDLING

**Current State:** Endpoints exist but need request validation

**Required Changes:**

#### 4.1: Add Pydantic Request Models
```python
from pydantic import BaseModel, Field

class StartGameRequest(BaseModel):
    device_id: str = Field(default="aquabuzz-001", min_length=1)
    player_id: str = Field(default="guest", min_length=1)

class FinishGameRequest(BaseModel):
    device_id: str = Field(default="aquabuzz-001", min_length=1)
```

#### 4.2: Update Endpoints to Use Models
```python
@app.post("/api/game/start")
async def start_game(
    request: StartGameRequest,
    db: Session = Depends(get_db)
):
    device_id = request.device_id
    player_id = request.player_id
    
    # ... rest of logic unchanged ...
```

**Verification:**
- Send invalid JSON → verify 422 error
- Send valid request → verify command created

---

### PHASE 5: INTEGRATION TESTING

**Test Matrix:**

| Test | Action | Expected Result | Physical HW? |
|------|--------|----------------|--------------|
| T1 | Click START on dashboard | ESP32 starts game, dashboard shows RUNNING | YES |
| T2 | Click FINISH during game | ESP32 finishes game with correct score, dashboard shows FINISHED | YES |
| T3 | Touch maze physically | Physical game starts normally | YES |
| T4 | Touch finish physically | Physical finish works normally with correct scoring | YES |
| T5 | Click START twice rapidly | Only 1 command sent, 2nd click ignored | NO |
| T6 | Click FINISH with no game | ESP32 rejects with "no_active_game" | YES |
| T7 | Disconnect ESP32, click START | Dashboard shows error after timeout | NO |
| T8 | Reconnect ESP32 | New commands work | YES |
| T9 | Send 'r', 's', 'b' via serial | Legacy commands still work | YES |

---

## IMPLEMENTATION ORDER

**Day 1: Firmware (3-4 hours)**
1. Implement JSON command buffer
2. Implement JSON parser helper
3. Implement START handler
4. Implement FINISH handler
5. Test with serial monitor

**Day 2: Gateway & Dashboard (2-3 hours)**
1. Add dedicated command worker thread
2. Update dashboard click handlers
3. Fix state synchronization
4. Test command flow without hardware

**Day 3: Integration Testing (2-3 hours)**
1. Full system test with physical ESP32
2. Verify all test cases
3. Document any remaining issues

---

## SUCCESS CRITERIA

✅ Dashboard START button triggers actual ESP32 game start  
✅ Dashboard FINISH button triggers actual ESP32 game finish  
✅ ESP32 sends command acknowledgments  
✅ Dashboard shows correct state based on actual events  
✅ Physical maze controls still work normally  
✅ Existing scoring and hit tracking unchanged  
✅ Duplicate command protection works  
✅ Error handling and timeouts work  

---

## RISK MITIGATION

**Risk:** Breaking existing physical gameplay  
**Mitigation:** Preserve onMazePressed() and onFinishPressed(), call them from both paths

**Risk:** ArduinoJson library not installed  
**Mitigation:** Implement simple manual JSON parser as fallback

**Risk:** Serial communication reliability  
**Mitigation:** Keep existing reconnection logic, add command timeouts

**Risk:** Dashboard state desynchronization  
**Mitigation:** Use SSE events as source of truth, not API polling

---

## FILES TO MODIFY

1. `firmware/aquabuzz_connected/aquabuzz_connected.ino` - Add JSON parsing
2. `backend/serial_gateway.py` - Add command worker thread
3. `dashboard/index.html` - Fix state sync and click handling
4. `backend/app/main.py` - Add Pydantic models (optional improvement)

**NO CHANGES NEEDED:**
- `backend/app/mqtt_client.py` - Already has ACK subscription
- `backend/app/models.py` - GameCommand model already exists
- Pin assignments, scoring formula, MQTT topics - All preserved
