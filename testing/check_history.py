import mysql.connector

conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='123456789',
    database='crowdcount'
)

cursor = conn.cursor(dictionary=True)
cursor.execute('SELECT area_id, zone_id, count, timestamp FROM historical_counts ORDER BY timestamp DESC LIMIT 20')
rows = cursor.fetchall()

print("\n=== HISTORICAL_COUNTS TABLE (Latest 20 records) ===")
for r in rows:
    print(f"area_id={r['area_id']}, zone_id={r['zone_id']}, count={r['count']}, time={r['timestamp']}")

cursor.close()
conn.close()
