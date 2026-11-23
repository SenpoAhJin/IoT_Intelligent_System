# AquaBuzz System Architecture

## Overview

AquaBuzz is a distributed IoT system combining embedded real-time control, message-based integration, RESTful services, and machine learning intelligence.

## Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Physical Layer                            │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │  Maze Wire   │    │  Finish Pad  │    │    Buzzer    │     │
│  │   (GPIO 27)  │    │   (GPIO 33)  │    │   (GPIO 26)  │     │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘     │
│         └────────────────────┴────────────────────┘             │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────┴──────────────────────────────────┐
│                      ESP32 Firmware                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Main Loop (Core 1, highest priority)                      │ │
│  │  - driveBuzzerNow() - instant response (<1ms)              │ │
│  │  - updateContacts() - 20ms debounced state machine         │ │
│  │  - handleSerialCommand() - non-blocking                    │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  FreeRTOS Tasks (Core 0, background)                       │ │
│  │  ├─ serialTask: Queue-based printing                       │ │
│  │  ├─ wifiTask: Connection management                        │ │
│  │  └─ mqttTask: Publish events, subscribe config             │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Persistent Storage (NVS)                                  │ │
│  │  - boot_count (incremented on each boot)                   │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────┬───────────────────────────────────┘
                              │ MQTT (QoS 0/1)
                              │ WiFi
┌─────────────────────────────┴───────────────────────────────────┐
│                    Mosquitto MQTT Broker                         │
│  - Topics: aquabuzz/{device_id}/{events,heartbeat,config}       │
│  - Port 1883 (plain MQTT)                                       │
│  - Port 9001 (WebSocket, future)                                │
└─────────────────────────────┬───────────────────────────────────┘
                              │
            ┌─────────────────┴─────────────────┐
            │                                   │
┌───────────┴────────┐              ┌───────────┴────────┐
│  Python Backend    │              │   Dashboard (Web)  │
│  (FastAPI)         │◄─────REST────┤   (HTML/JS)        │
└───────────┬────────┘              └────────────────────┘
            │
            ├─ MQTT Subscriber (ingests events)
            ├─ SQLite Database (runs, hits, players, devices)
            ├─ Intelligence Engine (features, ML, suggestions)
            └─ REST API (queries, insights, config push)
```

## Layer Responsibilities

### 1. Physical Layer
- Maze wire: conductive path the player must avoid
- Finish pad: target endpoint (electrically isolated from maze)
- Buzzer: immediate audio feedback on contact
- Ring: player-held grounded probe

### 2. Firmware Layer (ESP32)

#### Real-Time Loop (Core 1)
- **Sub-millisecond response**: `driveBuzzerNow()` runs first every loop iteration
- **No blocking**: Zero delays, no network calls, no Serial.print() in loop
- **Debounced state machine**: 20ms debounce for counting/timing, instant buzzer
- **Interrupt-free**: Uses polling for maximum determinism

#### Background Tasks (Core 0, FreeRTOS)
- **Serial Task**: Consumes print queue, never blocks game logic
- **WiFi Task**: Manages connection, reconnects on failure
- **MQTT Task**: 
  - Publishes events (run_start, hit_start, hit_end, run_finish, heartbeat)
  - Subscribes to config updates
  - Buffers events if offline (future: persistent queue)

#### Unique Run Identification
- `run_uid = device_id + "-" + boot_count + "-" + run_no`
- `boot_count` persisted in NVS, incremented on boot
- Ensures global uniqueness across reboots

### 3. Message Broker (Mosquitto)
- **Pub/Sub hub**: Decouples device from backend
- **QoS 0 for events**: Low latency, tolerates drops (run_finish is authoritative)
- **QoS 1 for config**: Ensures delivery of difficulty updates
- **Stateless**: No retained messages, each run is ephemeral

### 4. Backend Layer (Python FastAPI)

#### Components
1. **MQTT Subscriber**
   - Runs in background thread
   - Ingests events, creates/updates database records
   - Idempotent by `(run_uid, event, hit)`

2. **Database (SQLite + SQLAlchemy)**
   - `players`: Player records
   - `devices`: Device registry with heartbeat tracking
   - `runs`: Run records with timing and score
   - `hits`: Individual hit records per run
   - `suggestions`: Generated insights

3. **Intelligence Engine** (intelligence/ package)
   - **features.py**: Extract timing, hit rate, clustering metrics
   - **behavior.py**: Tag patterns (dragging, overshooting, rushing)
   - **classifier.py**: Rule-based + ML skill classification
   - **trends.py**: Linear regression on recent performance
   - **anomalies.py**: Detect wiring errors, stuck contacts, offline devices
   - **suggestions.py**: Generate actionable advice
   - **difficulty.py**: Adaptive penalty recommendation
   - **llm_coach.py**: Optional Claude-based natural language feedback

4. **REST API**
   - `GET /api/runs`: Query run history
   - `GET /api/leaderboard`: Top scores
   - `GET /api/players`: Player stats and skill levels
   - `GET /api/insights/{player_id}`: Full intelligence analysis
   - `POST /api/devices/{id}/config`: Push difficulty to device via MQTT

5. **Live Updates** (future)
   - Server-Sent Events (SSE) or WebSocket
   - Stream new runs to dashboard in real-time

### 5. Dashboard Layer
- **Static HTML/JS**: Minimal dependencies, mobile-friendly
- **Polling**: Auto-refresh every 5s (future: SSE push)
- **Views**:
  - System health (MQTT status, run count)
  - Leaderboard (top 10 scores)
  - Recent runs
  - Player list with skill badges

## Data Flow

### Game Run Lifecycle

```
1. Player touches maze wire (first time)
   ├─ ESP32: state → RUNNING, start timer
   ├─ ESP32: publish run_start
   └─ Backend: create Run record

