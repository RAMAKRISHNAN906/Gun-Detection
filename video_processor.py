"""
Video Processing Module
Handles frame extraction, frame-by-frame detection,
annotated video generation, and timeline heatmap data.
"""

import cv2
import numpy as np
import json
import time
import os
import subprocess
import shutil
from pathlib import Path
from detector import WeaponDetector


class VideoProcessor:
    """Processes videos frame-by-frame with weapon detection."""

    def __init__(self, detector=None):
        self.detector = detector or WeaponDetector()
        self.upload_dir = Path(__file__).parent / 'static' / 'uploads'
        self.processed_dir = self.upload_dir / 'processed'
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def process_video(self, video_path, progress_callback=None, frame_skip=None):
        """
        Fast processing: analyze 25 sampled frames, output full-duration video.
        Phase 1 (~12s): seek & detect 25 frames.
        Phase 2 (~5s): write full video using nearest annotated frame per position.
        """
        MAX_SAMPLE_FRAMES = 25

        video_path = str(video_path)
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0

        # Resize for faster inference (max 640px wide)
        proc_width = min(width, 640)
        proc_height = int(height * proc_width / width) if width > 0 else height
        do_scale = proc_width != width

        # Evenly spaced sample indices
        n_samples = min(MAX_SAMPLE_FRAMES, total_frames)
        step = total_frames / n_samples
        sample_indices = [int(i * step) for i in range(n_samples)]

        basename = Path(video_path).stem

        # ── Phase 1: Detect on sampled frames ─────────────────────────
        all_detections = []
        timeline = []
        frame_snapshots = []
        total_weapons = 0
        total_persons = 0
        max_threat_level = 'SAFE'
        threat_priority = {'SAFE': 0, 'LOW': 1, 'MEDIUM': 2, 'HIGH': 3}
        total_confidence = 0
        confidence_count = 0
        processing_times = []
        weapon_frames = 0
        fighting_frames = 0
        max_fighting_group = 0
        processed_count = 0

        # Maps sample_frame_idx -> annotated frame (full resolution)
        annotated_map = {}

        for i, frame_idx in enumerate(sample_indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                continue

            current_second = frame_idx / fps if fps > 0 else 0
            small = cv2.resize(frame, (proc_width, proc_height)) if do_scale else frame
            result = self.detector.detect(small)

            annotated = cv2.resize(result['annotated_frame'], (width, height)) if do_scale else result['annotated_frame']
            annotated_map[frame_idx] = annotated

            processing_times.append(result['inference_time'])
            weapon_count = result['weapon_count']
            person_count = result['person_count']
            threat = result['threat']

            total_weapons += weapon_count
            total_persons += person_count
            if weapon_count > 0:
                weapon_frames += 1
            if result.get('fighting_detected'):
                fighting_frames += 1
                group_size = threat.get('fighting_group_size', 0)
                if group_size > max_fighting_group:
                    max_fighting_group = group_size
            for d in result['detections']:
                if d['type'] == 'weapon':
                    total_confidence += d['confidence']
                    confidence_count += 1
            if threat_priority.get(threat['level'], 0) > threat_priority.get(max_threat_level, 0):
                max_threat_level = threat['level']

            timeline.append({
                'second': int(current_second),
                'timestamp': round(current_second, 2),
                'threat_level': threat['level'],
                'weapon_count': weapon_count,
                'person_count': person_count,
                'score': threat['score'],
                'fighting': result.get('fighting_detected', False),
            })
            all_detections.append({
                'frame': frame_idx,
                'second': round(current_second, 2),
                'detections': [{'label': d['label'], 'confidence': round(d['confidence'], 3),
                                'bbox': d['bbox'], 'type': d['type']} for d in result['detections']],
                'threat': threat['level'],
                'weapon_count': weapon_count,
            })
            if weapon_count > 0 and len(frame_snapshots) < 20:
                snap_name = f"{basename}_frame_{frame_idx}.jpg"
                snap_path = str(self.processed_dir / snap_name)
                cv2.imwrite(snap_path, annotated)
                frame_snapshots.append({
                    'path': f"/static/uploads/processed/{snap_name}",
                    'frame': frame_idx, 'second': round(current_second, 2),
                    'threat': threat['level'], 'weapons': weapon_count,
                })

            processed_count += 1
            if progress_callback:
                percent = int(((i + 1) / n_samples) * 50)  # phase 1 = 0-50%
                progress_callback(percent, f"Analyzing frame {i+1}/{n_samples}")

        cap.release()

        # ── Phase 2: Write full-duration output video ──────────────────
        # For each original frame, use the nearest sampled annotated frame
        output_path = str(self.processed_dir / f"{basename}_detected.mp4")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        sorted_sample_indices = sorted(annotated_map.keys())

        cap2 = cv2.VideoCapture(video_path)
        frame_write_idx = 0
        while True:
            ret, orig_frame = cap2.read()
            if not ret:
                break

            # Find nearest sampled index
            nearest = min(sorted_sample_indices, key=lambda s: abs(s - frame_write_idx))
            out.write(annotated_map[nearest])

            frame_write_idx += 1
            if progress_callback and total_frames > 0:
                percent = 50 + int((frame_write_idx / total_frames) * 50)  # phase 2 = 50-100%
                if frame_write_idx % 30 == 0:
                    progress_callback(percent, f"Building output video...")

        cap2.release()
        out.release()

        # Re-encode to H.264 for browser playback
        output_path = self._reencode_h264(output_path)

        # Calculate summary statistics
        avg_processing_time = np.mean(processing_times) if processing_times else 0
        avg_fps = 1.0 / avg_processing_time if avg_processing_time > 0 else 0
        avg_confidence = total_confidence / confidence_count if confidence_count > 0 else 0

        # Build heatmap data (aggregate per second)
        heatmap = self._build_heatmap(timeline, duration)

        # AI interpretation
        interpretation = self._generate_interpretation(
            total_weapons, total_persons, max_threat_level,
            avg_confidence, weapon_frames, processed_count, frame_snapshots,
            fighting_frames, max_fighting_group
        )

        return {
            'output_video': f"/static/uploads/processed/{basename}_detected.mp4",
            'output_video_fs': output_path,
            'total_frames': total_frames,
            'processed_frames': processed_count,
            'fps': round(fps, 1),
            'duration': round(duration, 2),
            'width': width,
            'height': height,
            'total_weapons_detected': total_weapons,
            'total_persons_detected': total_persons,
            'weapon_frames': weapon_frames,
            'fighting_frames': fighting_frames,
            'max_fighting_group': max_fighting_group,
            'max_threat_level': max_threat_level,
            'avg_confidence': round(avg_confidence, 3),
            'avg_processing_fps': round(avg_fps, 1),
            'avg_inference_ms': round(avg_processing_time * 1000, 1),
            'timeline': timeline,
            'heatmap': heatmap,
            'frame_snapshots': frame_snapshots,
            'all_detections': all_detections,
            'interpretation': interpretation,
        }

    def _reencode_h264(self, video_path):
        """Re-encode video to H.264 using ffmpeg for browser compatibility."""
        if not shutil.which('ffmpeg'):
            print("[!] ffmpeg not found, skipping re-encode. Video may not play in browser.")
            return video_path

        h264_path = video_path.replace('.mp4', '_h264.mp4')
        try:
            subprocess.run([
                'ffmpeg', '-y', '-i', video_path,
                '-c:v', 'libx264', '-preset', 'fast',
                '-crf', '23', '-movflags', '+faststart',
                '-pix_fmt', 'yuv420p',
                h264_path,
            ], capture_output=True, timeout=300)

            if os.path.exists(h264_path) and os.path.getsize(h264_path) > 0:
                os.replace(h264_path, video_path)
                print(f"[+] Re-encoded to H.264: {video_path}")
            else:
                print("[!] ffmpeg re-encode produced empty file, keeping original.")
        except Exception as e:
            print(f"[!] ffmpeg re-encode failed: {e}")
            if os.path.exists(h264_path):
                os.remove(h264_path)

        return video_path

    def process_image(self, image_path):
        """Process a single image for weapon detection."""
        image_path = str(image_path)
        frame = cv2.imread(image_path)
        if frame is None:
            raise ValueError(f"Could not read image: {image_path}")

        result = self.detector.detect(frame)

        # Save annotated image
        basename = Path(image_path).stem
        output_name = f"{basename}_detected.jpg"
        output_path = str(self.processed_dir / output_name)
        cv2.imwrite(output_path, result['annotated_frame'])

        threat = result['threat']
        weapon_detections = [d for d in result['detections'] if d['type'] == 'weapon']
        avg_conf = np.mean([d['confidence'] for d in weapon_detections]) if weapon_detections else 0

        fighting_detected = result.get('fighting_detected', False)
        fighting_group = threat.get('fighting_group_size', 0) if fighting_detected else 0
        interpretation = self._generate_interpretation(
            result['weapon_count'], result['person_count'],
            threat['level'], avg_conf, 1 if result['weapon_count'] > 0 else 0,
            1, [],
            fighting_frames=1 if fighting_detected else 0,
            max_fighting_group=fighting_group,
        )

        return {
            'output_image': f"/static/uploads/processed/{output_name}",
            'output_image_fs': output_path,
            'detections': [{
                'label': d['label'],
                'confidence': round(d['confidence'], 3),
                'bbox': d['bbox'],
                'type': d['type'],
            } for d in result['detections']],
            'threat': threat,
            'weapon_count': result['weapon_count'],
            'person_count': result['person_count'],
            'inference_time_ms': round(result['inference_time'] * 1000, 1),
            'avg_confidence': round(avg_conf, 3),
            'interpretation': interpretation,
        }

    def _build_heatmap(self, timeline, duration):
        """Build second-by-second heatmap from timeline data."""
        if not timeline:
            return []

        max_second = int(duration) + 1
        heatmap = []

        # Group timeline by second
        second_data = {}
        for entry in timeline:
            s = entry['second']
            if s not in second_data:
                second_data[s] = {'weapons': 0, 'max_score': 0, 'threat': 'SAFE'}
            second_data[s]['weapons'] = max(second_data[s]['weapons'], entry['weapon_count'])
            second_data[s]['max_score'] = max(second_data[s]['max_score'], entry['score'])
            threat_priority = {'SAFE': 0, 'LOW': 1, 'MEDIUM': 2, 'HIGH': 3}
            if threat_priority.get(entry['threat_level'], 0) > threat_priority.get(second_data[s]['threat'], 0):
                second_data[s]['threat'] = entry['threat_level']

        for s in range(max_second):
            data = second_data.get(s, {'weapons': 0, 'max_score': 0, 'threat': 'SAFE'})
            heatmap.append({
                'second': s,
                'weapons': data['weapons'],
                'score': data['max_score'],
                'threat': data['threat'],
            })

        return heatmap

    def _generate_interpretation(self, total_weapons, total_persons,
                                  max_threat, avg_confidence, weapon_frames,
                                  total_frames, snapshots,
                                  fighting_frames=0, max_fighting_group=0):
        """Generate AI interpretation text."""
        messages = []

        if total_weapons == 0 and fighting_frames == 0:
            messages.append("No weapons were detected in the analyzed content.")
            messages.append("The scene appears to be safe with no visible threats.")
            return {
                'summary': 'No threats detected',
                'messages': messages,
                'recommendations': ['No action required'],
            }

        # Fighting detection messages
        if fighting_frames > 0:
            messages.append(
                f"GROUP FIGHT DETECTED: {fighting_frames} frame(s) show a group of "
                f"{max_fighting_group} or more members in close proximity — potential fighting activity."
            )

        # Weapon messages
        if total_weapons > 0:
            if total_weapons >= 5:
                messages.append(f"CRITICAL: {total_weapons} weapon instances detected across {weapon_frames} frames.")
            elif total_weapons >= 2:
                messages.append(f"Multiple weapon instances ({total_weapons}) detected in {weapon_frames} frames.")
            else:
                messages.append(f"Weapon detected in {weapon_frames} frame(s).")

        if total_persons > 0 and total_weapons > 0:
            messages.append(f"{total_persons} person(s) identified in proximity to detected weapons.")

        if avg_confidence > 0.8:
            messages.append(f"High detection confidence ({avg_confidence:.0%}) indicates clear weapon visibility.")
        elif avg_confidence > 0.5:
            messages.append(f"Moderate detection confidence ({avg_confidence:.0%}).")
        elif avg_confidence > 0:
            messages.append(f"Low detection confidence ({avg_confidence:.0%}) - results may need manual review.")

        # Weapon density
        if total_frames > 0 and total_weapons > 0:
            density = weapon_frames / total_frames
            if density > 0.5:
                messages.append("Weapons are visible in majority of analyzed frames - sustained threat.")
            elif density > 0.2:
                messages.append("Weapons appear in multiple segments of the content.")
            elif density > 0:
                messages.append("Weapon appearance is brief/isolated.")

        # Recommendations
        recommendations = []
        if fighting_frames > 0 and total_weapons > 0:
            recommendations = [
                'URGENT: Armed group fight detected — dispatch security immediately',
                'Alert security personnel',
                'Preserve evidence for analysis',
                'Cross-reference with suspect database',
            ]
        elif fighting_frames > 0:
            recommendations = [
                'Group fight detected — alert security personnel',
                'Review flagged frames for further evidence',
                'Monitor situation for escalation',
            ]
        elif max_threat == 'HIGH':
            recommendations = [
                'Immediate review recommended',
                'Alert security personnel',
                'Cross-reference with suspect database',
                'Preserve evidence for analysis',
            ]
        elif max_threat == 'MEDIUM':
            recommendations = [
                'Review flagged frames carefully',
                'Verify detection accuracy with manual check',
                'Monitor for escalation',
            ]
        else:
            recommendations = [
                'Low-priority review suggested',
                'Verify if detection is a false positive',
            ]

        summary_parts = []
        if fighting_frames > 0:
            summary_parts.append(f"GROUP FIGHT ({max_fighting_group} members) detected in {fighting_frames} frame(s)")
        if total_weapons > 0:
            summary_parts.append(f"{max_threat} threat — {total_weapons} weapon(s) detected")

        return {
            'summary': ' | '.join(summary_parts) if summary_parts else 'Analysis complete',
            'messages': messages,
            'recommendations': recommendations,
            'fighting_frames': fighting_frames,
            'max_fighting_group': max_fighting_group,
        }
