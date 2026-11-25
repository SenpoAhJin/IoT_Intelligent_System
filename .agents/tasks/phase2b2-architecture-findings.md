# AQUABUZZ PHASE 2B-2 ARCHITECTURE FINDINGS

**Investigation Date:** 2024-12-21  
**Investigator:** Architecture Planning Agent  
**Scope:** Dashboard-controlled game lifecycle integration preparation

---

## EXECUTIVE SUMMARY

This document presents comprehensive findings from investigating the current AquaBuzz system architecture to inform Phase 2B-2 implementation: dashboard-controlled game lifecycle. The investigation reveals a **hardware-triggered, event-driven architecture** with mature MQTT messaging, SSE-based real-time updates, and idempotent database event processing.

**Key Findings:**
- ✅ Robust serial-to-MQTT gateway with event normalization
- ✅ Idempotent event processing with duplicate protection
- ✅ Working SSE infrastructure for real-time updates
- ✅ Game Control UI prepared but not integrated (Phase 2A complete)
- ⚠️ **NO existing command protocol** for dashboard → ESP32 communication
- ⚠️ Current firmware uses **hardware triggers only** (maze touch starts game)
- ⚠️ Serial Gateway has **read-only architecture** (no command sending capability)

**Critical Constraint:** ESP32 firmware modification is **explicitly prohibited** in this phase. All preparation must be non-invasive and backward-compatible.

---

## 1. CURRENT GAME LIFECYCLE ARCHITECTURE

### 1.1 Run Start Mechanism (Hardware-Triggered)

**Current Flow:**
```
Ring touches maze wire → ESP32 detects contact → Game starts immediately
```

**ESP32 Firmware (aquabuzz_connected.ino):**
```cpp
void onMazePressed() {
    unsigned long now = millis();
    
    if (state == WAITING) {
        if (now >= finishLockoutUntil) {
            runNo++;
            runUid = String(DEVICE_ID) + "-" + String(bootCount) + "-" + String(runNo);
            runStartMs = now;
            runEndMs = 0;
            hitCount = 0;
            state = RUNNING;
            finishReleased = !finishPressed;
            
            // Serial output with timestamp
            queuePrint("{\"run\":%d,\"event\":\"run_start\",\"t_ms\":0,\"esp32_ts_ms\":%lu}", 
                       runNo, now);
        }
    }
    // Subsequent touches counted as hits...
}
```

**Key Properties:**
- State machine: `WAITING → RUNNING → FINISHED`
- Run UID format: `{device_id}-{boot_count}-{run_no}`
- **First maze touch starts timer** (not counted as hit)
- 5-second lockout after finish prevents immediate restart
- State changes are **entirely internal** to ESP32

**Serial Gateway Processing:**
```python
def normalize_event(self, raw_event: dict) -> Optional[dict]:
    event_type = raw_event.get("event")
    
    if event_type == "run_start":
        run_uid = self.generate_run_uid(run_no)
        self.current_run_state = {
            "run_uid": run_uid,
            "run_no": run_no,
            "player_id": self.player_id,
            "device_id": self.device_id
        }
        # Adds device_id, player_id, run_uid to event
        # Publishes to MQTT: aquabuzz/{device_id}/events
```

**Backend Processing (main.py handle_mqtt_event):**
```python
if event_type == "run_start":
    # Idempotent: only create if doesn't exist
    run = db.query(Run).filter(Run.run_uid == run_uid).first()
    if not run:
        run = Run(
            run_uid=run_uid,
            device_id=device_id,
            player_id=player_id,
            run_no=event.get("run_no", 0),
            started_at=datetime.utcnow(),
            status="started"
        )
        db.add(run)
        db.commit()
        # Broadcasts SSE event to dashboard
```

**Dashboard Response:**
```javascript
function handleLiveEvent(event) {
    if (eventType === 'run_start') {
        activeRunUid = runUid;
        displayedRunUid = runUid;
        loadData();  // Refresh all data
    }
}
```

**Integration Points Identified:**
- ❌ No external command input capability in firmware
- ❌ No "start game" API endpoint exists
- ❌ Serial Gateway has no command transmission function
- ✅ Event flow well-established and reliable

---

### 1.2 Run Finish Mechanism (Hardware-Triggered)

**Current Flow:**
```
Ring touches finish pad → ESP32 calculates stats → Publishes run_finish → Backend saves
```

**ESP32 Firmware:**
```cpp
void onFinishPressed() {
    if (state == RUNNING) {
        unsigned long now = millis();
        
        // CRITICAL: Close active hit before calculating stats
        if (currentHitStartMs > 0) {
            unsigned long duration = now - currentHitStartMs;
            hits[hitCount - 1].durationMs = duration;
            queuePrint("{\"run\":%d,\"event\":\"hit_end\",...}", ...);
            currentHitStartMs = 0;
        }
        
        runEndMs = now;
        state = FINISHED;
        finishLockoutUntil = now + LOCKOUT_MS;
        
        // Calculate aggregate stats
        unsigned long totalTimeMs = runEndMs - runStartMs;
        unsigned long totalContactMs = 0;
        unsigned long longestHitMs = 0;
        
        for (int i = 0; i < hitCount; i++) {
            totalContactMs += hits[i].durationMs;
            if (hits[i].durationMs > longestHitMs) {
                longestHitMs = hits[i].durationMs;
            }
        }
        
        // Apply difficulty settings
        int scoredHits = max(0, hitCount - freeHits);
        unsigned long score = totalTimeMs + (scoredHits * hitPenaltyMs);
        
        queuePrint("{\"run\":%d,\"event\":\"run_finish\",\"t_ms\":%lu,\"hits\":%d,"
                   "\"total_contact_ms\":%lu,\"longest_hit_ms\":%lu,\"score\":%lu,...}",
                   runNo, totalTimeMs, hitCount, totalContactMs, longestHitMs, score, now);
        
        delay(100);
        state = WAITING;  // Automatically returns to waiting
    }
}
```

**Backend Processing:**
```python
elif event_type == "run_finish":
    run = db.query(Run).filter(Run.run_uid == run_uid).first()
    if not run:
        print(f"[MQTT] WARNING: run_finish for unknown run {run_uid}")
        return
    
    # Idempotent - only update if not already finished
    if run.status != "finished":
        run.finished_at = datetime.utcnow()
        run.duration_ms = event.get("t_ms", 0)
        
        # CRITICAL FIX: Calculate from Hit records (source of truth)
        hit_records = db.query(Hit).filter(Hit.run_uid == run_uid).all()
        completed_hits = [h for h in hit_records if h.duration_ms > 0]
        
        run.hits = len(completed_hits)
        run.total_contact_ms = sum(h.duration_ms for h in completed_hits)
        run.longest_hit_ms = max((h.duration_ms for h in completed_hits), default=0)
        
        # Recalculate score using actual hit count
        scored_hits = max(0, run.hits - free_hits)
        run.score = run.duration_ms + (scored_hits * run.hit_penalty_ms)
        
        run.status = "finished"
        db.commit()
        
        analyze_run(run, db)  # Trigger intelligence analysis
    
    broadcast_event(event)  # Notify dashboard via SSE
```

