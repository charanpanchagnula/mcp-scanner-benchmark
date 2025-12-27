import json
import time
import requests
import sys

BASE_URL = "http://localhost:8000/api"
GOLDEN_REPOS_FILE = "backend/rules/golden_repos.json"

def load_repos():
    with open(GOLDEN_REPOS_FILE, "r") as f:
        return json.load(f)

def trigger_scan(url, scan_type):
    print(f"[{scan_type.upper()}] Triggering scan for {url}...")
    headers = {"Content-Type": "application/json"}
    payload = {
        "repo_url": url,
        "branch": "main",
        "scan_type": scan_type
    }
    response = requests.post(f"{BASE_URL}/scan", json=payload, headers=headers)
    response.raise_for_status()
    return response.json()["id"]

def wait_for_scan(scan_id):
    print(f"Waiting for scan {scan_id} to complete...", end="", flush=True)
    while True:
        response = requests.get(f"{BASE_URL}/scans/{scan_id}")
        response.raise_for_status()
        status = response.json()["status"]
        if status in ["completed", "error"]:
            print(f" Done ({status})")
            return status
        print(".", end="", flush=True)
        time.sleep(5)

def main():
    try:
        repos = load_repos()
        print(f"Starting sequential benchmarking for {len(repos)} repositories.")
        
        for scan_type in ["static", "dynamic"]:
            print(f"\n--- Starting {scan_type.upper()} scans ---")
            for repo_url in repos:
                try:
                    scan_id = trigger_scan(repo_url, scan_type)
                    status = wait_for_scan(scan_id)
                except Exception as e:
                    print(f"Error during scan of {repo_url}: {e}")
                    
        print("\nAll golden repository scans completed.")
    except Exception as e:
        print(f"Script failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
