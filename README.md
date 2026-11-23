# AquaBuzz Intelligent IoT System

An intelligent buzz-wire maze game system with real-time monitoring, behavior analysis, and adaptive difficulty. Built with ESP32, MQTT, Python FastAPI, and machine learning.

## 🎯 Overview

AquaBuzz is a physical buzz-wire maze game enhanced with IoT intelligence. Players guide a metal ring along a maze wire without touching it. The system tracks every touch, analyzes playing patterns, provides personalized feedback, and adapts difficulty in real-time.

### Key Features

- **Instant Response**: Sub-millisecond buzzer reaction using FreeRTOS on ESP32
- **Intelligent Analysis**: ML-powered skill classification and behavior pattern detection
- **Real-time Dashboard**: Live game monitoring with SSE/WebSocket updates
- **Adaptive Difficulty**: Dynamic penalty adjustment based on player performance
- **Offline Resilient**: Game works without network, syncs when connected
- **Multi-player**: Track and compare performance across multiple players

## 🔌 Hardware Wiring

**Board**: ESP32 Dev Module

| Component | ESP32 Pin | Mode | Behavior |
|-----------|-----------|------|----------|
| Maze wire (START) | GPIO 27 | INPUT_PULLUP | LOW when ring touches wire |
| Finish pad | GPIO 33 | INPUT_PULLUP | LOW when ring touches finish |
| Buzzer (via MOSFET) | GPIO 26 | OUTPUT | HIGH = buzzer ON |

**Important**: The finish pad must be electrically separate from the maze wire. See [docs/wiring.md](docs/wiring.md) for details.

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for simulator and local development)
- Arduino IDE or arduino-cli (for firmware flashing)
- ESP32 board support in Arduino

### 1. Start the Backend Stack

```bash
# Start Mosquitto MQTT broker, backend API, and dashboard
docker compose up -d

# Check services are running
docker compose ps
```

Backend API: http://localhost:8000  
Dashboard: http://localhost:8000/dashboard  
API Docs: http://localhost:8000/docs

### 2. Flash the Firmware

#### Option A: Arduino IDE
1. Open `firmware/aquabuzz_connected/aquabuzz_connected.ino`
2. Copy `firmware/secrets.example.h` to `firmware/secrets.h`
3. Edit `secrets.h` with your Wi-Fi and MQTT credentials
4. Select **Tools > Board > ESP32 Dev Module**
5. Select your serial port
6. Upload

#### Option B: arduino-cli
```bash
# Configure secrets
cp firmware/secrets.example.h firmware/secrets.h
# Edit secrets.h with your credentials

# Compile and upload
arduino-cli compile --fqbn esp32:esp32:esp32 firmware/aquabuzz_connected
arduino-cli upload -p COM3 --fqbn esp32:esp32:esp32 firmware/aquabuzz_connected
```

### 3. Test with Simulator

```bash
# Generate realistic game runs without hardware
python tools/simulator.py --runs 50 --players 3

# Watch the dashboard update in real-time
```

## 📊 System Architecture

```
┌─────────────┐         MQTT          ┌──────────────┐
│   ESP32     │◄─────────────────────►│  Mosquitto   │
│  (Firmware) │   aquabuzz/+/events   │    Broker    │
└─────────────┘                       └───────┬──────┘
                                              │
                                              │ Subscribe
                                              ▼
┌─────────────┐         REST          ┌──────────────┐
│  Dashboard  │◄─────────────────────►│   FastAPI    │
│  (Web UI)   │    GET /api/runs      │   Backend    │
└─────────────┘    SSE /api/live      └───────┬──────┘
                                              │
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │  Intelligence    │
                                    │  - Classifier    │
                                    │  - Trends        │
                                    │  - Anomalies     │
                                    │  - Suggestions   │
                                    └──────────────────┘
```

## 🧠 Intelligence Features

### Behavior Analysis
- **Dragging**: Average touch duration ≥ 400ms
- **Overshooting**: Average touch duration ≤ 120ms  
- **Rushing**: Fast completion with many hits
- **Too Cautious**: Slow completion with zero hits

### Skill Classification
- **Beginner**: Score > 15s, many long touches
- **Intermediate**: Score 8-15s, moderate hits
- **Expert**: Score < 8s, few short touches

Uses scikit-learn decision tree trained on historical data (falls back to rules if <30 runs).

### Trend Detection
Linear regression on last 10 runs to identify improvement or decline.

