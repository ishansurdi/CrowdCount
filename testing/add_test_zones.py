import mysql.connector
import json

conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='123456789',
    database='crowdcount'
)

cursor = conn.cursor()

# Add test zones
zones_data = [
    (1, 1, 'Zone 1', json.dumps([[100,100],[500,100],[500,300],[100,300]]), True),
    (1, 2, 'Zone 2', json.dumps([[100,350],[500,350],[500,550],[100,550]]), True),
    (1, 3, 'Zone 3', json.dumps([[600,100],[900,100],[900,300],[600,300]]), True),
    (2, 1, 'Zone 1', json.dumps([[200,200],[600,200],[600,400],[200,400]]), True),
    (3, 1, 'Zone 1', json.dumps([[150,150],[550,150],[550,350],[150,350]]), True),
]

cursor.executemany(
    "INSERT IGNORE INTO zones (area_id, zone_id, zone_name, polygon_coords, visible_to_users) VALUES (%s, %s, %s, %s, %s)",
    zones_data
)
conn.commit()

# Verify
cursor.execute("SELECT * FROM zones")
zones = cursor.fetchall()
print(f"✅ Added {cursor.rowcount} zones")
print(f"📊 Total zones in database: {len(zones)}")
for zone in zones:
    print(f"   - Area {zone[1]}, Zone {zone[2]}: {zone[3]}")

cursor.close()
conn.close()
