import mysql.connector

conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='123456789',
    database='crowdcount'
)
cursor = conn.cursor(dictionary=True)
cursor.execute('SELECT area_id, area_name FROM areas ORDER BY area_id')
areas = cursor.fetchall()
print('Areas in DB:')
for area in areas:
    print(f"  area_id={area['area_id']}, area_name={area['area_name']}")

# Check zones
cursor.execute('SELECT area_id, zone_id, zone_name FROM zones ORDER BY area_id, zone_id')
zones = cursor.fetchall()
print('\nZones in DB:')
for zone in zones:
    print(f"  area_id={zone['area_id']}, zone_id={zone['zone_id']}, name={zone['zone_name']}")

conn.close()
