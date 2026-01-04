import mysql.connector

conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='123456789',
    database='crowdcount'
)
cursor = conn.cursor(dictionary=True)
cursor.execute('SELECT * FROM historical_counts ORDER BY timestamp DESC LIMIT 10')
rows = cursor.fetchall()
print('Recent historical counts:')
for row in rows:
    print(f"  {row}")
    
cursor.execute('SELECT COUNT(*) as total FROM historical_counts')
print(f"\nTotal records: {cursor.fetchone()['total']}")
conn.close()
