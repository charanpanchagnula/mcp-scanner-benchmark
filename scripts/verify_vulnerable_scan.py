import json
import time
import requests
import sys

BASE_URL = "http://localhost:8000/api"

def trigger_local_scan():
    print(f"[STATIC] Triggering local scan for vulnerable examples...")
    headers = {"Content-Type": "application/json"}
    payload = {
        "repo_url": "local:///app/vulnerable_examples",
        "branch": "main",
        "scan_type": "static"
    }
    response = requests.post(f"{BASE_URL}/scan", json=payload, headers=headers)
    response.raise_for_status()
    return response.json()["id"]

def wait_for_scan(scan_id):
    print(f"Waiting for scan {scan_id} to complete...", end="", flush=True)
    while True:
        response = requests.get(f"{BASE_URL}/scans/{scan_id}")
        response.raise_for_status()
        data = response.json()
        status = data["status"]
        if status in ["completed", "error"]:
            print(f" Done ({status})")
            return data
        print(".", end="", flush=True)
        time.sleep(2)

def main():
    try:
        scan_id = trigger_local_scan()
        result = wait_for_scan(scan_id)
        
        print("\n--- Scan Summary ---")
        print(f"Target: {result['target']}")
        print(f"Status: {result['status']}")
        
        results = result.get("scanner_results", {})
        for scanner, res in results.items():
            static_res = res.get("static", {})
            vulns = static_res.get("vulnerabilities", [])
            print(f"\n[{scanner}] Found {len(vulns)} vulnerabilities")
            for v in vulns:
                print(f"  - {v['message']} (Severity: {v['severity']})")
                
        if not any(res.get("static", {}).get("vulnerabilities") for res in results.values()):
            print("\nNo vulnerabilities were detected by any scanner.")
            
    except Exception as e:
        print(f"Script failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
