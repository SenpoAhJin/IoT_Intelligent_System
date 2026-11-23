# AquaBuzz Wiring Guide

## Hardware Requirements

- ESP32 Dev Module
- Buzz-wire maze (metal wire bent into maze shape)
- Metal ring with handle (must fit over wire)
- Separate metal finish pad
- D4184 MOSFET module (or similar) for buzzer drive
- Active buzzer (5V)
- Jumper wires
- Power supply (USB or 5V)

## Pin Connections

| Component | ESP32 Pin | Type | Description |
|-----------|-----------|------|-------------|
| Maze Wire | GPIO 27 | INPUT_PULLUP | Main maze wire - connects to START |
| Finish Pad | GPIO 33 | INPUT_PULLUP | Separate metal pad at finish |
| Buzzer MOSFET | GPIO 26 | OUTPUT | Controls D4184 module signal |
| Ring Ground | GND | Ground | Metal ring connects to ESP32 ground |

## Wiring Diagram (Text)

```
ESP32                           Buzz-Wire Maze
┌─────────────┐                 
│             │                 
│  GPIO 27 ──┼────────────────► MAZE WIRE (START)
│             │                 
│  GPIO 33 ──┼────────────────► FINISH PAD (separate!)
│             │                 
│  GPIO 26 ──┼────► D4184 Signal
│             │      │
│  GND ───────┼──────┼─────────► RING HANDLE
│             │      │
│  VIN/5V ────┼──────┴─────────► D4184 VCC
│             │                 
│  GND ───────┼────────────────► D4184 GND
│             │      │
└─────────────┘      └──────────► BUZZER +

                     BUZZER - ──► D4184 OUT
```

## Critical Wiring Rules

### 1. Finish Pad MUST Be Separate

**WRONG**:
```
MAZE WIRE ━━━━━━━ [connected] ━━━━━ FINISH PAD
```

**CORRECT**:
```
MAZE WIRE ━━━━━━━     (gap)     ━━━━━ FINISH PAD
                   
      GPIO 27                      GPIO 33
```

If the finish pad touches the maze wire at any point, the game will finish instantly (<500ms). The firmware will log a warning: `{"warn":"finish_and_maze_both_low"}`.

### 2. Ground Connection

The metal ring held by the player MUST be connected to ESP32 GND. When the ring touches either the maze wire or finish pad, it creates a path to ground, pulling that GPIO LOW.

### 3. Pull-Up Configuration

Both GPIO 27 and GPIO 33 use `INPUT_PULLUP` mode. This means:
- **No contact**: Pin reads HIGH (default state)
- **Ring touches wire/pad**: Pin reads LOW (active state)

The firmware inverts this reading so LOW = contact detected.

### 4. Buzzer Driver

The D4184 MOSFET module:
- **Signal**: Connected to GPIO 26
- **VCC**: Connected to 5V (can share with ESP32 VIN)
- **GND**: Connected to ESP32 GND
- **OUT**: Connected to buzzer negative
- **Buzzer positive**: Connected to 5V

When GPIO 26 goes HIGH, the MOSFET switches and the buzzer sounds.

## Testing the Wiring

### Test 1: Continuity Check

Use a multimeter in continuity mode:

1. Touch probes to MAZE WIRE and FINISH PAD
   - Should show **OPEN** (no continuity)
   - If it beeps, they're connected - **FIX THIS**

2. Touch probes to RING and ESP32 GND
   - Should show **CONTINUITY** (connected)

3. Touch RING to MAZE WIRE while measuring GPIO 27 voltage
   - Should drop from ~3.3V to ~0V

### Test 2: Serial Monitor

Upload firmware and open serial monitor at 115200 baud:

1. **Power-on test**: Should hear two buzzer beeps
2. **Touch maze wire**: First touch starts run (no buzzer penalty)
3. **Touch maze wire again**: Counts as hit, buzzer sounds
4. **Touch finish pad**: Run ends, stats printed

### Test 3: Buzzer Command

Send `b` over serial:
- Should hear two short beeps
- If no sound, check MOSFET wiring

## Common Problems

### Problem: Buzzer doesn't sound
**Check**:
- MOSFET signal wire on GPIO 26
- MOSFET VCC has 5V
- Buzzer polarity (positive to 5V, negative to MOSFET OUT)
- Send `b` command to test

### Problem: Run finishes immediately
**Symptoms**: 
- Every run completes in <500ms
- Warning: `{"warn":"finish_and_maze_both_low"}`

**Cause**: Finish pad is electrically connected to maze wire

**Fix**: Physically separate the finish pad from the maze wire

### Problem: Finish pad doesn't work
**Check**:
- GPIO 33 connection to finish pad
- Finish pad is metal and conductive
- Ring is properly grounded

### Problem: First touch doesn't start run
**Check**:
- GPIO 27 connection to maze wire
- Ring is grounded
- Maze wire is conductive
- Wait 5 seconds after previous run (lockout period)

## Physical Construction Tips

1. **Maze wire**: Use solid core copper wire (18-22 AWG), easy to bend and holds shape
2. **Ring**: Use a keyring or bent wire, ensure good electrical contact
3. **Finish pad**: Use a coin, metal plate, or copper tape
4. **Isolation**: Mount finish pad on plastic/wood, keep clear of maze wire
5. **Ground wire**: Attach to ring with solder or tight mechanical connection

## Safety Notes

- Use low voltage only (5V max)
- Ensure no sharp edges on wire
- Secure all connections to prevent shorts
- Test thoroughly before extended use

## Verification Checklist

- [ ] GPIO 27 → Maze wire (START)
- [ ] GPIO 33 → Finish pad
- [ ] GPIO 26 → MOSFET signal
- [ ] GND → Ring handle
- [ ] Finish pad electrically separate from maze wire
- [ ] Buzzer sounds on power-up (two beeps)
- [ ] First maze touch starts run (no buzzer)
- [ ] Subsequent touches trigger buzzer
- [ ] Finish pad completes run

If all checks pass, your wiring is correct!
