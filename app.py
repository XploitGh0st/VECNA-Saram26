"""
VECNA - Verified Expiry & Cold-chain Navigation Assistant
Flask Backend Server with SQLAlchemy ORM

A robust IoT telemetry ingestion system for refrigerated truck monitoring.
"""

from flask import Flask, request, jsonify, render_template, Response, stream_with_context
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from typing import Optional
import os
import json
import queue
import threading

# ============================================================================
# APPLICATION CONFIGURATION
# ============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'vecna-dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///vecna.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False  # Set True for SQL debugging

db = SQLAlchemy(app)

# SSE notification queue for real-time updates
sse_clients = []  # List of SSE clients
sse_lock = threading.Lock()  # Thread-safe access

# ============================================================================
# THRESHOLD CONSTANTS
# ============================================================================

TEMP_WARNING_THRESHOLD = 7.0      # °C - Above this triggers temperature alert
TEMP_CRITICAL_THRESHOLD = 10.0   # °C - Critical spoilage risk
BATTERY_LOW_THRESHOLD = 20       # % - Below this triggers low battery alert
BATTERY_CRITICAL_THRESHOLD = 10  # % - Critical battery level
SIGNAL_WEAK_THRESHOLD = -85      # dBm - Weak signal strength


# ============================================================================
# DATABASE MODELS - NORMALIZED SCHEMA
# ============================================================================

class Truck(db.Model):
    """
    Static information about registered trucks in the fleet.
    Each truck can have multiple trips over its lifetime.
    """
    __tablename__ = 'trucks'
    
    id = db.Column(db.Integer, primary_key=True)
    gateway_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    plate_number = db.Column(db.String(20), nullable=True)
    driver_name = db.Column(db.String(100), nullable=True)
    truck_model = db.Column(db.String(100), nullable=True)
    refrigeration_unit = db.Column(db.String(100), nullable=True)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    trips = db.relationship('Trip', backref='truck', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'gateway_id': self.gateway_id,
            'plate_number': self.plate_number,
            'driver_name': self.driver_name,
            'truck_model': self.truck_model,
            'refrigeration_unit': self.refrigeration_unit,
            'registered_at': self.registered_at.isoformat() if self.registered_at else None,
            'is_active': self.is_active
        }


class Trip(db.Model):
    """
    Represents a journey/delivery run.
    Links telemetry data to a specific trip for analytics.
    """
    __tablename__ = 'trips'
    
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    truck_id = db.Column(db.Integer, db.ForeignKey('trucks.id'), nullable=False)
    
    # Trip metadata
    origin = db.Column(db.String(100), nullable=True)
    destination = db.Column(db.String(100), nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='ACTIVE')  # ACTIVE, COMPLETED, CANCELLED
    
    # Computed stats (updated on ingestion)
    total_frames = db.Column(db.Integer, default=0)
    alert_count = db.Column(db.Integer, default=0)
    
    # Relationships
    telemetry_frames = db.relationship('TelemetryFrame', backref='trip', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'trip_id': self.trip_id,
            'truck_id': self.truck_id,
            'origin': self.origin,
            'destination': self.destination,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'status': self.status,
            'total_frames': self.total_frames,
            'alert_count': self.alert_count
        }


class TelemetryFrame(db.Model):
    """
    A single telemetry snapshot from the gateway.
    Contains location data and gateway health metrics.
    """
    __tablename__ = 'telemetry_frames'
    
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trips.id'), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    received_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Location Data
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    speed_kmh = db.Column(db.Float, nullable=True)
    heading_deg = db.Column(db.Float, nullable=True)
    satellites = db.Column(db.Integer, nullable=True)
    
    # Gateway Health Metrics
    battery_mv = db.Column(db.Integer, nullable=True)
    signal_strength_dbm = db.Column(db.Integer, nullable=True)
    uptime_seconds = db.Column(db.Integer, nullable=True)
    cpu_temp_c = db.Column(db.Float, nullable=True)
    
    # Frame status
    has_alerts = db.Column(db.Boolean, default=False)
    
    # Relationships
    sensor_readings = db.relationship('SensorReading', backref='frame', lazy='dynamic')
    alerts = db.relationship('SystemAlert', backref='frame', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'trip_id': self.trip_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'received_at': self.received_at.isoformat() if self.received_at else None,
            'location': {
                'lat': self.latitude,
                'lng': self.longitude,
                'speed_kmh': self.speed_kmh,
                'heading_deg': self.heading_deg,
                'satellites': self.satellites
            },
            'gateway_health': {
                'battery_mv': self.battery_mv,
                'signal_strength_dbm': self.signal_strength_dbm,
                'uptime_seconds': self.uptime_seconds,
                'cpu_temp_c': self.cpu_temp_c
            },
            'has_alerts': self.has_alerts,
            'sensor_count': self.sensor_readings.count()
        }


