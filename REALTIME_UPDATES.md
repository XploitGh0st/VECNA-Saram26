# VECNA Real-Time Dashboard Updates

## Overview
The VECNA dashboard now features **real-time updates** using Server-Sent Events (SSE). The dashboard automatically updates as new telemetry data arrives from your chicken package container sensor.

## Key Features

### 🔄 Automatic Updates
- Dashboard updates instantly when new sensor data arrives
- No need to refresh the page manually
- Live temperature, battery, and location tracking

### 📦 Single Device Monitoring
The system is configured to monitor **one device**:
- **Device ID**: `CHICKEN-PKG-001`
- **Product Type**: Chicken Package
- **Purpose**: Monitor temperature and conditions of chicken container during transport

### 🌡️ Temperature Monitoring
- **Normal Range**: 0-6.9°C (Green status)
- **Warning Zone**: 7.0-9.9°C (Yellow status with pulsing alert)
- **Critical Zone**: ≥10°C (Red status with urgent alert)

## How It Works

### Backend (Flask)
1. When telemetry data is received via `/api/v1/telemetry`
2. Data is stored in the database
3. All connected dashboard clients are notified via SSE
4. Dashboard updates instantly without polling

### Frontend (Dashboard)
1. Connects to `/api/v1/stream` on page load
2. Listens for real-time updates
3. Updates all UI components immediately:
   - Temperature readings
   - Location on map
   - Gateway health metrics
   - Alert notifications
   - Last update timestamp

### Connection Resilience
- Automatic reconnection if connection drops
- Fallback polling every 10 seconds as backup
- Keepalive messages to maintain connection

## Usage

### 1. Start the Server
```powershell
python app.py
```

### 2. Open Dashboard
Navigate to: http://localhost:5000

The dashboard will show:
- Real-time connection status
- Live map with vehicle location
- Chicken package sensor data
- Gateway health vitals
- Active alerts

### 3. Send Test Data

**Single Test:**
```powershell
python send_sample_data.py
```

**Continuous Updates (every 5 seconds):**
```powershell
python send_sample_data.py --continuous 5
```

**Continuous with limit (10 updates, 5 second interval):**
```powershell
python send_sample_data.py --continuous 5 10
```

## Dashboard Components

### 📍 Live Map
- Shows real-time vehicle location
- Updates position as GPS data arrives
- Displays speed, heading, and satellite count

### 🥶 Chicken Package Card
- **Large temperature display** with color coding
- **Status indicator**: NOMINAL / WARNING / CRITICAL
- **Battery level** with icon
- **Signal strength** indicator
- **Pulsing animations** for warnings/critical alerts

### 📡 Gateway Vitals
- Battery voltage
- Signal strength
- CPU temperature
- System uptime
- GPS satellite count
- Current speed

### ⚠️ Active Alerts
- Temperature threshold violations
- Low battery warnings
- Weak signal notifications
- Real-time alert updates

## Temperature Scenarios

The test script simulates realistic scenarios:

### Normal Operation (80% of time)
```json
{
  "temp_c": 2.5,
  "status": "NOMINAL"
}
```

### Getting Warm (15% of time)
```json
{
  "temp_c": 6.2,
  "status": "WARNING"
}
```

### Critical Temperature (5% of time)
```json
{
  "temp_c": 8.5,
  "status": "CRITICAL"
}
```

## Monitoring Your Hardware

When you connect your actual ESP32 gateway with the chicken package sensor:

1. **Configure Gateway ID**: Keep as `TRUCK-402` or update in your hardware
2. **Trip ID**: Will be `TRIP-CHICKEN-{date}`
3. **Send data** to: `http://your-server:5000/api/v1/telemetry`

### Expected Payload Format
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

## Browser Console

The dashboard logs helpful messages:
- `🚀 VECNA Dashboard initializing...`
- `📡 Connecting to real-time stream...`
- `✓ Real-time connection established`
- `📊 Real-time update received`

Check browser console (F12) to monitor connection status.

## Troubleshooting

### Dashboard not updating?
1. Check browser console for connection errors
2. Verify Flask server is running
3. Test with: `python send_sample_data.py`

### Connection keeps dropping?
- Check firewall settings
- Ensure server is accessible
- Look for proxy/network issues

### Data not appearing?
- Verify JSON payload format
- Check Flask server logs
- Ensure database is initialized

## Production Deployment

For production use:
1. Set proper `SECRET_KEY` environment variable
2. Use production database (PostgreSQL)
3. Deploy with proper WSGI server (gunicorn)
4. Configure HTTPS for secure SSE connections
5. Set up proper CORS if frontend is on different domain

## Next Steps

1. ✅ Real-time updates working
2. ✅ Single chicken package sensor
3. 🔜 Connect actual ESP32 hardware
4. 🔜 Add historical temperature graphs
5. 🔜 SMS/Email alert notifications
6. 🔜 Export temperature logs for compliance
