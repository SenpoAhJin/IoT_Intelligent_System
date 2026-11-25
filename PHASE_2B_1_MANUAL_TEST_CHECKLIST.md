# PHASE 2B-1: MANUAL TEST CHECKLIST

**Purpose:** Visual verification of SSE reliability fixes  
**When to use:** After deployment, before marking Phase 2B-1 complete  
**Duration:** ~10 minutes

---

## PREREQUISITES

- [ ] Backend running: `.\scripts\rise.ps1`
- [ ] Chrome browser with DevTools
- [ ] Dashboard URL: **http://localhost:3000** (or 3001, 3002, 8080, 8081 if 3000 is occupied)
- [ ] Backend API URL: http://localhost:8000

**Note:** The RISE script tries ports in order: 3000 → 3001 → 3002 → 8080 → 8081.  
Check the RISE startup output to confirm which port the dashboard is using.

---

## TEST 1: SSE INITIAL CONNECTION

**Steps:**
1. Open Chrome (use Incognito mode for clean state)
2. Open DevTools (F12) → Go to **Console** tab
3. Navigate to: **http://localhost:3000** (check RISE output for actual port)
4. Watch console output

**✅ PASS Criteria:**
- [ ] Console shows: `[SSE] Connecting to live events stream...`
- [ ] Console shows: `[SSE] ✓ Connected to live events stream`
- [ ] Console shows: `[Dashboard] Initialization complete`
- [ ] **NO ERRORS** about "ERR_INCOMPLETE_CHUNKED_ENCODING"
- [ ] **NO ERRORS** about "SSE connection error"

**❌ FAIL If:**
- Red errors in console
- Repeated "Reconnecting in..." messages
- Dashboard shows error banner about SSE connection

---

## TEST 2: SSE NETWORK CONNECTION

**Steps:**
1. In DevTools, go to **Network** tab
2. Refresh page (F5)
3. In filter box, type: `live`
4. Click on the `/api/live` request

