import json
import subprocess
import uuid
from typing import Dict, Any, List
from .base import BaseScanner
from models.common import ScannerOutput, Vulnerability

class RampartsWrapper(BaseScanner):
    @property
    def name(self) -> str:
        return "ramparts"

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
                    raw_output="No MCP configurations found. Skipping ramparts."
                )

            all_vulns = []
            all_raw = []
            
            for config in configs:
                cmd = ["ramparts", "scan", config]
                result = subprocess.run(cmd, capture_output=True, text=True, check=False)
                
                # ramparts output parsing (placeholder if needed, but currently returns raw)
                all_raw.append(f"--- Result for {config} ---\n{result.stdout}\n{result.stderr}")
                
            return ScannerOutput(
                scanner_name=self.name,
                vulnerabilities=all_vulns,
                raw_output="\n".join(all_raw)
            )

        except Exception as e:
            return ScannerOutput(scanner_name=self.name, vulnerabilities=[], error=str(e))

    def scan_dynamic(self, target_url: str) -> ScannerOutput:
        return self.scan_static(target_url)
