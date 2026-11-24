"""
AquaBuzz Serial-to-MQTT Gateway v2
Reads JSON events from ESP32 via USB Serial and publishes to MQTT broker.
Handles event normalization, heartbeat publishing, and network independence.
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
        else:
            print(f"[MQTT] Connection failed with code {rc}")
            self.mqtt_connected = False
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback."""
        print(f"[MQTT] Disconnected (code {rc})")
        self.mqtt_connected = False
        
        if rc != 0 and self.running:
            print(f"[MQTT] Unexpected disconnect. Will reconnect...")
    
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
            topic = f"aquabuzz/{self.device_id}/events"
            payload = json.dumps(event_data)
            result = self.mqtt_client.publish(topic, payload, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"[MQTT] Published event: {event_data['event']}")
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
                        line = self.serial_port.readline().decode('utf-8', errors='ignore')
                        
                        # Parse line
                        raw_event = self.parse_line(line)
                        
                        if raw_event:
                            # Check if it's a game event
                            if "event" in raw_event:
                                print(f"[Serial] Raw event: {json.dumps(raw_event)}")
                                
                                # Normalize event
                                normalized_event = self.normalize_event(raw_event)
                                
                                if normalized_event:
                                    print(f"[Gateway] Normalized: {json.dumps(normalized_event)}")
                                    self.publish_event(normalized_event)
                                else:
                                    print(f"[Gateway] Event ignored or invalid")
                            
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
