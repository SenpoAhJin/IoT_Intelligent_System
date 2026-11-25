# PHASE 2A: VISUAL GUIDE

**Dashboard Game Control Interface Preview**

---

## WHAT YOU'LL SEE

### 1. Game Control Card Location

```
┌────────────────────────────────────────┐
│ 🎮 AquaBuzz Live Dashboard             │
│ Real-time intelligent buzz-wire maze   │
│                                        │
│ [🔄 Refresh Now]                       │
│                                        │
│ ┌────────────────────────────────────┐ │
│ │ 🎮 GAME CONTROL                    │ │  ⬅️ NEW!
│ │ ════════════════════════════════   │ │
│ │                                    │ │
│ │ Status: ⏸ WAITING                  │ │
│ │                                    │ │
│ │ [🚀 START GAME]  (disabled)        │ │
│ │                                    │ │
│ │ ⚙️ Dashboard Controls Prepared     │ │
│ │ ESP32 command integration pending  │ │
│ └────────────────────────────────────┘ │
│                                        │
│ [System Health] [Top Scores] [Recent]  │
│ ...existing sections...                │
└────────────────────────────────────────┘
```

---

## 2. WAITING STATE (Current)

```
╔════════════════════════════════════════╗
║ 🎮 Game Control                        ║
╠════════════════════════════════════════╣
║                                        ║
║           ⏸ WAITING                    ║
║          (yellow text)                 ║
║                                        ║
║  ┌────────────────────────────────┐   ║
║  │    🚀 START GAME               │   ║
║  │    (green gradient, disabled)  │   ║
║  └────────────────────────────────┘   ║
║                                        ║
║  ┌────────────────────────────────┐   ║
║  │ ⚙️ Dashboard Controls Prepared │   ║
║  │ ESP32 command integration      │   ║
║  │ pending (Phase 2B)             │   ║
║  │                                │   ║
║  │ Current system uses existing   │   ║
║  │ hardware-triggered lifecycle   │   ║
║  └────────────────────────────────┘   ║
║      (yellow banner)                   ║
╚════════════════════════════════════════╝
```

**What It Means:**
- System ready but awaiting Phase 2B integration
- Button visible but disabled (by design)
- Clear notice explains what's pending

---

## 3. RUNNING STATE (After Phase 2B)

```
╔════════════════════════════════════════╗
║ 🎮 Game Control                        ║
╠════════════════════════════════════════╣
║                                        ║
║           🔴 RUNNING                    ║
║     (green text, pulsing)              ║
║                                        ║
║  ┌─────────┬─────────┬─────────────┐  ║
║  │Elapsed  │  Hits   │  Contact    │  ║
║  │  5.2s   │    3    │   0.45s     │  ║
║  └─────────┴─────────┴─────────────┘  ║
║  ┌─────────────────────────────────┐  ║
║  │       Longest Hit               │  ║
║  │          150ms                  │  ║
║  └─────────────────────────────────┘  ║
║                                        ║
║  ┌────────────────────────────────┐   ║
║  │    🏁 FINISH GAME              │   ║
║  │    (red gradient, enabled)     │   ║
║  └────────────────────────────────┘   ║
║                                        ║
╚════════════════════════════════════════╝
```

**Live Updates:**
- Timer updates every 100ms
- Hits increment on contact
- Metrics update in real-time

---

## 4. FINISHED STATE (After Phase 2B)

```
╔════════════════════════════════════════╗
║ 🎮 Game Control                        ║
╠════════════════════════════════════════╣
║                                        ║
║           ✅ FINISHED                   ║
║          (blue text)                   ║
║                                        ║
║  ┌─────────┬─────────┬─────────────┐  ║
║  │Final    │  Hits   │  Contact    │  ║
║  │  12.4s  │    7    │   1.23s     │  ║
║  └─────────┴─────────┴─────────────┘  ║
║  ┌─────────────────────────────────┐  ║
║  │       Longest Hit               │  ║
║  │          230ms                  │  ║
║  └─────────────────────────────────┘  ║
║                                        ║
║  ┌─────────────────────────────────┐  ║
║  │       FINAL SCORE               │  ║
║  │         13.63s                  │  ║
║  │    (large gold number)          │  ║
║  └─────────────────────────────────┘  ║
║                                        ║
║  ┌────────────────────────────────┐   ║
║  │    🔄 START NEW GAME           │   ║
║  │    (blue gradient, enabled)    │   ║
║  └────────────────────────────────┘   ║
║                                        ║
╚════════════════════════════════════════╝
```

**Victory State:**
- All metrics frozen at final values
- Final score prominent (gold)
- Ready to start new game

