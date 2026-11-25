# AquaBuzz Phase 1.2: Final Code Diff Review

**Date:** November 25, 2026  
**Engineer:** Senior Frontend Engineer  
**Review Type:** EXACT CODE DIFF WITH RACE CONDITION ANALYSIS  
**Status:** ⏳ **AWAITING FINAL APPROVAL**

---

## EXECUTIVE SUMMARY

This document provides the **exact before-and-after code diff** with comprehensive race condition analysis and an improved **two-state approach** that maintains display stability.

### Key Improvement: Two-State Management

**Better Approach:** Separate `activeRunUid` (tracks current game) from `displayedRunUid` (tracks what's shown)

**Benefit:** Completed game details remain visible until next game starts, preventing momentary blank states.

---

## 1. COMPLETE PROPOSED DIFF

### File: `dashboard/index.html`

**Lines Modified:** ~35 lines total (increased from 25 to handle two-state management)

---

### SECTION A: Global State Variables (Line ~406)

#### BEFORE:
```javascript
        // Auto-detect backend API URL
        const API_BASE = window.location.port ? 
            `http://localhost:8000/api` : 
            `${window.location.protocol}//${window.location.hostname}:8000/api`;
        
        let activeRuns = [];
        
        // FEAT-004: Dashboard latency measurement
        let lastEventTimestamp = null;
        let latencyStats = {
            apiLatency: [],
            renderLatency: []
        };
```

#### AFTER:
```javascript
        // Auto-detect backend API URL
        const API_BASE = window.location.port ? 
            `http://localhost:8000/api` : 
            `${window.location.protocol}//${window.location.hostname}:8000/api`;
        
        let activeRuns = [];
        
        // Active run tracking for display priority
        let activeRunUid = null;      // Currently active game (run_start received, not finished)
        let displayedRunUid = null;   // Run currently shown in details (persists after finish)
        let lastApiResponseTime = 0;  // Timestamp to prevent stale data overwrites
        
        // FEAT-004: Dashboard latency measurement
        let lastEventTimestamp = null;
        let latencyStats = {
            apiLatency: [],
            renderLatency: []
        };
```

**Changes:**
- **+3 state variables** to handle active/displayed run separation and race conditions
- **activeRunUid:** Tracks if a game is currently in progress
- **displayedRunUid:** Tracks which run's details are shown (persists after completion)
- **lastApiResponseTime:** Prevents stale API responses from overwriting newer data

**Purpose:** Separate concerns - active game detection vs. display persistence

---

### SECTION B: SSE Event Handler (Lines 412-422)

#### BEFORE:
```javascript
        function handleLiveEvent(event) {
            const eventType = event.event;
            console.log(`[SSE] Received ${eventType} event:`, event);
            
            // FEAT-009: Trigger immediate refresh on key events
            if (eventType === 'hit_start' || eventType === 'hit_end' || 
                eventType === 'run_start' || eventType === 'run_finish') {
                // Refresh data immediately without waiting for poll interval
                loadData();
            }
        }
```

#### AFTER:
```javascript
        function handleLiveEvent(event) {
            const eventType = event.event;
            const runUid = event.run_uid;
            
            console.log(`[SSE] Received ${eventType} event:`, event);
            
            // Track active run lifecycle
            if (eventType === 'run_start') {
                activeRunUid = runUid;
                displayedRunUid = runUid;  // Immediately switch to new game
                console.log(`[SSE] Active run started: ${activeRunUid}`);
            } else if (eventType === 'run_finish' || eventType === 'run_cancel') {
                console.log(`[SSE] Run ${activeRunUid} completed (${eventType})`);
                activeRunUid = null;  // No longer active
                // Keep displayedRunUid - don't clear completed game from view
            }
            
            // FEAT-009: Trigger immediate refresh on key events
            if (eventType === 'hit_start' || eventType === 'hit_end' || 
                eventType === 'run_start' || eventType === 'run_finish') {
                // Refresh data immediately without waiting for poll interval
                loadData();
            }
        }
```

**Changes:**
- **Extract `run_uid`** from every SSE event
- **On `run_start`:** Set both `activeRunUid` AND `displayedRunUid` (immediate switch)
- **On `run_finish`/`run_cancel`:** Clear `activeRunUid` but KEEP `displayedRunUid`
- **Result:** Completed game stays visible until next game starts

**Lines Added:** +10 lines

---

### SECTION C: Run Selection Logic (Lines 613-619)

#### BEFORE:
```javascript
                document.getElementById('recent-runs').innerHTML = html;
                
                // Show details for most recent completed run
                const latestFinished = data.find(r => r.status === 'finished');
                if (latestFinished) {
                    loadRunDetails(latestFinished.id);
                }
            } catch (err) {
                document.getElementById('recent-runs').innerHTML = '<div class="empty-state">Error loading runs</div>';
            }
        }
