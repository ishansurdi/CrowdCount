"""
Admin Routes
Protected endpoints for system administration
"""

from flask import Blueprint, jsonify, request
from backend.auth.jwt_utils import admin_required
from backend.db import get_db
import bcrypt
import json
import os
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

@admin_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for admin API"""
    return jsonify({
        'status': 'ok',
        'service': 'admin-api',
        'endpoints_available': [
            '/threshold',
            '/cameras',
            '/users',
            '/zones/by-name/<area>',
            '/zones/sync-all'
        ]
    }), 200

def _sync_zones_to_json(area_name, db, area_id):
    """Helper function to sync zones from database to JSON file"""
    try:
        # Get all zones for this area from database
        zones_data = db.execute_query(
            """
            SELECT zone_id, zone_name, polygon_coords
            FROM zones
            WHERE area_id = %s
            ORDER BY zone_id
            """,
            (area_id,),
            fetch=True
        )
        
        # Convert to JSON format
        zones_list = []
        for zone in (zones_data or []):
            coords = json.loads(zone['polygon_coords']) if zone.get('polygon_coords') else []
            zones_list.append({
                'id': zone['zone_id'],
                'name': zone['zone_name'],
                'color': [0, 255, 0],  # Default green color
                'points': coords
            })
        
        # Write to JSON file
        zones_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'zones')
        os.makedirs(zones_dir, exist_ok=True)
        
        json_file = os.path.join(zones_dir, f'zones_{area_name}.json')
        with open(json_file, 'w') as f:
            json.dump({'zones': zones_list}, f, indent=4)
        
        print(f"✅ Synced {len(zones_list)} zones to {json_file}")
        
    except Exception as e:
        print(f"⚠️ Failed to sync zones to JSON for {area_name}: {e}")

@admin_bp.route('/threshold', methods=['GET', 'POST'])
@admin_required
def manage_threshold():
    """Get or update global threshold (Admin only)"""
    try:
        db = get_db()
        user = request.current_user
        
        if request.method == 'GET':
            # Get current threshold
            threshold = db.execute_query(
                "SELECT global_threshold, last_updated FROM thresholds ORDER BY id DESC LIMIT 1",
                fetch_one=True
            )
            
            return jsonify({
                'success': True,
                'threshold': threshold['global_threshold'] if threshold else 50,
                'last_updated': threshold['last_updated'].isoformat() if threshold and threshold['last_updated'] else None
            }), 200
        
        elif request.method == 'POST':
            # Update threshold
            data = request.get_json()
            new_threshold = data.get('threshold')
            
            if not new_threshold or not isinstance(new_threshold, int):
                return jsonify({'error': 'Invalid threshold value'}), 400
            
            # Update or insert threshold
            # First check if record exists
            exists = db.execute_query(
                "SELECT id FROM thresholds LIMIT 1",
                fetch_one=True
            )
            
            if exists:
                # Update existing record
                db.execute_query(
                    """
                    UPDATE thresholds 
                    SET global_threshold = %s, updated_by = %s, last_updated = NOW()
                    WHERE id = %s
                    """,
                    (new_threshold, user['user_id'], exists['id'])
                )
            else:
                # Insert new record
                db.execute_query(
                    """
                    INSERT INTO thresholds (global_threshold, updated_by, last_updated)
                    VALUES (%s, %s, NOW())
                    """,
                    (new_threshold, user['user_id'])
                )
            
            print(f"✅ Threshold updated to {new_threshold} by {user['name']}")
            
            return jsonify({
                'success': True,
                'threshold': new_threshold
            }), 200
            
    except Exception as e:
        print(f"❌ Threshold management error: {e}")
        return jsonify({'error': 'Failed to manage threshold'}), 500

@admin_bp.route('/users', methods=['GET'])
@admin_required
def list_users():
    """List all users (Admin only)"""
    try:
        db = get_db()
        
        users = db.execute_query(
            """
            SELECT 
                user_id,
                name,
                email,
                role,
                created_at
            FROM users
            ORDER BY created_at DESC
            """,
            fetch=True
        )
        
        # Get assigned areas for each user
        for user in (users or []):
            areas = db.execute_query(
                """
                SELECT a.area_name
                FROM areas a
                JOIN user_areas ua ON a.area_id = ua.area_id
                WHERE ua.user_id = %s
                """,
                (user['user_id'],),
                fetch=True
            )
            user['areas'] = [area['area_name'] for area in (areas or [])]
        
        return jsonify({
            'success': True,
            'users': users or []
        }), 200
        
    except Exception as e:
        print(f"❌ List users error: {e}")
        return jsonify({'error': 'Failed to fetch users'}), 500

@admin_bp.route('/users', methods=['POST'])
@admin_required
def create_user():
    """Create new user (Admin only)"""
    try:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        role = data.get('role', 'user')
        areas = data.get('areas', [])
        
        if not name or not email or not password:
            return jsonify({'error': 'Name, email, and password required'}), 400
        
        if role not in ['admin', 'user']:
            return jsonify({'error': 'Invalid role'}), 400
        
        db = get_db()
        
        # Check if email already exists
        existing = db.execute_query(
            "SELECT user_id FROM users WHERE email = %s",
            (email,),
            fetch_one=True
        )
        
        if existing:
            return jsonify({'error': 'Email already exists'}), 409
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Create user
        user_id = db.execute_query(
            """
            INSERT INTO users (name, email, password_hash, role)
            VALUES (%s, %s, %s, %s)
            """,
            (name, email, password_hash.decode('utf-8'), role)
        )
        
        # Assign areas
        for area_name in areas:
            area = db.execute_query(
                "SELECT area_id FROM areas WHERE area_name = %s",
                (area_name,),
                fetch_one=True
            )
            if area:
                db.execute_query(
                    "INSERT INTO user_areas (user_id, area_id) VALUES (%s, %s)",
                    (user_id, area['area_id'])
                )
        
        print(f"✅ User created: {email} (role: {role})")
        
        return jsonify({
            'success': True,
            'user_id': user_id
        }), 201
        
    except Exception as e:
        print(f"❌ Create user error: {e}")
        return jsonify({'error': 'Failed to create user'}), 500

@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """Update user (Admin only)"""
    try:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        role = data.get('role')
        areas = data.get('areas', [])
        
        if not name or not email or not role:
            return jsonify({'error': 'Name, email, and role required'}), 400
        
        if role not in ['admin', 'user']:
            return jsonify({'error': 'Invalid role'}), 400
        
        db = get_db()
        
        # Check if email already exists for different user
        existing = db.execute_query(
            "SELECT user_id FROM users WHERE email = %s AND user_id != %s",
            (email, user_id),
            fetch_one=True
        )
        
        if existing:
            return jsonify({'error': 'Email already exists'}), 409
        
        # Update user basic info
        if password:
            # Update with new password
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            db.execute_query(
                """
                UPDATE users 
                SET name = %s, email = %s, password_hash = %s, role = %s
                WHERE user_id = %s
                """,
                (name, email, password_hash.decode('utf-8'), role, user_id)
            )
        else:
            # Update without changing password
            db.execute_query(
                """
                UPDATE users 
                SET name = %s, email = %s, role = %s
                WHERE user_id = %s
                """,
                (name, email, role, user_id)
            )
        
        # Update area assignments
        # First, remove all existing assignments
        db.execute_query(
            "DELETE FROM user_areas WHERE user_id = %s",
            (user_id,)
        )
        
        # Then add new assignments
        for area_name in areas:
            area = db.execute_query(
                "SELECT area_id FROM areas WHERE area_name = %s",
                (area_name,),
                fetch_one=True
            )
            if area:
                db.execute_query(
                    "INSERT INTO user_areas (user_id, area_id) VALUES (%s, %s)",
                    (user_id, area['area_id'])
                )
        
        print(f"✅ User {user_id} updated")
        
        return jsonify({
            'success': True,
            'user_id': user_id
        }), 200
        
    except Exception as e:
        print(f"❌ Update user error: {e}")
        return jsonify({'error': 'Failed to update user'}), 500

@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Delete user (Admin only)"""
    try:
        db = get_db()
        current_user = request.current_user
        
        # Prevent self-deletion
        if user_id == current_user['user_id']:
            return jsonify({'error': 'Cannot delete yourself'}), 400
        
        result = db.execute_query(
            "DELETE FROM users WHERE user_id = %s",
            (user_id,)
        )
        
        if result:
            print(f"✅ User {user_id} deleted by {current_user['name']}")
            return jsonify({'success': True}), 200
        else:
            return jsonify({'error': 'User not found'}), 404
            
    except Exception as e:
        print(f"❌ Delete user error: {e}")
        return jsonify({'error': 'Failed to delete user'}), 500

