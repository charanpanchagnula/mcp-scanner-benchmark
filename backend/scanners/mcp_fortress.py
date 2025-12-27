import os
import json
import subprocess
import uuid
from typing import Dict, Any, List
from .base import BaseScanner
from models.common import ScannerOutput, Vulnerability

class MCPFortressWrapper(BaseScanner):
    @property
    def name(self) -> str:
        return "mcp-fortress"

    @property
    def supports_static(self) -> bool:
        return True

    @property
    def supports_dynamic(self) -> bool:
        return False

    def scan_static(self, target_path: str) -> ScannerOutput:
        try:
            # mcp-fortress scan <package>
            # For local projects, we need to see if it supports directory scanning.
            # Based on docs, it primarily scans npm/pypi packages.
            # However, we can try to scan the local directory if it has a package.json.
            
            configs = self.find_mcp_configs(target_path)
            if not configs:
                return ScannerOutput(
                    scanner_name=self.name,
                    vulnerabilities=[],
                    raw_output="No MCP configurations found for mcp-fortress."
                )

            all_vulns = []
            all_raw = []

            for config in configs:
                config_dir = os.path.dirname(config)
                package_json_path = os.path.join(config_dir, "package.json")
                
                scan_target = None
                # If package.json exists, try to scan the package name from registry
                if os.path.exists(package_json_path):
                    try:
                        with open(package_json_path, "r") as f:
                            pj = json.load(f)
                            if pj.get("name"):
                                scan_target = pj["name"]
                    except:
                        pass
                
                if not scan_target:
                    all_raw.append(f"--- Skip for {config} ---\nLocal scanning not supported by mcp-fortress unless it is a registered npm/pypi package.")
                    continue

                # Run mcp-fortress scan <package-name>
                cmd = ["mcp-fortress", "scan", scan_target]
                result = subprocess.run(cmd, capture_output=True, text=True, check=False)
                
                # If it failed because it tried to download a path@latest, we'll note it
                if "Scan failed" in result.stdout or result.returncode != 0:
                    all_raw.append(f"--- Failed for {config} (package: {scan_target}) ---\n{result.stdout}\n{result.stderr}")
                    continue

                vulns = self._parse_fortress_output(result.stdout, os.path.basename(config))
                all_vulns.extend(vulns)
                all_raw.append(f"--- Result for {config} (package: {scan_target}) ---\n{result.stdout}")

            return ScannerOutput(
                scanner_name=self.name,
                vulnerabilities=all_vulns,
                raw_output="\n".join(all_raw)
            )

        except Exception as e:
            return ScannerOutput(scanner_name=self.name, vulnerabilities=[], error=str(e))

    def _parse_fortress_output(self, stdout: str, config_name: str) -> List[Vulnerability]:
        vulns = []
        # mcp-fortress output is text-heavy with emojis.
        # Example: 🛡️ Scanning... ⚠️ Risk Score: 45 ... 🚨 Critical: ...
        
        lines = stdout.splitlines()
        current_risk = None
        
        for line in lines:
            line = line.strip()
            if "Risk Score:" in line:
                current_risk = line.split("Risk Score:")[1].strip()
            
            if "🚨" in line or "⚠️" in line or "CRITICAL" in line.upper() or "WARNING" in line.upper():
                msg = line
                severity = "MEDIUM"
                if "🚨" in line or "CRITICAL" in line.upper():
                    severity = "HIGH"
                elif "⚠️" in line or "WARNING" in line.upper():
                    severity = "MEDIUM"
                
                # Try to map to rule_id
                rule_id = "mcp-fortress-violation"
                msg_lower = msg.lower()
                if "injection" in msg_lower:
                    rule_id = "mcp-prompt-injection"
                elif "permission" in msg_lower or "access" in msg_lower:
                    rule_id = "mcp-access-control-violation"
                elif "malicious" in msg_lower:
                    rule_id = "mcp-malicious-code"

                vulns.append(Vulnerability(
                    id=str(uuid.uuid4()),
                    rule_id=rule_id,
                    message=msg,
                    severity=severity,
                    file_path=config_name,
                    start_line=0,
                    end_line=0,
                    code_snippet="",
                    scanner=self.name,
                    metadata={"raw_line": line, "risk_score": current_risk}
                ))
        
        return vulns

    def scan_dynamic(self, target_url: str) -> ScannerOutput:
        return ScannerOutput(scanner_name=self.name, vulnerabilities=[], raw_output="mcp-fortress dynamic scanning not yet implemented in wrapper.")
