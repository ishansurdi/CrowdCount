# counter_state.py
import datetime
from collections import defaultdict

STATE = {
    "areas": {
        "entrance": {
            "live": 0,
            "zones": {},
            "last_updated": None
        },
        "retail": {
            "live": 0,
            "zones": {},
            "last_updated": None
        },
        "foodcourt": {
            "live": 0,
            "zones": {},
            "last_updated": None
        }
    }
}

HISTORY = defaultdict(list)


def update_area(area, live_count, zone_counts):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    STATE["areas"][area]["live"] = live_count
    STATE["areas"][area]["zones"] = zone_counts
    STATE["areas"][area]["last_updated"] = ts

    HISTORY[area].append({
        "timestamp": ts,
        "live": live_count,
        "zones": zone_counts
    })


def get_area_state(area):
    return STATE["areas"].get(area, {})


def get_history(area, limit=100):
    return HISTORY[area][-limit:]
