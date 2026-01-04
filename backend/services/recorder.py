"""
Historical Data Recorder Service
Records crowd counts every 5 seconds for analytics
"""

import threading
import time
from datetime import datetime
from backend.db import get_db

class HistoricalRecorder:
    def __init__(self, get_areas_state_func=None):
        self.running = False
        self.thread = None
        self.interval = 5  # Record every 5 seconds
        self.get_areas_state = get_areas_state_func  # Function to get AREAS_STATE
        
    def start(self):
        """Start the recording service"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._record_loop, daemon=True)
            self.thread.start()
            print("✅ Historical recorder started (5s interval)")
    
    def stop(self):
        """Stop the recording service"""
        self.running = False
        if self.thread:
            self.thread.join()
        print("⏹ Historical recorder stopped")
    
    def _record_loop(self):
        """Main recording loop"""
        while self.running:
            try:
                self._record_snapshot()
            except Exception as e:
                print(f"❌ Recording error: {e}")
            
            time.sleep(self.interval)
    
    def _record_snapshot(self):
        """Record current counts to historical_counts table"""
        import os
        
        # Get AREAS_STATE from the callback function
        if self.get_areas_state is None:
            print("❌ Recording error: No AREAS_STATE accessor provided!")
            return
            
        AREAS_STATE = self.get_areas_state()
        
        db = get_db()
        timestamp = datetime.now()
        
        # DEBUGGING: Check object IDs and PID
        print(f"🔍 RECORDER - PID {os.getpid()} - id(AREAS_STATE) = {id(AREAS_STATE)}")
        print(f"📊 Recording snapshot - AREAS_STATE: {AREAS_STATE}")
        
        for area_name, state in AREAS_STATE.items():
            try:
                # Get area_id from database
                area = db.execute_query(
                    "SELECT area_id FROM areas WHERE area_name = %s",
                    (area_name,),
                    fetch_one=True
                )
                
                if not area:
                    continue
                
                area_id = area['area_id']
                live_people = state.get('live_people', 0)
                zone_counts = state.get('zone_counts', {})
                
                # Always record, even if zero (to track when areas are empty)
                # Record overall area count (zone_id = NULL)
                db.execute_query(
                    """
                    INSERT INTO historical_counts (area_id, zone_id, count, timestamp)
                    VALUES (%s, NULL, %s, %s)
                    """,
                    (area_id, live_people, timestamp)
                )
                
                # Record individual zone counts
                if zone_counts:
                    for zone_id_str, count in zone_counts.items():
                        try:
                            zone_id = int(zone_id_str)
                            
                            # Verify zone exists in database
                            zone_exists = db.execute_query(
                                """
                                SELECT id FROM zones 
                                WHERE area_id = %s AND zone_id = %s
                                """,
                                (area_id, zone_id),
                                fetch_one=True
                            )
                            
                            if zone_exists:
                                db.execute_query(
                                    """
                                    INSERT INTO historical_counts (area_id, zone_id, count, timestamp)
                                    VALUES (%s, %s, %s, %s)
                                    """,
                                    (area_id, zone_id, count, timestamp)
                                )
                        except (ValueError, TypeError):
                            # Skip invalid zone IDs
                            continue
            except Exception as e:
                print(f"❌ Recording error for {area_name}: {e}")
                continue


# Global recorder instance (singleton pattern)
_recorder_instance = None
_recorder_lock = threading.Lock()
_recorder_process_id = None

def get_recorder(get_areas_state_func=None):
    """Get the singleton recorder instance"""
    global _recorder_instance, _recorder_process_id
    import os
    current_pid = os.getpid()
    
    # If we're in a different process, reset the instance
    if _recorder_process_id and _recorder_process_id != current_pid:
        _recorder_instance = None
        
    if _recorder_instance is None:
        with _recorder_lock:
            if _recorder_instance is None:
                _recorder_instance = HistoricalRecorder(get_areas_state_func)
                _recorder_process_id = current_pid
    return _recorder_instance

def start_recorder(get_areas_state_func=None):
    """Start the historical recorder service"""
    import os
    recorder = get_recorder(get_areas_state_func)
    if not recorder.running:
        print(f"🔵 Starting recorder in PID {os.getpid()}, Thread {threading.current_thread().ident}")
        recorder.start()
    else:
        print(f"⚠️  Recorder already running in PID {os.getpid()}")

def stop_recorder():
    """Stop the historical recorder service"""
    recorder = get_recorder()
    recorder.stop()
