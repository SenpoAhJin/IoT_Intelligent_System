# WORKING_2 QUICK REFERENCE

**Dashboard-Controlled Game Lifecycle Baseline**

---

## 📌 ESSENTIAL INFORMATION

| Property | Value |
|----------|-------|
| **Repository** | https://github.com/SenpoAhJin/IoT_Intelligent_System.git |
| **Branch** | `working_2` |
| **Tag** | `working_2-dashboard-control-baseline` |
| **Commit** | `a474fc738e129853b98fae267bd2f8afc97b2294` |
| **Date** | 2026-11-25 |
| **Tests** | 33/33 passing ✅ |
| **Status** | Production-ready ✅ |

---

## 🚀 QUICK RECOVERY

### One-Line Recovery

```powershell
git fetch origin && git checkout working_2 && git reset --hard working_2-dashboard-control-baseline
```

### Using Recovery Script

```powershell
.\scripts\restore-working-2.ps1
```

---

## 🎯 WHAT'S IN WORKING_2

### New Features (vs Working_1)

✅ **Dashboard START Command** - Start game from dashboard  
✅ **Dashboard FINISH Command** - End game from dashboard  
✅ **ESP32 JSON Command Parser** - Processes remote commands  
✅ **Serial Gateway Command Worker** - Dedicated command thread  
✅ **Command Acknowledgment System** - Confirms command execution  
✅ **6 New Tests** - SSE reliability tests added  

### Preserved Features (from Working_1)

✅ Physical maze start/finish controls  
✅ Real-time SSE dashboard updates  
✅ Hit tracking and scoring  
✅ MQTT integration  
✅ Database persistence  
✅ RISE startup/shutdown system  

---

## 📂 KEY FILES

### Implementation Files

```
firmware/aquabuzz_connected/aquabuzz_connected.ino  # ESP32 command parser
backend/serial_gateway.py                           # Command worker thread
backend/app/main.py                                 # API endpoints
backend/app/mqtt_client.py                          # MQTT commands
dashboard/index.html                                # Game controls
```

### Documentation Files

```
WORKING_2_PRESERVATION_REPORT.md                    # This preservation
PHASE_2B2_IMPLEMENTATION_REPORT.md                  # Technical details
PHASE_2B2_QUICK_SUMMARY.md                          # Quick guide
PHASE_2B2_TESTING_GUIDE.md                          # Testing procedures
```

### Test Files

```
backend/tests/test_sse_reliability.py               # SSE tests
scripts/test-game-control.ps1                       # Dashboard control tests
scripts/test_sse_connection.ps1                     # SSE connection tests
```

---

## 🔧 POST-RECOVERY SETUP

### 1. Create Environment Files

**backend/.env**:
```env
MQTT_BROKER=your-broker.com
MQTT_PORT=1883
MQTT_USERNAME=your-username
MQTT_PASSWORD=your-password
DATABASE_URL=sqlite:///./aquabuzz.db
```

**firmware/aquabuzz_connected/secrets.h**:
```cpp
#define WIFI_SSID "your-ssid"
#define WIFI_PASSWORD "your-password"
#define MQTT_BROKER "your-broker.com"
#define MQTT_PORT 1883
#define MQTT_USERNAME "your-username"
#define MQTT_PASSWORD "your-password"
```

### 2. Install Dependencies

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Upload Firmware

Use Arduino IDE to upload firmware to ESP32.

### 4. Start System

```powershell
.\scripts\rise.ps1
```

---

## ✅ QUICK VERIFICATION

### Check Recovery Success

```powershell
# Verify commit
git log -1 --format="%H"
# Expected: a474fc738e129853b98fae267bd2f8afc97b2294

# Verify branch
git branch --show-current
# Expected: working_2
```

### Run Tests

```powershell
cd backend
python -m pytest tests -v
# Expected: 33 passed
```

### Test Dashboard

1. Start system: `.\scripts\rise.ps1`
2. Open: `http://localhost:8000`
3. Click "START GAME"
4. Click "FINISH GAME"
5. Verify score displayed

---

## 🎮 DASHBOARD CONTROLS

### Game Flow

```
WAITING → Click "START GAME" → RUNNING → Click "FINISH GAME" → FINISHED
           ↑                                                      ↓
           └─────────── Click "START NEW GAME" ─────────────────┘
```

### Button States

| State | START Button | FINISH Button | NEW GAME Button |
|-------|--------------|---------------|-----------------|
| WAITING | ✅ Enabled | ❌ Disabled | ❌ Disabled |
| RUNNING | ❌ Disabled | ✅ Enabled | ❌ Disabled |
| FINISHED | ❌ Disabled | ❌ Disabled | ✅ Enabled |

---

## 🔄 SYSTEM ARCHITECTURE

```
┌──────────────┐
│  Dashboard   │ (Browser)
└──────┬───────┘
       │ HTTP POST /game/start, /game/finish
       ↓
┌──────────────┐
│ Backend API  │ (FastAPI)
└──────┬───────┘
       │ MQTT Publish aquabuzz/commands
       ↓
┌──────────────┐
│ MQTT Broker  │
└──────┬───────┘
       │ MQTT Subscribe
       ↓
┌──────────────┐
│ Serial GW    │ (Python)
│ Command      │ ← Dedicated thread
│ Worker       │
└──────┬───────┘
       │ Serial JSON {"cmd":"start"}
       ↓
┌──────────────┐
│   ESP32      │ (Firmware)
│   Command    │
│   Parser     │
└──────┬───────┘
       │
       ↓
   Game Logic
```

