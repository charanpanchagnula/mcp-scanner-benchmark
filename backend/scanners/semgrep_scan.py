import json
import subprocess
import uuid
from typing import Dict, Any, List
from .base import BaseScanner
from models.common import ScannerOutput, Vulnerability

class SemgrepScanner(BaseScanner):
    @property
    def name(self) -> str:
        return "Semgrep"

    @property
    def supports_static(self) -> bool:
        return True

    @property
    def supports_dynamic(self) -> bool:
        return False

    def scan_static(self, target_path: str) -> ScannerOutput:
        config_path = "rules/mcp_security.yaml"
        # If running from backend root, rules is in ./rules
        
        try:
            cmd = [
                "uv", "run", "semgrep", 
                "scan", 
                "--config", config_path, 
                "--json", 
                "--disable-version-check",
                "--metrics=off",
                target_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            vulns = []
            try:
                data = json.loads(result.stdout)
                for item in data.get("results", []):
                    check_id = item.get("check_id")
                    
                    # Track category for internal metrics (optional)
                    category = "Insecure Configuration"
                    check_id_lower = check_id.lower()
                    if "injection" in check_id_lower or "exec" in check_id_lower:
                         category = "Tool Execution Abuse"
                    elif "prompt" in check_id_lower or "context" in check_id_lower:
                         category = "Prompt Injection"
                    
                    vulns.append(Vulnerability(
                        id=str(uuid.uuid4()),
                        rule_id=check_id,  # Use the specific check_id
                        message=item.get("extra", {}).get("message", ""),
                        severity=item.get("extra", {}).get("severity", "UNKNOWN"),
                        file_path=item.get("path", ""),
                        start_line=item.get("start", {}).get("line", 0),
                        end_line=item.get("end", {}).get("line", 0),
                        code_snippet=item.get("extra", {}).get("lines", ""),
                        scanner="Semgrep",
                        metadata={**item.get("extra", {}).get("metadata", {}), "category": category}
                    ))
            except json.JSONDecodeError:
                return ScannerOutput(
                    scanner_name=self.name,
                    vulnerabilities=[],
                    raw_output=result.stdout,
                    error="Failed to parse JSON"
                )

            return ScannerOutput(
                scanner_name=self.name,
                vulnerabilities=vulns
            )

        except Exception as e:
            return ScannerOutput(
                scanner_name=self.name,
                vulnerabilities=[],
                error=str(e)
            )

    def scan_dynamic(self, target_url: str) -> ScannerOutput:
        return ScannerOutput(
            scanner_name=self.name,
            vulnerabilities=[],
            error="Semgrep does not support dynamic scanning."
        )
