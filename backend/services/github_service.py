import os
import shutil
import httpx
import zipfile
import io

class GitHubService:
    def __init__(self, temp_dir: str = "temp_scans"):
        self.temp_dir = temp_dir
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def clone_repo(self, url: str, branch: str, scan_id: str) -> str:
        """
        Downloads a GitHub repository as a ZIP archive and extracts it.
        Or handles local:// paths for direct directory access.
        Returns the absolute path to the directory.
        """
        if url.startswith("local://"):
            local_path = url.replace("local://", "")
            if not os.path.exists(local_path):
                raise Exception(f"Local path does not exist: {local_path}")
            return os.path.abspath(local_path)

        target_dir = os.path.join(self.temp_dir, scan_id)
        
        # Clean up if exists
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)

        print(f"Cloning {url} to {target_dir}...", flush=True)
        
        try:
            import subprocess
            # Ensure url ends with .git for consistency, though not strictly required
            if not url.endswith(".git"):
                clone_url = f"{url}.git"
            else:
                clone_url = url
            
            # Try specified branch first
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", "--branch", branch, clone_url, target_dir],
                    check=True, capture_output=True, text=True
                )
            except subprocess.CalledProcessError:
                # Fallback to default branch if 'main' was requested but failed
                if branch == "main":
                    print(f"Clone with branch 'main' failed. Retrying with default branch...", flush=True)
                    subprocess.run(
                        ["git", "clone", "--depth", "1", clone_url, target_dir],
                        check=True, capture_output=True, text=True
                    )
                else:
                    raise

            return os.path.abspath(target_dir)

        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to clone repository: {e.stderr}")
        except Exception as e:
            raise Exception(f"Failed to clone repository: {str(e)}")