**Integration Points Identified:**
- ❌ No external "finish game" command capability
- ✅ Firmware automatically returns to WAITING after finish
- ✅ Backend recalculates statistics from Hit records (robust)
- ⚠️ Firmware aggregates are logged but not trusted

---

### 1.3 Hit Processing Flow

**Hit Start (hit_start):**
```
Ring contacts maze → ESP32 creates Hit record → Serial → Gateway → MQTT → Backend
```

**ESP32:**
```cpp
currentHitStartMs = now;
hitCount++;
hits[hitCount - 1].startMs = now - runStartMs;
hits[hitCount - 1].durationMs = 0;  // Will be set on hit_end

queuePrint("{\"run\":%d,\"event\":\"hit_start\",\"hit\":%d,\"t_ms\":%lu,...}", 
           runNo, hitCount, now - runStartMs);
```

**Backend:**
```python
elif event_type == "hit_start":
    run = db.query(Run).filter(Run.run_uid == run_uid).first()
    if not run:
        return
    
    hit_no = event.get("hit", 0)
    start_ms = event.get("t_ms", 0)
    
    # Idempotent check
    existing = db.query(Hit).filter(
        Hit.run_uid == run_uid, 
        Hit.hit_no == hit_no
    ).first()
    
    if not existing:
        hit = Hit(
            run_uid=run_uid,
            hit_no=hit_no,
            start_ms=start_ms,
            duration_ms=0  # Completed on hit_end
        )
        db.add(hit)
        db.commit()
```

**Hit End (hit_end):**
```cpp
void onMazeReleased() {
    if (state == RUNNING && currentHitStartMs > 0) {
        unsigned long now = millis();
        unsigned long duration = now - currentHitStartMs;
        hits[hitCount - 1].durationMs = duration;
        
        queuePrint("{\"run\":%d,\"event\":\"hit_end\",\"hit\":%d,\"dur_ms\":%lu,...}", 
                   runNo, hitCount, duration);
        
        currentHitStartMs = 0;
    }
}
```

**Backend:**
```python
elif event_type == "hit_end":
    hit = db.query(Hit).filter(
        Hit.run_uid == run_uid, 
        Hit.hit_no == hit_no
    ).first()
    
    if hit:
        if hit.duration_ms == 0:  # Only update if not already set
            hit.duration_ms = event.get("dur_ms", 0)
            db.commit()
    else:
        # Hit start was missed - create complete record
        hit = Hit(...)
        db.add(hit)
        db.commit()
```

**Properties:**
- ✅ Idempotent processing prevents duplicates
- ✅ Database is source of truth (not firmware aggregates)
- ✅ Handles missed events gracefully
- ✅ In-progress hits tracked (duration_ms = 0)

---

## 2. MQTT ARCHITECTURE

### 2.1 Topic Structure

**Device → Backend:**
- `aquabuzz/{device_id}/events` - Game events (QoS 1)
  - `run_start`, `hit_start`, `hit_end`, `run_finish`, `run_cancel`
- `aquabuzz/{device_id}/heartbeat` - Device health (QoS 1, every 10s)

**Backend → Device (Existing but Unused):**
- `aquabuzz/{device_id}/config` - Difficulty settings
- `aquabuzz/{device_id}/player` - Set active player

**Example Event Payload:**
```json
{
  "device_id": "aquabuzz-001",
  "player_id": "guest",
  "run_uid": "aquabuzz-001-1-5",
  "run_no": 5,
  "event": "hit_end",
  "hit": 3,
  "t_ms": 8421,
  "dur_ms": 230,
  "esp32_ts_ms": 1234567890,
  "gateway_rx_ts": 1703174890.123
}
```

**MQTT Client Configuration (backend/app/mqtt_client.py):**
```python
class MQTTEventIngester:
    def __init__(self, broker_host, broker_port, username, password):
        self.client = mqtt.Client(client_id="aquabuzz-backend")
        if username and password:
            self.client.username_pw_set(username, password)
        
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe("aquabuzz/+/events")
            client.subscribe("aquabuzz/+/heartbeat")
    
    def publish(self, topic: str, payload: dict):
        json_payload = json.dumps(payload)
        result = self.client.publish(topic, json_payload, qos=1)
        return result.rc == mqtt.MQTT_ERR_SUCCESS
```

### 2.2 Serial Gateway Architecture

**File:** `backend/serial_gateway.py`

**Current Capabilities:**
- ✅ Auto-detect ESP32 on COM ports (CP210x, CH340)
- ✅ Read serial JSON messages
- ✅ Normalize events (add device_id, player_id, run_uid)
- ✅ Publish to MQTT with QoS 1
- ✅ Session tracking with gateway_session_id
- ✅ Automatic reconnection (serial and MQTT)
- ✅ Background heartbeat publishing (every 10s)
- ✅ Latency measurement (FEAT-002)
- ❌ **NO command transmission capability**

**Key Code Sections:**

**Serial Read Loop:**
```python
def read_serial_loop(self):
    while self.running:
        if self.serial_port.in_waiting:
            line = self.serial_port.readline().decode('utf-8', errors='ignore')
            raw_event = self.parse_line(line)
            
            if raw_event and "event" in raw_event:
                normalized_event = self.normalize_event(raw_event)
                if normalized_event:
                    normalized_event["gateway_rx_ts"] = time.time()
                    self.publish_event(normalized_event)
```

**Event Normalization:**
```python
def normalize_event(self, raw_event: dict) -> Optional[dict]:
    event_type = raw_event.get("event")
    run_no = raw_event.get("run", 0)
    
    if event_type == "run_start":
        run_uid = self.generate_run_uid(run_no)
        self.current_run_state = {
            "run_uid": run_uid,
            "run_no": run_no,
            "player_id": self.player_id,
            "device_id": self.device_id
        }
    
    # Ensure we have an active run for other events
    if event_type in ["hit_start", "hit_end", "run_finish", "run_cancel"]:
        if not self.current_run_state:
            return None  # Ignore orphaned events
    
    # Build normalized event
    normalized = {
        "device_id": self.device_id,
        "player_id": self.player_id,
        "run_uid": self.current_run_state["run_uid"],
        "event": event_type,
        # Copy original fields (t_ms, hits, score, etc.)
    }
    
    return normalized
```

**Command Protocol Gaps:**
- ❌ No `send_command()` method
- ❌ No command queue
- ❌ No acknowledgment handling
- ❌ No timeout mechanism
- ✅ Serial write capability exists (via `serial.Serial.write()`)

---

## 3. BACKEND API ARCHITECTURE

### 3.1 Existing Endpoints

**Health and Status:**
- `GET /api/health` - System health, active runs, devices
- `GET /api/active_run` - Currently active run (browser refresh recovery)

**Data Retrieval:**
- `GET /api/runs?limit=50&player_id=X` - Recent runs
- `GET /api/runs/{run_id}` - Single run with hit details
- `GET /api/players` - All players with stats
- `GET /api/leaderboard?limit=10` - Top scores
- `GET /api/insights/{player_id}` - Intelligence analysis

**Real-time:**
- `GET /api/live` - Server-Sent Events stream

**Configuration (Unused):**
- `POST /api/devices/{device_id}/config` - Push difficulty to device

### 3.2 Event Processing Pipeline

```
MQTT Event → handle_mqtt_event() → Database Transaction → broadcast_event() → SSE Clients
```

