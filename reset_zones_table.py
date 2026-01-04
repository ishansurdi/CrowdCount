"""
Reset and reinitialize database with correct schema
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.db import get_db
import mysql.connector

def reset_database():
    """Drop zones table and recreate with correct schema"""
    db = get_db()
    
    print("🔧 Disabling foreign key checks...")
    db.execute_query("SET FOREIGN_KEY_CHECKS = 0")
    
    print("🗑️  Dropping dependent tables...")
    db.execute_query("DROP TABLE IF EXISTS live_counts")
    db.execute_query("DROP TABLE IF EXISTS historical_counts")
    db.execute_query("DROP TABLE IF EXISTS alerts")
    
    print("🗑️  Dropping zones table...")
    db.execute_query("DROP TABLE IF EXISTS zones")
    
    print("📝 Creating zones table with correct schema...")
    db.execute_query("""
        CREATE TABLE zones (
            id INT AUTO_INCREMENT PRIMARY KEY,
            area_id INT NOT NULL,
            zone_id INT NOT NULL,
            zone_name VARCHAR(50) NOT NULL,
            polygon_coords TEXT,
            visible_to_users BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (area_id) REFERENCES areas(area_id) ON DELETE CASCADE,
            UNIQUE KEY unique_area_zone (area_id, zone_id),
            INDEX idx_zone_id (zone_id)
        )
    """)
    
    print("📝 Recreating dependent tables...")
    
    # Live counts
    db.execute_query("""
        CREATE TABLE IF NOT EXISTS live_counts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            area_id INT NOT NULL,
            zone_id INT,
            current_count INT NOT NULL DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (area_id) REFERENCES areas(area_id) ON DELETE CASCADE,
            INDEX idx_area_timestamp (area_id, timestamp)
        )
    """)
    
    # Historical counts
    db.execute_query("""
        CREATE TABLE IF NOT EXISTS historical_counts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            area_id INT NOT NULL,
            zone_id INT,
            count INT NOT NULL DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (area_id) REFERENCES areas(area_id) ON DELETE CASCADE,
            INDEX idx_area_timestamp (area_id, timestamp),
            INDEX idx_zone_timestamp (zone_id, timestamp)
        )
    """)
    
    # Alerts
    db.execute_query("""
        CREATE TABLE IF NOT EXISTS alerts (
            alert_id INT AUTO_INCREMENT PRIMARY KEY,
            area_id INT NOT NULL,
            zone_id INT,
            observed_count INT NOT NULL,
            threshold INT NOT NULL,
            status ENUM('active', 'acknowledged') NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            acknowledged_at TIMESTAMP NULL,
            acknowledged_by INT,
            FOREIGN KEY (area_id) REFERENCES areas(area_id) ON DELETE CASCADE,
            FOREIGN KEY (acknowledged_by) REFERENCES users(user_id) ON DELETE SET NULL,
            INDEX idx_status (status),
            INDEX idx_area_created (area_id, created_at)
        )
    """)
    
    print("🔧 Re-enabling foreign key checks...")
    db.execute_query("SET FOREIGN_KEY_CHECKS = 1")
    
    print("✅ Database schema reset complete!")

if __name__ == '__main__':
    reset_database()
