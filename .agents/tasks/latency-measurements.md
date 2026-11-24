# AquaBuzz Latency Measurements and Analysis

**Date:** 2024  
**Branch:** latency-optimization-investigation  
**Status:** Code Analysis Complete (Physical Testing Required)

---

## Executive Summary

**Identified Primary Bottleneck: Dashboard Polling (3-second fixed interval)**

The dashboard polls the backend API every 3 seconds. This creates a 0-3 second variable delay before any event becomes visible to the user, independent of all other pipeline stages.

---

## Stage-by-Stage Analysis

### 1. ESP32 Event Generation

**Code Review Findings:**
- Contact detection: `loop()` runs continuously
- Debounce time: 20ms (`DEBOUNCE_MS`)
- Buzzer response: Immediate via `driveBuzzerNow()` (called first in loop)
- Event queuing: FreeRTOS `serialQueue` (non-blocking, size 50)
- JSON serialization: Minimal overhead (sprintf-style formatting)

**Expected Latency:** 20-50ms (dominated by debounce)

**Instrumentation Added:** `esp32_ts_ms` field on all events

**Bottleneck Risk:** ❌ LOW - Buzzer responds immediately, proving sensor detection is fast

---

### 2. USB Serial Transmission

**Code Review Findings:**
- Baud rate: 115200 (~11.5 KB/s)
- Typical event size: ~80 bytes JSON
- Transmission time: ~7ms per event
- Queue: FreeRTOS task `serialTask` drains queue to Serial

**Expected Latency:** 10-20ms

**Bottleneck Risk:** ❌ LOW - Serial is fast enough for event rates

---

### 3. Serial Gateway Processing

**Code Review Findings:**
- **BLOCKING READ:** `serial_port.readline()` with 1-second timeout
- Read loop: Checks `in_waiting` before reading (good)
- JSON parsing: Standard `json.loads()` (fast)
- Event normalization: Simple dict operations (fast)
- MQTT publish: QoS 1 (at-least-once, requires ACK)

**Expected Latency:** 10-100ms (normal), up to 1000ms if serial blocks

**Instrumentation Added:** 
- `gateway_rx_ts` timestamp
- Serial read timing (stderr log when GATEWAY_VERBOSE=1)
- MQTT publish timing (stderr log when GATEWAY_VERBOSE=1)

**Bottleneck Risk:** ⚠️ MEDIUM - Blocking readline() can delay MQTT processing

**Optimization Opportunity:**
```python
# Current (line ~400):
line = self.serial_port.readline()  # Blocks up to 1s

# Optimized alternative:
if self.serial_port.in_waiting > 0:
    line = self.serial_port.readline()
else:
    time.sleep(0.01)  # Small sleep to prevent CPU spinning
```

---

### 4. MQTT Network Transit

**Code Review Findings:**
- Broker: `test.mosquitto.org` (public, variable latency)
- QoS: 1 (requires PUBACK from broker)
- Keep-alive: 60 seconds
- Network: Internet-based (not local)

**Expected Latency:** 50-500ms (highly variable, depends on internet)

**Instrumentation:** Gateway logs MQTT publish timing

**Bottleneck Risk:** ⚠️ MEDIUM - Public broker introduces network latency

**Optimization Opportunity:**
- Use local MQTT broker (Mosquitto on localhost)
- Expected improvement: 50-500ms → 1-10ms
- Requires deployment change (not code change)

---

### 5. Backend Event Processing

**Code Review Findings:**
- Event handler: Synchronous `handle_mqtt_event()`
- Database: SQLite with synchronous writes
- Database operations:
  - `run_start`: INSERT Run + 2× SELECT (device, player) + 2× potential INSERTs
  - `hit_start`: SELECT Run + SELECT existing Hit + INSERT Hit
  - `hit_end`: SELECT Run + SELECT Hit + UPDATE Hit
  - `run_finish`: SELECT Run + SELECT all Hits + UPDATE Run + intelligence analysis
- Each database operation commits immediately (good for data safety, adds latency)

**Expected Latency:** 10-50ms per event (p95: 100ms)

**Instrumentation Added:**
- `backend_rx_ts` timestamp when event enters handler
- Database write timing (logged when LOG_LEVEL=DEBUG)
- Total processing timing (logged when LOG_LEVEL=DEBUG)

**Bottleneck Risk:** ❌ LOW - Database writes are fast enough for game event rates

**Optimization Opportunity:**
- Async event processing (queue events, process in background)
- Database connection pooling (already using SQLAlchemy, may already have)

---

### 6. Dashboard Polling

**Code Review Findings:**
- **FIXED 3-SECOND INTERVAL:** `setInterval(loadData, 3000)`
- API endpoints called every 3 seconds:
  - `/api/health`
  - `/api/leaderboard?limit=5`
  - `/api/runs?limit=10`
  - `/api/players`
- All calls made in parallel (`Promise.all`)
- No event-driven updates
- No indication when new events arrive

**Expected Latency:** 0-3000ms (average: 1500ms)

