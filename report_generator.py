"""
Report Generator Module
Creates PDF reports with charts, detection summaries,
and threat analysis using ReportLab and Matplotlib.
"""

import io
import os
import json
from pathlib import Path
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
    Table, TableStyle, PageBreak, HRFlowable
)


REPORTS_DIR = Path(__file__).parent / 'reports'
REPORTS_DIR.mkdir(exist_ok=True)

THREAT_COLORS = {
    'HIGH': colors.HexColor('#FF0040'),
    'MEDIUM': colors.HexColor('#FF8800'),
    'LOW': colors.HexColor('#FFCC00'),
    'SAFE': colors.HexColor('#00CC66'),
}


def generate_report(analysis_data, filename=None):
    """
    Generate a PDF report from analysis results.

    Args:
        analysis_data: Dict from VideoProcessor or image analysis
        filename: Optional output filename

    Returns:
        Path to generated PDF file
    """
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"threat_report_{timestamp}.pdf"

    output_path = REPORTS_DIR / filename
    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=25 * mm, bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Title'],
        fontSize=24, spaceAfter=20,
        textColor=colors.HexColor('#0A0E27'),
    )
    heading_style = ParagraphStyle(
        'CustomHeading', parent=styles['Heading2'],
        fontSize=16, spaceAfter=10, spaceBefore=15,
        textColor=colors.HexColor('#1a1a2e'),
    )
    body_style = ParagraphStyle(
        'CustomBody', parent=styles['Normal'],
        fontSize=11, spaceAfter=6, leading=14,
    )
    alert_style = ParagraphStyle(
        'AlertStyle', parent=styles['Normal'],
        fontSize=13, spaceAfter=10,
        textColor=colors.white, backColor=colors.HexColor('#FF0040'),
        borderPadding=10, leading=18,
    )

    elements = []

    # === HEADER ===
    elements.append(Paragraph("AI WEAPON DETECTION REPORT", title_style))
    elements.append(HRFlowable(
        width="100%", thickness=2,
        color=colors.HexColor('#00d4ff'), spaceAfter=10
    ))

    now = datetime.now().strftime('%B %d, %Y at %H:%M:%S')
    elements.append(Paragraph(f"Generated: {now}", body_style))
    elements.append(Spacer(1, 10))

    # === THREAT SUMMARY ===
    threat_level = analysis_data.get('max_threat_level',
                                      analysis_data.get('threat', {}).get('level', 'SAFE'))
    threat_color = THREAT_COLORS.get(threat_level, THREAT_COLORS['SAFE'])

    elements.append(Paragraph("THREAT ASSESSMENT", heading_style))

    threat_data = [
        ['Threat Level', threat_level],
        ['Status', 'WEAPON DETECTED' if threat_level != 'SAFE' else 'SAFE'],
    ]

    # Add interpretation if available
    interpretation = analysis_data.get('interpretation', {})
    if interpretation.get('summary'):
        threat_data.append(['Summary', interpretation['summary']])

    threat_table = Table(threat_data, colWidths=[150, 300])
    threat_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
        ('BACKGROUND', (1, 0), (1, 0), threat_color),
        ('TEXTCOLOR', (1, 0), (1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#333366')),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(threat_table)
    elements.append(Spacer(1, 15))

    # === DETECTION STATISTICS ===
    elements.append(Paragraph("DETECTION STATISTICS", heading_style))

    is_video = 'total_frames' in analysis_data
    if is_video:
        stats_data = [
            ['Metric', 'Value'],
            ['Total Frames', str(analysis_data.get('total_frames', 'N/A'))],
            ['Processed Frames', str(analysis_data.get('processed_frames', 'N/A'))],
            ['Video Duration', f"{analysis_data.get('duration', 0):.1f}s"],
            ['Video FPS', str(analysis_data.get('fps', 'N/A'))],
            ['Resolution', f"{analysis_data.get('width', 0)}x{analysis_data.get('height', 0)}"],
            ['Weapons Detected', str(analysis_data.get('total_weapons_detected', 0))],
            ['Persons Detected', str(analysis_data.get('total_persons_detected', 0))],
            ['Frames with Weapons', str(analysis_data.get('weapon_frames', 0))],
            ['Avg Confidence', f"{analysis_data.get('avg_confidence', 0):.1%}"],
            ['Processing Speed', f"{analysis_data.get('avg_processing_fps', 0):.1f} FPS"],
            ['Avg Inference Time', f"{analysis_data.get('avg_inference_ms', 0):.1f} ms"],
        ]
    else:
        stats_data = [
            ['Metric', 'Value'],
            ['Weapons Detected', str(analysis_data.get('weapon_count', 0))],
            ['Persons Detected', str(analysis_data.get('person_count', 0))],
            ['Avg Confidence', f"{analysis_data.get('avg_confidence', 0):.1%}"],
            ['Inference Time', f"{analysis_data.get('inference_time_ms', 0):.1f} ms"],
        ]

    stats_table = Table(stats_data, colWidths=[200, 250])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f5')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(stats_table)
    elements.append(Spacer(1, 15))

    # === TIMELINE HEATMAP CHART (for videos) ===
    if is_video and analysis_data.get('heatmap'):
        elements.append(Paragraph("THREAT TIMELINE", heading_style))
        chart_path = _generate_timeline_chart(analysis_data['heatmap'])
        if chart_path:
            elements.append(RLImage(chart_path, width=500, height=180))
            elements.append(Spacer(1, 10))

    # === CONFIDENCE DISTRIBUTION CHART ===
    if is_video and analysis_data.get('all_detections'):
        weapon_confs = []
        for frame_data in analysis_data['all_detections']:
            for det in frame_data.get('detections', []):
                if det['type'] == 'weapon':
                    weapon_confs.append(det['confidence'])
        if weapon_confs:
            elements.append(Paragraph("CONFIDENCE DISTRIBUTION", heading_style))
            conf_chart_path = _generate_confidence_chart(weapon_confs)
            if conf_chart_path:
                elements.append(RLImage(conf_chart_path, width=400, height=200))
                elements.append(Spacer(1, 10))

    # === AI INTERPRETATION ===
    elements.append(Paragraph("AI INTERPRETATION", heading_style))
    if interpretation.get('messages'):
        for msg in interpretation['messages']:
            elements.append(Paragraph(f"  {msg}", body_style))
    else:
        elements.append(Paragraph("No additional interpretation available.", body_style))

    elements.append(Spacer(1, 10))

    # === RECOMMENDATIONS ===
    if interpretation.get('recommendations'):
        elements.append(Paragraph("RECOMMENDATIONS", heading_style))
        for rec in interpretation['recommendations']:
            elements.append(Paragraph(f"  {rec}", body_style))

    elements.append(Spacer(1, 20))

    # === DETECTION DETAILS TABLE ===
    if is_video and analysis_data.get('all_detections'):
        weapon_frames_data = [
            fd for fd in analysis_data['all_detections']
            if fd.get('weapon_count', 0) > 0
        ]
        if weapon_frames_data:
            elements.append(PageBreak())
            elements.append(Paragraph("FRAME-BY-FRAME DETECTIONS", heading_style))

            detail_data = [['Frame', 'Time (s)', 'Weapons', 'Threat', 'Labels']]
            for fd in weapon_frames_data[:50]:  # Limit to 50 entries
                labels = ', '.join(
                    f"{d['label']} ({d['confidence']:.0%})"
                    for d in fd['detections'] if d['type'] == 'weapon'
                )
                detail_data.append([
                    str(fd['frame']),
                    f"{fd['second']:.1f}",
                    str(fd['weapon_count']),
                    fd['threat'],
                    labels,
                ])

            detail_table = Table(detail_data, colWidths=[60, 60, 60, 70, 200])
            detail_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('PADDING', (0, 0), (-1, -1), 5),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1),
                 [colors.white, colors.HexColor('#f8f8fc')]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(detail_table)

    # === FOOTER ===
    elements.append(Spacer(1, 30))
    elements.append(HRFlowable(
        width="100%", thickness=1,
        color=colors.HexColor('#cccccc'), spaceAfter=10
    ))
    footer_style = ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontSize=8, textColor=colors.grey, alignment=TA_CENTER,
    )
    elements.append(Paragraph(
        "AI Weapon Detection System - Confidential Report - "
        f"Generated {now}",
        footer_style
    ))

    # Build PDF
    doc.build(elements)
    return str(output_path)


