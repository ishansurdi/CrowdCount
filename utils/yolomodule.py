"""
CrowdCount – Milestone 2 (MULTI-AREA FIXED)
Author: Ishan Rahul Surdi
Fixed: Each area now has independent tracking, zones, and counting
"""

import cv2
import os
import json
import time
import math
import datetime
from ultralytics import YOLO
import numpy as np
from collections import defaultdict

# ================================
# CONFIG
# ================================
MODE = "webcam"
IMAGE_FOLDER = "images"
VIDEO_PATH = "demo_video.mp4"
MODEL_PATH = "models/yolov8n.pt"

# ================================
# MULTI-AREA STATE MANAGEMENT
# ================================
class AreaTracker:
    """Independent tracker for each area"""
    def __init__(self, zone_file):
        self.zone_file = zone_file
        self.zones = self.load_zones(zone_file)
        self.tracker = ByteTrack(track_thresh=0.5, track_buffer=30, match_thresh=0.7)
        self.zone_counts = {z["id"]: 0 for z in self.zones}
        self.track_zone_memory = {}
        
    def load_zones(self, path):
        """Load zones from file"""
        if not os.path.exists(path):
            print(f"⚠️  {path} not found. Initializing empty zones.")
            return []

        try:
            with open(path, "r") as f:
                content = f.read().strip()
                if content == "":
                    print(f"⚠️  {path} is EMPTY. Initializing with zero zones.")
                    return []

                data = json.loads(content)
                
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get("zones", [])
                else:
                    print(f"⚠️  Unexpected zone file format in {path}. Returning empty zones.")
                    return []

        except json.JSONDecodeError:
            print(f"❌ {path} is CORRUPTED. Resetting zones.")
            return []
    
    def reload_zones(self):
        """Reload zones from file"""
        self.zones = self.load_zones(self.zone_file)
        self.zone_counts = {z["id"]: 0 for z in self.zones}
        self.track_zone_memory = {}
        print(f"✅ Reloaded {len(self.zones)} zones from {self.zone_file}")

# Global registry of area trackers
area_trackers = {}
current_area = None

def get_area_tracker(zone_file):
    """Get or create tracker for specific area"""
    global area_trackers
    if zone_file not in area_trackers:
        area_trackers[zone_file] = AreaTracker(zone_file)
        print(f"🎯 Created new tracker for {zone_file}")
    return area_trackers[zone_file]

# ================================
# POINT IN POLYGON
# ================================
def point_in_zone(point, zone):
    pts = np.array(zone["points"], dtype=np.int32)
    return cv2.pointPolygonTest(pts, (int(point[0]), int(point[1])), False) >= 0

# ================================
# BYTETRACK TRACKER
# ================================
class KalmanFilter:
    """Simple Kalman filter for tracking bounding box center and scale."""
    def __init__(self):
        self.mean = np.zeros(7)
        self.covariance = np.eye(7)
        
        self.motion_mat = np.eye(7)
        self.motion_mat[0, 4] = 1
        self.motion_mat[1, 5] = 1
        self.motion_mat[2, 6] = 1
        
        self.update_mat = np.eye(4, 7)
        
        self.std_weight_position = 1. / 20
        self.std_weight_velocity = 1. / 160
        
    def initiate(self, bbox):
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        w = x2 - x1
        h = y2 - y1
        s = w * h
        r = w / max(h, 1e-6)
        
        self.mean = np.array([cx, cy, s, r, 0, 0, 0])
        
        std = [
            2 * self.std_weight_position * s ** 0.5,
            2 * self.std_weight_position * s ** 0.5,
            1e-2,
            2 * self.std_weight_position * s ** 0.5,
            10 * self.std_weight_velocity * s ** 0.5,
            10 * self.std_weight_velocity * s ** 0.5,
            1e-5
        ]
        self.covariance = np.diag(np.square(std))
        
    def predict(self):
        std_pos = [
            self.std_weight_position * self.mean[2] ** 0.5,
            self.std_weight_position * self.mean[2] ** 0.5,
            1e-2,
            self.std_weight_position * self.mean[2] ** 0.5
        ]
        std_vel = [
            self.std_weight_velocity * self.mean[2] ** 0.5,
            self.std_weight_velocity * self.mean[2] ** 0.5,
            1e-5
        ]
        motion_cov = np.diag(np.square(np.r_[std_pos, std_vel]))
        
        self.mean = np.dot(self.motion_mat, self.mean)
        self.covariance = np.linalg.multi_dot((
            self.motion_mat, self.covariance, self.motion_mat.T)) + motion_cov
            
    def update(self, bbox):
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        w = x2 - x1
        h = y2 - y1
        s = w * h
        r = w / max(h, 1e-6)
        
        measurement = np.array([cx, cy, s, r])
        
        std = [
            self.std_weight_position * self.mean[2] ** 0.5,
            self.std_weight_position * self.mean[2] ** 0.5,
            1e-1,
            self.std_weight_position * self.mean[2] ** 0.5
        ]
        innovation_cov = np.diag(np.square(std))
        
        projected_mean = np.dot(self.update_mat, self.mean)
        projected_cov = np.linalg.multi_dot((
            self.update_mat, self.covariance, self.update_mat.T)) + innovation_cov
            
        kalman_gain = np.linalg.multi_dot((
            self.covariance, self.update_mat.T, np.linalg.inv(projected_cov)))
            
        innovation = measurement - projected_mean
        self.mean = self.mean + np.dot(kalman_gain, innovation)
        self.covariance = self.covariance - np.linalg.multi_dot((
            kalman_gain, self.update_mat, self.covariance))
    
    def get_bbox(self):
        cx, cy, s, r = self.mean[:4]
        w = (s * r) ** 0.5
        h = s / max(w, 1e-6)
        x1 = cx - w / 2
        y1 = cy - h / 2
        x2 = cx + w / 2
        y2 = cy + h / 2
        return [int(x1), int(y1), int(x2), int(y2)]