**Key Properties:**
```python
def handle_mqtt_event(event: dict):
    backend_rx_ts = time.time()
    
    db = next(get_db())
    try:
        # 1. Ensure device exists
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            device = Device(id=device_id)
            db.add(device)
            db.commit()
        
        # 2. Process event (idempotent)
        if event_type == "run_start":
            run = db.query(Run).filter(Run.run_uid == run_uid).first()
            if not run:  # Only create if new
                run = Run(...)
                db.add(run)
                db.commit()
        
        # 3. Broadcast to SSE clients
        broadcast_event(event)
        
    except Exception as e:
        db.rollback()
    finally:
        db.close()
```

**Idempotency Guarantees:**
- `run_start`: Check if `run_uid` exists before creating
- `hit_start`: Check if `(run_uid, hit_no)` exists
- `hit_end`: Only update if `duration_ms == 0`
- `run_finish`: Only update if `status != "finished"`

### 3.3 SSE Infrastructure (Real-time Updates)

**Endpoint:** `/api/live`

**Implementation (PHASE 2B-1 Fixed):**
```python
@app.get("/api/live")
async def live_events():
    global sse_client_counter
    sse_client_counter += 1
    client_id = sse_client_counter
    
    # AsyncIO queue for this client
    client_queue = asyncio.Queue(maxsize=200)
    client_tuple = (client_id, client_queue)
    sse_clients.append(client_tuple)
    
    async def event_generator():
        event_sequence = 0
        last_keepalive = time.time()
        keepalive_interval = 15
        
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        client_queue.get(),
                        timeout=keepalive_interval
                    )
                    
                    event_sequence += 1
                    event_data = json.dumps(event)
                    
                    yield f"id: {event_sequence}\n"
                    yield f"event: game_event\n"
                    yield f"data: {event_data}\n\n"
                    
                except asyncio.TimeoutError:
                    yield f": keepalive {int(time.time())}\n\n"
        
        finally:
            if client_tuple in sse_clients:
                sse_clients.remove(client_tuple)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
```

**Broadcasting:**
```python
async def broadcast_event_async(event: dict):
    if not sse_clients:
        return
    
    for client_id, client_queue in sse_clients:
        try:
            client_queue.put_nowait(event)  # Non-blocking
        except asyncio.QueueFull:
            print(f"[SSE] Client {client_id} queue full, event dropped")
```

**Dashboard Connection:**
```javascript
function connectSSE() {
    eventSource = new EventSource(`${API_BASE}/live`);
    
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleLiveEvent(data);
    };
    
    eventSource.onerror = (error) => {
        sseConnected = false;
        // Exponential backoff reconnection
        setTimeout(connectSSE, delay);
    };
}
```

**Properties:**
- ✅ Async/await throughout (no blocking)
- ✅ Keep-alive every 15 seconds
- ✅ Graceful client cleanup
- ✅ Event sequence IDs
- ✅ Queue overflow protection
- ✅ Automatic reconnection with backoff

---

## 4. DATABASE SCHEMA

### 4.1 Tables

**Players:**
```python
class Player(Base):
    __tablename__ = "players"
    
    id = Column(String, primary_key=True)  # player_id
    name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**Devices:**
```python
class Device(Base):
    __tablename__ = "devices"
    
    id = Column(String, primary_key=True)  # device_id
    name = Column(String, nullable=True)
    last_heartbeat = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

**Runs:**
```python
class Run(Base):
    __tablename__ = "runs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_uid = Column(String, unique=True, nullable=False, index=True)
    device_id = Column(String, ForeignKey("devices.id"))
    player_id = Column(String, ForeignKey("players.id"))
    run_no = Column(Integer)
    
    # Timing
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    duration_ms = Column(Integer)
    
    # Performance
    hits = Column(Integer, default=0)
    total_contact_ms = Column(Integer, default=0)
    longest_hit_ms = Column(Integer, default=0)
    hit_penalty_ms = Column(Integer, default=2000)
    score = Column(Integer)
    
    # Status: "started", "finished", "cancelled", "abandoned"
    status = Column(String, default="started")
```

**Hits:**
```python
class Hit(Base):
    __tablename__ = "hits"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_uid = Column(String, ForeignKey("runs.run_uid"))
    hit_no = Column(Integer)
    start_ms = Column(Integer)  # ms from run start
    duration_ms = Column(Integer)  # 0 = in progress
```

### 4.2 Transaction Patterns

**Run Lifecycle States:**
```
"started" → "finished"  (normal completion)
"started" → "cancelled" (manual reset)
"started" → "abandoned" (timeout after 30 minutes)
```

**Active Run Detection:**
```python
active_runs = db.query(Run).filter(
    Run.status == "started",
    Run.finished_at.is_(None)
).count()
```

**Stale Run Cleanup:**
```python
def detect_and_mark_stale_runs(db: Session, timeout_minutes: int = 30):
    cutoff = datetime.utcnow() - timedelta(minutes=timeout_minutes)
    stale_runs = db.query(Run).filter(
        Run.status == "started",
        Run.started_at < cutoff,
        Run.finished_at.is_(None)
    ).all()
    
    for run in stale_runs:
        run.status = "abandoned"
    
    db.commit()
```

---

## 5. DASHBOARD ARCHITECTURE

### 5.1 Phase 2A Game Control UI (Prepared, Not Integrated)

**Visual Design:** Complete with 5 states
- WAITING: Yellow "⏸ WAITING", START GAME button enabled
- RUNNING: Green "🔴 RUNNING", live metrics, FINISH GAME button enabled
- FINISHED: Blue "✅ FINISHED", final score, NEW GAME button
- STARTING: "Command pending" (future)
- FINISHING: "Finalization pending" (future)

**Current State:**
```javascript
// PHASE 2A: Game control state (not connected)
let gameControlState = 'WAITING';
let gameControlMetrics = {
    startTime: null,
    elapsedMs: 0,
    hits: 0,
    contactMs: 0,
    longestHitMs: 0,
    finalScore: 0
};
```

**Button Handlers (Stubbed):**
```javascript
function handleStartGame() {
    // PHASE 2A: Do NOT simulate game start
    alert('🚧 Game control integration pending (Phase 2B)');
}

function handleFinishGame() {
    // PHASE 2A: Do NOT simulate game finish
    confirm('⚠️ Game control integration pending (Phase 2B)');
}
```

**Integration Notice Displayed:**
```
⚙️ Dashboard Controls Prepared
ESP32 command integration pending (Phase 2B)
Current system uses existing hardware-triggered game lifecycle
```

### 5.2 Active Run Tracking (Existing)

**Browser Refresh Recovery:**
```javascript
async function recoverActiveRunAfterRefresh() {
    const res = await fetch(`${API_BASE}/active_run`);
    const data = await res.json();
    
    if (data.active && data.run_uid) {
        activeRunUid = data.run_uid;
        displayedRunUid = data.run_uid;
        await loadRunDetails(data.run_id);
        return true;
    }
    return false;
}
```

**SSE Event Handling:**
```javascript
function handleLiveEvent(event) {
    if (event.event === 'run_start') {
        activeRunUid = event.run_uid;
        displayedRunUid = event.run_uid;
    } else if (event.event === 'run_finish' || event.event === 'run_cancel') {
        activeRunUid = null;
        // displayedRunUid persists to show completed game
    }
    
    loadData();  // Refresh all data
}
```