def _generate_timeline_chart(heatmap):
    """Generate timeline heatmap chart and return path to image."""
    if not heatmap:
        return None

    fig, ax = plt.subplots(figsize=(10, 3))
    fig.patch.set_facecolor('#0a0e27')
    ax.set_facecolor('#0a0e27')

    seconds = [h['second'] for h in heatmap]
    scores = [h['score'] for h in heatmap]
    threat_colors_map = {
        'SAFE': '#00cc66', 'LOW': '#ffcc00',
        'MEDIUM': '#ff8800', 'HIGH': '#ff0040',
    }
    bar_colors = [threat_colors_map.get(h['threat'], '#00cc66') for h in heatmap]

    ax.bar(seconds, scores, color=bar_colors, width=0.8, alpha=0.85)
    ax.set_xlabel('Time (seconds)', color='white', fontsize=9)
    ax.set_ylabel('Threat Score', color='white', fontsize=9)
    ax.set_title('Weapon Detection Timeline', color='#00d4ff', fontsize=12, fontweight='bold')
    ax.tick_params(colors='white', labelsize=8)
    ax.spines['bottom'].set_color('#333366')
    ax.spines['left'].set_color('#333366')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_ylim(0, 100)

    # Legend
    patches = [
        mpatches.Patch(color=c, label=l)
        for l, c in threat_colors_map.items()
    ]
    ax.legend(handles=patches, loc='upper right', fontsize=7,
              facecolor='#1a1a2e', edgecolor='#333366', labelcolor='white')

    plt.tight_layout()
    chart_path = str(REPORTS_DIR / 'timeline_chart.png')
    fig.savefig(chart_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return chart_path


def _generate_confidence_chart(confidences):
    """Generate confidence distribution histogram."""
    if not confidences:
        return None

    fig, ax = plt.subplots(figsize=(8, 3.5))
    fig.patch.set_facecolor('#0a0e27')
    ax.set_facecolor('#0a0e27')

    ax.hist(confidences, bins=20, range=(0, 1),
            color='#00d4ff', alpha=0.8, edgecolor='#0099cc')
    ax.set_xlabel('Confidence Score', color='white', fontsize=9)
    ax.set_ylabel('Count', color='white', fontsize=9)
    ax.set_title('Detection Confidence Distribution',
                 color='#00d4ff', fontsize=12, fontweight='bold')
    ax.tick_params(colors='white', labelsize=8)
    ax.spines['bottom'].set_color('#333366')
    ax.spines['left'].set_color('#333366')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Add mean line
    mean_conf = np.mean(confidences)
    ax.axvline(mean_conf, color='#ff0040', linestyle='--', linewidth=2, label=f'Mean: {mean_conf:.2f}')
    ax.legend(fontsize=8, facecolor='#1a1a2e', edgecolor='#333366', labelcolor='white')

    plt.tight_layout()
    chart_path = str(REPORTS_DIR / 'confidence_chart.png')
    fig.savefig(chart_path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return chart_path
