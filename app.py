"""
AI Weapon Detection System - Flask Application
Advanced web application for real-time AI video analysis
and weapon detection using YOLOv8 and Computer Vision.
"""

import os
import json
import uuid
import threading
from pathlib import Path
from datetime import datetime

from flask import (
    Flask, render_template, request, jsonify,
    send_file, redirect, url_for, session
)
from werkzeug.utils import secure_filename

from detector import WeaponDetector
from video_processor import VideoProcessor
from report_generator import generate_report
from auth import init_db, register_user, authenticate_user, login_required, get_current_user

# ── App Configuration ──────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = 'sentinel-ai-secret-key-2026-weapon-detection'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

# Initialize user database
init_db()

UPLOAD_DIR = Path(__file__).parent / 'static' / 'uploads'
PROCESSED_DIR = UPLOAD_DIR / 'processed'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
ALLOWED_VIDEO_EXT = {'.mp4', '.avi', '.mov', '.mkv', '.wmv'}
ALLOWED_EXT = ALLOWED_IMAGE_EXT | ALLOWED_VIDEO_EXT

# ── Global State ───────────────────────────────────────────────────
detector = None
processor = None
processing_jobs = {}  # job_id -> {status, progress, result}


def get_detector():
    global detector, processor
    if detector is None:
        detector = WeaponDetector(confidence_threshold=0.25)
        processor = VideoProcessor(detector)
    return detector, processor


# ── Auth Routes ────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """Login page."""
    if 'user_id' in session:
        return redirect(url_for('index'))

    error = None
    success = request.args.get('registered')
    if success:
        success = 'Account created successfully! Please sign in.'

    if request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        ok, result = authenticate_user(email, password)
        if ok:
            session['user_id'] = result['id']
            session['user_name'] = result['fullname']
            session['user_email'] = result['email']
            return redirect(url_for('index'))
        else:
            error = result

    return render_template('login.html', error=error, success=success)


@app.route('/signup', methods=['GET', 'POST'])
def signup_page():
    """Signup page."""
    if 'user_id' in session:
        return redirect(url_for('index'))

    error = None
    if request.method == 'POST':
        fullname = request.form.get('fullname', '')
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if password != confirm:
            error = 'Passwords do not match'
        else:
            ok, msg = register_user(fullname, email, password)
            if ok:
                return redirect(url_for('login_page', registered='1'))
            else:
                error = msg

    return render_template('signup.html', error=error)


@app.route('/logout')
def logout():
    """Log out the current user."""
    session.clear()
    return redirect(url_for('login_page'))


# ── Protected Routes ───────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    """Landing page."""
    return render_template('index.html', user=get_current_user())


@app.route('/upload')
@login_required
def upload_page():
    """Upload page."""
    return render_template('upload.html', user=get_current_user())


@app.route('/results/<job_id>')
@login_required
def results_page(job_id):
    """Detection results page."""
    job = processing_jobs.get(job_id)
    if not job:
        return redirect(url_for('upload_page'))
    return render_template('results.html', job_id=job_id, job=job, user=get_current_user())


@app.route('/report/<job_id>')
@login_required
def report_page(job_id):
    """AI interpretation report page."""
    job = processing_jobs.get(job_id)
    if not job or job['status'] != 'completed':
        return redirect(url_for('upload_page'))
    return render_template('report.html', job_id=job_id, job=job, user=get_current_user())


# ── API Endpoints ──────────────────────────────────────────────────