**Display Priority Logic:**
```javascript
// Priority 1: Active game (in progress)
// Priority 2: Previously displayed game (after finish)
// Priority 3: Latest finished game (fallback)
```

### 5.3 Polling and Real-time Updates

**Adaptive Polling:**
```javascript
let pollInterval = 3000;  // 3s idle, 1s during active games

function updatePollRate() {
    const newInterval = (activeRuns > 0) ? 1000 : 3000;
    if (newInterval !== pollInterval) {
        pollInterval = newInterval;
        clearInterval(intervalId);
        intervalId = setInterval(loadData, pollInterval);
    }
}
```

**SSE Connection:**
```javascript
function connectSSE() {
    eventSource = new EventSource(`${API_BASE}/live`);
    
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleLiveEvent(data);
    };
    
    eventSource.onerror = () => {
        sseReconnectAttempts++;
        if (sseReconnectAttempts >= 5) {
            useSseUpdates = false;  // Fallback to polling only
        } else {
            setTimeout(connectSSE, delay);  // Exponential backoff
        }
    };
}
```

---

## 6. ESP32 FIRMWARE CONSTRAINTS (READ-ONLY ANALYSIS)

### 6.1 Current State Machine

```cpp
enum GameState {
  WAITING,
  RUNNING,
  FINISHED
};

GameState state = WAITING;
```

**State Transitions:**
```
WAITING → RUNNING:   onMazePressed() [first touch, lockout expired]
RUNNING → FINISHED:  onFinishPressed() [finish pad touched]
FINISHED → WAITING:  Automatic after delay(100) in onFinishPressed()
```

**Lockout Mechanism:**
```cpp
unsigned long finishLockoutUntil = 0;
const unsigned long LOCKOUT_MS = 5000;

// In onMazePressed():
if (now >= finishLockoutUntil) {
    // Start new game
}
```

### 6.2 Serial Command Handling (Minimal)

**Existing Commands:**
```cpp
void handleSerialCommand() {
    if (Serial.available()) {
        char cmd = Serial.read();
        
        if (cmd == 'r') {        // Reset
            if (state == RUNNING) {
                queuePrint("{\"run\":%d,\"event\":\"run_cancel\",\"t_ms\":%lu}", ...);
                runNo++;
            }
            state = WAITING;
            // Reset all state variables
        } 
        else if (cmd == 's') {   // Summary
            queuePrint("{\"info\":\"summary\",\"run\":%d,\"state\":...}", ...);
        } 
        else if (cmd == 'b') {   // Buzzer test
            // Two beeps
        }
    }
}
```

**Properties:**
- ✅ Single-character commands
- ✅ Non-blocking (Serial.available() check)
- ✅ Called every loop iteration
- ⚠️ **NO multi-byte command protocol**
- ⚠️ **NO JSON command parsing**
- ⚠️ **NO acknowledgment mechanism**

### 6.3 Serial Output Format

**All events use JSON over serial:**
```cpp
queuePrint("{\"run\":%d,\"event\":\"run_start\",\"t_ms\":0,\"esp32_ts_ms\":%lu}", ...);
```

**Queue-based Output (FreeRTOS):**
```cpp
QueueHandle_t serialQueue;
void serialTask(void *parameter) {
    SerialMessage msg;
    for (;;) {
        if (xQueueReceive(serialQueue, &msg, portMAX_DELAY)) {
            Serial.println(msg.text);
        }
    }
}
```

**Properties:**
- ✅ Non-blocking serial output
- ✅ Prevents loop() stalls
- ✅ FIFO ordering guaranteed
- ✅ 50-message queue depth

### 6.4 MQTT Callback (Unused for Commands)

```cpp
void mqttCallback(char* topic, byte* payload, unsigned int length) {
    String topicStr = String(topic);
    String payloadStr = "";
    for (unsigned int i = 0; i < length; i++) {
        payloadStr += (char)payload[i];
    }
    
    queuePrint("{\"mqtt_rx\":\"%s\"}", topicStr.c_str());
    
    // Handle config updates
    if (topicStr.endsWith("/config")) {
        // Simple JSON parsing (not implemented)
        queuePrint("{\"info\":\"config_received\"}");
    } 
    else if (topicStr.endsWith("/player")) {
        playerId = payloadStr;
        queuePrint("{\"player\":\"%s\"}", playerId.c_str());
    }
}
```

**Properties:**
- ✅ MQTT subscription active
- ⚠️ Config parsing not implemented
- ⚠️ No game control commands handled
- ⚠️ Player ID update works (simple string)

---

## 7. INTEGRATION POINTS FOR PHASE 2B-2

### 7.1 Dashboard → Backend (NEW)

**Required Endpoints:**

**POST /api/game/start**
```python
@app.post("/api/game/start")
async def start_game(device_id: str = "aquabuzz-001", player_id: str = "guest"):
    """
    Request game start via dashboard.
    Backend sends command to Serial Gateway → ESP32.
    """
    # 1. Validate no active game on this device
    # 2. Create command request
    # 3. Send to Serial Gateway
    # 4. Return pending status
    # 5. Await confirmation event from ESP32
```

**POST /api/game/finish**
```python
@app.post("/api/game/finish")
async def finish_game(run_uid: str):
    """
    Request game finish via dashboard.
    Backend sends command to Serial Gateway → ESP32.
    """
    # 1. Validate run_uid is active
    # 2. Create finish command
    # 3. Send to Serial Gateway
    # 4. Return pending status
    # 5. Await run_finish event from ESP32
```

**GET /api/game/status**
```python
@app.get("/api/game/status")
async def game_status():
    """
    Get current game command state.
    Returns pending commands, timeouts, errors.
    """
```

### 7.2 Backend → Serial Gateway (NEW)

**Command Transport Options:**

**Option A: HTTP API on Serial Gateway**
```python
# Add Flask/FastAPI endpoint to serial_gateway.py
@app.post("/command/start")
async def command_start(device_id: str):
    # Queue command for transmission
    # Return immediately (async)
```

**Option B: Shared Queue/Database**
```python
# Backend writes to commands table
# Serial Gateway polls and processes
```

**Option C: MQTT Command Topic (Recommended)**
```python
# Backend publishes to: aquabuzz/commands/{device_id}
# Serial Gateway subscribes and forwards to serial
```

**Recommended: Option C (MQTT Command Topic)**
- ✅ Consistent with existing MQTT architecture
- ✅ No new HTTP dependencies
- ✅ Natural pub/sub pattern
- ✅ Serial Gateway already has MQTT client

### 7.3 Serial Gateway → ESP32 (NEW)

**Command Protocol Proposal:**

**Serial Message Format:**
```json
{"cmd":"start","t":1703174890}
{"cmd":"finish","t":1703174920}
{"cmd":"ack","cmd_id":"start-1703174890","status":"ok"}
```

