# Backend Architecture & Code Walkthrough

This document provides an exhaustive, granular explanation of the backend codebase for the MCP Scanner Benchmark. The backend is built using **FastAPI** and is responsible for orchestrating security scans, aggregating results, and performing AI-driven evaluation using **Agno (DeepSeek)**.

## Core Application Files

### `main.py`
This is the entry point of the application. It initializes the web server, defines API endpoints, and orchestrates the entire benchmark workflow.

*   **FastAPI Initialization**: Creates the `FastAPI` app instance with metadata (title, description), enabling the automatic Swagger UI documentation at `/docs`.
*   **CORS Middleware**: Configures Cross-Origin Resource Sharing to allow the Next.js frontend (running on port 3000) to communicate with this backend (on port 8000). It allows all origins, methods, and headers for development ease.
*   **Persistent Storage Settings**: Defines constants for `DATA_FILE` (`scan_index.json`) and `RESULTS_DIR` (`scan_results/`). It also includes a check to creating `RESULTS_DIR` if it doesn't exist, ensuring the app never crashes on a fresh install.
*   **`load_data()`**: A helper function that reads `scan_index.json`. 
    *   It checks file existence first.
    *   If missing, it returns a default "empty" structure with blank scan lists and leaderboards.
*   **`save_data()`**: Writes the lightweight index of scans to disk. 
    *   **Optimization**: It actively strips out the `scanner_results` field from individual scan objects before saving to the index. This prevents `scan_index.json` from growing into megabytes size, ensuring the endpoint remains fast.
*   **`save_scan_result()`**: Saves the full, heavy JSON output of a single scan (including all raw tool logs and vulnerabilities) to a separate file in `scan_results/{id}.json`. This segregates "list view" data from "detail view" data.
*   **`POST /api/scan` Endpoint**: 
    *   Accepts a `ScanRequest` (URL, branch, type).
    *   Generates a new UUID.
    *   Sets initial status to "pending".
    *   **Async Processing**: Uses FastAPI's `BackgroundTasks` to trigger `run_benchmark` *after* returning the response, preventing the HTTP request from timing out during long scans.
*   **`GET /api/scans` Endpoint**: 
    *   Implements pagination (`limit`, `offset`) to handle large histories efficiently.
    *   Reverses the list to show newest scans first.
    *   Supports filtering by `scan_type` (static vs dynamic).
*   **`run_benchmark()` (Async Task)**: The core logic driver.
    1.  **Cloning**: calls `GitHubService.clone_repo` to fetch the code.
    2.  **Discovery**: calls `ScannerRegistry.discover_scanners` to find applicable tools.
    3.  **Parallel Execution**: Uses `ThreadPoolExecutor` to run scanners concurrently. This is crucial for performance as some scanners (like Fuzzers) are slow.
    4.  **Error Handling**: Catches exceptions per-scanner so one failure doesn't crash the whole benchmark.
    5.  **Aggregation**: Collects results from all success/failed scanners into a single `scanner_results` dict.
    6.  **AI Evaluation**: Instantiates `ScannerEvaluator` and sends the aggregated results to DeepSeek to determine the winner and score.
    7.  **Leaderboard Update**: Calls `LeaderboardAgent` to update the global holistic scores based on the new findings.
    8.  **Finalize**: Updates the status to "completed" (or "error") and saves everything.

### `agent/evaluator.py`
This file contains the "Agentic" logic. It uses the `agno` library to interface with DeepSeek.

*   **`ScannerEvaluator` Class**: The main AI judge.
*   **Initialization**: 
    *   Loads `DEEPSEEK_API_KEY` from environment variables.
    *   Initializes the `DeepSeek` model via Agno.
    *   Sets up the system prompt with a specific persona: "Elite AppSec Reviewer".
*   **Evaluation Instructions**: The prompt explicitly commands the agent to:
    *   Audit each finding for validity (checking for False Positives).
    *   Rate the "Descriptiveness" of remediation advice.
    *   Assign a precise 0-100% score for each tool.
    *   Select a "Winner" and justify the choice.
