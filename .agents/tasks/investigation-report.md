# AquaBuzz System Investigation Report

**Date:** November 25, 2026  
**Investigation Type:** Complete Root Cause Analysis  
**Status:** Investigation Complete - Ready for Repair Planning

---

## EXECUTIVE SUMMARY

This investigation examined the actual current state of the AquaBuzz system to identify root causes of reported issues. The investigation revealed:

1. **Database Location Issue**: Working database is in project root, not backend folder
2. **Hit Count Discrepancy**: 11 of 14 finished runs show hits=0 despite having Hit records
3. **Stale Run Present**: One abandoned run (test-run-001) with status='started'
4. **Active Run Miscounting**: Health endpoint counts stale runs as active
5. **Hardcoded Paths**: RISE scripts use absolute paths instead of dynamic detection
6. **Process Tracking**: Scripts save PowerShell wrapper PIDs, not actual Python PIDs

---

## 1. DATABASE STATE ANALYSIS

### Database Files Found

Three database files exist in the project:

1. **`c:\...\Intelligent_System_IS\aquabuzz.db`** ← **ACTUAL WORKING DATABASE**
   - Size: 36,864 bytes
   - Contains: 15 runs, 11 hits
   - **This is the database the backend actually uses**

2. **`c:\...\Intelligent_System_IS\backend\aquabuzz.db`**
   - Size: 36,864 bytes
   - Contains: 0 runs, 0 hits
   - Empty database (recently initialized or unused)

3. **`c:\...\Intelligent_System_IS\scripts\aquabuzz.db`**
   - Size: 0 bytes
   - Empty file

**ROOT CAUSE #1**: The backend configuration points to the project root database, not the backend folder database. This discrepancy needs to be documented or consolidated.

### Database Content Analysis

#### Runs by Status

```
Status 'finished': 14 runs
Status 'started': 1 run
```

#### Stale Run Record

**run_uid:** `test-run-001`

```
id: 1
run_uid: test-run-001
device_id: aquabuzz-001
player_id: test-player
run_no: 1
started_at: 2026-11-24 13:09:48.039042
finished_at: None
duration_ms: None
hits: 0
total_contact_ms: 0
longest_hit_ms: 0
hit_penalty_ms: 2000
score: None
status: started
```

**Analysis**: This is an abandoned test run that was never finished or cancelled. It has been sitting in the database since November 24, 2026 at 13:09:48.

**ROOT CAUSE #2**: No stale-run detection mechanism exists. Runs with status='started' that never receive a run_finish event remain in the database indefinitely.

#### Recent Finished Runs (Sample)

All 14 finished runs show the same pattern:

```
run_uid: aquabuzz-001-ca3bdf73-14
  player: guest
  hits: 0          ← Declared zero hits
  total_contact_ms: 0
  longest_hit_ms: 0
  score: 0
  finished_at: 2026-11-24 16:29:33.160788
  
  ACTUAL HIT RECORDS IN DATABASE:
    Hit #1: start=765ms, duration=4ms  ← Hit exists!
  
  ❌ DISCREPANCY: Run.hits=0 but actual Hit records=1
```

This pattern repeats for 11 out of 14 finished runs.

#### Hit Table Analysis

```
Total hits: 11
Hits with duration_ms = 0: 3
Hits with duration_ms > 0: 8
```

**Analysis:**
- 11 Hit records exist in the database
- 8 hits were completed (hit_end received)
- 3 hits were started but never received hit_end (duration_ms=0)

#### Hit Count Discrepancy Summary

**11 runs have mismatched hit counts:**

| run_uid | Run.hits (declared) | Actual Hit Records |
|---------|--------------------|--------------------|
| aquabuzz-001-771b673c-1 | 0 | 1 |
| aquabuzz-001-771b673c-3 | 0 | 1 |
| aquabuzz-001-771b673c-6 | 0 | 1 |
| aquabuzz-001-ca3bdf73-7 | 0 | 1 |
| aquabuzz-001-ca3bdf73-8 | 0 | 1 |
| aquabuzz-001-ca3bdf73-9 | 0 | 1 |
| aquabuzz-001-ca3bdf73-10 | 0 | 1 |
| aquabuzz-001-ca3bdf73-11 | 0 | 1 |
| aquabuzz-001-ca3bdf73-12 | 0 | 1 |
| aquabuzz-001-ca3bdf73-13 | 0 | 1 |
| aquabuzz-001-ca3bdf73-14 | 0 | 1 |

