import os
import json
import subprocess
import uuid
from typing import Dict, Any, List
from .base import BaseScanner
from models.common import ScannerOutput, Vulnerability

class MCPWatchWrapper(BaseScanner):
    @property
    def name(self) -> str:
        return "mcp-watch"

    @property
    def supports_static(self) -> bool:
        return True

    @property
    def supports_dynamic(self) -> bool:
        return False

    def scan_static(self, target_path: str) -> ScannerOutput:
        try:
            configs = self.find_mcp_configs(target_path)
            
            if not configs:
                return ScannerOutput(
                    scanner_name=self.name,
                    vulnerabilities=[],
                    raw_output="No MCP configurations found. Skipping mcp-watch."
                )

            all_vulns = []
            all_raw = []
            script_path = "/app/scanners/mcp_watch_tool/dist/main.js"
            
            if not os.path.exists(script_path):
                 return ScannerOutput(scanner_name=self.name, vulnerabilities=[], error=f"Tool not found at {script_path}")

            for config in configs:
                # mcp-watch needs the directory containing the config, not the config itself
                target_dir = os.path.dirname(config)
                try:
                    cmd = ["mcp-watch", target_dir]
                    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
                    vulns = self._parse_watch_output(result.stdout, os.path.basename(config))
                    all_vulns.extend(vulns)
                    all_raw.append(f"--- Result for {config} ---\n{result.stdout}\n{result.stderr}")
                except subprocess.TimeoutExpired:
                    all_raw.append(f"--- Result for {config} (Timed Out after 60s) ---")
                
            return ScannerOutput(
                scanner_name=self.name,
                vulnerabilities=all_vulns,
                raw_output="\n".join(all_raw)
            )

        except Exception as e:
            return ScannerOutput(scanner_name=self.name, vulnerabilities=[], error=str(e))

    def _parse_watch_output(self, stdout: str, config_name: str) -> List[Vulnerability]:
        vulns = []
        try:
            json_start = stdout.find('{')
            json_end = stdout.rfind('}')
            if json_start != -1 and json_end != -1:
                json_str = stdout[json_start:json_end+1]
                data = json.loads(json_str)
            else:
                data = {}

            results = data.get("vulnerabilities", []) if isinstance(data, dict) else []
            for res in results:
                try:
                    original_cat = res.get("category", "").lower()
                    original_msg = res.get("message", "").lower()
                    
                    # Map to canonical benchmark rules if possible
                    rule_id = "mcp-watch-violation"
                    if "prompt-injection" in original_cat or "injection" in original_msg:
                        rule_id = "mcp-prompt-injection"
                    elif "command-injection" in original_cat or "shell" in original_msg:
                        rule_id = "mcp-command-injection"
                    elif "access-control" in original_cat or "permission" in original_msg:
                        rule_id = "mcp-access-control-violation"
                    elif "toxic" in original_msg:
                        rule_id = "mcp-toxic-flow"
                    elif "secret" in original_cat or "password" in original_cat:
                        rule_id = "mcp-hardcoded-secret"
                    elif original_cat:
                        rule_id = f"mcp-watch-{original_cat.replace(' ', '-')}"

                    vulns.append(Vulnerability(
                        id=res.get("id") or str(uuid.uuid4()),
                        rule_id=rule_id,
                        message=res.get("message", ""),
                        severity=res.get("severity", "MEDIUM").upper(),
                        file_path=res.get("file") or config_name,
                        start_line=res.get("line") or 0,
                        end_line=res.get("line") or 0,
                        code_snippet=res.get("evidence", ""),
                        scanner=self.name,
                        metadata={**res, "original_category": original_cat, "config": config_name}
                    ))
                except Exception:
                    pass
        except Exception:
            pass
        return vulns

    def scan_dynamic(self, target_url: str) -> ScannerOutput:
        # mcp-watch scan <repo>
        # We can implement similarly if we pass the URL.
        # But for now we are using cloned local path, so scan_static logic applies mainly.
        return ScannerOutput(scanner_name=self.name, vulnerabilities=[], raw_output="mcp-watch does not support dynamic scanning.", error="Not Supported")