### Anomaly Detection
- Finish < 500ms after start (wiring error)
- Touch > 10s duration (stuck contact)
- Missing device heartbeats
- Impossible hit rates

### Adaptive Difficulty
Recommends adjusted penalties based on recent performance:
- 3+ clean runs → harder (increase penalty)
- 3+ struggles → easier (reduce penalty)
- Optimal zone: 1-3 hits per run

## 🎮 Game Logic

### State Machine
```
WAITING → RUNNING → FINISHED → (5s lockout) → WAITING
```

### Timing Rules
1. **First maze touch**: Starts timer (not counted as hit)
2. **Subsequent touches**: Counted as hits with duration tracking
3. **Finish touch**: Ends run, calculates score
4. **Score formula**: `time_ms + (hits × penalty_ms)`

### Serial Commands
- `r` - Reset current run
- `s` - Print run summary
- `b` - Buzzer test (two beeps)

## 📡 MQTT Topics

### Device → Backend
- `aquabuzz/{device_id}/events` - Game events (run_start, hit_start, hit_end, run_finish, run_cancel)
- `aquabuzz/{device_id}/heartbeat` - Device health (every 10s)

### Backend → Device
- `aquabuzz/{device_id}/config` - Difficulty settings
- `aquabuzz/{device_id}/player` - Set active player

### Event Format
```json
{
  "device_id": "aquabuzz-001",
  "run_uid": "aquabuzz-001-5-23",
  "run_no": 23,
  "player_id": "alice",
  "event": "hit_end",
  "hit": 3,
  "t_ms": 8421,
  "dur_ms": 230,
  "ts": "2024-11-23T10:15:30.123Z"
}
```

## 🔧 Development

### Run Backend Locally
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Run Tests
```bash
cd backend
pytest tests/ -v --cov=app --cov=intelligence
```

### Compile Firmware
```bash
arduino-cli compile --fqbn esp32:esp32:esp32 firmware/aquabuzz_connected
```

## 🐛 Troubleshooting

### Finish Pad Triggers Immediately
**Problem**: Finish pad is wired to the maze wire  
**Solution**: Finish pad must be electrically isolated. Check with multimeter.

### Buzzer Doesn't Sound
**Problem**: MOSFET wiring or pin configuration  
**Solution**: Test with serial command `b`. Check GPIO 26 connection.

### Wi-Fi Won't Connect
**Problem**: Wrong credentials or weak signal  
**Solution**: Check `secrets.h`, monitor serial output at 115200 baud.

### MQTT Not Publishing
**Problem**: Broker unreachable or auth failure  
**Solution**: Verify broker IP, check mosquitto logs: `docker compose logs mqtt`

### Dashboard Shows No Data
**Problem**: Backend not receiving events  
**Solution**: 
1. Check MQTT connection: `mosquitto_sub -h localhost -t 'aquabuzz/#' -v`
2. Check backend logs: `docker compose logs backend`

See [docs/troubleshooting.md](docs/troubleshooting.md) for more details.

## 📁 Project Structure

```
IoT_Intelligent_System/
├── firmware/
│   ├── aquabuzz_core/           # Standalone game (v6)
│   │   └── aquabuzz_core.ino
│   ├── aquabuzz_connected/      # IoT-enabled version
│   │   └── aquabuzz_connected.ino
│   └── secrets.example.h
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── mqtt_client.py       # MQTT subscriber
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── schemas.py           # Pydantic schemas
│   │   └── db.py                # Database setup
│   ├── intelligence/
│   │   ├── features.py          # Feature extraction
│   │   ├── behavior.py          # Behavior analysis
│   │   ├── classifier.py        # Skill classification
│   │   ├── trends.py            # Trend detection
│   │   ├── anomalies.py         # Anomaly detection
│   │   ├── suggestions.py       # Suggestion engine
│   │   ├── difficulty.py        # Adaptive difficulty
│   │   └── llm_coach.py         # Optional LLM feedback
│   ├── tests/                   # Pytest unit tests
│   └── requirements.txt
├── dashboard/                   # Web UI
├── tools/
│   └── simulator.py             # Fake run generator
├── docs/
│   ├── architecture.md
│   ├── wiring.md
│   ├── mqtt-topics.md
│   └── troubleshooting.md
└── docker-compose.yml
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with clear commit messages
4. Add tests for new features
5. Submit a pull request

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built as an intelligent IoT demonstration project combining embedded systems, real-time processing, and machine learning.

---

**Status**: ✅ Fully functional  
**Last Updated**: 2024-11-23  
**Version**: 1.0.0