**ROOT CAUSE #3**: The run_finish event handler is NOT using actual database Hit records to calculate aggregates, despite claims in IMPLEMENTATION_REPORT.md that it does.

---

## 2. EVENT PROCESSING CODE ANALYSIS

### File: `backend/app/main.py`

#### handle_mqtt_event() Function

**Location:** Lines 95-250 (approximately)

#### run_finish Event Handler Analysis

**Location:** Lines 183-230 (approximately)

**Current Implementation:**

```python
elif event_type == "run_finish":
    # Complete run with final statistics
    run = db.query(Run).filter(Run.run_uid == run_uid).first()
    if not run:
        print(f"[MQTT] WARNING: run_finish for unknown run {run_uid}")
        return
    
    # Idempotent - only update if not already finished
    if run.status != "finished":
        run.finished_at = datetime.utcnow()
        run.duration_ms = event.get("t_ms", 0)
        run.hit_penalty_ms = event.get("hit_penalty_ms", 2000)
        
        # CRITICAL FIX: Calculate aggregate stats from actual Hit records
        # Do NOT trust firmware's aggregate calculation - use database as source of truth
        hit_records = db.query(Hit).filter(Hit.run_uid == run_uid).all()
        
        # Count only completed hits (duration_ms > 0)
        completed_hits = [h for h in hit_records if h.duration_ms > 0]
        
        run.hits = len(completed_hits)
        run.total_contact_ms = sum(h.duration_ms for h in completed_hits)
        run.longest_hit_ms = max((h.duration_ms for h in completed_hits), default=0)
        
        # Recalculate score using actual hit count
        free_hits = 0  # Can be made configurable
        scored_hits = max(0, run.hits - free_hits)
        run.score = run.duration_ms + (scored_hits * run.hit_penalty_ms)
        
        run.status = "finished"
        db.commit()
```

**Analysis:**

The code CLAIMS to query Hit records and calculate aggregates from the database:

```python
hit_records = db.query(Hit).filter(Hit.run_uid == run_uid).all()
```

But the actual database shows:
- Hit records DO exist (11 hits across 11 runs)
- BUT Run.hits remains 0 for all these runs

**HYPOTHESIS: The code logic looks correct, but the query may be returning empty results.**

**Possible Causes:**

1. **run_uid mismatch**: The run_uid in the Hit table might not match the run_uid in the run_finish event
2. **Timing issue**: run_finish event arrives BEFORE hit_end events are processed
3. **Database session issue**: Different database sessions may not see uncommitted Hit records
4. **Transaction isolation**: Hit records may not be committed before run_finish queries them

**ROOT CAUSE #4**: The run_finish event handler queries Hit records, but consistently finds zero hits despite Hit records being created. This suggests a timing, transaction, or run_uid matching problem.

#### hit_start and hit_end Processing

**hit_start (Lines ~115-145):**

```python
elif event_type == "hit_start":
    # Check if hit already exists (idempotency)
    existing = db.query(Hit).filter(
        Hit.run_uid == run_uid, 
        Hit.hit_no == hit_no
    ).first()
    
    if not existing:
        hit = Hit(
            run_uid=run_uid,
            hit_no=hit_no,
            start_ms=start_ms,
            duration_ms=0  # Will be updated on hit_end
        )
        db.add(hit)
        db.commit()
```

✅ **Idempotency:** Properly checks for existing hit before creating
✅ **Immediate Creation:** Creates Hit record on hit_start (not waiting for hit_end)
✅ **Commit:** Commits immediately

**hit_end (Lines ~146-180):**

```python
elif event_type == "hit_end":
    hit = db.query(Hit).filter(
        Hit.run_uid == run_uid, 
        Hit.hit_no == hit_no
    ).first()
    
    if hit:
        # Update duration
        if hit.duration_ms == 0:  # Only update if not already set
            hit.duration_ms = dur_ms
            db.commit()
    else:
        # Hit start was missed - create complete record
        print(f"[MQTT] WARNING: hit_end without hit_start, creating complete record")
        start_ms = event.get("t_ms", 0) - dur_ms
        hit = Hit(...)
        db.add(hit)
        db.commit()
```

✅ **Idempotency:** Only updates duration_ms once
✅ **Fallback:** Creates hit record if hit_start was missed
✅ **Commit:** Commits immediately