@admin_bp.route('/alerts', methods=['GET'])
@admin_required
def get_all_alerts():
    """Get all alerts (Admin only)"""
    try:
        from backend.services.alerts import get_alert_manager
        
        alert_manager = get_alert_manager()
        limit = request.args.get('limit', 50, type=int)
        
        alerts = alert_manager.get_alert_history(limit=limit)
        
        return jsonify({
            'success': True,
            'alerts': alerts
        }), 200
        
    except Exception as e:
        print(f"❌ Get alerts error: {e}")
        return jsonify({'error': 'Failed to fetch alerts'}), 500

@admin_bp.route('/alerts/<int:alert_id>/acknowledge', methods=['POST'])
@admin_required
def acknowledge_alert(alert_id):
    """Acknowledge an alert (Admin only)"""
    try:
        from backend.services.alerts import get_alert_manager
        
        alert_manager = get_alert_manager()
        user = request.current_user
        
        success = alert_manager.acknowledge_alert(alert_id, user['user_id'])
        
        if success:
            return jsonify({'success': True}), 200
        else:
            return jsonify({'error': 'Failed to acknowledge alert'}), 500
            
    except Exception as e:
        print(f"❌ Acknowledge alert error: {e}")
        return jsonify({'error': 'Failed to acknowledge alert'}), 500

