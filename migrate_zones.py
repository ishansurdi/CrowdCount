"""
Migration script to load zones from JSON files into the database
"""

import json
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.db import get_db

AREA_MAPPING = {
    'entrance': 1,
    'retail': 2,
    'foodcourt': 3
}

def migrate_zones():
    """Load zones from JSON files into database"""
    db = get_db()
    
    zones_dir = os.path.join(os.path.dirname(__file__), 'zones')
    
    for area_name, area_id in AREA_MAPPING.items():
        zone_file = os.path.join(zones_dir, f'zones_{area_name}.json')
        
        if not os.path.exists(zone_file):
            print(f"⚠️ Zone file not found: {zone_file}")
            continue
        
        try:
            with open(zone_file, 'r') as f:
                data = json.load(f)
                zones = data.get('zones', [])
            
            if not zones:
                print(f"⚠️ No zones found in {zone_file}")
                continue
            
            # Delete existing zones for this area
            db.execute_query(
                "DELETE FROM zones WHERE area_id = %s",
                (area_id,)
            )
            print(f"🗑️  Cleared existing zones for {area_name}")
            
            # Insert zones from JSON
            for zone in zones:
                zone_id = zone.get('id')
                zone_name = zone.get('name', f"Zone_{zone_id}")
                points = zone.get('points', [])
                
                # Convert points to JSON string
                coords_json = json.dumps(points)
                
                db.execute_query(
                    """
                    INSERT INTO zones (area_id, zone_id, zone_name, polygon_coords, visible_to_users)
                    VALUES (%s, %s, %s, %s, TRUE)
                    """,
                    (area_id, zone_id, zone_name, coords_json)
                )
            
            print(f"✅ Migrated {len(zones)} zones for {area_name}")
            
        except Exception as e:
            print(f"❌ Error migrating {area_name}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n✅ Zone migration completed!")

if __name__ == '__main__':
    migrate_zones()