**Analysis:** The hit processing logic looks sound. Hit records ARE being created (11 exist in database).

**ROOT CAUSE #5**: Hit records are successfully created and committed. The problem is NOT in hit processing; it's in run_finish failing to find these hits.

---

## 3. ACTIVE RUN COUNTING

### File: `backend/app/main.py`

**Location:** Line 322 (approximately)

```python
@app.get("/api/health")
async def health(db: Session = Depends(get_db)):
    """Health check endpoint."""
    total_runs = db.query(Run).count()
    total_players = db.query(Player).count()
    active_runs = db.query(Run).filter(Run.status == "started").count()
    completed_runs = db.query(Run).filter(Run.status == "finished").count()
```

**Current Query:**

```python
active_runs = db.query(Run).filter(Run.status == "started").count()
```

**Analysis:**

This query counts ALL runs with `status='started'`, regardless of:
- How long ago they started
- Whether finished_at is NULL
- Whether they're genuinely active or abandoned

**Current Behavior:**

```
active_runs = 1  (includes test-run-001 from 11+ hours ago)
```

**ROOT CAUSE #6**: Active run counting has no timeout or staleness detection. Any run with status='started' is counted as active forever.

**Impact:** The dashboard shows "Games Playing: 1" even though no game is actually active.

---

## 4. RISE SCRIPT ANALYSIS

### File: `scripts/rise.ps1`

#### Hardcoded Paths

**Line 7:**

```powershell
$script:PROJECT_ROOT = 'C:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma''am Mikae\Intelligent_System_IS'
```

**ROOT CAUSE #7**: Project root is hardcoded to a specific user's path. This script will fail on:
- Different Windows users
- Different installation locations
- Shared development environments
- Any machine other than the original developer's

**Recommended Fix:** Use `$PSScriptRoot` to dynamically determine project root:

```powershell
$script:PROJECT_ROOT = Split-Path -Parent $PSScriptRoot
```

#### Process Tracking Implementation

**Function: Save-ProcessInfo (Lines ~455-480)**

```powershell
function Save-ProcessInfo {
    param(
        [string]$Service,
        [int]$ProcessId,
        [int]$Port,
        [string]$Url = ''
    )
    
    # Saves $ProcessId directly to JSON
}
```

**Main Execution (Lines ~530-540):**

```powershell
$process = Start-Process powershell -ArgumentList "-NoProfile", "-Command", $uvicornCmd -WindowStyle Normal -WorkingDirectory $script:BACKEND_DIR -PassThru

$script:BackendProcessId = $process.Id
```

**Analysis:**

When `Start-Process powershell` is called:
1. PowerShell creates a NEW PowerShell process
2. That PowerShell process runs the command (e.g., uvicorn)
3. The returned `$process.Id` is the **PowerShell wrapper PID**, not the Python PID

**Example:**

```
PowerShell Wrapper PID: 12345  ← This is what gets saved
└─ python.exe PID: 12346       ← This is the actual backend
```

When `rise-stop.ps1` runs and tries to kill PID 12345:
- If the PowerShell wrapper already exited, PID 12345 doesn't exist
- The actual Python process (12346) keeps running
- Result: Orphaned Python processes

**ROOT CAUSE #8**: Process tracking saves PowerShell wrapper PIDs instead of actual service PIDs.

#### Process Detection Logic

**Function: Start-BackendService (Lines ~135-240)**

**Port Reuse Logic:**

```powershell
$existingProcessId = Get-ProcessOwningPort -Port $script:API_PORT

if ($existingProcessId) {
    if (Test-IsAquaBuzzBackend -ProcessId $existingProcessId) {
        # Try to reuse
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:$script:API_PORT/api/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($health.status -eq 'healthy') {
                Write-Host '  Existing AquaBuzz backend is healthy - reusing it'
                $script:BackendProcessId = $existingProcessId
                return
            }
        } catch {
            Write-Host '  Existing backend not responding to health check'
        }
    }
}
```

✅ **Good:** Health check before reusing
✅ **Good:** ForgeMind process detection and protection

**Issue:** Even if reused, still doesn't track child processes properly.

#### uvicorn --reload Child Processes

**Command Used (Line ~230):**

```powershell
$uvicornCmd = "& '$script:VENV_PYTHON' -m uvicorn app.main:app --host 0.0.0.0 --port $script:API_PORT --reload"
```