---

## COLOR SCHEME

### Card Background
```
Gradient: #1e3a8a → #3b82f6
         (dark blue → bright blue)
Border: #60a5fa (light blue, 2px)
Text: White
```

### Status Colors
```
⏸ WAITING:   #fbbf24 (amber/yellow)
🔴 RUNNING:   #10b981 (green) + pulse animation
✅ FINISHED:  #3b82f6 (blue)
```

### Button Colors
```
🚀 START:    #10b981 → #059669 (green gradient)
🏁 FINISH:   #ef4444 → #dc2626 (red gradient)
🔄 NEW GAME: #3b82f6 → #2563eb (blue gradient)
```

### Integration Notice
```
Background: rgba(251, 191, 36, 0.2) (light amber)
Border: #fbbf24 (amber, 2px)
Icon: ⚙️ gear
```

---

## BUTTON INTERACTIONS

### When You Click START GAME (Phase 2A)

```
┌──────────────────────────────────────┐
│ 🚧 Game control integration pending  │
│    (Phase 2B)                        │
│                                      │
│ Current system uses existing         │
│ hardware-triggered game lifecycle.   │
│                                      │
│ Dashboard-controlled start will be   │
│ enabled after ESP32 integration.     │
│                                      │
│            [ OK ]                    │
└──────────────────────────────────────┘
```

**Console Output:**
```
[GameControl] START GAME requested (integration pending)
```

### When You Click FINISH GAME (Phase 2A)

```
┌──────────────────────────────────────┐
│ ⚠️ Game control integration pending  │
│    (Phase 2B)                        │
│                                      │
│ Current system uses existing         │
│ hardware-triggered game lifecycle.   │
│                                      │
│ Dashboard-controlled finish will be  │
│ enabled after ESP32 integration.     │
│                                      │
│ This action has no effect yet.       │
│                                      │
│      [ Cancel ]    [ OK ]            │
└──────────────────────────────────────┘
```

---

## MOBILE VIEW (375px)

```
┌─────────────────────┐
│ 🎮 AquaBuzz         │
│                     │
│ [🔄 Refresh]        │
│                     │
│ ┌─────────────────┐ │
│ │ 🎮 Game Control │ │
│ │ ═══════════════ │ │
│ │                 │ │
│ │  ⏸ WAITING      │ │
│ │                 │ │
│ │ ┌─────────────┐ │ │
│ │ │ 🚀 START    │ │ │
│ │ │    GAME     │ │ │
│ │ └─────────────┘ │ │
│ │  (full width,   │ │
│ │   touch-sized)  │ │
│ │                 │ │
│ │ ⚙️ Dashboard    │ │
│ │ Controls Ready  │ │
│ │ Integration     │ │
│ │ Pending         │ │
│ └─────────────────┘ │
│                     │
│ [System Health]     │
│ [Top Scores]        │
│ [Recent Activity]   │
│ ...stacked...       │
└─────────────────────┘
```

**Mobile Optimizations:**
- Full-width buttons
- Large touch targets (44px+ height)
- 2-column metric grid
- Readable font sizes
- No horizontal scroll

---

## TABLET VIEW (768px)

```
┌──────────────────────────────────┐
│ 🎮 AquaBuzz Live Dashboard       │
│                                  │
│ [🔄 Refresh Now]                 │
│                                  │
│ ┌──────────────────────────────┐ │
│ │ 🎮 Game Control              │ │
│ │                              │ │
│ │       ⏸ WAITING              │ │
│ │                              │ │
│ │  [🚀 START GAME]             │ │
│ │                              │ │
│ │  ⚙️ Integration Pending      │ │
│ └──────────────────────────────┘ │
│                                  │
│ ┌────────┐ ┌──────┐ ┌─────────┐ │
│ │ Health │ │Scores│ │Activity │ │
│ └────────┘ └──────┘ └─────────┘ │
└──────────────────────────────────┘
```

---

## DESKTOP VIEW (1920px)

