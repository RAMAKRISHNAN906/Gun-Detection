"""
AI Weapon Detection Module
Uses YOLOv8 for detecting weapons (guns, pistols, rifles, revolvers)
and persons holding weapons in images and video frames.
"""

import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO
import time
import re


# Weapon class labels for custom model
WEAPON_CLASSES = {
    0: 'gun',
    1: 'pistol',
    2: 'rifle',
    3: 'revolver',
    4: 'knife',
}

# COCO classes relevant to threat detection
COCO_PERSON_CLASS = 0
COCO_RELEVANT = {0: 'person'}

# Threat level thresholds
THREAT_LEVELS = {
    'HIGH': {'min_weapons': 2, 'min_confidence': 0.7, 'color': (0, 0, 255)},
    'MEDIUM': {'min_weapons': 1, 'min_confidence': 0.5, 'color': (0, 165, 255)},
    'LOW': {'min_weapons': 1, 'min_confidence': 0.3, 'color': (0, 255, 255)},
    'SAFE': {'min_weapons': 0, 'min_confidence': 0.0, 'color': (0, 255, 0)},
}

# Colors for bounding boxes
COLORS = {
    'gun': (0, 0, 255),
    'pistol': (0, 50, 255),
    'rifle': (0, 0, 200),
    'revolver': (50, 0, 255),
    'knife': (0, 100, 255),
    'person': (255, 165, 0),
    'default': (0, 255, 255),
}