**Analysis:**

The `--reload` flag causes uvicorn to:
1. Start a parent watcher process
2. Spawn child worker processes
3. Watch for file changes and restart workers

**Process Tree:**

```
PowerShell Wrapper (tracked PID)
└─ Python uvicorn parent
   └─ Python uvicorn worker (actual server)
      └─ Child processes spawned on file change
```

Only the wrapper PID is tracked, so stopping it may not stop the entire tree.

**ROOT CAUSE #9**: --reload mode complicates process management. Workers may survive shutdown attempts.

### File: `scripts/rise-stop.ps1`

#### Shutdown Safety Checks

**Function: Test-IsForgeMindProcess (Lines ~10-25)**

```powershell
function Test-IsForgeMindProcess {
    param([int]$ProcessId)
    
    if ($proc.CommandLine -like '*arise*' -or $proc.CommandLine -like '*rest*' -or $proc.CommandLine -like '*ForgeMind*') {
        return $true
    }
}
```

✅ **Good:** Protects ForgeMind processes
✅ **Good:** Checks command line, not just process name

**Function: Test-IsAquaBuzzProcess (Lines ~27-60)**

```powershell
function Test-IsAquaBuzzProcess {
    param([int]$ProcessId, [string]$ServiceName)
    
    if ($ServiceName -eq 'backend' -and $commandLine -like '*uvicorn*app.main:app*') {
        return $true
    }
    # ... similar checks for gateway and dashboard
}
```

✅ **Good:** Verifies process by command line
✅ **Good:** Service-specific validation

**Stop Logic (Lines ~95-130):**

```powershell
$process = Get-Process -Id $processId -ErrorAction SilentlyContinue

if (-not $process) {
    Write-Host "  Process $processId not found (already stopped)"
    continue
}

if (Test-IsForgeMindProcess -ProcessId $processId) {
    Write-Host "  SKIPPED: ForgeMind process detected"
    continue
}

if (-not (Test-IsAquaBuzzProcess -ProcessId $processId -ServiceName $service)) {
    Write-Host "  SKIPPED: Not an AquaBuzz process"
    continue
}

Stop-Process -Id $processId -Force
```

✅ **Good:** Multiple safety checks
✅ **Good:** Graceful handling of missing processes

**Issue:** Only stops tracked PIDs. If wrapper PID is gone but child Python processes remain, they're not detected or stopped.

**ROOT CAUSE #10**: Shutdown script can't stop orphaned child processes if the tracked wrapper PID no longer exists.

---

## 5. ROOT CAUSE SUMMARY

### Critical Issues

| # | Root Cause | Impact | Severity |
|---|------------|--------|----------|
| 1 | Multiple database files; unclear which is authoritative | Confusion, potential data loss | Medium |
| 2 | No stale-run detection mechanism | Stale runs counted as active forever | High |
| 3 | run_finish claims to use DB but Run.hits always 0 | Incorrect hit counts, broken leaderboard | **Critical** |
| 4 | run_finish finds zero Hit records despite hits existing | Core game statistics broken | **Critical** |
| 5 | Hit records successfully created but not found by run_finish | Data exists but isn't used | **Critical** |
| 6 | Active run query has no timeout/staleness check | Inflated active game counts | Medium |
| 7 | Hardcoded project root path | Script fails on other machines | High |
| 8 | Process tracker saves wrapper PIDs, not actual service PIDs | Orphaned processes after restart | High |
| 9 | --reload mode creates untracked child processes | Duplicate processes accumulate | Medium |
| 10 | Shutdown can't stop orphaned children if wrapper PID gone | Manual cleanup required | Medium |

### Hypothesis: Why run_finish Finds Zero Hits

The code SHOULD work:

```python
hit_records = db.query(Hit).filter(Hit.run_uid == run_uid).all()
```

But it consistently returns zero hits. Possible explanations:

**A. Event Ordering Issue**

If `run_finish` arrives BEFORE `hit_start`/`hit_end` events:
- Backend processes run_finish first
- Queries Hit table → finds nothing
- Later, hit events arrive and create Hit records
- But run is already marked finished

**Evidence:** This would explain why hits exist in DB but Run.hits=0

**B. run_uid Mismatch**

If the run_uid in Hit records doesn't exactly match the run_uid in Run:
- Hit records: `aquabuzz-001-ca3bdf73-14`
- Run record: `aquabuzz-001-ca3bdf73-14`
- Query with mismatch: Finds nothing