@admin_bp.route('/diagnostics', methods=['GET'])
@admin_required
def get_diagnostics():
    """Get system diagnostics (Admin only)"""
    try:
        db = get_db()
        
        # Database stats
        record_count = db.execute_query(
            "SELECT COUNT(*) as count FROM historical_counts",
            fetch_one=True
        )
        
        user_count = db.execute_query(
            "SELECT COUNT(*) as count FROM users",
            fetch_one=True
        )
        
        alert_count = db.execute_query(
            "SELECT COUNT(*) as count FROM alerts WHERE status = 'active'",
            fetch_one=True
        )
        
        # Calculate sampling rate (records per minute)
        recent_records = db.execute_query(
            """
            SELECT COUNT(*) as count 
            FROM historical_counts 
            WHERE timestamp >= NOW() - INTERVAL 1 MINUTE
            """,
            fetch_one=True
        )
        
        return jsonify({
            'success': True,
            'diagnostics': {
                'database': {
                    'connected': db.connection.is_connected(),
                    'total_records': record_count['count'] if record_count else 0,
                    'active_alerts': alert_count['count'] if alert_count else 0,
                    'total_users': user_count['count'] if user_count else 0
                },
                'sampling': {
                    'rate_per_minute': recent_records['count'] if recent_records else 0,
                    'expected_rate': 12  # 3 areas * 5 second interval = 12 per minute
                },
                'status': 'operational'
            }
        }), 200
        
    except Exception as e:
        print(f"❌ Diagnostics error: {e}")
        return jsonify({'error': 'Failed to fetch diagnostics'}), 500
# === Camera Feed Management ===

@admin_bp.route('/cameras', methods=['GET'])
@admin_required
def list_cameras():
    """List all camera feeds (Admin only)"""
    try:
        db = get_db()
        
        cameras = db.execute_query(
            """
            SELECT 
                a.area_id,
                a.area_name,
                a.video_source,
                a.visible_to_users,
                COUNT(DISTINCT z.zone_id) as zone_count
            FROM areas a
            LEFT JOIN zones z ON a.area_id = z.area_id
            GROUP BY a.area_id, a.area_name, a.video_source, a.visible_to_users
            ORDER BY a.area_name
            """,
            fetch=True
        )
        
        return jsonify({
            'success': True,
            'cameras': cameras or []
        }), 200
        
    except Exception as e:
        print(f"❌ List cameras error: {e}")
        return jsonify({'error': 'Failed to fetch cameras'}), 500

