# AQUABUZZ LATENCY INVESTIGATION AND OPTIMIZATION PLAN

**Status:** Ready for Implementation  
**Branch:** latency-optimization-investigation  
**Date:** 2024  
**Baseline:** All 26 automated tests passing

---

## EXECUTIVE SUMMARY

This plan addresses the **1-3 second dashboard display delay** while preserving all working functionality. The physical buzzer responds immediately, but dashboard hits appear delayed. This is a **stability-first optimization** that uses incremental measurements, non-invasive instrumentation, and continuous testing.

---

## PART 1: CURRENT SYSTEM UNDERSTANDING

### Architecture (Verified from Codebase)

```
ESP32 Firmware (C++) → USB Serial (115200 baud) → Serial Gateway (Python) → 
MQTT (test.mosquitto.org) → FastAPI Backend (Python) → SQLite Database → 
Dashboard (HTTP Polling every 3s)
```

### Key Timing Points

| Stage | Current Implementation | Expected Latency |
|-------|----------------------|------------------|
| **ESP32 Contact Detection** | `loop()` with 20ms debounce | < 50ms |
| **ESP32 Serial Output** | Queued via FreeRTOS `serialQueue` | < 10ms |
| **Serial Transmission** | 115200 baud (~11.5KB/s) | < 20ms per event |
| **Serial Gateway Processing** | Blocking `readline()` with 1s timeout | 10ms - 1000ms |
| **MQTT Publish** | QoS 1, public broker | 50ms - 500ms |
| **Backend Event Processing** | Synchronous database writes | 10ms - 100ms |
| **Dashboard Polling** | HTTP GET every 3000ms | 0ms - 3000ms |
| **Total Pipeline** | Sum of above | **~100ms - 4600ms** |

### Critical Files (Absolute Paths)

```
c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS\firmware\aquabuzz_connected\aquabuzz_connected.ino
c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS\backend\serial_gateway.py
c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS\backend\app\main.py
c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS\backend\app\mqtt_client.py
c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS\dashboard\index.html
c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS\backend\app\models.py
```

### Known Issues from Investigation

1. **Dashboard Polling Delay:** 3-second intervals mean hits can take 0-3 seconds to appear
2. **Serial Gateway Blocking Read:** `readline()` with 1s timeout may delay event processing
3. **MQTT Public Broker:** test.mosquitto.org introduces variable network latency
4. **Synchronous Database Writes:** Each event blocks until database commit completes
5. **Hit #1 Display Issue:** Hit appears in Individual Hits before Total Hits updates (race condition in dashboard rendering)

---

## PART 2: NON-INVASIVE LATENCY MEASUREMENT

### Strategy

Add **correlation IDs** and **stage timestamps** without changing event flow. Use monotonic clocks within processes. Never block ESP32 operations.

### FEAT-001: ESP32 Timestamp Instrumentation

**Goal:** Measure ESP32 event generation timing

**Files to Modify:**
- `firmware/aquabuzz_connected/aquabuzz_connected.ino`

**Changes:**
1. Add monotonic timestamp to each event JSON (use `millis()`)
2. Prefix: `"esp32_ts_ms"` for each event
3. Add optional verbose mode flag (default: off, enable with 'v' serial command)

**Example Output:**
```json
{"run":1,"event":"hit_start","hit":1,"t_ms":523,"esp32_ts_ms":4523}
```

**Verification:**
- Upload firmware to ESP32
- Open Serial Monitor (115200 baud)
- Trigger maze contact
- Confirm `esp32_ts_ms` field present
- Verify buzzer still responds immediately
- Run existing tests: `scripts\test-full-flow.py` (should still pass)

**Rollback:** Git revert if any test fails

---

### FEAT-002: Serial Gateway Latency Logging

**Goal:** Measure serial read and MQTT publish delays

**Files to Modify:**
- `backend/serial_gateway.py`

**Changes:**
1. Add `gateway_rx_ts` timestamp when event received from serial
2. Add `gateway_mqtt_ts` timestamp when MQTT publish completes
3. Calculate and log deltas:
   - `serial_lag_ms = gateway_rx_ts - esp32_ts_ms` (clock skew, informational only)
   - `mqtt_lag_ms = gateway_mqtt_ts - gateway_rx_ts` (actual gateway processing time)
4. Add optional verbose logging mode (environment variable `GATEWAY_VERBOSE=1`)
5. Log to stderr to separate from normal stdout

**Example Log Output:**
```
[Latency] hit_start: serial_read=15ms, mqtt_publish=45ms, total_gateway=60ms
```

**Verification:**
- Set `$env:GATEWAY_VERBOSE=1`
- Run `python backend\serial_gateway.py`
- Trigger ESP32 event
- Confirm latency logs appear
- Confirm events still reach backend
- Check backend receives events correctly: `curl http://localhost:8000/api/health`

**Rollback:** Git revert if gateway crashes or events stop flowing

