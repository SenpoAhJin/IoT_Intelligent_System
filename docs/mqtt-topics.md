# MQTT Topics and Message Format

## Topic Structure

All topics follow the pattern: `aquabuzz/<device_id>/<channel>`

## Device → Backend (Published by ESP32)

### Events: `aquabuzz/<device_id>/events`

All game events are published to this topic as JSON messages.

#### run_start
```json
{
  "device_id": "aquabuzz-001",
  "run_uid": "aquabuzz-001-5-23",
  "run_no": 23,
  "player_id": "alice",
  "event": "run_start",
  "t_ms": 0,
  "ts": "2024-11-23T10:15:30.123Z"
}
```

#### hit_start
```json
{
  "device_id": "aquabuzz-001",
  "run_uid": "aquabuzz-001-5-23",
  "run_no": 23,
  "player_id": "alice",
  "event": "hit_start",
  "hit": 3,
  "t_ms": 8421,
  "ts": "2024-11-23T10:15:38.544Z"
}
```

#### hit_end
```json
{
  "device_id": "aquabuzz-001",
  "run_uid": "aquabuzz-001-5-23",
  "run_no": 23,
  "player_id": "alice",
  "event": "hit_end",
  "hit": 3,
  "t_ms": 8651,
  "dur_ms": 230,
  "ts": "2024-11-23T10:15:38.774Z"
}
```

#### run_finish
```json
{
  "device_id": "aquabuzz-001",
  "run_uid": "aquabuzz-001-5-23",
  "run_no": 23,
  "player_id": "alice",
  "event": "run_finish",
  "t_ms": 12450,
  "hits": 4,
  "total_contact_ms": 890,
  "longest_hit_ms": 320,
  "hit_penalty_ms": 2000,
  "score": 20450,
  "ts": "2024-11-23T10:15:42.573Z"
}
```

#### run_cancel
```json
{
  "device_id": "aquabuzz-001",
  "run_uid": "aquabuzz-001-5-23",
  "run_no": 23,
  "player_id": "alice",
  "event": "run_cancel",
  "t_ms": 5240,
  "ts": "2024-11-23T10:15:35.363Z"
}
```

### Heartbeat: `aquabuzz/<device_id>/heartbeat`

Sent every 10 seconds to indicate device is alive.

```json
{
  "device_id": "aquabuzz-001",
  "ts": "2024-11-23T10:15:30.123Z"
}
```

## Backend → Device (Subscribed by ESP32)

### Configuration: `aquabuzz/<device_id>/config`

Backend publishes difficulty settings that the device applies to the next run.

```json
{
  "hit_penalty_ms": 2500,
  "free_hits": 1,
  "time_limit_ms": null,
  "fast_time_ms": 7000
}
```

**Fields**:
- `hit_penalty_ms`: Penalty added per hit (0-10000ms)
- `free_hits`: Number of hits that don't count (0-10)
- `time_limit_ms`: Optional time limit, null = no limit (1000-300000ms)
- `fast_time_ms`: Optional fast time goal (1000-60000ms)

### Player Selection: `aquabuzz/<device_id>/player`

Backend can set the active player.

```json
"bob"
```

Simple string payload with player ID.

## Field Descriptions

### Common Fields

- `device_id`: Unique device identifier (configured in secrets.h)
- `run_uid`: Globally unique run identifier: `<device_id>-<boot_count>-<run_no>`
- `run_no`: Run number since boot (increments on each run)
- `player_id`: Current player identifier (default: "guest")
- `event`: Event type (run_start, hit_start, hit_end, run_finish, run_cancel)
- `ts`: UTC timestamp (ISO 8601 format), only present after NTP sync

### Timing Fields

- `t_ms`: Milliseconds since run start (relative time within run)
- `dur_ms`: Duration of event in milliseconds
- `hit_penalty_ms`: Penalty per hit in milliseconds (for score calculation)

### Hit Fields

- `hit`: Hit number within run (1-indexed)
- `hits`: Total number of hits in run
- `total_contact_ms`: Sum of all hit durations
- `longest_hit_ms`: Duration of longest single hit

### Score

- `score`: Final score = `duration_ms + (hits - free_hits) * hit_penalty_ms`

## Message Ordering

Events for a single run arrive in this order:

1. `run_start` (once)
2. `hit_start` / `hit_end` pairs (zero or more)
3. `run_finish` or `run_cancel` (once)

The backend must handle:
- **Out-of-order delivery**: MQTT QoS 0 doesn't guarantee order
- **Duplicate events**: Network retries may cause duplicates
- **Missing events**: Lost packets (use run_finish as source of truth)

## Idempotency

Backend should process events idempotently using `(run_uid, event, hit)` as a unique key:
- Multiple `run_start` with same `run_uid` → update, don't duplicate
- Multiple `hit_end` with same `(run_uid, hit)` → ignore duplicates
- `run_finish` is authoritative for final stats

## Testing with mosquitto_sub

Subscribe to all events:
```bash
mosquitto_sub -h localhost -t 'aquabuzz/#' -v
```

Subscribe to specific device:
```bash
mosquitto_sub -h localhost -t 'aquabuzz/aquabuzz-001/#' -v
```

## Testing with mosquitto_pub

Set player:
```bash
mosquitto_pub -h localhost -t 'aquabuzz/aquabuzz-001/player' -m '"bob"'
```

Push difficulty config:
```bash
mosquitto_pub -h localhost -t 'aquabuzz/aquabuzz-001/config' \
  -m '{"hit_penalty_ms":3000,"free_hits":2,"time_limit_ms":null,"fast_time_ms":null}'
```

## QoS Recommendations

- **Device → Backend**: QoS 0 (fire and forget) for performance
- **Backend → Device**: QoS 1 (at least once) for config reliability

## Retained Messages

No messages should be retained. Each run is a unique sequence of events.
