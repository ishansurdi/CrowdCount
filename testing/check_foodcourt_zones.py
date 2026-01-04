import mysql.connector

conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='123456789',
    database='crowdcount'
)
cursor = conn.cursor(dictionary=True)
cursor.execute('SELECT area_id, zone_id, zone_name, polygon_coords FROM zones WHERE area_id=3 ORDER BY zone_id')
zones = cursor.fetchall()
print('Foodcourt zones in DB:')
for z in zones:
    print(f"  zone_id={z['zone_id']}, name={z['zone_name']}")
    
conn.close()
