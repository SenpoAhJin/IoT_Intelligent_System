/*
 * AquaBuzz Connected Firmware v1.0
 * 
 * IoT-enabled buzz-wire maze with MQTT event streaming.
 * Based on aquabuzz_core v6 with Wi-Fi + MQTT layer.
 * 
 * Hardware: ESP32 Dev Module
 * Serial: 115200 baud
 */

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <Preferences.h>
#include "secrets.h"

// Pin definitions
const int PIN_MAZE = 27;
const int PIN_FINISH = 33;
const int PIN_BUZZER = 26;

// Timing constants
const unsigned long DEBOUNCE_MS = 20;
const unsigned long LOCKOUT_MS = 5000;
const unsigned long HEARTBEAT_INTERVAL_MS = 10000;

// Difficulty settings (can be updated via MQTT)
unsigned long hitPenaltyMs = 2000;
int freeHits = 0;
unsigned long timeLimitMs = 0;  // 0 = no limit

// Game states
enum GameState {
  WAITING,
  RUNNING,
  FINISHED
};

// Hit tracking
struct Hit {
  unsigned long startMs;
  unsigned long durationMs;
};

// Global state
GameState state = WAITING;
unsigned long runStartMs = 0;
unsigned long runEndMs = 0;
unsigned long finishLockoutUntil = 0;
int runNo = 0;
int bootCount = 0;
String runUid = "";
String playerId = "guest";
int hitCount = 0;
Hit hits[100];

// Contact tracking
bool mazePressed = false;
bool finishPressed = false;
unsigned long mazeLastChangeMs = 0;
unsigned long finishLastChangeMs = 0;
bool mazeRaw = false;
bool finishRaw = false;
unsigned long currentHitStartMs = 0;
bool finishReleased = true;

// Networking
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
Preferences prefs;
unsigned long lastHeartbeat = 0;
bool wifiConnected = false;
bool mqttConnected = false;

// Queues
QueueHandle_t serialQueue;
QueueHandle_t mqttQueue;
const int SERIAL_QUEUE_SIZE = 50;
const int MQTT_QUEUE_SIZE = 100;

struct SerialMessage {
  char text[256];
};

struct MQTTMessage {
  char topic[128];
  char payload[512];
};

// ==================== Core Game Logic (preserved from v6) ====================

void driveBuzzerNow() {
  // Read sensor directly for immediate buzzer response
  // Do NOT modify mazeRaw - that's used by updateContacts() for debouncing
  bool currentContact = !digitalRead(PIN_MAZE);
  digitalWrite(PIN_BUZZER, currentContact ? HIGH : LOW);
}

void queuePrint(const char* format, ...) {
  SerialMessage msg;
  va_list args;
  va_start(args, format);
  vsnprintf(msg.text, sizeof(msg.text), format, args);
  va_end(args);
  xQueueSend(serialQueue, &msg, 0);
}

void queueMQTT(const char* topic, const char* format, ...) {
  MQTTMessage msg;
  strncpy(msg.topic, topic, sizeof(msg.topic) - 1);
  
  va_list args;
  va_start(args, format);
  vsnprintf(msg.payload, sizeof(msg.payload), format, args);
  va_end(args);
  
  xQueueSend(mqttQueue, &msg, 0);
}

void updateContacts() {
  unsigned long now = millis();
  
  // Maze contact
  bool mazeCurrentRaw = !digitalRead(PIN_MAZE);
  if (mazeCurrentRaw != mazeRaw) {
    mazeRaw = mazeCurrentRaw;
    mazeLastChangeMs = now;
  }
  if ((now - mazeLastChangeMs) >= DEBOUNCE_MS) {
    if (mazeCurrentRaw && !mazePressed) {
      mazePressed = true;
      onMazePressed();
    } else if (!mazeCurrentRaw && mazePressed) {
      mazePressed = false;
      onMazeReleased();
    }
  }
  
  // Finish contact
  bool finishCurrentRaw = !digitalRead(PIN_FINISH);
  if (finishCurrentRaw != finishRaw) {
    finishRaw = finishCurrentRaw;
    finishLastChangeMs = now;
  }
  if ((now - finishLastChangeMs) >= DEBOUNCE_MS) {
    if (finishCurrentRaw && !finishPressed) {
      finishPressed = true;
      if (!finishReleased) {
        queuePrint("{\"warn\":\"finish_held_at_start\"}");
      } else {
        onFinishPressed();
      }
    } else if (!finishCurrentRaw && finishPressed) {
      finishPressed = false;
      finishReleased = true;
    }
  }
}