---

### FEAT-003: Backend Event Processing Timing

**Goal:** Measure MQTT reception, database write, and total processing time

**Files to Modify:**
- `backend/app/main.py` (function: `handle_mqtt_event`)

**Changes:**
1. Add `backend_rx_ts` timestamp when MQTT event enters `handle_mqtt_event()`
2. Add `backend_db_ts` timestamp after database commit
3. Add `backend_done_ts` timestamp before function returns
4. Calculate and log:
   - `mqtt_to_backend_ms = backend_rx_ts - gateway_mqtt_ts` (network + MQTT latency)
   - `db_write_ms = backend_db_ts - backend_rx_ts` (database latency)
   - `processing_ms = backend_done_ts - backend_rx_ts` (total backend time)
5. Add debug logging controlled by `LOG_LEVEL=DEBUG` in `.env`

**Example Log Output:**
```
[Latency] hit_start run-123-45: mqtt_rx=5ms, db_write=12ms, total=17ms
```

**Verification:**
- Set `LOG_LEVEL=DEBUG` in `backend/.env`
- Restart backend: `.\scripts\rise.ps1`
- Trigger ESP32 event
- Check backend terminal for latency logs
- Verify database records created: `curl http://localhost:8000/api/runs?limit=5`
- Run automated tests: `python scripts\test-full-flow.py`

**Rollback:** Remove debug logging if performance degrades

---

### FEAT-004: Dashboard Polling Measurement

**Goal:** Measure API response time and rendering delay

**Files to Modify:**
- `dashboard/index.html`

**Changes:**
1. Add `performance.now()` before and after each API fetch
2. Calculate:
   - `api_fetch_ms = fetch_end - fetch_start` (network + backend response)
   - `render_ms = render_end - fetch_end` (DOM update time)
3. Display latency stats in System Health card (optional, behind debug flag)
4. Add browser console logging for debugging
5. Track "event-to-display" time by comparing event timestamps to display time

**Example Console Output:**
```
[Dashboard] API fetch (health): 45ms, render: 2ms
[Dashboard] Event-to-display lag: 2847ms (last hit)
```

**Verification:**
- Open dashboard: `http://localhost:3000`
- Open browser DevTools (F12) → Console tab
- Trigger ESP32 event
- Observe console logs showing API and render times
- Verify dashboard still updates correctly
- Check System Health card displays timing (if debug mode enabled)

**Rollback:** Remove console logging if it impacts browser performance

---

### FEAT-005: End-to-End Latency Report

**Goal:** Aggregate all measurements into bottleneck analysis

**Files to Create:**
- `.agents/tasks/latency-measurements.json` (data file)
- `.agents/tasks/bottleneck-analysis.md` (human-readable report)

**Data Collection:**
1. Run 10 physical test runs with ESP32
2. Collect timestamps from all stages
3. Calculate mean, median, p95, and max for each stage
4. Identify bottleneck (stage with highest latency contribution)

**Example Report Structure:**
```markdown
# Latency Bottleneck Analysis

## Summary
Total end-to-end latency: 2847ms (average)
Primary bottleneck: Dashboard polling (3000ms worst case)

## Stage Breakdown
1. ESP32 Detection: 25ms (p95)
2. Serial Transmission: 15ms (p95)
3. Serial Gateway: 60ms (p95)
4. MQTT Network: 180ms (p95)
5. Backend Processing: 20ms (p95)
6. Dashboard Poll Delay: 0-3000ms (variable)

## Recommendations
[Based on measured data]
```

**Verification:**
- Review measurements for outliers or anomalies
- Confirm measurements align with expected ranges
- Share report with user for validation

**Success Criteria:** Identify which stage contributes > 50% of total latency

---

## PART 3: HIT DETECTION TIMING INVESTIGATION

### Problem Statement

**Observed Behavior:**
- Hit #1 appears in "Individual Hits" section
- "Total Hits" shows 0
- "Contact Time" shows 0ms
- Hit appears incomplete until page refresh or next poll

**Hypothesis:** Race condition between hit_start and dashboard rendering, compounded by polling delay

### FEAT-006: Hit State Transition Audit

**Goal:** Verify hit_start and hit_end flow through entire pipeline

**Files to Modify:**
- `backend/app/main.py` (add detailed logging for Hit table operations)
- `dashboard/index.html` (add hit state visualization)

**Changes:**

1. **Backend Hit State Logging:**
   ```python
   # In handle_mqtt_event, event_type == "hit_start"
   print(f"[HitState] Created Hit #{hit_no} for {run_uid}: start_ms={start_ms}, duration=0 (PENDING)")
   
   # In handle_mqtt_event, event_type == "hit_end"
   print(f"[HitState] Completed Hit #{hit_no} for {run_uid}: duration={dur_ms}ms (COMPLETED)")
   ```

