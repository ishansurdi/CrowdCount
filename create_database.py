"""Create CrowdCount database if it doesn't exist"""
import mysql.connector
from mysql.connector import Error

try:
    # Connect without specifying database
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='123456789'
    )
    
    if conn.is_connected():
        cursor = conn.cursor()
        
        # Create database if not exists
        cursor.execute("CREATE DATABASE IF NOT EXISTS crowdcount")
        print("✅ Database 'crowdcount' created/verified")
        
        # Verify it exists
        cursor.execute("SHOW DATABASES LIKE 'crowdcount'")
        result = cursor.fetchone()
        if result:
            print("✅ Database 'crowdcount' is ready")
        
        cursor.close()
        conn.close()
        
        print("\n🚀 Now you can start the backend:")
        print("   python backend/app.py")
        
except Error as e:
    print(f"❌ Error: {e}")
