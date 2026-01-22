# VECNA Hardware Integration Manual

## ESP32 Gateway Firmware Integration Guide

**Version:** 1.0.0  
**Last Updated:** January 2026  
**Target Hardware:** ESP32-WROOM-32 / ESP32-S3 Master Gateway

---

## Table of Contents

1. [Overview](#overview)
2. [API Endpoint](#api-endpoint)
3. [JSON Payload Specification](#json-payload-specification)
4. [Field Definitions](#field-definitions)
5. [Data Types & Constraints](#data-types--constraints)
6. [ESP32 Code Examples](#esp32-code-examples)
7. [Error Handling](#error-handling)
8. [Best Practices](#best-practices)

---

## Overview

The VECNA backend expects telemetry data from ESP32 Master Gateways via HTTP POST requests. Each gateway aggregates data from:

- **GPS Module** (NEO-6M / NEO-M8N) - Location tracking
- **BLE Slave Nodes** (ESP32-C3 / nRF52) - Cargo temperature sensors
- **Internal Sensors** - Gateway health monitoring

The gateway should transmit data at regular intervals (recommended: every 30-60 seconds during active trips).

---

## API Endpoint

### Production
```
POST https://your-server.com/api/v1/telemetry
Content-Type: application/json
```

### Development
```
POST http://localhost:5000/api/v1/telemetry
Content-Type: application/json
```

### Response Codes

| Code | Description |
|------|-------------|
| `201` | Telemetry ingested successfully |
| `400` | Invalid JSON payload or missing required fields |
| `500` | Server error |

---

## JSON Payload Specification

### Complete Payload Structure

```json
{
  "gateway_id": "TRUCK-402",
  "trip_id": "TRIP-CHN-BLR-05",
  "timestamp": "2026-01-16T14:30:00Z",
  
  "location": {
    "lat": 13.0827,
    "lng": 80.2707,
    "speed_kmh": 62.5,
    "heading_deg": 270,
    "satellites": 8
  },

  "gateway_health": {
    "battery_mv": 3800,
    "signal_strength_dbm": -65,
    "uptime_seconds": 7200,
    "cpu_temp_c": 42.5
  },

  "cargo_sensors": [
    {
      "node_id": "BOX-A12",
      "product_type": "Poultry",
      "temp_c": 3.5,
      "battery_pct": 85,
      "link_quality": -72,
      "status": "NOMINAL"
    },
    {
      "node_id": "BOX-B05",
      "product_type": "Seafood",
      "temp_c": 8.1,
      "battery_pct": 40,
      "link_quality": -80,
      "status": "WARNING"
    }
  ]
}
```

---

## Field Definitions

### Root Level Fields (Required)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gateway_id` | string | ✅ Yes | Unique identifier for the truck/gateway (e.g., "TRUCK-402") |
| `trip_id` | string | ✅ Yes | Current trip identifier (e.g., "TRIP-CHN-BLR-05") |
| `timestamp` | string | ✅ Yes | ISO 8601 timestamp in UTC (e.g., "2026-01-16T14:30:00Z") |

### Location Object

| Field | Type | Required | Description | Range |
|-------|------|----------|-------------|-------|
| `lat` | float | ⚠️ Recommended | GPS latitude in decimal degrees | -90.0 to 90.0 |
| `lng` | float | ⚠️ Recommended | GPS longitude in decimal degrees | -180.0 to 180.0 |
| `speed_kmh` | float | Optional | Current speed in km/h | 0.0 to 200.0 |
| `heading_deg` | float | Optional | Direction of travel in degrees | 0 to 360 |
| `satellites` | integer | Optional | Number of GPS satellites in view | 0 to 24 |

### Gateway Health Object

| Field | Type | Required | Description | Range |
|-------|------|----------|-------------|-------|
| `battery_mv` | integer | Optional | Gateway battery voltage in millivolts | 2500 to 4200 |
| `signal_strength_dbm` | integer | Optional | WiFi/4G signal strength in dBm | -120 to 0 |
| `uptime_seconds` | integer | Optional | Seconds since last gateway reboot | 0 to 2^32 |
| `cpu_temp_c` | float | Optional | ESP32 internal temperature in °C | -40.0 to 125.0 |

### Cargo Sensors Array

Each object in the `cargo_sensors` array represents one BLE slave node:

| Field | Type | Required | Description | Range |
|-------|------|----------|-------------|-------|
| `node_id` | string | ✅ Yes | Unique sensor box ID (e.g., "BOX-A12") | Max 50 chars |
| `product_type` | string | Optional | Type of cargo (e.g., "Poultry", "Seafood", "Dairy") | Max 50 chars |
| `temp_c` | float | ✅ Yes | Temperature reading in Celsius | -40.0 to 85.0 |
| `battery_pct` | integer | ⚠️ Recommended | Sensor battery percentage | 0 to 100 |
| `link_quality` | integer | Optional | BLE RSSI in dBm | -100 to 0 |
| `status` | string | Optional | Pre-computed status (NOMINAL/WARNING/CRITICAL) | Enum |

---

## Data Types & Constraints

### Timestamp Format

The `timestamp` field MUST be in ISO 8601 format with UTC timezone:

```
YYYY-MM-DDTHH:MM:SSZ
```

**Examples:**
- ✅ `"2026-01-16T14:30:00Z"` - Correct
- ✅ `"2026-01-16T14:30:00+00:00"` - Correct (explicit UTC)
- ❌ `"2026-01-16 14:30:00"` - Incorrect (missing T and Z)
- ❌ `"16/01/2026 14:30"` - Incorrect (wrong format)

**ESP32 Code to Generate Timestamp:**
```cpp
#include <time.h>

String getISOTimestamp() {
    time_t now;
    struct tm timeinfo;
    time(&now);
    gmtime_r(&now, &timeinfo);
    
    char buffer[30];
    strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
    return String(buffer);
}
```

### ID Naming Conventions

| Field | Convention | Examples |
|-------|------------|----------|
| `gateway_id` | TRUCK-{number} | TRUCK-402, TRUCK-1001 |
| `trip_id` | TRIP-{origin}-{dest}-{seq} | TRIP-CHN-BLR-05 |
| `node_id` | BOX-{zone}{number} | BOX-A12, BOX-B05 |

### Status Enum Values

The `status` field in cargo sensors should be one of:

| Value | Meaning | Trigger Condition |
|-------|---------|-------------------|
| `NOMINAL` | All parameters within safe limits | temp < 7.0°C AND battery > 20% |
| `WARNING` | Approaching threshold | 7.0°C ≤ temp < 10.0°C OR 10% ≤ battery < 20% |
| `CRITICAL` | Immediate attention required | temp ≥ 10.0°C OR battery < 10% |

---

## ESP32 Code Examples

### Complete ArduinoJson Implementation

```cpp
#include <ArduinoJson.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>

// Configuration
const char* VECNA_ENDPOINT = "http://your-server.com/api/v1/telemetry";
const char* GATEWAY_ID = "TRUCK-402";
const char* TRIP_ID = "TRIP-CHN-BLR-05";

// Sensor data structures
struct GPSData {
    float lat;
    float lng;
    float speed_kmh;
    float heading_deg;
    int satellites;
};

struct GatewayHealth {
    int battery_mv;
    int signal_strength_dbm;
    unsigned long uptime_seconds;
    float cpu_temp_c;
};

struct CargoSensor {
    String node_id;
    String product_type;
    float temp_c;
    int battery_pct;
    int link_quality;
    String status;
};

// Build and send telemetry
bool sendTelemetry(GPSData& gps, GatewayHealth& health, 
                   CargoSensor sensors[], int sensorCount) {
    
    // Calculate required JSON document size
    // Base: ~300 bytes + ~150 bytes per sensor
    const size_t capacity = JSON_OBJECT_SIZE(4) +      // Root
                           JSON_OBJECT_SIZE(5) +       // location
                           JSON_OBJECT_SIZE(4) +       // gateway_health
                           JSON_ARRAY_SIZE(sensorCount) + 
                           sensorCount * JSON_OBJECT_SIZE(6) +
                           512; // String buffer
    
    DynamicJsonDocument doc(capacity);
    
    // Root level fields
    doc["gateway_id"] = GATEWAY_ID;
    doc["trip_id"] = TRIP_ID;
    doc["timestamp"] = getISOTimestamp();
    
    // Location object (nested)
    JsonObject location = doc.createNestedObject("location");
    location["lat"] = gps.lat;
    location["lng"] = gps.lng;
    location["speed_kmh"] = gps.speed_kmh;
    location["heading_deg"] = gps.heading_deg;
    location["satellites"] = gps.satellites;
    
    // Gateway health object (nested)
    JsonObject gateway_health = doc.createNestedObject("gateway_health");
    gateway_health["battery_mv"] = health.battery_mv;
    gateway_health["signal_strength_dbm"] = health.signal_strength_dbm;
    gateway_health["uptime_seconds"] = health.uptime_seconds;
    gateway_health["cpu_temp_c"] = health.cpu_temp_c;
    
    // Cargo sensors array
    JsonArray cargo_sensors = doc.createNestedArray("cargo_sensors");
    for (int i = 0; i < sensorCount; i++) {
        JsonObject sensor = cargo_sensors.createNestedObject();
        sensor["node_id"] = sensors[i].node_id;
        sensor["product_type"] = sensors[i].product_type;
        sensor["temp_c"] = sensors[i].temp_c;
        sensor["battery_pct"] = sensors[i].battery_pct;
        sensor["link_quality"] = sensors[i].link_quality;
        sensor["status"] = sensors[i].status;
    }
    
    // Serialize to string
    String jsonPayload;
    serializeJson(doc, jsonPayload);
    
    // Send HTTP POST
    HTTPClient http;
    http.begin(VECNA_ENDPOINT);
    http.addHeader("Content-Type", "application/json");
    
    int httpResponseCode = http.POST(jsonPayload);
    
    if (httpResponseCode == 201) {
        Serial.println("✓ Telemetry sent successfully");
        http.end();
        return true;
    } else {
        Serial.printf("✗ HTTP Error: %d\n", httpResponseCode);
        Serial.println(http.getString());
        http.end();
        return false;
    }
}

// Utility: Get ISO timestamp
String getISOTimestamp() {
    time_t now;
    struct tm timeinfo;
    time(&now);
    gmtime_r(&now, &timeinfo);
    
    char buffer[30];
    strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
    return String(buffer);
}

// Utility: Compute sensor status
String computeStatus(float temp_c, int battery_pct) {
    if (temp_c >= 10.0 || battery_pct < 10) {
        return "CRITICAL";
    } else if (temp_c >= 7.0 || battery_pct < 20) {
        return "WARNING";
    }
    return "NOMINAL";
}

// Example usage in loop()
void loop() {
    // Collect GPS data
    GPSData gps = {
        .lat = 13.0827,
        .lng = 80.2707,
        .speed_kmh = 62.5,
        .heading_deg = 270.0,
        .satellites = 8
    };
    
    // Collect gateway health
    GatewayHealth health = {
        .battery_mv = readBatteryVoltage(),
        .signal_strength_dbm = WiFi.RSSI(),
        .uptime_seconds = millis() / 1000,
        .cpu_temp_c = temperatureRead()  // ESP32 internal temp
    };
    
    // Collect sensor data from BLE slaves
    CargoSensor sensors[4];
    int sensorCount = collectBLESensorData(sensors);  // Your BLE collection function
    
    // Send telemetry
    sendTelemetry(gps, health, sensors, sensorCount);
    
    delay(30000); // Send every 30 seconds
}
```

### Minimal Payload Example

If some sensors are offline or data unavailable, send what you have:

```cpp
// Minimal required payload
DynamicJsonDocument doc(256);
doc["gateway_id"] = "TRUCK-402";
doc["trip_id"] = "TRIP-CHN-BLR-05";
doc["timestamp"] = getISOTimestamp();

// Empty arrays are valid
JsonArray cargo_sensors = doc.createNestedArray("cargo_sensors");
// No sensors added - this is OK!

// Send it
String jsonPayload;
serializeJson(doc, jsonPayload);
```

---

## Error Handling

### Response Format

**Success (201):**
```json
{
  "success": true,
  "message": "Telemetry ingested successfully",
  "data": {
    "frame_id": 1234,
    "trip_id": "TRIP-CHN-BLR-05",
    "sensors_processed": 4,
    "alerts_generated": 2
  }
}
```

**Validation Error (400):**
```json
{
  "success": false,
  "error": "Missing required fields: gateway_id, timestamp"
}
```

**Server Error (500):**
```json
{
  "success": false,
  "error": "Server error: Database connection failed"
}
```

### ESP32 Retry Logic

```cpp
bool sendWithRetry(String& payload, int maxRetries = 3) {
    for (int attempt = 1; attempt <= maxRetries; attempt++) {
        HTTPClient http;
        http.begin(VECNA_ENDPOINT);
        http.addHeader("Content-Type", "application/json");
        http.setTimeout(10000); // 10 second timeout
        
        int code = http.POST(payload);
        http.end();
        
        if (code == 201) {
            return true;
        }
        
        Serial.printf("Attempt %d failed (code %d), retrying...\n", 
                      attempt, code);
        delay(attempt * 2000); // Exponential backoff
    }
    
    // Store locally for later sync
    storeOfflineData(payload);
    return false;
}
```

---

## Best Practices

### 1. Time Synchronization

Ensure NTP sync on boot for accurate timestamps:

```cpp
void syncTime() {
    configTime(0, 0, "pool.ntp.org", "time.nist.gov");
    
    Serial.print("Syncing time");
    while (time(nullptr) < 1000000000) {
        Serial.print(".");
        delay(100);
    }
    Serial.println(" done!");
}
```

### 2. Sensor Status Pre-computation

Calculate status on the gateway to reduce server load:

```cpp
String computeStatus(float temp, int battery) {
    // Critical conditions
    if (temp >= 10.0) return "CRITICAL";
    if (battery < 10) return "CRITICAL";
    
    // Warning conditions
    if (temp >= 7.0) return "WARNING";
    if (battery < 20) return "WARNING";
    
    return "NOMINAL";
}
```

### 3. Offline Data Buffering

Store telemetry locally when connectivity is lost:

```cpp
#include <SPIFFS.h>
#include <ArduinoJson.h>

void storeOfflineData(String& payload) {
    File file = SPIFFS.open("/offline_buffer.jsonl", FILE_APPEND);
    if (file) {
        file.println(payload);
        file.close();
    }
}

void syncOfflineData() {
    if (!SPIFFS.exists("/offline_buffer.jsonl")) return;
    
    File file = SPIFFS.open("/offline_buffer.jsonl", FILE_READ);
    while (file.available()) {
        String line = file.readStringUntil('\n');
        if (line.length() > 0) {
            // Try to send buffered data
            HTTPClient http;
            http.begin(VECNA_ENDPOINT);
            http.addHeader("Content-Type", "application/json");
            http.POST(line);
            http.end();
        }
    }
    file.close();
    SPIFFS.remove("/offline_buffer.jsonl");
}
```

### 4. Heartbeat Intervals

| Scenario | Interval | Notes |
|----------|----------|-------|
| Active Trip (moving) | 30 seconds | Full telemetry |
| Active Trip (parked) | 60 seconds | Reduce battery drain |
| Idle Mode | 5 minutes | Location + health only |
| Emergency (temp alert) | 10 seconds | Rapid updates |

---

## Checklist Before Deployment

- [ ] NTP time sync configured
- [ ] Correct `gateway_id` set in firmware
- [ ] Trip ID management implemented
- [ ] BLE scanning for all slave nodes
- [ ] GPS module parsing tested
- [ ] Battery voltage ADC calibrated
- [ ] WiFi/4G failover logic
- [ ] Offline buffer implemented
- [ ] Alert threshold values match server
- [ ] Retry logic with exponential backoff

---

## Support

For integration support or to report issues:
- **Email:** iot-support@vecna-coldchain.com
- **Documentation:** https://docs.vecna-coldchain.com
- **API Status:** https://status.vecna-coldchain.com

---

*This document is part of the VECNA Cold Chain Monitoring System.*
