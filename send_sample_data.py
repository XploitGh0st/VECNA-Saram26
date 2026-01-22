"""
VECNA - Sample Data Sender
Sends sample telemetry data to the VECNA API for testing.
"""

import requests
from datetime import datetime, timezone
import random
import time

# API Configuration
API_URL = "http://127.0.0.1:5000/api/v1/telemetry"

def generate_sample_payload():
    """Generate a realistic sample telemetry payload for a chicken package container."""
    
    # Simulate slight GPS movement
    base_lat = 13.0827 + random.uniform(-0.01, 0.01)
    base_lng = 80.2707 + random.uniform(-0.01, 0.01)
    
    # Simulate realistic chicken storage temperatures (0-4°C is ideal)
    # Occasionally go above to simulate potential issues
    temp_variation = random.choice([
        round(random.uniform(2, 4), 1),    # Normal (80% probability)
        round(random.uniform(2, 4), 1),    
        round(random.uniform(2, 4), 1),    
        round(random.uniform(2, 4), 1),    
        round(random.uniform(5, 7), 1),    # Getting warm (15%)
        round(random.uniform(7.5, 9), 1)   # Warning zone (5%)
    ])
    
    payload = {
        "gateway_id": "TRUCK-402",
        "trip_id": f"TRIP-CHICKEN-{datetime.now().strftime('%Y%m%d')}",
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        
        "location": {
            "lat": round(base_lat, 6),
            "lng": round(base_lng, 6),
            "speed_kmh": round(random.uniform(40, 80), 1),
            "heading_deg": random.randint(0, 359),
            "satellites": random.randint(6, 12)
        },
        
        "gateway_health": {
            "battery_mv": random.randint(3600, 4200),
            "signal_strength_dbm": random.randint(-80, -50),
            "uptime_seconds": random.randint(1000, 50000),
            "cpu_temp_c": round(random.uniform(35, 55), 1)
        },
        
        "cargo_sensors": [
            {
                "node_id": "CHICKEN-PKG-001",
                "product_type": "Chicken Package",
                "temp_c": temp_variation,
                "battery_pct": random.randint(70, 100),
                "link_quality": random.randint(-75, -60)
            }
        ]
    }
    
    return payload


def send_telemetry(payload):
    """Send telemetry data to the API."""
    try:
        response = requests.post(
            API_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        return response.json(), response.status_code
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to server. Is the Flask app running?"}, 0
    except Exception as e:
        return {"error": str(e)}, 0


def main():
    """Main function to send sample data."""
    print("=" * 60)
    print("  VECNA - Sample Data Sender")
    print("=" * 60)
    print(f"\n  Target API: {API_URL}\n")
    
    # Generate and display payload
    payload = generate_sample_payload()
    
    print("  Generated Payload:")
    print(f"    Gateway ID: {payload['gateway_id']}")
    print(f"    Trip ID: {payload['trip_id']}")
    print(f"    Timestamp: {payload['timestamp']}")
    print(f"    Location: ({payload['location']['lat']}, {payload['location']['lng']})")
    print(f"    Speed: {payload['location']['speed_kmh']} km/h")
    print(f"    Sensors: {len(payload['cargo_sensors'])} cargo boxes")
    
    print("  Sensor Readings:")
    for sensor in payload['cargo_sensors']:
        temp = sensor['temp_c']
        if temp >= 10:
            status = "CRITICAL"
        elif temp >= 7:
            status = "WARNING"
        else:
            status = "OK"
        print(f"    - {sensor['node_id']} ({sensor['product_type']}): "
              f"{temp}°C, Battery: {sensor['battery_pct']}% [{status}]")
    
    # Send the data
    print("\n  Sending telemetry data...")
    result, status_code = send_telemetry(payload)
    
    if status_code == 201:
        print(f"\n  ✓ Success! Status: {status_code}")
        print(f"    Frame ID: {result.get('data', {}).get('frame_id')}")
        print(f"    Sensors Processed: {result.get('data', {}).get('sensors_processed')}")
        print(f"    Alerts Generated: {result.get('data', {}).get('alerts_generated')}")
    elif status_code == 0:
        print(f"\n  ✗ Connection Error: {result.get('error')}")
    else:
        print(f"\n  ✗ Failed! Status: {status_code}")
        print(f"    Error: {result.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 60)


def continuous_mode(interval_seconds=10, count=None):
    """Send data continuously at specified intervals."""
    print("=" * 60)
    print("  VECNA - Continuous Data Sender")
    print(f"  Interval: {interval_seconds} seconds")
    print(f"  Count: {'Unlimited' if count is None else count}")
    print("  Press Ctrl+C to stop")
    print("=" * 60 + "\n")
    
    sent = 0
    try:
        while count is None or sent < count:
            payload = generate_sample_payload()
            result, status_code = send_telemetry(payload)
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            if status_code == 201:
                alerts = result.get('data', {}).get('alerts_generated', 0)
                print(f"[{timestamp}] ✓ Frame sent - Alerts: {alerts}")
            else:
                print(f"[{timestamp}] ✗ Failed - {result.get('error', 'Unknown')}")
            
            sent += 1
            if count is None or sent < count:
                time.sleep(interval_seconds)
                
    except KeyboardInterrupt:
        print(f"\n\nStopped. Total frames sent: {sent}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--continuous":
        # Continuous mode: python send_sample_data.py --continuous [interval] [count]
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        count = int(sys.argv[3]) if len(sys.argv) > 3 else None
        continuous_mode(interval, count)
    else:
        # Single send mode
        main()
