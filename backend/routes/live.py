"""
Live Monitoring Routes
Protected endpoints for real-time crowd data
"""

from flask import Blueprint, jsonify, request
from backend.auth.jwt_utils import token_required
from backend.db import get_db

live_bp = Blueprint('live', __name__, url_prefix='/api/live')

@live_bp.route('/areas', methods=['GET'])
@token_required
def get_user_areas():
    """Get areas assigned to current user"""
    try:
        user = request.current_user
        user_id = user['user_id']
        role = user['role']
        
        db = get_db()
        
        # Admin sees all areas, users see assigned areas
        if role == 'admin':
            areas = db.execute_query(
                "SELECT area_id, area_name, video_source FROM areas",
                fetch=True
            )
        else:
            areas = db.execute_query(
                """
                SELECT a.area_id, a.area_name, a.video_source
                FROM areas a
                JOIN user_areas ua ON a.area_id = ua.area_id
                WHERE ua.user_id = %s
                """,
                (user_id,),
                fetch=True
            )
        
        return jsonify({
            'success': True,
            'areas': areas or []
        }), 200
        
    except Exception as e:
        print(f"❌ Get areas error: {e}")
        return jsonify({'error': 'Failed to fetch areas'}), 500

@live_bp.route('/<area>', methods=['GET'])
@token_required
def get_live_data(area):
    """Get live metrics for specific area"""
    try:
        from backend.app import AREAS_STATE
        
        user = request.current_user
        user_id = user['user_id']
        role = user['role']
        
        # Check if user has access to this area
        if role != 'admin':
            db = get_db()
            has_access = db.execute_query(
                """
                SELECT 1 FROM user_areas ua
                JOIN areas a ON ua.area_id = a.area_id
                WHERE ua.user_id = %s AND a.area_name = %s
                """,
                (user_id, area),
                fetch_one=True
            )
            
            if not has_access:
                return jsonify({'error': 'Access denied to this area'}), 403
        
        # Get live state
        if area not in AREAS_STATE:
            return jsonify({'error': 'Area not found'}), 404
        
        state = AREAS_STATE[area]
        
        return jsonify({
            'success': True,
            'area': area,
            'data': state
        }), 200
        
    except Exception as e:
        print(f"❌ Get live data error: {e}")
        return jsonify({'error': 'Failed to fetch live data'}), 500

@live_bp.route('/threshold', methods=['GET'])
@token_required
def get_threshold():
    """Get current threshold value (all authenticated users)"""
    try:
        db = get_db()
        
        # Get current threshold
        threshold = db.execute_query(
            "SELECT global_threshold, last_updated FROM thresholds ORDER BY id DESC LIMIT 1",
            fetch_one=True
        )
        
        return jsonify({
            'success': True,
            'global_threshold': threshold['global_threshold'] if threshold else 50,
            'last_updated': threshold['last_updated'].isoformat() if threshold and threshold['last_updated'] else None
        }), 200
        
    except Exception as e:
        print(f"❌ Get threshold error: {e}")
        return jsonify({'error': 'Failed to fetch threshold'}), 500

@live_bp.route('/threshold/history', methods=['GET'])
@token_required
def get_threshold_history():
    """Get threshold violation history for user's areas"""
    try:
        user = request.current_user
        user_id = user['user_id']
        role = user['role']
        
        db = get_db()
        
        # Get limit from query params
        limit = request.args.get('limit', 50, type=int)
        
        # Admin sees all violations, users see only their assigned areas
        if role == 'admin':
            violations = db.execute_query(
                """
                SELECT tv.*, a.area_name, t.global_threshold
                FROM threshold_violations tv
                JOIN areas a ON tv.area_id = a.area_id
                JOIN thresholds t ON tv.threshold_id = t.id
                ORDER BY tv.violation_time DESC
                LIMIT %s
                """,
                (limit,),
                fetch=True
            )
        else:
            violations = db.execute_query(
                """
                SELECT tv.*, a.area_name, t.global_threshold
                FROM threshold_violations tv
                JOIN areas a ON tv.area_id = a.area_id
                JOIN thresholds t ON tv.threshold_id = t.id
                JOIN user_areas ua ON a.area_id = ua.area_id
                WHERE ua.user_id = %s
                ORDER BY tv.violation_time DESC
                LIMIT %s
                """,
                (user_id, limit),
                fetch=True
            )
        
        # Format violations
        formatted = []
        for v in (violations or []):
            formatted.append({
                'id': v['id'],
                'area_name': v['area_name'],
                'people_count': v['people_count'],
                'threshold': v['global_threshold'],
                'violation_time': v['violation_time'].isoformat(),
                'zone_details': v.get('zone_details', '')
            })
        
        return jsonify({
            'success': True,
            'violations': formatted
        }), 200
        
    except Exception as e:
        print(f"❌ Get threshold history error: {e}")
        return jsonify({'error': 'Failed to fetch threshold history'}), 500
