"""
Simple Zone Editor - Single Window for Testing
Press R to draw rectangles, works immediately!
"""

import cv2
import numpy as np
import json
import os

# State variables
zones = []
mode = "normal"
drawing_points = []
rect_start = None
rect_dragging = False
mouse_pos = (0, 0)

ZONE_FILE = "zones/zones_test.json"

def load_zones():
    global zones
    if os.path.exists(ZONE_FILE):
        with open(ZONE_FILE, 'r') as f:
            data = json.load(f)
            zones = data.get("zones", [])
            print(f"✅ Loaded {len(zones)} zones")
    else:
        zones = []
        print("📝 Starting with empty zones")

def save_zones():
    os.makedirs(os.path.dirname(ZONE_FILE), exist_ok=True)
    with open(ZONE_FILE, 'w') as f:
        json.dump({"zones": zones}, f, indent=2)
    print(f"💾 Saved {len(zones)} zones to {ZONE_FILE}")

def mouse_callback(event, x, y, flags, param):
    global mode, drawing_points, rect_start, rect_dragging, mouse_pos, zones
    
    mouse_pos = (x, y)
    
    if event == cv2.EVENT_LBUTTONDOWN:
        if mode == 'draw_rect':
            rect_start = (x, y)
            rect_dragging = True
            print(f"🎯 Rectangle start: ({x}, {y})")
    
    elif event == cv2.EVENT_LBUTTONUP:
        if mode == 'draw_rect' and rect_dragging and rect_start:
            x1, y1 = rect_start
            x2, y2 = x, y
            
            # Create rectangle zone
            new_zone = {
                "id": len(zones) + 1,
                "points": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
            }
            zones.append(new_zone)
            save_zones()
            
            print(f"✅ Rectangle zone SAVED! ({x1},{y1}) to ({x2},{y2}). Total: {len(zones)}")
            
            rect_start = None
            rect_dragging = False
            mode = 'normal'

def main():
    global mode, rect_start, rect_dragging
    
    print("🎯 Simple Zone Editor Starting...")
    
    # Load existing zones
    load_zones()
    
    # Open video - use webcam (0) for testing
    print(f"📹 Opening webcam (camera 0)...")
    
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("❌ Failed to open webcam, trying sample video...")
        # Fallback to any available video
        cap = cv2.VideoCapture("sample.mp4")
        
    if not cap.isOpened():
        print("❌ No video source available")
        print("💡 TIP: Place a video file named 'sample.mp4' in the current directory")
        return
    
    # Create window
    window_name = "🎨 Zone Editor - Press R to draw rectangles"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 720)
    cv2.setMouseCallback(window_name, mouse_callback)
    
    print("\n" + "="*60)
    print("✅ ZONE EDITOR READY!")
    print("="*60)
    print("\n🖱️  CONTROLS:")
    print("   R - Start drawing rectangle (click & drag)")
    print("   D - Delete last zone")
    print("   S - Save zones manually")
    print("   Q - Quit")
    print("\n" + "="*60 + "\n")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("⚠️ No frame, restarting video...")
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        
        # Resize for display
        display = cv2.resize(frame, (1280, 720))
        
        # Draw existing zones
        for zone in zones:
            pts = np.array(zone["points"], np.int32)
            pts = pts.reshape((-1, 1, 2))
            
            # Green transparent fill
            overlay = display.copy()
            cv2.fillPoly(overlay, [pts], (0, 255, 0))
            cv2.addWeighted(overlay, 0.2, display, 0.8, 0, display)
            
            # Green border
            cv2.polylines(display, [pts], True, (0, 255, 0), 3)
            
            # Zone label
            zone_id = zone.get("id", "?")
            M = cv2.moments(pts)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                cv2.putText(display, f"Zone {zone_id}", (cx - 40, cy),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        # Draw rectangle preview while dragging
        if mode == "draw_rect" and rect_dragging and rect_start:
            x1, y1 = rect_start
            x2, y2 = mouse_pos
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), 4)
            cv2.putText(display, "Drawing Rectangle...", (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        # HUD
        cv2.putText(display, f"Zones: {len(zones)}", (20, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        if mode != "normal":
            cv2.putText(display, f"MODE: {mode.upper()}", (20, 80), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        # Instructions
        instructions = [
            "R - Rectangle | D - Delete | S - Save | Q - Quit"
        ]
        for i, text in enumerate(instructions):
            cv2.putText(display, text, (20, 720 - 40 + i * 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        cv2.imshow(window_name, display)
        
        # Keyboard
        key = cv2.waitKey(20) & 0xFF
        
        if key == ord('q'):
            print("👋 Quitting...")
            break
        elif key == ord('r'):
            mode = 'draw_rect'
            rect_start = None
            rect_dragging = False
            print("🟥 MODE: DRAW RECTANGLE - Click and drag!")
        elif key == ord('d'):
            if zones:
                deleted = zones.pop()
                save_zones()
                print(f"🗑️ Deleted zone {deleted.get('id')}. Remaining: {len(zones)}")
            else:
                print("⚠️ No zones to delete")
        elif key == ord('s'):
            save_zones()
    
    cap.release()
    cv2.destroyAllWindows()
    print("🏁 Zone editor stopped")

if __name__ == '__main__':
    main()