*   **`_extract_json()`**: A utility method designed to be resilient against LLM output variance.
    *   It tries `json.loads` first.
    *   It looks for markdown code blocks (` ```json `).
    *   It falls back to regex searching for `{ ... }` boundaries if the model writes conversational text before/after the JSON.
*   **`evaluate()` Method**: 
    *   Constructs a massive prompt string containing the entire JSONdump of the scan results.
    *   Executes the `self.agent.run()` call.
    *   Returns a structured `CategoryEvaluation` dictionary.
*   **`LeaderboardAgent` Class**: A specialized agent for long-term statistics.
*   **`update_leaderboard()`**:
    *   Takes the `current_leaderboard` state and `new_scores`.
    *   Queries the agent to calculate the new holistic view.
*   **`_manual_update()` Fallback**: A safety mechanism.
    *   If the LLM fails or times out, this Python function calculates a weighted moving average.
    *   This ensures the leaderboard data is never corrupted or lost due to API glitches.

### `models/common.py`
Defines the Pydantic data models used throughout the application for type safety and validation.

*   **`Vulnerability`**: The atomic unit of a finding.
    *   `rule_id`: Standardized ID (e.g., `mcp-prompt-injection`).
    *   `severity`: Critical, High, Medium, Low, Info.
    *   `file_path`, `start_line`: Location of the issue.
    *   `metadata`: Flexible dictionary for storing raw scanner-specific extras.
*   **`ScannerOutput`**: Represents the output of a single tool.
    *   `vulnerabilities`: List of `Vulnerability` objects.
    *   `raw_output`: Complete stdout/stderr capture for debugging.
    *   `error`: Capture of any exception strings if the tool crashed.
*   **`ScanResult`**: The complete record of a benchmark.
    *   `scanner_results`: Dictionary mapping scanner names to `ScannerOutput`.
    *   `evaluation`: Nested dictionary containing the AI's `CategoryEvaluation`.
*   **`CategoryEvaluation`**: The structured output from the AI Agent.
    *   `scores`: Map of `ScannerName -> Percentage (float)`.
    *   `best_features`: List of strings explaining why the winner won.
*   **`Leaderboard`**: Schema for the global state.
    *   `static`: Dict of `Scanner -> Score`.
    *   `dynamic`: Dict of `Scanner -> Score`.
    *   `total_scans`: Integer counter.

### `services/github_service.py`
Handles all interactions with the filesystem and Git.

*   **Temporary Directory Strategy**:
    *   Uses `backend/temp_scans/{guid}` for every clone.
    *   This isolation prevents race conditions where parallel scans might overwrite each other's files.
*   **`clone_repo()`**:
    *   Accepts `repo_url` and `branch`.
    *   Validates the git executable is present.
    *   Runs `git clone --depth 1` (Shallow Clone) to save bandwidth and time.
    *   Returns the absolute path to the cloned directory, which is passed to the scanners.
*   **Error Handling**:
    *   Captures `stderr` from git commands.
    *   Raises `ValueError` if the clone fails (e.g., repository not found, authentication failure), which propagates up to the API response.

### `scanners/registry.py`
Dynamically loads scanner plugins.

*   **`ScannerRegistry` Class**: A singleton-like helper.
*   **`discover_scanners()`**:
    *   Scans the `backend/scanners` directory for python files.
    *   Imports them via `importlib`.
    *   Inspects classes to see if they inherit from `BaseScanner`.
    *   Returns a list of instantiated scanner classes (e.g., `[MCPScanWrapper(), SemgrepScanner(), ...]`).
*   **Type Filtering**: Allows filtering scanners by capability (`supports_static` or `supports_dynamic`) so we don't run a Fuzzer on a static code analysis request.
*   **Extensibility**: This design means adding a new scanner requires **zero changes** to `main.py`. You just drop a new `.py` file into `scanners/`, and it is automatically picked up.

---

## Detailed Scanner Implementations (`backend/scanners/`)

This system uses a plugin architecture. Each file below wraps a specific security tool into a common interface.

### `mcp_scan.py` (mcp-scan)
*   **Tool Description**: The official reference scanner from Invariant Labs. It parses the `mcp.json` configuration and checks for common misconfigurations and security best practices.
*   **Supported Modes**: Static (Analysis) and Dynamic (Deep Inspection).
*   **Command Execution**: 
    *   It uses `uv run mcp-scan <path> --json --opt-out`.
    *   The `--json` flag ensures structured output.
    *   The `--opt-out` flag prevents the tool from hanging while trying to push telemetry to the Invariant cloud.
*   **Normalization Logic**:
    *   The raw JSON from `mcp-scan` uses proprietary rule codes. This wrapper maps them to the project's standard IDs.
    *   `"os.system"` or `"shell"` matching rules are mapped to `mcp-shell-injection`.
    *   `"prompt"` matching rules are mapped to `mcp-prompt-injection`.
    *   `"secret"` matching rules are mapped to `mcp-hardcoded-secret`.
*   **Parsing Details**: It handles both list-based and dictionary-based JSON return formats, making it robust against different versions of the `mcp-scan` CLI.

### `mcp_shield.py` (mcp-shield)
*   **Tool Description**: A policy enforcement tool that visualizes the "permission tree" of an MCP server. It's great for seeing what files or URLs a server can access.
*   **Supported Modes**: Static Only.
*   **Command Execution**: Runs `mcp-shield --path <config>`.
*   **Output Parsing (Complex)**: 
    *   Unlike other tools, `mcp-shield` outputs a visual ASCII text tree, not JSON.
    *   This wrapper implements a custom text parser that iterates line-by-line.
    *   It looks for the `✖` symbol (Cross Mark) or the text "Error" to identify blocking vulnerabilities.
    *   It extracts "Risk:" levels (Low/Medium/High) directly from the text.
    *   It maintains context of which "Server" or "Tool" it is currently parsing by tracking indentation and header lines (e.g., "1. Server: ...").
*   **Mapped Vulnerabilities**:
    *   Detects "Hidden instructions" -> mapped to `mcp-prompt-injection`.
    *   Detects "Insecure transport" -> mapped to `mcp-insecure-transport`.
    *   Detects "Sensitive file" -> mapped to `mcp-access-control-violation`.

### `mcp_watch.py` (mcp-watch)
*   **Tool Description**: A governance tool focused on "Toxic Flow" and high-level architectural risks.
*   **Supported Modes**: Static Only.
*   **Unique Quirk**: This tool requires the *directory path* as an argument, not the specific configuration file. The wrapper handles this by running `os.path.dirname(config_path)`.
*   **Execution**: Launches a specific Node.js script located at `/app/scanners/mcp_watch_tool/dist/main.js`.
*   **Output Parsing**:
    *   It scans the stdout for the first `{` and last `}` to extract the JSON payload, ignoring any logs printed before/after.
    *   It maps categories like "toxic-flow" and "access-control" to the benchmark's standard schema.

### `mcp_fortress.py` (mcp-fortress)
*   **Tool Description**: A scanner designed primarily for published NPM and PyPI packages.
*   **Supported Modes**: Static Only.
*   **Execution Strategy**:
    *   It first inspects the target directory for a `package.json`.
    *   It extracts the `name` field from the package file.
    *   It then runs `mcp-fortress scan <package_name>`.
*   **Limitation Handling**: If the target repo is not a valid NPM package (i.e., has no `package.json` with a name), the scanner gracefully skips and logs a "Not supported" message instead of failing.
*   **Output Parsing**:
    *   Parses a text-heavy, emoji-rich output format.
    *   Regex matches "Risk Score: <number>".
    *   Detects "🚨" or "CRITICAL" keywords to assign High severity.
    *   Detects "⚠️" or "WARNING" keywords to assign Medium severity.

### `semgrep_scan.py` (Semgrep)
*   **Tool Description**: A highly popular, fast static analysis tool. We use it with a custom rulepack.
*   **Supported Modes**: Static Only.
*   **Configuration**: 
    *   Uses a dedicated config file: `backend/rules/mcp_security.yaml`.
    *   This YAML file contains custom regular expressions (Regex) and structural patterns to find MCP vulnerabilities.
*   **Execution**: `uv run semgrep scan --config backend/rules/mcp_security.yaml --json --quiet`.
*   **Feature**: It produces the cleanest JSON output of all scanners, requiring very little normalization. The `check_id` from the YAML rule (e.g., `mcp-eval-usage`) becomes the `rule_id` directly.

### `active_fuzzer.py` (ActiveFuzzer)
*   **Tool Description**: A custom-built **dynamic analysis engine** utilizing the Python MCP SDK. It connects to the server as a real client.
*   **Supported Modes**: Dynamic Only.
*   **Heuristic Discovery**:
    *   Before running, it tries to figure out *how* to run the server.
    *   If no `mcp.json` is present, it scans for `package.json` (Node) or `server.py` (Python) and auto-generates a temporary configuration to launch the server.
*   **Session Management**:
    *   Uses `stdio_client` to spawn the server process.
    *   Uses `asyncio.wait_for` to strictly enforce a 30-second timeout. If a server hangs or loops, the fuzzer kills it to preserve the benchmark integrity.
*   **Attack Vector: Command Injection**:
    *   It iterates through every tool exposed by the server.
    *   If it finds a parameter named `code` or `command`, it sends a python payload: `print('VULN_DETECTED')`.
    *   It captures the result and checks if the string `VULN_DETECTED` echoes back, confirming RCE.
*   **Attack Vector: LFI (Local File Inclusion)**:
    *   If it finds a parameter named `path` or `file`, it tries to read the `server.py` itself.
    *   It checks if the returned content contains python keywords like `import` or `def`. If so, it confirms source code leakage.
