"""
Test script to verify zone synchronization functionality
"""
import os
import json
import time

def check_zone_files():
    """Check all zone JSON files"""
    zones_dir = "zones"
    areas = ["entrance", "retail", "foodcourt"]
    
    print("=" * 60)
    print("Zone Files Status Check")
    print("=" * 60)
    
    for area in areas:
        zone_file = os.path.join(zones_dir, f"zones_{area}.json")
        
        if os.path.exists(zone_file):
            # Get file modification time
            mtime = os.path.getmtime(zone_file)
            mtime_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
            
            # Load and parse zones
            with open(zone_file, 'r') as f:
                data = json.load(f)
                zones = data.get('zones', [])
            
            print(f"\n✅ {area.upper()}")
            print(f"   File: {zone_file}")
            print(f"   Last Modified: {mtime_str}")
            print(f"   Zone Count: {len(zones)}")
            
            if zones:
                print(f"   Zones:")
                for zone in zones:
                    zone_id = zone.get('id', '?')
                    zone_name = zone.get('name', 'Unnamed')
                    points = zone.get('points', [])
                    print(f"      - Zone {zone_id}: {zone_name} ({len(points)} points)")
        else:
            print(f"\n❌ {area.upper()}")
            print(f"   File: {zone_file}")
            print(f"   Status: NOT FOUND")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    check_zone_files()
