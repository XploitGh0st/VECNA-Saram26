# VECNA Quick Start Guide
## Real-Time Chicken Package Monitoring

This guide will help you get the VECNA dashboard running with real-time updates for your chicken package container.

## 🚀 Quick Start (3 Steps)

### Step 1: Start the Server
Open PowerShell in the VECNA folder and run:
```powershell
python app.py
```

You should see:
```
✓ Database initialized successfully
✓ Demo data seeded successfully

============================================================
  VECNA - Cold Chain Monitoring System
  Starting Flask Development Server...
============================================================

  Dashboard: http://localhost:5000
  API Endpoint: http://localhost:5000/api/v1/telemetry
  Health Check: http://localhost:5000/health
```

### Step 2: Open the Dashboard
Open your web browser and navigate to:
```
http://localhost:5000
```

You'll see:
- 🗺️ Live map showing vehicle location
- 📦 Chicken package sensor card with temperature
- 📡 Gateway health metrics
- ⚠️ Real-time alerts panel

### Step 3: Send Test Data
Open a **new PowerShell window** and run:

**Single test update:**
```powershell
python send_sample_data.py
```

**Continuous updates (every 5 seconds):**
```powershell
python send_sample_data.py --continuous 5
```

Watch the dashboard update in real-time! ✨

## 📊 What You'll See

### Chicken Package Card
- **Temperature** displayed prominently
- **Green** = Normal (< 7°C)
- **Yellow** = Warning (7-9.9°C) with pulsing animation
- **Red** = Critical (≥ 10°C) with urgent pulsing
- **Battery level** and signal strength

### Live Map
- Vehicle position updates automatically
- Speed, heading, and GPS satellite count
- Truck icon with info popup

### Gateway Vitals
- Battery voltage
- Signal strength
- CPU temperature
- System uptime
- GPS status

### Alert Panel
- Real-time temperature warnings
- Battery alerts
- Signal quality issues

## 🌡️ Temperature Thresholds

| Temperature | Status | Color | Alert |
|-------------|--------|-------|-------|
| 0-6.9°C | NOMINAL | 🟢 Green | None |
| 7.0-9.9°C | WARNING | 🟡 Yellow | Temperature Alert |
| ≥10°C | CRITICAL | 🔴 Red | Critical Alert |

## 🔄 Real-Time Updates

The dashboard uses **Server-Sent Events (SSE)** for instant updates:
- No page refresh needed
- Updates appear within milliseconds
- Automatic reconnection if connection drops
- Fallback polling as backup

## 🧪 Testing Different Scenarios

The test script simulates realistic chicken storage scenarios:
- **80%** of the time: Normal temperatures (2-4°C)
- **15%** of the time: Getting warm (5-7°C)
- **5%** of the time: Warning zone (7-9°C)

## 🛠️ Connecting Your Hardware

When ready to connect your ESP32 with the chicken package sensor:

### 1. Configure your ESP32
Update these values in your ESP32 code:
```cpp
const char* API_URL = "http://YOUR_SERVER_IP:5000/api/v1/telemetry";
const char* GATEWAY_ID = "TRUCK-402";
const char* NODE_ID = "CHICKEN-PKG-001";
```

### 2. Send POST requests to:
```
http://YOUR_SERVER_IP:5000/api/v1/telemetry
```

### 3. JSON Payload Format:
```json
{
  "gateway_id": "TRUCK-402",
  "trip_id": "TRIP-CHICKEN-20260121",
  "timestamp": "2026-01-21T10:30:00Z",
  "location": {
    "lat": 13.0827,
    "lng": 80.2707,
    "speed_kmh": 65.5,
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

## 🔍 Monitoring & Debugging

### Check Server Status
```powershell
curl http://localhost:5000/health
```

### View Latest Data
```powershell
curl http://localhost:5000/api/v1/dashboard/summary
```

### Browser Console
Press **F12** in your browser to see real-time connection logs:
- Connection status
- Data received
- Any errors

## ⚙️ Configuration

### Change Update Interval
Edit `send_sample_data.py` continuous mode:
```powershell
# Every 3 seconds
python send_sample_data.py --continuous 3

# Every 10 seconds, send 20 updates
python send_sample_data.py --continuous 10 20
```

### Customize Temperature Thresholds
Edit [app.py](app.py#L24-L28):
```python
TEMP_WARNING_THRESHOLD = 7.0      # °C
TEMP_CRITICAL_THRESHOLD = 10.0    # °C
BATTERY_LOW_THRESHOLD = 20        # %
BATTERY_CRITICAL_THRESHOLD = 10   # %
```

## 🐛 Troubleshooting

### Dashboard not updating?
1. Check if server is running: `http://localhost:5000/health`
2. Look at browser console (F12) for errors
3. Try sending test data: `python send_sample_data.py`

### "Connection refused" error?
- Ensure Flask server is running
- Check the port (default is 5000)
- Verify firewall isn't blocking connections

### Database error?
```powershell
# Delete and recreate database
rm instance\vecna.db
python app.py
```

### No real-time updates?
- Check browser console for SSE connection
- Some corporate networks block SSE
- Fallback polling should still work (10 second interval)

## 📁 Project Structure

```
VECNA/
├── app.py                          # Flask backend with SSE
├── requirements.txt                # Python dependencies
├── send_sample_data.py            # Test data generator
├── templates/
│   └── dashboard.html             # Real-time dashboard UI
├── instance/
│   └── vecna.db                   # SQLite database
├── QUICKSTART.md                  # This file
└── REALTIME_UPDATES.md           # Detailed SSE documentation
```

## 📚 Next Steps

1. ✅ Get the dashboard running
2. ✅ Send test data and watch real-time updates
3. 🔜 Configure your ESP32 hardware
4. 🔜 Connect actual temperature sensor
5. 🔜 Set up SMS/email alerts
6. 🔜 Deploy to production server

## 💡 Tips

- Keep the continuous test running while developing
- Open multiple browser tabs to test multi-client SSE
- Check the [REALTIME_UPDATES.md](REALTIME_UPDATES.md) for advanced features
- Monitor the Flask server console for incoming requests

## 🎯 Ready for Production?

See [HARDWARE_INTEGRATION_MANUAL.md](HARDWARE_INTEGRATION_MANUAL.md) for:
- ESP32 configuration
- Hardware setup
- Production deployment
- Security best practices

---

**Need Help?** Check the browser console (F12) and server logs for detailed error messages.