class WeaponDetector:
    """YOLOv8-based weapon detection engine."""

    def __init__(self, model_path=None, confidence_threshold=0.25):
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.person_model = None  # COCO model for person detection
        self.model_type = None  # 'custom' or 'coco'
        self.custom_classes = {}  # Read from model
        self.active_custom_class_ids = set()
        self._load_model(model_path)

    def _load_model(self, model_path=None):
        """Load YOLOv8 model - custom weapon model or fallback to COCO."""
        models_dir = Path(__file__).parent / 'models'
        models_dir.mkdir(exist_ok=True)

        custom_loaded = False

        # Priority 1: User-specified model path
        if model_path and Path(model_path).exists():
            self.model = YOLO(str(model_path))
            self.model_type = 'custom'
            custom_loaded = True
            self.custom_classes = self.model.names
            self.active_custom_class_ids = self._find_supported_class_ids(self.custom_classes)
            supported = [self.custom_classes[i] for i in sorted(self.active_custom_class_ids)]
            print(f"[+] Loaded custom weapon model: {model_path}")
            print(f"[+] Active classes: {supported}")

        # Priority 2: Look for custom weapon model in models directory
        if not custom_loaded:
            custom_paths = [
                models_dir / 'weapon_best_videos.pt',
                models_dir / 'weapon_yolov8.pt',
                models_dir / 'weapon_best.pt',
                models_dir / 'best.pt',
                models_dir / 'threat' / 'weights' / 'best.pt',
                models_dir / 'firearm' / 'weights' / 'best.pt',
            ]
            best_path, best_names = self._pick_best_custom_model(custom_paths)
            if best_path is not None:
                self.model = YOLO(str(best_path))
                self.model_type = 'custom'
                custom_loaded = True
                self.custom_classes = best_names
                self.active_custom_class_ids = self._find_supported_class_ids(self.custom_classes)
                supported = [self.custom_classes[i] for i in sorted(self.active_custom_class_ids)]
                print(f"[+] Loaded custom weapon model: {best_path}")
                print(f"[+] Active classes: {supported}")

        if custom_loaded:
            if not self.active_custom_class_ids:
                print("[!] Custom model has no recognized gun/knife classes; using all model classes as weapons.")
                self.active_custom_class_ids = set(self.custom_classes.keys())
            # Also load COCO model for person detection
            print("[*] Loading COCO model for person detection...")
            self.person_model = YOLO('yolov8n.pt')
            print("[+] Person detection model ready.")
        else:
            # Priority 3: Use YOLOv8n (COCO) as fallback
            print("[*] No custom weapon model found. Using YOLOv8n COCO model.")
            print("[*] Place your trained model as 'models/weapon_best.pt' for best results.")
            self.model = YOLO('yolov8n.pt')
            self.model_type = 'coco'

    def _normalize_label(self, label):
        text = str(label).strip().lower()
        text = re.sub(r'[^a-z0-9]+', ' ', text).strip()

        if 'knife' in text or 'blade' in text or 'dagger' in text:
            return 'knife'
        if 'revolver' in text:
            return 'revolver'
        if 'pistol' in text or 'handgun' in text:
            return 'pistol'
        if 'rifle' in text or 'shotgun' in text or 'carbine' in text or 'ak' in text:
            return 'rifle'
        if 'gun' in text or 'firearm' in text or 'weapon' in text:
            return 'gun'
        return text.replace(' ', '_')

    def _find_supported_class_ids(self, names):
        allowed = {'gun', 'pistol', 'rifle', 'revolver', 'knife'}
        supported = set()
        if isinstance(names, dict):
            iterator = names.items()
        else:
            iterator = enumerate(names)

        for class_id, raw_name in iterator:
            if self._normalize_label(raw_name) in allowed:
                supported.add(int(class_id))
        return supported

    def _pick_best_custom_model(self, custom_paths):
        best_score = -1
        best_path = None
        best_names = {}

        for p in custom_paths:
            if not p.exists():
                continue

            try:
                candidate = YOLO(str(p))
                names = candidate.names
                supported_ids = self._find_supported_class_ids(names)
                if isinstance(names, dict):
                    name_values = names.values()
                else:
                    name_values = names
                normalized = {self._normalize_label(v) for v in name_values}

                # Prefer broader weapon coverage and especially knife support.
                score = len(supported_ids)
                if 'knife' in normalized:
                    score += 2

                if score > best_score:
                    best_score = score
                    best_path = p
                    best_names = names
            except Exception as exc:
                print(f"[!] Failed loading candidate model {p}: {exc}")

        return best_path, best_names

    def detect(self, frame):
        """
        Run weapon detection on a single frame.
        Returns list of detection dicts and annotated frame.
        """
        start_time = time.time()
        detections = []
        annotated = frame.copy()

        results = self.model(frame, conf=self.confidence_threshold, verbose=False)

        if self.model_type == 'custom':
            detections = self._process_custom_results(results, annotated)
            # Also detect persons using COCO model
            if self.person_model:
                person_results = self.person_model(frame, conf=0.3, classes=[0], verbose=False)
                detections += self._process_person_results(person_results, annotated)
        else:
            detections = self._process_coco_results(results, annotated)

        inference_time = time.time() - start_time

        # Calculate threat assessment
        threat = self._assess_threat(detections)

        # Check for group fighting
        fighting = self._detect_group_fighting(detections)
        if fighting['detected']:
            threat['fighting'] = True
            threat['fighting_message'] = fighting['message']
            threat['fighting_group_size'] = fighting['group_size']
            # Escalate threat level if currently safe
            if threat['level'] == 'SAFE':
                threat['level'] = 'MEDIUM'
                threat['color'] = '#ff8800'
                threat['message'] = fighting['message']

        # Draw threat banner on frame
        self._draw_threat_banner(annotated, threat, detections)

        return {
            'detections': detections,
            'annotated_frame': annotated,
            'threat': threat,
            'inference_time': inference_time,
            'weapon_count': sum(1 for d in detections if d['type'] == 'weapon'),
            'person_count': sum(1 for d in detections if d['type'] == 'person'),
            'fighting_detected': fighting['detected'],
        }

    def _process_custom_results(self, results, frame):
        """Process results from custom weapon-trained model."""
        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                confidence = float(box.conf[0])
                class_id = int(box.cls[0])
                if self.active_custom_class_ids and class_id not in self.active_custom_class_ids:
                    continue

                # Read label from model's class names and normalize to expected weapon labels
                raw_label = self.custom_classes.get(class_id, f'weapon_{class_id}')
                label = self._normalize_label(raw_label)

                detection = {
                    'bbox': [x1, y1, x2, y2],
                    'confidence': confidence,
                    'label': label,
                    'class_id': class_id,
                    'type': 'weapon',
                }
                detections.append(detection)

                color = COLORS.get(label, COLORS['gun'])
                self._draw_detection(frame, detection, color)

        return detections

    def _process_person_results(self, results, frame):
        """Process COCO person-only results."""
        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                confidence = float(box.conf[0])
                detection = {
                    'bbox': [x1, y1, x2, y2],
                    'confidence': confidence,
                    'label': 'person',
                    'class_id': 0,
                    'type': 'person',
                }
                detections.append(detection)
                self._draw_detection(frame, detection, COLORS['person'])
        return detections

    def _process_coco_results(self, results, frame):
        """
        Process COCO model results.
        Detects persons and objects that could indicate threats.
        COCO relevant classes for weapon-adjacent detection:
          0=person, 43=knife, 76=scissors
        """
        detections = []
        # Extended COCO classes that may relate to weapons/threats
        weapon_adjacent = {43: 'knife', 76: 'scissors'}
        person_boxes = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                confidence = float(box.conf[0])
                class_id = int(box.cls[0])

                if class_id == COCO_PERSON_CLASS:
                    detection = {
                        'bbox': [x1, y1, x2, y2],
                        'confidence': confidence,
                        'label': 'person',
                        'class_id': class_id,
                        'type': 'person',
                    }
                    detections.append(detection)
                    person_boxes.append([x1, y1, x2, y2])
                    self._draw_detection(frame, detection, COLORS['person'])

                elif class_id in weapon_adjacent:
                    label = weapon_adjacent[class_id]
                    detection = {
                        'bbox': [x1, y1, x2, y2],
                        'confidence': confidence,
                        'label': label,
                        'class_id': class_id,
                        'type': 'weapon',
                    }
                    detections.append(detection)
                    self._draw_detection(frame, detection, COLORS.get(label, COLORS['default']))

        return detections

    def _draw_detection(self, frame, detection, color):
        """Draw bounding box and label on frame."""
        x1, y1, x2, y2 = detection['bbox']
        confidence = detection['confidence']
        label = detection['label']

        # Draw bounding box with thickness based on confidence
        thickness = max(2, int(confidence * 4))
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

        # Draw corner accents for futuristic look
        corner_len = min(30, (x2 - x1) // 4, (y2 - y1) // 4)
        accent_color = tuple(min(255, c + 50) for c in color)

        # Top-left corner
        cv2.line(frame, (x1, y1), (x1 + corner_len, y1), accent_color, thickness + 1)
        cv2.line(frame, (x1, y1), (x1, y1 + corner_len), accent_color, thickness + 1)
        # Top-right corner
        cv2.line(frame, (x2, y1), (x2 - corner_len, y1), accent_color, thickness + 1)
        cv2.line(frame, (x2, y1), (x2, y1 + corner_len), accent_color, thickness + 1)
        # Bottom-left corner
        cv2.line(frame, (x1, y2), (x1 + corner_len, y2), accent_color, thickness + 1)
        cv2.line(frame, (x1, y2), (x1, y2 - corner_len), accent_color, thickness + 1)
        # Bottom-right corner
        cv2.line(frame, (x2, y2), (x2 - corner_len, y2), accent_color, thickness + 1)
        cv2.line(frame, (x2, y2), (x2, y2 - corner_len), accent_color, thickness + 1)

        # Draw label background
        text = f"{label.upper()} {confidence:.0%}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 10, y1), color, -1)
        cv2.putText(frame, text, (x1 + 5, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    def _assess_threat(self, detections):
        """Assess threat level based on detections."""
        weapon_detections = [d for d in detections if d['type'] == 'weapon']
        person_detections = [d for d in detections if d['type'] == 'person']
        weapon_count = len(weapon_detections)

        if weapon_count == 0:
            return {
                'level': 'SAFE',
                'color': '#00ff00',
                'score': 0,
                'message': 'No weapons detected',
                'details': [],
            }

        max_conf = max(d['confidence'] for d in weapon_detections) if weapon_detections else 0
        avg_conf = np.mean([d['confidence'] for d in weapon_detections]) if weapon_detections else 0

        details = []
        # Generate AI interpretation messages
        for wd in weapon_detections:
            wx1, wy1, wx2, wy2 = wd['bbox']
            wcx, wcy = (wx1 + wx2) // 2, (wy1 + wy2) // 2

            # Check proximity to persons
            for pd in person_detections:
                px1, py1, px2, py2 = pd['bbox']
                if (px1 <= wcx <= px2 and py1 <= wcy <= py2):
                    details.append(f"Weapon ({wd['label']}) detected on person - confidence {wd['confidence']:.0%}")
                    break
                elif self._boxes_overlap(wd['bbox'], pd['bbox']):
                    details.append(f"Weapon ({wd['label']}) detected near person - confidence {wd['confidence']:.0%}")
                    break
            else:
                side = "left" if wcx < wd['bbox'][2] * 0.5 else "right"
                details.append(f"{wd['label'].capitalize()} detected on {side} side - confidence {wd['confidence']:.0%}")

        if weapon_count >= 2 and max_conf >= 0.6:
            details.insert(0, "CRITICAL: Multiple weapons detected in scene")

        # Determine threat level
        if weapon_count >= 2 or max_conf >= 0.7:
            level = 'HIGH'
            color = '#ff0040'
            score = min(100, int(avg_conf * 100) + weapon_count * 15)
        elif max_conf >= 0.5:
            level = 'MEDIUM'
            color = '#ff8800'
            score = int(avg_conf * 80)
        else:
            level = 'LOW'
            color = '#ffcc00'
            score = int(avg_conf * 50)

        return {
            'level': level,
            'color': color,
            'score': score,
            'message': f"WEAPON DETECTED: {level} RISK",
            'details': details,
            'weapon_count': weapon_count,
            'person_count': len(person_detections),
            'max_confidence': max_conf,
            'avg_confidence': avg_conf,
        }

    def _detect_group_fighting(self, detections, min_group=3, proximity_factor=1.5):
        """
        Detect if a group of people are clustered together (fighting scenario).

        Args:
            detections: list of detection dicts
            min_group: minimum number of persons to trigger alert (default 3)
            proximity_factor: boxes whose expanded versions overlap are considered close

        Returns:
            dict with 'detected', 'message', 'group_size'
        """
        person_boxes = [d['bbox'] for d in detections if d['type'] == 'person']

        if len(person_boxes) < min_group:
            return {'detected': False, 'message': '', 'group_size': len(person_boxes)}

        # Find the largest cluster of overlapping/nearby persons
        def expanded_box(box, factor):
            x1, y1, x2, y2 = box
            w = x2 - x1
            h = y2 - y1
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            nw, nh = w * factor / 2, h * factor / 2
            return [int(cx - nw), int(cy - nh), int(cx + nw), int(cy + nh)]

        def boxes_close(b1, b2):
            eb1 = expanded_box(b1, proximity_factor)
            eb2 = expanded_box(b2, proximity_factor)
            return not (eb1[2] < eb2[0] or eb2[2] < eb1[0] or
                        eb1[3] < eb2[1] or eb2[3] < eb1[1])

        # Union-Find to group close persons
        parent = list(range(len(person_boxes)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i, j):
            pi, pj = find(i), find(j)
            if pi != pj:
                parent[pi] = pj

        for i in range(len(person_boxes)):
            for j in range(i + 1, len(person_boxes)):
                if boxes_close(person_boxes[i], person_boxes[j]):
                    union(i, j)

        # Count cluster sizes
        from collections import Counter
        cluster_sizes = Counter(find(i) for i in range(len(person_boxes)))
        max_cluster = max(cluster_sizes.values())

        if max_cluster >= min_group:
            return {
                'detected': True,
                'message': f'ALERT: MEMBERS ARE FIGHTING ({max_cluster} persons)',
                'group_size': max_cluster,
            }

        return {'detected': False, 'message': '', 'group_size': len(person_boxes)}

    def _boxes_overlap(self, box1, box2, threshold=0.1):
        """Check if two bounding boxes overlap."""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        if x1 >= x2 or y1 >= y2:
            return False

        intersection = (x2 - x1) * (y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        min_area = min(area1, area2)

        return (intersection / max(min_area, 1)) > threshold

    def _draw_threat_banner(self, frame, threat, detections):
        """Draw threat level banner on frame."""
        h, w = frame.shape[:2]
        level = threat['level']
        fighting = threat.get('fighting', False)

        if level == 'SAFE' and not fighting:
            banner_color = (0, 180, 0)
            text = "SAFE - No Weapons Detected"
        elif fighting and level == 'SAFE':
            banner_color = (0, 100, 255)  # orange-red for fighting
            text = threat.get('fighting_message', 'ALERT: MEMBERS ARE FIGHTING')
        else:
            banner_color = THREAT_LEVELS.get(level, THREAT_LEVELS['MEDIUM'])['color']
            text = f"WARNING: {threat['message']}"

        # Semi-transparent banner
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 40), banner_color, -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        cv2.putText(frame, text, (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Fighting alert — draw a second banner below the main one
        if fighting:
            fight_color = (0, 60, 220)
            fight_text = threat.get('fighting_message', 'MEMBERS ARE FIGHTING')
            if level != 'SAFE':
                # Draw extra banner below main
                fight_overlay = frame.copy()
                cv2.rectangle(fight_overlay, (0, 40), (w, 80), fight_color, -1)
                cv2.addWeighted(fight_overlay, 0.75, frame, 0.25, 0, frame)
                cv2.putText(frame, fight_text, (10, 68),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Stats on right side
        stats = f"Detections: {len(detections)}"
        (sw, _), _ = cv2.getTextSize(stats, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.putText(frame, stats, (w - sw - 10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    def detect_image(self, image_path):
        """Detect weapons in a single image file."""
        frame = cv2.imread(str(image_path))
        if frame is None:
            raise ValueError(f"Could not read image: {image_path}")
        return self.detect(frame)
