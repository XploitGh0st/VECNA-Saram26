# VECNA - Verified Expiry & Cold-chain Navigation Assistant

A robust IoT backend and real-time dashboard for monitoring refrigerated cargo in trucks with **live Server-Sent Events (SSE)** updates.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)
![Real-time](https://img.shields.io/badge/Real--time-SSE-brightgreen.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## ✨ Key Features

- **⚡ Real-time Updates** - Dashboard updates instantly via Server-Sent Events (SSE)
- **🌡️ Temperature Monitoring** - Continuous chicken package container monitoring
- **📡 Live Telemetry** - ESP32 gateway with GPS, signal strength, and health metrics
- **🗺️ Interactive Map** - Live vehicle tracking with Leaflet.js
- **🚨 Intelligent Alerts** - Auto-detection of temperature violations and low battery
- **💾 Normalized Database** - SQLAlchemy ORM with Trucks, Trips, Sensors, and Alerts
- **📊 Professional Dashboard** - Dark-themed mission control interface

## 🚀 Quick Start

See [QUICKSTART.md](QUICKSTART.md) for a 3-step guide to get running!

### 1. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 2. Run the Server

```powershell
python app.py
```

### 3. Open Dashboard & Send Test Data

**Open browser:**
```
http://localhost:5000
```

**Send test data (new terminal):**
```powershell
# Single update
python send_sample_data.py

# Continuous updates every 5 seconds
python send_sample_data.py --continuous 5
```

Watch the dashboard update in real-time! ✨

## 📦 Chicken Package Monitoring

The system is configured for **one device**:
- **Device ID**: `CHICKEN-PKG-001`
- **Product**: Chicken Package Container
- **Temperature Range**:
  - 🟢 Normal: 0-6.9°C
  - 🟡 Warning: 7.0-9.9°C
  - 🔴 Critical: ≥10°C

## 🔌 API Endpoints

### Real-time Stream (SSE)
```
GET /api/v1/stream
```
Server-Sent Events endpoint for real-time dashboard updates.

### Telemetry Ingestion

```
POST /api/v1/telemetry
Content-Type: application/json
```

**Example Payload (Chicken Package):**
```json
{
  "gateway_id": "TRUCK-402",
  "trip_id": "TRIP-CHICKEN-20260121",
  "timestamp": "2026-01-21T14:30:00Z",
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
      "node_id": "CHICKEN-PKG-001",
      "product_type": "Chicken Package",
      "temp_c": 3.5,
      "battery_pct": 85,
      "link_quality": -72
    }
  ]
}
```
stream` | **SSE real-time updates** |
| GET | `/api/v1/dashboard/summary` | Get all active trip data |
| GET | `/api/v1/trucks` | List all registered trucks |
| GET | `/api/v1/trips` | List all trips |
| GET | `/api/v1/trips/<trip_id>/latest` | Get latest telemetry for a trip |
| GET | `/api/v1/alerts` | Get all unresolved alerts |
| POST | `/api/v1/alerts/<id>/resolve` | Resolve an alert |

## 🎯 Real-Time Updates

The dashboard connects to `/api/v1/stream` for instant updates:
- ⚡ Updates appear within **milliseconds**
- 🔄 Automatic reconnection on disconnect
- 📡 Keepalive messages maintain connection
- 💪 Fallback polling as backup

See [REALTIME_UPDATES.md](REALTIME_UPDATES.md) for technical details.ata |
| GET | `/api/v1/trucks` | List all registered trucks |
| GET | `/api/v1/trips` | List all trips |
| GET | `/api/v1/trips/<trip_id>/latest` | Get latest telemetry for a trip |
| GET | `/api/v1/alerts` | Get all unresolved alerts |
| POST | `/api/v1/alerts/<id>/resolve` | Resolve an alert |

## Database Schema

```
┌─────────────┐       ┌─────────────┐       ┌──────────────────┐
│   Trucks    │       │    Trips    │       │ TelemetryFrames  │
├─────────────┤       ├─────────────┤       ├──────────────────┤
│ gateway_id  │──────▶│ truck_id    │──────▶│ trip_id          │
│ plate_number│       │ trip_id     │       │ timestamp        │
│ driver_name │       │ origin      │       │ lat, lng         │
│ truck_model │       │ destination │       │ speed_kmh        │
└─────────────┘       │ status      │       │ battery_mv       │
                      └─────────────┘       │ cpu_temp_c       │
                                            └────────┬─────────┘
                                                     │
                      ┌──────────────────┐           │
                      │  SensorReadings  │◀──────────┤
                      ├──────────────────┤           │
                      │ node_id          │           │
                      │ temp_c           │           ▼
                      │ battery_pct      │    ┌─────────────────┐
                      │ status           │    │  SystemAlerts   │
                      └──────────────────┘    ├─────────────────┤
                                              │ alert_type      │
                                              │ severity        │
                                              │ meswith SSE
├── requirements.txt               # Python dependencies
├── send_sample_data.py            # Test data generator
├── QUICKSTART.md                  # ⭐ Start here!
├── REALTIME_UPDATES.md            # SSE technical docs
├── HARDWARE_INTEGRATION_MANUAL.md # ESP32 firmware guide
├── README.md                      # This file
├── templates/
│   └── dashboard.html             # Real-time dashboard UI
└── instance/
    └── vecna.dbarning | Critical |
|------------|---------|----------|
| Temperature | ≥ 7.0°C | ≥ 10.0°C |
| Battery | < 20% | < 10% |
| Signal | < -85 dBm | - |

## Project Structure

```
VECNA/
├── app.py                         # Flask backend server
├── requirements.txt               # Python dependencies
├── HARDWARE_INTEGRATION_MANUAL.md # ESP32 firmware guide
├──🧪 Testing

### Using the Test Script
```powershell
# Single test
python send_sample_data.py

# Every 5 seconds
python send_sample_daCHICKEN-20260121",
    "timestamp": "2026-01-21T14:30:00Z",
    "location": {"lat": 13.0827, "lng": 80.2707, "speed_kmh": 50},
    "cargo_sensors": [
      {"node_id": "CHICKEN-PKG-001", "product_type": "Chicken Package", "temp_c": 3.5, "battery_pct": 90, "link_quality": -7

### Using                    # This file
├── templates/
│   └── dashboard.html             # Mission Control UI
└── vecna.db                       # SQLite database (auto-created)
```

## Hardware Integration

See [HARDWARE_INTEGRATION_MANUAL.md](HARDWARE_INTEGRATION_MANUAL.md) for detailed instructions on:
- JSON payload format
- ESP32 code examples
- ArduinoJson implementation
- Error handling and retry logic
- Best practices

## Testing with cURL

```bash
# Send test telemetry
curl -X POST http://localhost:5000/api/v1/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "gateway_id": "TRUCK-402",
    "trip_id": "TRIP-TEST-01",
    "timestamp": "2026-01-16T14:30:00Z",
    "location": {"lat": 13.0827, "lng": 80.2707, "speed_kmh": 50},
    "cargo_sensors": [
      {"node_id": "BOX-A01", "product_type": "Dairy", "temp_c": 4.5, "battery_pct": 90}
    ]
  }'

# Get dashboard data
curl http://localhost:5000/api/v1/dashboard/summary
```

## Production Deployment

For productioReal-time cold chain monitoring for your chicken packages.* 🐔🧊

---

## 📚 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Get started in 3 steps
- **[REALTIME_UPDATES.md](REALTIME_UPDATES.md)** - SSE implementation details
- **[HARDWARE_INTEGRATION_MANUAL.md](HARDWARE_INTEGRATION_MANUAL.md)** - ESP32 setup guide

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

Set environment variables:
```bash
export DATABASE_URL=postgresql://user:pass@host/vecna
export SECRET_KEY=your-secure-key
```

## License

MIT License - See LICENSE file for details.

---

**VECNA** - *Keeping your cold chain safe, one byte at a time.* 🧊
