"""
MySQL Database Connection and Schema Management
Handles all database operations for CrowdCount Milestone-4
"""

import mysql.connector
from mysql.connector import pooling, Error
import bcrypt
from datetime import datetime
import os

class Database:
    def __init__(self):
        self.connection = None
        self.pool = None
        self.config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'user': os.getenv('DB_USER', 'root'),
            'password': os.getenv('DB_PASSWORD', '123456789'),
            'database': os.getenv('DB_NAME', 'crowdcount'),
            'pool_name': 'crowdcount_pool',
            'pool_size': 10,
            'pool_reset_session': True,
            'autocommit': True,
            'use_pure': True
        }
    
    def connect(self):
        """Establish database connection pool"""
        try:
            if not self.pool:
                # Create connection pool
                self.pool = mysql.connector.pooling.MySQLConnectionPool(**self.config)
                print("✅ MySQL Database connection pool created")
            
            # Get connection from pool
            self.connection = self.pool.get_connection()
            if self.connection.is_connected():
                print("✅ MySQL Database connected successfully")
                return True
        except Error as e:
            print(f"❌ Database connection error: {e}")
            return False
    
    def disconnect(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("📴 Database connection closed")
    
    def execute_query(self, query, params=None, fetch=False, fetch_one=False):
        """Execute a query with optional parameters using connection pool"""
        connection = None
        cursor = None
        try:
            # Get fresh connection from pool
            if not self.pool:
                self.connect()
            
            connection = self.pool.get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            
            if fetch_one:
                result = cursor.fetchone()
            elif fetch:
                result = cursor.fetchall()
            else:
                connection.commit()
                result = cursor.lastrowid or cursor.rowcount
            
            return result
        except Error as e:
            print(f"❌ Query error: {e}")
            return None
        finally:
            # Always close cursor and return connection to pool
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()
    
    def initialize_schema(self):
        """Create all required tables"""
        schemas = [
            # Users table
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role ENUM('admin', 'user') NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            
            # Areas table
            """
            CREATE TABLE IF NOT EXISTS areas (
                area_id INT AUTO_INCREMENT PRIMARY KEY,
                area_name VARCHAR(50) UNIQUE NOT NULL,
                video_source VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            
            # User-Area mapping
            """
            CREATE TABLE IF NOT EXISTS user_areas (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                area_id INT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (area_id) REFERENCES areas(area_id) ON DELETE CASCADE,
                UNIQUE KEY unique_user_area (user_id, area_id)
            )
            """,
            
            # Zones table
            """
            CREATE TABLE IF NOT EXISTS zones (
                id INT AUTO_INCREMENT PRIMARY KEY,
                area_id INT NOT NULL,
                zone_id INT NOT NULL,
                zone_name VARCHAR(50) NOT NULL,
                polygon_coords TEXT,
                visible_to_users BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (area_id) REFERENCES areas(area_id) ON DELETE CASCADE,
                UNIQUE KEY unique_area_zone (area_id, zone_id)
            )
            """,
            
            # Live counts
            """
            CREATE TABLE IF NOT EXISTS live_counts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                area_id INT NOT NULL,
                zone_id INT,
                current_count INT NOT NULL DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (area_id) REFERENCES areas(area_id) ON DELETE CASCADE,
                FOREIGN KEY (zone_id) REFERENCES zones(zone_id) ON DELETE SET NULL,
                INDEX idx_area_timestamp (area_id, timestamp)
            )
            """,
            
            # Historical counts
            """
            CREATE TABLE IF NOT EXISTS historical_counts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                area_id INT NOT NULL,
                zone_id INT,
                count INT NOT NULL DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (area_id) REFERENCES areas(area_id) ON DELETE CASCADE,
                FOREIGN KEY (zone_id) REFERENCES zones(zone_id) ON DELETE SET NULL,
                INDEX idx_area_timestamp (area_id, timestamp),
                INDEX idx_zone_timestamp (zone_id, timestamp)
            )
            """,
            
            # Thresholds
            """
            CREATE TABLE IF NOT EXISTS thresholds (
                id INT AUTO_INCREMENT PRIMARY KEY,
                global_threshold INT NOT NULL DEFAULT 50,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                updated_by INT,
                FOREIGN KEY (updated_by) REFERENCES users(user_id) ON DELETE SET NULL
            )
            """,
            
            # Alerts
            """
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
                FOREIGN KEY (zone_id) REFERENCES zones(zone_id) ON DELETE SET NULL,
                FOREIGN KEY (acknowledged_by) REFERENCES users(user_id) ON DELETE SET NULL,
                INDEX idx_status (status),
                INDEX idx_area_created (area_id, created_at)
            )
            """,
            
            # Threshold violations history
            """
            CREATE TABLE IF NOT EXISTS threshold_violations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                area_id INT NOT NULL,
                threshold_id INT NOT NULL,
                people_count INT NOT NULL,
                violation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                zone_details TEXT,
                FOREIGN KEY (area_id) REFERENCES areas(area_id) ON DELETE CASCADE,
                FOREIGN KEY (threshold_id) REFERENCES thresholds(id) ON DELETE CASCADE,
                INDEX idx_area_time (area_id, violation_time),
                INDEX idx_violation_time (violation_time)
            )
            """
        ]
        
        for schema in schemas:
            self.execute_query(schema)
        
        print("✅ Database schema initialized")
        self._seed_default_data()
    
    def _seed_default_data(self):
        """Insert default admin user and areas"""
        # Check if admin exists
        admin_exists = self.execute_query(
            "SELECT user_id FROM users WHERE email = %s",
            ('admin@crowdcount.com',),
            fetch_one=True
        )
        
        if not admin_exists:
            # Create admin user
            admin_password = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
            # Store as string (will be encoded back to bytes on verification)
            admin_password_str = admin_password.decode('utf-8')
            self.execute_query(
                """
                INSERT INTO users (name, email, password_hash, role)
                VALUES (%s, %s, %s, %s)
                """,
                ('Admin User', 'admin@crowdcount.com', admin_password_str, 'admin')
            )
            print("✅ Default admin created (admin@crowdcount.com / admin123)")
        
        # Create default user
        user_exists = self.execute_query(
            "SELECT user_id FROM users WHERE email = %s",
            ('user@crowdcount.com',),
            fetch_one=True
        )
        
        if not user_exists:
            user_password = bcrypt.hashpw('user123'.encode('utf-8'), bcrypt.gensalt())
            user_password_str = user_password.decode('utf-8')
            user_id = self.execute_query(
                """
                INSERT INTO users (name, email, password_hash, role)
                VALUES (%s, %s, %s, %s)
                """,
                ('Regular User', 'user@crowdcount.com', user_password_str, 'user')
            )
            print("✅ Default user created (user@crowdcount.com / user123)")
        
        # Create areas
        areas_data = [
            ('entrance', 'youtube-videos/enterance.mp4'),
            ('retail', 'youtube-videos/retail.mp4'),
            ('foodcourt', 'youtube-videos/foodcourt.mp4')
        ]
        
        for area_name, video_source in areas_data:
            area_exists = self.execute_query(
                "SELECT area_id FROM areas WHERE area_name = %s",
                (area_name,),
                fetch_one=True
            )
            
            if not area_exists:
                area_id = self.execute_query(
                    "INSERT INTO areas (area_name, video_source) VALUES (%s, %s)",
                    (area_name, video_source)
                )
                
                # Assign all areas to admin
                admin = self.execute_query(
                    "SELECT user_id FROM users WHERE role = 'admin' LIMIT 1",
                    fetch_one=True
                )
                if admin:
                    self.execute_query(
                        "INSERT IGNORE INTO user_areas (user_id, area_id) VALUES (%s, %s)",
                        (admin['user_id'], area_id)
                    )
                
                # Assign entrance and retail to regular user
                if area_name in ['entrance', 'retail'] and user_id:
                    self.execute_query(
                        "INSERT IGNORE INTO user_areas (user_id, area_id) VALUES (%s, %s)",
                        (user_id, area_id)
                    )
                
                # Create default zones for this area
                # Entrance has 3 zones, Retail has 1 zone, Foodcourt has 1 zone
                zone_counts = {'entrance': 3, 'retail': 1, 'foodcourt': 1}
                num_zones = zone_counts.get(area_name, 1)
                
                for zone_num in range(1, num_zones + 1):
                    zone_exists = self.execute_query(
                        "SELECT id FROM zones WHERE area_id = %s AND zone_id = %s",
                        (area_id, zone_num),
                        fetch_one=True
                    )
                    
                    if not zone_exists:
                        self.execute_query(
                            """
                            INSERT INTO zones (area_id, zone_id, zone_name, visible_to_users)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (area_id, zone_num, f"Zone {zone_num}", True)
                        )
        
        print("✅ Default areas created")
        
        # Initialize default threshold
        threshold_exists = self.execute_query(
            "SELECT id FROM thresholds LIMIT 1",
            fetch_one=True
        )
        
        if not threshold_exists:
            self.execute_query(
                "INSERT INTO thresholds (global_threshold) VALUES (%s)",
                (50,)
            )
            print("✅ Default threshold set to 50")

# Global database instance
db = Database()

def init_database():
    """Initialize database connection and schema"""
    if db.connect():
        db.initialize_schema()
        return True
    return False

def get_db():
    """Get database instance"""
    return db
