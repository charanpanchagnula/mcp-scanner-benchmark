import os
import json
import re
from typing import List, Dict, Any, Optional
from agno.agent import Agent
from agno.models.deepseek import DeepSeek
from models.common import EvaluationResult, ScannerOutput, CategoryEvaluation, Leaderboard

class ScannerEvaluator:
# ... (rest of class)
    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            print("Warning: DEEPSEEK_API_KEY not found.")
            
        self.agent = Agent(
            model=DeepSeek(id="deepseek-chat", api_key=api_key),
            instructions=[
                "You are an Elite AppSec Reviewer and Security Tool Evaluator.",
                "Review the provided scan results from different MCP scanners.",
                "For the given scan category (Static or Dynamic):",
                "1. Analyze each scanner's findings based on:",
                "   - Detection rate: How many valid vulnerabilities were found?",
                "   - False Positives: Did the scanner flag benign code? (Judgement based on code snippet and common MCP patterns)",
                "   - Confidence Score: How certain is the scanner? (If provided or inferred)",
                "   - Descriptiveness: How helpful are the messages for remediation?",
                "   - False Negatives: If other scanners found critical issues and this one didn't.",
                "2. Assign a Percentage Score (0-100) for each scanner representing its performance in this specific scan.",
                "3. Determine a winner and rank the others.",
                "4. Provide a summary and list of best features.",
                "Return the results in the structured format defined by CategoryEvaluation."
            ],
            output_schema=CategoryEvaluation
        )

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from text, handling markdown blocks if present."""
        if not text:
            return None
            
        # Try direct parsing first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
            
        # Try extracting from markdown code blocks
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
                
        # Try finding the first '{' and last '}'
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                pass
                
        return None

    def evaluate(self, scan_results: Dict[str, Any], scan_type: str = "static") -> Dict[str, Any]:
        """
        Evaluate the results from multiple scanners.
        Args:
             scan_results: Dict of scanner_name -> dict (serialized ScannerOutput)
             scan_type: "static" or "dynamic"
        """
        prompt_context = f"""
        You are evaluating {scan_type.upper()} security scan results.
        
        SCAN RESULTS:
        {json.dumps(scan_results, indent=2)}
        
        Please perform a deep analysis of these findings and produce a scoring report.
        """
        
        try:
            print(f"DEBUG: Running evaluation for {scan_type}...", flush=True)
            response = self.agent.run(prompt_context)
            content = response.content
            
            print(f"DEBUG: Agent response content: {content}", flush=True)
            
            result = None
            if hasattr(content, "model_dump"):
                result = content.model_dump()
            elif isinstance(content, dict):
                result = content
            else:
                result = self._extract_json(str(content))
            
            if not result:
                raise ValueError(f"Could not parse Agent response as JSON: {content}")

            return result
                
        except Exception as e:
            print(f"DEBUG: Evaluation error: {e}", flush=True)
            return {
                "error": str(e),
                "winner": "Error",
                "runners_up": [],
                "rankings": [],
                "scores": {},
                "summary": f"Evaluation failed: {e}",
                "best_features": [],
                "missed_vulnerabilities": []
            }

class LeaderboardAgent:
    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        self.agent = Agent(
            model=DeepSeek(id="deepseek-chat", api_key=api_key),
            instructions=[
                "You are an Analytics Engine responsible for maintaining a security scanner leaderboard.",
                "You will be given the CURRENT holistic leaderboard and NEW scan scores.",
                "Your task is to update the holistic percentages by calculating a moving average or weighted average.",
                "Ensure that the holistic score reflects the long-term performance across multiple targets.",
                "Increment the total_scans count by 1.",
                "Return the updated Leaderboard JSON object."
            ],
            output_schema=Leaderboard
        )

    def update_leaderboard(self, current_leaderboard: Dict[str, Any], new_scores: Dict[str, float], scan_type: str) -> Dict[str, Any]:
        prompt = f"""
        Current Leaderboard: {json.dumps(current_leaderboard, indent=2)}
        New Scan Scores ({scan_type}): {json.dumps(new_scores, indent=2)}
        
        Please provide the updated holistic leaderboard state.
        """
        
        try:
            # For simplicity, we can also do this with math if we want it predictable, 
            # but the user asked for a leaderboard agent.
            response = self.agent.run(prompt)
            content = response.content
            
            if hasattr(content, "model_dump"):
                return content.model_dump()
            elif isinstance(content, dict):
                return content
            else:
                # Basic fallback to manual math if agent fails or returns weirdness
                return self._manual_update(current_leaderboard, new_scores, scan_type)
        except Exception as e:
            print(f"Leaderboard update failed: {e}", flush=True)
            return self._manual_update(current_leaderboard, new_scores, scan_type)

    def _manual_update(self, current: Dict[str, Any], new_scores: Dict[str, float], scan_type: str) -> Dict[str, Any]:
        lb = current.copy()
        total = lb.get("total_scans", 0)
        new_total = total + 1
        lb["total_scans"] = new_total
        
        if scan_type not in lb:
            lb[scan_type] = {}
            
        for scanner, score in new_scores.items():
            old_avg = lb[scan_type].get(scanner, 0)
            # Moving average: ((old_avg * total) + new_score) / new_total
            new_avg = ((old_avg * total) + score) / new_total
            lb[scan_type][scanner] = round(new_avg, 2)
            
        return lb