void onMazePressed() {
  unsigned long now = millis();
  
  if (state == WAITING) {
    if (now >= finishLockoutUntil) {
      runNo++;
      runUid = String(DEVICE_ID) + "-" + String(bootCount) + "-" + String(runNo);
      runStartMs = now;
      runEndMs = 0;
      hitCount = 0;
      state = RUNNING;
      finishReleased = !finishPressed;
      
      // Serial output ONLY - gateway handles MQTT publishing
      // FEAT-001: Add esp32_ts_ms timestamp for latency measurement
      queuePrint("{\"run\":%d,\"event\":\"run_start\",\"t_ms\":0,\"esp32_ts_ms\":%lu}", runNo, now);
    }
  } else if (state == RUNNING) {
    currentHitStartMs = now;
    hitCount++;
    hits[hitCount - 1].startMs = now - runStartMs;
    hits[hitCount - 1].durationMs = 0;
    
    // Serial output ONLY
    // FEAT-001: Add esp32_ts_ms timestamp for latency measurement
    queuePrint("{\"run\":%d,\"event\":\"hit_start\",\"hit\":%d,\"t_ms\":%lu,\"esp32_ts_ms\":%lu}",
               runNo, hitCount, now - runStartMs, now);
  }
}

void onMazeReleased() {
  if (state == RUNNING && currentHitStartMs > 0) {
    unsigned long now = millis();
    unsigned long duration = now - currentHitStartMs;
    hits[hitCount - 1].durationMs = duration;
    
    // Serial output ONLY
    // FEAT-001: Add esp32_ts_ms timestamp for latency measurement
    queuePrint("{\"run\":%d,\"event\":\"hit_end\",\"hit\":%d,\"t_ms\":%lu,\"dur_ms\":%lu,\"esp32_ts_ms\":%lu}",
               runNo, hitCount, now - runStartMs, duration, now);
    
    currentHitStartMs = 0;
  }
}

void onFinishPressed() {
  if (state == RUNNING) {
    unsigned long now = millis();
    
    // CRITICAL FIX: Close active hit before calculating final stats
    if (currentHitStartMs > 0) {
      unsigned long duration = now - currentHitStartMs;
      hits[hitCount - 1].durationMs = duration;
      
      // Serial output ONLY
      // FEAT-001: Add esp32_ts_ms timestamp for latency measurement
      queuePrint("{\"run\":%d,\"event\":\"hit_end\",\"hit\":%d,\"t_ms\":%lu,\"dur_ms\":%lu,\"esp32_ts_ms\":%lu}",
                 runNo, hitCount, now - runStartMs, duration, now);
      
      currentHitStartMs = 0;
    }
    
    runEndMs = now;
    state = FINISHED;
    finishLockoutUntil = now + LOCKOUT_MS;
    
    // Calculate stats AFTER closing active hit
    unsigned long totalTimeMs = runEndMs - runStartMs;
    unsigned long totalContactMs = 0;
    unsigned long longestHitMs = 0;
    
    for (int i = 0; i < hitCount; i++) {
      totalContactMs += hits[i].durationMs;
      if (hits[i].durationMs > longestHitMs) {
        longestHitMs = hits[i].durationMs;
      }
    }
    
    // Apply difficulty settings
    int scoredHits = max(0, hitCount - freeHits);
    unsigned long score = totalTimeMs + (scoredHits * hitPenaltyMs);
    
    // Serial output ONLY
    // FEAT-001: Add esp32_ts_ms timestamp for latency measurement
    queuePrint("{\"run\":%d,\"event\":\"run_finish\",\"t_ms\":%lu,\"hits\":%d,\"total_contact_ms\":%lu,\"longest_hit_ms\":%lu,\"hit_penalty_ms\":%lu,\"score\":%lu,\"esp32_ts_ms\":%lu}",
               runNo, totalTimeMs, hitCount, totalContactMs, longestHitMs, hitPenaltyMs, score, now);
    
    delay(100);
    state = WAITING;
  }
}

void handleSerialCommand() {
  if (Serial.available()) {
    char cmd = Serial.read();
    
    if (cmd == 'r') {
      if (state == RUNNING) {
        // Serial output ONLY
        queuePrint("{\"run\":%d,\"event\":\"run_cancel\",\"t_ms\":%lu}", runNo, millis() - runStartMs);
        runNo++;  // Increment on cancel
      }
      state = WAITING;
      runStartMs = 0;
      runEndMs = 0;
      hitCount = 0;
      currentHitStartMs = 0;
      queuePrint("{\"info\":\"reset\"}");
    } else if (cmd == 's') {
      queuePrint("{\"info\":\"summary\",\"run\":%d,\"state\":\"%s\",\"hits\":%d,\"wifi\":\"%s\",\"mqtt\":\"%s\"}",
                 runNo,
                 state == WAITING ? "WAITING" : state == RUNNING ? "RUNNING" : "FINISHED",
                 hitCount,
                 wifiConnected ? "connected" : "disconnected",
                 mqttConnected ? "connected" : "disconnected");
    } else if (cmd == 'b' && state != RUNNING) {
      queuePrint("{\"info\":\"buzzer_test\"}");
      digitalWrite(PIN_BUZZER, HIGH);
      delay(100);
      digitalWrite(PIN_BUZZER, LOW);
      delay(100);
      digitalWrite(PIN_BUZZER, HIGH);
      delay(100);
      digitalWrite(PIN_BUZZER, LOW);
    }
  }
}

