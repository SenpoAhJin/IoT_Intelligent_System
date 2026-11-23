/*
 * AquaBuzz Secrets Configuration
 * 
 * Copy this file to secrets.h and fill in your credentials.
 * secrets.h is gitignored and will not be committed.
 */

#ifndef SECRETS_H
#define SECRETS_H

// WiFi credentials
#define WIFI_SSID "your-wifi-ssid"
#define WIFI_PASSWORD "your-wifi-password"

// MQTT broker
#define MQTT_BROKER "192.168.1.100"  // or "mqtt.example.com"
#define MQTT_PORT 1883
#define MQTT_USERNAME ""  // Leave empty if no auth
#define MQTT_PASSWORD ""

// Device identity
#define DEVICE_ID "aquabuzz-001"

#endif