@admin_bp.route('/cameras', methods=['POST'])
@admin_required
def create_camera():
    """Create new camera feed (Admin only)"""
    try:
        data = request.get_json()
        area_name = data.get('area_name')
        video_source = data.get('video_source')
        
        if not area_name:
            return jsonify({'error': 'Area name required'}), 400
        
        db = get_db()
        
        # Check if area already exists
        existing = db.execute_query(
            "SELECT area_id FROM areas WHERE area_name = %s",
            (area_name,),
            fetch_one=True
        )
        
        if existing:
            return jsonify({'error': 'Area already exists'}), 409
        
        # Create area
        area_id = db.execute_query(
            "INSERT INTO areas (area_name, video_source) VALUES (%s, %s)",
            (area_name, video_source)
        )
        
        print(f"✅ Camera feed created: {area_name}")
        
        return jsonify({
            'success': True,
            'area_id': area_id
        }), 201
        
    except Exception as e:
        print(f"❌ Create camera error: {e}")
        return jsonify({'error': 'Failed to create camera'}), 500

@admin_bp.route('/cameras/<int:area_id>', methods=['PUT'])
@admin_required
def update_camera(area_id):
    """Update camera feed (Admin only)"""
    try:
        data = request.get_json()
        video_source = data.get('video_source')
        
        db = get_db()
        
        db.execute_query(
            "UPDATE areas SET video_source = %s WHERE area_id = %s",
            (video_source, area_id)
        )
        
        print(f"✅ Camera {area_id} updated")
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        print(f"❌ Update camera error: {e}")
        return jsonify({'error': 'Failed to update camera'}), 500

@admin_bp.route('/cameras/<int:area_id>/visibility', methods=['PUT'])
@admin_required
def toggle_camera_visibility(area_id):
    """Toggle camera visibility for users (Admin only)"""
    try:
        data = request.get_json()
        visible = data.get('visible_to_users', True)
        
        db = get_db()
        
        db.execute_query(
            "UPDATE areas SET visible_to_users = %s WHERE area_id = %s",
            (visible, area_id)
        )
        
        print(f"✅ Camera {area_id} visibility set to {visible}")
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        print(f"❌ Toggle visibility error: {e}")
        return jsonify({'error': 'Failed to update visibility'}), 500

@admin_bp.route('/cameras/<int:area_id>', methods=['DELETE'])
@admin_required
def delete_camera(area_id):
    """Delete camera feed (Admin only)"""
    try:
        db = get_db()
        
        result = db.execute_query(
            "DELETE FROM areas WHERE area_id = %s",
            (area_id,)
        )
        
        if result:
            print(f"✅ Camera {area_id} deleted")
            return jsonify({'success': True}), 200
        else:
            return jsonify({'error': 'Camera not found'}), 404
            
    except Exception as e:
        print(f"❌ Delete camera error: {e}")
        return jsonify({'error': 'Failed to delete camera'}), 500

@admin_bp.route('/cameras/<int:area_id>/visibility', methods=['PUT'])
@admin_required
def update_camera_visibility(area_id):
    """Toggle camera visibility for users (Admin only)"""
    try:
        db = get_db()
        data = request.get_json()
        visible = data.get('visible_to_users', True)
        
        result = db.execute_query(
            "UPDATE areas SET visible_to_users = %s WHERE area_id = %s",
            (visible, area_id)
        )
        
        if result:
            print(f"✅ Camera {area_id} visibility updated to {visible}")
            return jsonify({'success': True, 'visible_to_users': visible}), 200
        else:
            return jsonify({'error': 'Camera not found'}), 404
            
    except Exception as e:
        print(f"❌ Update visibility error: {e}")
        return jsonify({'error': 'Failed to update visibility'}), 500

# === Zone Management ===

@admin_bp.route('/zones/<int:area_id>', methods=['GET'])
@admin_required
def get_zones(area_id):
    """Get zones for an area (Admin only)"""
    try:
        db = get_db()
        
        zones = db.execute_query(
            """
            SELECT zone_id, zone_name, polygon_coords
            FROM zones
            WHERE area_id = %s
            ORDER BY zone_id
            """,
            (area_id,),
            fetch=True
        )
        
        return jsonify({
            'success': True,
            'zones': zones or []
        }), 200
        
    except Exception as e:
        print(f"❌ Get zones error: {e}")
        return jsonify({'error': 'Failed to fetch zones'}), 500

