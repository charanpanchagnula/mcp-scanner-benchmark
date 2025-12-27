from fastapi import FastAPI, HTTPException, BackgroundTasks, Response
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid
import json
import os
from datetime import datetime

from scanners.registry import ScannerRegistry
from agent.evaluator import ScannerEvaluator

app = FastAPI(title="MCP Scanner Benchmark", description="Agentic evaluation of MCP scanners")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Persistence
DATA_FILE = "scan_index.json"
RESULTS_DIR = "scan_results"

if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"scans": [], "leaderboard": {"static": {}, "dynamic": {}}}

def save_data(data):
    # Save index (without scanner_results to keep it light)
    index_scans = []
    for s in data["scans"]:
        # Extract summary info
        index_scans.append({
            "id": s["id"],
            "timestamp": s["timestamp"],
            "target": s["target"],
            "branch": s["branch"],
            "scan_type": s.get("scan_type", "static"),
            "status": s["status"],
            "evaluation": s.get("evaluation"),
            "error": s.get("error")
        })
    
    index_data = {
        "scans": index_scans,
        "leaderboard": data.get("leaderboard", {"static": {}, "dynamic": {}})
    }
    
    with open(DATA_FILE, "w") as f:
        json.dump(index_data, f, indent=2)

def save_scan_result(scan_id: str, full_result: Dict[str, Any]):
    file_path = os.path.join(RESULTS_DIR, f"{scan_id}.json")
    with open(file_path, "w") as f:
        json.dump(full_result, f, indent=2)

def load_scan_result(scan_id: str) -> Optional[Dict[str, Any]]:
    file_path = os.path.join(RESULTS_DIR, f"{scan_id}.json")
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return None

from services.github_service import GitHubService

# Models
class ScanRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    scan_type: str = "static" # "static" or "dynamic"

class ScanSummary(BaseModel):
    id: str
    timestamp: str
    target: str # Repo URL
    branch: str
    scan_type: str = "static"
    status: str = "pending"
    evaluation: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class ScanResult(BaseModel):
    id: str
    timestamp: str
    target: str # Repo URL
    branch: str
    scan_type: str = "static"
    scanner_results: Dict[str, Any]
    evaluation: Optional[Dict[str, Any]] = None
    status: str = "pending"
    error: Optional[str] = None

# Global data
db = load_data()
github_service = GitHubService()

# --- API Endpoints (Prefixed with /api) ---

@app.get("/api")
def read_root():
    return {"message": "MCP Scanner Benchmark API is running"}

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

def run_benchmark(scan_id: str, repo_url: str, branch: str, scan_type: str = "static"):
    print(f"Starting benchmark {scan_id} for {repo_url} (type: {scan_type})", flush=True)
    
    try:
        # 0. Clone Repo
        target_path = github_service.clone_repo(repo_url, branch, scan_id)
        print(f"Repository cloned to: {target_path}", flush=True)

        all_scanners = ScannerRegistry.get_scanners()
        
        # Filter scanners based on capability
        if scan_type == "static":
            scanners = [s for s in all_scanners if s.supports_static]
        else:
            scanners = [s for s in all_scanners if s.supports_dynamic]

        results = {}
        
        # 1. Run Scanners in Parallel
        print(f"Running {len(scanners)} scanners in parallel (scan_type={scan_type})...", flush=True)
        
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def execute_single_scanner(scanner):
            print(f"  > Starting {scanner.name}...", flush=True)
            s_res = {}
            
            # Static Scan
            if scan_type == "static":
                try:
                    res_static = scanner.scan_static(target_path)
                    if hasattr(res_static, "model_dump"):
                        s_res["static"] = res_static.model_dump()
                    else:
                        s_res["static"] = res_static
                except Exception as e:
                    s_res["static"] = {"error": str(e)}

            # Dynamic Scan
            if scan_type == "dynamic":
                try:
                    res_dynamic = scanner.scan_dynamic(target_path)
                    if hasattr(res_dynamic, "model_dump"):
                        s_res["dynamic"] = res_dynamic.model_dump()
                    else:
                        s_res["dynamic"] = res_dynamic
                except Exception as e:
                    s_res["dynamic"] = {"error": str(e)}
                
            print(f"  < Finished {scanner.name}", flush=True)
            return scanner.name, s_res

        # Execute in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            # We wrap the scanner execution in a timeout at the ThreadPool level if possible, 
            # but per-scanner is better for logging.
            future_to_scanner = {executor.submit(execute_single_scanner, s): s for s in scanners}
            # Wait with a total timeout of 10 minutes for all scanners
            for future in as_completed(future_to_scanner, timeout=600):
                try:
                    scanner_name, s_result = future.result()
                except Exception as e:
                    print(f"Scanner execution failed or timed out: {e}", flush=True)
                    continue
                
                # Relativize paths here
                for scan_mode in ["static", "dynamic"]:
                    if scan_mode in s_result and "vulnerabilities" in s_result[scan_mode]:
                        for vuln in s_result[scan_mode]["vulnerabilities"]:
                            f_path = vuln.get("file_path", "")
                            if f_path.startswith(target_path):
                                # Make it relative, strip leading slash
                                rel = os.path.relpath(f_path, target_path)
                                vuln["file_path"] = rel
                            elif f_path.startswith("/app/"): # Docker common path
                                # Try to make it relative to app root then target path
                                app_rel = os.path.relpath(f_path, "/app")
                                # If it's inside target_path relative to app...
                                inner_rel = os.path.relpath(target_path, "/app")
                                if app_rel.startswith(inner_rel):
                                    vuln["file_path"] = os.path.relpath(app_rel, inner_rel)

                results[scanner_name] = s_result

        # 2. Evaluate with Agent
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key:
            from agent.evaluator import ScannerEvaluator, LeaderboardAgent
            print(f"Evaluating {scan_type} results (results keys: {list(results.keys())})...", flush=True)
            try:
                evaluator = ScannerEvaluator()
                # Categorized evaluation (returns CategoryEvaluation dict)
                comp_evaluation = evaluator.evaluate(results, scan_type=scan_type)
                print(f"Evaluation returned score: {comp_evaluation.get('scores')}", flush=True)

                # Holistic Leaderboard Update
                lb_agent = LeaderboardAgent()
                current_lb = db.get("leaderboard", {"static": {}, "dynamic": {}, "total_scans": 0})
                # Ensure it matches Leaderboard model structure
                if "total_scans" not in current_lb: current_lb["total_scans"] = 0
                
                new_scores = comp_evaluation.get("scores", {})
                updated_lb = lb_agent.update_leaderboard(current_lb, new_scores, scan_type)
                db["leaderboard"] = updated_lb
                
                # Construct full EvaluationResult
                if scan_type == "static":
                    evaluation = {"static": comp_evaluation, "dynamic": None}
                else:
                    evaluation = {"static": None, "dynamic": comp_evaluation}

            except Exception as e:
                print(f"Evaluation failed: {e}", flush=True)
                evaluation = {"error": f"Evaluation failed: {e}", "skipped": True}
        else:
            print("Skipping evaluation (DEEPSEEK_API_KEY not set)", flush=True)
            evaluation = {"skipped": True, "reason": "No API key"}
        
        # 3. Update DB
        for s in db["scans"]:
            if s["id"] == scan_id:
                s["status"] = "completed"
                s["evaluation"] = evaluation
                # Save full result to individual file
                full_result = {**s, "scanner_results": results}
                save_scan_result(scan_id, full_result)
                break
                
    except Exception as e:
        print(f"Benchmark failed: {e}")
        for s in db["scans"]:
            if s["id"] == scan_id:
                s["status"] = "error"
                s["error"] = str(e)
                save_scan_result(scan_id, s)
                break
            
    save_data(db)
    print(f"Benchmark {scan_id} finished.")