2. Player touches maze wire (subsequent)
   ├─ ESP32: buzzer ON (instant)
   ├─ ESP32: publish hit_start
   ├─ Backend: prepare Hit record
   └─ (player releases)
       ├─ ESP32: buzzer OFF
       ├─ ESP32: publish hit_end
       └─ Backend: complete Hit record

3. Player touches finish pad
   ├─ ESP32: state → FINISHED, calculate stats
   ├─ ESP32: publish run_finish (authoritative)
   └─ Backend:
       ├─ Update Run record (duration, score, hits)
       ├─ Extract features
       ├─ Analyze behavior → tags
       ├─ Classify skill
       ├─ Detect anomalies
       ├─ Generate suggestions
       └─ Store Suggestion records

4. User views dashboard
   ├─ Browser: GET /api/runs
   ├─ Backend: query database
   └─ Browser: render stats
```

## Intelligence Pipeline

```
Raw Run Data
    │
    ├─ Feature Extraction
    │   ├─ avg_hit_duration_ms
    │   ├─ hits_per_second
    │   ├─ time_to_first_hit_ms
    │   └─ ...
    │
    ├─ Behavior Analysis
    │   ├─ dragging (avg duration >= 400ms)
    │   ├─ overshooting (avg duration <= 120ms)
    │   └─ rushing (fast + many hits)
    │
    ├─ Skill Classification
    │   ├─ ML Model (if >30 runs, trained decision tree)
    │   └─ Rule-based fallback
    │       ├─ expert: score < 8s, hits <= 2
    │       ├─ intermediate: score < 15s, hits <= 5
    │       └─ beginner: else
    │
    ├─ Trend Detection
    │   ├─ Linear regression on last 10 runs
    │   └─ improving / stable / declining
    │
    ├─ Anomaly Detection
    │   ├─ too_fast (<500ms, wiring error)
    │   ├─ stuck_contact (>10s single hit)
    │   └─ excessive_hits (>50 hits)
    │
    ├─ Difficulty Recommendation
    │   ├─ 3+ clean runs → increase penalty
    │   ├─ 3+ struggles → decrease penalty, add free hits
    │   └─ 1-3 hits average → balanced, no change
    │
    └─ Suggestion Generation
        ├─ Behavior advice
        ├─ Skill feedback
        ├─ Trend encouragement/warning
        └─ Anomaly alerts
```

## Concurrency Model

### Firmware (ESP32)
- **Core 1**: Game loop (time-critical, polling)
- **Core 0**: FreeRTOS tasks (networking, logging)
- **Queues**: Lock-free communication between cores

### Backend (Python)
- **Main thread**: FastAPI async request handling
- **MQTT thread**: Background subscriber (daemon thread)
- **Database**: SQLite with write serialization (single writer)

## Fault Tolerance

### Device Offline
- Backend: Detect missing heartbeats (60s threshold)
- Dashboard: Show device offline status
- Firmware: Queue events in RAM (up to 100), send when reconnected

### MQTT Broker Down
- Firmware: Game continues normally, events lost
- Backend: Reconnects automatically
- Note: Events during outage are lost (acceptable for demo)

### Backend Crash
- MQTT broker retains events briefly
- Dashboard shows API error
- Restart backend, historical data persists (SQLite)

### Database Corruption
- Backup sqlite file regularly
- Use write-ahead log (WAL) mode for crash recovery

## Security Considerations

### Current (Demo)
- No authentication on MQTT
- No TLS/SSL
- Backend listens on all interfaces

### Production Recommendations
- MQTT username/password or client certificates
- TLS 1.3 for MQTT and API
- API key or JWT authentication
- Rate limiting on API endpoints
- Input validation on all MQTT messages

## Performance Characteristics

### Firmware
- **Buzzer latency**: <1ms (measured from contact to audible sound)
- **Loop frequency**: ~1kHz (varies, not critical as long as >500Hz)
- **Event publishing**: Non-blocking, queued

### Backend
- **Event ingestion**: ~1000 events/sec (single thread, unbatched)
- **API response**: <50ms for typical queries
- **Intelligence analysis**: ~10ms per run (synchronous on run_finish)

### Network
- **Event size**: 100-300 bytes JSON
- **Bandwidth**: <1KB/s per device (typical)
- **Latency tolerance**: Events can arrive 1-2s delayed with no impact

## Deployment Topologies

### Development (Local)
```
Laptop: docker-compose up
├─ Mosquitto (1883)
├─ Backend (8000)
└─ Dashboard (3000)

ESP32: connects to laptop WiFi, MQTT_BROKER=192.168.x.x
```

### Production (Cloud)
```
Cloud VM:
├─ Mosquitto (1883, TLS)
├─ Backend (8000, behind nginx)
└─ PostgreSQL (instead of SQLite)

Devices: connect over internet

Dashboard: static hosting (S3, Cloudflare Pages)
```

## Future Enhancements

1. **Persistent event queue**: Firmware stores events in SPIFFS if offline
2. **NTP time sync**: Accurate timestamps instead of relative `t_ms`
3. **WebSocket/SSE**: Real-time dashboard updates
4. **Multi-device support**: Multiple mazes, aggregate leaderboard
5. **Touch position tracking**: Additional sensors to identify trouble spots
6. **Video recording**: Sync run video with event timeline
7. **Mobile app**: React Native or Flutter companion app
8. **Cloud training**: Upload anonymized runs to train global ML model

## References

- [ESP32 FreeRTOS Documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/system/freertos.html)
- [MQTT 3.1.1 Specification](https://mqtt.org/mqtt-specification/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [scikit-learn Decision Trees](https://scikit-learn.org/stable/modules/tree.html)