@admin_bp.route('/zones/<int:area_id>', methods=['POST'])
@admin_required
def save_zones(area_id):
    """Save zones for an area (Admin only)"""
    try:
        data = request.get_json()
        zones = data.get('zones', [])
        
        db = get_db()
        
        # Delete existing zones
        db.execute_query(
            "DELETE FROM zones WHERE area_id = %s",
            (area_id,)
        )
        
        # Insert new zones
        for zone in zones:
            db.execute_query(
                """
                INSERT INTO zones (area_id, zone_id, zone_name, polygon_coords)
                VALUES (%s, %s, %s, %s)
                """,
                (area_id, zone['zone_id'], zone.get('zone_name'), zone.get('polygon_coords'))
            )
        
        print(f"✅ Zones saved for area {area_id}: {len(zones)} zones")
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        print(f"❌ Save zones error: {e}")
        return jsonify({'error': 'Failed to save zones'}), 500

# === Zone Management by Area Name ===

AREA_NAME_TO_ID = {
    'entrance': 1,
    'retail': 2,
    'foodcourt': 3
}

@admin_bp.route('/zones/by-name/<string:area_name>', methods=['GET'])
@admin_required
def get_zones_by_name(area_name):
    """Get zones for an area by name (Admin only)"""
    try:
        area_id = AREA_NAME_TO_ID.get(area_name.lower())
        if not area_id:
            return jsonify({'error': 'Invalid area name'}), 400
        
        db = get_db()
        
        zones_data = db.execute_query(
            """
            SELECT zone_id, zone_name, polygon_coords, visible_to_users
            FROM zones
            WHERE area_id = %s
            ORDER BY zone_id
            """,
            (area_id,),
            fetch=True
        )
        
        # Parse coordinates if they're stored as strings
        zones = []
        for zone in (zones_data or []):
            zone_dict = dict(zone)
            if isinstance(zone_dict.get('polygon_coords'), str):
                try:
                    zone_dict['coordinates'] = json.loads(zone_dict['polygon_coords'])
                except:
                    zone_dict['coordinates'] = []
            else:
                zone_dict['coordinates'] = zone_dict.get('polygon_coords', [])
            zones.append(zone_dict)
        
        return jsonify({
            'success': True,
            'zones': zones
        }), 200
        
    except Exception as e:
        print(f"❌ Get zones by name error: {e}")
        return jsonify({'error': 'Failed to fetch zones'}), 500

