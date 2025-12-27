import json
import requests
import time

BASE_URL = "http://localhost:8000/api"
GOLDEN_REPOS_FILE = "backend/rules/golden_repos.json"

def trigger_all():
    try:
        with open(GOLDEN_REPOS_FILE, "r") as f:
            repos = json.load(f)
        
        print(f"Loaded {len(repos)} golden repositories.")
        
        for scan_type in ["static", "dynamic"]:
            print(f"\n--- Triggering {scan_type.upper()} scans ---")
            for url in repos:
                try:
                    payload = {
                        "repo_url": url,
                        "branch": "main",
                        "scan_type": scan_type
                    }
                    response = requests.post(f"{BASE_URL}/scan", json=payload)
                    if response.status_code == 200:
                        scan_id = response.json().get("id")
                        print(f"  [+] Triggered {scan_type} for {url} (ID: {scan_id})")
                    else:
                        print(f"  [-] Failed {scan_type} for {url}: {response.text}")
                except Exception as e:
                    print(f"  [-] Error triggering {scan_type} for {url}: {e}")
                
                # Tiny sleep to avoid overwhelming the request queue immediately
                time.sleep(0.5)

        print("\nAll 46 benchmark scans have been kicked off.")
        
    except Exception as e:
        print(f"Trigger script failed: {e}")

if __name__ == "__main__":
    # Wait a moment for backend to be fully ready if it just restarted
    time.sleep(2)
    trigger_all()
