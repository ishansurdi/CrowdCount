"""
Multi-Area CrowdCount System with Independent Zone Editors
Each area (Entrance, Retail, Food Court) has:
- Independent video window
- Zone drawing tools (rectangle/polygon)
- Real-time people counting
- Zone-specific metrics
- Backend dashboard integration
"""

import cv2
import datetime
import threading
import time
import numpy as np
from utils.camera_feed import open_camera, get_camera_frame, release_camera
import utils.zones as zone_mod
from utils.yolomodule import week2_process_frame, week2_set_zone_file, week2_reload_zones
import subprocess
import requests
import json
import os

# Backend integration
BACKEND_URL = "http://127.0.0.1:5000"
BACKEND_AVAILABLE = True
BACKEND_RETRY_TIME = 0  # Timestamp to retry backend after errors

# Thread lock for YOLO processing (prevents race conditions)
yolo_lock = threading.Lock()

# Zone sync tracking
zone_file_timestamps = {}
zone_sync_lock = threading.Lock()

def check_zone_file_updates(area_id, zone_file):
    """Check if zone file has been updated and reload if needed"""
    try:
        if not os.path.exists(zone_file):
            return False
        
        current_mtime = os.path.getmtime(zone_file)
        
        with zone_sync_lock:
            last_mtime = zone_file_timestamps.get(area_id, 0)
            
            if current_mtime > last_mtime:
                zone_file_timestamps[area_id] = current_mtime
                return True
        
        return False
    except Exception as e:
        print(f"⚠️ Error checking zone file updates for {area_id}: {e}")
        return False

