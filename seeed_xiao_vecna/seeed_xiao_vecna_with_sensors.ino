/*
 * ============================================================================
 *  VECNA - Seeed Studio XIAO ESP32 with REAL SENSORS
 * ============================================================================
 *  
 *  Complete version with DHT22 temperature sensor and GPS module support.
 *  
 *  Hardware Required:
 *  - Seeed Studio XIAO ESP32C3 or ESP32S3
 *  - DHT22/AM2302 Temperature & Humidity Sensor
 *  - NEO-6M GPS Module (optional)
 *  - 3.7V LiPo Battery (optional)
 *  
 *  Wiring:
 *  ┌─────────────────────────────────────────────────────────────┐
 *  │  DHT22 Sensor:                                              │
 *  │    VCC  → 3.3V                                              │
 *  │    GND  → GND                                               │
 *  │    DATA → D2 (GPIO2)                                        │
 *  │    (Add 10K pull-up resistor between VCC and DATA)          │
 *  │                                                             │
 *  │  GPS Module (NEO-6M):                                       │
 *  │    VCC → 3.3V                                               │
 *  │    GND → GND                                                │
 *  │    TX  → D7 (GPIO21 on ESP32C3)                             │
 *  │    RX  → D6 (GPIO20 on ESP32C3)                             │
 *  │                                                             │
 *  │  Battery Monitoring (optional):                             │
 *  │    Battery+ → Voltage Divider → D0 (A0)                     │
 *  └─────────────────────────────────────────────────────────────┘
 *  
 *  Libraries Required (Install via Arduino Library Manager):
 *  - ArduinoJson by Benoit Blanchon
 *  - DHT sensor library by Adafruit
 *  - TinyGPSPlus by Mikal Hart
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
#include <DHT.h>
#include <TinyGPSPlus.h>
#include <HardwareSerial.h>

// ============================================================================
//  CONFIGURATION - UPDATE THESE VALUES!
// ============================================================================

// WiFi Credentials - CHANGE THESE!
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// VECNA Server - CHANGE THIS TO YOUR PC's IP!
const char* SERVER_IP = "192.168.1.100";
const int SERVER_PORT = 5000;
String API_ENDPOINT = "/api/v1/telemetry";

// Device Configuration
const char* GATEWAY_ID = "TRUCK-402";
const char* TRIP_ID_PREFIX = "TRIP-CHICKEN";
const char* NODE_ID = "CHICKEN-PKG-001";
const char* PRODUCT_TYPE = "Chicken Package";

// Timing
const unsigned long SEND_INTERVAL_MS = 10000;   // 10 seconds
const unsigned long WIFI_TIMEOUT_MS = 20000;    // 20 seconds
const unsigned long GPS_TIMEOUT_MS = 2000;      // 2 seconds

// NTP for timestamps
const char* NTP_SERVER = "pool.ntp.org";
const long GMT_OFFSET_SEC = 19800;              // IST = +5:30
const int DAYLIGHT_OFFSET_SEC = 0;

// ============================================================================
//  PIN DEFINITIONS - Seeed Studio XIAO ESP32C3
// ============================================================================

#define DHT_PIN           D2      // DHT22 Data Pin
#define DHT_TYPE          DHT22   // DHT22 or DHT11

#define GPS_SERIAL_RX     D7      // GPS TX → ESP32 RX
#define GPS_SERIAL_TX     D6      // GPS RX → ESP32 TX
#define GPS_BAUD          9600

#define BATTERY_PIN       D0      // ADC for battery monitoring
#define LED_PIN           D10     // Status LED

// Enable/Disable Features
#define USE_DHT_SENSOR    true
#define USE_GPS_MODULE    false   // Set to true if you have GPS connected
#define USE_BATTERY_ADC   false   // Set to true if monitoring battery

// ============================================================================
//  GLOBAL OBJECTS
// ============================================================================

#if USE_DHT_SENSOR
DHT dht(DHT_PIN, DHT_TYPE);
#endif

#if USE_GPS_MODULE
TinyGPSPlus gps;
HardwareSerial gpsSerial(1);  // Use UART1
#endif

// State variables
unsigned long lastSendTime = 0;
int frameCount = 0;
bool wifiConnected = false;

// GPS Data (defaults for Chennai if no GPS)
float currentLatitude = 13.0827;
float currentLongitude = 80.2707;
float currentSpeed = 0.0;
int currentHeading = 0;
int satellites = 0;
bool gpsValid = false;

// Sensor Data
float lastTemperature = 0.0;
float lastHumidity = 0.0;
bool sensorValid = false;

// ============================================================================
//  SENSOR FUNCTIONS
// ============================================================================

float readTemperature() {
  #if USE_DHT_SENSOR
    float temp = dht.readTemperature();
    
    if (isnan(temp)) {
      Serial.println("  [WARN] DHT22 read failed, using last value");
      return lastTemperature;
    }
    
    lastTemperature = temp;
    sensorValid = true;
    return temp;
  #else
    // Simulate temperature if no sensor
    float baseTemp = 3.5;
    float variation = (random(-10, 15)) / 10.0;
    return baseTemp + variation;
  #endif
}

float readHumidity() {
  #if USE_DHT_SENSOR
    float humidity = dht.readHumidity();
    
    if (isnan(humidity)) {
      return lastHumidity;
    }
    
    lastHumidity = humidity;
    return humidity;
  #else
    return random(60, 80);
  #endif
}

int readBatteryPercent() {
  #if USE_BATTERY_ADC
    // Read ADC value
    int adcValue = analogRead(BATTERY_PIN);
    
    // Convert to voltage (assuming 1:1 voltage divider)
    // XIAO ESP32C3 ADC is 12-bit (0-4095), 3.3V reference
    float voltage = (adcValue / 4095.0) * 3.3 * 2;  // *2 for divider
    
    // Map voltage to percentage (3.2V = 0%, 4.2V = 100%)
    int percent = map(voltage * 100, 320, 420, 0, 100);
    return constrain(percent, 0, 100);
  #else
    return random(75, 100);
  #endif
}

int readGatewayBatteryMv() {
  #if USE_BATTERY_ADC
    int adcValue = analogRead(BATTERY_PIN);
    float voltage = (adcValue / 4095.0) * 3.3 * 2;
    return (int)(voltage * 1000);  // Convert to millivolts
  #else
    return random(3600, 4200);
  #endif
}

int getSignalStrength() {
  if (WiFi.status() == WL_CONNECTED) {
    return WiFi.RSSI();
  }
  return -80;
}

unsigned long getUptimeSeconds() {
  return millis() / 1000;
}

float getCpuTemperature() {
  return temperatureRead();
}

// ============================================================================
//  GPS FUNCTIONS
// ============================================================================

void updateGPSData() {
  #if USE_GPS_MODULE
    unsigned long start = millis();
    
    // Read GPS data for a bit
    while (millis() - start < GPS_TIMEOUT_MS) {
      while (gpsSerial.available() > 0) {
        if (gps.encode(gpsSerial.read())) {
          
          if (gps.location.isValid()) {
            currentLatitude = gps.location.lat();
            currentLongitude = gps.location.lng();
            gpsValid = true;
          }
          
          if (gps.speed.isValid()) {
            currentSpeed = gps.speed.kmph();
          }
          
          if (gps.course.isValid()) {
            currentHeading = (int)gps.course.deg();
          }
          
          if (gps.satellites.isValid()) {
            satellites = gps.satellites.value();
          }
        }
      }
    }
    
    if (!gpsValid) {
      Serial.println("  [WARN] GPS not valid, using default location");
    }
  #else
    // Simulate GPS movement for testing
    currentLatitude += (random(-100, 100) / 100000.0);
    currentLongitude += (random(-100, 100) / 100000.0);
    currentSpeed = random(40, 80);
    currentHeading = random(0, 359);
    satellites = random(6, 12);
    gpsValid = false;
  #endif
}

// ============================================================================
//  TIMESTAMP FUNCTIONS
// ============================================================================

String getISOTimestamp() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
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
  Serial.println("\n┌────────────────────────────────────┐");
  Serial.println("│     Connecting to WiFi...          │");
  Serial.println("└────────────────────────────────────┘");
  Serial.print("  SSID: ");
  Serial.println(WIFI_SSID);
  
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
      Serial.println("\n  [ERROR] WiFi timeout!");
      return false;
    }
  }
  
  Serial.println();
  Serial.println("  ✓ Connected!");
  Serial.print("  IP: ");
  Serial.println(WiFi.localIP());
  Serial.print("  RSSI: ");
  Serial.print(WiFi.RSSI());
  Serial.println(" dBm");
  
  return true;
}

// ============================================================================
//  BUILD & SEND TELEMETRY
// ============================================================================

String buildTelemetryPayload() {
  StaticJsonDocument<1024> doc;
  
  doc["gateway_id"] = GATEWAY_ID;
  doc["trip_id"] = getTodayTripId();
  doc["timestamp"] = getISOTimestamp();
  
  // Location
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
  
  // Cargo sensor
  JsonArray sensors = doc.createNestedArray("cargo_sensors");
  JsonObject sensor1 = sensors.createNestedObject();
  sensor1["node_id"] = NODE_ID;
  sensor1["product_type"] = PRODUCT_TYPE;
  sensor1["temp_c"] = readTemperature();
  sensor1["battery_pct"] = readBatteryPercent();
  sensor1["link_quality"] = random(-75, -55);
  
  String payload;
  serializeJson(doc, payload);
  return payload;
}

bool sendTelemetry() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[!] WiFi disconnected. Reconnecting...");
    if (!connectWiFi()) {
      return false;
    }
  }
  
  String url = "http://" + String(SERVER_IP) + ":" + String(SERVER_PORT) + API_ENDPOINT;
  
  updateGPSData();
  String payload = buildTelemetryPayload();
  
  // Print nicely formatted
  Serial.println("\n╔════════════════════════════════════════╗");
  Serial.println("║        SENDING TELEMETRY               ║");
  Serial.println("╠════════════════════════════════════════╣");
  Serial.print("║  URL: ");
  Serial.println(url);
  Serial.println("╠════════════════════════════════════════╣");
  
  StaticJsonDocument<1024> doc;
  deserializeJson(doc, payload);
  
  Serial.print("  Gateway: ");
  Serial.println(doc["gateway_id"].as<String>());
  Serial.print("  Trip: ");
  Serial.println(doc["trip_id"].as<String>());
  Serial.print("  Time: ");
  Serial.println(doc["timestamp"].as<String>());
  Serial.print("  Location: ");
  Serial.print(doc["location"]["lat"].as<float>(), 6);
  Serial.print(", ");
  Serial.println(doc["location"]["lng"].as<float>(), 6);
  Serial.print("  Speed: ");
  Serial.print(doc["location"]["speed_kmh"].as<float>());
  Serial.println(" km/h");
  
  // Sensor readings
  JsonArray sensors = doc["cargo_sensors"];
  for (JsonObject sensor : sensors) {
    Serial.println("  ────────────────────────────────────");
    Serial.print("  Sensor: ");
    Serial.println(sensor["node_id"].as<String>());
    Serial.print("  Product: ");
    Serial.println(sensor["product_type"].as<String>());
    Serial.print("  Temperature: ");
    Serial.print(sensor["temp_c"].as<float>(), 1);
    Serial.println(" °C");
    Serial.print("  Battery: ");
    Serial.print(sensor["battery_pct"].as<int>());
    Serial.println(" %");
  }
  
  Serial.println("╠════════════════════════════════════════╣");
  
  // Send HTTP request
  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(10000);
  
  int httpCode = http.POST(payload);
  String response = http.getString();
  
  if (httpCode == 201) {
    Serial.println("║  ✓ SUCCESS!                            ║");
    
    StaticJsonDocument<512> respDoc;
    deserializeJson(respDoc, response);
    
    Serial.print("║  Frame ID: ");
    Serial.print(respDoc["data"]["frame_id"].as<int>());
    Serial.println("                          ║");
    Serial.print("║  Alerts: ");
    Serial.print(respDoc["data"]["alerts_generated"].as<int>());
    Serial.println("                              ║");
    
    frameCount++;
    http.end();
    Serial.println("╚════════════════════════════════════════╝\n");
    return true;
    
  } else {
    Serial.println("║  ✗ FAILED!                             ║");
    Serial.print("║  Code: ");
    Serial.print(httpCode);
    Serial.println("                              ║");
    http.end();
    Serial.println("╚════════════════════════════════════════╝\n");
    return false;
  }
}

// ============================================================================
//  LED INDICATOR
// ============================================================================

void blinkLED(int times, int delayMs) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(delayMs);
    digitalWrite(LED_PIN, LOW);
    delay(delayMs);
  }
}

// ============================================================================
//  SETUP
// ============================================================================

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  // ASCII Art Header
  Serial.println("\n");
  Serial.println("╔══════════════════════════════════════════════════════════╗");
  Serial.println("║                                                          ║");
  Serial.println("║   ██╗   ██╗███████╗ ██████╗███╗   ██╗ █████╗             ║");
  Serial.println("║   ██║   ██║██╔════╝██╔════╝████╗  ██║██╔══██╗            ║");
  Serial.println("║   ██║   ██║█████╗  ██║     ██╔██╗ ██║███████║            ║");
  Serial.println("║   ╚██╗ ██╔╝██╔══╝  ██║     ██║╚██╗██║██╔══██║            ║");
  Serial.println("║    ╚████╔╝ ███████╗╚██████╗██║ ╚████║██║  ██║            ║");
  Serial.println("║     ╚═══╝  ╚══════╝ ╚═════╝╚═╝  ╚═══╝╚═╝  ╚═╝            ║");
  Serial.println("║                                                          ║");
  Serial.println("║        Cold Chain Monitoring System - Seeed XIAO         ║");
  Serial.println("║                    With Real Sensors                     ║");
  Serial.println("║                                                          ║");
  Serial.println("╚══════════════════════════════════════════════════════════╝");
  Serial.println();
  
  // Initialize pins
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  
  // Initialize DHT sensor
  #if USE_DHT_SENSOR
    Serial.println("Initializing DHT22 sensor...");
    dht.begin();
    delay(2000);  // DHT22 needs 2 seconds to stabilize
    Serial.println("  ✓ DHT22 ready");
  #endif
  
  // Initialize GPS
  #if USE_GPS_MODULE
    Serial.println("Initializing GPS module...");
    gpsSerial.begin(GPS_BAUD, SERIAL_8N1, GPS_SERIAL_RX, GPS_SERIAL_TX);
    Serial.println("  ✓ GPS serial ready");
  #endif
  
  // Print config
  Serial.println("\nConfiguration:");
  Serial.print("  Gateway ID: ");
  Serial.println(GATEWAY_ID);
  Serial.print("  Server: http://");
  Serial.print(SERVER_IP);
  Serial.print(":");
  Serial.println(SERVER_PORT);
  Serial.print("  Interval: ");
  Serial.print(SEND_INTERVAL_MS / 1000);
  Serial.println(" seconds");
  Serial.print("  DHT Sensor: ");
  Serial.println(USE_DHT_SENSOR ? "Enabled" : "Simulated");
  Serial.print("  GPS Module: ");
  Serial.println(USE_GPS_MODULE ? "Enabled" : "Simulated");
  Serial.println();
  
  // Connect WiFi
  if (connectWiFi()) {
    wifiConnected = true;
    blinkLED(3, 100);
    
    // Sync time
    Serial.println("\nSyncing NTP time...");
    configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);
    
    struct tm timeinfo;
    int attempts = 0;
    while (!getLocalTime(&timeinfo) && attempts < 10) {
      delay(500);
      Serial.print(".");
      attempts++;
    }
    Serial.println();
    
    if (attempts < 10) {
      Serial.print("  Time: ");
      Serial.println(getISOTimestamp());
    }
    
    // Initial reading
    #if USE_DHT_SENSOR
      Serial.println("\nInitial sensor reading:");
      float temp = readTemperature();
      float hum = readHumidity();
      Serial.print("  Temperature: ");
      Serial.print(temp, 1);
      Serial.println(" °C");
      Serial.print("  Humidity: ");
      Serial.print(hum, 1);
      Serial.println(" %");
    #endif
    
    // Send first telemetry
    Serial.println("\nSending initial telemetry...");
    sendTelemetry();
    
  } else {
    blinkLED(10, 50);
  }
  
  Serial.println("\n════════════════════════════════════════");
  Serial.println("  System Running - Monitoring Started");
  Serial.println("════════════════════════════════════════\n");
}

// ============================================================================
//  MAIN LOOP
// ============================================================================

void loop() {
  unsigned long currentTime = millis();
  
  if (currentTime - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = currentTime;
    
    if (sendTelemetry()) {
      blinkLED(1, 50);
    } else {
      blinkLED(5, 50);
    }
    
    // Stats
    Serial.println("────────────────────────────────────────");
    Serial.print("  Frames sent: ");
    Serial.println(frameCount);
    Serial.print("  Uptime: ");
    Serial.print(getUptimeSeconds() / 60);
    Serial.println(" minutes");
    Serial.print("  Free heap: ");
    Serial.print(ESP.getFreeHeap() / 1024);
    Serial.println(" KB");
    Serial.println("────────────────────────────────────────\n");
  }
  
  // Process GPS data continuously
  #if USE_GPS_MODULE
    while (gpsSerial.available() > 0) {
      gps.encode(gpsSerial.read());
    }
  #endif
  
  delay(100);
}
