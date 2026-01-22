/*
 * ============================================================================
 *  VECNA - Seeed Studio XIAO ESP32 Telemetry Sender
 * ============================================================================
 *  
 *  This code runs on Seeed Studio XIAO ESP32C3/S3 to send cold-chain 
 *  telemetry data to the VECNA dashboard via WiFi.
 *  
 *  Hardware Connections:
 *  - DHT22/AM2302 Temperature Sensor → D2 (GPIO2)
 *  - GPS Module (NEO-6M) → RX=D7, TX=D6 (or software serial)
 *  - Optional: Battery monitoring via ADC
 *  
 *  Author: VECNA Project
 *  Date: January 2026
 *  
 * ============================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>

// ============================================================================
//  CONFIGURATION - UPDATE THESE VALUES!
// ============================================================================

// WiFi Credentials
const char* WIFI_SSID = "YOUR_WIFI_SSID";           // <-- Change this!
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";   // <-- Change this!

// VECNA Server Configuration
const char* SERVER_IP = "192.168.1.100";            // <-- Change to your PC's IP!
const int SERVER_PORT = 5000;
String API_ENDPOINT = "/api/v1/telemetry";

// Device Configuration
const char* GATEWAY_ID = "TRUCK-402";               // Unique truck identifier
const char* TRIP_ID_PREFIX = "TRIP-CHICKEN";        // Trip ID prefix
const char* NODE_ID = "CHICKEN-PKG-001";            // Sensor node ID
const char* PRODUCT_TYPE = "Chicken Package";       // Product being monitored

// Timing Configuration
const unsigned long SEND_INTERVAL_MS = 10000;       // Send data every 10 seconds
const unsigned long WIFI_TIMEOUT_MS = 20000;        // WiFi connection timeout

// NTP Configuration (for accurate timestamps)
const char* NTP_SERVER = "pool.ntp.org";
const long GMT_OFFSET_SEC = 19800;                  // IST = UTC + 5:30 (19800 seconds)
const int DAYLIGHT_OFFSET_SEC = 0;

// ============================================================================
//  PIN DEFINITIONS
// ============================================================================

// For XIAO ESP32C3
#define TEMP_SENSOR_PIN   D2    // DHT22 Data Pin
#define BATTERY_ADC_PIN   D0    // Battery voltage divider (optional)
#define LED_BUILTIN_PIN   D10   // Onboard LED (varies by board)

// GPS Serial (if using hardware serial)
#define GPS_RX_PIN        D7
#define GPS_TX_PIN        D6

// ============================================================================
//  GLOBAL VARIABLES
// ============================================================================

unsigned long lastSendTime = 0;
int frameCount = 0;
bool wifiConnected = false;

// Simulated/Default values (replace with actual sensor readings)
float currentLatitude = 13.0827;    // Chennai default
float currentLongitude = 80.2707;
float currentSpeed = 0.0;
int currentHeading = 0;
int satellites = 0;

// ============================================================================
//  SENSOR SIMULATION (Replace with actual sensor code)
// ============================================================================

// Temperature reading (simulated - replace with DHT22/DS18B20 code)
float readTemperature() {
  // =========================================
  // TODO: Replace with actual sensor reading!
  // =========================================
  // For DHT22:
  // return dht.readTemperature();
  
  // For DS18B20:
  // sensors.requestTemperatures();
  // return sensors.getTempCByIndex(0);
  
  // Simulated temperature (2-5°C normal range for chicken)
  float baseTemp = 3.5;
  float variation = (random(-10, 15)) / 10.0;  // -1.0 to +1.5
  return baseTemp + variation;
}

// Battery percentage (simulated - replace with ADC reading)
int readBatteryPercent() {
  // =========================================
  // TODO: Replace with actual battery reading!
  // =========================================
  // Example for voltage divider on ADC:
  // int adcValue = analogRead(BATTERY_ADC_PIN);
  // float voltage = (adcValue / 4095.0) * 3.3 * 2;  // Assuming 1:1 divider
  // return map(voltage * 100, 320, 420, 0, 100);    // 3.2V=0%, 4.2V=100%
  
  return random(75, 100);
}

// Gateway battery (mV)
int readGatewayBatteryMv() {
  return random(3600, 4200);
}

// Signal strength (simulated based on WiFi RSSI)
int getSignalStrength() {
  if (WiFi.status() == WL_CONNECTED) {
    return WiFi.RSSI();
  }
  return -80;
}

// Uptime in seconds
unsigned long getUptimeSeconds() {
  return millis() / 1000;
}

// CPU temperature (ESP32 internal)
float getCpuTemperature() {
  // ESP32 internal temp sensor (approximate)
  return temperatureRead();  // Built-in function
}

// ============================================================================
//  GPS FUNCTIONS (Simulated - Replace with TinyGPS++ code)
// ============================================================================

void updateGPSData() {
  // =========================================
  // TODO: Replace with actual GPS reading!
  // =========================================
  // Using TinyGPS++:
  // while (gpsSerial.available() > 0) {
  //   if (gps.encode(gpsSerial.read())) {
  //     if (gps.location.isValid()) {
  //       currentLatitude = gps.location.lat();
  //       currentLongitude = gps.location.lng();
  //     }
  //     if (gps.speed.isValid()) {
  //       currentSpeed = gps.speed.kmph();
  //     }
  //     if (gps.course.isValid()) {
  //       currentHeading = (int)gps.course.deg();
  //     }
  //     satellites = gps.satellites.value();
  //   }
  // }
  
  // Simulated GPS movement
  currentLatitude += (random(-100, 100) / 100000.0);
  currentLongitude += (random(-100, 100) / 100000.0);
  currentSpeed = random(40, 80);
  currentHeading = random(0, 359);
  satellites = random(6, 12);
}

// ============================================================================
//  TIMESTAMP FUNCTION
// ============================================================================

String getISOTimestamp() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    // Fallback if NTP not synced
    return "2026-01-21T00:00:00Z";
  }
  
  char buffer[30];
  strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
  return String(buffer);
}

String getTodayTripId() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    return String(TRIP_ID_PREFIX) + "-20260121";
  }
  
  char buffer[20];
  strftime(buffer, sizeof(buffer), "%Y%m%d", &timeinfo);
  return String(TRIP_ID_PREFIX) + "-" + String(buffer);
}

// ============================================================================
//  WIFI CONNECTION
// ============================================================================

bool connectWiFi() {
  Serial.println("\n----------------------------------------");
  Serial.println("  Connecting to WiFi...");
  Serial.print("  SSID: ");
  Serial.println(WIFI_SSID);
  Serial.println("----------------------------------------");
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  unsigned long startTime = millis();
  int dots = 0;
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    dots++;
    
    if (dots % 40 == 0) Serial.println();
    
    if (millis() - startTime > WIFI_TIMEOUT_MS) {
      Serial.println("\n  [ERROR] WiFi connection timeout!");
      return false;
    }
  }
  
  Serial.println("\n");
  Serial.println("  ✓ WiFi Connected!");
  Serial.print("  IP Address: ");
  Serial.println(WiFi.localIP());
  Serial.print("  Signal Strength: ");
  Serial.print(WiFi.RSSI());
  Serial.println(" dBm");
  Serial.println("----------------------------------------\n");
  
  return true;
}

// ============================================================================
//  BUILD JSON PAYLOAD
// ============================================================================

String buildTelemetryPayload() {
  // Create JSON document
  StaticJsonDocument<1024> doc;
  
  // Basic info
  doc["gateway_id"] = GATEWAY_ID;
  doc["trip_id"] = getTodayTripId();
  doc["timestamp"] = getISOTimestamp();
  
  // Location data
  JsonObject location = doc.createNestedObject("location");
  location["lat"] = currentLatitude;
  location["lng"] = currentLongitude;
  location["speed_kmh"] = currentSpeed;
  location["heading_deg"] = currentHeading;
  location["satellites"] = satellites;
  
  // Gateway health
  JsonObject health = doc.createNestedObject("gateway_health");
  health["battery_mv"] = readGatewayBatteryMv();
  health["signal_strength_dbm"] = getSignalStrength();
  health["uptime_seconds"] = getUptimeSeconds();
  health["cpu_temp_c"] = getCpuTemperature();
  
  // Cargo sensors (single chicken package sensor)
  JsonArray sensors = doc.createNestedArray("cargo_sensors");
  JsonObject sensor1 = sensors.createNestedObject();
  sensor1["node_id"] = NODE_ID;
  sensor1["product_type"] = PRODUCT_TYPE;
  sensor1["temp_c"] = readTemperature();
  sensor1["battery_pct"] = readBatteryPercent();
  sensor1["link_quality"] = random(-75, -55);  // BLE RSSI simulation
  
  // Serialize to string
  String payload;
  serializeJson(doc, payload);
  
  return payload;
}

// ============================================================================
//  SEND TELEMETRY TO SERVER
// ============================================================================

bool sendTelemetry() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WARN] WiFi not connected. Attempting reconnect...");
    if (!connectWiFi()) {
      return false;
    }
  }
  
  // Build the URL
  String url = "http://" + String(SERVER_IP) + ":" + String(SERVER_PORT) + API_ENDPOINT;
  
  // Update GPS data
  updateGPSData();
  
  // Build payload
  String payload = buildTelemetryPayload();
  
  Serial.println("========================================");
  Serial.println("  SENDING TELEMETRY DATA");
  Serial.println("========================================");
  Serial.print("  URL: ");
  Serial.println(url);
  Serial.println("  Payload:");
  
  // Pretty print the JSON
  StaticJsonDocument<1024> doc;
  deserializeJson(doc, payload);
  serializeJsonPretty(doc, Serial);
  Serial.println("\n");
  
  // Send HTTP POST request
  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(10000);  // 10 second timeout
  
  int httpCode = http.POST(payload);
  String response = http.getString();
  
  Serial.print("  Response Code: ");
  Serial.println(httpCode);
  
  if (httpCode == 201) {
    Serial.println("  ✓ SUCCESS! Data sent to dashboard.");
    
    // Parse response
    StaticJsonDocument<512> respDoc;
    DeserializationError error = deserializeJson(respDoc, response);
    
    if (!error) {
      int frameId = respDoc["data"]["frame_id"] | 0;
      int sensorsProcessed = respDoc["data"]["sensors_processed"] | 0;
      int alertsGenerated = respDoc["data"]["alerts_generated"] | 0;
      
      Serial.print("  Frame ID: ");
      Serial.println(frameId);
      Serial.print("  Sensors Processed: ");
      Serial.println(sensorsProcessed);
      Serial.print("  Alerts Generated: ");
      Serial.println(alertsGenerated);
    }
    
    frameCount++;
    http.end();
    Serial.println("========================================\n");
    return true;
    
  } else {
    Serial.print("  ✗ FAILED! Error: ");
    Serial.println(response);
    http.end();
    Serial.println("========================================\n");
    return false;
  }
}

// ============================================================================
//  LED STATUS INDICATOR
// ============================================================================

void blinkLED(int times, int delayMs) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(delayMs);
    digitalWrite(LED_BUILTIN, LOW);
    delay(delayMs);
  }
}

// ============================================================================
//  SETUP
// ============================================================================

void setup() {
  // Initialize serial
  Serial.begin(115200);
  delay(1000);
  
  // Welcome message
  Serial.println("\n");
  Serial.println("╔════════════════════════════════════════════════════════╗");
  Serial.println("║                                                        ║");
  Serial.println("║   ██╗   ██╗███████╗ ██████╗███╗   ██╗ █████╗           ║");
  Serial.println("║   ██║   ██║██╔════╝██╔════╝████╗  ██║██╔══██╗          ║");
  Serial.println("║   ██║   ██║█████╗  ██║     ██╔██╗ ██║███████║          ║");
  Serial.println("║   ╚██╗ ██╔╝██╔══╝  ██║     ██║╚██╗██║██╔══██║          ║");
  Serial.println("║    ╚████╔╝ ███████╗╚██████╗██║ ╚████║██║  ██║          ║");
  Serial.println("║     ╚═══╝  ╚══════╝ ╚═════╝╚═╝  ╚═══╝╚═╝  ╚═╝          ║");
  Serial.println("║                                                        ║");
  Serial.println("║         Cold Chain Monitoring - Seeed XIAO             ║");
  Serial.println("║                                                        ║");
  Serial.println("╚════════════════════════════════════════════════════════╝");
  Serial.println();
  
  // Initialize LED
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);
  
  // Print configuration
  Serial.println("Configuration:");
  Serial.print("  Gateway ID: ");
  Serial.println(GATEWAY_ID);
  Serial.print("  Server: ");
  Serial.print(SERVER_IP);
  Serial.print(":");
  Serial.println(SERVER_PORT);
  Serial.print("  Send Interval: ");
  Serial.print(SEND_INTERVAL_MS / 1000);
  Serial.println(" seconds");
  Serial.println();
  
  // Connect to WiFi
  if (connectWiFi()) {
    wifiConnected = true;
    blinkLED(3, 100);  // Success blink
    
    // Initialize NTP
    Serial.println("Syncing time with NTP server...");
    configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);
    
    // Wait for time sync
    struct tm timeinfo;
    int attempts = 0;
    while (!getLocalTime(&timeinfo) && attempts < 10) {
      delay(500);
      attempts++;
    }
    
    if (attempts < 10) {
      Serial.print("  Time synced: ");
      Serial.println(getISOTimestamp());
    } else {
      Serial.println("  [WARN] NTP sync failed, using fallback time");
    }
    
    // Send initial data
    Serial.println("\nSending initial telemetry...");
    sendTelemetry();
    
  } else {
    blinkLED(10, 50);  // Error blink
  }
  
  Serial.println("\n========================================");
  Serial.println("  VECNA Gateway Started!");
  Serial.println("  Monitoring chicken package container...");
  Serial.println("========================================\n");
}

// ============================================================================
//  MAIN LOOP
// ============================================================================

void loop() {
  // Check if it's time to send data
  unsigned long currentTime = millis();
  
  if (currentTime - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = currentTime;
    
    // Send telemetry
    if (sendTelemetry()) {
      blinkLED(1, 50);  // Quick success blink
    } else {
      blinkLED(5, 50);  // Error blink
    }
    
    // Print stats
    Serial.print("Total frames sent: ");
    Serial.println(frameCount);
    Serial.print("Uptime: ");
    Serial.print(getUptimeSeconds());
    Serial.println(" seconds");
    Serial.print("Free heap: ");
    Serial.print(ESP.getFreeHeap());
    Serial.println(" bytes\n");
  }
  
  // Small delay to prevent watchdog issues
  delay(100);
}

// ============================================================================
//  END OF CODE
// ============================================================================