class SensorReading(db.Model):
    """
    Individual cargo box sensor reading.
    Linked to a TelemetryFrame for time-series tracking.
    """
    __tablename__ = 'sensor_readings'
    
    id = db.Column(db.Integer, primary_key=True)
    frame_id = db.Column(db.Integer, db.ForeignKey('telemetry_frames.id'), nullable=False, index=True)
    
    # Sensor identification
    node_id = db.Column(db.String(50), nullable=False, index=True)
    product_type = db.Column(db.String(50), nullable=True)
    
    # Sensor data
    temp_c = db.Column(db.Float, nullable=False)
    battery_pct = db.Column(db.Integer, nullable=True)
    link_quality = db.Column(db.Integer, nullable=True)  # BLE RSSI in dBm
    
    # Computed status
    status = db.Column(db.String(20), default='NOMINAL')  # NOMINAL, WARNING, CRITICAL
    temp_alert = db.Column(db.Boolean, default=False)
    battery_alert = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'frame_id': self.frame_id,
            'node_id': self.node_id,
            'product_type': self.product_type,
            'temp_c': self.temp_c,
            'battery_pct': self.battery_pct,
            'link_quality': self.link_quality,
            'status': self.status,
            'temp_alert': self.temp_alert,
            'battery_alert': self.battery_alert
        }


