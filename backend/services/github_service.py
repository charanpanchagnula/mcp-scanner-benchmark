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

        # Construct zip url (e.g. https://github.com/user/repo/archive/refs/heads/main.zip)
        # Handle .git suffix if present
        if url.endswith(".git"):
            url = url[:-4]
        
        zip_url = f"{url}/archive/refs/heads/{branch}.zip"
        print(f"Downloading source code from {zip_url}...", flush=True)
        
        try:
            # Use a browser-like User-Agent to avoid 504/403 errors from GitHub
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            
            # Use streaming to handle large files (avoid OOM and show progress)
            # Increased timeout to 300s (5 min) because this repo is ~860MB
            with httpx.Client(follow_redirects=True, timeout=300.0, verify=False, headers=headers) as client:
                with client.stream("GET", zip_url) as response:
                    response.raise_for_status()
                    
                    zip_path = os.path.join(self.temp_dir, f"{scan_id}.zip")
                    with open(zip_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)
            
            print(f"Download complete. Extracting {zip_path}...", flush=True)
            try:
                with zipfile.ZipFile(zip_path, 'r') as z:
                    z.extractall(target_dir)
            finally:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
                    
            # Move contents one level up if nested (GitHub zips usually are repo-branch/content)
            extracted_folders = [f for f in os.listdir(target_dir) if os.path.isdir(os.path.join(target_dir, f))]
            if len(extracted_folders) == 1:
                inner_dir = os.path.join(target_dir, extracted_folders[0])
                for item in os.listdir(inner_dir):
                    shutil.move(os.path.join(inner_dir, item), target_dir)
                os.rmdir(inner_dir)
                
            return os.path.abspath(target_dir)
            
        except Exception as e:
            raise Exception(f"Failed to download repository source: {str(e)}")