**Serial Gateway Changes Required:**
```python
class SerialGateway:
    def __init__(self):
        # Add command queue
        self.command_queue = queue.Queue()
        self.pending_commands = {}  # cmd_id → timeout
    
    def send_command(self, command: dict):
        """Send command to ESP32 via serial."""
        cmd_json = json.dumps(command) + "\n"
        self.serial_port.write(cmd_json.encode('utf-8'))
        
        # Track for acknowledgment
        cmd_id = f"{command['cmd']}-{command['t']}"
        self.pending_commands[cmd_id] = {
            "sent_at": time.time(),
            "timeout": 5.0,
            "command": command
        }
    
    def handle_acknowledgment(self, ack_data: dict):
        """Process acknowledgment from ESP32."""
        cmd_id = ack_data.get("cmd_id")
        if cmd_id in self.pending_commands:
            del self.pending_commands[cmd_id]
            # Publish success to MQTT
    
    def check_timeouts(self):
        """Detect command timeouts."""
        now = time.time()
        for cmd_id, cmd_info in list(self.pending_commands.items()):
            if now - cmd_info["sent_at"] > cmd_info["timeout"]:
                # Publish timeout event to MQTT
                del self.pending_commands[cmd_id]
```

### 7.4 ESP32 Firmware (PHASE 3 - Future)

**Command Handler (Future Implementation):**
```cpp
void handleSerialCommand() {
    if (Serial.available()) {
        String line = Serial.readStringUntil('\n');
        
        // Try JSON parsing (requires ArduinoJson library)
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
        // Cannot start (already running or in lockout)
        queuePrint("{\"cmd\":\"ack\",\"cmd_id\":\"start-%ld\",\"status\":\"error\","
                   "\"reason\":\"invalid_state\"}", timestamp);
    }
}

void handleDashboardFinish(long timestamp) {
    if (state == RUNNING) {
        // Force finish (same as onFinishPressed())
        // Close active hit, calculate stats, publish run_finish
        
        // Acknowledge
        queuePrint("{\"cmd\":\"ack\",\"cmd_id\":\"finish-%ld\",\"status\":\"ok\"}", timestamp);
    } else {
        queuePrint("{\"cmd\":\"ack\",\"cmd_id\":\"finish-%ld\",\"status\":\"error\","
                   "\"reason\":\"not_running\"}", timestamp);
    }
}
```

---

## 8. COMMAND PROTOCOL PROPOSAL

### 8.1 Protocol Requirements

**Functional:**
- ✅ Start game without maze touch
- ✅ Finish game without finish pad touch
- ✅ Acknowledgment/rejection with reason
- ✅ Timeout detection (5 seconds)
- ✅ Idempotent commands
- ✅ Invalid state handling

**Non-functional:**
- ✅ Backward compatible (existing firmware ignores unknown commands)
- ✅ Non-blocking (queue-based)
- ✅ Reliable (acknowledgment required)
- ✅ Debuggable (JSON format)
- ✅ Low latency (< 100ms typical)

### 8.2 Command Flow Diagram

```
Dashboard         Backend          Serial Gateway     ESP32
   |                |                   |               |
   |-- POST /game/start -------------->|               |
   |                |                   |               |
   |                |-- MQTT: cmd/start->               |
   |                |                   |               |
   |                |                   |-- Serial: {"cmd":"start"}-->
   |                |                   |               |
   |                |                   |<-- Serial: {"cmd":"ack","status":"ok"}--
   |                |                   |               |
   |                |<-- MQTT: ack/start-|               |
   |                |                   |               |
   |                |                   |<-- Serial: {"event":"run_start"}--------
   |                |                   |               |
   |                |<-- MQTT: events --|               |
   |                |                   |               |
   |<-- SSE: run_start ----------------|               |
   |                |                   |               |
```

### 8.3 Message Formats

**Dashboard → Backend:**
```http
POST /api/game/start
Content-Type: application/json

{
  "device_id": "aquabuzz-001",
  "player_id": "alice"
}
```

**Backend → Serial Gateway (MQTT):**
```
Topic: aquabuzz/commands/aquabuzz-001
Payload: {
  "command": "start",
  "timestamp": 1703174890,
  "player_id": "alice",
  "request_id": "req-12345"
}
```

**Serial Gateway → ESP32 (Serial):**
```
{"cmd":"start","t":1703174890}\n
```

**ESP32 → Serial Gateway (Serial):**
```
{"cmd":"ack","cmd_id":"start-1703174890","status":"ok"}\n
{"run":1,"event":"run_start","t_ms":0,"esp32_ts_ms":1234567890}\n
```

**Serial Gateway → Backend (MQTT):**
```
Topic: aquabuzz/aquabuzz-001/ack
Payload: {
  "command": "start",
  "request_id": "req-12345",
  "status": "ok",
  "timestamp": 1703174890
}

Topic: aquabuzz/aquabuzz-001/events
Payload: {
  "device_id": "aquabuzz-001",
  "player_id": "alice",
  "run_uid": "aquabuzz-001-1-1",
  "event": "run_start",
  ...
}
```

**Backend → Dashboard (SSE):**
```
event: game_event
data: {"event":"run_start","run_uid":"aquabuzz-001-1-1",...}
```

### 8.4 Error Handling

**Timeout Scenario:**
```
1. Backend sends command to Serial Gateway (via MQTT)
2. Serial Gateway forwards to ESP32 (via Serial)
3. Wait 5 seconds for acknowledgment
4. If no ACK received:
   - Serial Gateway publishes timeout event to MQTT
   - Backend marks command as failed
   - Dashboard shows error: "Command timeout - ESP32 not responding"
```

**Invalid State Scenario:**
```
1. User clicks START GAME while game already running
2. Backend checks active_run endpoint
3. If active game exists, reject immediately (no command sent)
4. Dashboard shows: "Game already in progress"
```

**Duplicate Command Protection:**
```
1. Backend tracks pending commands by device_id
2. If command already pending for device, reject new request
3. Dashboard disables button until command completes or times out
```

**Disconnected Hardware:**
```
1. Serial Gateway detects serial disconnection
2. Publishes device offline status to MQTT
3. Backend marks device as offline
4. Dashboard disables game control buttons
5. Shows: "ESP32 disconnected - reconnect hardware"
```

---

## 9. DATABASE TRANSACTION PATTERNS

### 9.1 Command State Tracking (New Table Required)

**Proposed Schema:**
```python
class GameCommand(Base):
    __tablename__ = "game_commands"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String, unique=True, nullable=False, index=True)
    device_id = Column(String, ForeignKey("devices.id"), nullable=False)
    command = Column(String, nullable=False)  # "start", "finish"
    
    # Command lifecycle
    requested_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    
    # Status: "pending", "sent", "acknowledged", "timeout", "rejected"
    status = Column(String, default="pending")
    
    # Metadata
    player_id = Column(String, nullable=True)
    run_uid = Column(String, nullable=True)  # Set after run_start event
    error_reason = Column(String, nullable=True)
```

### 9.2 Command Lifecycle States

```
"pending" → "sent" → "acknowledged" (success)
"pending" → "sent" → "timeout" (failure)
"pending" → "rejected" (invalid state)
```

### 9.3 Transaction Patterns