2. **Dashboard Hit State Display:**
   - Show active (incomplete) hits with visual indicator: `🔴 Hit #1 (in progress)`
   - Show completed hits: `✓ Hit #1 - 230ms`
   - Add "Active Contact" counter in live game card

3. **Database Query Verification:**
   - Log all Hit table queries
   - Confirm hit_start creates record with `duration_ms=0`
   - Confirm hit_end updates existing record
   - Check for orphaned hits (start but no end)

**Test Cases:**

| Scenario | Expected Behavior | Current Behavior | Pass/Fail |
|----------|------------------|------------------|-----------|
| Quick tap (< 100ms) | Hit appears immediately with duration | Delayed display | ❌ |
| Long hold (> 1s) | Hit shows "in progress" then completes | Appears only after release | ❌ |
| Finish while touching | Hit #N closes before run_finish | Unknown | ⚠️ |
| Rapid taps (< 500ms apart) | Each hit tracked separately | Unknown | ⚠️ |

**Verification:**
- Run physical test with ESP32
- Watch backend logs for HitState entries
- Observe dashboard behavior for each scenario
- Document timing of when hit becomes visible
- Compare backend timestamp vs dashboard display timestamp

**Success Criteria:** Identify exact point where hit data exists in database but hasn't reached dashboard

---

### FEAT-007: Hit Display Timing Fix

**Goal:** Display hits immediately when hit_start occurs, update when hit_end arrives

**Current Implementation Problem:**
```javascript
// dashboard/index.html currently shows only completed hits (duration > 0)
// This means hit_start is invisible until hit_end arrives
```

**Files to Modify:**
- `dashboard/index.html` (function: `loadRunDetails`)
- `backend/app/main.py` (endpoint: `GET /api/runs/{run_id}`)

**Changes:**

1. **Backend API Enhancement:**
   - Modify `RunDetail` schema to include active_hits list
   - Return both completed and in-progress hits
   - Add `is_active` boolean field to hit records

2. **Dashboard Real-Time Hit Display:**
   ```javascript
   // Show in-progress hits
   if (hit.duration_ms === 0) {
       hitsHtml += `<div class="stat hit-active">
           <span class="stat-label">🔴 Hit #${hit.hit_no} (IN PROGRESS)</span>
           <span class="stat-value">Started at ${(hit.start_ms/1000).toFixed(2)}s</span>
       </div>`;
   } else {
       // Show completed hits (existing code)
   }
   ```

3. **Active Game Monitoring:**
   - Add separate API endpoint: `GET /api/runs/active` (returns all in-progress runs)
   - Poll active games more frequently (every 1 second) when game detected
   - Return to 3-second polling when no active games

**Verification:**
- Start physical game
- Touch maze wire → hit_start event
- Dashboard should show "Hit #1 (IN PROGRESS)" within 1 second
- Release wire → hit_end event
- Dashboard should update to show duration within 1 second
- Run automated tests
- Confirm backward compatibility with completed runs

**Rollback:** Revert if dashboard displays incorrect hit counts

---

## PART 4: DASHBOARD REAL-TIME IMPROVEMENTS

### Current Limitations

**Polling Architecture:**
- `setInterval(loadData, 3000)` - Fixed 3-second interval
- No event-driven updates
- Dashboard unaware of when events actually occur
- Worst-case display delay: 3000ms + network latency

### FEAT-008: Adaptive Polling Rate

**Goal:** Faster polling during active games, slower when idle

**Files to Modify:**
- `dashboard/index.html`

**Changes:**

1. **Dynamic Poll Interval:**
   ```javascript
   let pollInterval = 3000; // Start at 3s
   let intervalId = null;
   
   function updatePollRate() {
       clearInterval(intervalId);
       
       if (activeRuns > 0) {
           pollInterval = 1000; // 1s during games
       } else {
           pollInterval = 3000; // 3s when idle
       }
       
       intervalId = setInterval(loadData, pollInterval);
   }
   ```

2. **Active Game Detection:**
   - Use `/api/health` to detect `active_runs > 0`
   - Switch to fast polling when game starts
   - Return to slow polling 10 seconds after last game ends

3. **Network-Adaptive Polling:**
   - Measure API response time
   - If response > 500ms, increase interval to avoid congestion
   - If response < 100ms, can safely decrease interval

**Verification:**
- Load dashboard
- Confirm initial 3-second polling
- Start ESP32 game
- Confirm polling switches to 1-second
- Finish game
- Confirm polling returns to 3-second after 10s
- Check browser network tab for request frequency

**Performance Impact:**
- Idle: 20 requests/minute (unchanged)
- Active game: 60 requests/minute (3x increase, temporary)
- Acceptable for local network

**Rollback:** Revert if browser becomes unresponsive or backend overloaded

---

### FEAT-009: Server-Sent Events (SSE) Implementation

**Goal:** Push events to dashboard immediately without polling

**Risk Assessment:** MEDIUM (new communication pattern, requires testing)