@app.post("/api/scan", response_model=ScanResult)
async def trigger_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    scan_id = str(uuid.uuid4())
    new_scan = {
        "id": scan_id,
        "timestamp": datetime.utcnow().isoformat(),
        "target": request.repo_url,
        "branch": request.branch,
        "scan_type": request.scan_type,
        "scanner_results": {},
        "evaluation": None,
        "status": "pending"
    }
    
    db["scans"].insert(0, new_scan)
    save_data(db)
    
    background_tasks.add_task(run_benchmark, scan_id, request.repo_url, request.branch, request.scan_type)
    
    return new_scan

@app.get("/api/scans", response_model=List[ScanSummary])
def list_scans(limit: int = 20, offset: int = 0, scan_type: Optional[str] = None):
    scans = db["scans"]
    
    if scan_type:
        # Filter by scan_type, handling legacy items without scan_type as "static"
        filtered = [
            s for s in scans 
            if s.get("scan_type") == scan_type or (not s.get("scan_type") and scan_type == "static")
        ]
        return filtered[offset : offset + limit]
        
    return scans[offset : offset + limit]

@app.get("/api/scans/{scan_id}", response_model=ScanResult)
def get_scan(scan_id: str):
    res = load_scan_result(scan_id)
    if res:
        return res
    
    # Fallback to index if full file not found (legacy or error)
    for s in db["scans"]:
        if s["id"] == scan_id:
            return {**s, "scanner_results": {}}
            
    raise HTTPException(status_code=404, detail="Scan not found")

@app.get("/api/leaderboard")
def get_leaderboard():
    return db["leaderboard"]

@app.delete("/api/scans/{scan_id}")
def delete_scan(scan_id: str):
    scan_to_delete = None
    for s in db["scans"]:
        if s["id"] == scan_id:
            scan_to_delete = s
            break
    
    if not scan_to_delete:
        raise HTTPException(status_code=404, detail="Scan not found")
        
    db["scans"].remove(scan_to_delete)
    
    # Remove file
    file_path = os.path.join(RESULTS_DIR, f"{scan_id}.json")
    if os.path.exists(file_path):
        os.remove(file_path)
    
    save_data(db)
    return {"status": "deleted", "id": scan_id}

@app.delete("/api/scans")
def delete_all_scans():
    db["scans"] = []
    db["leaderboard"] = {"static": {}, "dynamic": {}}
    
    # Clear directory
    for f in os.listdir(RESULTS_DIR):
        if f.endswith(".json"):
            os.remove(os.path.join(RESULTS_DIR, f))
            
    save_data(db)
    return {"status": "all_deleted"}

# --- Static Files / SPA Fallback ---

# Mount logic:
# If 'static' directory exists (copied from frontend build), serve it.
# Check for '/static' location
STATIC_DIR = "/static"

if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    # SPA Fallback for 404s (Client-side routing)
    @app.exception_handler(404)
    async def custom_404_handler(_, __):
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
else:
    print(f"WARNING: Static files directory '{STATIC_DIR}' not found. UI will not be served.")