**Create Command:**
```python
@app.post("/api/game/start")
async def start_game(device_id: str, player_id: str, db: Session = Depends(get_db)):
    # 1. Check for active game
    active_run = db.query(Run).filter(
        Run.device_id == device_id,
        Run.status == "started"
    ).first()
    
    if active_run:
        raise HTTPException(400, "Game already in progress")
    
    # 2. Check for pending commands
    pending_cmd = db.query(GameCommand).filter(
        GameCommand.device_id == device_id,
        GameCommand.status.in_(["pending", "sent"])
    ).first()
    
    if pending_cmd:
        raise HTTPException(409, "Command already pending")
    
    # 3. Create command record
    request_id = f"req-{uuid.uuid4().hex[:8]}"
    cmd = GameCommand(
        request_id=request_id,
        device_id=device_id,
        command="start",
        player_id=player_id,
        status="pending"
    )
    db.add(cmd)
    db.commit()
    
    # 4. Publish to MQTT
    mqtt_client.publish(f"aquabuzz/commands/{device_id}", {
        "command": "start",
        "request_id": request_id,
        "player_id": player_id,
        "timestamp": int(time.time())
    })
    
    # 5. Update status
    cmd.status = "sent"
    cmd.sent_at = datetime.utcnow()
    db.commit()
    
    return {"request_id": request_id, "status": "sent"}
```

**Handle Acknowledgment:**
```python
def handle_command_ack(ack_event: dict, db: Session):
    request_id = ack_event.get("request_id")
    status = ack_event.get("status")  # "ok" or "error"
    
    cmd = db.query(GameCommand).filter(
        GameCommand.request_id == request_id
    ).first()
    
    if not cmd:
        return
    
    if status == "ok":
        cmd.status = "acknowledged"
        cmd.acknowledged_at = datetime.utcnow()
    else:
        cmd.status = "rejected"
        cmd.error_reason = ack_event.get("reason", "Unknown error")
    
    db.commit()
```

**Timeout Detection:**
```python
def detect_command_timeouts(db: Session, timeout_seconds: int = 5):
    cutoff = datetime.utcnow() - timedelta(seconds=timeout_seconds)
    
    timed_out_commands = db.query(GameCommand).filter(
        GameCommand.status == "sent",
        GameCommand.sent_at < cutoff,
        GameCommand.acknowledged_at.is_(None)
    ).all()
    
    for cmd in timed_out_commands:
        cmd.status = "timeout"
        cmd.error_reason = f"No acknowledgment received within {timeout_seconds}s"
    
    db.commit()
    
    return len(timed_out_commands)
```

---

## 10. TESTING REQUIREMENTS

### 10.1 Existing Test Infrastructure

**Location:** `backend/tests/`

**Existing Tests:**
- `test_features.py` - Feature extraction
- `test_behavior.py` - Behavior analysis
- `test_classifier.py` - Skill classification
- `test_difficulty.py` - Difficulty recommendation
- `test_anomalies.py` - Anomaly detection
- `test_repairs.py` - System repairs (Phase 1.3)
- `test_sse_reliability.py` - SSE connection reliability

**Test Framework:** pytest

**Example Pattern:**
```python
import pytest
from app.db import get_db, init_db
from app.models import Run, Hit

@pytest.fixture
def db_session():
    init_db()
    db = next(get_db())
    yield db
    db.close()

def test_idempotent_run_start(db_session):
    # Test that duplicate run_start events don't create duplicate runs
    pass
```

### 10.2 Required New Tests

**Unit Tests:**

**test_game_commands.py:**
```python
def test_start_game_command_creation()
def test_start_game_duplicate_rejection()
def test_start_game_while_active_rejection()
def test_finish_game_command_creation()
def test_finish_game_without_active_rejection()
def test_command_acknowledgment_handling()
def test_command_timeout_detection()
def test_command_error_handling()
```

**test_serial_gateway_commands.py:**
```python
def test_send_command_to_serial()
def test_receive_acknowledgment()
def test_command_timeout_detection()
def test_mqtt_command_subscription()
def test_duplicate_command_prevention()
```

**test_dashboard_game_controls.py:**
```python
def test_start_button_state_transitions()
def test_finish_button_state_transitions()
def test_command_pending_ui_state()
def test_command_error_ui_state()
def test_browser_refresh_recovery()
```

**Integration Tests (Requires Hardware):**

**test_e2e_dashboard_start.py:**
```python
def test_dashboard_start_to_esp32_start()
def test_dashboard_start_acknowledgment()
def test_dashboard_start_timeout()
def test_dashboard_start_during_active_game()
```

**test_e2e_dashboard_finish.py:**
```python
def test_dashboard_finish_to_esp32_finish()
def test_dashboard_finish_acknowledgment()
def test_dashboard_finish_timeout()
def test_dashboard_finish_without_active_game()
```

### 10.3 Manual Testing Checklist

**Dashboard Control Flow:**
1. [ ] START GAME button enabled when WAITING
2. [ ] START GAME sends command to backend
3. [ ] Backend creates command record
4. [ ] Backend publishes to MQTT commands topic
5. [ ] Serial Gateway receives MQTT command
6. [ ] Serial Gateway forwards to ESP32 via serial
7. [ ] ESP32 acknowledges command
8. [ ] Serial Gateway publishes acknowledgment to MQTT
9. [ ] Backend updates command status
10. [ ] ESP32 starts game and publishes run_start
11. [ ] Backend creates Run record
12. [ ] Backend broadcasts run_start via SSE
13. [ ] Dashboard updates to RUNNING state
14. [ ] FINISH GAME button now enabled
15. [ ] Live metrics update during game
16. [ ] FINISH GAME sends command
17. [ ] ESP32 finishes game and publishes run_finish
18. [ ] Dashboard updates to FINISHED state
19. [ ] Final score displayed
20. [ ] NEW GAME button enabled

**Error Scenarios:**
1. [ ] START GAME while game already running → Error message
2. [ ] FINISH GAME while no game running → Error message
3. [ ] Command timeout (ESP32 disconnected) → Timeout message
4. [ ] Duplicate command prevention
5. [ ] Browser refresh during active game → State recovery
6. [ ] Serial disconnection → Buttons disabled
7. [ ] MQTT disconnection → Error handling
8. [ ] Invalid state transitions rejected

---

## 11. CONSTRAINTS AND RISKS

### 11.1 Explicit Constraints

**From User Requirements:**
1. ✅ **NO ESP32 firmware modification in this phase**
2. ✅ **NO firmware upload in this phase**
3. ✅ **ALL existing functionality must remain operational**
4. ✅ **NO breaking changes to working system**
5. ✅ **Backward compatibility required**

**Technical Constraints:**
1. ESP32 firmware has minimal command parsing (single-char only)
2. Serial Gateway currently read-only architecture
3. No existing command acknowledgment protocol
4. MQTT subscriptions need expansion
5. Dashboard UI prepared but not connected

### 11.2 Risk Assessment

**High Risk:**
- **Serial Gateway command sending** - Architecture change required
  - Mitigation: Preserve existing read loop, add parallel command sender
  - Fallback: Queue-based with retry logic

- **Command timeout handling** - New failure mode
  - Mitigation: 5-second timeout, clear error messages
  - Fallback: User can retry; existing hardware controls still work

**Medium Risk:**
- **Database schema changes** - GameCommand table
  - Mitigation: SQLAlchemy migrations
  - Fallback: Use existing Run table with status="pending"