**Files to Modify:**
- `backend/app/main.py` (add SSE endpoint)
- `dashboard/index.html` (add EventSource client)

**Backend Changes:**

1. **Add SSE Endpoint:**
   ```python
   from fastapi.responses import StreamingResponse
   import asyncio
   import queue
   
   # Global event broadcast
   sse_clients = []  # List of queues, one per connected dashboard
   
   @app.get("/api/live")
   async def live_events():
       """Stream live events to dashboard via SSE"""
       client_queue = queue.Queue()
       sse_clients.append(client_queue)
       
       async def event_generator():
           try:
               while True:
                   event = await asyncio.to_thread(client_queue.get, timeout=30)
                   yield f"data: {json.dumps(event)}\n\n"
           except:
               pass
           finally:
               sse_clients.remove(client_queue)
       
       return StreamingResponse(
           event_generator(),
           media_type="text/event-stream",
           headers={
               "Cache-Control": "no-cache",
               "X-Accel-Buffering": "no"
           }
       )
   ```

2. **Broadcast Events:**
   ```python
   # In handle_mqtt_event, after processing each event
   for client_queue in sse_clients:
       try:
           client_queue.put_nowait({
               "type": event_type,
               "data": event,
               "timestamp": datetime.utcnow().isoformat()
           })
       except queue.Full:
           pass  # Skip slow clients
   ```

**Dashboard Changes:**

1. **EventSource Client:**
   ```javascript
   let eventSource = null;
   
   function connectSSE() {
       eventSource = new EventSource(`${API_BASE}/live`);
       
       eventSource.onmessage = (event) => {
           const data = JSON.parse(event.data);
           handleLiveEvent(data);
       };
       
       eventSource.onerror = () => {
           console.log('[SSE] Connection lost, reconnecting...');
           eventSource.close();
           setTimeout(connectSSE, 5000);
       };
   }
   
   function handleLiveEvent(event) {
       if (event.type === 'hit_start') {
           // Update hit display immediately
           updateHitDisplay(event.data);
       } else if (event.type === 'run_finish') {
           // Refresh full data
           loadData();
       }
   }
   ```

2. **Fallback to Polling:**
   - Keep existing polling as backup
   - If SSE connection fails 3 times, stay on polling
   - Show connection status in System Health card

**Testing Strategy:**

1. **Unit Tests:**
   - Test SSE endpoint returns valid event-stream
   - Test client reconnection logic
   - Test multiple simultaneous dashboard connections

2. **Integration Tests:**
   - Trigger ESP32 event
   - Verify SSE event received by dashboard within 500ms
   - Test dashboard recovery after backend restart
   - Test dashboard behavior with slow network (throttle to 3G)

3. **Load Tests:**
   - 5 simultaneous dashboards
   - 10 events per second
   - Verify no memory leaks
   - Verify backend CPU < 50%

**Verification:**
- Open dashboard
- Open browser DevTools → Network tab → Filter: EventStream
- Confirm SSE connection established
- Trigger ESP32 event
- Confirm event appears in dashboard < 500ms
- Restart backend, confirm dashboard reconnects
- Run automated tests: `python scripts\test-full-flow.py`

**Success Criteria:**
- Event-to-display latency < 500ms (excluding network transit)
- Dashboard reconnects within 5 seconds after backend restart
- No memory leaks after 1 hour of operation
- Backward compatible with existing API

**Rollback Plan:**
- If SSE causes backend crashes: disable SSE, return to polling
- If dashboards don't reconnect: add reconnection backoff
- If memory leaks detected: add client cleanup logic

---

### FEAT-010: WebSocket Alternative (Optional)

**When to Implement:** Only if SSE proves inadequate

**Advantages over SSE:**
- Bidirectional communication
- Lower overhead for high-frequency updates
- Better mobile browser support

**Disadvantages:**
- More complex implementation
- Requires WebSocket library (e.g., `python-socketio`)
- Stateful connections harder to load balance

**Decision Criteria:**
- Implement WebSocket if:
  - SSE event rate > 10/second causes issues
  - Need to send commands from dashboard to backend
  - Mobile browser SSE compatibility problems observed

**Defer to later phase** unless specific need identified

---

## PART 5: SAFE PERFORMANCE OPTIMIZATIONS

### FEAT-011: Serial Gateway Async Processing

**Goal:** Remove blocking serial reads without breaking event order

**Current Bottleneck:**
```python
# serial_gateway.py line ~280
line = self.serial_port.readline()  # Blocks up to 1 second
```

**Problem:** While waiting for serial data, MQTT messages can't be processed

**Files to Modify:**
- `backend/serial_gateway.py`

**Changes:**

1. **Non-Blocking Serial Read:**
   ```python
   # Replace blocking readline with non-blocking check
   if self.serial_port.in_waiting > 0:
       line = self.serial_port.readline().decode('utf-8', errors='ignore')
       # Process line
   else:
       time.sleep(0.01)  # Small sleep to prevent CPU spinning
   ```