class ByteTrack:
    """ByteTrack tracking algorithm."""
    def __init__(self, track_thresh=0.5, track_buffer=30, match_thresh=0.8):
        self.track_thresh = track_thresh
        self.track_buffer = track_buffer
        self.match_thresh = match_thresh
        self.frame_id = 0
        self.tracks = []
        self.lost_tracks = []
        self.removed_tracks = []
        self.next_id = 1
        
    def update(self, detections, scores=None):
        self.frame_id += 1
        
        if scores is None:
            scores = [1.0] * len(detections)
        
        high_dets = []
        low_dets = []
        for det, score in zip(detections, scores):
            if score >= self.track_thresh:
                high_dets.append((det, score))
            else:
                low_dets.append((det, score))
        
        for track in self.tracks:
            track['kalman'].predict()
        
        matched, unmatched_tracks, unmatched_dets = self._match(
            self.tracks, high_dets)
        
        for track_idx, det_idx in matched:
            det, score = high_dets[det_idx]
            self.tracks[track_idx]['kalman'].update(det)
            self.tracks[track_idx]['bbox'] = det
            self.tracks[track_idx]['score'] = score
            self.tracks[track_idx]['age'] += 1
            self.tracks[track_idx]['missed'] = 0
        
        unmatched_tracks_obj = [self.tracks[i] for i in unmatched_tracks]
        matched2, unmatched_tracks2, unmatched_low = self._match(
            unmatched_tracks_obj, low_dets)
        
        for i, det_idx in matched2:
            track_idx = unmatched_tracks[i]
            det, score = low_dets[det_idx]
            self.tracks[track_idx]['kalman'].update(det)
            self.tracks[track_idx]['bbox'] = det
            self.tracks[track_idx]['score'] = score
            self.tracks[track_idx]['age'] += 1
            self.tracks[track_idx]['missed'] = 0
        
        for i in unmatched_tracks2:
            track_idx = unmatched_tracks[i]
            self.tracks[track_idx]['missed'] += 1
        
        for det_idx in unmatched_dets:
            det, score = high_dets[det_idx]
            kf = KalmanFilter()
            kf.initiate(det)
            track = {
                'id': self.next_id,
                'kalman': kf,
                'bbox': det,
                'score': score,
                'age': 1,
                'missed': 0
            }
            self.tracks.append(track)
            self.next_id += 1
        
        self.tracks = [t for t in self.tracks if t['missed'] < self.track_buffer]
        
        output = []
        for track in self.tracks:
            if track['missed'] == 0:
                bbox = track['bbox']
                cx = (bbox[0] + bbox[2]) / 2
                cy = (bbox[1] + bbox[3]) / 2
                output.append({
                    'id': track['id'],
                    'bbox': bbox,
                    'centroid': (cx, cy),
                    'score': track['score']
                })
        
        return output
    
    def _match(self, tracks, detections):
        if len(tracks) == 0 or len(detections) == 0:
            return [], list(range(len(tracks))), list(range(len(detections)))
        
        iou_matrix = np.zeros((len(tracks), len(detections)))
        for i, track in enumerate(tracks):
            track_bbox = track['kalman'].get_bbox()
            for j, (det_bbox, _) in enumerate(detections):
                iou_matrix[i, j] = self._iou(track_bbox, det_bbox)
        
        matched_indices = []
        unmatched_tracks = []
        unmatched_dets = list(range(len(detections)))
        
        track_indices = list(range(len(tracks)))
        while len(track_indices) > 0 and len(unmatched_dets) > 0:
            max_iou = 0
            best_t, best_d = -1, -1
            for t in track_indices:
                for d in unmatched_dets:
                    if iou_matrix[t, d] > max_iou:
                        max_iou = iou_matrix[t, d]
                        best_t, best_d = t, d
            
            if max_iou < self.match_thresh:
                break
                
            matched_indices.append((best_t, best_d))
            track_indices.remove(best_t)
            unmatched_dets.remove(best_d)
        
        unmatched_tracks = track_indices
        
        return matched_indices, unmatched_tracks, unmatched_dets
    
    def _iou(self, bbox1, bbox2):
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2
        
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)
        
        if x2_i < x1_i or y2_i < y1_i:
            return 0.0
        
        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection
        
        return intersection / max(union, 1e-6)