@admin_bp.route('/zones/by-name/<string:area_name>', methods=['POST'])
@admin_required
def save_zones_by_name(area_name):
    """Save zones for an area by name (Admin only)"""
    try:
        area_id = AREA_NAME_TO_ID.get(area_name.lower())
        if not area_id:
            return jsonify({'error': 'Invalid area name'}), 400
        
        data = request.get_json()
        zones = data.get('zones', [])
        
        db = get_db()
        
        # Save zones to database (don't delete existing ones, just update/insert)
        for zone in zones:
            # Convert coordinates to JSON string if needed
            coords = zone.get('points', zone.get('coordinates', []))
            coords_json = json.dumps(coords) if coords else '[]'
            
            # Check if zone exists
            existing = db.execute_query(
                "SELECT zone_id FROM zones WHERE area_id = %s AND zone_id = %s",
                (area_id, zone['id']),
                fetch=True
            )
            
            if existing and len(existing) > 0:
                # Update existing zone
                db.execute_query(
                    """
                    UPDATE zones 
                    SET zone_name = %s, polygon_coords = %s
                    WHERE area_id = %s AND zone_id = %s
                    """,
                    (zone.get('name', f"Zone {zone['id']}"), coords_json, area_id, zone['id'])
                )
            else:
                # Insert new zone
                db.execute_query(
                    """
                    INSERT INTO zones (area_id, zone_id, zone_name, polygon_coords, visible_to_users)
                    VALUES (%s, %s, %s, %s, TRUE)
                    """,
                    (area_id, zone['id'], zone.get('name', f"Zone {zone['id']}"), coords_json)
                )
        
        # IMPORTANT: Always sync to JSON file after saving
        _sync_zones_to_json(area_name, db, area_id)
        
        print(f"✅ Zones saved for area {area_name}: {len(zones)} zones (DB + JSON synced)")
        
        return jsonify({
            'success': True,
            'zones_saved': len(zones),
            'message': 'Zones saved to database and synced to JSON file'
        }), 200
        
    except Exception as e:
        print(f"❌ Save zones by name error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to save zones'}), 500

@admin_bp.route('/zones/by-name/<string:area_name>/<int:zone_id>/visibility', methods=['PUT'])
@admin_required
def toggle_zone_visibility_by_name(area_name, zone_id):
    """Toggle zone visibility by area name (Admin only)"""
    try:
        area_id = AREA_NAME_TO_ID.get(area_name.lower())
        if not area_id:
            return jsonify({'error': 'Invalid area name'}), 400
        
        data = request.get_json()
        visible = data.get('visible_to_users', True)
        
        db = get_db()
        db.execute_query(
            """
            UPDATE zones 
            SET visible_to_users = %s
            WHERE area_id = %s AND zone_id = %s
            """,
            (visible, area_id, zone_id)
        )
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        print(f"❌ Toggle zone visibility error: {e}")
        return jsonify({'error': 'Failed to update visibility'}), 500

@admin_bp.route('/zones/by-name/<string:area_name>/<int:zone_id>', methods=['DELETE'])
@admin_required
def delete_zone_by_name(area_name, zone_id):
    """Delete zone by area name (Admin only)"""
    try:
        area_id = AREA_NAME_TO_ID.get(area_name.lower())
        if not area_id:
            return jsonify({'error': 'Invalid area name'}), 400
        
        db = get_db()
        db.execute_query(
            "DELETE FROM zones WHERE area_id = %s AND zone_id = %s",
            (area_id, zone_id)
        )
        
        # Sync to JSON file
        _sync_zones_to_json(area_name, db, area_id)
        
        print(f"✅ Zone {zone_id} deleted from {area_name} (DB + JSON)")
        
        return jsonify({'success': True}), 200
        
    except Exception as e:
        print(f"❌ Delete zone error: {e}")
        return jsonify({'error': 'Failed to delete zone'}), 500

@admin_bp.route('/zones/sync/<string:area_name>', methods=['POST'])
@admin_required
def sync_zones_to_file(area_name):
    """Manually sync zones from database to JSON file (Admin only)"""
    try:
        area_id = AREA_NAME_TO_ID.get(area_name.lower())
        if not area_id:
            return jsonify({'error': 'Invalid area name'}), 400
        
        db = get_db()
        _sync_zones_to_json(area_name, db, area_id)
        
        # Get updated zone count
        zone_count = db.execute_query(
            "SELECT COUNT(*) as count FROM zones WHERE area_id = %s",
            (area_id,),
            fetch_one=True
        )
        
        return jsonify({
            'success': True,
            'zones_synced': zone_count['count'] if zone_count else 0,
            'message': f'Zones synced to zones_{area_name}.json'
        }), 200
        
    except Exception as e:
        print(f"❌ Sync zones error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to sync zones'}), 500

@admin_bp.route('/zones/sync-all', methods=['POST'])
@admin_required  
def sync_all_zones():
    """Sync all zones from database to JSON files (Admin only)"""
    try:
        print("📥 Sync all zones request received")
        db = get_db()
        results = {}
        
        for area_name, area_id in AREA_NAME_TO_ID.items():
            try:
                _sync_zones_to_json(area_name, db, area_id)
                
                # Count zones for this area
                zone_count = db.execute_query(
                    "SELECT COUNT(*) as count FROM zones WHERE area_id = %s",
                    (area_id,),
                    fetch_one=True
                )
                results[area_name] = zone_count['count'] if zone_count else 0
                print(f"✅ Synced {area_name}: {results[area_name]} zones")
            except Exception as area_error:
                print(f"⚠️ Error syncing {area_name}: {area_error}")
                results[area_name] = 0
        
        print(f"✅ All zones sync completed: {results}")
        
        return jsonify({
            'success': True,
            'areas_synced': results,
            'message': 'All zones synced to JSON files'
        }), 200
        
    except Exception as e:
        print(f"❌ Sync all zones error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500