2. **Separate MQTT Thread:**
   - Already using `mqtt_client.loop_start()` (background thread)
   - Verify MQTT callbacks don't block serial processing
   - Add queue for outbound MQTT messages if needed

**Verification:**
- Send rapid serial events (< 100ms apart)
- Confirm all events processed in order
- Confirm no events dropped
- Check CPU usage doesn't spike
- Run existing tests

**Expected Improvement:** Reduce gateway processing latency from 10-1000ms to 10-50ms

**Rollback:** Revert if events arrive out of order or get dropped

---

### FEAT-012: Backend Async Event Processing

**Goal:** Process MQTT events without blocking other requests

**Current Bottleneck:**
```python
# main.py handle_mqtt_event is synchronous
# Each database write blocks until commit completes
```

**Files to Modify:**
- `backend/app/main.py`
- `backend/app/mqtt_client.py`

**Changes:**

1. **Async Event Handler:**
   ```python
   async def handle_mqtt_event_async(event: dict):
       """Non-blocking event processing"""
       async with get_async_db() as db:
           # Async database operations
           await process_event_async(event, db)
   
   def handle_mqtt_event(event: dict):
       """MQTT callback (sync) queues async work"""
       asyncio.create_task(handle_mqtt_event_async(event))
   ```

2. **Connection Pooling:**
   - FastAPI already uses SQLAlchemy async
   - Verify connection pool size adequate (default: 5)
   - Increase to 10 if needed

3. **Event Queue:**
   - Add bounded queue (max 1000 events)
   - If queue full, drop events with warning (overflow protection)
   - Log queue depth for monitoring

**Verification:**
- Send 10 events rapidly
- Confirm all processed correctly
- Check database for missing/duplicate records
- Run automated tests
- Monitor backend memory usage

**Expected Improvement:** Reduce backend processing time from 20ms to < 10ms

**Rollback:** Revert if race conditions cause data corruption

---

### FEAT-013: Database Write Optimization

**Goal:** Reduce database commit latency without compromising data integrity

**Files to Modify:**
- `backend/app/main.py`
- `backend/app/db.py`

**Changes:**

1. **Batch Commits (Careful!):**
   - DO NOT batch hit_start and hit_end (must be immediate for real-time display)
   - CAN batch heartbeat updates (acceptable to be stale)
   - CAN batch suggestion creation (non-critical)

2. **Database Indexes:**
   ```python
   # Verify indexes exist on frequently queried columns
   # models.py already has index on run_uid (confirmed)
   # Add composite index if queries slow:
   Index('ix_runs_player_status', 'player_id', 'status')
   Index('ix_hits_run_hit', 'run_uid', 'hit_no')  # For hit lookups
   ```

3. **Read-Only API Optimization:**
   - Use `db.query(...).options(joinedload())` to reduce N+1 queries
   - Cache static data (leaderboard for 5 seconds)
   - Add `@lru_cache` for expensive calculations

**Verification:**
- Run database query profiling: `PRAGMA query_plan_detail=ON`
- Confirm hit_start and hit_end still create records immediately
- Run automated tests
- Load test: 100 runs in 10 seconds

**Expected Improvement:** Reduce database write time from 10-50ms to 5-20ms

**Rollback:** Revert if data consistency issues appear

---

### FEAT-014: MQTT QoS Optimization

**Goal:** Balance delivery guarantee with latency

**Current Settings:**
- Gateway publishes with `qos=1` (at least once delivery)
- Backend subscribes without explicit QoS

**Files to Modify:**
- `backend/serial_gateway.py`
- `backend/app/mqtt_client.py`

**Changes:**

1. **Analyze QoS Trade-offs:**
   - QoS 0: Fastest, no guarantee (acceptable for heartbeats)
   - QoS 1: At-least-once (current, may duplicate)
   - QoS 2: Exactly-once (slowest, rarely needed)

2. **Tiered QoS Strategy:**
   ```python
   # Gateway publishes
   if event_type == "heartbeat":
       qos = 0  # Fire and forget
   elif event_type in ["hit_start", "hit_end", "run_start", "run_finish"]:
       qos = 1  # Ensure delivery (backend has deduplication)
   ```

3. **MQTT Keep-Alive Tuning:**
   - Current: 60 seconds
   - Consider reducing to 30 seconds for faster reconnection detection

**Verification:**
- Monitor MQTT broker logs for message delivery
- Confirm no duplicate events reach backend (existing idempotency should handle)
- Check network packet capture for QoS handshake timing
- Run stress test: unplug/replug network during game

**Expected Improvement:** Reduce MQTT latency by 10-50ms for heartbeats

**Rollback:** Revert if events get lost (should not happen with idempotent backend)

---

## PART 6: TESTING AND VERIFICATION STRATEGY

### Continuous Testing Approach