# ================================
# YOLO DETECTOR
# ================================
model = YOLO(MODEL_PATH)

def detect_people(frame):
    results = model.predict(frame, classes=[0], conf=0.5, imgsz=480, verbose=False)
    detections = []
    for r in results:
        for b in r.boxes:
            x1, y1, x2, y2 = map(int, b.xyxy[0])
            detections.append((x1, y1, x2, y2))
    return detections

# ================================
# EXPORTABLE API FOR main.py
# ================================

def week2_set_zone_file(zone_file_path):
    """Set the active zone file for the current area"""
    global current_area
    current_area = zone_file_path
    tracker = get_area_tracker(zone_file_path)
    print(f"🎯 Zone file set to: {zone_file_path} ({len(tracker.zones)} zones)")

def week2_get_zones():
    """Return loaded zones for current area"""
    if current_area is None:
        return []
    tracker = get_area_tracker(current_area)
    return tracker.zones

def week2_reload_zones():
    """Reload zones from file for current area"""
    if current_area is None:
        return
    tracker = get_area_tracker(current_area)
    tracker.reload_zones()

def week2_process_frame(frame):
    """Process frame with area-specific tracking and counting"""
    if current_area is None:
        print("⚠️ No area set! Call week2_set_zone_file() first")
        return frame, {}, 0
    
    tracker = get_area_tracker(current_area)
    
    # Detect people
    detections = detect_people(frame)
    
    # Update tracker
    tracks = tracker.tracker.update(detections)
    
    live_people_count = len(detections)
    
    # Reset zone counts (current occupancy)
    tracker.zone_counts = {z["id"]: 0 for z in tracker.zones}
    
    # Count people in zones
    for t in tracks:
        tid = t["id"]
        cx, cy = t["centroid"]
        
        # Count if person is currently in zone
        for z in tracker.zones:
            if point_in_zone((cx, cy), z):
                tracker.zone_counts[z["id"]] += 1
        
        # Draw bounding boxes and IDs
        x1, y1, x2, y2 = t["bbox"]
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
        cv2.putText(frame, f"ID {tid}", (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # Draw centroid
        cx_int, cy_int = int(cx), int(cy)
        cv2.circle(frame, (cx_int, cy_int), 5, (0, 0, 255), -1)
        cv2.circle(frame, (cx_int, cy_int), 8, (255, 255, 255), 2)
    
    return frame, tracker.zone_counts, live_people_count

def week2_reset_counts():
    """Reset all zone counts for current area"""
    if current_area is None:
        return
    tracker = get_area_tracker(current_area)
    tracker.zone_counts = {z["id"]: 0 for z in tracker.zones}
    tracker.track_zone_memory = {}