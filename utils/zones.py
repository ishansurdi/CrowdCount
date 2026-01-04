
"""
zones.py

Zone management module. Responsibilities:
- load_zones(path)
- save_zones(path, zones)
- draw_zones(frame, zones, selected_id=None, hover_id=None)
- add_zone(zones, points, name=None, color=None)
- edit_zone(zones, zone_id, points)
- delete_zone(zones, zone_id)
- point_in_zone(point, zone)

Zones data structure:
[ {"id": int, "name": str, "color": [B,G,R], "points": [[x,y], ...]}, ... ]
"""

import json
import os
import cv2
import numpy as np


def load_zones(path="zones.json"):
    if not os.path.exists(path):
        print("⚠ zones.json not found. Initializing empty zones.")
        return []

    try:
        with open(path, "r") as f:
            content = f.read().strip()

            if content == "":
                print("⚠ zones.json is EMPTY. Initializing zero zones.")
                return []

            data = json.loads(content)
            
            # Handle both formats: [] and {"zones": [...]}
            if isinstance(data, list):
                zones = data
            elif isinstance(data, dict):
                zones = data.get("zones", [])
            else:
                print("⚠ Unexpected zone file format. Returning empty zones.")
                return []

            # ensure integer coordinates
            for z in zones:
                z["points"] = [[int(p[0]), int(p[1])] for p in z.get("points", [])]

            return zones

    except json.JSONDecodeError:
        print("❌ zones.json is CORRUPTED. Resetting zones.")
        return []

    except Exception as e:
        print("❌ Unexpected zones.json error:", e)
        return []



def save_zones(path, zones):
    data = {"zones": zones}
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


def draw_zones(frame, zones, selected_id=None, hover_id=None, zone_counts=None):
    overlay = frame.copy()
    for z in zones:
        pts = np.array(z["points"], dtype=np.int32).reshape((-1, 1, 2))
        color = tuple(int(c) for c in z.get("color", (0, 255, 0)))
        thickness = 2
        
        # Get count for this zone
        count = zone_counts.get(z["id"], 0) if zone_counts else 0
        
        if selected_id == z["id"]:
            # highlighted
            cv2.polylines(overlay, [pts], True, (0, 255, 255), thickness=4)
            cv2.putText(overlay, f"{z['name']} (ID:{z['id']}) Count: {count}", (pts[0][0][0], max(15, pts[0][0][1]-10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        elif hover_id == z["id"]:
            cv2.polylines(overlay, [pts], True, (255, 255, 255), thickness=4)
            cv2.polylines(overlay, [pts], True, color, thickness=2)
            cv2.putText(overlay, f"{z['name']}: {count}", (pts[0][0][0], max(15, pts[0][0][1]-10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        else:
            cv2.polylines(overlay, [pts], True, color, thickness)
            cv2.putText(overlay, f"{z['name']}: {count}", (pts[0][0][0], max(15, pts[0][0][1]-10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    cv2.addWeighted(overlay, 0.9, frame, 0.1, 0, frame)
    return frame


def add_zone(zones, points, name=None, color=None):
    new_id = 1 if not zones else max(z['id'] for z in zones) + 1
    if name is None:
        name = f"Zone_{new_id}"
    if color is None:
        # default cycle colors
        palette = [(0,255,0),(255,0,0),(0,0,255),(0,255,255),(255,128,0)]
        color = palette[(new_id-1) % len(palette)]
    zone = {"id": new_id, "name": name, "color": [int(c) for c in color], "points": [[int(p[0]), int(p[1])] for p in points]}
    zones.append(zone)
    return zone


def edit_zone(zones, zone_id, new_points):
    for z in zones:
        if z['id'] == zone_id:
            z['points'] = [[int(p[0]), int(p[1])] for p in new_points]
            return True
    return False


def delete_zone(zones, zone_id):
    for i, z in enumerate(zones):
        if z['id'] == zone_id:
            del zones[i]
            return True
    return False


def point_in_zone(point, zone):
    pts = np.array(zone['points'], dtype=np.int32)
    return cv2.pointPolygonTest(pts, (int(point[0]), int(point[1])), False) >= 0