def sync_zones_from_backend(area_id):
    """Fetch latest zones from backend and sync to JSON file"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/admin/zones/by-name/{area_id}",
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('zones'):
                return True
        return False
    except Exception as e:
        # Silently fail - backend might not be running
        return False

def update_backend(area, live_people, zone_counts):
    """Update backend with current metrics"""
    global BACKEND_AVAILABLE, BACKEND_RETRY_TIME
    
    current_time = time.time()
    
    # If backend was unavailable, retry after 10 seconds
    if not BACKEND_AVAILABLE:
        if current_time - BACKEND_RETRY_TIME > 10:
            BACKEND_AVAILABLE = True
            print(f"🔄 Retrying backend connection...")
        else:
            return
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/update/{area}", 
            json={
                'live_people': live_people,
                'zone_counts': zone_counts
            },
            timeout=3  # Increased from 1 to 3 seconds
        )
        if response.status_code == 200:
            print(f"✅ {area}: {live_people} people | zones: {zone_counts}")
        else:
            print(f"⚠️ Backend returned status {response.status_code} for {area}")
    except Exception as e:
        print(f"❌ Backend error for {area}: {e}")
        BACKEND_AVAILABLE = False
        BACKEND_RETRY_TIME = current_time

# Area configurations
AREAS_CONFIG = {
    "entrance": {
        "name": "🚪 Mall Entrance",
        "video": "youtube-videos/enterance.mp4",
        "zone_file": "zones/zones_entrance.json",
        "window_pos": (10, 50),
        "color": (0, 255, 0)  # Green
    },
    "retail": {
        "name": "🛒 Retail Area",
        "video": "youtube-videos/retail.mp4", 
        "zone_file": "zones/zones_retail.json",
        "window_pos": (820, 50),
        "color": (255, 0, 0)  # Blue
    },
    "foodcourt": {
        "name": "🍔 Food Court",
        "video": "youtube-videos/foodcourt.mp4",
        "zone_file": "zones/zones_foodcourt.json", 
        "window_pos": (10, 700),
        "color": (0, 0, 255)  # Red
    }
}

DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 600


class AreaEditor:
    """Independent zone editor for each area"""
    
    def __init__(self, area_id, config):
        self.area_id = area_id
        self.config = config
        self.name = config["name"]
        self.zone_file = config["zone_file"]
        
        # UI state
        self.mode = "normal"
        self.mouse_pos = (0, 0)
        self.drawing_points = []
        self.rect_start = None
        self.rect_dragging = False
        self.paused = False
        
        # Data
        self.zones = zone_mod.load_zones(self.zone_file)
        self.current_frame = None
        self.live_count = 0
        self.zone_counts = {}
        self.last_zone_check = time.time()
        
        # Initialize zone file timestamp
        if os.path.exists(self.zone_file):
            with zone_sync_lock:
                zone_file_timestamps[self.area_id] = os.path.getmtime(self.zone_file)
        
        print(f"✅ Initialized {self.name} - {len(self.zones)} zones loaded")
    
    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events for zone drawing"""
        self.mouse_pos = (x, y)
        
        if event == cv2.EVENT_LBUTTONDOWN:
            if self.mode == 'draw_rect':
                self.rect_start = (x, y)
                self.rect_dragging = True
                self.drawing_points = []
                print(f"🎯 {self.name}: Rectangle start ({x}, {y})")
                
            elif self.mode == 'draw_polygon':
                self.drawing_points.append([x, y])
                print(f"📍 {self.name}: Point {len(self.drawing_points)}: ({x}, {y})")
        
        elif event == cv2.EVENT_LBUTTONUP:
            if self.mode == 'draw_rect' and self.rect_dragging and self.rect_start:
                print(f"🎯 {self.name}: Rectangle end ({x}, {y})")
                self._finish_rectangle(x, y)
    
    def _finish_rectangle(self, x2, y2):
        """Complete rectangle zone drawing"""
        x1, y1 = self.rect_start
        
        # Create rectangle points (display coords)
        rect_points = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
        
        # Scale to original resolution
        if self.current_frame is not None:
            orig_h, orig_w = self.current_frame.shape[:2]
            scale_x = orig_w / DISPLAY_WIDTH
            scale_y = orig_h / DISPLAY_HEIGHT
            
            original_points = [
                [int(p[0] * scale_x), int(p[1] * scale_y)] 
                for p in rect_points
            ]
            
            # Add and save zone
            zone_mod.add_zone(self.zones, original_points)
            zone_mod.save_zones(self.zone_file, self.zones)
            
            # Reload zones for YOLO processing
            week2_set_zone_file(self.zone_file)
            week2_reload_zones()
            self.zones = zone_mod.load_zones(self.zone_file)
            
            print(f"✅ Rectangle zone added to {self.name} | Total: {len(self.zones)}")
        
        # Reset state
        self.rect_start = None
        self.rect_dragging = False
        self.mode = 'normal'
    
    def _finish_polygon(self):
        """Complete polygon zone drawing"""
        if len(self.drawing_points) < 3:
            print("⚠️  Need at least 3 points")
            return
        
        if self.current_frame is not None:
            orig_h, orig_w = self.current_frame.shape[:2]
            scale_x = orig_w / DISPLAY_WIDTH
            scale_y = orig_h / DISPLAY_HEIGHT
            
            original_points = [
                [int(p[0] * scale_x), int(p[1] * scale_y)] 
                for p in self.drawing_points
            ]
            
            zone_mod.add_zone(self.zones, original_points)
            zone_mod.save_zones(self.zone_file, self.zones)
            
            # Reload zones for YOLO processing
            week2_set_zone_file(self.zone_file)
            week2_reload_zones()
            self.zones = zone_mod.load_zones(self.zone_file)
            
            print(f"✅ Polygon zone added to {self.name} | Total: {len(self.zones)}")
        
        self.drawing_points = []
        self.mode = 'normal'
    
    def draw_ui(self, frame):
        """Draw UI overlay with zones and controls"""
        display = cv2.resize(frame, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
        
        # Calculate scaling
        orig_h, orig_w = frame.shape[:2]
        scale_x = DISPLAY_WIDTH / orig_w
        scale_y = DISPLAY_HEIGHT / orig_h
        
        # Draw saved zones
        for zone in self.zones:
            scaled_points = [
                [int(p[0] * scale_x), int(p[1] * scale_y)] 
                for p in zone["points"]
            ]
            pts = np.array(scaled_points, np.int32).reshape((-1, 1, 2))
            
            # Zone fill (semi-transparent)
            overlay = display.copy()
            cv2.fillPoly(overlay, [pts], self.config["color"])
            cv2.addWeighted(overlay, 0.2, display, 0.8, 0, display)
            
            # Zone border
            cv2.polylines(display, [pts], True, self.config["color"], 3)
            
            # Zone label with count
            zone_id = zone.get("id", "?")
            count = self.zone_counts.get(zone_id, 0)
            
            M = cv2.moments(pts)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                cv2.putText(display, f"Zone {zone_id}: {count}", 
                           (cx - 50, cy),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, 
                           self.config["color"], 2)
        
        # Draw current drawing
        if self.mode == "draw_rect" and self.rect_dragging and self.rect_start:
            x1, y1 = self.rect_start
            x2, y2 = self.mouse_pos
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 255), 3)
            cv2.putText(display, "Drawing Rectangle...", (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        elif self.drawing_points:
            # Draw polygon preview
            for i in range(len(self.drawing_points) - 1):
                cv2.line(display, 
                        tuple(self.drawing_points[i]), 
                        tuple(self.drawing_points[i + 1]), 
                        (0, 255, 255), 3)
            
            if self.mode == "draw_polygon" and self.drawing_points:
                cv2.line(display, 
                        tuple(self.drawing_points[-1]), 
                        self.mouse_pos, 
                        (0, 255, 255), 2)
        
        # HUD - Top bar
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        cv2.rectangle(display, (0, 0), (DISPLAY_WIDTH, 110), (40, 40, 40), -1)
        
        cv2.putText(display, self.name, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        cv2.putText(display, ts, (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        
        # Live count
        cv2.putText(display, f"LIVE: {self.live_count}", (10, 95), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        
        # Zone total
        zone_total = sum(self.zone_counts.values()) if self.zone_counts else 0
        cv2.putText(display, f"ZONES: {len(self.zones)} | IN ZONES: {zone_total}", 
                   (250, 95), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        
        # Current mode indicator
        if self.mode != "normal":
            mode_text = f"MODE: {self.mode.upper()}"
            cv2.putText(display, mode_text, (DISPLAY_WIDTH - 300, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Instructions - Bottom bar
        instructions = [
            "R-Rectangle | N-Polygon | F-Finish | S-Save | D-Delete | SPACE-Pause | Q-Quit"
        ]
        
        y_start = DISPLAY_HEIGHT - 30
        for text in instructions:
            cv2.putText(display, text, (10, y_start), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            y_start += 20
        
        return display
    
    def handle_key(self, key):
        """Handle keyboard input"""
        if key == ord('q'):
            return False  # Signal to quit
        
        elif key == ord(' '):
            self.paused = not self.paused
            print(f"{'⏸ PAUSED' if self.paused else '▶ PLAY'} - {self.name}")
        
        elif key == ord('r'):
            self.mode = 'draw_rect'
            self.drawing_points = []
            print(f"🟥 {self.name}: RECTANGLE MODE - Click and drag")
        
        elif key == ord('n'):
            self.mode = 'draw_polygon'
            self.drawing_points = []
            print(f"🔷 {self.name}: POLYGON MODE - Click points, press F to finish")
        
        elif key == ord('f') or key == 13:
            if self.mode == 'draw_polygon':
                self._finish_polygon()
        
        elif key == ord('s'):
            zone_mod.save_zones(self.zone_file, self.zones)
            print(f"💾 {self.name}: Zones saved")
        
        elif key == ord('d'):
            self.mode = 'delete_select'
            print(f"🗑️  {self.name}: DELETE MODE - Press 1-9 to delete zone")
        
        elif key in [ord(str(i)) for i in range(1, 10)]:
            if self.mode == 'delete_select':
                zone_id = int(chr(key))
                if zone_mod.delete_zone(self.zones, zone_id):
                    zone_mod.save_zones(self.zone_file, self.zones)
                    
                    # Reload zones for YOLO processing
                    week2_set_zone_file(self.zone_file)
                    week2_reload_zones()
                    self.zones = zone_mod.load_zones(self.zone_file)
                    
                    print(f"✅ {self.name}: Deleted zone {zone_id}")
                else:
                    print(f"❌ {self.name}: Zone {zone_id} not found")
                self.mode = 'normal'
        
        return True  # Continue running
    
    def run(self):
        """Main processing loop for this area"""
        print(f"🎬 Starting {self.name}...")
        
        # Set zone file for YOLO processing
        week2_set_zone_file(self.zone_file)
        
        # Open local video file
        video_path = self.config["video"]
        cap = open_camera(video_path)
        if cap is None:
            print(f"❌ Failed to open {self.name} stream")
            return
        
        # Create window (use simple name without emojis for OpenCV)
        window_name = self.config["name"].split()[-1]  # Extract: "Entrance", "Area", "Court"
        if "Entrance" in self.config["name"]:
            window_name = "Entrance"
        elif "Retail" in self.config["name"]:
            window_name = "Retail"
        else:
            window_name = "FoodCourt"
        
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, DISPLAY_WIDTH, DISPLAY_HEIGHT)
        
        # Position window
        x, y = self.config["window_pos"]
        cv2.moveWindow(window_name, x, y)
        
        # Set mouse callback
        cv2.setMouseCallback(window_name, self.mouse_callback)
        
        last_backend_update = 0
        BACKEND_UPDATE_INTERVAL = 2.0
        
        print(f"✅ {self.name} ready!")
        
        while True:
            # Pause handling
            if self.paused:
                key = cv2.waitKey(50) & 0xFF
                if not self.handle_key(key):
                    break
                continue
            
            # Get frame
            ret, frame = get_camera_frame(cap)
            if not ret or frame is None:
                # Video ended - loop it
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                time.sleep(0.1)
                continue
            
            self.current_frame = frame
            
            # Check for zone file updates every 5 seconds
            current_time = time.time()
            if current_time - self.last_zone_check >= 5.0:
                if check_zone_file_updates(self.area_id, self.zone_file):
                    # Zones have been updated - reload them
                    with yolo_lock:
                        self.zones = zone_mod.load_zones(self.zone_file)
                        week2_set_zone_file(self.zone_file)
                        week2_reload_zones()
                    print(f"🔄 {self.name}: Zones reloaded from file ({len(self.zones)} zones)")
                self.last_zone_check = current_time
            
            # Process with YOLO (thread-safe)
            with yolo_lock:
                week2_set_zone_file(self.zone_file)
                processed_frame, self.zone_counts, self.live_count = week2_process_frame(frame.copy())
            
            # Update backend periodically
            if current_time - last_backend_update >= BACKEND_UPDATE_INTERVAL:
                update_backend(self.area_id, self.live_count, self.zone_counts)
                last_backend_update = current_time
            
            # Draw UI
            display = self.draw_ui(processed_frame)
            
            # Show
            cv2.imshow(window_name, display)
            
            # Check if window closed
            try:
                if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                    break
            except:
                break
            
            # Handle keys
            key = cv2.waitKey(20) & 0xFF
            if not self.handle_key(key):
                break
        
        # Cleanup
        release_camera(cap)
        try:
            cv2.destroyWindow(window_name)
        except:
            pass
        print(f"👋 {self.name} stopped")


def zone_sync_worker():
    """Background worker to sync zones from backend periodically"""
    print("🔄 Zone sync worker started")
    while True:
        try:
            time.sleep(10)  # Check every 10 seconds
            
            for area_id in AREAS_CONFIG.keys():
                # Try to sync zones from backend
                sync_zones_from_backend(area_id)
        except Exception as e:
            # Silent fail - don't spam console
            pass

def main():
    """Start all area editors"""
    print("="*60)
    print("🎯 CROWDCOUNT MULTI-AREA SYSTEM")
    print("="*60)
    print("\n🎨 Starting 3 independent zone editors:")
    print("   • Mall Entrance")
    print("   • Retail Area")
    print("   • Food Court")
    print("\n📊 Dashboard: http://127.0.0.1:5000")
    print("="*60 + "\n")
    
    # Start zone sync worker thread
    sync_thread = threading.Thread(
        target=zone_sync_worker,
        daemon=True,
        name="ZoneSyncWorker"
    )
    sync_thread.start()
    
    # Create editors (using local video files)
    editors = []
    threads = []
    
    for area_id, config in AREAS_CONFIG.items():
        editor = AreaEditor(area_id, config)
        editors.append(editor)
        
        # Start in thread
        thread = threading.Thread(
            target=editor.run,
            daemon=True,
            name=f"Thread-{area_id}"
        )
        threads.append(thread)
        thread.start()
        
        print(f"✅ Started {config['name']}")
        time.sleep(0.5)  # Stagger window creation
    
    print("\n" + "="*60)
    print("🎨 ALL EDITORS RUNNING!")
    print("="*60)
    print("\n🖱️  CONTROLS (same for all windows):")
    print("   R  - Draw Rectangle Zone")
    print("   N  - Draw Polygon Zone")
    print("   F  - Finish Polygon")
    print("   S  - Save Zones")
    print("   D  - Delete Zone (then press 1-9)")
    print("   SPACE - Pause/Resume")
    print("   Q  - Close Window")
    print("\n" + "="*60 + "\n")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
            if not any(t.is_alive() for t in threads):
                break
    except KeyboardInterrupt:
        print("\n⏹ Shutting down...")
    
    print("👋 System stopped")


if __name__ == '__main__':
    main()