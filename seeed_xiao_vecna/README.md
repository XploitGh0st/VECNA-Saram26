# VECNA - Seeed Studio XIAO ESP32 Setup Guide

## 🚀 Quick Start

### Step 1: Install Arduino IDE & Board Support

1. Download [Arduino IDE 2.x](https://www.arduino.cc/en/software)
2. Add ESP32 board support:
   - Go to `File` → `Preferences`
   - Add to "Additional Board Manager URLs":
     ```
     https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
     ```
   - Go to `Tools` → `Board` → `Boards Manager`
   - Search for "esp32" and install "ESP32 by Espressif Systems"

3. Select your board:
   - `Tools` → `Board` → `ESP32 Arduino` → `XIAO_ESP32C3` (or `XIAO_ESP32S3`)

### Step 2: Install Required Libraries

Go to `Sketch` → `Include Library` → `Manage Libraries` and install:

| Library | Author | Purpose |
|---------|--------|---------|
| ArduinoJson | Benoit Blanchon | JSON parsing/creation |
| DHT sensor library | Adafruit | Temperature sensor |
| TinyGPSPlus | Mikal Hart | GPS parsing |

### Step 3: Configure the Code

Open `seeed_xiao_vecna.ino` and update these values:

```cpp
// WiFi Credentials - CHANGE THESE!
const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Server IP - CHANGE THIS TO YOUR PC's IP!
const char* SERVER_IP = "192.168.1.100";  // Find with: ipconfig (Windows) or ifconfig (Mac/Linux)
```

### Step 4: Upload & Run

1. Connect your XIAO ESP32 via USB
2. Select the correct COM port: `Tools` → `Port`
3. Click Upload (→ arrow button)
4. Open Serial Monitor: `Tools` → `Serial Monitor` (115200 baud)

---

## 🔌 Hardware Wiring

### Basic Setup (Simulated Data - No Sensors)

Just the XIAO ESP32 board! Good for testing the WiFi connection.

### With DHT22 Temperature Sensor

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   DHT22 Sensor              XIAO ESP32C3                     │
│   ┌─────────┐               ┌───────────┐                    │
│   │  + ─────│───────────────│─ 3.3V     │                    │
│   │  DATA ──│───────────────│─ D2       │                    │
│   │  NC     │               │           │                    │
│   │  - ─────│───────────────│─ GND      │                    │
│   └─────────┘               └───────────┘                    │
│                                                              │
│   Note: Add 10K resistor between VCC and DATA (pull-up)      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### With GPS Module (NEO-6M)

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   NEO-6M GPS                XIAO ESP32C3                     │
│   ┌─────────┐               ┌───────────┐                    │
│   │ VCC ────│───────────────│─ 3.3V     │                    │
│   │ GND ────│───────────────│─ GND      │                    │
│   │ TX ─────│───────────────│─ D7 (RX)  │                    │
│   │ RX ─────│───────────────│─ D6 (TX)  │                    │
│   └─────────┘               └───────────┘                    │
│                                                              │
│   Note: GPS TX → ESP32 RX, GPS RX → ESP32 TX (crossed!)      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Full Setup with All Sensors

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│                      XIAO ESP32C3                                │
│                      ┌─────────┐                                 │
│    DHT22 VCC ────────│─ 3.3V   │                                 │
│    DHT22 DATA ───────│─ D2     │                                 │
│    DHT22 GND ────────│─ GND    │                                 │
│                      │         │                                 │
│    GPS VCC ──────────│─ 3.3V   │ (share with DHT22)              │
│    GPS GND ──────────│─ GND    │ (share with DHT22)              │
│    GPS TX ───────────│─ D7     │                                 │
│    GPS RX ───────────│─ D6     │                                 │
│                      │         │                                 │
│    Battery+ ─[R1]────│─ D0     │ (optional battery monitoring)   │
│             └─[R2]───│─ GND    │                                 │
│                      └─────────┘                                 │
│                                                                  │
│    R1 = R2 = 100K (voltage divider for 4.2V battery)            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📡 Finding Your PC's IP Address

### Windows
```powershell
ipconfig
# Look for "IPv4 Address" under your WiFi adapter
# Example: 192.168.1.100
```

### Mac/Linux
```bash
ifconfig | grep inet
# or
ip addr show
```

Make sure your XIAO and PC are on the **same WiFi network**!

---

## 🧪 Testing

### 1. Start the VECNA Server

```bash
cd "c:\Users\nanda\OneDrive - MSFT\Documents\Project\VECNA"
python app.py
```

You should see:
```
  Dashboard: http://localhost:5000
  API Endpoint: http://localhost:5000/api/v1/telemetry
```

### 2. Open Dashboard

Open browser: `http://localhost:5000`

### 3. Upload Code to XIAO

The Serial Monitor should show:
```
╔══════════════════════════════════════════════════════════╗
║   VECNA - Cold Chain Monitoring - Seeed XIAO            ║
╚══════════════════════════════════════════════════════════╝

  ✓ WiFi Connected!
  IP Address: 192.168.1.50
  
  ✓ SUCCESS! Data sent to dashboard.
```

### 4. See Data on Dashboard

The dashboard should update in real-time with:
- Truck location on map
- Temperature readings
- Battery status
- Alerts if temperature > 7°C

---

## 🔧 Troubleshooting

### "WiFi connection timeout!"
- Check SSID and password spelling
- Make sure 2.4GHz WiFi (not 5GHz)
- Move closer to router

### "Connection refused" or timeout
- Check SERVER_IP is correct
- Make sure Flask app.py is running
- Check Windows Firewall allows port 5000:
  ```powershell
  New-NetFirewallRule -DisplayName "VECNA Flask" -Direction Inbound -Port 5000 -Protocol TCP -Action Allow
  ```

### "DHT read failed"
- Check wiring (VCC, GND, DATA)
- Add 10K pull-up resistor between VCC and DATA
- Wait 2 seconds between readings

### No GPS fix
- Go outdoors or near window
- Wait 1-2 minutes for cold start
- Check GPS antenna connection

---

## 📋 Code Files

| File | Description |
|------|-------------|
| `seeed_xiao_vecna.ino` | Basic version with simulated sensors |
| `seeed_xiao_vecna_with_sensors.ino` | Full version with DHT22 & GPS support |

---

## 🛒 Parts List

| Component | Model | Approx. Price |
|-----------|-------|---------------|
| Microcontroller | Seeed XIAO ESP32C3 | ₹600-800 |
| Temperature Sensor | DHT22/AM2302 | ₹150-200 |
| GPS Module | NEO-6M | ₹300-400 |
| Jumper Wires | Male-Female | ₹50 |
| Breadboard | 400 point | ₹80 |
| USB-C Cable | Data cable | ₹100 |

**Total: ~₹1,300-1,600**

---

## 📞 Support

If you have issues:
1. Check Serial Monitor output
2. Verify WiFi connection
3. Test API with `curl` or Postman:
   ```bash
   curl -X POST http://YOUR_IP:5000/api/v1/telemetry \
     -H "Content-Type: application/json" \
     -d '{"gateway_id":"TEST","trip_id":"TEST-1","timestamp":"2026-01-21T12:00:00Z","cargo_sensors":[{"node_id":"S1","temp_c":5.0}]}'
   ```

Happy Monitoring! 🐔🧊
