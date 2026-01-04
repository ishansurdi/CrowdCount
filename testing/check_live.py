from backend.db import get_db

db = get_db()

# Check schema first
cols = db.execute_query('DESCRIBE live_counts', fetch=True)
print('=== LIVE_COUNTS SCHEMA ===')
for c in cols:
    print(f"  {c['Field']} ({c['Type']})")

# Check live_counts table (using correct column name)
records = db.execute_query('''
    SELECT a.area_name, lc.current_count, lc.timestamp, lc.zone_id
    FROM live_counts lc
    JOIN areas a ON lc.area_id = a.area_id
    WHERE lc.zone_id IS NULL
    ORDER BY lc.timestamp DESC
    LIMIT 5
''', fetch=True)

print('\n=== LIVE_COUNTS TABLE (zone_id IS NULL) ===')
for r in (records or []):
    print(f"{r['area_name']}: {r['current_count']} people, updated: {r['timestamp']}")
