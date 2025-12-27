import os
import json
import subprocess
import uuid
from typing import Dict, Any, List
from .base import BaseScanner
from models.common import ScannerOutput, Vulnerability

class MCPShieldWrapper(BaseScanner):
    @property
    def name(self) -> str:
        return "mcp-shield"

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
                    raw_output="No MCP configurations found. Skipping mcp-shield."
                )
            
            all_vulns = []
            all_raw = []
            
            for config in configs:
                try:
                    cmd = ["mcp-shield", "--path", config]
                    result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=os.path.dirname(config), timeout=60)
                    
                    # Parse text output (basic implementation)
                    vulns = self._parse_shield_output(result.stdout, config_name=os.path.basename(config))
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

    def _parse_shield_output(self, stdout: str, config_name: str = "mcp.json") -> List[Vulnerability]:
        vulns = []
        try:
            import re
            lines = stdout.splitlines()
            current_tool = None
            current_server = None
            current_risk = None
            
            for line in lines:
                line = line.strip()
                if not line: continue
                
                if line.startswith("1. Server:") or line.startswith("Server:") or "server:" in line.lower():
                    # Handle "Server: name" or "1. Server: name"
                    if ":" in line:
                        current_server = line.split(":", 1)[1].strip()
                elif line.startswith("Tool:") or "tool:" in line.lower():
                    if ":" in line:
                        current_tool = line.split(":", 1)[1].strip()
                elif "risk level:" in line.lower():
                    if ":" in line:
                        current_risk = line.split(":", 1)[1].strip()
                elif line.startswith("- ") or line.startswith("– ") or "Risk:" in line or "✖" in line or "Error" in line or "└──" in line:
                    # Extract server name from tree lines like "└── ✖ mcp-server-browserbase"
                    if "✖" in line and not current_server:
                        parts = line.split("✖", 1)
                        if len(parts) > 1:
                            potential_server = parts[1].split("—", 1)[0].strip()
                            current_server = potential_server

                    msg = line
                    if line.startswith("- ") or line.startswith("– "):
                        msg = line[2:].strip()
                    if "Issues:" in line: continue
                    
                    rule_id = "mcp-shield-violation"
                    msg_lower = msg.lower()
                    
                    if "hidden instructions" in msg_lower or "prompt injection" in msg_lower:
                        rule_id = "mcp-prompt-injection"
                    elif "sensitive file" in msg_lower or "access-control" in msg_lower:
                        rule_id = "mcp-access-control-violation"
                    elif "insecure transport" in msg_lower:
                        rule_id = "mcp-insecure-transport"
                    elif "execution" in msg_lower or "command" in msg_lower:
                        rule_id = "mcp-command-injection"
                    elif "connection closed" in msg_lower or "not found" in msg_lower:
                        rule_id = "mcp-server-startup-error"

                    if current_server or current_tool or "✖" in line or "Error" in line:
                        vulns.append(Vulnerability(
                           id=str(uuid.uuid4()),
                           rule_id=rule_id,
                           message=f"{msg} (Server: {current_server or 'Unknown'}, Tool: {current_tool or 'Generic'})",
                           severity="HIGH" if "Error" in line or "✖" in line else (current_risk.upper() if current_risk else "MEDIUM"),
                           file_path=config_name,
                           start_line=0,
                           end_line=0,
                           code_snippet="",
                           scanner=self.name,
                           metadata={"server": current_server, "tool": current_tool, "config": config_name}
                        ))
        except Exception:
            pass
        return vulns

    def scan_dynamic(self, target_url: str) -> ScannerOutput:
        return ScannerOutput(scanner_name=self.name, vulnerabilities=[], raw_output="mcp-shield is a static analysis tool.", error="Not Supported")