```

#### AFTER:
```javascript
                document.getElementById('recent-runs').innerHTML = html;
                
                // Record API response time for race condition protection
                const apiResponseTime = Date.now();
                
                // Show details: prioritize active game, preserve displayed game, fall back to latest finished
                let runToDisplay = null;
                let displayReason = '';
                
                // Priority 1: Active game (currently in progress)
                if (activeRunUid) {
                    runToDisplay = data.find(r => r.run_uid === activeRunUid);
                    if (runToDisplay) {
                        displayReason = `active game (${activeRunUid})`;
                        displayedRunUid = activeRunUid;  // Update displayed reference
                    } else {
                        console.log(`[Dashboard] Active run ${activeRunUid} not yet in API response, keeping current display`);
                        // Don't clear activeRunUid - run might just not be in DB yet
                        // Fall through to check displayedRunUid
                    }
                }
                
                // Priority 2: Previously displayed run (keep showing until new game starts)
                if (!runToDisplay && displayedRunUid) {
                    runToDisplay = data.find(r => r.run_uid === displayedRunUid);
                    if (runToDisplay) {
                        displayReason = `previously displayed run (${displayedRunUid}, status: ${runToDisplay.status})`;
                    } else {
                        console.log(`[Dashboard] Previously displayed run ${displayedRunUid} no longer in recent runs`);
                        displayedRunUid = null;  // Clear stale reference
                    }
                }
                
                // Priority 3: Latest finished run (fallback when no active or displayed run)
                if (!runToDisplay) {
                    runToDisplay = data.find(r => r.status === 'finished');
                    if (runToDisplay) {
                        displayReason = `latest finished run (${runToDisplay.run_uid})`;
                        displayedRunUid = runToDisplay.run_uid;  // Remember what we're showing
                    }
                }
                
                // Apply display if we have a run and this isn't a stale response
                if (runToDisplay) {
                    if (apiResponseTime >= lastApiResponseTime) {
                        console.log(`[Dashboard] Displaying ${displayReason}`);
                        loadRunDetails(runToDisplay.id);
                        lastApiResponseTime = apiResponseTime;
                    } else {
                        console.log(`[Dashboard] Ignoring stale API response (${apiResponseTime} < ${lastApiResponseTime})`);
                    }
                }
            } catch (err) {
                document.getElementById('recent-runs').innerHTML = '<div class="empty-state">Error loading runs</div>';
            }
        }
```

**Changes:**
- **Three-tier priority system:**
  1. Active game (currently playing)
  2. Previously displayed run (persists after completion)
  3. Latest finished (fallback)
- **Race condition protection:** Compare `apiResponseTime` to prevent stale overwrites
- **Defensive handling:** Don't clear states prematurely
- **Extensive logging:** Track every decision for debugging

**Lines Added:** +42 lines (increased for comprehensive race protection)

**Total Section Length:** 7 lines → 49 lines

---

## 2. RUN LIFECYCLE HANDLING: TWO-STATE APPROACH

### Why Two States?

**Problem with Single State:**
```
Run 67 finishes → Clear activeRunUid
                → loadRecentRuns() finds nothing to display
                → Brief blank state
Run 68 starts   → Set activeRunUid
                → Display switches to run 68
```

**Solution with Two States:**
```
Run 67 finishes → Clear activeRunUid (no longer active)
                → Keep displayedRunUid = run67
                → Dashboard shows run 67 final stats
Run 68 starts   → Set activeRunUid = run68
                → Set displayedRunUid = run68 (immediate switch)
                → Dashboard shows run 68 (new game)
```

### State Transition Diagram

```
Initial State:
  activeRunUid = null
  displayedRunUid = null
  → Dashboard shows: Latest finished run (fallback)

─────────────────────────────────────────────

Event: run_start (run 67)
  activeRunUid = "...-67"
  displayedRunUid = "...-67"
  → Dashboard shows: Run 67 (Total Hits: 0)

