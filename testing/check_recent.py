from backend.db import get_db

db = get_db()
rows = db.execute_query('''
    SELECT area_id, count, timestamp 
    FROM historical_counts 
    WHERE zone_id IS NULL 
    ORDER BY timestamp DESC 
    LIMIT 20
''', fetch=True)

print('\n📊 Last 20 historical records:')
print('='*60)
if rows:
    for row in rows:
        print(f"{row['timestamp']} - Area {row['area_id']}: {row['count']} people")
else:
    print("No records found!")
