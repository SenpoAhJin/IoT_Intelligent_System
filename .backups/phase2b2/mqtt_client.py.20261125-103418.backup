"""MQTT client for ingesting device events."""

import json
import threading
import paho.mqtt.client as mqtt
from datetime import datetime
from typing import Callable, Optional
import os


class MQTTEventIngester:
    """MQTT client that subscribes to device events and processes them."""
    
    def __init__(self, broker_host: str, broker_port: int, 
                 username: Optional[str] = None, password: Optional[str] = None):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        
        self.client = mqtt.Client(client_id=os.getenv("MQTT_CLIENT_ID", "aquabuzz-backend"))
        
        if username and password:
            self.client.username_pw_set(username, password)
        
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        self.event_handler = None
        self.connected = False
        
    def set_event_handler(self, handler: Callable):
        """Set callback for processing events."""
        self.event_handler = handler
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker."""
        if rc == 0:
            print(f"[MQTT] Connected to {self.broker_host}:{self.broker_port}")
            self.connected = True
            
            # Subscribe to all device events
            client.subscribe("aquabuzz/+/events")
            client.subscribe("aquabuzz/+/heartbeat")
            print("[MQTT] Subscribed to aquabuzz/+/events and heartbeats")
        else:
            print(f"[MQTT] Connection failed with code {rc}")
            self.connected = False
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker."""
        print(f"[MQTT] Disconnected with code {rc}")
        self.connected = False
    
    def _on_message(self, client, userdata, msg):
        """Callback when message received."""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            # Parse JSON payload
            data = json.loads(payload)
            
            # Add metadata
            data['_topic'] = topic
            data['_received_at'] = datetime.utcnow().isoformat()
            
            # Route to handler
            if self.event_handler:
                self.event_handler(data)
            else:
                print(f"[MQTT] No handler for: {topic}")
                
        except json.JSONDecodeError:
            print(f"[MQTT] Invalid JSON on {msg.topic}: {msg.payload}")
        except Exception as e:
            print(f"[MQTT] Error processing message: {e}")
    
    def start(self):
        """Start MQTT client in background thread."""
        def run():
            try:
                self.client.connect(self.broker_host, self.broker_port, keepalive=60)
                self.client.loop_forever()
            except Exception as e:
                print(f"[MQTT] Connection error: {e}")
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        print("[MQTT] Client started in background")
    
    def publish(self, topic: str, payload: dict):
        """Publish a message to a topic."""
        try:
            json_payload = json.dumps(payload)
            result = self.client.publish(topic, json_payload, qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"[MQTT] Published to {topic}")
                return True
            else:
                print(f"[MQTT] Publish failed: {result.rc}")
                return False
        except Exception as e:
            print(f"[MQTT] Publish error: {e}")
            return False
    
    def stop(self):
        """Stop MQTT client."""
        self.client.disconnect()
        self.client.loop_stop()
