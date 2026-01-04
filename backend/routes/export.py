"""
Export Routes
Protected endpoints for data export (Admin only)
"""

from flask import Blueprint, jsonify, make_response
from backend.auth.jwt_utils import admin_required
from backend.db import get_db
from datetime import datetime
import csv
import io

export_bp = Blueprint('export', __name__, url_prefix='/api/export')

@export_bp.route('/csv/<area>', methods=['GET'])
@admin_required
def export_area_csv(area):
    """Export area data as CSV (Admin only)"""
    try:
        db = get_db()
        
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
        records = db.execute_query(
            """
            SELECT 
                hc.timestamp,
                COALESCE(z.zone_name, 'Overall') as zone,
                hc.count
            FROM historical_counts hc
            LEFT JOIN zones z ON hc.zone_id = z.zone_id
            WHERE hc.area_id = %s
            ORDER BY hc.timestamp DESC
            LIMIT 10000
            """,
            (area_id,),
            fetch=True
        )
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(['Timestamp', 'Zone', 'Count'])
        
        # Write data
        for record in (records or []):
            writer.writerow([
                record['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                record['zone'],
                record['count']
            ])
        
        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=crowdcount_{area}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        return response
        
    except Exception as e:
        print(f"❌ Export CSV error: {e}")
        return jsonify({'error': 'Export failed'}), 500

@export_bp.route('/summary/<area>', methods=['GET'])
@admin_required
def export_area_summary(area):
    """Get exportable summary data (Admin only)"""
    try:
        db = get_db()
        
        # Get area_id
        area_data = db.execute_query(
            "SELECT area_id FROM areas WHERE area_name = %s",
            (area,),
            fetch_one=True
        )
        
        if not area_data:
            return jsonify({'error': 'Area not found'}), 404
        
        area_id = area_data['area_id']
        
        # Get summary stats
        summary = db.execute_query(
            """
            SELECT 
                DATE(timestamp) as date,
                AVG(count) as avg_count,
                MAX(count) as max_count,
                MIN(count) as min_count,
                COUNT(*) as records
            FROM historical_counts
            WHERE area_id = %s AND zone_id IS NULL
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
            LIMIT 30
            """,
            (area_id,),
            fetch=True
        )
        
        # Get alert summary
        alerts = db.execute_query(
            """
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as total_alerts,
                SUM(CASE WHEN status = 'acknowledged' THEN 1 ELSE 0 END) as acknowledged
            FROM alerts
            WHERE area_id = %s
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            LIMIT 30
            """,
            (area_id,),
            fetch=True
        )
        
        return jsonify({
            'success': True,
            'area': area,
            'summary': {
                'daily_stats': summary or [],
                'alert_stats': alerts or []
            }
        }), 200
        
    except Exception as e:
        print(f"❌ Export summary error: {e}")
        return jsonify({'error': 'Failed to generate summary'}), 500
