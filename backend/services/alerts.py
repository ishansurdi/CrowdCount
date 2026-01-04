"""
Alert Management Service
Handles threshold-based alerts and notifications
"""

from datetime import datetime
from backend.db import get_db

class AlertManager:
    def __init__(self):
        self.last_alert_time = {}
        self.cooldown = 20  # 20 seconds cooldown per area
    
    def check_threshold(self, area_name, live_count, zone_counts):
        """Check if count exceeds threshold and create alert if needed"""
        try:
            db = get_db()
            
            # Get current global threshold
            threshold_data = db.execute_query(
                "SELECT global_threshold FROM thresholds ORDER BY id DESC LIMIT 1",
                fetch_one=True
            )
            
            if not threshold_data:
                return None
            
            threshold = threshold_data['global_threshold']
            
            # Check if live count exceeds threshold
            if live_count <= threshold:
                return None
            
            # Check cooldown
            current_time = datetime.now().timestamp()
            last_alert = self.last_alert_time.get(area_name, 0)
            
            if current_time - last_alert < self.cooldown:
                return None  # Still in cooldown
            
            # Get area_id
            area = db.execute_query(
                "SELECT area_id FROM areas WHERE area_name = %s",
                (area_name,),
                fetch_one=True
            )
            
            if not area:
                return None
            
            area_id = area['area_id']
            
            # Get threshold_id
            threshold_record = db.execute_query(
                "SELECT id FROM thresholds ORDER BY id DESC LIMIT 1",
                fetch_one=True
            )
            threshold_id = threshold_record['id'] if threshold_record else None
            
            # Create alert
            alert_id = db.execute_query(
                """
                INSERT INTO alerts (area_id, zone_id, observed_count, threshold, status)
                VALUES (%s, NULL, %s, %s, 'active')
                """,
                (area_id, live_count, threshold)
            )
            
            # Record threshold violation for history
            if threshold_id:
                # Format zone details
                zone_details = ', '.join([f"Zone {k}: {v}" for k, v in zone_counts.items()]) if zone_counts else 'N/A'
                
                db.execute_query(
                    """
                    INSERT INTO threshold_violations 
                    (area_id, threshold_id, people_count, violation_time, zone_details)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (area_id, threshold_id, live_count, datetime.now(), zone_details)
                )
            
            # Update last alert time
            self.last_alert_time[area_name] = current_time
            
            print(f"⚠️  ALERT: {area_name} exceeded threshold ({live_count} > {threshold})")
            
            return {
                'alert_id': alert_id,
                'area': area_name,
                'count': live_count,
                'threshold': threshold
            }
            
        except Exception as e:
            print(f"❌ Alert check error: {e}")
            return None
    
    def acknowledge_alert(self, alert_id, user_id):
        """Mark an alert as acknowledged"""
        try:
            db = get_db()
            
            db.execute_query(
                """
                UPDATE alerts 
                SET status = 'acknowledged', 
                    acknowledged_at = %s,
                    acknowledged_by = %s
                WHERE alert_id = %s
                """,
                (datetime.now(), user_id, alert_id)
            )
            
            print(f"✅ Alert {alert_id} acknowledged by user {user_id}")
            return True
            
        except Exception as e:
            print(f"❌ Alert acknowledge error: {e}")
            return False
    
    def get_active_alerts(self, area_name=None):
        """Get all active alerts, optionally filtered by area"""
        try:
            db = get_db()
            
            if area_name:
                alerts = db.execute_query(
                    """
                    SELECT a.*, ar.area_name 
                    FROM alerts a
                    JOIN areas ar ON a.area_id = ar.area_id
                    WHERE a.status = 'active' AND ar.area_name = %s
                    ORDER BY a.created_at DESC
                    """,
                    (area_name,),
                    fetch=True
                )
            else:
                alerts = db.execute_query(
                    """
                    SELECT a.*, ar.area_name 
                    FROM alerts a
                    JOIN areas ar ON a.area_id = ar.area_id
                    WHERE a.status = 'active'
                    ORDER BY a.created_at DESC
                    """,
                    fetch=True
                )
            
            return alerts or []
            
        except Exception as e:
            print(f"❌ Get alerts error: {e}")
            return []
    
    def get_alert_history(self, area_name=None, limit=50):
        """Get alert history"""
        try:
            db = get_db()
            
            if area_name:
                alerts = db.execute_query(
                    """
                    SELECT a.*, ar.area_name, u.name as acknowledged_by_name
                    FROM alerts a
                    JOIN areas ar ON a.area_id = ar.area_id
                    LEFT JOIN users u ON a.acknowledged_by = u.user_id
                    WHERE ar.area_name = %s
                    ORDER BY a.created_at DESC
                    LIMIT %s
                    """,
                    (area_name, limit),
                    fetch=True
                )
            else:
                alerts = db.execute_query(
                    """
                    SELECT a.*, ar.area_name, u.name as acknowledged_by_name
                    FROM alerts a
                    JOIN areas ar ON a.area_id = ar.area_id
                    LEFT JOIN users u ON a.acknowledged_by = u.user_id
                    ORDER BY a.created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                    fetch=True
                )
            
            return alerts or []
            
        except Exception as e:
            print(f"❌ Get alert history error: {e}")
            return []

# Global alert manager instance
alert_manager = AlertManager()

def get_alert_manager():
    """Get the alert manager instance"""
    return alert_manager