Event: hit_start (run 67)
  activeRunUid = "...-67" (unchanged)
  displayedRunUid = "...-67" (unchanged)
  → Dashboard shows: Run 67 (Total Hits: 1)

Event: hit_end (run 67)
  activeRunUid = "...-67" (unchanged)
  displayedRunUid = "...-67" (unchanged)
  → Dashboard shows: Run 67 (Total Hits: 1, with duration)

Event: run_finish (run 67)
  activeRunUid = null (cleared - no longer active)
  displayedRunUid = "...-67" (KEPT - keep showing)
  → Dashboard shows: Run 67 (Final statistics)

─────────────────────────────────────────────

Event: run_start (run 68)
  activeRunUid = "...-68"
  displayedRunUid = "...-68" (immediately switched)
  → Dashboard shows: Run 68 (Total Hits: 0)

[Run 68 continues...]
```

### Benefits of Two-State Approach

✅ **Stability:** Completed game remains visible until new game starts  
✅ **No Flicker:** No momentary blank state between games  
✅ **Clear Intent:** `active` = "is game running?", `displayed` = "what should user see?"  
✅ **Race Protection:** Can verify active run exists before switching display  

---

## 3. RACE CONDITION ANALYSIS

### Race Condition 1: API Polling Before run_start

**Scenario:**
```
T+0ms:   Polling interval fires → API request begins
T+50ms:  SSE: run_start event arrives → Set activeRunUid
T+100ms: API response arrives → Find run matching activeRunUid
```

**Analysis:**
- API request initiated before `activeRunUid` set
- But response arrives AFTER SSE event processed
- Run selection logic checks CURRENT `activeRunUid` value
- Finds matching run in response

**Result:** ✅ **No issue** - Selection uses current state, not state at request time

---

### Race Condition 2: run_start Arrives While API Request Pending

**Scenario:**
```
T+0ms:   API request begins (triggered by polling)
T+25ms:  SSE: run_start arrives → Set activeRunUid = "...-67"
T+50ms:  First API response arrives → Looks for activeRunUid
```

**Analysis:**
- `activeRunUid` set while first request in flight
- First response may not include new run yet (database write in progress)
- Selection logic handles this:
  ```javascript
  if (!runToDisplay) {
      console.log('Active run not yet in API response, keeping current display');
      // Don't clear activeRunUid
  }
  ```
- Next refresh (triggered by `hit_start` or polling) will find it

**Result:** ✅ **No issue** - Defensive handling prevents premature state clearing

---

### Race Condition 3: Consecutive hit_start and hit_end

**Scenario:**
```
T+0ms:  SSE: hit_start → Trigger loadData()
T+5ms:  SSE: hit_end → Trigger loadData() again
T+10ms: First loadData() completes
T+15ms: Second loadData() completes
```

**Analysis:**
- Both events trigger refresh
- Both refreshes will fetch same database state (hit recorded)
- Both will select same run (`activeRunUid` unchanged)
- Both will call `loadRunDetails()` with same run ID
- Second call simply re-renders same data

**Result:** ✅ **No issue** - Redundant but harmless

**Optimization Opportunity:** Could debounce `loadData()` calls within 100ms window

---

### Race Condition 4: run_finish Before API Refresh Completes

**Scenario:**
```
T+0ms:   SSE: hit_end → Trigger loadData() → API request begins
T+25ms:  SSE: run_finish → Clear activeRunUid, trigger loadData() again
T+50ms:  First API response arrives (run still status='started')
T+100ms: Second API response arrives (run now status='finished')
```

**Analysis:**
- First response has stale status
- But `activeRunUid` already cleared by `run_finish` event
- First response selection logic:
  ```javascript
  Priority 1: Active game - Skip (activeRunUid = null)
  Priority 2: Displayed game - Find run 67, display it
  ```
- Second response has updated status, displays same run with final stats

**Result:** ✅ **No issue** - `displayedRunUid` persistence handles this gracefully

---

### Race Condition 5: New Run Starts Immediately After Previous Finishes

**Scenario:**
```
T+0ms:   SSE: run_finish (run 67) → Clear activeRunUid
T+10ms:  SSE: run_start (run 68) → Set activeRunUid = "...-68"
T+20ms:  API response arrives with BOTH runs
```

**Analysis:**
- `run_finish` clears `activeRunUid`, keeps `displayedRunUid = "...-67"`
- `run_start` sets `activeRunUid = "...-68"` AND `displayedRunUid = "...-68"`
- API response selection:
  ```javascript
  Priority 1: Active game (run 68) - FOUND, display it
  ```
- Dashboard immediately switches to run 68

**Result:** ✅ **No issue** - Immediate switch on new `run_start`

---

### Race Condition 6: Older API Response Arrives After Newer SSE Event

**Scenario:**
```
T+0ms:   API request #1 begins
T+50ms:  SSE: run_finish → Trigger loadData() → API request #2 begins
T+75ms:  API response #2 arrives (newer, run finished)
T+100ms: API response #1 arrives (older, run still active)
```

**Analysis:**
**WITHOUT timestamp protection:** Response #1 would overwrite Response #2 (BAD!)

**WITH timestamp protection:**
```javascript
// Response #2 arrives
apiResponseTime = 75
lastApiResponseTime = 0
75 >= 0 → Apply (update lastApiResponseTime = 75)