**✅ PASS Criteria:**
- [ ] Request appears in network list
- [ ] Status: **200** or **pending** (gray, not red)
- [ ] Type: **eventsource**
- [ ] Connection stays open (doesn't close immediately)

**Additional Check (EventStream tab):**
1. Click the `/api/live` request
2. Go to **EventStream** tab
3. Wait 20 seconds

**✅ PASS Criteria:**
- [ ] See keep-alive comments appearing every ~15 seconds
- [ ] Format: `: keepalive <timestamp>`
- [ ] No "failed to load" messages

**❌ FAIL If:**
- Status shows error (red)
- Request closes immediately
- Type is not "eventsource"
- No keep-alive messages after 20 seconds

---

## TEST 3: BROWSER REFRESH RECOVERY

**Steps:**
1. With dashboard loaded and SSE connected
2. Note the console message: `[Dashboard] Initialization complete`
3. Press **F5** to refresh page
4. Watch console output

**✅ PASS Criteria:**
- [ ] Console shows: `[Recovery] Checking for active run after browser refresh...`
- [ ] Console shows: `[Recovery] No active run, loading latest finished run` (or active run if game running)
- [ ] Console shows: `[Dashboard] Initialization complete`
- [ ] SSE reconnects: `[SSE] ✓ Connected to live events stream`
- [ ] **NO ERRORS** during refresh

**If Game is Active:**
- [ ] Dashboard displays the active game (not an old finished game)
- [ ] Hit counter matches actual hits
- [ ] Elapsed time continues updating

**❌ FAIL If:**
- Errors during recovery
- SSE fails to reconnect
- Dashboard shows wrong game after refresh

---

## TEST 4: MULTIPLE BROWSER TABS

**Steps:**
1. With dashboard open in Tab 1
2. Open new tab (Tab 2)
3. Navigate to: **http://localhost:3000** (same port as Tab 1)
4. Open new tab (Tab 3)
5. Navigate to: **http://localhost:3000**
6. Check backend console

**✅ PASS Criteria:**
- [ ] Tab 1 console: SSE connected
- [ ] Tab 2 console: SSE connected
- [ ] Tab 3 console: SSE connected
- [ ] Backend console shows: `[SSE] Client #1 connected, 1 total clients`
- [ ] Backend console shows: `[SSE] Client #2 connected, 2 total clients`
- [ ] Backend console shows: `[SSE] Client #3 connected, 3 total clients`
- [ ] All tabs show same data
- [ ] No connection errors in any tab

**❌ FAIL If:**
- Any tab fails to connect
- Backend doesn't show 3 clients
- Errors about too many connections

---

## TEST 5: CONNECTION STABILITY

**Steps:**
1. Open dashboard
2. Wait 60 seconds without any interaction
3. Watch console and network tab

**✅ PASS Criteria:**
- [ ] SSE connection stays open (Network tab shows "pending")
- [ ] Keep-alive comments appear every ~15 seconds
- [ ] No disconnections
- [ ] No reconnection attempts
- [ ] Console shows periodic: `[Dashboard] API fetch: X ms, render: Y ms`

**❌ FAIL If:**
- Connection closes unexpectedly
- Reconnection attempts occur
- Errors appear in console

---

## TEST 6: CLOSE TAB CLEANUP

**Steps:**
1. Open dashboard in Tab 1
2. Backend console should show: `[SSE] Client #1 connected, 1 total clients`
3. Close Tab 1
4. Check backend console

**✅ PASS Criteria:**
- [ ] Backend console shows: `[SSE] Client #1 disconnected (cancelled)`
- [ ] Backend console shows: `[SSE] Client #1 cleaned up, 0 clients remaining`
- [ ] No errors about abandoned connections
- [ ] No memory leaks (backend memory stable)

**❌ FAIL If:**
- Backend doesn't detect disconnection
- Client counter doesn't decrease
- Errors about cleanup failures

---

## TEST 7: LIVE EVENT DELIVERY (Optional - Requires Hardware)

**Prerequisites:**
- ESP32 connected and running
- Serial Gateway active
- MQTT broker running

**Steps:**
1. Open dashboard with DevTools console visible
2. Start a game on ESP32 (physical button or touch wire)
3. Touch wire to create hits
4. Finish game (wire reaches end)
5. Watch console output

**✅ PASS Criteria:**
- [ ] Console shows: `[SSE] Received game_event:` for `run_start`
- [ ] Dashboard immediately switches to new game
- [ ] Console shows: `[SSE] Received game_event:` for each `hit_start`
- [ ] Hit counter increments in real-time
- [ ] Console shows: `[SSE] Received game_event:` for each `hit_end`
- [ ] Contact time updates in real-time
- [ ] Console shows: `[SSE] Received game_event:` for `run_finish`
- [ ] Final score displayed immediately

**Event Latency:**
- [ ] Events appear within **1-2 seconds** of physical action
- [ ] No noticeable delay between touch and dashboard update

**❌ FAIL If:**
- Events not received
- Delay > 5 seconds
- Dashboard doesn't update
- Errors during event processing

---

## TEST 8: RAPID CONNECT/DISCONNECT (Stress Test)

**Steps:**
1. Open dashboard tab
2. Close it immediately (Ctrl+W)
3. Repeat 10 times quickly
4. Check backend console

**✅ PASS Criteria:**
- [ ] Backend handles all connections/disconnections
- [ ] Final client count: **0**
- [ ] No "queue full" warnings
- [ ] No memory leaks
- [ ] No abandoned connections
- [ ] Backend console shows proper cleanup for each client

**❌ FAIL If:**
- Client counter doesn't return to 0
- Errors about abandoned connections
- Backend memory increases significantly
- Queue overflow warnings

---

## TEST 9: NETWORK TAB INSPECTION

**Steps:**
1. Open dashboard with DevTools Network tab
2. Filter: `api`
3. Watch requests over 60 seconds

**✅ PASS Criteria:**
- [ ] `/api/live` request stays pending (SSE connection)
- [ ] `/api/health` polled every 1-3 seconds
- [ ] `/api/runs` polled every 1-3 seconds
- [ ] `/api/leaderboard` polled every 1-3 seconds
- [ ] `/api/players` polled every 1-3 seconds
- [ ] All requests return **200** status
- [ ] No failed requests (red)

**Polling Rate:**
- [ ] When idle (no active game): ~3 seconds between polls
- [ ] When game active: ~1 second between polls

**❌ FAIL If:**
- Any requests fail
- SSE connection closes
- Polling stops
- Polling rate incorrect

---

## TEST 10: ERROR RECOVERY

**Steps:**
1. Open dashboard
2. Stop the backend: `.\scripts\rise-stop.ps1`
3. Wait 5 seconds
4. Start the backend: `.\scripts\rise.ps1`
5. Watch dashboard console

**✅ PASS Criteria:**
- [ ] Console shows: `[SSE] Connection error`
- [ ] Console shows: `[SSE] Reconnecting in...` (up to 5 attempts)
- [ ] After backend restart, console shows: `[SSE] ✓ Connected to live events stream`
- [ ] Dashboard recovers automatically
- [ ] All data loads correctly after reconnection

**After 5 Failed Attempts (if backend stays down):**
- [ ] Console shows: `[SSE] Max reconnection attempts reached, falling back to polling only`
- [ ] Dashboard banner shows: "Live updates unavailable, using polling mode"
- [ ] Dashboard still functions (slower updates via polling)

**❌ FAIL If:**
- Dashboard doesn't attempt reconnection
- Infinite reconnection loop
- Dashboard breaks after backend restart
- No fallback to polling mode

---

## FINAL VERIFICATION

### All Tests Complete?

- [ ] Test 1: SSE Initial Connection ✅
- [ ] Test 2: SSE Network Connection ✅
- [ ] Test 3: Browser Refresh Recovery ✅
- [ ] Test 4: Multiple Browser Tabs ✅
- [ ] Test 5: Connection Stability ✅
- [ ] Test 6: Close Tab Cleanup ✅
- [ ] Test 7: Live Event Delivery ✅ (optional)
- [ ] Test 8: Rapid Connect/Disconnect ✅
- [ ] Test 9: Network Tab Inspection ✅
- [ ] Test 10: Error Recovery ✅

### Critical Checks

- [ ] **NO** `ERR_INCOMPLETE_CHUNKED_ENCODING` errors seen
- [ ] **NO** repeated reconnection loops
- [ ] **NO** memory leaks observed
- [ ] **NO** abandoned connections
- [ ] SSE connections stable for 60+ seconds
- [ ] Browser refresh preserves state
- [ ] Multiple tabs work simultaneously
- [ ] Events delivered in real-time (if hardware available)

---

## SIGN-OFF

**Tester Name:** ________________________  
**Date:** ________________________  
**Result:** ☐ PASS   ☐ FAIL  

**Issues Found (if any):**
_____________________________________________________________
_____________________________________________________________
_____________________________________________________________

**Additional Notes:**
_____________________________________________________________
_____________________________________________________________
_____________________________________________________________

---

## IF TESTS FAIL

### Check Backend Logs
```powershell
# Backend console should show:
[SSE] Client #N connected, X total clients
[SSE] Client #N cleaned up, X clients remaining
```

### Check Browser Console
```javascript
// Should see:
[SSE] Connecting to live events stream...
[SSE] ✓ Connected to live events stream
[Dashboard] Initialization complete
```

### Common Issues

**Problem:** SSE won't connect  
**Solution:** Check CORS settings, verify port 8000 is accessible

**Problem:** Events not received  
**Solution:** Check MQTT broker, verify Serial Gateway running

**Problem:** High reconnection attempts  
**Solution:** Check network firewall, disable browser extensions

**Problem:** Memory increasing  
**Solution:** Check for abandoned clients, verify cleanup logs

---

**TESTING COMPLETE**

If all tests pass: **Phase 2B-1 is VERIFIED ✅**  
If any tests fail: **Review logs and investigate before proceeding**