@app.route('/api/upload', methods=['POST'])
def api_upload():
    """Handle file upload and start processing."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        return jsonify({'error': f'Unsupported file format: {ext}'}), 400

    # Save uploaded file
    safe_name = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    file_path = UPLOAD_DIR / unique_name
    file.save(str(file_path))

    # Determine file type
    is_video = ext in ALLOWED_VIDEO_EXT
    file_type = 'video' if is_video else 'image'

    # Create processing job
    job_id = uuid.uuid4().hex[:12]
    processing_jobs[job_id] = {
        'status': 'processing',
        'progress': 0,
        'message': 'Starting analysis...',
        'file_path': str(file_path),
        'file_name': safe_name,
        'file_type': file_type,
        'original_url': f"/static/uploads/{unique_name}",
        'result': None,
        'created_at': datetime.now().isoformat(),
    }

    # Start processing in background thread
    thread = threading.Thread(
        target=_process_job,
        args=(job_id, str(file_path), file_type),
        daemon=True
    )
    thread.start()

    return jsonify({
        'job_id': job_id,
        'status': 'processing',
        'file_type': file_type,
    })


@app.route('/api/status/<job_id>')
def api_status(job_id):
    """Get processing job status."""
    job = processing_jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    response = {
        'status': job['status'],
        'progress': job['progress'],
        'message': job.get('message', ''),
        'file_type': job['file_type'],
    }

    if job['status'] == 'completed' and job['result']:
        result = job['result']
        response['threat_level'] = result.get(
            'max_threat_level',
            result.get('threat', {}).get('level', 'SAFE')
        )
        response['weapon_count'] = result.get(
            'total_weapons_detected',
            result.get('weapon_count', 0)
        )

    if job['status'] == 'error':
        response['error'] = job.get('error', 'Unknown error')

    return jsonify(response)


@app.route('/api/results/<job_id>')
def api_results(job_id):
    """Get full results for a completed job."""
    job = processing_jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    if job['status'] != 'completed':
        return jsonify({
            'error': 'Job not completed',
            'status': job['status'],
        }), 400

    result = job['result']

    # Build response (excluding raw frame data for JSON size)
    response = {
        'job_id': job_id,
        'file_type': job['file_type'],
        'file_name': job['file_name'],
        'original_url': job['original_url'],
        'status': 'completed',
    }

    if job['file_type'] == 'video':
        response.update({
            'output_url': result.get('output_video', ''),
            'total_frames': result.get('total_frames', 0),
            'processed_frames': result.get('processed_frames', 0),
            'duration': result.get('duration', 0),
            'fps': result.get('fps', 0),
            'width': result.get('width', 0),
            'height': result.get('height', 0),
            'total_weapons': result.get('total_weapons_detected', 0),
            'total_persons': result.get('total_persons_detected', 0),
            'weapon_frames': result.get('weapon_frames', 0),
            'max_threat_level': result.get('max_threat_level', 'SAFE'),
            'avg_confidence': result.get('avg_confidence', 0),
            'processing_fps': result.get('avg_processing_fps', 0),
            'inference_ms': result.get('avg_inference_ms', 0),
            'heatmap': result.get('heatmap', []),
            'frame_snapshots': result.get('frame_snapshots', []),
            'interpretation': result.get('interpretation', {}),
        })
    else:
        threat = result.get('threat', {})
        response.update({
            'output_url': result.get('output_image', ''),
            'detections': result.get('detections', []),
            'weapon_count': result.get('weapon_count', 0),
            'person_count': result.get('person_count', 0),
            'threat_level': threat.get('level', 'SAFE'),
            'threat_score': threat.get('score', 0),
            'threat_message': threat.get('message', ''),
            'threat_details': threat.get('details', []),
            'avg_confidence': result.get('avg_confidence', 0),
            'inference_ms': result.get('inference_time_ms', 0),
            'interpretation': result.get('interpretation', {}),
        })

    return jsonify(response)


@app.route('/api/report/<job_id>')
def api_generate_report(job_id):
    """Generate and download PDF report."""
    job = processing_jobs.get(job_id)
    if not job or job['status'] != 'completed':
        return jsonify({'error': 'No completed job found'}), 404

    try:
        report_path = generate_report(job['result'])
        return send_file(
            report_path,
            as_attachment=True,
            download_name=f"weapon_detection_report_{job_id}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/report-data/<job_id>')
def api_report_data(job_id):
    """Get report data as JSON for the report page."""
    job = processing_jobs.get(job_id)
    if not job or job['status'] != 'completed':
        return jsonify({'error': 'No completed job found'}), 404

    result = job['result']
    interpretation = result.get('interpretation', {})
    threat = result.get('threat', {})

    is_video = job['file_type'] == 'video'

    data = {
        'job_id': job_id,
        'file_type': job['file_type'],
        'file_name': job['file_name'],
        'created_at': job['created_at'],
        'threat_level': result.get('max_threat_level', threat.get('level', 'SAFE')),
        'threat_score': result.get('threat', {}).get('score', 0)
            if not is_video else
            max((h.get('score', 0) for h in result.get('heatmap', [{'score': 0}])), default=0),
        'interpretation': interpretation,
        'avg_confidence': result.get('avg_confidence', 0),
    }

    if is_video:
        data.update({
            'total_frames': result.get('total_frames', 0),
            'processed_frames': result.get('processed_frames', 0),
            'duration': result.get('duration', 0),
            'total_weapons': result.get('total_weapons_detected', 0),
            'weapon_frames': result.get('weapon_frames', 0),
            'processing_fps': result.get('avg_processing_fps', 0),
            'heatmap': result.get('heatmap', []),
            'frame_snapshots': result.get('frame_snapshots', []),
        })
    else:
        data.update({
            'weapon_count': result.get('weapon_count', 0),
            'person_count': result.get('person_count', 0),
            'threat_details': threat.get('details', []),
            'inference_ms': result.get('inference_time_ms', 0),
        })

    return jsonify(data)


# ── Background Processing ─────────────────────────────────────────

def _process_job(job_id, file_path, file_type):
    """Process uploaded file in background thread."""
    try:
        _, proc = get_detector()

        def progress_cb(percent, message):
            processing_jobs[job_id]['progress'] = percent
            processing_jobs[job_id]['message'] = message

        if file_type == 'video':
            processing_jobs[job_id]['message'] = 'Analyzing video frames...'
            # Process 1 frame per second for speed (auto frame_skip based on fps)
            result = proc.process_video(file_path, progress_callback=progress_cb, frame_skip=None)
        else:
            processing_jobs[job_id]['message'] = 'Analyzing image...'
            processing_jobs[job_id]['progress'] = 50
            result = proc.process_image(file_path)
            processing_jobs[job_id]['progress'] = 100

        processing_jobs[job_id]['status'] = 'completed'
        processing_jobs[job_id]['result'] = result
        processing_jobs[job_id]['message'] = 'Analysis complete'

    except Exception as e:
        processing_jobs[job_id]['status'] = 'error'
        processing_jobs[job_id]['error'] = str(e)
        processing_jobs[job_id]['message'] = f'Error: {str(e)}'
        print(f"[!] Processing error for job {job_id}: {e}")


@app.route('/health')
def health():
    return jsonify({'status': 'ok'}), 200


# ── Main ───────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print("=" * 60)
    print("  AI WEAPON DETECTION SYSTEM")
    print(f"  Starting server on http://0.0.0.0:{port}")
    print("=" * 60)
    print("[*] Server starting (model loads on first request)...")
    # use_reloader=False prevents auto-restart which wipes in-memory jobs
    app.run(debug=False, use_reloader=False, host='0.0.0.0', port=port)
