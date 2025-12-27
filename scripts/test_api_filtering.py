import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_filtering():
    try:
        # 1. Fetch static
        res = requests.get(f"{BASE_URL}/scans?scan_type=static&limit=5")
        if res.status_code == 200:
            scans = res.json()
            print(f"Static scans found: {len(scans)}")
            for s in scans:
                print(f"  ID: {s['id']}, Type: {s.get('scan_type', 'static')}")
        else:
            print(f"Failed to fetch static: {res.status_code}")

        # 2. Fetch dynamic
        res = requests.get(f"{BASE_URL}/scans?scan_type=dynamic&limit=5")
        if res.status_code == 200:
            scans = res.json()
            print(f"Dynamic scans found: {len(scans)}")
            for s in scans:
                print(f"  ID: {s['id']}, Type: {s.get('scan_type')}")
        else:
            print(f"Failed to fetch dynamic: {res.status_code}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_filtering()