**Evidence:** Need to verify exact run_uid values match

**C. Database Session/Transaction Isolation**

If hit_start/hit_end use different DB sessions:
- Hit created in session A and committed
- run_finish queries in session B
- Session B might not see session A's commits (unlikely with SQLite)

**Evidence:** Each event creates its own session via `get_db()`

**D. MQTT Event Delivery Order**

Serial Gateway or MQTT broker might not preserve event order:
- ESP32 sends: hit_start → hit_end → run_finish (in order)
- MQTT delivers: run_finish → hit_start → hit_end (out of order)

**Evidence:** This is the MOST LIKELY cause

---

## 6. EXACT LINE NUMBERS WHERE PROBLEMS EXIST

### backend/app/main.py

| Line(s) | Problem | Description |
|---------|---------|-------------|
| ~183-230 | run_finish handler | Queries Hit records but consistently finds zero |
| ~195 | Hit query | `db.query(Hit).filter(Hit.run_uid == run_uid).all()` returns empty |
| ~198-202 | Aggregate calculation | Calculates from empty list, results in hits=0 |
| ~322 | active_runs query | No timeout for stale run detection |

### scripts/rise.ps1

| Line(s) | Problem | Description |
|---------|---------|-------------|
| 7 | Hardcoded PROJECT_ROOT | User-specific absolute path |
| ~230 | uvicorn command | Uses --reload creating child processes |
| ~232 | Process ID capture | Saves wrapper PID, not actual Python PID |
| ~460-480 | Save-ProcessInfo | Stores wrapper PID to JSON |

### scripts/rise-stop.ps1

| Line(s) | Problem | Description |
|---------|---------|-------------|
| 7 | Hardcoded PROJECT_ROOT | Same as rise.ps1 |
| ~115-125 | Stop logic | Only stops tracked PIDs, misses orphans |

---

## 7. SPECIFIC CODE CHANGES NEEDED

### Fix #1: Database Path Consolidation

**Decision Required:** Which database should be authoritative?

**Option A:** Use `backend/aquabuzz.db`
- Move project root database to backend/
- Update backend/.env or db.py

**Option B:** Use project root `aquabuzz.db`
- Document this as the standard location
- Ensure all scripts use it consistently

### Fix #2: Stale Run Detection

**File:** `backend/app/main.py` (health endpoint)

**Before:**
```python
active_runs = db.query(Run).filter(Run.status == "started").count()
```

**After:**
```python
# Define timeout (e.g., 10 minutes)
ACTIVE_RUN_TIMEOUT = timedelta(minutes=10)
cutoff_time = datetime.utcnow() - ACTIVE_RUN_TIMEOUT

active_runs = db.query(Run).filter(
    Run.status == "started",
    Run.started_at >= cutoff_time
).count()
```

### Fix #3: run_finish Event Ordering

**Root Issue:** run_finish may arrive before hit events

**Solution:** Buffer events or add delay

**Option A: Event Buffering**
- Queue all events for a run
- Process in order: run_start → hit_* → run_finish

**Option B: Delayed Finalization**
- On run_finish, mark run as "finishing"
- Wait 1-2 seconds
- Then query hits and finalize

**Option C: Hit Count from Event**
- Trust firmware's hit count instead of querying database
- Use firmware values: hits, total_contact_ms, longest_hit_ms

### Fix #4: Dynamic Project Root

**File:** `scripts/rise.ps1`

**Before:**
```powershell
$script:PROJECT_ROOT = 'C:\Users\Alord\...'
```

**After:**
```powershell
# Dynamically determine project root (parent of scripts/)
$script:PROJECT_ROOT = Split-Path -Parent $PSScriptRoot
```

### Fix #5: Actual Process ID Tracking

**Problem:** Need actual Python PID, not wrapper PID

**Solution:** Parse command output or query after launch

**Example:**
```powershell
# After starting backend
Start-Sleep -Seconds 2

# Find actual Python process by port
$actualPid = Get-ProcessOwningPort -Port $script:API_PORT
if ($actualPid) {
    $script:BackendProcessId = $actualPid
}
```

### Fix #6: Remove --reload in Production

**File:** `scripts/rise.ps1`

**Before:**
```powershell
$uvicornCmd = "... --reload"
```

