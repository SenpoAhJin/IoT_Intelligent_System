# WORKING_1 BASELINE — QUICK REFERENCE CARD

**Date Preserved:** November 25, 2026  
**Status:** ✅ Complete and Verified

---

## 🔗 GitHub Links

**Repository:** https://github.com/SenpoAhJin/IoT_Intelligent_System.git

**Branch:** [`working_1`](https://github.com/SenpoAhJin/IoT_Intelligent_System/tree/working_1)

**Tag:** [`working_1-baseline`](https://github.com/SenpoAhJin/IoT_Intelligent_System/releases/tag/working_1-baseline)

**Commit:** [`08fa7ab`](https://github.com/SenpoAhJin/IoT_Intelligent_System/commit/08fa7ab7dd590bb60b2826b06d614910b3c1f62f)

---

## ⚡ Quick Recovery

```powershell
.\scripts\restore-working-1.ps1
```

That's it! The script handles everything automatically.

---

## 🎯 What's Preserved

✅ **Complete Working System:**
- Dashboard with real-time updates
- FastAPI backend + MQTT
- Serial Gateway (ESP32 auto-detect)
- Database models & persistence
- ESP32 firmware source (unchanged)
- RISE startup/shutdown scripts
- Full test suite
- Complete documentation

✅ **Recovery Tools:**
- Automated restoration script
- Database backup (65 KB)
- Preservation documentation

✅ **Security:**
- No secrets committed
- .env properly gitignored
- Database excluded from repo

---

## 📋 Manual Recovery (If Needed)

```powershell
# 1. Fetch from GitHub
git fetch origin working_1
git fetch origin refs/tags/working_1-baseline:refs/tags/working_1-baseline

# 2. Switch to baseline
git checkout -b working_1 working_1-baseline

# 3. Restore database (optional)
Copy-Item "backups\aquabuzz-working1-20261125-111944.db" "backend\aquabuzz.db" -Force

# 4. Install & configure
pip install -r backend\requirements.txt
# Edit backend\.env with your settings

# 5. Start system
rise
```

---

## 🚀 Starting Development from Baseline

```powershell
# Create feature branch from baseline
git checkout -b feature/your-feature working_1-baseline

# Work on your feature...

# When ready to integrate
git checkout working_1
git merge feature/your-feature
```

---

## 🔧 Key Files

| File | Purpose |
|------|---------|
| `scripts/restore-working-1.ps1` | Automated recovery |
| `WORKING_1_BASELINE_PRESERVATION.md` | Full documentation |
| `WORKING_1_PRESERVATION_REPORT.md` | Preservation results |
| `backups/aquabuzz-working1-*.db` | Database backup |
| `backend/.env.example` | Environment template |

---

## ⚠️ Important Rules

### Firmware Development
- ❌ **NO automated firmware modification**
- ✅ Manual development via Arduino IDE only
- ✅ Manual upload to ESP32
- ✅ Manual commit after verification

### Database Management
- ❌ **NO auto-clearing or recreation**
- ✅ Manual backups before changes
- ✅ Restore from `backups/` if needed

### Security
- ❌ **NEVER commit `.env` or `secrets.h`**
- ✅ Use `.env.example` as template
- ✅ Configure locally after clone

---

## 📊 Preservation Metrics

| Item | Status |
|------|--------|
| System Components | ✅ 10/10 |
| Documentation | ✅ Complete |
| Security Checks | ✅ Passed |
| GitHub Push | ✅ Verified |
| Recovery Tools | ✅ Tested |
| Firmware Policy | ✅ Enforced |

---

## 🆘 If Something Breaks

```powershell
# Quick recovery to known-good state
.\scripts\restore-working-1.ps1

# Or manual reset
git checkout working_1
git reset --hard working_1-baseline
```

**This baseline is your safety net.** Use it whenever you need to get back to a working state.

---

## 📞 Support Resources

- **Full Preservation Documentation:** `WORKING_1_BASELINE_PRESERVATION.md`
- **Preservation Report:** `WORKING_1_PRESERVATION_REPORT.md`
- **Quickstart Guide:** `QUICKSTART_GUIDE.md`
- **Getting Started:** `START_HERE.md`

---

**STABILITY FIRST. SAVE EVERYTHING. PRESERVE THE FIRMWARE.**

*Keep this reference handy for quick access to baseline recovery.*