// ==================== Networking Tasks ====================

void serialTask(void *parameter) {
  SerialMessage msg;
  for (;;) {
    if (xQueueReceive(serialQueue, &msg, portMAX_DELAY)) {
      Serial.println(msg.text);
    }
  }
}

void mqttTask(void *parameter) {
  MQTTMessage msg;
  for (;;) {
    if (xQueueReceive(mqttQueue, &msg, pdMS_TO_TICKS(100))) {
      if (mqttConnected) {
        mqttClient.publish(msg.topic, msg.payload, false);
      }
    }
    
    // Maintain MQTT connection
    if (!mqttClient.connected() && wifiConnected) {
      if (mqttClient.connect(DEVICE_ID, MQTT_USERNAME, MQTT_PASSWORD)) {
        mqttConnected = true;
        mqttClient.subscribe("aquabuzz/" DEVICE_ID "/config");
        mqttClient.subscribe("aquabuzz/" DEVICE_ID "/player");
        queuePrint("{\"mqtt\":\"connected\"}");
      }
    }
    
    if (mqttConnected) {
      mqttClient.loop();
      
      // Heartbeat
      if (millis() - lastHeartbeat > HEARTBEAT_INTERVAL_MS) {
        mqttClient.publish("aquabuzz/" DEVICE_ID "/heartbeat",
                          "{\"device_id\":\"" DEVICE_ID "\"}");
        lastHeartbeat = millis();
      }
    }
    
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String topicStr = String(topic);
  String payloadStr = "";
  for (unsigned int i = 0; i < length; i++) {
    payloadStr += (char)payload[i];
  }
  
  queuePrint("{\"mqtt_rx\":\"%s\"}", topicStr.c_str());
  
  // Handle config updates
  if (topicStr.endsWith("/config")) {
    // Parse JSON manually (simple approach)
    // Real implementation would use ArduinoJson
    if (payloadStr.indexOf("hit_penalty_ms") > 0) {
      queuePrint("{\"info\":\"config_received\"}");
    }
  } else if (topicStr.endsWith("/player")) {
    playerId = payloadStr;
    queuePrint("{\"player\":\"%s\"}", playerId.c_str());
  }
}

void wifiTask(void *parameter) {
  for (;;) {
    if (WiFi.status() != WL_CONNECTED) {
      wifiConnected = false;
      mqttConnected = false;
      
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
      queuePrint("{\"wifi\":\"connecting\"}");
      
      int attempts = 0;
      while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        vTaskDelay(pdMS_TO_TICKS(500));
        attempts++;
      }
      
      if (WiFi.status() == WL_CONNECTED) {
        wifiConnected = true;
        queuePrint("{\"wifi\":\"connected\",\"ip\":\"%s\"}", WiFi.localIP().toString().c_str());
      } else {
        queuePrint("{\"wifi\":\"failed\"}");
        vTaskDelay(pdMS_TO_TICKS(10000));  // Retry in 10s
      }
    }
    
    vTaskDelay(pdMS_TO_TICKS(1000));
  }
}

// ==================== Setup and Loop ====================

void setup() {
  pinMode(PIN_MAZE, INPUT_PULLUP);
  pinMode(PIN_FINISH, INPUT_PULLUP);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);
  
  Serial.begin(115200);
  delay(100);
  
  // Load boot count from NVS
  prefs.begin("aquabuzz", false);
  bootCount = prefs.getInt("boot_count", 0);
  bootCount++;
  prefs.putInt("boot_count", bootCount);
  prefs.end();
  
  // Create queues
  serialQueue = xQueueCreate(SERIAL_QUEUE_SIZE, sizeof(SerialMessage));
  mqttQueue = xQueueCreate(MQTT_QUEUE_SIZE, sizeof(MQTTMessage));
  
  // Create tasks
  xTaskCreate(serialTask, "SerialTask", 4096, NULL, 1, NULL);
  xTaskCreate(wifiTask, "WiFiTask", 4096, NULL, 1, NULL);
  xTaskCreate(mqttTask, "MQTTTask", 8192, NULL, 1, NULL);
  
  // Setup MQTT
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  
  queuePrint("{\"info\":\"aquabuzz_connected_v1\",\"boot\":%d,\"device\":\"" DEVICE_ID "\"}", bootCount);
  
  // Power-on buzzer test
  digitalWrite(PIN_BUZZER, HIGH);
  delay(100);
  digitalWrite(PIN_BUZZER, LOW);
  delay(100);
  digitalWrite(PIN_BUZZER, HIGH);
  delay(100);
  digitalWrite(PIN_BUZZER, LOW);
}

void loop() {
  driveBuzzerNow();  // MUST be first
  updateContacts();
  handleSerialCommand();
}
