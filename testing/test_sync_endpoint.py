"""
Test the zone sync endpoint
"""
import requests
import json

API_BASE = "http://127.0.0.1:5000"

def test_health():
    """Test admin API health"""
    try:
        response = requests.get(f"{API_BASE}/api/admin/health")
        print(f"Health Check Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_sync(token):
    """Test zone sync endpoint"""
    try:
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        print(f"\nTesting sync-all endpoint...")
        response = requests.post(f"{API_BASE}/api/admin/zones/sync-all", headers=headers)
        
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        
        if 'application/json' in response.headers.get('content-type', ''):
            data = response.json()
            print(f"Response JSON: {json.dumps(data, indent=2)}")
        else:
            print(f"Response Text (first 500 chars): {response.text[:500]}")
        
    except Exception as e:
        print(f"❌ Sync test failed: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Zone Sync Endpoint")
    print("=" * 60)
    
    # Test health check first
    if not test_health():
        print("\n⚠️ Backend may not be running. Start it with: python backend/app.py")
        exit(1)
    
    # Get token from user
    print("\n" + "=" * 60)
    print("To test the sync endpoint, you need an admin token.")
    print("1. Open the admin portal in browser")
    print("2. Open browser console (F12)")
    print("3. Type: localStorage.getItem('crowdcount_token')")
    print("4. Copy the token (without quotes)")
    print("=" * 60)
    
    token = input("\nEnter admin token (or press Enter to skip): ").strip()
    
    if token:
        test_sync(token)
    else:
        print("\nSkipped sync test (no token provided)")
