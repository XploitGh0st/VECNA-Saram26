"""
VECNA Spoilage Detector - Camera-based Detection System
Uses camera to detect QR codes and analyze spoilage indicator color on VECNA labels.
"""

import cv2
import numpy as np
import json
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional, Tuple, List
import time
import base64
import io
from flask import Flask, render_template, request, jsonify, Response

# ArUco dictionary (must match label generator)
ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_250)
ARUCO_PARAMS = cv2.aruco.DetectorParameters()

# OpenCV QR Code detector (no external dependencies)
QR_DETECTOR = cv2.QRCodeDetector()

app = Flask(__name__)


class SpoilageLevel(Enum):
    """Spoilage level classification."""
    FRESH = "FRESH"
    SLIGHT = "SLIGHT"
    MODERATE = "MODERATE"
    SPOILED = "SPOILED"
    UNKNOWN = "UNKNOWN"


@dataclass
class DetectionResult:
    """Result of spoilage detection."""
    package_id: str
    product_type: str
    batch_id: str
    pack_date: str
    aruco_id: int
    spoilage_level: SpoilageLevel
    spoilage_percentage: float
    confidence: float
    timestamp: str
    color_readings: dict
    is_safe: bool
    recommendation: str


class VECNASpoilageDetector:
    """
    Camera-based spoilage detection for VECNA labels.
    Analyzes the color of the spoilage indicator to determine freshness.
    """
    
    # Color ranges for spoilage detection (in HSV)
    # Fresh: White/Light gray shades ONLY
    # Any saturation < 40 and value > 180 is considered white/fresh
    FRESH_HSV_LOWER = np.array([0, 0, 180])
    FRESH_HSV_UPPER = np.array([180, 40, 255])
    
    # Spoiled: ANY color that is not white (has saturation or is dark)
    # This will be calculated as anything NOT matching fresh
    
    def __init__(self, camera_id: int = 0, debug: bool = False):
        """Initialize the detector with camera settings."""
        self.camera_id = camera_id
        self.debug = debug
        self.cap = None
        self.last_detection = None
        
    def start_camera(self) -> bool:
        """Initialize and start the camera."""
        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            print("Error: Could not open camera")
            return False
        
        # Set camera properties for better quality
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        return True
    
    def stop_camera(self):
        """Release the camera."""
        if self.cap:
            self.cap.release()
            cv2.destroyAllWindows()
    
    def decode_qr_codes(self, frame: np.ndarray) -> List[dict]:
        """Decode QR codes in the frame using OpenCV's built-in detector."""
        results = []
        
        # Try with original frame first
        images_to_try = [frame]
        
        # Add preprocessed versions
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_3ch = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        images_to_try.append(gray_3ch)
        
        # Histogram equalized
        eq = cv2.equalizeHist(gray)
        eq_3ch = cv2.cvtColor(eq, cv2.COLOR_GRAY2BGR)
        images_to_try.append(eq_3ch)
        
        # Sharpened
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(frame, -1, kernel)
        images_to_try.append(sharpened)
        
        for img in images_to_try:
            try:
                data, points, _ = QR_DETECTOR.detectAndDecode(img)
                
                if data and points is not None:
                    try:
                        parsed_data = json.loads(data)
                        pts = points[0].astype(np.int32)
                        results.append({
                            'data': parsed_data,
                            'polygon': pts,
                            'rect': cv2.boundingRect(pts)
                        })
                        return results  # Found QR, return immediately
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
            except Exception:
                pass
        
        return results
    
    def detect_aruco_markers(self, frame: np.ndarray) -> List[dict]:
        """Detect ArUco markers in the frame with enhanced preprocessing."""
        results = []
        
        # Get grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Create multiple detector parameter sets to try
        param_sets = []
        
        # Parameter set 1: Default with relaxed thresholds
        params1 = cv2.aruco.DetectorParameters()
        params1.adaptiveThreshWinSizeMin = 3
        params1.adaptiveThreshWinSizeMax = 23
        params1.adaptiveThreshWinSizeStep = 5
        params1.adaptiveThreshConstant = 7
        params1.minMarkerPerimeterRate = 0.005  # Very small markers allowed
        params1.maxMarkerPerimeterRate = 4.0
        params1.polygonalApproxAccuracyRate = 0.08
        params1.minCornerDistanceRate = 0.01
        params1.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        param_sets.append(params1)
        
        # Parameter set 2: For low contrast images
        params2 = cv2.aruco.DetectorParameters()
        params2.adaptiveThreshWinSizeMin = 5
        params2.adaptiveThreshWinSizeMax = 35
        params2.adaptiveThreshWinSizeStep = 5
        params2.adaptiveThreshConstant = 10
        params2.minMarkerPerimeterRate = 0.005
        params2.maxMarkerPerimeterRate = 4.0
        params2.polygonalApproxAccuracyRate = 0.1
        params2.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_CONTOUR
        param_sets.append(params2)
        
        # Image preprocessing variations
        images_to_try = []
        
        # Original grayscale
        images_to_try.append(gray)
        
        # Histogram equalized
        images_to_try.append(cv2.equalizeHist(gray))
        
        # CLAHE with different parameters
        clahe1 = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        images_to_try.append(clahe1.apply(gray))
        
        clahe2 = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
        images_to_try.append(clahe2.apply(gray))
        
        # Sharpen the image
        kernel_sharpen = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(gray, -1, kernel_sharpen)
        images_to_try.append(sharpened)
        
        # Binary threshold at different levels
        _, binary1 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        images_to_try.append(binary1)
        
        _, binary2 = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        images_to_try.append(binary2)
        
        # Adaptive threshold variations
        adaptive1 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY, 11, 2)
        images_to_try.append(adaptive1)
        
        adaptive2 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                          cv2.THRESH_BINARY, 15, 5)
        images_to_try.append(adaptive2)
        
        # Morphological operations to clean up
        kernel = np.ones((3, 3), np.uint8)
        morph = cv2.morphologyEx(binary1, cv2.MORPH_CLOSE, kernel)
        images_to_try.append(morph)
        
        # Try each parameter set with each image
        for params in param_sets:
            detector = cv2.aruco.ArucoDetector(ARUCO_DICT, params)
            
            for img in images_to_try:
                try:
                    corners, ids, rejected = detector.detectMarkers(img)
                    
                    if ids is not None and len(ids) > 0:
                        for i, marker_id in enumerate(ids):
                            marker_corners = corners[i][0].astype(np.int32)
                            x_min = int(np.min(marker_corners[:, 0]))
                            y_min = int(np.min(marker_corners[:, 1]))
                            x_max = int(np.max(marker_corners[:, 0]))
                            y_max = int(np.max(marker_corners[:, 1]))
                            
                            # Check if this marker ID is already detected
                            if not any(r['id'] == int(marker_id[0]) for r in results):
                                results.append({
                                    'id': int(marker_id[0]),
                                    'corners': marker_corners,
                                    'rect': (x_min, y_min, x_max - x_min, y_max - y_min)
                                })
                        
                        # Found markers, return early
                        if results:
                            return results
                except Exception:
                    continue
        
        return results
    
    def find_indicator_region_from_aruco(self, frame: np.ndarray, aruco_rect: Tuple[int, int, int, int]) -> Optional[Tuple[int, int, int, int]]:
        """
        Find the spoilage indicator strip based on ArUco marker position.
        
        Label layout (8cm x 4.5cm) - ArUco is at BOTTOM-LEFT, indicator is to the RIGHT:
        - ArUco marker: x+3mm from left, y+5mm from bottom, size 14mm
        - Indicator strip: x+20mm from left, y+8mm from bottom, size 45mm x 10mm
        
        In image coordinates (Y increases downward), the ArUco at "bottom" of label
        has a HIGH Y value. The indicator is at the SAME vertical level (slightly higher
        in image = slightly LOWER Y value because Y increases downward).
        
        We read the CENTER of the strip where the actual color change happens.
        """
        x, y, w, h = aruco_rect
        
        # Debug print
        print(f"  [DEBUG] ArUco rect: x={x}, y={y}, w={w}, h={h}")
        
        # The indicator strip is to the RIGHT of the ArUco marker
        # In label_generator.py:
        #   ArUco at x+3mm, indicator at x+20mm, so gap is 17mm - 14mm(aruco_size) = 3mm
        #   In terms of ArUco width: 3mm / 14mm ≈ 0.21
        gap = int(w * 0.2)
        
        # Strip width is approximately 3.2x the ArUco width (45mm / 14mm ≈ 3.2)
        strip_width = int(w * 3.2)
        
        # Strip height is about 70% of ArUco height (10mm / 14mm ≈ 0.7)
        strip_height = int(h * 0.7)
        
        # Indicator strip position:
        # - To the right of ArUco (add ArUco width + gap)
        # - Slightly ABOVE ArUco in image coords (y + 8mm vs y + 5mm in PDF = 3mm higher)
        #   In image coords (Y down), "higher on label" = lower Y value
        #   3mm / 14mm ≈ 0.21 of ArUco height, so subtract this from Y
        indicator_x = x + w + gap
        indicator_y = y - int(h * 0.2)  # Slightly ABOVE ArUco (lower Y in image)
        
        # Make sure Y doesn't go negative
        if indicator_y < 0:
            indicator_y = y
        
        print(f"  [DEBUG] Full indicator region: x={indicator_x}, y={indicator_y}, w={strip_width}, h={strip_height}")
        
        # Read the CENTER portion of the strip (from 25% to 75% width)
        # This is where fresh vs spoiled transition happens
        center_start = int(strip_width * 0.25)
        center_width = int(strip_width * 0.50)
        
        final_x = indicator_x + center_start
        final_y = indicator_y
        final_w = center_width
        final_h = strip_height
        
        print(f"  [DEBUG] Reading center region: x={final_x}, y={final_y}, w={final_w}, h={final_h}")
        
        # Ensure within frame bounds
        frame_h, frame_w = frame.shape[:2]
        if final_x + final_w > frame_w:
            final_w = frame_w - final_x - 5
        if final_y + final_h > frame_h:
            final_h = frame_h - final_y - 5
            
        if final_w > 0 and final_h > 0:
            return (final_x, final_y, final_w, final_h)
        return None
    
    def analyze_spoilage_indicator(self, frame: np.ndarray, region: Tuple[int, int, int, int]) -> Tuple[SpoilageLevel, float, dict]:
        """
        Analyze the color of the MIDDLE of the spoilage indicator region.
        Simple logic: WHITE shades = FRESH, ANY other color = SPOILED.
        Returns spoilage level, percentage, and color readings.
        """
        x, y, w, h = region
        indicator_roi = frame[y:y+h, x:x+w]
        
        if indicator_roi.size == 0:
            return SpoilageLevel.UNKNOWN, 0.0, {}
        
        # Convert to HSV for color analysis
        hsv = cv2.cvtColor(indicator_roi, cv2.COLOR_BGR2HSV)
        
        # Fresh mask: White/light gray shades only (low saturation, high value)
        fresh_mask = cv2.inRange(hsv, self.FRESH_HSV_LOWER, self.FRESH_HSV_UPPER)
        
        # Spoiled: Everything that is NOT white (inverse of fresh mask)
        spoiled_mask = cv2.bitwise_not(fresh_mask)
        
        # Calculate percentage of each
        total_pixels = indicator_roi.shape[0] * indicator_roi.shape[1]
        if total_pixels == 0:
            return SpoilageLevel.UNKNOWN, 0.0, {}
            
        fresh_pct = np.sum(fresh_mask > 0) / total_pixels * 100
        spoiled_pct = np.sum(spoiled_mask > 0) / total_pixels * 100
        
        # Get average color values for debugging/display
        avg_hsv = np.mean(hsv, axis=(0, 1))
        avg_bgr = np.mean(indicator_roi, axis=(0, 1))
        
        color_readings = {
            'fresh_percent': round(fresh_pct, 2),
            'spoiled_percent': round(spoiled_pct, 2),
            'avg_hue': round(avg_hsv[0], 2),
            'avg_saturation': round(avg_hsv[1], 2),
            'avg_value': round(avg_hsv[2], 2),
            'avg_bgr': [round(c, 2) for c in avg_bgr]
        }
        
        # Spoilage percentage is simply the non-white percentage
        spoilage_percentage = spoiled_pct
        
        # Determine spoilage level based on how much non-white color is detected
        # Simple threshold: >20% non-white = spoiled
        if spoilage_percentage < 10:
            level = SpoilageLevel.FRESH
        elif spoilage_percentage < 20:
            level = SpoilageLevel.SLIGHT
        elif spoilage_percentage < 40:
            level = SpoilageLevel.MODERATE
        else:
            level = SpoilageLevel.SPOILED
            
        return level, spoilage_percentage, color_readings
    
    def get_recommendation(self, level: SpoilageLevel) -> str:
        """Get safety recommendation based on spoilage level."""
        recommendations = {
            SpoilageLevel.FRESH: "✅ Product is fresh and safe for consumption.",
            SpoilageLevel.SLIGHT: "⚠️ Product shows slight changes. Use within 24 hours.",
            SpoilageLevel.MODERATE: "⚠️ Noticeable spoilage detected. Use immediately or discard.",
            SpoilageLevel.SPOILED: "❌ Product is spoiled. DO NOT CONSUME. Dispose safely.",
            SpoilageLevel.UNKNOWN: "❓ Unable to determine spoilage level. Inspect manually."
        }
        return recommendations.get(level, "Check product manually.")
    
    def detect_from_frame(self, frame: np.ndarray) -> Optional[DetectionResult]:
        """
        Process a single frame and detect spoilage.
        PRIMARY: Visual analysis of the indicator strip color (via ArUco positioning)
        SECONDARY: QR code for package info (ID, product, batch)
        
        The strip color is the GROUND TRUTH - it changes based on actual spoilage.
        """
        # Decode QR codes for package information
        qr_results = self.decode_qr_codes(frame)
        
        # Detect ArUco markers (REQUIRED for locating the indicator strip)
        aruco_results = self.detect_aruco_markers(frame)
        
        # Get QR data for package info (not for spoilage decision)
        qr_data = {}
        if qr_results:
            for qr in qr_results:
                if 'id' in qr['data']:
                    qr_data = qr['data']
                    break
        
        # We NEED ArUco marker to locate the indicator strip
        if not aruco_results:
            return None
        
        # Process ArUco marker to find spoilage indicator
        for aruco in aruco_results:
            aruco_id = aruco['id']
            
            # Find indicator region based on ArUco marker position
            region = self.find_indicator_region_from_aruco(frame, aruco['rect'])
            
            if region:
                # Analyze spoilage visually
                visual_level, percentage, colors = self.analyze_spoilage_indicator(frame, region)
                colors['qr_verified'] = False
                
                result = DetectionResult(
                    package_id=qr_data.get('id', f'ARUCO-{aruco_id}'),
                    product_type=qr_data.get('product', 'Chicken'),
                    batch_id=qr_data.get('batch', 'Unknown'),
                    pack_date=qr_data.get('packed', 'Unknown'),
                    aruco_id=aruco_id,
                    spoilage_level=visual_level,
                    spoilage_percentage=round(percentage, 2),
                    confidence=min(100, colors.get('fresh_percent', 0) + colors.get('spoiled_percent', 0)),
                    timestamp=datetime.now().isoformat(),
                    color_readings=colors,
                    is_safe=visual_level in [SpoilageLevel.FRESH, SpoilageLevel.SLIGHT],
                    recommendation=self.get_recommendation(visual_level)
                )
                
                self.last_detection = result
                return result
        
        return None
    
    def draw_detection_overlay(self, frame: np.ndarray, result: DetectionResult, aruco_corners: np.ndarray, indicator_region: Tuple[int, int, int, int], qr_polygon: np.ndarray = None) -> np.ndarray:
        """Draw detection results on the frame."""
        output = frame.copy()
        
        # Draw ArUco marker boundary (blue)
        cv2.polylines(output, [aruco_corners], True, (255, 0, 0), 3)
        cv2.putText(output, f"ArUco #{result.aruco_id}", 
                    (aruco_corners[0][0], aruco_corners[0][1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        
        # Draw QR code boundary if available (green)
        if qr_polygon is not None:
            cv2.polylines(output, [qr_polygon], True, (0, 255, 0), 2)
        
        # Draw indicator region
        x, y, w, h = indicator_region
        color = (0, 255, 0) if result.is_safe else (0, 0, 255)
        cv2.rectangle(output, (x, y), (x + w, y + h), color, 2)
        cv2.putText(output, "Indicator", (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Draw status panel
        panel_height = 200
        panel = np.zeros((panel_height, frame.shape[1], 3), dtype=np.uint8)
        panel[:] = (40, 40, 40)  # Dark gray background
        
        # Status color
        status_colors = {
            SpoilageLevel.FRESH: (0, 255, 0),      # Green
            SpoilageLevel.SLIGHT: (0, 255, 255),   # Yellow
            SpoilageLevel.MODERATE: (0, 165, 255), # Orange
            SpoilageLevel.SPOILED: (0, 0, 255),    # Red
            SpoilageLevel.UNKNOWN: (128, 128, 128) # Gray
        }
        status_color = status_colors.get(result.spoilage_level, (128, 128, 128))
        
        # Draw status indicator
        cv2.circle(panel, (50, 50), 30, status_color, -1)
        
        # Text information
        cv2.putText(panel, f"Package: {result.package_id}", (100, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(panel, f"Product: {result.product_type} | ArUco: {result.aruco_id}", (100, 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        cv2.putText(panel, f"Status: {result.spoilage_level.value}", (100, 90), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)
        cv2.putText(panel, f"Spoilage: {result.spoilage_percentage:.1f}%  |  Confidence: {result.confidence:.1f}%", (100, 120), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        
        # Recommendation
        rec_color = (0, 255, 0) if result.is_safe else (0, 0, 255)
        cv2.putText(panel, result.recommendation[:70], (20, 160), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, rec_color, 1)
        
        # Combine frame and panel
        output = np.vstack([output, panel])
        
        return output
    
    def run_detection_loop(self):
        """Main detection loop with camera feed."""
        if not self.start_camera():
            return
        
        print("\n" + "="*60)
        print("  VECNA Spoilage Detector - Camera Mode")
        print("="*60)
        print("\n  Instructions:")
        print("  - Point camera at VECNA label")
        print("  - Ensure ArUco marker and indicator bar are visible")
        print("  - QR code (bottom right) provides package details")
        print("  - Press 'Q' to quit")
        print("  - Press 'S' to save last detection")
        print("="*60 + "\n")
        
        detection_cooldown = 0
        last_result = None
        last_aruco = None
        last_region = None
        last_qr_polygon = None
        
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    print("Error: Could not read frame")
                    break
                
                display_frame = frame.copy()
                
                # Detect ArUco markers and QR codes
                aruco_results = self.detect_aruco_markers(frame)
                qr_results = self.decode_qr_codes(frame)
                
                if aruco_results and detection_cooldown == 0:
                    for aruco in aruco_results:
                        region = self.find_indicator_region_from_aruco(frame, aruco['rect'])
                        if region:
                            result = self.detect_from_frame(frame)
                            if result:
                                last_result = result
                                last_aruco = aruco
                                last_region = region
                                last_qr_polygon = qr_results[0]['polygon'] if qr_results else None
                                
                                display_frame = self.draw_detection_overlay(
                                    display_frame, result, aruco['corners'], region, last_qr_polygon
                                )
                                detection_cooldown = 30  # Skip frames to avoid flickering
                                
                                # Print to console
                                print(f"\n[{result.timestamp}] Detection:")
                                print(f"  Package: {result.package_id}")
                                print(f"  Product: {result.product_type}")
                                print(f"  ArUco ID: {result.aruco_id}")
                                print(f"  Status: {result.spoilage_level.value}")
                                print(f"  Spoilage: {result.spoilage_percentage}%")
                                print(f"  Safe: {'Yes' if result.is_safe else 'NO!'}")
                                break
                
                if detection_cooldown > 0:
                    detection_cooldown -= 1
                    if last_result and last_aruco and last_region:
                        # Keep showing last detection
                        # Update aruco position if still visible
                        current_aruco = None
                        for aruco in aruco_results:
                            if aruco['id'] == last_result.aruco_id:
                                current_aruco = aruco
                                break
                        
                        if current_aruco:
                            region = self.find_indicator_region_from_aruco(frame, current_aruco['rect'])
                            if region:
                                qr_poly = qr_results[0]['polygon'] if qr_results else None
                                display_frame = self.draw_detection_overlay(
                                    display_frame, last_result, current_aruco['corners'], region, qr_poly
                                )
                
                # Add instructions overlay
                cv2.putText(display_frame, "Point at VECNA label (ArUco + Indicator) | Q=Quit | S=Save", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                cv2.imshow('VECNA Spoilage Detector', display_frame)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('s') and last_result:
                    # Save detection result
                    filename = f"detection_{last_result.package_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    with open(filename, 'w') as f:
                        json.dump({
                            'package_id': last_result.package_id,
                            'product_type': last_result.product_type,
                            'batch_id': last_result.batch_id,
                            'pack_date': last_result.pack_date,
                            'aruco_id': last_result.aruco_id,
                            'spoilage_level': last_result.spoilage_level.value,
                            'spoilage_percentage': last_result.spoilage_percentage,
                            'confidence': last_result.confidence,
                            'timestamp': last_result.timestamp,
                            'color_readings': last_result.color_readings,
                            'is_safe': last_result.is_safe,
                            'recommendation': last_result.recommendation
                        }, f, indent=2)
                    print(f"\n✅ Detection saved to {filename}")
                    
        finally:
            self.stop_camera()


def detect_from_image(image_path: str) -> Optional[DetectionResult]:
    """
    Detect spoilage from a static image file.
    Useful for testing without a camera.
    """
    detector = VECNASpoilageDetector()
    
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"Error: Could not load image {image_path}")
        return None
    
    result = detector.detect_from_frame(frame)
    
    if result:
        print("\n" + "="*50)
        print("  VECNA Spoilage Detection Result")
        print("="*50)
        print(f"  Package ID:    {result.package_id}")
        print(f"  Product:       {result.product_type}")
        print(f"  Batch:         {result.batch_id}")
        print(f"  Pack Date:     {result.pack_date}")
        print(f"  ArUco ID:      {result.aruco_id}")
        print("-"*50)
        print(f"  Spoilage Level:      {result.spoilage_level.value}")
        print(f"  Spoilage Percentage: {result.spoilage_percentage}%")
        print(f"  Confidence:          {result.confidence}%")
        print("-"*50)
        print(f"  White (Fresh):  {result.color_readings.get('fresh_percent', 0)}%")
        print(f"  Color (Spoiled): {result.color_readings.get('spoiled_percent', 0)}%")
        print(f"  Avg Saturation:  {result.color_readings.get('avg_saturation', 0)}")
        print(f"  Avg Value:       {result.color_readings.get('avg_value', 0)}")
        print("-"*50)
        print(f"  Safe to Consume: {'YES' if result.is_safe else 'NO!'}")
        print(f"  {result.recommendation}")
        print("="*50 + "\n")
    else:
        print("No VECNA label detected in image (ArUco marker required).")
    
    return result


# ============================================================================
# WEB INTERFACE ROUTES
# ============================================================================

@app.route('/detector')
def detector_page():
    """Render the spoilage detector web interface."""
    return render_template('detector.html')


@app.route('/api/detect', methods=['POST'])
def api_detect():
    """API endpoint to detect spoilage from uploaded image."""
    try:
        detector = VECNASpoilageDetector()
        
        # Check if image is uploaded as file or base64
        if 'image' in request.files:
            file = request.files['image']
            # Read image from file
            file_bytes = np.frombuffer(file.read(), np.uint8)
            frame = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        elif request.json and 'image' in request.json:
            # Base64 encoded image (from webcam)
            image_data = request.json['image']
            # Remove data URL prefix if present
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            # Decode base64
            img_bytes = base64.b64decode(image_data)
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            return jsonify({'success': False, 'error': 'No image provided'}), 400
        
        if frame is None:
            return jsonify({'success': False, 'error': 'Could not decode image'}), 400
        
        # Perform detection (handles both QR-only and ArUco+visual)
        result = detector.detect_from_frame(frame)
        
        if result:
            # Draw overlay on image if we have ArUco markers
            aruco_results = detector.detect_aruco_markers(frame)
            qr_results = detector.decode_qr_codes(frame)
            
            if aruco_results:
                aruco = aruco_results[0]
                region = detector.find_indicator_region_from_aruco(frame, aruco['rect'])
                if region:
                    qr_poly = qr_results[0]['polygon'] if qr_results else None
                    frame = detector.draw_detection_overlay(frame, result, aruco['corners'], region, qr_poly)
            elif qr_results:
                # QR-only detection - draw simple overlay
                qr_poly = qr_results[0]['polygon']
                cv2.polylines(frame, [qr_poly], True, (0, 255, 0), 3)
                
                # Draw status panel
                panel_height = 150
                panel = np.zeros((panel_height, frame.shape[1], 3), dtype=np.uint8)
                panel[:] = (40, 40, 40)
                
                status_color = (0, 255, 0) if result.is_safe else (0, 0, 255)
                cv2.circle(panel, (50, 50), 30, status_color, -1)
                cv2.putText(panel, f"Package: {result.package_id}", (100, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(panel, f"Status: {result.spoilage_level.value} (QR Verified)", (100, 60), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
                cv2.putText(panel, result.recommendation[:70], (20, 110), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 1)
                
                frame = np.vstack([frame, panel])
            
            # Encode result image to base64
            _, buffer = cv2.imencode('.jpg', frame)
            result_image = base64.b64encode(buffer).decode('utf-8')
            
            return jsonify({
                'success': True,
                'result': {
                    'package_id': result.package_id,
                    'product_type': result.product_type,
                    'batch_id': result.batch_id,
                    'pack_date': result.pack_date,
                    'aruco_id': result.aruco_id,
                    'spoilage_level': result.spoilage_level.value,
                    'spoilage_percentage': result.spoilage_percentage,
                    'confidence': result.confidence,
                    'is_safe': result.is_safe,
                    'recommendation': result.recommendation,
                    'color_readings': result.color_readings
                },
                'result_image': f'data:image/jpeg;base64,{result_image}'
            })
        else:
            # No detection - still return the image
            _, buffer = cv2.imencode('.jpg', frame)
            result_image = base64.b64encode(buffer).decode('utf-8')
            
            return jsonify({
                'success': False,
                'error': 'No VECNA label detected. Ensure ArUco marker is visible.',
                'result_image': f'data:image/jpeg;base64,{result_image}'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='VECNA Spoilage Detector')
    parser.add_argument('--image', '-i', type=str, help='Path to image file for detection')
    parser.add_argument('--camera', '-c', type=int, default=0, help='Camera ID (default: 0)')
    parser.add_argument('--debug', '-d', action='store_true', help='Enable debug mode')
    parser.add_argument('--web', '-w', action='store_true', help='Run web interface')
    parser.add_argument('--port', '-p', type=int, default=5002, help='Web server port (default: 5002)')
    
    args = parser.parse_args()
    
    if args.web:
        # Web interface mode
        print("\n" + "="*60)
        print("  VECNA Spoilage Detector - Web Interface")
        print("="*60)
        print(f"\n  Detector: http://localhost:{args.port}/detector")
        print("="*60 + "\n")
        app.run(debug=True, host='0.0.0.0', port=args.port)
    elif args.image:
        # Static image detection
        detect_from_image(args.image)
    else:
        # Live camera detection
        detector = VECNASpoilageDetector(camera_id=args.camera, debug=args.debug)
        detector.run_detection_loop()
