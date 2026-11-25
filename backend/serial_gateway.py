"""
AquaBuzz Serial-to-MQTT Gateway v2
Reads JSON events from ESP32 via USB Serial and publishes to MQTT broker.
Handles event normalization, heartbeat publishing, and network independence.

PHASE 2B-2: Added command transport capability
- Subscribes to MQTT command topics
- Forwards commands to ESP32 via serial
- Tracks acknowledgments and timeouts
"""

import serial
import serial.tools.list_ports
import json
import time
import threading
import paho.mqtt.client as mqtt
import os
import sys
import uuid
import queue
from datetime import datetime
from typing import Optional, Dict

# Configuration
BAUD_RATE = 115200
DEVICE_ID = os.getenv("DEVICE_ID", "aquabuzz-001")
DEFAULT_PLAYER_ID = os.getenv("DEFAULT_PLAYER_ID", "guest")
MQTT_BROKER = os.getenv("MQTT_BROKER_HOST", "test.mosquitto.org")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", 1883))
MQTT_CLIENT_ID = "aquabuzz-serial-gateway"

# Reconnection settings
SERIAL_RETRY_DELAY = 5  # seconds
MQTT_RETRY_DELAY = 10  # seconds
HEARTBEAT_INTERVAL = 10  # seconds (backend expects heartbeat within 30s)

# Allow explicit COM port override
EXPLICIT_COM_PORT = os.getenv("COM_PORT", None)

# FEAT-002: Latency measurement configuration
GATEWAY_VERBOSE = os.getenv("GATEWAY_VERBOSE", "0") == "1"


