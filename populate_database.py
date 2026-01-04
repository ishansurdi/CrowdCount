"""Populate areas and zones tables from existing zone files"""
import mysql.connector
import json
import os

# Connect to database
conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='123456789',
    database='crowdcount'
)
cursor = conn.cursor()

print("=" * 60)
print("🔧 POPULATING DATABASE WITH AREAS AND ZONES")
print("=" * 60)

# Define areas configuration
areas_config = {
    "entrance": {
        "name": "entrance",
        "video_source": "https://youtu.be/WMm5HiAq_Kg",
        "zone_file": "zones/zones_entrance.json"
    },
    "retail": {
        "name": "retail",
        "video_source": "https://www.youtube.com/watch?v=KMJS66jBtVQ",
        "zone_file": "zones/zones_retail.json"
    },
    "foodcourt": {
        "name": "foodcourt",
        "video_source": "https://www.youtube.com/watch?v=BrvJZdiNuRw",
        "zone_file": "zones/zones_foodcourt.json"
    }
}

# Insert areas
print("\n1️⃣ Inserting areas...")
for area_key, area_info in areas_config.items():
    try:
        cursor.execute(
            "INSERT INTO areas (area_name, video_source) VALUES (%s, %s) ON DUPLICATE KEY UPDATE video_source = %s",
            (area_info['name'], area_info['video_source'], area_info['video_source'])
        )
        conn.commit()
        print(f"   ✓ {area_info['name']}")
    except Exception as e:
        print(f"   ❌ {area_info['name']}: {e}")

# Load and insert zones from zone files
print("\n2️⃣ Inserting zones...")
for area_key, area_info in areas_config.items():
    # Get area_id
    cursor.execute("SELECT area_id FROM areas WHERE area_name = %s", (area_info['name'],))
    result = cursor.fetchone()
    if not result:
        print(f"   ⚠️ Skipping {area_info['name']} - not found in areas table")
        continue
    
    area_id = result[0]
    
    # Load zone file
    zone_file_path = area_info['zone_file']
    if not os.path.exists(zone_file_path):
        print(f"   ⚠️ Zone file not found: {zone_file_path}")
        continue
    
    try:
        with open(zone_file_path, 'r') as f:
            content = f.read().strip()
            if not content:
                print(f"   ⚠️ Empty zone file: {zone_file_path}")
                continue
            
            zones_data = json.loads(content)
            if isinstance(zones_data, dict):
                zones = zones_data.get('zones', [])
            elif isinstance(zones_data, list):
                zones = zones_data
            else:
                zones = []
            
            if not zones:
                print(f"   ⚠️ No zones in {area_info['name']}")
                continue
            
            # Insert zones
            for zone in zones:
                zone_id = zone.get('id', 1)
                zone_name = f"Zone {zone_id}"
                points = zone.get('points', [])
                polygon_coords = json.dumps(points)
                
                try:
                    cursor.execute(
                        """
                        INSERT INTO zones (area_id, zone_id, zone_name, polygon_coords, visible_to_users)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE zone_name = %s, polygon_coords = %s
                        """,
                        (area_id, zone_id, zone_name, polygon_coords, True, zone_name, polygon_coords)
                    )
                    conn.commit()
                    print(f"   ✓ {area_info['name']} - Zone {zone_id} ({len(points)} points)")
                except Exception as e:
                    print(f"   ❌ {area_info['name']} - Zone {zone_id}: {e}")
    
    except Exception as e:
        print(f"   ❌ Error loading zones for {area_info['name']}: {e}")

# Verify
print("\n3️⃣ Verification:")
cursor.execute("SELECT COUNT(*) FROM areas")
area_count = cursor.fetchone()[0]
print(f"   📊 Areas in database: {area_count}")

cursor.execute("SELECT COUNT(*) FROM zones")
zone_count = cursor.fetchone()[0]
print(f"   📊 Zones in database: {zone_count}")

print("\n✅ Database populated successfully!")
print("=" * 60)

cursor.close()
conn.close()
