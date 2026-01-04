import requests
import time

print("Testing main.py -> backend communication...")

# Wait a bit for data to flow
time.sleep(3)

# Check if backend is receiving data
response = requests.get('http://127.0.0.1:5000/areas')
data = response.json()

print("\n=== Current AREAS_STATE from /areas endpoint ===")
for area, state in data.items():
    live_people = state.get('live_people', 0)
    zone_counts = state.get('zone_counts', {})
    timestamp = state.get('timestamp', 'N/A')
    print(f"{area}: {live_people} people, zones={zone_counts}, updated={timestamp}")