class SerialGateway:
    """ESP32 Serial to MQTT gateway with event normalization."""
    
    def __init__(self):
        self.serial_port: Optional[serial.Serial] = None
        self.mqtt_client: Optional[mqtt.Client] = None
        self.mqtt_connected = False
        self.device_id = DEVICE_ID
        self.player_id = DEFAULT_PLAYER_ID
        self.running = True
        self.serial_connected = False
        
        # Session tracking
        self.gateway_session_id = str(uuid.uuid4())[:8]
        self.current_run_state: Optional[Dict] = None
        self.last_heartbeat_time = 0
        
        # Heartbeat thread
        self.heartbeat_thread = None
        
        # PHASE 2B-2: Command transport infrastructure
        self.command_queue = queue.Queue(maxsize=10)  # Command queue for serial transmission
        self.pending_commands = {}  # cmd_id → {"sent_at": time, "timeout": 5.0, "command": {...}}
        self.command_timeout_seconds = 5.0
        
        print(f"[Gateway] Session ID: {self.gateway_session_id}")
        
    def find_esp32_port(self) -> Optional[str]:
        """
        Auto-detect ESP32 COM port.
        Looks for common ESP32 USB-to-Serial chip identifiers.
        """
        # If explicit COM port specified, use it
        if EXPLICIT_COM_PORT:
            print(f"[Serial] Using explicit COM port: {EXPLICIT_COM_PORT}")
            return EXPLICIT_COM_PORT
        
        ports = serial.tools.list_ports.comports()
        
        # ESP32 common identifiers
        esp32_identifiers = [
            'CP210',  # Silicon Labs CP2102/CP2104
            'CH340',  # CH340 USB-to-Serial
            'CH341',
            'UART',   # Generic UART
            'USB-SERIAL',
            'USB Serial'
        ]
        
        for port in ports:
            port_desc = (port.description or '').upper()
            port_hw = (port.hwid or '').upper()
            
            for identifier in esp32_identifiers:
                if identifier.upper() in port_desc or identifier.upper() in port_hw:
                    print(f"[Serial] Found potential ESP32 on {port.device}: {port.description}")
                    return port.device
        
        # If no match, list available ports
        if ports:
            print("[Serial] Available COM ports:")
            for port in ports:
                print(f"  {port.device}: {port.description}")
        
        return None
    
    def connect_serial(self) -> bool:
        """Connect to ESP32 via Serial."""
        while self.running:
            try:
                # Find ESP32 port
                port = self.find_esp32_port()
                
                if not port:
                    print("[Serial] No ESP32 found. Retrying in 5s...")
                    self.serial_connected = False
                    time.sleep(SERIAL_RETRY_DELAY)
                    continue
                
                # Connect
                print(f"[Serial] Connecting to {port} at {BAUD_RATE} baud...")
                self.serial_port = serial.Serial(
                    port=port,
                    baudrate=BAUD_RATE,
                    timeout=1.0
                )
                
                # Wait for connection to stabilize
                time.sleep(2)
                
                # Flush any stale data
                if self.serial_port.in_waiting:
                    self.serial_port.read_all()
                
                print(f"[Serial] Connected to ESP32 on {port}")
                self.serial_connected = True
                return True
                
            except serial.SerialException as e:
                print(f"[Serial] Connection failed: {e}")
                print(f"[Serial] Retrying in {SERIAL_RETRY_DELAY}s...")
                self.serial_port = None
                self.serial_connected = False
                time.sleep(SERIAL_RETRY_DELAY)
            except Exception as e:
                print(f"[Serial] Unexpected error: {e}")
                self.serial_connected = False
                time.sleep(SERIAL_RETRY_DELAY)
        
        return False
    
    def setup_mqtt(self):
        """Initialize MQTT client."""
        self.mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
        
        # PHASE 2B-2: Handle incoming command messages
        self.mqtt_client.on_message = self._on_mqtt_message
        
        # Optional authentication
        username = os.getenv("MQTT_USERNAME")
        password = os.getenv("MQTT_PASSWORD")
        if username and password:
            self.mqtt_client.username_pw_set(username, password)
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connection callback."""
        if rc == 0:
            print(f"[MQTT] Connected to {MQTT_BROKER}:{MQTT_PORT}")
            self.mqtt_connected = True
            
            # PHASE 2B-2: Subscribe to command topic for this device
            command_topic = f"aquabuzz/commands/{self.device_id}"
            client.subscribe(command_topic, qos=1)
            print(f"[MQTT] Subscribed to {command_topic}")
        else:
            print(f"[MQTT] Connection failed with code {rc}")
            self.mqtt_connected = False
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback."""
        print(f"[MQTT] Disconnected (code {rc})")
        self.mqtt_connected = False
        
        if rc != 0 and self.running:
            print(f"[MQTT] Unexpected disconnect. Will reconnect...")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """
        PHASE 2B-2: Handle incoming MQTT messages (commands from backend).
        
        Expected message on aquabuzz/commands/{device_id}:
        {
            "command": "start"|"finish",
            "request_id": "req-12345678",
            "player_id": "alice" (for start command),
            "run_uid": "..." (for finish command),
            "timestamp": 1234567890
        }
        """
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            # Only process command messages
            if f"/commands/{self.device_id}" not in topic:
                return
            
            command_data = json.loads(payload)
            print(f"[MQTT] Received command: {json.dumps(command_data)}")
            
            # Queue command for serial transmission
            self.queue_command(command_data)
            
        except json.JSONDecodeError as e:
            print(f"[MQTT] Invalid JSON in command message: {e}")
        except Exception as e:
            print(f"[MQTT] Error processing command: {e}")
    
    def connect_mqtt(self):
        """Connect to MQTT broker with retry."""
        while self.running:
            try:
                print(f"[MQTT] Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
                self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
                self.mqtt_client.loop_start()
                
                # Wait for connection
                timeout = 10
                start = time.time()
                while not self.mqtt_connected and (time.time() - start) < timeout:
                    time.sleep(0.5)
                
                if self.mqtt_connected:
                    return True
                else:
                    print("[MQTT] Connection timeout")
                    
            except Exception as e:
                print(f"[MQTT] Connection error: {e}")
            
            print(f"[MQTT] Retrying in {MQTT_RETRY_DELAY}s...")
            time.sleep(MQTT_RETRY_DELAY)
        
        return False
    
    def generate_run_uid(self, run_no: int) -> str:
        """Generate unique run identifier."""
        return f"{self.device_id}-{self.gateway_session_id}-{run_no}"
    
    def normalize_event(self, raw_event: dict) -> Optional[dict]:
        """
        Normalize raw ESP32 event to backend-compatible format.
        Adds device_id, player_id, and run_uid.
        """
        event_type = raw_event.get("event")
        
        # Ignore non-game events
        if not event_type or event_type not in ["run_start", "hit_start", "hit_end", "run_finish", "run_cancel"]:
            return None
        
        run_no = raw_event.get("run", 0)
        
        # Handle run_start: create new run state
        if event_type == "run_start":
            run_uid = self.generate_run_uid(run_no)
            self.current_run_state = {
                "run_uid": run_uid,
                "run_no": run_no,
                "player_id": self.player_id,
                "device_id": self.device_id
            }
            print(f"[Gateway] Started run: {run_uid} (run #{run_no}, player: {self.player_id})")
        
        # Ensure we have an active run for other events
        if event_type in ["hit_start", "hit_end", "run_finish", "run_cancel"]:
            if not self.current_run_state:
                print(f"[Gateway] WARNING: Received {event_type} without active run, ignoring")
                return None
            
            # Verify run number matches
            if run_no != self.current_run_state["run_no"]:
                print(f"[Gateway] WARNING: Run number mismatch (expected {self.current_run_state['run_no']}, got {run_no})")
                return None
        
        # Build normalized event
        if self.current_run_state:
            normalized = {
                "device_id": self.device_id,
                "player_id": self.player_id,
                "run_uid": self.current_run_state["run_uid"],
                "run_no": run_no,
                "event": event_type
            }
            
            # Copy original event fields (t_ms, hits, score, etc.)
            for key, value in raw_event.items():
                if key not in ["event", "run"]:
                    normalized[key] = value
            
            # Clear run state on finish or cancel
            if event_type in ["run_finish", "run_cancel"]:
                print(f"[Gateway] Completed run: {self.current_run_state['run_uid']}")
                self.current_run_state = None
            
            return normalized
        
        return None
    
    def publish_event(self, event_data: dict):
        """Publish event to MQTT."""
        if not self.mqtt_connected:
            print("[MQTT] Not connected, cannot publish event")
            return False
        
        try:
            # FEAT-002: Measure MQTT publish latency
            mqtt_start = time.time()
            
            topic = f"aquabuzz/{self.device_id}/events"
            payload = json.dumps(event_data)
            result = self.mqtt_client.publish(topic, payload, qos=1)
            
            mqtt_end = time.time()
            mqtt_lag_ms = (mqtt_end - mqtt_start) * 1000
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"[MQTT] Published event: {event_data['event']}")
                
                # FEAT-002: Latency logging
                if GATEWAY_VERBOSE:
                    sys.stderr.write(f"[Latency] {event_data['event']}: mqtt_publish={mqtt_lag_ms:.1f}ms\n")
                    sys.stderr.flush()
                
                return True
            else:
                print(f"[MQTT] Publish failed: {result.rc}")
                return False
                
        except Exception as e:
            print(f"[MQTT] Publish error: {e}")
            return False
    
    def publish_heartbeat(self):
        """Publish heartbeat to indicate device is online."""
        if not self.mqtt_connected:
            return False
        
        try:
            heartbeat_data = {
                "device_id": self.device_id,
                "heartbeat": True,
                "status": "online" if self.serial_connected else "gateway_only",
                "source": "usb-serial-gateway",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            topic = f"aquabuzz/{self.device_id}/heartbeat"
            payload = json.dumps(heartbeat_data)
            result = self.mqtt_client.publish(topic, payload, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.last_heartbeat_time = time.time()
                return True
            else:
                return False
                
        except Exception as e:
            print(f"[MQTT] Heartbeat error: {e}")
            return False
    
    def queue_command(self, command_data: dict):
        """
        PHASE 2B-2: Queue a command for transmission to ESP32.
        
        Args:
            command_data: Backend command with request_id, command, timestamp
        """
        try:
            self.command_queue.put_nowait(command_data)
            print(f"[Command] Queued: {command_data['command']} (request_id: {command_data['request_id']})")
        except queue.Full:
            print(f"[Command] ERROR: Command queue full, cannot queue {command_data['command']}")
            # Publish immediate failure
            self.publish_command_ack(command_data['request_id'], command_data['command'], "error", "Queue full")
    
    def send_command(self, command_data: dict):
        """
        PHASE 2B-2: Send command to ESP32 via serial.
        
        Protocol (compatible with future firmware):
        {"cmd":"start","t":1234567890}\n
        {"cmd":"finish","t":1234567890}\n
        """
        if not self.serial_port or not self.serial_port.is_open:
            print(f"[Command] ERROR: Cannot send command, serial not connected")
            self.publish_command_ack(
                command_data['request_id'],
                command_data['command'],
                "error",
                "Serial port not connected"
            )
            return False
        
        try:
            # Build serial command message
            serial_cmd = {
                "cmd": command_data['command'],
                "t": command_data['timestamp']
            }
            
            cmd_json = json.dumps(serial_cmd) + "\n"
            
            # Write to serial (non-blocking)
            self.serial_port.write(cmd_json.encode('utf-8'))
            print(f"[Command] Sent to ESP32: {cmd_json.strip()}")
            
            # Track for acknowledgment/timeout
            cmd_id = f"{command_data['command']}-{command_data['timestamp']}"
            self.pending_commands[cmd_id] = {
                "sent_at": time.time(),
                "timeout": self.command_timeout_seconds,
                "command": command_data,
                "request_id": command_data['request_id']
            }
            
            return True
            
        except Exception as e:
            print(f"[Command] ERROR sending to ESP32: {e}")
            self.publish_command_ack(
                command_data['request_id'],
                command_data['command'],
                "error",
                f"Serial write failed: {str(e)}"
            )
            return False
    
    def handle_command_acknowledgment(self, ack_data: dict):
        """
        PHASE 2B-2: Process acknowledgment from ESP32.
        
        Expected ESP32 ACK format:
        {"cmd":"ack","cmd_id":"start-1234567890","status":"ok"}
        {"cmd":"ack","cmd_id":"start-1234567890","status":"error","reason":"already_running"}
        """
        cmd_id = ack_data.get("cmd_id")
        status = ack_data.get("status")  # "ok" or "error"
        reason = ack_data.get("reason", "")
        
        if not cmd_id or cmd_id not in self.pending_commands:
            print(f"[Command] ACK for unknown cmd_id: {cmd_id}")
            return
        
        # Remove from pending
        pending_info = self.pending_commands.pop(cmd_id)
        request_id = pending_info["request_id"]
        command_name = pending_info["command"]["command"]
        
        # Publish acknowledgment to backend via MQTT
        self.publish_command_ack(request_id, command_name, status, reason)
        
        print(f"[Command] ACK received: {cmd_id} → {status} {reason}")
    
    def publish_command_ack(self, request_id: str, command: str, status: str, error_reason: str = ""):
        """
        PHASE 2B-2: Publish command acknowledgment to backend.
        
        Args:
            request_id: Backend's request identifier
            command: "start" or "finish"
            status: "ok", "error", or "timeout"
            error_reason: Error description if status != "ok"
        """
        if not self.mqtt_connected:
            print(f"[Command] Cannot publish ACK, MQTT disconnected")
            return
        
        ack_payload = {
            "device_id": self.device_id,
            "request_id": request_id,
            "command": command,
            "status": status,
            "timestamp": int(time.time())
        }
        
        if error_reason:
            ack_payload["error_reason"] = error_reason
        
        topic = f"aquabuzz/{self.device_id}/ack"
        payload_json = json.dumps(ack_payload)
        
        result = self.mqtt_client.publish(topic, payload_json, qos=1)
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"[Command] Published ACK: {status} for {request_id}")
        else:
            print(f"[Command] Failed to publish ACK: {result.rc}")
    
    def check_command_timeouts(self):
        """
        PHASE 2B-2: Check for commands that haven't been acknowledged.
        Called periodically during read loop.
        """
        now = time.time()
        timed_out = []
        
        for cmd_id, cmd_info in list(self.pending_commands.items()):
            if now - cmd_info["sent_at"] > cmd_info["timeout"]:
                timed_out.append(cmd_id)
        
        for cmd_id in timed_out:
            cmd_info = self.pending_commands.pop(cmd_id)
            request_id = cmd_info["request_id"]
            command_name = cmd_info["command"]["command"]
            
            print(f"[Command] TIMEOUT: {cmd_id} (no acknowledgment after {cmd_info['timeout']}s)")
            
            # Publish timeout to backend
            self.publish_command_ack(
                request_id,
                command_name,
                "timeout",
                f"No acknowledgment received within {cmd_info['timeout']}s"
            )
    
    def heartbeat_loop(self):
        """Background thread for publishing heartbeats."""
        print("[Heartbeat] Thread started")
        
        while self.running:
            try:
                # Only publish heartbeat if we have both serial and MQTT
                if self.serial_connected and self.mqtt_connected:
                    if self.publish_heartbeat():
                        print(f"[Heartbeat] Published (serial: {self.serial_connected}, mqtt: {self.mqtt_connected})")
                
                # Sleep for interval
                time.sleep(HEARTBEAT_INTERVAL)
                
            except Exception as e:
                print(f"[Heartbeat] Error: {e}")
                time.sleep(HEARTBEAT_INTERVAL)
        
        print("[Heartbeat] Thread stopped")
    
    def parse_line(self, line: str) -> Optional[dict]:
        """
        Parse a line from serial.
        Returns JSON dict if valid, None if diagnostic text.
        """
        line = line.strip()
        
        if not line:
            return None
        
        # Try to parse as JSON
        try:
            data = json.loads(line)
            return data
        except json.JSONDecodeError:
            # Not JSON - probably diagnostic text
            # Print for debugging but don't process
            if line.startswith('{'):
                print(f"[ESP32] Invalid JSON: {line[:50]}...")
            return None
    
    def read_serial_loop(self):
        """Main loop: read from serial, normalize events, publish to MQTT."""
        print("\n[Gateway] Starting serial read loop...")
        print("[Gateway] Press Ctrl+C to stop\n")
        
        while self.running:
            try:
                # Check serial connection
                if not self.serial_port or not self.serial_port.is_open:
                    print("[Serial] Connection lost. Reconnecting...")
                    self.serial_connected = False
                    if not self.connect_serial():
                        continue
                
                # Check MQTT connection
                if not self.mqtt_connected:
                    print("[MQTT] Connection lost. Reconnecting...")
                    if not self.connect_mqtt():
                        continue
                
                # Read from serial
                if self.serial_port.in_waiting:
                    try:
                        # FEAT-002: Measure serial read latency
                        read_start = time.time()
                        line = self.serial_port.readline().decode('utf-8', errors='ignore')
                        read_end = time.time()
                        
                        # Parse line
                        raw_event = self.parse_line(line)
                        
                        if raw_event:
                            # FEAT-002: Add gateway reception timestamp
                            gateway_rx_ts = time.time()
                            
                            # Check if it's a game event
                            if "event" in raw_event:
                                print(f"[Serial] Raw event: {json.dumps(raw_event)}")
                                
                                # Normalize event
                                normalized_event = self.normalize_event(raw_event)
                                
                                if normalized_event:
                                    # FEAT-002: Add gateway timestamps for latency tracking
                                    normalized_event["gateway_rx_ts"] = gateway_rx_ts
                                    
                                    print(f"[Gateway] Normalized: {json.dumps(normalized_event)}")
                                    
                                    # FEAT-002: Latency logging
                                    if GATEWAY_VERBOSE:
                                        serial_lag_ms = (read_end - read_start) * 1000
                                        sys.stderr.write(f"[Latency] {normalized_event['event']}: serial_read={serial_lag_ms:.1f}ms\n")
                                        sys.stderr.flush()
                                    
                                    self.publish_event(normalized_event)
                                else:
                                    print(f"[Gateway] Event ignored or invalid")
                            
                            # PHASE 2B-2: Handle command acknowledgments from ESP32
                            elif "cmd" in raw_event and raw_event.get("cmd") == "ack":
                                print(f"[ESP32] ACK: {json.dumps(raw_event)}")
                                self.handle_command_acknowledgment(raw_event)
                            
                            # Handle info messages
                            elif "info" in raw_event:
                                print(f"[ESP32] Info: {raw_event}")
                            
                            # Handle warnings
                            elif "warn" in raw_event:
                                print(f"[ESP32] Warning: {raw_event}")
                    
                    except UnicodeDecodeError:
                        # Ignore decode errors
                        pass
                    except Exception as e:
                        print(f"[Serial] Read error: {e}")
                
                # PHASE 2B-2: Process command queue (non-blocking)
                try:
                    while not self.command_queue.empty():
                        command_data = self.command_queue.get_nowait()
                        self.send_command(command_data)
                except queue.Empty:
                    pass
                except Exception as e:
                    print(f"[Command] Error processing queue: {e}")
                
                # PHASE 2B-2: Check for command timeouts every iteration
                self.check_command_timeouts()
                
                # Small delay to prevent CPU spinning
                time.sleep(0.01)
                
            except serial.SerialException as e:
                print(f"[Serial] Error: {e}")
                print("[Serial] Reconnecting...")
                self.serial_port = None
                self.serial_connected = False
                time.sleep(SERIAL_RETRY_DELAY)
                
            except KeyboardInterrupt:
                print("\n[Gateway] Shutdown requested")
                self.running = False
                break
                
            except Exception as e:
                print(f"[Gateway] Unexpected error: {e}")
                time.sleep(1)
    
    def run(self):
        """Start the gateway."""
        print("="*60)
        print("  AquaBuzz Serial-to-MQTT Gateway v2")
        print("="*60)
        print(f"  Device ID: {self.device_id}")
        print(f"  Default Player: {self.player_id}")
        print(f"  MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
        print(f"  Serial Baud: {BAUD_RATE}")
        print(f"  Heartbeat Interval: {HEARTBEAT_INTERVAL}s")
        print("="*60)
        print()
        
        # Setup MQTT
        self.setup_mqtt()
        
        # Connect to MQTT first
        if not self.connect_mqtt():
            print("[Gateway] Failed to connect to MQTT. Exiting.")
            return
        
        # Connect to Serial
        if not self.connect_serial():
            print("[Gateway] Failed to connect to ESP32.")
            print("[Gateway] Will retry in background...")
        
        # Start heartbeat thread
        self.heartbeat_thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        
        # Start reading loop
        try:
            self.read_serial_loop()
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean shutdown."""
        print("\n[Gateway] Cleaning up...")
        
        self.running = False
        
        # Publish offline status if possible
        if self.mqtt_connected and self.mqtt_client:
            try:
                offline_data = {
                    "device_id": self.device_id,
                    "heartbeat": True,
                    "status": "offline",
                    "source": "usb-serial-gateway",
                    "timestamp": datetime.utcnow().isoformat()
                }
                topic = f"aquabuzz/{self.device_id}/heartbeat"
                self.mqtt_client.publish(topic, json.dumps(offline_data), qos=1)
                print("[MQTT] Published offline status")
                time.sleep(0.5)  # Allow message to be sent
            except:
                pass
        
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            print("[Serial] Port closed")
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            print("[MQTT] Disconnected")
        
        print("[Gateway] Shutdown complete")


def main():
    """Entry point."""
    # Load .env if available
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            load_dotenv(env_path)
            print(f"[Config] Loaded .env from {env_path}")
    except ImportError:
        print("[Config] python-dotenv not installed, using environment variables")
    
    # Create and run gateway
    gateway = SerialGateway()
    gateway.run()


if __name__ == "__main__":
    main()