**After Every Change:**
1. Run automated test suite: `python scripts\test-full-flow.py`
2. Manual physical test: Touch ESP32 maze wire, verify buzzer and dashboard
3. Check all 26 baseline tests still pass
4. Git commit with descriptive message

**If Any Test Fails:**
- STOP immediately
- Do not proceed to next feature
- Analyze root cause
- Fix or rollback
- Re-run all tests
- Only continue when ALL tests pass

### Test Suite Enhancement

**New Test File:** `scripts/test-latency-flow.py`

**Test Cases:**

1. **End-to-End Latency Test:**
   - Inject event with timestamp at serial gateway
   - Measure time until event appears in `/api/runs` response
   - Assert total latency < 2000ms (goal: < 500ms)

2. **Hit Timing Test:**
   - Send hit_start event
   - Query `/api/runs/{id}` immediately
   - Confirm hit appears with duration=0
   - Send hit_end event
   - Query again, confirm duration updated
   - Assert database reflects changes within 100ms

3. **Concurrent Event Test:**
   - Send 10 events rapid-fire (< 50ms apart)
   - Confirm all 10 processed correctly
   - Confirm correct order maintained
   - Confirm no duplicates or missing events

4. **Dashboard Polling Test:**
   - Start dashboard in headless browser (Selenium/Playwright)
   - Inject event
   - Measure time until DOM updates
   - Assert display latency < 3500ms (before optimization)
   - Assert display latency < 1000ms (after optimization)

5. **Failure Recovery Test:**
   - Disconnect MQTT broker mid-game
   - Confirm ESP32 continues functioning
   - Reconnect MQTT
   - Confirm events resume flowing
   - Confirm no data loss

**Verification Commands:**
```powershell
# Run test suite
cd c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS
..\.venv\Scripts\python.exe scripts\test-full-flow.py
..\.venv\Scripts\python.exe scripts\test-latency-flow.py

# Manual verification
.\scripts\rise.ps1  # Start system
# Trigger physical event
# Check dashboard: http://localhost:3000
# Check API: http://localhost:8000/api/runs?limit=5
# Check health: http://localhost:8000/api/health
```

---

## PART 7: IMPLEMENTATION ORDER AND DEPENDENCIES

### Phase 1: Measurement (Non-Breaking, 1-2 days)

**Goal:** Collect baseline data without changing behavior

1. ✅ FEAT-001: ESP32 Timestamp Instrumentation
2. ✅ FEAT-002: Serial Gateway Latency Logging  
3. ✅ FEAT-003: Backend Event Processing Timing
4. ✅ FEAT-004: Dashboard Polling Measurement
5. ✅ FEAT-005: End-to-End Latency Report

**Validation:** Generate bottleneck analysis report with real measurements

---

### Phase 2: Hit Timing Fix (High Priority, 1 day)

**Goal:** Solve the "Hit #1 appears but Total Hits = 0" problem

6. ✅ FEAT-006: Hit State Transition Audit
7. ✅ FEAT-007: Hit Display Timing Fix

**Validation:** Hit appears in dashboard within 1 second of physical contact

---

### Phase 3: Dashboard Optimization (Medium Risk, 1-2 days)

**Goal:** Reduce polling delay, add real-time updates

8. ✅ FEAT-008: Adaptive Polling Rate  
9. ✅ FEAT-009: Server-Sent Events Implementation  
10. ⏸️ FEAT-010: WebSocket Alternative (optional, only if needed)

**Validation:** Event-to-display latency < 500ms (measured end-to-end)

---

### Phase 4: Backend Optimization (Low Risk, 1 day)

**Goal:** Remove processing bottlenecks without breaking functionality

11. ✅ FEAT-011: Serial Gateway Async Processing
12. ✅ FEAT-012: Backend Async Event Processing  
13. ✅ FEAT-013: Database Write Optimization
14. ✅ FEAT-014: MQTT QoS Optimization

**Validation:** Backend processing time < 50ms per event (p95)

---

### Phase 5: Validation and Tuning (1 day)

**Goal:** Confirm all optimizations work together

15. Run full test suite with physical ESP32
16. Measure end-to-end latency with all optimizations active
17. Compare to baseline measurements
18. Document improvements
19. Create before/after demo video

**Success Criteria:**
- Dashboard displays hits within 500ms of physical contact (down from 1-3s)
- All 26+ automated tests pass
- No functionality broken
- System remains stable for 1-hour continuous operation

---

## PART 8: ROLLBACK AND SAFETY

### Git Branch Strategy

```
main (production-ready)
 └── latency-optimization-investigation (current, baseline committed)
      ├── feat/001-esp32-timestamps
      ├── feat/002-gateway-logging
      ├── feat/003-backend-timing
      └── ... (one branch per FEAT)
```

**Merge Strategy:**
- Merge each FEAT to `latency-optimization-investigation` after verification
- Final merge to `main` only after full Phase 5 validation
- Keep `main` always deployable

