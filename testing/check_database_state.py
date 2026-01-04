"""Check database state for historical_counts issue"""
import mysql.connector
from mysql.connector import Error

try:
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='123456789',
        database='crowdcount'
    )
    
    cursor = conn.cursor(dictionary=True)
    
    print("=" * 60)
    print("🔍 CHECKING DATABASE STATE")
    print("=" * 60)
    
    # Check areas table
    print("\n1️⃣ AREAS TABLE:")
    cursor.execute("SELECT * FROM areas")
    areas = cursor.fetchall()
    if areas:
        for area in areas:
            print(f"   ✓ {area}")
    else:
        print("   ⚠️ NO AREAS FOUND!")
    
    # Check zones table
    print("\n2️⃣ ZONES TABLE:")
    cursor.execute("SELECT * FROM zones")
    zones = cursor.fetchall()
    if zones:
        for zone in zones:
            print(f"   ✓ {zone}")
    else:
        print("   ⚠️ NO ZONES FOUND!")
    
    # Check historical_counts table
    print("\n3️⃣ HISTORICAL_COUNTS TABLE (Last 10 entries):")
    cursor.execute("SELECT * FROM historical_counts ORDER BY timestamp DESC LIMIT 10")
    historical = cursor.fetchall()
    if historical:
        for row in historical:
            print(f"   {row}")
    else:
        print("   ⚠️ NO HISTORICAL DATA!")
    
    # Check live_counts table
    print("\n4️⃣ LIVE_COUNTS TABLE:")
    cursor.execute("SELECT * FROM live_counts ORDER BY timestamp DESC LIMIT 10")
    live = cursor.fetchall()
    if live:
        for row in live:
            print(f"   {row}")
    else:
        print("   ⚠️ NO LIVE DATA!")
    
    print("\n" + "=" * 60)
    print("💡 DIAGNOSIS:")
    if not areas:
        print("   ❌ Problem: Areas table is empty")
        print("   🔧 Solution: Need to populate areas table with entrance/retail/foodcourt")
    elif not zones:
        print("   ⚠️ Warning: Zones table is empty (zone-specific data won't be recorded)")
    
    if not historical and areas:
        print("   ❌ Problem: Historical counts not being recorded")
        print("   🔧 Check: Recorder service might not be inserting correctly")
    
    print("=" * 60)
    
    cursor.close()
    conn.close()
    
except Error as e:
    print(f"❌ Database error: {e}")
