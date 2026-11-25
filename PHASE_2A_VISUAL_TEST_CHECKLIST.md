# PHASE 2A: VISUAL TEST CHECKLIST

**Test Date:** November 25, 2026  
**Dashboard URL:** http://localhost:3000  
**Browser:** Chrome/Edge (Chromium)

---

## DESKTOP TESTING (1920x1080)

### Game Control Card
- [ ] Card visible immediately after refresh button
- [ ] Blue gradient background (`#1e3a8a → #3b82f6`)
- [ ] "🎮 Game Control" header
- [ ] Status shows "⏸ WAITING" (yellow text)
- [ ] START GAME button visible and large
- [ ] Button shows green gradient
- [ ] Button text: "🚀 START GAME"
- [ ] Button is disabled (grayed out)
- [ ] Integration notice visible with gear icon
- [ ] Notice text mentions "Phase 2B"
- [ ] Notice mentions "existing hardware-triggered lifecycle"

### Button Interaction (Desktop)
- [ ] Click START GAME → Shows alert
- [ ] Alert mentions "Phase 2B"
- [ ] Alert mentions "integration pending"
- [ ] Alert mentions "existing hardware-triggered lifecycle"
- [ ] No actual game state changes
- [ ] Check browser console for log: "[GameControl] START GAME requested"

### Existing Sections (Verify Not Broken)
- [ ] "🔄 Refresh Now" button still works
- [ ] System Health card present
- [ ] Shows Backend API status
- [ ] Shows MQTT status
- [ ] Shows device status
- [ ] Top Scores card present
- [ ] Recent Activity card present
- [ ] Players & Performance card present
- [ ] All cards have proper spacing
- [ ] No layout overlaps

### Live Game Card (If Active Game Running)
- [ ] "LIVE GAME IN PROGRESS" card shows when game active
- [ ] Game Control shows "🔴 RUNNING (Hardware)" status
- [ ] Buttons remain disabled

---

## MOBILE TESTING (375x667 Simulated)

### Open Chrome DevTools
1. Press F12
2. Click "Toggle Device Toolbar" (Ctrl+Shift+M)
3. Select "iPhone SE" or similar

### Mobile Layout
- [ ] Game Control card full-width
- [ ] No horizontal scrolling
- [ ] START GAME button full-width
- [ ] Button height adequate for thumb (44px+)
- [ ] Text readable (no tiny fonts)
- [ ] Integration notice readable
- [ ] All cards stack vertically
- [ ] No text cutoff
- [ ] Proper padding maintained

### Touch Interaction (Simulated)
- [ ] Tap START GAME → Alert appears
- [ ] Alert is readable on mobile
- [ ] No accidental double-taps
- [ ] Button provides visual feedback

---

## TABLET TESTING (768x1024 Simulated)

### Open Chrome DevTools
1. Select "iPad Mini" or similar

### Tablet Layout
- [ ] Game Control card prominent
- [ ] Proper grid layout (not too stretched)
- [ ] Buttons appropriately sized
- [ ] Text scales well
- [ ] No awkward spacing

---

## BROWSER CONSOLE TESTS

### Check for Errors
```javascript
// Open console (F12)
// Look for:
✅ No red errors
✅ "[SSE] Connected to live events stream"
✅ "[Dashboard] API fetch: XXms, render: XXms"
✅ No duplicate EventSource warnings
✅ No "undefined" errors
```

### Test Game Control State
```javascript
// In console, type:
gameControlState
// Expected: "WAITING"

gameControlMetrics
// Expected: Object with startTime: null, hits: 0, etc.
```

---

## FUNCTIONAL TESTS

### SSE Connection
- [ ] Open Network tab (F12)
- [ ] Look for `/api/live` connection
- [ ] Status: 200 OK (pending)
- [ ] Type: eventsource
- [ ] Still connected after 30 seconds

### API Calls
- [ ] Network tab shows periodic `/api/health` calls
- [ ] Network tab shows `/api/runs?limit=10` calls
- [ ] All return 200 OK
- [ ] Polling interval: ~3 seconds (no active game)

### Data Display
- [ ] Recent runs show in Recent Activity
- [ ] Top scores show in leaderboard
- [ ] Player stats show in Players section
- [ ] All numbers match backend data

---

## BUTTON STATE TESTS

### START GAME Button
- [ ] Initial state: Visible, Disabled
- [ ] Cursor: not-allowed (when hovered)
- [ ] Opacity: 0.5 (grayed out)
- [ ] Click: Shows alert (despite disabled)

### FINISH GAME Button
- [ ] Initial state: Hidden (`display: none`)
- [ ] Not visible in WAITING state

### NEW GAME Button
- [ ] Initial state: Hidden (`display: none`)
- [ ] Not visible in WAITING state

---

## METRICS DISPLAY TESTS

### Metrics Container
- [ ] Initial state: Hidden (`display: none`)
- [ ] Not visible in WAITING state
- [ ] Grid prepared with 4 boxes:
  - Elapsed Time
  - Total Hits
  - Contact Time
  - Longest Hit