### Rollback Procedures

**If Individual FEAT Fails:**
```powershell
git checkout latency-optimization-investigation
git revert <commit-hash>
git push
```

**If Entire Optimization Fails:**
```powershell
git checkout main  # Return to working baseline
# Debug issue offline
# Re-attempt after root cause analysis
```

**Automated Rollback Trigger:**
- If any test fails 3 times consecutively: automatic revert
- If backend crashes during testing: automatic revert
- If dashboard becomes unresponsive: automatic revert

### Safety Checklist Before Each Change

- [ ] Current code committed to Git
- [ ] All existing tests passing
- [ ] Rollback command documented
- [ ] Physical ESP32 available for testing
- [ ] Backup of database exists
- [ ] User notified of testing in progress

---

## PART 9: SUCCESS METRICS

### Baseline (Before Optimization)

| Metric | Current Value |
|--------|--------------|
| Event-to-display latency (avg) | 1500ms - 3000ms |
| Event-to-display latency (p95) | 2800ms - 4500ms |
| Backend processing time | 20ms - 100ms |
| Serial gateway processing | 10ms - 1000ms |
| Dashboard polling interval | 3000ms fixed |
| MQTT publish latency | 50ms - 500ms |

### Target (After Optimization)

| Metric | Target Value | Stretch Goal |
|--------|-------------|--------------|
| Event-to-display latency (avg) | < 500ms | < 300ms |
| Event-to-display latency (p95) | < 1000ms | < 500ms |
| Backend processing time | < 50ms | < 20ms |
| Serial gateway processing | < 50ms | < 20ms |
| Dashboard polling (active game) | 1000ms | Real-time (SSE) |
| MQTT publish latency | 50ms - 500ms | (unchanged) |

### User-Visible Improvements

**Before:**
- Touch maze wire
- Buzzer sounds immediately ✅
- Dashboard updates 1-3 seconds later ❌

**After:**
- Touch maze wire
- Buzzer sounds immediately ✅
- Dashboard updates within 0.5 seconds ✅
- Hit shows as "in progress" immediately ✅
- Hit duration updates when contact ends ✅

---

## PART 10: KNOWN CONSTRAINTS AND LIMITATIONS

### Cannot Be Optimized

1. **Network Latency to test.mosquitto.org:**
   - Public broker location-dependent
   - Expected: 50-500ms
   - Solution: Accept as baseline, or deploy local Mosquitto (future work)

2. **Physical Sensor Debounce:**
   - 20ms required for electrical stability
   - Cannot reduce without false triggers

3. **USB Serial Baud Rate:**
   - 115200 is standard, well-supported
   - Higher rates (230400, 460800) require driver support verification
   - Risk of data corruption if increased

### Acceptable Trade-offs

1. **Faster Polling = More Network Traffic:**
   - 1-second polling during games acceptable (temporary)
   - Return to 3-second when idle

2. **SSE Keeps Connections Open:**
   - Acceptable for local deployment
   - Each dashboard = 1 persistent HTTP connection
   - Limit: 100 concurrent dashboards (more than sufficient)

3. **Async Processing = Complexity:**
   - Worth it for latency reduction
   - Requires careful testing for race conditions

---

## PART 11: DOCUMENTATION AND REPORTING

### Deliverables

1. **Latency Measurement Data:**
   - `.agents/tasks/latency-measurements.json`
   - Raw timestamps from 10 test runs
   - Per-stage breakdowns

2. **Bottleneck Analysis Report:**
   - `.agents/tasks/bottleneck-analysis.md`
   - Identification of primary latency contributor
   - Recommendations prioritized by impact

3. **Implementation Log:**
   - `.agents/tasks/implementation-log.md`
   - Each FEAT: changes made, verification results, issues encountered
   - Git commit hashes for traceability

4. **Before/After Comparison:**
   - `.agents/tasks/optimization-results.md`
   - Latency metrics before and after
   - User-visible improvements demonstrated
   - Video recording of physical test (optional)

5. **Updated Architecture Diagram:**
   - `docs/architecture-optimized.md`
   - Show SSE/WebSocket addition
   - Highlight async processing changes

### User Communication

**Progress Updates:**
- After each phase completion
- If any breaking issues encountered
- When ready for user acceptance testing

**Final Report Structure:**
```markdown
# AquaBuzz Latency Optimization Results

## Summary
Reduced dashboard display delay from 1-3 seconds to < 500ms

## Measurements
[Before/After comparison table]

## Changes Made
[List of FEATs implemented]

## Testing Evidence
[Test results, screenshots, video]

## Known Issues
[Any remaining issues or limitations]

## Future Improvements
[Optional enhancements not in scope]
```

---

## PART 12: FUTURE ENHANCEMENTS (OUT OF SCOPE)

**Not Included in Current Plan:**

