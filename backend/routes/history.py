"""
Historical Data Routes
Protected endpoints for analytics and trends
"""

from flask import Blueprint, jsonify, request
from backend.auth.jwt_utils import token_required
from backend.db import get_db
from datetime import datetime, timedelta

history_bp = Blueprint('history', __name__, url_prefix='/api/history')

@history_bp.route('/<area>', methods=['GET'])
@token_required
def get_historical_data(area):
    """Get historical data for area"""
    try:
        user = request.current_user
        user_id = user['user_id']
        role = user['role']
        
        # Get query parameters
        limit = request.args.get('limit', 100, type=int)
        hours = request.args.get('hours', 1, type=int)
        
        # Check access
        db = get_db()
        
        if role != 'admin':
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
                return jsonify({'error': 'Access denied'}), 403
        
        # Get area_id
        area_data = db.execute_query(
            "SELECT area_id FROM areas WHERE area_name = %s",
            (area,),
            fetch_one=True
        )
        
        if not area_data:
            return jsonify({'error': 'Area not found'}), 404
        
        area_id = area_data['area_id']
        
        # Get historical data
        since = datetime.now() - timedelta(hours=hours)
        
        history = db.execute_query(
            """
            SELECT 
                timestamp as recorded_at,
                count as total_count
            FROM historical_counts
            WHERE area_id = %s 
                AND zone_id IS NULL
                AND timestamp >= %s
            ORDER BY timestamp ASC
            LIMIT %s
            """,
            (area_id, since, limit),
            fetch=True
        )
        
        # Format timestamps for JSON serialization
        formatted_history = []
        for record in (history or []):
            formatted_history.append({
                'recorded_at': record['recorded_at'].isoformat() if record['recorded_at'] else None,
                'total_count': record['total_count']
            })
        
        return jsonify({
            'success': True,
            'area': area,
            'history': formatted_history,
            'total_records': len(formatted_history)
        }), 200
        
    except Exception as e:
        print(f"❌ Get history error: {e}")
        return jsonify({'error': 'Failed to fetch history'}), 500

@history_bp.route('/stats/<area>', methods=['GET'])
@token_required
def get_area_stats(area):
    """Get statistical summary for area"""
    try:
        user = request.current_user
        user_id = user['user_id']
        role = user['role']
        
        db = get_db()
        
        # Check access
        if role != 'admin':
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
                return jsonify({'error': 'Access denied'}), 403
        
        # Get area_id
        area_data = db.execute_query(
            "SELECT area_id FROM areas WHERE area_name = %s",
            (area,),
            fetch_one=True
        )
        
        if not area_data:
            return jsonify({'error': 'Area not found'}), 404
        
        area_id = area_data['area_id']
        
        # Calculate stats
        stats = db.execute_query(
            """
            SELECT 
                AVG(count) as avg_count,
                MAX(count) as max_count,
                MIN(count) as min_count,
                COUNT(*) as total_records
            FROM historical_counts
            WHERE area_id = %s 
                AND zone_id IS NULL
                AND timestamp >= NOW() - INTERVAL 24 HOUR
            """,
            (area_id,),
            fetch_one=True
        )
        
        return jsonify({
            'success': True,
            'area': area,
            'stats': {
                'average': round(stats['avg_count'], 2) if stats['avg_count'] else 0,
                'maximum': stats['max_count'] or 0,
                'minimum': stats['min_count'] or 0,
                'records': stats['total_records'] or 0
            }
        }), 200
        
    except Exception as e:
        print(f"❌ Get stats error: {e}")
        return jsonify({'error': 'Failed to fetch stats'}), 500