---

## 🧪 TESTING CHECKLIST

### Automated Tests ✅
```powershell
python -m pytest backend/tests -v
```
Expected: 33 passed

### Dashboard Control Tests ✅
```powershell
.\scripts\test-game-control.ps1
```

### SSE Connection Tests ✅
```powershell
.\scripts\test_sse_connection.ps1
```

### Manual Hardware Tests ✅
- [ ] Dashboard START triggers game
- [ ] Hit tracking works during dashboard game
- [ ] Dashboard FINISH calculates score correctly
- [ ] Physical maze start still works
- [ ] Physical finish contact still works
- [ ] SSE updates dashboard in real-time

---

## 📊 COMPARISON TABLE

| Feature | Working_1 | Working_2 |
|---------|:---------:|:---------:|
| Physical controls | ✅ | ✅ |
| SSE updates | ✅ | ✅ |
| Hit tracking | ✅ | ✅ |
| Dashboard START | ❌ | ✅ |
| Dashboard FINISH | ❌ | ✅ |
| Command parser | ❌ | ✅ |
| Command worker | ❌ | ✅ |
| Tests | 27 | 33 |

---

## 🐛 TROUBLESHOOTING

### Recovery Issues

**Problem**: Recovery fails  
**Solution**: Check for uncommitted changes
```powershell
git status
git stash  # If needed
```

**Problem**: Wrong commit after recovery  
**Solution**: Reset to tag explicitly
```powershell
git reset --hard working_2-dashboard-control-baseline
```

### Test Failures

**Problem**: Tests fail  
**Solution**: Install dependencies
```powershell
pip install -r backend/requirements.txt
```

**Problem**: Import errors  
**Solution**: Activate virtual environment
```powershell
.\.venv\Scripts\Activate.ps1
```

### Dashboard Connection Issues

**Problem**: Dashboard doesn't load  
**Solution**: Check backend is running
```powershell
# Should show backend, gateway, and broker running
Get-Process | Where-Object { $_.Name -like "*python*" -or $_.Name -like "*uvicorn*" }
```

**Problem**: START button doesn't work  
**Solution**: Check MQTT connection
```powershell
# Check backend logs for MQTT connection
# Check ESP32 serial monitor for command receipt
```

---

## 🔗 QUICK LINKS

- [Repository](https://github.com/SenpoAhJin/IoT_Intelligent_System)
- [Branch: working_2](https://github.com/SenpoAhJin/IoT_Intelligent_System/tree/working_2)
- [Tag: working_2-dashboard-control-baseline](https://github.com/SenpoAhJin/IoT_Intelligent_System/releases/tag/working_2-dashboard-control-baseline)
- [Commit: a474fc7](https://github.com/SenpoAhJin/IoT_Intelligent_System/commit/a474fc738e129853b98fae267bd2f8afc97b2294)

---

## 📝 NOTES

### Safe to Modify
- Dashboard styling and UI
- Documentation files
- Test files
- Configuration values

### Do NOT Modify (Without Backup)
- ESP32 firmware core logic
- Serial Gateway command worker
- MQTT message formats
- Database schema

### Before Making Changes

1. Create a new branch:
   ```powershell
   git checkout -b feature/my-change
   ```

2. Preserve working_2 as fallback:
   ```powershell
   # Always keep working_2 unchanged
   # working_2 is your safety net
   ```

---

## 🎓 KEY LEARNINGS

### What Makes Working_2 Special

1. **Unified Game Logic**: Dashboard commands use the SAME code path as physical controls
2. **Command Acknowledgment**: Every command gets explicit success/error response
3. **Thread Safety**: Dedicated command worker prevents race conditions
4. **Fail-Safe Design**: Physical controls always work, dashboard adds extra control

### Why This Architecture Works

- **Separation of Concerns**: Dashboard → API → MQTT → Gateway → ESP32
- **Event-Driven**: SSE ensures dashboard stays synchronized
- **Idempotent Commands**: Duplicate commands don't break the system
- **Observable**: Every step logs and can be monitored

---

## 🚨 IMPORTANT REMINDERS

⚠️ **Never force push to working_2**  
⚠️ **Always tag stable versions**  
⚠️ **Keep working_1 as baseline**  
⚠️ **Document all major changes**  
⚠️ **Test before committing**  

✅ **working_2 is production-ready**  
✅ **All tests passing**  
✅ **Hardware verified**  
✅ **Documentation complete**  

---

## 📞 SUPPORT

If recovery fails or tests don't pass:

1. Check full report: `WORKING_2_PRESERVATION_REPORT.md`
2. Review implementation: `PHASE_2B2_IMPLEMENTATION_REPORT.md`
3. Check testing guide: `PHASE_2B2_TESTING_GUIDE.md`
4. Verify environment files are configured correctly

---

**WORKING_2: DASHBOARD CONTROL COMPLETE. SYSTEM STABLE. RECOVERY READY.**

*Last updated: 2026-11-25*