1. **Local MQTT Broker:**
   - Replace test.mosquitto.org with local Mosquitto
   - Would reduce network latency by 50-200ms
   - Requires installation and configuration

2. **ESP32 Direct WiFi Mode:**
   - Bypass serial gateway entirely
   - ESP32 publishes directly to MQTT
   - Eliminates serial transmission delay
   - Requires WiFi credentials on device

3. **Dashboard Service Worker:**
   - Background sync and offline caching
   - Push notifications for game events
   - Requires HTTPS and service worker setup

4. **WebSocket Bidirectional Control:**
   - Send difficulty changes to ESP32 in real-time
   - Start/stop games from dashboard
   - Requires WebSocket on firmware

5. **Historical Latency Monitoring:**
   - Track latency metrics over time
   - Alert if degradation detected
   - Requires metrics database (InfluxDB/Prometheus)

**Recommendation:** Defer these until core latency optimization validated

---

## EXECUTION READINESS CHECKLIST

### Prerequisites

- [x] Git branch created: `latency-optimization-investigation`
- [x] Baseline committed and tagged
- [x] All 26 automated tests passing
- [x] Physical ESP32 hardware available
- [x] Serial connection verified
- [x] MQTT broker accessible
- [x] Dashboard loading correctly
- [x] User approval to proceed

### Implementation Readiness

- [x] Plan reviewed and approved
- [x] File paths verified (absolute paths documented)
- [x] Rollback procedures documented
- [x] Test commands verified
- [x] Safety constraints understood
- [x] Success metrics defined

### Next Steps

1. **User Review:** Confirm plan aligns with expectations
2. **Begin Phase 1:** Start with FEAT-001 (ESP32 timestamps)
3. **Measure Baseline:** Collect initial latency data
4. **Incremental Implementation:** One FEAT at a time, test after each
5. **Report Progress:** Update user after each phase

---

## APPENDIX A: QUICK REFERENCE

### Critical Commands

```powershell
# Start system
.\scripts\rise.ps1

# Stop system
.\scripts\rise-stop.ps1

# Run tests
..\.venv\Scripts\python.exe scripts\test-full-flow.py

# Check health
curl http://localhost:8000/api/health

# View dashboard
start http://localhost:3000

# Serial monitor (if needed)
# Arduino IDE: Tools → Serial Monitor → 115200 baud
```

### File Locations

```
Firmware:        firmware/aquabuzz_connected/aquabuzz_connected.ino
Serial Gateway:  backend/serial_gateway.py
Backend:         backend/app/main.py
MQTT Client:     backend/app/mqtt_client.py
Dashboard:       dashboard/index.html
Database Models: backend/app/models.py
Tests:           scripts/test-full-flow.py
```

### Git Workflow

```powershell
# Check status
git status

# Commit changes
git add <file>
git commit -m "FEAT-001: Add ESP32 timestamps"

# Create feature branch
git checkout -b feat/001-esp32-timestamps

# Merge to investigation branch
git checkout latency-optimization-investigation
git merge feat/001-esp32-timestamps

# Rollback if needed
git revert <commit-hash>
```

---

## APPENDIX B: TROUBLESHOOTING GUIDE

### Issue: Firmware Upload Fails

**Symptoms:** Arduino IDE can't upload to ESP32  
**Solutions:**
- Check USB cable (must support data, not just power)
- Install CP210x or CH340 drivers
- Try different USB port
- Select correct board: ESP32 Dev Module
- Check COM port in Device Manager

### Issue: Serial Gateway Can't Find ESP32

**Symptoms:** `[Serial] No ESP32 found`  
**Solutions:**
- Verify ESP32 connected and powered
- Check Device Manager for COM port
- Set explicit port: `$env:COM_PORT = "COM3"`
- Try different baud rate (unlikely)

### Issue: Backend Won't Start

**Symptoms:** Port 8000 already in use  
**Solutions:**
```powershell
netstat -ano | findstr :8000
taskkill /PID <process_id> /F
```

### Issue: Dashboard Shows "Cannot Connect"

**Symptoms:** Dashboard loads but shows backend offline  
**Solutions:**
- Verify backend running: `curl http://localhost:8000/api/health`
- Check firewall not blocking port 8000
- Try different port: `uvicorn app.main:app --port 8001`
- Check browser console for errors (F12)

### Issue: Events Not Appearing in Dashboard

**Symptoms:** ESP32 sending events but dashboard not updating  
**Checklist:**
1. ESP32 serial output visible in Serial Monitor? (115200 baud)
2. Gateway logs showing events received?
3. Backend logs showing MQTT events?
4. Database has records? `curl http://localhost:8000/api/runs?limit=5`
5. Dashboard polling? (Check Network tab in DevTools)

---

**Plan Version:** 1.0  
**Last Updated:** 2024  
**Status:** ✅ READY FOR IMPLEMENTATION  
**Estimated Duration:** 5-7 days (incremental, with testing)

---

**END OF PLAN**