### Score Container
- [ ] Initial state: Hidden (`display: none`)
- [ ] Not visible in WAITING state

---

## INTEGRATION NOTICE TESTS

### Visual Elements
- [ ] Yellow/amber background (`rgba(251, 191, 36, 0.2)`)
- [ ] Yellow/amber border (2px solid `#fbbf24`)
- [ ] Gear icon (⚙️) visible
- [ ] Text centered
- [ ] Three lines of text:
  1. "Dashboard Controls Prepared"
  2. "ESP32 command integration pending (Phase 2B)"
  3. "Current system uses existing hardware-triggered game lifecycle"

### Content Verification
- [ ] Mentions "Phase 2B"
- [ ] Mentions "ESP32 command integration"
- [ ] Mentions "pending"
- [ ] Mentions "existing hardware-triggered"
- [ ] No typos
- [ ] Proper capitalization

---

## RESPONSIVE BREAKPOINT TESTS

### Narrow Desktop (1024px)
1. Resize browser to 1024px wide
- [ ] Layout adjusts smoothly
- [ ] No text overflow
- [ ] Cards remain readable

### Tablet Portrait (768px)
1. Resize to 768px
- [ ] Media query triggers
- [ ] Single-column layout
- [ ] Game Control full-width
- [ ] Buttons adapt

### Mobile (375px)
1. Resize to 375px
- [ ] Minimal layout
- [ ] All content accessible
- [ ] No horizontal scroll
- [ ] Touch targets adequate

---

## COLOR CONTRAST TESTS

### Accessibility
- [ ] Status text readable (WAITING yellow on blue)
- [ ] Button text readable (white on green/red/blue)
- [ ] Integration notice readable (dark text on light amber)
- [ ] All text meets WCAG AA standard

---

## ANIMATION TESTS

### Pulse Animation
- [ ] Status "RUNNING" (future) should pulse
- [ ] Smooth animation (no janky movement)
- [ ] 2-second cycle

### Button Hover
- [ ] Hover on START GAME → translateY(-2px)
- [ ] Smooth transition (0.2s)
- [ ] Box shadow appears
- [ ] Disabled button: no hover effect

### Button Active
- [ ] Click START GAME → translateY(-1px)
- [ ] Returns to normal after click
- [ ] Disabled button: no active effect

---

## CROSS-BROWSER TESTS

### Chrome (Primary)
- [ ] All features work
- [ ] No console errors
- [ ] Layout correct

### Edge (Chromium)
- [ ] All features work
- [ ] No console errors
- [ ] Layout correct

### Firefox
- [ ] All features work
- [ ] EventSource works
- [ ] Grid layout works
- [ ] No console errors

---

## PERFORMANCE TESTS

### Load Time
- [ ] Dashboard loads in <2 seconds
- [ ] No visible lag

### Scroll Performance
- [ ] Smooth scrolling
- [ ] No janky animations
- [ ] 60fps maintained

### Memory Usage
- [ ] Check Task Manager
- [ ] No memory leaks
- [ ] Stable over 5 minutes

---

## INTEGRATION WITH EXISTING FEATURES

### Refresh Button
- [ ] Click "🔄 Refresh Now"
- [ ] All sections update
- [ ] Game Control state preserved
- [ ] No errors

### SSE Events (If Available)
- [ ] Trigger a game event (hardware)
- [ ] Dashboard updates
- [ ] Game Control syncs with active run
- [ ] Shows "RUNNING (Hardware)" status

### Active Run Tracking
- [ ] If game active, verify sync
- [ ] Game Control reflects hardware state
- [ ] Buttons remain disabled

---

## FINAL CHECKLIST

### Documentation
- [ ] PHASE_2A_DASHBOARD_PREPARATION_REPORT.md created
- [ ] This checklist completed
- [ ] Screenshots captured (optional)

### Backup
- [ ] dashboard/index.html.backup-phase2a-* exists
- [ ] Backup file is valid HTML
- [ ] Rollback tested (optional)

### Git
- [ ] Changes reviewed
- [ ] No unintended modifications
- [ ] Ready for commit (but not committed per instructions)

### System State
- [ ] Backend still running
- [ ] MQTT still connected
- [ ] Dashboard still accessible
- [ ] No errors in backend logs

---

## PASS/FAIL CRITERIA

### ✅ PASS Requirements
- All existing functionality works
- Game Control card visible
- Buttons present and disabled
- Integration notice clear
- No console errors
- Mobile responsive
- No breaking changes

### ❌ FAIL Indicators
- Existing sections broken
- JavaScript errors
- Layout broken on mobile
- Buttons enabled (should be disabled)
- No integration notice
- Performance degradation
- Data not loading

---

**Test Status:** ⏳ Pending Manual Verification  
**Automated Tests:** ✅ All Passed  
**Manual Tests:** Requires visual inspection  

**Next Steps:**
1. Open http://localhost:3000 in browser
2. Walk through this checklist
3. Mark each item as checked
4. Document any issues found
5. Proceed to Phase 2B if all tests pass

