
import os
import asyncio
import json
import uuid
from typing import Dict, Any, List
from .base import BaseScanner
from models.common import ScannerOutput, Vulnerability
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import traceback

class ActiveFuzzer(BaseScanner):
    @property
    def name(self) -> str:
        return "ActiveFuzzer"

    @property
    def supports_static(self) -> bool:
        return False

    @property
    def supports_dynamic(self) -> bool:
        return True

    def scan_static(self, target_path: str) -> ScannerOutput:
        # Fuzzer doesn't do static analysis
        return ScannerOutput(
            scanner_name=self.name,
            vulnerabilities=[]
        )

    def scan_dynamic(self, target_path: str) -> ScannerOutput:
        # Fuzzer runs in a new thread with a new event loop
        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, self._fuzz_server(target_path))
                return future.result()
        except Exception as e:
            return ScannerOutput(
                scanner_name=self.name,
                vulnerabilities=[],
                raw_output=f"Error during dynamic scan dispatch: {str(e)}\n{traceback.format_exc()}",
                error=str(e)
            )

    async def _fuzz_server(self, config_path: str) -> ScannerOutput:
        vulns = []
        logs = []
        logs.append(f"Starting fuzzing for target: {config_path}")

        # 1. Resolve mcp.json
        # 1. Resolve mcp.json (Recursive search)
        mcp_config_path = None
        if os.path.isdir(config_path):
            # Check root first
            root_check = os.path.join(config_path, "mcp.json")
            if os.path.exists(root_check):
                mcp_config_path = root_check
            else:
                # Walk to find first mcp.json
                for root, dirs, files in os.walk(config_path):
                    if "mcp.json" in files:
                        mcp_config_path = os.path.join(root, "mcp.json")
                        break
            
        if not mcp_config_path:
             logs.append("No mcp.json found. Attempting heuristic detection...")
             
             # Heuristic 1: Node.js (package.json)
             # Walk to find package.json with "start" script or "main"
             detected_config = None
             for root, dirs, files in os.walk(config_path):
                 if "package.json" in files:
                     try:
                         with open(os.path.join(root, "package.json")) as f:
                             pkg = json.load(f)
                             
                         cmd = None
                         args = []
                         
                         if "scripts" in pkg and "start" in pkg["scripts"]:
                             # Use npm start
                             cmd = "npm"
                             args = ["start"]
                         elif "main" in pkg:
                             # Use node <main>
                             cmd = "node"
                             args = [pkg["main"]]
                         elif os.path.exists(os.path.join(root, "build", "index.js")):
                             cmd = "node"
                             args = ["build/index.js"]
                             
                         if cmd:
                             logs.append(f"Heuristic: Detected Node.js server at {root}")
                             detected_config = {
                                 "mcpServers": {
                                     f"auto-node-{os.path.basename(root)}": {
                                         "command": cmd,
                                         "args": args,
                                         "env": {}
                                     }
                                 }
                             }
                             # Write temp mcp.json to run context calculation correctly
                             mcp_config_path = os.path.join(root, "mcp.json")
                             with open(mcp_config_path, 'w') as f:
                                 json.dump(detected_config, f)
                             break
                     except:
                         pass
                 
                 # Heuristic 2: Python (server.py/main.py)
                 if not detected_config and ("requirements.txt" in files or "pyproject.toml" in files):
                     target_script = "server.py" if "server.py" in files else "main.py" if "main.py" in files else None
                     if target_script:
                         logs.append(f"Heuristic: Detected Python server at {root} ({target_script})")
                         detected_config = {
                                 "mcpServers": {
                                     f"auto-python-{os.path.basename(root)}": {
                                         "command": "python",
                                         "args": [target_script],
                                         "env": {}
                                     }
                                 }
                             }
                         mcp_config_path = os.path.join(root, "mcp.json")
                         with open(mcp_config_path, 'w') as f:
                                 json.dump(detected_config, f)
                         break
            
             if not mcp_config_path:
                 return ScannerOutput(scanner_name=self.name, vulnerabilities=[], raw_output="No mcp.json found and heuristics failed.", error="Config not found")
        
        logs.append(f"Using config file: {mcp_config_path}")

        if not os.path.exists(mcp_config_path):
             return ScannerOutput(scanner_name=self.name, vulnerabilities=[], raw_output=f"Config file not found: {mcp_config_path}", error="Config not found")

        try:
            with open(mcp_config_path) as f:
                config = json.load(f)
            
            logs.append("Config loaded successfully.")
            
            servers = config.get("mcpServers", {})
            if not servers:
                logs.append("No mcpServers defined in config.")

            for server_name, server_conf in servers.items():
                logs.append(f"--- Fuzzing Server: {server_name} ---")
                cmd = server_conf.get("command")
                args = server_conf.get("args", [])
                env = server_conf.get("env", {})
                
                cwd = os.path.dirname(mcp_config_path)
                logs.append(f"CWD: {cwd}")
                logs.append(f"Command: {cmd}, Args: {args}")

                # Environment setup
                full_env = os.environ.copy()
                full_env.update(env)
                
                # Resolve args absolute paths if they exist in CWD
                # This is a heuristic to help StdioClient find files
                resolved_args = []
                for arg in args:
                    potential_path = os.path.join(cwd, arg)
                    if os.path.exists(potential_path):
                        resolved_args.append(potential_path)
                    else:
                        resolved_args.append(arg)
                
                logs.append(f"Resolved Args: {resolved_args}")

                server_params = StdioServerParameters(
                    command=cmd,
                    args=resolved_args,
                    env=full_env
                )
                
                try:
                    await asyncio.wait_for(self._run_session(server_params, mcp_config_path, logs, vulns), timeout=30.0)
                except asyncio.TimeoutError:
                    logs.append("!!! SERVER SESSION TIMED OUT (30s) !!!")
                    logs.append("The server process hung or took too long to respond.")
                    # We continue to next server or finish
                except Exception as e:
                     logs.append(f"Server execution/connection failed: {str(e)}\n{traceback.format_exc()}")
                     
        except Exception as e:
            logs.append(f"Major fuzzer error: {str(e)}\n{traceback.format_exc()}")
            return ScannerOutput(scanner_name=self.name, vulnerabilities=[], raw_output="\n".join(logs), error=f"Fuzzing failed: {str(e)}")

        return ScannerOutput(
            scanner_name=self.name,
            vulnerabilities=vulns,
            raw_output="\n".join(logs)
        )

    async def _run_session(self, server_params, mcp_config_path, logs, vulns):
        logs.append("Initializing stdio client...")
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                try:
                    await asyncio.wait_for(session.initialize(), timeout=5.0)
                    logs.append("Session initialized.")
                    
                    tools_result = await asyncio.wait_for(session.list_tools(), timeout=5.0)
                    logs.append(f"Tools found: {len(tools_result.tools)}")
                    
                    for tool in tools_result.tools:
                        logs.append(f"Analyzing tool: {tool.name}")
                        props = tool.inputSchema.get("properties", {})
                        logs.append(f"  Input params: {list(props.keys())}")
                        
                        # FUZZING LOGIC
                        
                        # 1. Test Unsafe Eval / Command Injection (parameter named 'code' or 'command')
                        if "code" in props or "command" in props:
                            logs.append(f"  > Probing '{tool.name}' for Command Injection (param: code/command)")
                            
                            payload = {}
                            # Satisfy required params with dummy
                            for req in tool.inputSchema.get("required", []):
                                payload[req] = "test"
                            
                            # Overwrite target param
                            target_param = "code" if "code" in props else "command"
                            payload[target_param] = "print('VULN_DETECTED')"
                            
                            logs.append(f"    Payload: {payload}")

                            try:
                                res = await asyncio.wait_for(session.call_tool(tool.name, arguments=payload), timeout=10.0)
                                content = res.content[0].text if res.content else ""
                                logs.append(f"    Result: {content[:100]}...") # truncate
                                
                                if "VULN_DETECTED" in content:
                                    logs.append("    !!! VULNERABILITY DETECTED !!!")
                                    vulns.append(Vulnerability(
                                        id=str(uuid.uuid4()),
                                        rule_id="Tool Execution Abuse",
                                        message=f"Code Injection detected in tool '{tool.name}'. Payload executed.",
                                        severity="CRITICAL",
                                        file_path=mcp_config_path,
                                        scanner=self.name,
                                        start_line=0,
                                        end_line=0,
                                        code_snippet="Dynamic Analysis detection",
                                        metadata={"tool": tool.name, "output": content}
                                    ))
                                else:
                                    logs.append("    No vulnerability marker found.")
                            except asyncio.TimeoutError:
                                logs.append(f"    Tool execution timed out.")
                            except Exception as ex:
                                logs.append(f"    Tool execution error: {ex}")

                        # 2. Test LFI (parameter named 'path' or 'file')
                        if "path" in props or "file" in props:
                            logs.append(f"  > Probing '{tool.name}' for LFI (param: path/file)")
                            
                            payload = {}
                            for req in tool.inputSchema.get("required", []):
                                payload[req] = "test"
                                
                            target_param = "path" if "path" in props else "file"
                            # Try to read the server file itself or /etc/passwd
                            # server.py is likely in the CWD.
                            payload[target_param] = "server.py"
                            
                            logs.append(f"    Payload: {payload}")

                            try:
                                res = await asyncio.wait_for(session.call_tool(tool.name, arguments=payload), timeout=10.0)
                                content = res.content[0].text if res.content else ""
                                logs.append(f"    Result len: {len(content)}")
                                logs.append(f"    Result content: {content[:100]}")
                                
                                # logic: check if content looks like python code or contains known string
                                if "import" in content or "def " in content:
                                        logs.append("    !!! VULNERABILITY DETECTED !!!")
                                        vulns.append(Vulnerability(
                                        id=str(uuid.uuid4()),
                                        rule_id="Tool Execution Abuse",
                                        message=f"Local File Inclusion (LFI) detected in tool '{tool.name}'. File content returned.",
                                        severity="HIGH",
                                        file_path=mcp_config_path,
                                        scanner=self.name,
                                        start_line=0,
                                        end_line=0,
                                        code_snippet="Dynamic Analysis detection",
                                        metadata={"tool": tool.name, "output": content[:50]}
                                    ))
                                else:
                                    logs.append("    Content does not look like source code.")
                            except asyncio.TimeoutError:
                                logs.append(f"    Tool execution timed out.")
                            except Exception as ex:
                                logs.append(f"    Tool execution error: {ex}")
                except asyncio.TimeoutError:
                    logs.append("Session initialization or tool listing timed out.")
                except Exception as e:
                    logs.append(f"Session error: {e}")
                     