- **MQTT topic expansion** - New command topics
  - Mitigation: Separate namespaces (aquabuzz/commands/*)
  - Fallback: Existing event topics unaffected

**Low Risk:**
- **Backend API endpoints** - New routes
  - Mitigation: Standard FastAPI patterns
  - Fallback: Existing endpoints unchanged

- **Dashboard UI** - Already prepared in Phase 2A
  - Mitigation: Connect existing handlers
  - Fallback: Display integration notice

### 11.3 Rollback Strategy

**If Phase 2B-2 fails:**
1. Remove new API endpoints (/api/game/start, /api/game/finish)
2. Revert Serial Gateway to read-only version
3. Remove GameCommand table (or leave empty)
4. Dashboard returns to Phase 2A state (buttons disabled with notice)
5. Existing hardware-triggered flow continues to work

**Protected Components:**
- ✅ ESP32 firmware unchanged (rollback not needed)
- ✅ Existing MQTT topics unchanged
- ✅ Database Run/Hit tables unchanged
- ✅ SSE infrastructure unchanged
- ✅ Dashboard data display unchanged

---

## 12. INTEGRATION SEQUENCE RECOMMENDATION

### 12.1 Phase 2B-2 Implementation Order

**Step 1: Backend Command Infrastructure (Safe)**
- Add GameCommand database model
- Add POST /api/game/start endpoint (validation only, no MQTT yet)
- Add POST /api/game/finish endpoint (validation only)
- Add GET /api/game/status endpoint
- Write unit tests for command validation

**Step 2: MQTT Command Transport (Medium Risk)**
- Add MQTT command topic publication in backend
- Backend publishes to `aquabuzz/commands/{device_id}`
- Write tests for MQTT command publishing
- Verify existing event topics unaffected

**Step 3: Serial Gateway Command Capability (High Risk)**
- Subscribe to MQTT command topics in Serial Gateway
- Add `send_command()` method to Serial Gateway
- Add command queue and pending command tracking
- Add timeout detection logic
- Preserve existing read loop architecture
- Write unit tests for command sending

**Step 4: Dashboard Integration (Safe)**
- Connect START GAME button to POST /api/game/start
- Connect FINISH GAME button to POST /api/game/finish
- Add command pending state handling
- Add error message display
- Add timeout handling
- Remove integration pending notice

**Step 5: End-to-End Testing (Requires Firmware Update)**
- Update ESP32 firmware with command handler (Phase 3)
- Test dashboard → backend → gateway → ESP32 flow
- Test acknowledgment handling
- Test timeout scenarios
- Test error scenarios
- Performance testing

### 12.2 Testing Approach

**Phase 2B-2 Testing (Without Firmware Changes):**
1. Unit test all backend endpoints
2. Unit test Serial Gateway command sending
3. Unit test dashboard button handlers
4. Integration test MQTT command flow (without ESP32)
5. Manual test with mock serial device (echo acknowledgments)

**Phase 3 Testing (With Firmware Changes):**
1. Flash updated firmware
2. Full end-to-end testing
3. Performance testing (latency measurements)
4. Error recovery testing
5. User acceptance testing

---

## 13. PERFORMANCE EXPECTATIONS

### 13.1 Latency Budget

**Dashboard → ESP32 Game Start:**
```
Dashboard → Backend:        50ms (HTTP)
Backend → MQTT:             20ms (local broker)
MQTT → Serial Gateway:      10ms (subscription)
Serial Gateway → ESP32:     50ms (115200 baud, JSON parsing)
ESP32 Processing:           10ms (state change)
ESP32 → Gateway (ACK):      50ms (serial)
Gateway → Backend (MQTT):   20ms
Backend → Dashboard (SSE):  10ms
-------------------------------------------
Total (typical):           220ms
Total (worst case):        500ms (with retries)
```

**Acceptable Range:** 100ms - 500ms  
**User Perception:** < 500ms feels instant

### 13.2 Existing Performance Baselines

**From FEAT-002 Latency Measurements:**
- Serial read latency: ~5-20ms
- MQTT publish latency: ~10-30ms
- Database write latency: ~5-15ms
- SSE broadcast latency: ~1-5ms

**Dashboard Polling:**
- Active game: 1 second
- Idle: 3 seconds

---

## 14. COMMAND PROTOCOL SPECIFICATION

### 14.1 START Command

**Backend → Serial Gateway (MQTT):**
```json
{
  "command": "start",
  "request_id": "req-a1b2c3d4",
  "device_id": "aquabuzz-001",
  "player_id": "alice",
  "timestamp": 1703174890
}
```

**Serial Gateway → ESP32 (Serial):**
```json
{"cmd":"start","t":1703174890}
```

**ESP32 → Serial Gateway (Serial - ACK):**
```json
{"cmd":"ack","cmd_id":"start-1703174890","status":"ok"}
```

**ESP32 → Serial Gateway (Serial - Game Start):**
```json
{"run":1,"event":"run_start","t_ms":0,"esp32_ts_ms":1234567890}
```

**Serial Gateway → Backend (MQTT - ACK):**
```json
{
  "command": "start",
  "request_id": "req-a1b2c3d4",
  "status": "ok",
  "timestamp": 1703174890,
  "device_id": "aquabuzz-001"
}
```

### 14.2 FINISH Command

**Backend → Serial Gateway (MQTT):**
```json
{
  "command": "finish",
  "request_id": "req-e5f6g7h8",
  "device_id": "aquabuzz-001",
  "run_uid": "aquabuzz-001-1-5",
  "timestamp": 1703174920
}
```

**Serial Gateway → ESP32 (Serial):**
```json
{"cmd":"finish","t":1703174920}
```

**ESP32 → Serial Gateway (Serial - ACK):**
```json
{"cmd":"ack","cmd_id":"finish-1703174920","status":"ok"}
```

**ESP32 → Serial Gateway (Serial - Game Finish):**
```json
{
  "run":5,
  "event":"run_finish",
  "t_ms":12450,
  "hits":3,
  "total_contact_ms":420,
  "longest_hit_ms":180,
  "score":14450,
  "esp32_ts_ms":1234567902
}
```

### 14.3 Error Responses

**Invalid State:**
```json
{
  "cmd":"ack",
  "cmd_id":"start-1703174890",
  "status":"error",
  "reason":"already_running"
}
```

**Lockout Active:**
```json
{
  "cmd":"ack",
  "cmd_id":"start-1703174890",
  "status":"error",
  "reason":"lockout_active"
}
```

**Not Running:**
```json
{
  "cmd":"ack",
  "cmd_id":"finish-1703174920",
  "status":"error",
  "reason":"not_running"
}
```

---

## 15. CONCLUSIONS AND RECOMMENDATIONS

### 15.1 System Readiness Assessment

**Dashboard:** ✅ **READY**
- Phase 2A UI complete with 5 states
- Button handlers stubbed and prepared
- SSE connection robust
- Browser refresh recovery working

**Backend:** ⚠️ **PREPARATION REQUIRED**
- Existing endpoints mature and stable
- SSE infrastructure reliable
- MQTT ingestion idempotent
- **NEW:** Command endpoints, GameCommand table, timeout detection

**Serial Gateway:** ⚠️ **SIGNIFICANT CHANGES REQUIRED**
- Current architecture is read-only
- **NEW:** Command transmission capability needed
- **NEW:** MQTT command subscription needed
- **NEW:** Acknowledgment tracking needed
- **Risk:** Preserve existing read loop without interference

**ESP32 Firmware:** ❌ **BLOCKED (Phase 3)**
- Current firmware has NO command protocol
- Single-char commands insufficient
- JSON command parsing not implemented
- State machine modification needed
- **Constraint:** Cannot be changed in Phase 2B-2

### 15.2 Critical Path Analysis

**Phase 2B-2 Can Complete:**
1. ✅ Backend command API endpoints
2. ✅ MQTT command topic publication
3. ✅ Serial Gateway command transmission
4. ✅ Dashboard button integration
5. ✅ Unit and integration tests (without firmware)

**Phase 2B-2 Cannot Complete:**
1. ❌ End-to-end testing (requires firmware update)
2. ❌ Command acknowledgment verification
3. ❌ Actual game start from dashboard
4. ❌ Actual game finish from dashboard
5. ❌ Performance validation

**Recommendation:** Phase 2B-2 should prepare ALL infrastructure layers (dashboard, backend, Serial Gateway) and test them with **mock/simulated ESP32 responses**. Phase 3 updates firmware and validates end-to-end.

### 15.3 Key Design Decisions

**Decision 1: MQTT Command Transport**
- **Chosen:** Separate MQTT topic `aquabuzz/commands/{device_id}`
- **Rationale:** Consistent with event architecture, decouples backend from Serial Gateway
- **Alternative Rejected:** HTTP API on Serial Gateway (new dependency, tight coupling)

**Decision 2: Acknowledgment Protocol**
- **Chosen:** Explicit ACK messages from ESP32 with cmd_id matching
- **Rationale:** Reliable confirmation, timeout detection, error reporting
- **Alternative Rejected:** Assume success from run_start event (no timeout detection)

**Decision 3: Command State Tracking**
- **Chosen:** New GameCommand table in database
- **Rationale:** Persistent state, timeout detection, audit trail
- **Alternative Rejected:** In-memory tracking (lost on restart)

**Decision 4: Backward Compatibility**
- **Chosen:** Firmware ignores unknown JSON commands, falls back to char commands
- **Rationale:** Gradual rollout possible, old firmware continues to work
- **Alternative Rejected:** Breaking protocol change

### 15.4 Success Criteria for Phase 2B-2

**Must Have:**
1. ✅ Backend POST /api/game/start endpoint validates and publishes command
2. ✅ Backend POST /api/game/finish endpoint validates and publishes command
3. ✅ Serial Gateway subscribes to command topics
4. ✅ Serial Gateway forwards commands to serial port
5. ✅ Serial Gateway tracks pending commands with timeout
6. ✅ Dashboard START/FINISH buttons send API requests
7. ✅ Dashboard handles pending, success, error, timeout states
8. ✅ All existing functionality remains operational
9. ✅ Unit tests pass for all new components
10. ✅ Integration tests pass with mock ESP32

**Nice to Have:**
1. Command retry logic (manual retry sufficient for MVP)
2. Command queue (single pending command sufficient)
3. Multiple device support (single device sufficient)
4. Command history UI (database audit sufficient)

### 15.5 Final Recommendation

**Phase 2B-2 Implementation Plan:**

**Week 1: Backend Preparation**
- Implement GameCommand model
- Implement /api/game/start, /api/game/finish, /api/game/status
- Write unit tests
- Test with Postman/curl

**Week 2: Serial Gateway Enhancement**
- Add MQTT command subscription
- Implement send_command() method
- Add acknowledgment tracking
- Add timeout detection
- Write unit tests
- Test with mock serial device (Python script echoing ACKs)

**Week 3: Dashboard Integration**
- Connect button handlers to backend APIs
- Implement command state UI (pending, error, timeout)
- Add error message display
- Test with backend + mock gateway

**Week 4: Integration Testing**
- End-to-end testing with mock ESP32 (Python script)
- Simulate acknowledgments, errors, timeouts
- Performance testing (latency measurements)
- Regression testing (verify existing features)

**Phase 3: Firmware Integration (Future)**
- Update ESP32 firmware with JSON command handler
- Flash firmware
- End-to-end validation with real hardware
- User acceptance testing

**Risk Mitigation:**
- Keep existing hardware controls as backup
- Dashboard clearly shows command state
- Timeout errors provide clear guidance
- All changes are additive, no removals

---

## APPENDIX A: FILE LOCATIONS

```
c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS\

├── dashboard\
│   └── index.html                              # Phase 2A UI complete
│
├── backend\
│   ├── app\
│   │   ├── main.py                             # FastAPI app, event processing
│   │   ├── mqtt_client.py                      # MQTT subscriber
│   │   ├── models.py                           # Database models
│   │   ├── schemas.py                          # Pydantic schemas
│   │   └── db.py                               # Database setup
│   │
│   ├── serial_gateway.py                       # Serial-to-MQTT gateway
│   │
│   └── tests\
│       ├── test_features.py
│       ├── test_behavior.py
│       ├── test_classifier.py
│       ├── test_difficulty.py
│       ├── test_anomalies.py
│       ├── test_repairs.py
│       └── test_sse_reliability.py
│
└── firmware\
    └── aquabuzz_connected\
        └── aquabuzz_connected.ino              # ESP32 firmware (READ ONLY)
```

---

## APPENDIX B: CONFIGURATION FILES

**Backend .env:**
```bash
# MQTT Configuration
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_CLIENT_ID=aquabuzz-backend

# Serial Gateway Configuration
DEVICE_ID=aquabuzz-001
DEFAULT_PLAYER_ID=guest
COM_PORT=COM3

# Backend Configuration
DATABASE_URL=sqlite:///./aquabuzz.db
CORS_ORIGINS=*
LOG_LEVEL=INFO

# Feature Flags
GATEWAY_VERBOSE=0
```

**Serial Gateway Environment:**
```bash
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
DEVICE_ID=aquabuzz-001
DEFAULT_PLAYER_ID=guest
COM_PORT=COM3
GATEWAY_VERBOSE=1
```

---

## APPENDIX C: TEST DATA EXAMPLES

**Mock ESP32 Serial Output (Current):**
```json
{"run":1,"event":"run_start","t_ms":0,"esp32_ts_ms":1234567890}
{"run":1,"event":"hit_start","hit":1,"t_ms":2340,"esp32_ts_ms":1234570230}
{"run":1,"event":"hit_end","hit":1,"t_ms":2340,"dur_ms":120,"esp32_ts_ms":1234570350}
{"run":1,"event":"run_finish","t_ms":12450,"hits":3,"total_contact_ms":420,"longest_hit_ms":180,"score":14450,"esp32_ts_ms":1234580340}
```

**Mock ESP32 Serial Output (With Commands - Future):**
```json
{"cmd":"ack","cmd_id":"start-1703174890","status":"ok"}
{"run":1,"event":"run_start","t_ms":0,"esp32_ts_ms":1234567890}
{"cmd":"ack","cmd_id":"finish-1703174920","status":"ok"}
{"run":1,"event":"run_finish","t_ms":12450,"hits":3,"total_contact_ms":420,"longest_hit_ms":180,"score":14450,"esp32_ts_ms":1234580340}
```

---

**END OF ARCHITECTURE FINDINGS**

**Prepared by:** Architecture Planning Agent  
**Date:** 2024-12-21  
**Next Phase:** Implementation Planning (Phase 2B-2)
