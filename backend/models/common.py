from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

MCP_VULNERABILITY_TYPES = [
    "Prompt Injection",
    "Tool Execution Abuse",
    "Context Leakage",
    "Improper Access Control",
    "Insecure Configuration",
    "Tool Poisoning",
    "Denial of Service"
]

class Vulnerability(BaseModel):
    id: str
    rule_id: str
    message: str
    severity: str # HIGH, MEDIUM, LOW, INFO
    file_path: str
    start_line: int
    end_line: int
    code_snippet: str
    scanner: str
    metadata: Dict[str, Any] = {}

class ScannerOutput(BaseModel):
    scanner_name: str
    vulnerabilities: List[Vulnerability]
    raw_output: Optional[str] = None
    error: Optional[str] = None

class AgentRanking(BaseModel):
    scanner: str
    score: int = Field(..., description="Score from 0-100")
    reason: str

class CategoryEvaluation(BaseModel):
    winner: str
    runners_up: List[str]
    rankings: List[AgentRanking]
    scores: Dict[str, float] = Field(default_factory=dict, description="Scanner name -> percentage score (0-100)")
    summary: str
    best_features: List[str] = Field(default_factory=list, description="What made the winner the best?")
    missed_vulnerabilities: List[str] = Field(default_factory=list, description="Critical vulns missed by others")

class EvaluationResult(BaseModel):
    static: Optional[CategoryEvaluation] = None
    dynamic: Optional[CategoryEvaluation] = None

class Leaderboard(BaseModel):
    static: Dict[str, float] = Field(default_factory=dict, description="Scanner name -> holistic percentage score")
    dynamic: Dict[str, float] = Field(default_factory=dict, description="Scanner name -> holistic percentage score")
    total_scans: int = 0
