"""Test MySQL connection with different password options"""
import mysql.connector
from mysql.connector import Error

passwords = ['', '123456789', 'root', 'password', 'admin']

print("🔍 Testing MySQL Connection...")
print("=" * 50)

for pwd in passwords:
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password=pwd
        )
        if conn.is_connected():
            print(f"✅ SUCCESS! Password: '{pwd}' (or empty if blank)")
            print(f"\n💡 Update your db.py with this password:")
            print(f"   'password': os.getenv('DB_PASSWORD', '{pwd}'),")
            conn.close()
            break
    except Error as e:
        if '1045' in str(e):
            print(f"❌ Access denied with password: '{pwd}'")
        else:
            print(f"❌ Error with '{pwd}': {e}")
else:
    print("\n⚠️ No password worked. Options:")
    print("1. Reset MySQL root password:")
    print("   ALTER USER 'root'@'localhost' IDENTIFIED BY '123456789';")
    print("2. Or set environment variable:")
    print("   $env:DB_PASSWORD='your_actual_password'")
