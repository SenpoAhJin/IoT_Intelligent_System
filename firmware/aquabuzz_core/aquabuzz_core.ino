/*
 * AquaBuzz Core Firmware v6
 * 
 * Buzz-wire maze game with instant buzzer response and detailed hit tracking.
 * 
 * Hardware:
 *   - Maze wire on GPIO 27 (INPUT_PULLUP, LOW = contact)
 *   - Finish pad on GPIO 33 (INPUT_PULLUP, LOW = contact)
 *   - Buzzer MOSFET on GPIO 26 (OUTPUT, HIGH = buzzer on)
 * 
 * Serial: 115200 baud
 * Board: ESP32 Dev Module
 */

#include <Arduino.h>

// Pin definitions
const int PIN_MAZE = 27;
const int PIN_FINISH = 33;
const int PIN_BUZZER = 26;

// Timing constants
const unsigned long DEBOUNCE_MS = 20;
const unsigned long LOCKOUT_MS = 5000;
const unsigned long HIT_PENALTY_MS = 2000;

// Game states
enum GameState {
  WAITING,
  RUNNING,
  FINISHED
};

// Hit tracking structure
struct Hit {
  unsigned long startMs;
  unsigned long durationMs;
};

// Global state
GameState state = WAITING;
unsigned long runStartMs = 0;
unsigned long runEndMs = 0;
unsigned long finishLockoutUntil = 0;
int runId = 0;
int hitCount = 0;
Hit hits[100];  // Max 100 hits per run

// Contact state tracking
bool mazePressed = false;
bool finishPressed = false;
unsigned long mazeLastChangeMs = 0;
unsigned long finishLastChangeMs = 0;
bool mazeRaw = false;
bool finishRaw = false;
unsigned long currentHitStartMs = 0;
bool finishReleased = true;  // Track if finish has been released since run start

// Serial queue for non-blocking prints
QueueHandle_t serialQueue;
const int SERIAL_QUEUE_SIZE = 50;

struct SerialMessage {
  char text[256];
};

// FreeRTOS task for serial printing
void serialTask(void *parameter) {
  SerialMessage msg;
  for (;;) {
    if (xQueueReceive(serialQueue, &msg, portMAX_DELAY)) {
      Serial.println(msg.text);
    }
  }
}

void queuePrint(const char* format, ...) {
  SerialMessage msg;
  va_list args;
  va_start(args, format);
  vsnprintf(msg.text, sizeof(msg.text), format, args);
  va_end(args);
  xQueueSend(serialQueue, &msg, 0);  // Don't block if queue full
}

// Instant buzzer control - must be first line in loop()
void driveBuzzerNow() {
  mazeRaw = !digitalRead(PIN_MAZE);  // Active low
  digitalWrite(PIN_BUZZER, mazeRaw ? HIGH : LOW);
}

// Debounced contact detection
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
    // First touch starts the run (not a hit)
    if (now >= finishLockoutUntil) {
      runId++;
      runStartMs = now;
      runEndMs = 0;
      hitCount = 0;
      state = RUNNING;
      finishReleased = !finishPressed;  // Check if finish is already pressed
      
      queuePrint("{\"run\":%d,\"event\":\"run_start\",\"t_ms\":0}", runId);
      
      if (!finishReleased) {
        queuePrint("{\"warn\":\"finish_and_maze_both_low\",\"hint\":\"finish_wired_to_maze\"}");
      }
    }
  } else if (state == RUNNING) {
    // Subsequent touches are hits
    currentHitStartMs = now;
    hitCount++;
    hits[hitCount - 1].startMs = now - runStartMs;
    hits[hitCount - 1].durationMs = 0;  // Will be set on release
    
    queuePrint("{\"run\":%d,\"event\":\"hit_start\",\"hit\":%d,\"t_ms\":%lu}",
               runId, hitCount, now - runStartMs);
  }
}

void onMazeReleased() {
  if (state == RUNNING && currentHitStartMs > 0) {
    unsigned long now = millis();
    unsigned long duration = now - currentHitStartMs;
    hits[hitCount - 1].durationMs = duration;
    
    queuePrint("{\"run\":%d,\"event\":\"hit_end\",\"hit\":%d,\"t_ms\":%lu,\"dur_ms\":%lu}",
               runId, hitCount, now - runStartMs, duration);
    
    currentHitStartMs = 0;
  }
}

void onFinishPressed() {
  if (state == RUNNING) {
    unsigned long now = millis();
    runEndMs = now;
    state = FINISHED;
    finishLockoutUntil = now + LOCKOUT_MS;
    
    // Calculate stats
    unsigned long totalTimeMs = runEndMs - runStartMs;
    unsigned long totalContactMs = 0;
    unsigned long longestHitMs = 0;
    
    for (int i = 0; i < hitCount; i++) {
      totalContactMs += hits[i].durationMs;
      if (hits[i].durationMs > longestHitMs) {
        longestHitMs = hits[i].durationMs;
      }
    }
    
    unsigned long score = totalTimeMs + (hitCount * HIT_PENALTY_MS);
    
    queuePrint("{\"run\":%d,\"event\":\"run_finish\",\"t_ms\":%lu,\"hits\":%d,\"total_contact_ms\":%lu,\"longest_hit_ms\":%lu,\"hit_penalty_ms\":%lu,\"score\":%lu}",
               runId, totalTimeMs, hitCount, totalContactMs, longestHitMs, HIT_PENALTY_MS, score);
    
    // Reset to waiting after printing
    delay(100);  // Brief delay for serial queue to flush
    state = WAITING;
  }
}

void handleSerialCommand() {
  if (Serial.available()) {
    char cmd = Serial.read();
    
    if (cmd == 'r') {
      // Reset
      if (state == RUNNING) {
        queuePrint("{\"run\":%d,\"event\":\"run_cancel\",\"t_ms\":%lu}",
                   runId, millis() - runStartMs);
      }
      state = WAITING;
      runStartMs = 0;
      runEndMs = 0;
      hitCount = 0;
      currentHitStartMs = 0;
      queuePrint("{\"info\":\"reset\"}");
      
    } else if (cmd == 's') {
      // Summary
      queuePrint("{\"info\":\"summary\",\"run\":%d,\"state\":\"%s\",\"hits\":%d}",
                 runId,
                 state == WAITING ? "WAITING" : state == RUNNING ? "RUNNING" : "FINISHED",
                 hitCount);
      
    } else if (cmd == 'b') {
      // Buzzer test (only if not running)
      if (state != RUNNING) {
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
}

void setup() {
  // Initialize pins
  pinMode(PIN_MAZE, INPUT_PULLUP);
  pinMode(PIN_FINISH, INPUT_PULLUP);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);
  
  // Initialize serial
  Serial.begin(115200);
  delay(100);
  
  // Create serial queue and task
  serialQueue = xQueueCreate(SERIAL_QUEUE_SIZE, sizeof(SerialMessage));
  xTaskCreate(serialTask, "SerialTask", 4096, NULL, 1, NULL);
  
  // Power-on buzzer test
  queuePrint("{\"info\":\"aquabuzz_v6\",\"boot\":\"ready\"}");
  digitalWrite(PIN_BUZZER, HIGH);
  delay(100);
  digitalWrite(PIN_BUZZER, LOW);
  delay(100);
  digitalWrite(PIN_BUZZER, HIGH);
  delay(100);
  digitalWrite(PIN_BUZZER, LOW);
}

void loop() {
  driveBuzzerNow();  // MUST be first - instant response
  updateContacts();
  handleSerialCommand();
  // No delays or blocking calls
}
