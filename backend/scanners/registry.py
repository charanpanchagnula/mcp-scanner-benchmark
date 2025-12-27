from typing import List, Type
from .base import BaseScanner
from .mcp_scan import MCPScanWrapper
from .semgrep_scan import SemgrepScanner
from .mcp_shield import MCPShieldWrapper
from .ramparts import RampartsWrapper
from .mcp_watch import MCPWatchWrapper
from .mcp_fortress import MCPFortressWrapper
from .active_fuzzer import ActiveFuzzer

class ScannerRegistry:
    @staticmethod
    def get_scanners():
        return [
            MCPScanWrapper(),
            SemgrepScanner(),
            MCPShieldWrapper(),
            MCPWatchWrapper(),
            MCPFortressWrapper(),
            # RampartsWrapper(), # Skipping ramparts for now or keep it
            ActiveFuzzer()
        ]