**Instrumentation Added:**
- `performance.now()` before/after fetch
- API fetch timing
- Render timing
- Console logging for debugging

**Bottleneck Risk:** 🔴 **HIGH - PRIMARY BOTTLENECK**

**Impact:** Even if all other stages take 100ms total, dashboard adds 0-3000ms variable delay

**Optimization Opportunities:**
1. **Adaptive Polling (Easy):**
   - 1-second interval during active games
   - 3-second interval when idle
   - Expected improvement: 1500ms avg → 500ms avg

2. **Server-Sent Events (Medium):**
   - Backend pushes events to dashboard
   - Expected improvement: 1500ms avg → <100ms
   - Requires new endpoint + EventSource client

3. **WebSocket (Complex):**
   - Bi-directional real-time communication
   - Expected improvement: 1500ms avg → <100ms
   - Requires WebSocket server + client

---

## Latency Budget Estimate

Based on code analysis (physical measurements needed for confirmation):

| Stage | Minimum | Typical | Maximum | % of Total |
|-------|---------|---------|---------|------------|
| ESP32 Detection | 20ms | 30ms | 50ms | 1-3% |
| Serial Transmission | 5ms | 10ms | 20ms | <1% |
| Serial Gateway | 10ms | 50ms | 1000ms | 2-50% |
| MQTT Network | 50ms | 150ms | 500ms | 5-25% |
| Backend Processing | 10ms | 30ms | 100ms | 1-5% |
| **Dashboard Polling** | **0ms** | **1500ms** | **3000ms** | **60-95%** |
| **TOTAL** | **95ms** | **1770ms** | **4670ms** | **100%** |

**Primary Bottleneck:** Dashboard polling contributes 60-95% of total latency

**Secondary Bottleneck:** MQTT network (using public broker)

---

## Hit Detection Timing Investigation

### Problem Statement

**Observed Symptoms (from requirements):**
1. Hits appear after 1+ seconds
2. Hit #1 shows in "Individual Hits" but "Total Hits" = 0
3. "Contact Time" = 0ms for incomplete hits
4. Buzzer responds immediately but dashboard lags

### Root Cause Analysis

#### Issue 1: Dashboard Waits for Polling Cycle

**Finding:** Dashboard polls every 3 seconds, so hit_start event sits in database waiting to be retrieved

**Code Evidence:**
```javascript
// dashboard/index.html line 616
setInterval(loadData, 3000);  // Fixed 3-second interval
```

**Impact:** Hit can exist in database for 0-3 seconds before dashboard sees it

**Solution:** Implement event-driven updates (SSE or WebSocket) or adaptive polling

---

#### Issue 2: Hit #1 Shows but Total Hits = 0

**Finding:** Race condition between individual hit display and aggregate statistics

**Code Evidence:**
```python
# backend/app/main.py - run_finish event
completed_hits = [h for h in hit_records if h.duration_ms > 0]
run.hits = len(completed_hits)
```

**Scenario:**
1. `hit_start` creates Hit record with `duration_ms=0`
2. Dashboard polls and retrieves hit in "Individual Hits"
3. `hit_end` hasn't arrived yet, so `duration_ms` still 0
4. Run.hits counts only completed hits (`duration_ms > 0`)
5. Dashboard shows: Individual Hits = 1, Total Hits = 0

**Root Cause:** Dashboard displays incomplete hits in one section but aggregate in another

**Solution:** 
- Show active (in-progress) hits with visual indicator
- Separate "Active Hits" from "Completed Hits"
- Update Total Hits count to include in-progress hits, or label clearly

---

#### Issue 3: Contact Time = 0ms

**Finding:** This is CORRECT behavior for in-progress hits

**Code Evidence:**
```python
# backend/app/main.py - hit_start event
hit = Hit(
    run_uid=run_uid,
    hit_no=hit_no,
    start_ms=start_ms,
    duration_ms=0  # Will be updated on hit_end
)
```

**When hit_end arrives:**
```python
# backend/app/main.py - hit_end event
hit.duration_ms = dur_ms  # Updated with actual duration
```

**Root Cause:** Dashboard polling may catch hit between start and end

**Solution:** Dashboard should display in-progress hits differently:
- "🔴 Hit #1 (IN PROGRESS)" when duration_ms = 0
- "✓ Hit #1 - 230ms" when duration_ms > 0

---

#### Issue 4: Why Hits Appear After 1+ Seconds

**Chain of Events:**

```
Time 0ms: User touches maze wire
  ↓ ESP32 detects (20ms)
Time 20ms: Buzzer activates immediately ✓
  ↓ ESP32 queues event (5ms)
Time 25ms: Serial transmits (10ms)
  ↓ Gateway receives (50ms)
Time 85ms: Gateway publishes to MQTT (150ms network)
  ↓ MQTT delivers to backend (20ms)
Time 255ms: Backend writes to database (30ms)
  ↓ Event now in database, waiting...
Time 285ms: Event sits in database waiting for poll ⏳
  ↓ Dashboard polling cycle (average 1500ms wait)
Time 1785ms: Dashboard retrieves event ❌
  ↓ Dashboard renders (10ms)
Time 1795ms: User sees hit on screen
```