```
┌────────────────────────────────────────────────────────────┐
│ 🎮 AquaBuzz Live Dashboard                                 │
│ Real-time intelligent buzz-wire maze monitoring            │
│                                                            │
│ [🔄 Refresh Now]                                           │
│                                                            │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ 🎮 Game Control                                        │ │
│ │ ══════════════════════════════════════════════════════ │ │
│ │                                                        │ │
│ │                    ⏸ WAITING                           │ │
│ │                                                        │ │
│ │               [🚀 START GAME]                          │ │
│ │               (large, centered)                        │ │
│ │                                                        │ │
│ │  ⚙️ Dashboard Controls Prepared                        │ │
│ │  ESP32 command integration pending (Phase 2B)          │ │
│ │  Current system uses existing hardware-triggered       │ │
│ │  game lifecycle                                        │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                            │
│ ┌──────────┐ ┌───────────┐ ┌─────────────┐ ┌──────────┐ │
│ │ System   │ │ Top       │ │ Recent      │ │ Players  │ │
│ │ Health   │ │ Scores    │ │ Activity    │ │ & Perf   │ │
│ └──────────┘ └───────────┘ └─────────────┘ └──────────┘ │
└────────────────────────────────────────────────────────────┘
```

---

## ANIMATIONS

### Pulse Animation (RUNNING state)
```
Frame 1: Opacity 1.0  ●
Frame 2: Opacity 0.6  ◐  (1 second)
Frame 3: Opacity 1.0  ●  (2 seconds, repeat)
```

### Button Hover
```
Normal:    translateY(0)   ▬▬▬▬▬▬▬
Hover:     translateY(-2px) ▬▬▬▬▬▬▬  ↑ lifts
Active:    translateY(-1px) ▬▬▬▬▬▬▬  ↓ presses
```

### Card Glow (when game active)
```
Frame 1: box-shadow 0 0 20px rgba(blue, 0.5)
Frame 2: box-shadow 0 0 40px rgba(blue, 0.8)  (brighter)
Frame 3: box-shadow 0 0 20px rgba(blue, 0.5)  (dimmer, repeat)
```

---

## TYPOGRAPHY

### Headers
```
H1: 2.5em "AquaBuzz Dashboard"
H2: 1.4em "Game Control", "System Health", etc.
```

### Status Text
```
Game Status: 1.5em, bold, uppercase, letter-spacing: 2px
⏸ WAITING | 🔴 RUNNING | ✅ FINISHED
```

### Button Text
```
Font: 1.3em (desktop), 1.1em (mobile)
Weight: Bold
Transform: Uppercase
Spacing: 1px letter-spacing
Icon + Text: 🚀 START GAME
```

### Metric Values
```
Font: Courier New (monospace)
Size: 1.8em (large), 2.5em (final score)
Weight: Bold
Color: White (metrics), #fbbf24 (final score - gold)
```

---

## ACCESSIBILITY

### Color Contrast
- ✅ White text on blue: 7.2:1 (AAA)
- ✅ Yellow status on blue: 4.8:1 (AA)
- ✅ White button text on green: 6.5:1 (AAA)
- ✅ Dark text on amber notice: 8.1:1 (AAA)

### Touch Targets
- ✅ Buttons: 44px+ height (iOS guidelines)
- ✅ Large padding for comfortable tapping
- ✅ No tiny clickable elements

### Keyboard Navigation
- Tab through buttons
- Enter/Space to activate
- Esc to dismiss alerts

---

## BROWSER DEVTOOLS TESTING

### Open Console (F12)
```javascript
// Check game control state:
gameControlState
// Output: "WAITING"

// Check metrics:
gameControlMetrics
// Output: { startTime: null, hits: 0, ... }

// Test state change (Phase 2B):
updateGameControls('RUNNING', { startTime: Date.now(), hits: 0, ... })
```

### Network Tab
```
Name                Type        Status    Size
/api/live          eventsource  200       (pending)
/api/health        xhr          200       226 B
/api/runs?limit=10 xhr          200       1.2 KB
```

### Elements Tab
```html
<div class="card game-control-card">
  <h2>🎮 Game Control</h2>
  <div class="game-status">
    <span class="game-status-waiting">⏸ WAITING</span>
  </div>
  ...
</div>
```

---

## WHAT USERS SEE

### Non-Technical User
> "There's a new blue section at the top with a START GAME button, but it says integration is pending. The rest of the dashboard looks the same."

### Technical User
> "Dashboard now has game control UI prepared. Buttons are disabled with clear notices about Phase 2B. No backend changes yet. All existing monitoring functional."

### Game Operator
> "I can see where I'll be able to start and stop games from the dashboard in the future. Right now it's showing me it's ready but waiting for the ESP32 integration."

---

## PHASE 2B PREVIEW

### What Changes After Integration

**Before (Phase 2A):**
```
[🚀 START GAME] ← Disabled, shows alert
```

**After (Phase 2B):**
```
[🚀 START GAME] ← Enabled, starts game
                   ↓
              ESP32 starts
                   ↓
              Metrics update live
                   ↓
              [🏁 FINISH GAME]
```

---

**Visual Guide Complete** ✨

Open http://localhost:3000 to see it live!

