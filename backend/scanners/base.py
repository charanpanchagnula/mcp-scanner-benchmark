from abc import ABC, abstractmethod
from typing import Dict, Any, List
from models.common import ScannerOutput

class BaseScanner(ABC):
    """
    Abstract Base Class for MCP Scanners.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the scanner"""
        pass

    @property
    def supports_static(self) -> bool:
        """Whether the scanner supports static code analysis"""
        return True

    @property
    def supports_dynamic(self) -> bool:
        """Whether the scanner supports dynamic runtime analysis"""
        return True

    @abstractmethod
    def scan_static(self, target_path: str) -> ScannerOutput:
        pass

    @abstractmethod
    def scan_dynamic(self, target_url: str) -> ScannerOutput:
        pass

    def find_mcp_configs(self, target_path: str) -> List[str]:
        import json
        import os
        configs = []
        if not os.path.exists(target_path):
            return []
            
        if os.path.isfile(target_path):
            if target_path.endswith(".json"):
                try:
                    with open(target_path, 'r') as f:
                        data = json.load(f)
                        if "mcpServers" in data or ("command" in data and "args" in data):
                            return [os.path.abspath(target_path)]
                except:
                    pass
            return []

        for root, dirs, files in os.walk(target_path):
            for file in files:
                if file.endswith(".json"):
                    full_path = os.path.join(root, file)
                    try:
                        with open(full_path, 'r') as f:
                            data = json.load(f)
                            # Check if it looks like an MCP config
                            if "mcpServers" in data or ("command" in data and "args" in data):
                                configs.append(os.path.abspath(full_path))
                    except:
                        continue
        return configs