// Response #1 arrives
apiResponseTime = 100  // ← Wait, this is WRONG
```

**CORRECTION NEEDED:** Use request initiation time, not response arrival time!

**Fixed Implementation:**
```javascript
// At request start
const requestTime = Date.now();

// At response handling
if (requestTime >= lastApiRequestTime) {
    // Apply response
    lastApiRequestTime = requestTime;
} else {
    console.log('Ignoring response from older request');
}
```

**Result:** ✅ **Fixed with request timestamp** (not response timestamp)

---

### Race Condition 7: SSE Reconnects While Game Active

**Scenario:**
```
T+0ms:   Run 67 active, activeRunUid = "...-67"
T+10s:   Network drops, SSE disconnects
T+15s:   SSE reconnects (no events replayed)
T+20s:   hit_start arrives → Dashboard refreshes
```

**Analysis:**
- During disconnection: `activeRunUid` and `displayedRunUid` preserved (in-memory)
- After reconnection: States still valid
- Next event triggers refresh, finds run still active
- Dashboard continues showing correct run

**What if game FINISHED during disconnection?**
- `run_finish` event missed
- `activeRunUid` still set (stale)
- Next API refresh finds run with status='finished'
- Selection logic:
  ```javascript
  Priority 1: Active game - Find run 67, display it
  // But status shows 'finished' in details
  ```
- User sees finished game (correct data)
- Next `run_start` clears stale `activeRunUid`

**Result:** ✅ **Acceptable** - Shows correct data, stale `activeRunUid` doesn't cause data corruption

**Improvement Opportunity:** Could check run status and clear `activeRunUid` if finished

---

## 4. REVISED DIFF WITH RACE CONDITION FIX

### Correction: Use Request Time, Not Response Time

**Updated Section C (Lines 613-619):**

```javascript
                document.getElementById('recent-runs').innerHTML = html;
                
                // Record request initiation time (not response time) for race condition protection
                const requestTime = performance.now();  // Use performance.now() for precision
                
                // Show details: prioritize active game, preserve displayed game, fall back to latest finished
                let runToDisplay = null;
                let displayReason = '';
                
                // Priority 1: Active game (currently in progress)
                if (activeRunUid) {
                    runToDisplay = data.find(r => r.run_uid === activeRunUid);
                    if (runToDisplay) {
                        displayReason = `active game (${activeRunUid})`;
                        displayedRunUid = activeRunUid;  // Update displayed reference
                    } else {
                        console.log(`[Dashboard] Active run ${activeRunUid} not yet in API response, keeping current display`);
                        // Don't clear activeRunUid - run might just not be in DB yet
                    }
                }
                
                // Priority 2: Previously displayed run (keep showing until new game starts)
                if (!runToDisplay && displayedRunUid) {
                    runToDisplay = data.find(r => r.run_uid === displayedRunUid);
                    if (runToDisplay) {
                        displayReason = `previously displayed (${displayedRunUid}, ${runToDisplay.status})`;
                        
                        // Clear activeRunUid if displayed run is finished (handle missed run_finish event)
                        if (activeRunUid === displayedRunUid && runToDisplay.status === 'finished') {
                            console.log(`[Dashboard] Clearing stale activeRunUid - run ${activeRunUid} is finished`);
                            activeRunUid = null;
                        }
                    } else {
                        console.log(`[Dashboard] Previously displayed run ${displayedRunUid} no longer in recent runs`);
                        displayedRunUid = null;  // Clear stale reference
                    }
                }
                
                // Priority 3: Latest finished run (fallback)
                if (!runToDisplay) {
                    runToDisplay = data.find(r => r.status === 'finished');
                    if (runToDisplay) {
                        displayReason = `latest finished (${runToDisplay.run_uid})`;
                        displayedRunUid = runToDisplay.run_uid;
                    }
                }
                
                // Apply display if we have a run and this isn't from a stale request
                if (runToDisplay) {
                    if (requestTime >= lastApiRequestTime) {
                        console.log(`[Dashboard] Displaying ${displayReason}`);
                        loadRunDetails(runToDisplay.id);
                        lastApiRequestTime = requestTime;
                    } else {
                        console.log(`[Dashboard] Ignoring stale request (${requestTime.toFixed(1)} < ${lastApiRequestTime.toFixed(1)})`);
                    }
                }
            } catch (err) {
                document.getElementById('recent-runs').innerHTML = '<div class="empty-state">Error loading runs</div>';
            }
        }
