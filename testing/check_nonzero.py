import mysql.connector

conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='123456789',
    database='crowdcount'
)

cursor = conn.cursor(dictionary=True)

# Check AREAS_STATE by looking at recent updates
cursor.execute('''
    SELECT area_id, zone_id, count, timestamp 
    FROM historical_counts 
    WHERE count > 0
    ORDER BY timestamp DESC 
    LIMIT 10
''')
rows = cursor.fetchall()

print("\n=== NON-ZERO RECORDS IN HISTORICAL_COUNTS ===")
if rows:
    for r in rows:
        print(f"area_id={r['area_id']}, zone_id={r['zone_id']}, count={r['count']}, time={r['timestamp']}")
else:
    print("No non-zero records found!")

cursor.close()
conn.close()
