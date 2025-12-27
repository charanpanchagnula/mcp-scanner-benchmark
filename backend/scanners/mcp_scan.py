import os
import json
import subprocess
import uuid
from typing import Dict, Any, List
from .base import BaseScanner
from models.common import ScannerOutput, Vulnerability

class MCPScanWrapper(BaseScanner):
    @property
    def name(self) -> str:
        return "mcp-scan"

    @property
    def supports_static(self) -> bool:
        return True

    @property
    def supports_dynamic(self) -> bool:
        # mcp-scan run/check can be considered dynamic or at least deeper inspection
        return True

    def _parse_mcp_scan_output(self, output: str) -> List[Vulnerability]:
        vulns = []
        try:
            data = json.loads(output)
            # mcp-scan output can be a list of issues or a dict keyed by file path
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                # Check for "issues" key globally or per path
                if "issues" in data:
                    items = data["issues"]
                else:
                    # It might be { "path": { "issues": [...] } }
                    for path_data in data.values():
                        if isinstance(path_data, dict) and "issues" in path_data:
                            items.extend(path_data["issues"])
            
            for item in items:
                # Dynamic mapping of mcp-scan issues to Benchmark Rule IDs
                raw_rule = item.get("rule") or item.get("code") or "mcp-scan-violation"
                message = item.get("message") or str(item)
                
                # Align with Golden rules where possible
                rule_id = raw_rule
                msg_lower = message.lower()
                if "shell" in msg_lower or "os.system" in msg_lower:
                    rule_id = "mcp-shell-injection"
                elif "prompt" in msg_lower:
                    rule_id = "mcp-prompt-injection"
                elif "secret" in msg_lower:
                    rule_id = "mcp-hardcoded-secret"

                vulns.append(Vulnerability(
                    id=str(uuid.uuid4()),
                    rule_id=rule_id,
                    message=message,
                    severity=(item.get("severity") or "MEDIUM").upper(),
                    file_path=item.get("file") or item.get("path") or "mcp.json",
                    start_line=item.get("line") or 0,
                    end_line=item.get("line") or 0,
                    code_snippet=item.get("evidence") or "",
                    scanner=self.name,
                    metadata={**item, "original_rule": raw_rule}
                ))
        except Exception as e:
            print(f"Error parsing mcp-scan output: {e}")
        return vulns

    def scan_static(self, target_path: str) -> ScannerOutput:
        try:
            configs = self.find_mcp_configs(target_path)
            
            if not configs:
                return ScannerOutput(
                    scanner_name=self.name,
                    vulnerabilities=[],
                    raw_output="No MCP configurations found. Skipping mcp-scan."
                )

            all_vulns = []
            all_raw = []
            
            for config in configs:
                # Correct command: mcp-scan <path> --json --opt-out
                # --opt-out helps skip Invariant platform pushing which might 403
                cmd = ["uv", "run", "mcp-scan", config, "--json", "--opt-out"]
                result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=os.path.dirname(config), env=os.environ)
                
                vulns = self._parse_mcp_scan_output(result.stdout)
                all_vulns.extend(vulns)
                all_raw.append(f"--- Result for {config} ---\n{result.stdout}\n{result.stderr}")
            
            return ScannerOutput(
                scanner_name=self.name,
                vulnerabilities=all_vulns,
                raw_output="\n".join(all_raw)
            )
        except Exception as e:
            return ScannerOutput(scanner_name=self.name, vulnerabilities=[], error=str(e))

    def scan_dynamic(self, target_url: str) -> ScannerOutput:
        # For mcp-scan, dynamic means running the scan on the same local configs
        return self.scan_static(target_url)