class SystemAlert(db.Model):
    """
    System-generated alerts for anomalies.
    Supports multiple alert types with severity levels.
    """
    __tablename__ = 'system_alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    frame_id = db.Column(db.Integer, db.ForeignKey('telemetry_frames.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Alert details
    alert_type = db.Column(db.String(30), nullable=False)  # TEMP_HIGH, BATTERY_LOW, SIGNAL_WEAK, etc.
    severity = db.Column(db.String(20), default='WARNING')  # INFO, WARNING, CRITICAL
    node_id = db.Column(db.String(50), nullable=True)  # Which sensor triggered it (if applicable)
    message = db.Column(db.String(255), nullable=False)
    value = db.Column(db.Float, nullable=True)  # The triggering value
    threshold = db.Column(db.Float, nullable=True)  # The threshold that was exceeded
    
    # Resolution tracking
    is_resolved = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'frame_id': self.frame_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'alert_type': self.alert_type,
            'severity': self.severity,
            'node_id': self.node_id,
            'message': self.message,
            'value': self.value,
            'threshold': self.threshold,
            'is_resolved': self.is_resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def parse_iso_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse ISO 8601 timestamp string to datetime object."""
    if not timestamp_str:
        return None
    try:
        # Handle 'Z' suffix for UTC
        if timestamp_str.endswith('Z'):
            timestamp_str = timestamp_str[:-1] + '+00:00'
        return datetime.fromisoformat(timestamp_str)
    except ValueError:
        return None


def get_or_create_truck(gateway_id: str) -> Truck:
    """Get existing truck or create a new one."""
    truck = Truck.query.filter_by(gateway_id=gateway_id).first()
    if not truck:
        truck = Truck(gateway_id=gateway_id)
        db.session.add(truck)
        db.session.flush()  # Get the ID without committing
    return truck


def get_or_create_trip(trip_id: str, truck: Truck) -> Trip:
    """Get existing trip or create a new one."""
    trip = Trip.query.filter_by(trip_id=trip_id).first()
    if not trip:
        trip = Trip(
            trip_id=trip_id,
            truck_id=truck.id,
            started_at=datetime.utcnow(),
            status='ACTIVE'
        )
        db.session.add(trip)
        db.session.flush()
    return trip


def compute_sensor_status(temp_c: float, battery_pct: int) -> str:
    """Compute the overall status of a sensor based on readings."""
    if temp_c >= TEMP_CRITICAL_THRESHOLD or (battery_pct is not None and battery_pct < BATTERY_CRITICAL_THRESHOLD):
        return 'CRITICAL'
    elif temp_c >= TEMP_WARNING_THRESHOLD or (battery_pct is not None and battery_pct < BATTERY_LOW_THRESHOLD):
        return 'WARNING'
    return 'NOMINAL'


def create_alerts_for_reading(frame: TelemetryFrame, reading: SensorReading) -> list:
    """Generate alerts for a sensor reading if thresholds are exceeded."""
    alerts = []
    
    # Temperature Alert
    if reading.temp_c >= TEMP_WARNING_THRESHOLD:
        severity = 'CRITICAL' if reading.temp_c >= TEMP_CRITICAL_THRESHOLD else 'WARNING'
        alert = SystemAlert(
            frame_id=frame.id,
            alert_type='TEMP_HIGH',
            severity=severity,
            node_id=reading.node_id,
            message=f"Temperature {reading.temp_c}°C exceeds threshold for {reading.product_type or 'cargo'}",
            value=reading.temp_c,
            threshold=TEMP_WARNING_THRESHOLD
        )
        alerts.append(alert)
        reading.temp_alert = True
    
    # Battery Alert
    if reading.battery_pct is not None and reading.battery_pct < BATTERY_LOW_THRESHOLD:
        severity = 'CRITICAL' if reading.battery_pct < BATTERY_CRITICAL_THRESHOLD else 'WARNING'
        alert = SystemAlert(
            frame_id=frame.id,
            alert_type='BATTERY_LOW',
            severity=severity,
            node_id=reading.node_id,
            message=f"Sensor {reading.node_id} battery at {reading.battery_pct}%",
            value=reading.battery_pct,
            threshold=BATTERY_LOW_THRESHOLD
        )
        alerts.append(alert)
        reading.battery_alert = True
    
    # Signal Quality Alert
    if reading.link_quality is not None and reading.link_quality < SIGNAL_WEAK_THRESHOLD:
        alert = SystemAlert(
            frame_id=frame.id,
            alert_type='SIGNAL_WEAK',
            severity='INFO',
            node_id=reading.node_id,
            message=f"Sensor {reading.node_id} has weak BLE signal ({reading.link_quality} dBm)",
            value=reading.link_quality,
            threshold=SIGNAL_WEAK_THRESHOLD
        )
        alerts.append(alert)
    
    return alerts


def notify_sse_clients(data):
    """Send data to all connected SSE clients."""
    with sse_lock:
        # Remove disconnected clients
        disconnected = []
        for i, client_queue in enumerate(sse_clients):
            try:
                client_queue.put_nowait(data)
            except queue.Full:
                disconnected.append(i)
        
        # Remove disconnected clients
        for i in reversed(disconnected):
            sse_clients.pop(i)


# ============================================================================
# API ROUTES - TELEMETRY INGESTION
# ============================================================================

@app.route('/api/v1/telemetry', methods=['POST'])
def ingest_telemetry():
    """
    Primary telemetry ingestion endpoint.
    Accepts comprehensive JSON payload from ESP32 Gateway.
    
    Returns:
        201: Successfully ingested
        400: Invalid payload
        500: Server error
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON payload received'
            }), 400
        
        # Validate required fields
        required_fields = ['gateway_id', 'trip_id', 'timestamp']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing)}'
            }), 400
        
        # Parse timestamp
        timestamp = parse_iso_timestamp(data['timestamp'])
        if not timestamp:
            return jsonify({
                'success': False,
                'error': 'Invalid timestamp format. Use ISO 8601 (e.g., 2026-01-16T14:30:00Z)'
            }), 400
        
        # Get or create truck and trip
        truck = get_or_create_truck(data['gateway_id'])
        trip = get_or_create_trip(data['trip_id'], truck)
        
        # Extract location data
        location = data.get('location', {})
        gateway_health = data.get('gateway_health', {})
        
        # Create telemetry frame
        frame = TelemetryFrame(
            trip_id=trip.id,
            timestamp=timestamp,
            # Location
            latitude=location.get('lat'),
            longitude=location.get('lng'),
            speed_kmh=location.get('speed_kmh'),
            heading_deg=location.get('heading_deg'),
            satellites=location.get('satellites'),
            # Gateway health
            battery_mv=gateway_health.get('battery_mv'),
            signal_strength_dbm=gateway_health.get('signal_strength_dbm'),
            uptime_seconds=gateway_health.get('uptime_seconds'),
            cpu_temp_c=gateway_health.get('cpu_temp_c')
        )
        db.session.add(frame)
        db.session.flush()  # Get frame ID
        
        # Process cargo sensors
        all_alerts = []
        cargo_sensors = data.get('cargo_sensors', [])
        
        for sensor_data in cargo_sensors:
            # Validate required sensor fields
            if 'node_id' not in sensor_data or 'temp_c' not in sensor_data:
                continue
            
            battery_pct = sensor_data.get('battery_pct')
            
            # Create sensor reading
            reading = SensorReading(
                frame_id=frame.id,
                node_id=sensor_data['node_id'],
                product_type=sensor_data.get('product_type'),
                temp_c=sensor_data['temp_c'],
                battery_pct=battery_pct,
                link_quality=sensor_data.get('link_quality'),
                status=compute_sensor_status(sensor_data['temp_c'], battery_pct or 100)
            )
            db.session.add(reading)
            
            # Generate alerts
            alerts = create_alerts_for_reading(frame, reading)
            all_alerts.extend(alerts)
        
        # Add all alerts to session
        for alert in all_alerts:
            db.session.add(alert)
        
        # Update frame and trip stats
        if all_alerts:
            frame.has_alerts = True
            trip.alert_count += len(all_alerts)
        
        trip.total_frames += 1
        
        # Commit all changes
        db.session.commit()
        
        # Notify SSE clients with new data
        sse_data = {
            'frame': frame.to_dict(),
            'sensors': [SensorReading.query.get(r.id).to_dict() for r in db.session.query(SensorReading).filter_by(frame_id=frame.id).all()],
            'alerts': [a.to_dict() for a in all_alerts],
            'truck': truck.to_dict(),
            'trip': trip.to_dict()
        }
        notify_sse_clients(sse_data)
        
        return jsonify({
            'success': True,
            'message': 'Telemetry ingested successfully',
            'data': {
                'frame_id': frame.id,
                'trip_id': trip.trip_id,
                'sensors_processed': len(cargo_sensors),
                'alerts_generated': len(all_alerts)
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Telemetry ingestion error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500


# ============================================================================
# API ROUTES - DATA RETRIEVAL
# ============================================================================

@app.route('/api/v1/trucks', methods=['GET'])
def get_trucks():
    """Get all registered trucks."""
    trucks = Truck.query.filter_by(is_active=True).all()
    return jsonify({
        'success': True,
        'data': [t.to_dict() for t in trucks]
    })


@app.route('/api/v1/trips', methods=['GET'])
def get_trips():
    """Get all trips, optionally filtered by status."""
    status = request.args.get('status', 'ACTIVE')
    trips = Trip.query.filter_by(status=status).order_by(Trip.started_at.desc()).all()
    return jsonify({
        'success': True,
        'data': [t.to_dict() for t in trips]
    })


@app.route('/api/v1/trips/<trip_id>/latest', methods=['GET'])
def get_latest_telemetry(trip_id):
    """Get the most recent telemetry frame for a trip."""
    trip = Trip.query.filter_by(trip_id=trip_id).first()
    if not trip:
        return jsonify({'success': False, 'error': 'Trip not found'}), 404
    
    frame = TelemetryFrame.query.filter_by(trip_id=trip.id)\
        .order_by(TelemetryFrame.timestamp.desc()).first()
    
    if not frame:
        return jsonify({'success': False, 'error': 'No telemetry data'}), 404
    
    # Get sensor readings for this frame
    readings = SensorReading.query.filter_by(frame_id=frame.id).all()
    
    return jsonify({
        'success': True,
        'data': {
            'frame': frame.to_dict(),
            'sensors': [r.to_dict() for r in readings],
            'truck': trip.truck.to_dict()
        }
    })


@app.route('/api/v1/dashboard/summary', methods=['GET'])
def get_dashboard_summary():
    """
    Get comprehensive dashboard data.
    Returns latest position, sensors, and alerts for all active trips.
    """
    active_trips = Trip.query.filter_by(status='ACTIVE').all()
    
    dashboard_data = []
    
    for trip in active_trips:
        # Get latest frame
        frame = TelemetryFrame.query.filter_by(trip_id=trip.id)\
            .order_by(TelemetryFrame.timestamp.desc()).first()
        
        if not frame:
            continue
        
        # Get sensor readings
        readings = SensorReading.query.filter_by(frame_id=frame.id).all()
        
        # Get recent alerts (last 24 hours)
        recent_alerts = SystemAlert.query.filter_by(frame_id=frame.id)\
            .filter_by(is_resolved=False).all()
        
        dashboard_data.append({
            'trip': trip.to_dict(),
            'truck': trip.truck.to_dict(),
            'location': {
                'lat': frame.latitude,
                'lng': frame.longitude,
                'speed_kmh': frame.speed_kmh,
                'heading_deg': frame.heading_deg,
                'satellites': frame.satellites
            },
            'gateway_health': {
                'battery_mv': frame.battery_mv,
                'signal_strength_dbm': frame.signal_strength_dbm,
                'uptime_seconds': frame.uptime_seconds,
                'cpu_temp_c': frame.cpu_temp_c
            },
            'timestamp': frame.timestamp.isoformat() if frame.timestamp else None,
            'sensors': [r.to_dict() for r in readings],
            'alerts': [a.to_dict() for a in recent_alerts]
        })
    
    return jsonify({
        'success': True,
        'data': dashboard_data,
        'timestamp': datetime.utcnow().isoformat()
    })


@app.route('/api/v1/alerts', methods=['GET'])
def get_alerts():
    """Get all unresolved alerts."""
    alerts = SystemAlert.query.filter_by(is_resolved=False)\
        .order_by(SystemAlert.created_at.desc()).limit(100).all()
    return jsonify({
        'success': True,
        'data': [a.to_dict() for a in alerts]
    })


@app.route('/api/v1/alerts/<int:alert_id>/resolve', methods=['POST'])
def resolve_alert(alert_id):
    """Mark an alert as resolved."""
    alert = SystemAlert.query.get(alert_id)
    if not alert:
        return jsonify({'success': False, 'error': 'Alert not found'}), 404
    
    alert.is_resolved = True
    alert.resolved_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Alert resolved'
    })


# ============================================================================
# SSE ROUTES - REAL-TIME UPDATES
# ============================================================================

@app.route('/api/v1/stream')
def stream():
    """Server-Sent Events endpoint for real-time updates."""
    def event_stream():
        # Create a queue for this client
        client_queue = queue.Queue(maxsize=10)
        
        with sse_lock:
            sse_clients.append(client_queue)
        
        try:
            # Send initial connection message
            yield 'data: {"type": "connected"}\n\n'
            
            # Stream events to client
            while True:
                try:
                    # Wait for new data (with timeout to send keepalive)
                    data = client_queue.get(timeout=30)
                    yield f"data: {json.dumps(data)}\n\n"
                except queue.Empty:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
        except GeneratorExit:
            # Client disconnected
            with sse_lock:
                if client_queue in sse_clients:
                    sse_clients.remove(client_queue)
    
    return Response(
        stream_with_context(event_stream()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


# ============================================================================
# WEB ROUTES - DASHBOARD UI
# ============================================================================

@app.route('/')
def dashboard():
    """Render the main dashboard page."""
    return render_template('dashboard.html')


@app.route('/health')
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({
        'status': 'healthy',
        'service': 'VECNA Backend',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat()
    })


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_db():
    """Initialize the database and create tables."""
    with app.app_context():
        db.create_all()
        print("✓ Database initialized successfully")


def seed_demo_data():
    """Seed the database with demo data for testing."""
    with app.app_context():
        # Check if data exists
        if Truck.query.first():
            print("✓ Demo data already exists")
            return
        
        # Create demo truck
        truck = Truck(
            gateway_id='TRUCK-402',
            plate_number='TN-01-AB-1234',
            driver_name='Rajesh Kumar',
            truck_model='Tata 407 Reefer',
            refrigeration_unit='Carrier Transicold'
        )
        db.session.add(truck)
        db.session.flush()
        
        # Create demo trip
        trip = Trip(
            trip_id='TRIP-CHN-BLR-05',
            truck_id=truck.id,
            origin='Chennai',
            destination='Bangalore',
            started_at=datetime.utcnow(),
            status='ACTIVE'
        )
        db.session.add(trip)
        db.session.flush()
        
        # Create demo telemetry frame
        frame = TelemetryFrame(
            trip_id=trip.id,
            timestamp=datetime.utcnow(),
            latitude=13.0827,
            longitude=80.2707,
            speed_kmh=62.5,
            heading_deg=270,
            satellites=8,
            battery_mv=3800,
            signal_strength_dbm=-65,
            uptime_seconds=7200,
            cpu_temp_c=42.5,
            has_alerts=True
        )
        db.session.add(frame)
        db.session.flush()
        
        # Create demo sensor reading - Single chicken package container
        sensors = [
            {
                'node_id': 'CHICKEN-PKG-001',
                'product_type': 'Chicken Package',
                'temp_c': 3.5,
                'battery_pct': 85,
                'link_quality': -72,
                'status': 'NOMINAL'
            }
        ]
        
        for s in sensors:
            reading = SensorReading(
                frame_id=frame.id,
                node_id=s['node_id'],
                product_type=s['product_type'],
                temp_c=s['temp_c'],
                battery_pct=s['battery_pct'],
                link_quality=s['link_quality'],
                status=s['status'],
                temp_alert=s['temp_c'] >= TEMP_WARNING_THRESHOLD,
                battery_alert=s['battery_pct'] < BATTERY_LOW_THRESHOLD
            )
            db.session.add(reading)
            
            # Create alerts for issues
            if s['temp_c'] >= TEMP_WARNING_THRESHOLD:
                alert = SystemAlert(
                    frame_id=frame.id,
                    alert_type='TEMP_HIGH',
                    severity='WARNING',
                    node_id=s['node_id'],
                    message=f"Temperature {s['temp_c']}°C exceeds threshold for {s['product_type']}",
                    value=s['temp_c'],
                    threshold=TEMP_WARNING_THRESHOLD
                )
                db.session.add(alert)
            
            if s['battery_pct'] < BATTERY_LOW_THRESHOLD:
                alert = SystemAlert(
                    frame_id=frame.id,
                    alert_type='BATTERY_LOW',
                    severity='WARNING',
                    node_id=s['node_id'],
                    message=f"Sensor {s['node_id']} battery at {s['battery_pct']}%",
                    value=s['battery_pct'],
                    threshold=BATTERY_LOW_THRESHOLD
                )
                db.session.add(alert)
        
        trip.total_frames = 1
        trip.alert_count = 0
        
        db.session.commit()
        print("✓ Demo data seeded successfully")


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    init_db()
    seed_demo_data()
    
    print("\n" + "="*60)
    print("  VECNA - Cold Chain Monitoring System")
    print("  Starting Flask Development Server...")
    print("="*60)
    print("\n  Dashboard: http://localhost:5000")
    print("  API Endpoint: http://localhost:5000/api/v1/telemetry")
    print("  Health Check: http://localhost:5000/health")
    print("\n" + "="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