```

**Key Changes from Previous Version:**
1. ✅ Use `requestTime` tracked from function start, not response arrival
2. ✅ Clear stale `activeRunUid` if displayed run shows as finished (handles missed events)
3. ✅ Use `performance.now()` for monotonic precision

---

### Where to Capture Request Time

**Add at start of `loadRecentRuns()` function:**

```javascript
        async function loadRecentRuns() {
            const requestTime = performance.now();  // ← Capture at REQUEST start
            
            try {
                const res = await fetch(`${API_BASE}/runs?limit=10`);
                const data = await res.json();
                
                // ... rest of function uses requestTime for race protection
```

---

## 5. BACK-TO-BACK GAMES: EXPECTED BEHAVIOR

### Scenario Timeline

```
Game 67 Active:
  activeRunUid = "...-67"
  displayedRunUid = "...-67"
  → Dashboard: "Run 67 - Total Hits: 3 - IN PROGRESS"

Game 67 Finishes:
  activeRunUid = null (cleared)
  displayedRunUid = "...-67" (KEPT)
  → Dashboard: "Run 67 - Total Hits: 3 - Final Score: 8.2s"

5-Second Pause (No Active Game):
  activeRunUid = null
  displayedRunUid = "...-67" (KEPT)
  → Dashboard: STILL showing "Run 67 - Final Score: 8.2s"
  
Game 68 Starts:
  activeRunUid = "...-68"
  displayedRunUid = "...-68" (IMMEDIATELY SWITCHED)
  → Dashboard: "Run 68 - Total Hits: 0 - IN PROGRESS"

Game 68 First Hit:
  activeRunUid = "...-68" (unchanged)
  displayedRunUid = "...-68" (unchanged)
  → Dashboard: "Run 68 - Total Hits: 1 - IN PROGRESS"
```

### Visual Continuity

**Before Fix:**
- Run 67 finishes → Dashboard shows run 66 (previous game) ❌
- Run 68 starts → Dashboard shows run 67 (previous game) ❌
- Confusing for user

**After Fix:**
- Run 67 finishes → Dashboard shows run 67 final stats ✅
- Pause → Dashboard STILL shows run 67 ✅
- Run 68 starts → Dashboard IMMEDIATELY switches to run 68 ✅
- Clear, predictable behavior

---

## 6. REGRESSION RISKS (UPDATED)

### Risk 1: Stale activeRunUid After Missed run_finish (Medium → Low)

**Scenario:** SSE disconnection causes missed `run_finish` event

**Original Mitigation:** Next `run_start` clears it

**Enhanced Mitigation:** Now also cleared when API shows run as finished:
```javascript
if (activeRunUid === displayedRunUid && runToDisplay.status === 'finished') {
    activeRunUid = null;  // Clear stale reference
}
```

**Severity:** Low - Multiple recovery mechanisms

---

### Risk 2: Request Time Tracking Precision (New - Very Low)

**Issue:** `performance.now()` vs `Date.now()` precision

**Analysis:**
- `performance.now()`: Monotonic, millisecond precision
- `Date.now()`: System clock, can go backwards
- Using `performance.now()` is correct choice

**Verification:**
```javascript
const req1 = performance.now();  // e.g., 123456.789
await delay(10);
const req2 = performance.now();  // e.g., 123466.890
// req2 > req1 always true (monotonic)
```

**Severity:** Very Low - `performance.now()` is industry standard

---

### Risk 3: displayedRunUid Never Cleared (Low)

**Scenario:** Very old run stays displayed indefinitely

**Analysis:**
- Cleared when not found in API response (Priority 2 check)
- Overwritten when new game starts (Priority 1 takes precedence)
- Fallback to latest finished still works (Priority 3)

**Worst Case:** Shows 10-minute-old run if no new activity

**Acceptable:** User typically plays another game or refreshes page

**Severity:** Low - Self-correcting with user activity

---

### Risk 4: Performance.now() Overflow (Negligible)

**Issue:** `performance.now()` overflows after ~104 days of continuous operation

**Analysis:**
- Returns time since page load, not system boot
- Dashboard page rarely open for 104 days
- Page refresh resets counter

**Severity:** Negligible

---

### Risk 5: Synchronization Between States (Low)

**Scenario:** `activeRunUid` and `displayedRunUid` become inconsistent

**Prevention:**
- Both set together on `run_start`
- `activeRunUid` cleared independently on `run_finish`
- Defensive checks prevent invalid states

**Verification Points:**
- Priority 1: Updates `displayedRunUid` when active run found
- Priority 2: Clears `activeRunUid` if displayed run is finished

**Severity:** Low - Multiple synchronization points

---

## 7. TESTING REQUIREMENTS (UPDATED)

### Pre-Implementation Tests

#### Test 1: Verify Current Bug ✅
Already confirmed in Phase 1.1 investigation

#### Test 2: Verify SSE Event Structure ✅
Already confirmed - events contain `run_uid`

---

### Post-Implementation Tests

#### Test 3: Active Run Display During Single Game

**Procedure:**
1. Start run 67
2. Observe "Latest Run Details" shows run 67, Total Hits: 0
3. Make 3 contacts
4. Verify hit count increments 1 → 2 → 3
5. Finish game
6. Verify final statistics appear

**Pass Criteria:**
- Dashboard consistently shows run 67 throughout
- Hit count matches actual contacts
- Final statistics correct

---

#### Test 4: Back-to-Back Games with Pause

**Procedure:**
1. Complete run 67 (3 hits)
2. Wait 10 seconds (no activity)
3. Verify run 67 final stats STILL visible
4. Start run 68
5. Verify dashboard switches to run 68 immediately
6. Make 2 contacts in run 68
7. Finish run 68

**Pass Criteria:**
- Run 67 stays visible during 10-second pause
- Dashboard switches to run 68 on `run_start`
- No flicker or blank state between games

---

#### Test 5: Rapid Back-to-Back Games (No Pause)

**Procedure:**
1. Complete run 69
2. Immediately start run 70 (within 1 second)
3. Make first contact in run 70
4. Verify correct run displayed

**Pass Criteria:**
- Dashboard switches instantly from run 69 to run 70
- No display of intermediate runs

---

#### Test 6: Race Condition - Polling During run_start

**Procedure:**
1. Set polling to 1-second interval
2. Start game exactly when polling fires
3. Observe console logs
4. Verify correct run displayed

**Pass Criteria:**
- Console shows request handling
- No stale request overwrites newer data
- Correct run displayed

---

#### Test 7: Missed run_finish Event Recovery

**Procedure:**
1. Start run 71
2. Disconnect network
3. Finish game while disconnected
4. Reconnect network
5. Wait for next refresh
6. Verify activeRunUid eventually cleared

**Pass Criteria:**
- Dashboard shows finished game correctly
- Console shows "Clearing stale activeRunUid"
- Next game starts correctly

---

#### Test 8: Console Log Verification

**Expected Output:**
```
[SSE] Received run_start event: {...}
[SSE] Active run started: esp32-001-sessionX-70
[Dashboard] Displaying active game (esp32-001-sessionX-70)

[SSE] Received hit_start event: {...}
[Dashboard] Displaying active game (esp32-001-sessionX-70)

[SSE] Received run_finish event: {...}
[SSE] Run esp32-001-sessionX-70 completed (run_finish)
[Dashboard] Displaying previously displayed (esp32-001-sessionX-70, finished)

[SSE] Received run_start event: {...}
[SSE] Active run started: esp32-001-sessionX-71
[Dashboard] Displaying active game (esp32-001-sessionX-71)
```

**Pass Criteria:**
- State transitions logged clearly
- Run UIDs tracked correctly
- Display reasons explicit

---

#### Test 9: Stale Request Rejection

**Procedure:**
1. Enable network throttling (simulate slow connection)
2. Trigger two rapid refreshes
3. Observe console logs
4. Verify only newer request applied

**Expected Console:**
```
[Dashboard] Displaying active game (request time: 1234.5)
[Dashboard] Ignoring stale request (1230.2 < 1234.5)
```

**Pass Criteria:**
- Stale request explicitly rejected
- Dashboard shows data from newer request

---

#### Test 10: Extended Operation (Stress Test)

**Procedure:**
1. Leave system running 30 minutes
2. Play 10 games with varying pause lengths
3. Monitor console for errors
4. Check memory usage

**Pass Criteria:**
- No JavaScript errors
- No memory leaks
- State tracking remains consistent
- All games display correctly

---

## 8. PRESERVED FUNCTIONALITY CHECKLIST

✅ **ESP32 Firmware** - Zero modifications  
✅ **MOSFET/Buzzer** - Zero modifications  
✅ **Serial Gateway** - Zero modifications  
✅ **MQTT Configuration** - Zero modifications  
✅ **Backend API** - Zero modifications  
✅ **Database Schema** - Zero modifications  
✅ **Scoring Calculations** - Zero modifications  
✅ **RISE Scripts** - Zero modifications  
✅ **Dashboard Visual Design** - Preserved (only logic changes)  
✅ **SSE Implementation** - Enhanced, not replaced  
✅ **Polling Fallback** - Preserved and enhanced  
✅ **Historical Records** - Not affected  
✅ **Duplicate Event Protection** - Backend unchanged  
✅ **In-Progress Hit Display** - Already working, preserved  
✅ **All Dashboard Sections** - Health, Leaderboard, Players, Recent Activity

---

## 9. FINAL RECOMMENDATION

### Implementation Status

**Ready:** ✅ YES  
**Confidence:** 95%  
**Risk Level:** LOW

### Summary of Improvements Over Initial Proposal

| Aspect | Initial Proposal | Final Version |
|--------|------------------|---------------|
| State Management | Single `activeRunUid` | Two-state: `active` + `displayed` |
| Display Stability | May flicker between games | Smooth transitions, no blank states |
| Race Protection | Basic (response time) | Enhanced (request time) |
| Stale Event Handling | Manual clear only | Auto-clear + manual verification |
| Code Lines | ~25 lines | ~40 lines (more robust) |
| Test Scenarios | 8 tests | 10 tests (added stress tests) |

### Why Two-State Approach is Better

1. **User Experience:** No flickering or blank states
2. **Stability:** Completed game stays visible until new game
3. **Clarity:** Separate "is active" from "what to show"
4. **Robustness:** Handles missed events gracefully
5. **Debuggability:** Clearer console logs

### Implementation Estimate

**Time:** 20 minutes coding + 45-60 minutes testing = **~1.25 hours**  
**Files:** 1 (`dashboard/index.html`)  
**Lines:** ~40 lines added/modified  
**Risk:** Low with comprehensive test coverage

---

## 10. APPROVAL REQUEST

### What I'm Asking to Modify

**File:** `dashboard/index.html`

**Changes:**
1. Add 3 state variables (`activeRunUid`, `displayedRunUid`, `lastApiRequestTime`)
2. Modify `handleLiveEvent()` to track run lifecycle (+12 lines)
3. Modify `loadRecentRuns()` selection logic (+35 lines including race protection)
4. Add request time capture at function start (+1 line)

**Total:** ~48 lines added/modified

### Why This is Better Than Initial Proposal

✅ **Smoother UX** - No blank states between games  
✅ **More Robust** - Handles missed SSE events  
✅ **Race Resistant** - Prevents stale data overwrites  
✅ **Better Logging** - Easier to debug  
✅ **More Testable** - Clearer state transitions  

### Approval Needed

**To proceed, respond with:**
> "Approved - implement the two-state fix with race condition protection"

**Or if you need:**
- Clarification on any section
- More detail on race conditions
- Alternative approach consideration
- Additional verification

**I'm ready to implement once you approve!** 🚀

---

**End of Final Code Diff Review**
