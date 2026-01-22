"""
VECNA Label Generator - Web Interface
Generates spoilage indicator labels with QR codes for chicken packages.
"""

from flask import Flask, render_template, request, send_file, jsonify
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import mm, inch
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white, black
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics import renderPDF
import qrcode
from PIL import Image
import cv2
import numpy as np
import io
import os
import uuid
import json
from datetime import datetime, timedelta

# ArUco dictionary for marker generation
ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_250)

app = Flask(__name__)

# Configuration
LABEL_WIDTH = 80 * mm   # 8 cm width
LABEL_HEIGHT = 45 * mm  # 4.5 cm height
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'generated_labels')

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)


def generate_qr_code(data: str, size: int = 100) -> Image.Image:
    """Generate a QR code image from data."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    return img


def generate_aruco_marker(marker_id: int, size: int = 200) -> Image.Image:
    """Generate an ArUco marker image."""
    # Generate the marker
    marker_image = cv2.aruco.generateImageMarker(ARUCO_DICT, marker_id, size)
    
    # Add white border
    border_size = size // 10
    marker_with_border = cv2.copyMakeBorder(
        marker_image, 
        border_size, border_size, border_size, border_size,
        cv2.BORDER_CONSTANT, 
        value=255
    )
    
    # Convert to PIL Image
    pil_image = Image.fromarray(marker_with_border)
    return pil_image


def draw_spoilage_indicator(c: canvas.Canvas, x: float, y: float, width: float, height: float):
    """Draw the spoilage indicator gradient bar."""
    # Draw border
    c.setStrokeColor(HexColor('#4A6FA5'))
    c.setLineWidth(1.5)
    c.roundRect(x, y, width, height, 5, stroke=1, fill=0)
    
    # Inner padding
    inner_x = x + 3
    inner_y = y + 3
    inner_width = width - 6
    inner_height = height - 6
    
    # Draw gradient segments (FRESH to SPOILED)
    # Fresh section (white/light gray) - 70%
    fresh_width = inner_width * 0.70
    c.setFillColor(HexColor('#F5F5F5'))
    c.rect(inner_x, inner_y, fresh_width, inner_height, stroke=0, fill=1)
    
    # Transition section (tan/beige) - 15%
    trans_x = inner_x + fresh_width
    trans_width = inner_width * 0.15
    c.setFillColor(HexColor('#C4A574'))
    c.rect(trans_x, inner_y, trans_width, inner_height, stroke=0, fill=1)
    
    # Spoiled section (brown) - 15%
    spoil_x = trans_x + trans_width
    spoil_width = inner_width * 0.15
    c.setFillColor(HexColor('#8B6914'))
    c.rect(spoil_x, inner_y, spoil_width, inner_height, stroke=0, fill=1)


def draw_vecna_label(c: canvas.Canvas, x: float, y: float, label_data: dict):
    """Draw a single VECNA spoilage indicator label."""
    
    # Label dimensions
    w = LABEL_WIDTH
    h = LABEL_HEIGHT
    
    # Draw white background with rounded corners
    c.setFillColor(white)
    c.setStrokeColor(HexColor('#E0E0E0'))
    c.setLineWidth(0.5)
    c.roundRect(x, y, w, h, 6, stroke=1, fill=1)
    
    # Draw header wave/banner (blue arc) - scaled for smaller label
    c.setFillColor(HexColor('#A8C8E8'))
    c.saveState()
    path = c.beginPath()
    path.moveTo(x, y + h - 12*mm)
    path.curveTo(x + w*0.3, y + h - 8*mm, x + w*0.7, y + h - 14*mm, x + w, y + h - 10*mm)
    path.lineTo(x + w, y + h)
    path.lineTo(x, y + h)
    path.close()
    c.drawPath(path, fill=1, stroke=0)
    c.restoreState()
    
    # Draw bird/whale icon (simplified) - smaller
    c.setFillColor(HexColor('#4A7AB0'))
    icon_x = x + 6*mm
    icon_y = y + h - 9*mm
    c.circle(icon_x, icon_y + 1.5*mm, 3*mm, stroke=0, fill=1)
    c.setFillColor(white)
    c.circle(icon_x - 0.8*mm, icon_y + 2*mm, 0.6*mm, stroke=0, fill=1)  # Eye
    
    # PROJECT VECNA title
    c.setFillColor(HexColor('#2C5282'))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x + 14*mm, y + h - 8*mm, "PROJECT VECNA")
    
    # SPOILAGE INDICATOR header
    c.setFillColor(HexColor('#4A6FA5'))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(x + 20*mm, y + h - 14*mm, "SPOILAGE INDICATOR")
    
    # Generate unique ArUco marker ID from package_id
    package_id = label_data.get('package_id', str(uuid.uuid4())[:8])
    marker_id = hash(package_id) % 250
    
    # Generate and draw ArUco marker on left side
    aruco_img = generate_aruco_marker(marker_id, 200)
    aruco_buffer = io.BytesIO()
    aruco_img.save(aruco_buffer, format='PNG')
    aruco_buffer.seek(0)
    
    # ArUco marker position - left side, scaled for smaller label
    aruco_x = x + 3*mm
    aruco_y = y + 5*mm
    aruco_size = 14*mm
    
    # Draw ArUco border
    c.setStrokeColor(black)
    c.setLineWidth(1.5)
    c.rect(aruco_x - 0.5*mm, aruco_y - 0.5*mm, aruco_size + 1*mm, aruco_size + 1*mm, stroke=1, fill=0)
    
    # Draw ArUco marker image
    from reportlab.lib.utils import ImageReader
    aruco_buffer.seek(0)
    aruco_reader = ImageReader(aruco_buffer)
    c.drawImage(aruco_reader, aruco_x, aruco_y, width=aruco_size, height=aruco_size)
    
    # ArUco ID label below marker
    c.setFont("Helvetica", 5)
    c.setFillColor(HexColor('#666666'))
    c.drawString(aruco_x, aruco_y - 3*mm, f"ArUco: {marker_id}")
    
    # Draw spoilage indicator bar (next to ArUco marker)
    indicator_x = x + 20*mm
    indicator_y = y + 8*mm
    indicator_w = 45*mm
    indicator_h = 10*mm
    draw_spoilage_indicator(c, indicator_x, indicator_y, indicator_w, indicator_h)
    
    # Draw FRESH and SPOILED labels below the indicator bar
    c.setFont("Helvetica-Bold", 5)
    c.setFillColor(HexColor('#666666'))
    c.drawString(indicator_x + 2*mm, indicator_y - 3*mm, "FRESH")
    
    c.setFillColor(HexColor('#8B4513'))
    c.drawString(indicator_x + indicator_w - 10*mm, indicator_y - 3*mm, "SPOILED")
    
    # Draw QR code in bottom RIGHT corner
    is_spoiled = label_data.get('is_spoiled', False)
    
    qr_data = json.dumps({
        'id': package_id,
        'product': label_data.get('product_type', 'Chicken'),
        'packed': label_data.get('pack_date', datetime.now().isoformat()),
        'batch': label_data.get('batch_id', 'BATCH-001'),
        'aruco_id': marker_id,
        'is_spoiled': is_spoiled
    })
    
    qr_size = 9*mm
    qr_x = x + w - qr_size - 2*mm
    qr_y = y + 2*mm
    
    qr_widget = QrCodeWidget(qr_data)
    qr_widget.barWidth = qr_size
    qr_widget.barHeight = qr_size
    qr_drawing = Drawing(qr_size, qr_size)
    qr_drawing.add(qr_widget)
    renderPDF.draw(qr_drawing, c, qr_x, qr_y)


def generate_label_pdf(labels_data: list, filename: str = None) -> str:
    """Generate a PDF with multiple labels."""
    if not filename:
        filename = f"vecna_labels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    # Create PDF
    c = canvas.Canvas(filepath, pagesize=A4)
    page_width, page_height = A4
    
    # Calculate grid layout (2 columns, 4 rows per page)
    cols = 2
    rows = 4
    labels_per_page = cols * rows
    
    margin_x = 15*mm
    margin_y = 15*mm
    spacing_x = 10*mm
    spacing_y = 10*mm
    
    for i, label_data in enumerate(labels_data):
        page_index = i // labels_per_page
        label_index = i % labels_per_page
        
        # New page if needed
        if label_index == 0 and i > 0:
            c.showPage()
        
        # Calculate position
        col = label_index % cols
        row = label_index // cols
        
        x = margin_x + col * (LABEL_WIDTH + spacing_x)
        y = page_height - margin_y - (row + 1) * (LABEL_HEIGHT + spacing_y) + spacing_y
        
        draw_vecna_label(c, x, y, label_data)
    
    c.save()
    return filepath


# ============================================================================
# WEB ROUTES
# ============================================================================

@app.route('/labels')
def label_generator_page():
    """Render the label generator web interface."""
    return render_template('label_generator.html')


@app.route('/api/generate-labels', methods=['POST'])
def api_generate_labels():
    """API endpoint to generate labels."""
    try:
        data = request.get_json()
        
        num_labels = data.get('num_labels', 1)
        product_type = data.get('product_type', 'Chicken')
        batch_id = data.get('batch_id', f"BATCH-{datetime.now().strftime('%Y%m%d')}")
        pack_date = data.get('pack_date', datetime.now().isoformat())
        is_spoiled = data.get('is_spoiled', False)  # True = spoiled, False = fresh
        
        # Generate label data
        labels_data = []
        for i in range(num_labels):
            label = {
                'package_id': f"PKG-{uuid.uuid4().hex[:8].upper()}",
                'product_type': product_type,
                'batch_id': batch_id,
                'pack_date': pack_date,
                'is_spoiled': is_spoiled,
                'label_number': i + 1
            }
            labels_data.append(label)
        
        # Generate PDF
        filename = f"vecna_labels_{batch_id}_{datetime.now().strftime('%H%M%S')}.pdf"
        filepath = generate_label_pdf(labels_data, filename)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'labels_generated': num_labels,
            'download_url': f'/download-labels/{filename}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/download-labels/<filename>')
def download_labels(filename):
    """Download generated label PDF."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=filename)
    return jsonify({'error': 'File not found'}), 404


@app.route('/api/preview-label', methods=['POST'])
def preview_label():
    """Generate a preview image of a single label."""
    try:
        data = request.get_json() or {}
        
        label_data = {
            'package_id': data.get('package_id', f"PKG-{uuid.uuid4().hex[:8].upper()}"),
            'product_type': data.get('product_type', 'Chicken'),
            'batch_id': data.get('batch_id', f"BATCH-{datetime.now().strftime('%Y%m%d')}"),
            'pack_date': data.get('pack_date', datetime.now().isoformat()),
            'is_spoiled': data.get('is_spoiled', False)  # True = spoiled, False = fresh
        }
        
        # Generate single label PDF
        filename = f"preview_{uuid.uuid4().hex[:8]}.pdf"
        filepath = generate_label_pdf([label_data], filename)
        
        return send_file(filepath, mimetype='application/pdf')
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# STANDALONE MODE
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  VECNA Label Generator")
    print("  Web Interface for Spoilage Indicator Labels")
    print("="*60)
    print("\n  Label Generator: http://localhost:5001/labels")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5001)