**Actual delay:** ~1.8 seconds (mostly dashboard polling)

**Perceived delay:** >1 second between buzzer and display

**Conclusion:** The buzzer is IMMEDIATE (20ms), proving hardware is fast. The 1+ second delay is entirely in the event delivery pipeline, dominated by dashboard polling.

---

## Recommendations (Priority Order)

### 1. 🔴 HIGH PRIORITY: Dashboard Real-Time Updates

**Problem:** 60-95% of latency is dashboard polling

**Solution:** Implement Server-Sent Events (SSE)

**Expected Impact:** 
- Current: 0-3000ms dashboard lag (avg 1500ms)
- After: <100ms dashboard lag
- **Total improvement: 1400ms average reduction**

**Implementation:** FEAT-009 in plan

**Risk:** Medium (new communication pattern)

---

### 2. 🟡 MEDIUM PRIORITY: Adaptive Polling (Fallback)

**Problem:** Fixed 3-second interval even during active games

**Solution:** 1-second polling during games, 3-second when idle

**Expected Impact:**
- Current: avg 1500ms dashboard lag
- After: avg 500ms dashboard lag
- **Total improvement: 1000ms average reduction**

**Implementation:** FEAT-008 in plan

**Risk:** Low (simple change)

---

### 3. 🟡 MEDIUM PRIORITY: Local MQTT Broker

**Problem:** Public broker adds 50-500ms network latency

**Solution:** Run Mosquitto locally

**Expected Impact:**
- Current: 50-500ms MQTT lag
- After: 1-10ms MQTT lag
- **Total improvement: 100-400ms reduction**

**Implementation:** Deployment change (update .env)

**Risk:** Low (requires Mosquitto installation)

---

### 4. 🟢 LOW PRIORITY: Serial Gateway Async

**Problem:** Blocking readline() can delay by up to 1s (rare)

**Solution:** Non-blocking serial read with small sleep

**Expected Impact:**
- Current: 10-100ms typical (up to 1000ms worst case)
- After: 10-50ms typical (100ms worst case)
- **Total improvement: 10-50ms typical**

**Implementation:** FEAT-011 in plan

**Risk:** Low (simple change)

---

### 5. 🟢 LOW PRIORITY: Dashboard Hit State Display

**Problem:** Confusing display of incomplete hits

**Solution:** Visual indicators for in-progress vs completed hits

**Expected Impact:**
- Doesn't reduce latency
- Improves user experience (hits visible immediately)

**Implementation:** FEAT-007 in plan

**Risk:** Very Low (UI change only)

---

## Next Steps

1. ✅ **Phase 1 Complete:** Instrumentation added
2. ⚠️ **Phase 2 Needs Physical Testing:** Run actual game, collect real measurements
3. ➡️ **Phase 3:** Analyze hit detection timing with real data
4. ➡️ **Phase 4:** Implement dashboard real-time updates (SSE)
5. ➡️ **Phase 5:** Safe backend/gateway optimizations

**Blocker:** Physical ESP32 testing required to collect actual timing data and confirm analysis

**Recommended Action:** If ESP32 is available, run test game with:
- `LOG_LEVEL=DEBUG` in backend/.env
- `GATEWAY_VERBOSE=1` for serial gateway
- Browser console open to see dashboard timing
- Record full event flow timing for 5 test runs

---

## Measurement Collection Script (For Physical Testing)

```powershell
# Set debug mode
$env:LOG_LEVEL="DEBUG"
$env:GATEWAY_VERBOSE="1"

# Start system
.\scripts\rise.ps1

# Instructions:
# 1. Open dashboard: http://localhost:3000
# 2. Open browser DevTools (F12) → Console tab
# 3. Touch maze wire 5 times
# 4. Record timing from all 3 sources:
#    - Backend terminal (backend processing time)
#    - Gateway terminal (serial + MQTT time)
#    - Browser console (dashboard fetch time)
# 5. Save output to latency-measurements-physical.txt
```

**Analysis Formula:**
```
Total Latency = (Dashboard Display Time) - (ESP32 Event Time)
              = dashboard_render_ts - esp32_ts_ms

Dashboard Lag = (Dashboard Fetch Time) - (Backend Commit Time)
              = api_fetch_start - backend_db_commit_ts

Backend Lag = (Backend Commit Time) - (Gateway RX Time)
            = backend_db_commit_ts - gateway_rx_ts
```

---

## Conclusion

**Primary Bottleneck Identified:** Dashboard polling (3-second fixed interval)

**Primary Solution:** Implement Server-Sent Events for real-time dashboard updates

**Expected Total Improvement:** 
- Current: 1770ms average end-to-end latency
- After SSE: ~270ms average end-to-end latency
- **~1500ms (85%) reduction**

**All Optimizations Combined:**
- Current: 1770ms average
- After all optimizations: ~150ms average
- **~1620ms (92%) reduction**

This meets the goal of sub-500ms event-to-display latency.
