from flask import Flask, jsonify, send_from_directory, request, make_response, redirect
from flask_cors import CORS
import os
import sys
from datetime import datetime, timedelta
import json
import io
import csv
from collections import deque

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Milestone-4 components
try:
    from backend.db import init_database, get_db
    from backend.auth.auth_routes import auth_bp
    from backend.routes.live import live_bp
    from backend.routes.history import history_bp
    from backend.routes.export import export_bp
    from backend.routes.admin import admin_bp
    from backend.services.recorder import start_recorder
    from backend.services.alerts import get_alert_manager
    MILESTONE4_ENABLED = True
    print("✅ Milestone-4 modules loaded successfully")
except ImportError as e:
    print(f"⚠️ Milestone-4 features not available: {e}")
    MILESTONE4_ENABLED = False

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Register Milestone-4 blueprints if available
if MILESTONE4_ENABLED:
    app.register_blueprint(auth_bp)
    app.register_blueprint(live_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(admin_bp)

# In-memory state for multiple areas with detailed configuration
AREAS_CONFIG = {
    "entrance": {
        "name": "Mall Entrance",
        "description": "Main entrance monitoring",
        "video_url": "https://youtu.be/WMm5HiAq_Kg",
        "zone_file": "zones/zones_entrance.json",
        "total_zones": 0,
        "zones_info": []
    },
    "retail": {
        "name": "Retail Area", 
        "description": "Shopping area monitoring",
        "video_url": "https://www.youtube.com/watch?v=KMJS66jBtVQ",
        "zone_file": "zones/zones_retail.json",
        "total_zones": 0,
        "zones_info": []
    },
    "foodcourt": {
        "name": "Food Court",
        "description": "Dining area monitoring", 
        "video_url": "https://www.youtube.com/watch?v=BrvJZdiNuRw",
        "zone_file": "zones/zones_foodcourt.json",
        "total_zones": 0,
        "zones_info": []
    }
}

# Live state for each area
AREAS_STATE = {
    "entrance": {
        "live_people": 0,
        "zone_counts": {},
        "timestamp": datetime.now().isoformat(),
        "status": "initializing"
    },
    "retail": {
        "live_people": 0,
        "zone_counts": {},
        "timestamp": datetime.now().isoformat(),
        "status": "initializing"
    },
    "foodcourt": {
        "live_people": 0,
        "zone_counts": {},
        "timestamp": datetime.now().isoformat(),
        "status": "initializing"
    }
}

# Historical data storage (keep last 1000 entries per area)
HISTORY_LOGS = {
    "entrance": deque(maxlen=1000),
    "retail": deque(maxlen=1000),
    "foodcourt": deque(maxlen=1000)
}

# Threshold alerts configuration
ALERTS_CONFIG = {
    "entrance": {"limit": None, "active": False},
    "retail": {"limit": None, "active": False},
    "foodcourt": {"limit": None, "active": False}
}

def load_zone_info(zone_file):
    """Load zone information from zone file"""
    zone_path = os.path.join(os.path.dirname(__file__), '..', zone_file)
    try:
        if os.path.exists(zone_path):
            with open(zone_path, 'r') as f:
                content = f.read().strip()
                if content:
                    zones = json.loads(content)
                    if isinstance(zones, list):
                        return zones
                    elif isinstance(zones, dict):
                        return zones.get('zones', [])
        return []
    except Exception as e:
        print(f"Error loading {zone_file}: {e}")
        return []

def update_areas_config():
    """Update areas configuration with current zone info"""
    for area_id, config in AREAS_CONFIG.items():
        zones = load_zone_info(config['zone_file'])
        config['total_zones'] = len(zones)
        config['zones_info'] = [{
            'id': zone.get('id', i+1),
            'points_count': len(zone.get('points', [])),
            'color': zone.get('color', [0, 255, 0])
        } for i, zone in enumerate(zones)]

AVAILABLE_AREAS = ["entrance", "retail", "foodcourt"]

# Initialize zone configurations
update_areas_config()

@app.route("/", methods=["GET"])
def serve_dashboard():
    """Serve the main dashboard HTML (requires authentication in Milestone-4)."""
    from flask import redirect, request as flask_request
    
    if MILESTONE4_ENABLED:
        # Check if user has valid token
        token = flask_request.cookies.get('crowdcount_token')
        if not token:
            # Check Authorization header as fallback
            auth_header = flask_request.headers.get('Authorization')
            if auth_header:
                try:
                    token = auth_header.split(' ')[1]
                except:
                    pass
        
        if not token:
            # No token found, redirect to login
            return redirect('/login.html')
        
        # Verify token and redirect to appropriate portal
        try:
            from backend.auth.jwt_utils import decode_token
            payload = decode_token(token)
            if not payload:
                # Invalid token, redirect to login
                return redirect('/login.html')
            
            # Valid token - redirect to role-based portal
            user_role = payload.get('role', 'user')
            if user_role == 'admin':
                return redirect('/admin.html')
            else:
                return redirect('/user.html')
        except:
            return redirect('/login.html')
    
    # If Milestone-4 not available, serve old dashboard
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')
    return send_from_directory(frontend_path, 'index.html')


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for API monitoring."""
    return jsonify({
        "status": "CrowdCount Backend Running",
        "areas": AVAILABLE_AREAS
    })


@app.route("/areas", methods=["GET"])
def list_areas():
    """List all available areas with detailed configuration."""
    update_areas_config()  # Refresh zone info
    
    areas_info = {}
    for area_id in AVAILABLE_AREAS:
        areas_info[area_id] = {
            **AREAS_CONFIG[area_id],
            **AREAS_STATE[area_id],
            'area_id': area_id
        }
    
    return jsonify({
        "areas": areas_info,
        "total_areas": len(AVAILABLE_AREAS)
    })


@app.route("/live/<area>", methods=["GET"])
def live_metrics(area):
    """Get live metrics for a specific area."""
    if area not in AVAILABLE_AREAS:
        return jsonify({"error": "Invalid area"}), 404
    
    # Update zone configuration
    update_areas_config()
    
    # Combine configuration and current state
    area_data = {
        **AREAS_CONFIG[area],
        **AREAS_STATE[area],
        'area_id': area
    }
    
    return jsonify(area_data)


@app.route("/update/<area>", methods=["POST"])
def update_area(area):
    """Update live metrics for a specific area from the detection system."""
    if area not in AVAILABLE_AREAS:
        print(f"❌ Invalid area received: {area}")
        return jsonify({"error": "Invalid area"}), 404
    
    try:
        data = request.get_json()
        if not data:
            print(f"❌ No data provided for {area}")
            return jsonify({"error": "No data provided"}), 400
        
        live_people = data.get('live_people', 0)
        zone_counts = data.get('zone_counts', {})
        
        print(f"✅ RECEIVED UPDATE: {area} -> {live_people} people, zones: {zone_counts}")
        
        # Update area state
        update_area_state(area, live_people, zone_counts)
        
        return jsonify({
            "success": True, 
            "area": area, 
            "live_people": live_people,
            "zone_counts": zone_counts,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        print(f"❌ Error updating {area}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/history/<area>", methods=["GET"])
def get_history(area):
    """Get historical data for charts."""
    if area not in AVAILABLE_AREAS:
        return jsonify({"error": "Invalid area"}), 404
    
    # Get last N records (default 100)
    limit = request.args.get('limit', 100, type=int)
    history = list(HISTORY_LOGS[area])[-limit:]
    
    return jsonify({
        "area": area,
        "history": history,
        "total_records": len(history)
    })


@app.route("/threshold", methods=["POST"])
def set_threshold():
    """Set threshold alert for an area."""
    try:
        data = request.get_json()
        area = data.get('area')
        limit = data.get('limit')
        
        if area not in AVAILABLE_AREAS:
            return jsonify({"error": "Invalid area"}), 404
        
        if limit is None or not isinstance(limit, (int, float)):
            return jsonify({"error": "Invalid limit value"}), 400
        
        ALERTS_CONFIG[area]['limit'] = int(limit)
        
        # Check current count against new threshold
        current_count = AREAS_STATE[area]['live_people']
        ALERTS_CONFIG[area]['active'] = current_count > limit
        
        return jsonify({
            "success": True,
            "area": area,
            "limit": limit,
            "current_count": current_count,
            "alert_active": ALERTS_CONFIG[area]['active']
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/alerts/<area>", methods=["GET"])
def get_alerts(area):
    """Get alert status for an area."""
    if area not in AVAILABLE_AREAS:
        return jsonify({"error": "Invalid area"}), 404
    
    alert_config = ALERTS_CONFIG[area]
    current_count = AREAS_STATE[area]['live_people']
    
    return jsonify({
        "area": area,
        "active": alert_config['active'],
        "limit": alert_config['limit'],
        "current_count": current_count,
        "exceeded_by": current_count - alert_config['limit'] if alert_config['limit'] else 0
    })


@app.route("/export/csv/<area>", methods=["GET"])
def export_csv(area):
    """Export area data as CSV."""
    if area not in AVAILABLE_AREAS:
        return jsonify({"error": "Invalid area"}), 404
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['Timestamp', 'Total People', 'Zone Counts'])
    
    # Write historical data
    for record in HISTORY_LOGS[area]:
        writer.writerow([
            record['timestamp'],
            record['total'],
            json.dumps(record['zone_counts'])
        ])
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename={area}_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return response


@app.route("/export/pdf/<area>", methods=["GET"])
def export_pdf(area):
    """Export area summary as PDF (simplified - returns JSON for now)."""
    if area not in AVAILABLE_AREAS:
        return jsonify({"error": "Invalid area"}), 404
    
    # Get statistics
    history = list(HISTORY_LOGS[area])
    total_records = len(history)
    
    if total_records > 0:
        avg_count = sum(r['total'] for r in history) / total_records
        max_count = max(r['total'] for r in history)
        min_count = min(r['total'] for r in history)
    else:
        avg_count = max_count = min_count = 0
    
    summary = {
        "area": area,
        "area_name": AREAS_CONFIG[area]['name'],
        "current_count": AREAS_STATE[area]['live_people'],
        "statistics": {
            "total_records": total_records,
            "average_count": round(avg_count, 2),
            "max_count": max_count,
            "min_count": min_count
        },
        "timestamp": datetime.now().isoformat()
    }
    
    return jsonify(summary)


@app.route("/<path:filename>")
def serve_frontend(filename):
    """Serve frontend static files."""
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')
    try:
        return send_from_directory(frontend_path, filename)
    except:
        return jsonify({"error": "File not found"}), 404

@app.route("/videos/<video_name>")
def serve_video(video_name):
    """Serve video files for playback."""
    video_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'youtube-videos')
    try:
        return send_from_directory(video_path, video_name)
    except Exception as e:
        print(f"Error serving video {video_name}: {e}")
        return jsonify({"error": "Video not found"}), 404


def update_area_state(area, live_people, zone_counts):
    """
    Function to update area state and store in history.
    This is called by the video processing system via POST /update/<area>.
    """
    global AREAS_STATE  # Declare we're modifying the module-level variable!
    import os
    
    if area in AVAILABLE_AREAS:
        # Convert zone_counts keys to strings for consistency
        zone_counts_str = {str(k): v for k, v in zone_counts.items()}
        
        # Update current state
        AREAS_STATE[area] = {
            "live_people": live_people,
            "zone_counts": zone_counts_str,
            "timestamp": datetime.now().isoformat(),
            "status": "active"
        }
        
        # DEBUGGING: Verify the update actually happened
        print(f"🔍 IMMEDIATELY AFTER UPDATE - PID {os.getpid()} - AREAS_STATE[{area}]: {AREAS_STATE[area]}")
        print(f"🔍 id(AREAS_STATE) = {id(AREAS_STATE)}")
        
        # Add to history
        HISTORY_LOGS[area].append({
            "timestamp": datetime.now().isoformat(),
            "total": live_people,
            "zone_counts": zone_counts_str
        })
        
        # Check threshold alerts (Milestone-4)
        if MILESTONE4_ENABLED:
            alert_manager = get_alert_manager()
            alert_manager.check_threshold(area, live_people, zone_counts_str)
        
        # Legacy threshold check
        if ALERTS_CONFIG[area]['limit'] is not None:
            ALERTS_CONFIG[area]['active'] = live_people > ALERTS_CONFIG[area]['limit']
        
        print(f"📊 Updated {area}: {live_people} people, zones: {zone_counts_str}")


if __name__ == "__main__":
    print("🚀 CrowdCount Backend Starting...")
    print(f"📊 Monitoring Areas: {', '.join(AVAILABLE_AREAS)}")
    print("🌐 Dashboard: http://127.0.0.1:5000/")
    print("📡 API Health: http://127.0.0.1:5000/health")
    print("📋 Areas API: http://127.0.0.1:5000/areas")
    
    # Initialize Milestone-4 features
    if MILESTONE4_ENABLED:
        print("\n" + "="*60)
        print("🔐 MILESTONE-4: Multi-User Secure Platform")
        print("="*60)
        
        # Initialize database
        if init_database():
            print("✅ MySQL Database initialized")
            print("✅ JWT Authentication enabled")
            print("✅ Historical recorder starting...")
            # Pass a lambda that returns the CURRENT AREAS_STATE from THIS module
            start_recorder(lambda: AREAS_STATE)
            print("\n🔑 Login Page: http://127.0.0.1:5000/login.html")
            print("\n📝 Demo Accounts:")
            print("   Admin: admin@crowdcount.com / admin123")
            print("   User:  user@crowdcount.com / user123")
        else:
            print("⚠️ Database connection failed - running in legacy mode")
        
        print("="*60 + "\n")
    
    # IMPORTANT: debug=False to prevent Flask from creating multiple processes!
    # Even with use_reloader=False, debug=True causes process forking issues
    # where AREAS_STATE has different memory addresses in different processes
    app.run(debug=False, host='127.0.0.1', port=5000)