**After:**
```powershell
# Remove --reload for demonstration mode
$uvicornCmd = "... --host 0.0.0.0 --port $script:API_PORT"
```

**Benefit:** Simpler process tree, easier to manage

---

## 8. FILES THAT NEED MODIFICATION

### High Priority (Core Fixes)

1. **`backend/app/main.py`**
   - Fix run_finish event handler (solve hit count=0 issue)
   - Add stale run timeout to health endpoint
   - Possibly add event ordering/buffering

2. **`scripts/rise.ps1`**
   - Change PROJECT_ROOT to dynamic detection
   - Remove --reload flag
   - Improve process ID tracking
   - Fix process detection logic

3. **`scripts/rise-stop.ps1`**
   - Change PROJECT_ROOT to dynamic detection
   - Add child process detection and cleanup

### Medium Priority (Data Management)

4. **`backend/app/db.py`** or **`backend/.env`**
   - Clarify/consolidate database path
   - Document which database file is authoritative

5. **Database Cleanup Script** (new)
   - Script to clean up stale runs
   - Mark abandoned runs as "cancelled"
   - Don't delete historical data

### Low Priority (Documentation)

6. **`IMPLEMENTATION_REPORT.md`**
   - Update with actual findings
   - Remove claims that aren't true (hits=0 IS a problem)
   - Document root causes

7. **`QUICKSTART_GUIDE.md`**
   - Update process management instructions
   - Document stale run behavior

8. **`START_HERE.md`**
   - Reflect actual system state

---

## 9. TESTING REQUIREMENTS

### Database Verification Tests

```python
def test_hit_records_match_run_aggregates():
    """Verify Run.hits equals actual Hit record count."""
    runs = db.query(Run).filter(Run.status == 'finished').all()
    
    for run in runs:
        actual_hits = db.query(Hit).filter(Hit.run_uid == run.run_uid).count()
        assert run.hits == actual_hits, f"Run {run.run_uid}: declared={run.hits}, actual={actual_hits}"
```

### Event Ordering Tests

```python
def test_run_finish_before_hit_events():
    """Test if run_finish can arrive before hit events."""
    # Send events out of order
    send_mqtt_event(run_finish_event)
    send_mqtt_event(hit_start_event)
    send_mqtt_event(hit_end_event)
    
    # Verify hits are still counted
    run = db.query(Run).filter(Run.run_uid == test_run_uid).first()
    assert run.hits == 1
```

### Stale Run Tests

```python
def test_active_runs_excludes_stale():
    """Verify stale runs aren't counted as active."""
    # Create old run
    old_run = Run(
        run_uid="old-run",
        status="started",
        started_at=datetime.utcnow() - timedelta(hours=1)
    )
    db.add(old_run)
    db.commit()
    
    # Query active runs
    active_count = get_active_run_count()  # Should use timeout
    assert active_count == 0
```

### Process Management Tests

```powershell
# Test: rise command idempotency
rise
rise  # Should reuse existing processes

# Test: rise-stop cleanup
rise-stop
# Verify no uvicorn or serial_gateway processes remain
```

---

## 10. REMAINING LIMITATIONS

### Current Unknowns (Need Investigation)

1. **Exact run_uid values**: Need to verify run_uid in Hit vs Run tables match exactly
2. **Event arrival order**: Need MQTT broker logs to see actual delivery order
3. **Database session timing**: Need to add logging to see commit/query timing
4. **ESP32 firmware behavior**: Need to verify firmware sends events in correct order

### Cannot Be Verified Without Hardware

1. Serial gateway COM port detection
2. Actual sensor debounce timing
3. ESP32 event generation order
4. Physical gameplay timing

---

## CONCLUSION

This investigation has identified the actual root causes behind the reported issues:

**CRITICAL:** The hit count=0 problem is REAL and NOT fixed. Despite code claiming to query database, it consistently fails to find Hit records. This is likely due to event ordering (run_finish arriving before hit events).

**HIGH:** Stale runs are counted as active because there's no timeout-based detection.

**HIGH:** RISE scripts use hardcoded paths and track wrapper PIDs instead of actual service PIDs, causing portability and cleanup issues.

The next phase must implement fixes for these identified root causes, with particular focus on the event ordering problem in run_finish processing.

---

**Investigation Date:** November 25, 2026  
**Investigator:** AI Planning Agent  
**Status:** Complete - Ready for Implementation Planning
