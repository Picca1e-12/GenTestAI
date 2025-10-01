import os
import time
import difflib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
import git
from git import Repo, InvalidGitRepositoryError
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChangeEventHandler(FileSystemEventHandler):
    """
    Handles file system events and filters relevant changes
    """
    
    def __init__(self, repo_path: str, on_change_callback: Callable):
        self.repo_path = repo_path
        self.on_change_callback = on_change_callback
        self.ignored_patterns = [
            '.git', '__pycache__', 'node_modules', '.vscode', 
            '.idea', 'venv', 'env', '.pytest_cache', 'dist', 
            'build', '.DS_Store', 'Thumbs.db'
        ]
        self.ignored_extensions = [
            '.pyc', '.pyo', '.log', '.tmp', '.temp', '.cache',
            '.swp', '.swo', '.bak', '.orig'
        ]
        
    def should_ignore_file(self, file_path: str) -> bool:
        """
        Check if file should be ignored based on patterns and extensions
        """
        path = Path(file_path)
        
        # Check if any part of the path contains ignored patterns
        for part in path.parts:
            if any(pattern in part for pattern in self.ignored_patterns):
                return True
        
        # Check file extension
        if path.suffix in self.ignored_extensions:
            return True
            
        # Check if it's a hidden file (starts with .)
        if path.name.startswith('.') and path.suffix not in ['.py', '.js', '.ts', '.jsx', '.tsx']:
            return True
            
        return False
    
    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events"""
        if not event.is_directory and not self.should_ignore_file(event.src_path):
            logger.info(f"File modified: {event.src_path}")
            self.on_change_callback(event.src_path, "modified")
    
    def on_created(self, event: FileSystemEvent):
        """Handle file creation events"""
        if not event.is_directory and not self.should_ignore_file(event.src_path):
            logger.info(f"File created: {event.src_path}")
            self.on_change_callback(event.src_path, "created")
    
    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion events"""
        if not event.is_directory and not self.should_ignore_file(event.src_path):
            logger.info(f"File deleted: {event.src_path}")
            self.on_change_callback(event.src_path, "deleted")


class RepoWatcher:
    """
    Monitors file system changes in git repositories with proper diff tracking
    """
    
    def __init__(self, repo_path: str, repo_id: str):
        self.repo_path = os.path.abspath(repo_path)
        self.repo_id = repo_id
        self.observer = None
        self.event_handler = None
        self.is_running = False
        self.repo = None
        self.change_callbacks: List[Callable] = []
        
        # Store file snapshots for proper diff comparison
        self.file_snapshots: Dict[str, str] = {}
        
        # Validate repository
        if not self._validate_repository():
            raise ValueError(f"Invalid git repository: {repo_path}")
    
    def _validate_repository(self) -> bool:
        """
        Validate that the path is a valid git repository
        """
        try:
            if not os.path.exists(self.repo_path):
                logger.error(f"Repository path does not exist: {self.repo_path}")
                return False
            
            self.repo = Repo(self.repo_path)
            logger.info(f"Valid git repository found: {self.repo_path}")
            return True
            
        except InvalidGitRepositoryError:
            logger.error(f"Not a valid git repository: {self.repo_path}")
            return False
        except Exception as e:
            logger.error(f"Error validating repository {self.repo_path}: {e}")
            return False
    
    def add_change_callback(self, callback: Callable):
        """
        Add callback function to be called when changes are detected
        Callback should accept (file_path, change_type, change_data)
        """
        self.change_callbacks.append(callback)
    
    def initialize_snapshots(self) -> None:
        """
        Initialize snapshots for all files in the repository
        This creates a baseline for comparison
        """
        try:
            # Walk through all files in the repository
            for root, dirs, files in os.walk(self.repo_path):
                # Skip .git directory
                if '.git' in dirs:
                    dirs.remove('.git')
                
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, self.repo_path)
                    
                    # Skip ignored files
                    if not self.event_handler or not self.event_handler.should_ignore_file(file_path):
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                self.file_snapshots[relative_path] = f.read()
                        except Exception as e:
                            logger.warning(f"Could not read {relative_path}: {e}")
            
            logger.info(f"Initialized {len(self.file_snapshots)} file snapshots")
            
        except Exception as e:
            logger.error(f"Error initializing snapshots: {e}")
    
    def _on_file_change(self, file_path: str, change_type: str):
        """
        Internal method called when file changes are detected
        """
        try:
            # Get relative path from repository root
            relative_path = os.path.relpath(file_path, self.repo_path)
            
            # Extract git information with proper diff
            change_data = self._extract_git_info(file_path, change_type, relative_path)
            
            # Call all registered callbacks
            for callback in self.change_callbacks:
                try:
                    callback(file_path, change_type, change_data)
                except Exception as e:
                    logger.error(f"Error in change callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error processing file change {file_path}: {e}")
    
    def _extract_git_info(self, file_path: str, change_type: str, relative_path: str) -> Dict:
        """
        Extract git information for the changed file with proper diff tracking
        """
        change_data = {
            "repository_id": self.repo_id,
            "file_path": file_path,
            "relative_path": relative_path,
            "change_type": change_type,
            "timestamp": datetime.now().isoformat(),
            "file_extension": Path(file_path).suffix,
            "git_diff": "",
            "formatted_changes": "",
            "author": "unknown",
            "author_email": "unknown",
            "commit_hash": None,
            "lines_added": 0,
            "lines_removed": 0
        }
        
        try:
            # Get proper diff
            raw_diff = self._get_proper_diff(relative_path, change_type)
            change_data["git_diff"] = raw_diff
            
            # Format diff for better display
            change_data["formatted_changes"] = self._format_diff_simple(raw_diff)
            
            # Count lines added/removed from diff
            diff_stats = self._parse_diff_stats(raw_diff)
            change_data["lines_added"] = diff_stats["added"]
            change_data["lines_removed"] = diff_stats["removed"]
            
            # Get author information from recent commits
            author_info = self._get_author_info(relative_path)
            change_data["author"] = author_info["name"]
            change_data["author_email"] = author_info["email"]
            change_data["commit_hash"] = author_info["commit_hash"]
            
        except Exception as e:
            logger.error(f"Error extracting git info for {file_path}: {e}")
        
        return change_data
    
    def _get_proper_diff(self, relative_path: str, change_type: str) -> str:
        """
        Get proper diff that shows actual changes between file states
        """
        file_path = os.path.join(self.repo_path, relative_path)
        
        # Handle file deletion
        if change_type == "deleted" or not os.path.exists(file_path):
            if relative_path in self.file_snapshots:
                previous_content = self.file_snapshots[relative_path]
                del self.file_snapshots[relative_path]  # Clean up
                return self._create_diff(relative_path, previous_content, "")
            else:
                return "File deleted (no previous snapshot available)"
        
        # Read current file content
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                current_content = f.read()
        except Exception as e:
            return f"Error reading current file: {e}"
        
        # Get previous content for comparison
        previous_content = self.file_snapshots.get(relative_path, "")
        
        # If this is the first time we see this file, try to get it from git
        if not previous_content and change_type != "created":
            try:
                previous_content = self.repo.git.show(f"HEAD:{relative_path}")
            except:
                # File doesn't exist in HEAD, treat as new
                previous_content = ""
        
        # Update snapshot for next comparison
        self.file_snapshots[relative_path] = current_content
        
        # Create diff
        if previous_content == current_content:
            return "No actual changes detected"
        
        return self._create_diff(relative_path, previous_content, current_content)
    
    def _create_diff(self, relative_path: str, old_content: str, new_content: str) -> str:
        """
        Create a proper unified diff between two versions of content
        """
        old_lines = old_content.split('\n') if old_content else []
        new_lines = new_content.split('\n') if new_content else []
        
        # Use difflib to generate unified diff
        diff_lines = list(difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
            lineterm=''
        ))
        
        if not diff_lines:
            return "No changes detected"
        
        # Add git-style diff header
        header_lines = [f"diff --git a/{relative_path} b/{relative_path}"]
        
        if not old_content:
            header_lines.append("new file mode 100644")
        elif not new_content:
            header_lines.append("deleted file mode 100644")
        else:
            header_lines.append("index 0000000..1111111 100644")
        
        return '\n'.join(header_lines + diff_lines)
    
    def _format_diff_simple(self, diff: str) -> str:
        """
        Format diff to show changes in a clean, readable way
        """
        if not diff or diff in ["No changes detected", "No actual changes detected", "Error reading current file"]:
            return diff
        
        if diff.startswith("File deleted"):
            return diff
        
        lines = diff.split('\n')
        formatted_lines = []
        
        # Track if we're in a hunk
        in_hunk = False
        current_chunk = []  # Store lines until we hit context or end
        
        for line in lines:
            # Skip diff headers
            if (line.startswith('diff --git') or line.startswith('index') or 
                line.startswith('---') or line.startswith('+++') or 
                line.startswith('new file') or line.startswith('deleted file')):
                continue
                
            # Check for hunk header
            if line.startswith('@@'):
                in_hunk = True
                # Process any pending chunk before new hunk
                if current_chunk:
                    formatted_lines.extend(self._process_chunk(current_chunk))
                    current_chunk = []
                
                formatted_lines.append(f"\n📍 {line}")
                continue
            
            if in_hunk:
                if line.startswith('-') or line.startswith('+'):
                    # Add to current chunk (removal or addition)
                    current_chunk.append(line)
                else:
                    # Context line - process current chunk first
                    if current_chunk:
                        formatted_lines.extend(self._process_chunk(current_chunk))
                        current_chunk = []
                    
                    # Add context line (limit context display)
                    context_line = line[1:] if line.startswith(' ') else line
                    formatted_lines.append(f"   {context_line}")
        
        # Process any remaining chunk
        if current_chunk:
            formatted_lines.extend(self._process_chunk(current_chunk))
        
        return '\n'.join(formatted_lines) if formatted_lines else "No changes to display"
    
    def _process_chunk(self, chunk_lines: List[str]) -> List[str]:
        """
        Process a chunk of consecutive +/- lines and format them properly
        """
        if not chunk_lines:
            return []
        
        # Separate removals and additions while preserving order
        removals = []
        additions = []
        
        for line in chunk_lines:
            if line.startswith('-'):
                removals.append(line[1:])  # Remove the '-' prefix
            elif line.startswith('+'):
                additions.append(line[1:])  # Remove the '+' prefix
        
        result = []
        
        # If we have both removals and additions, it's a replacement/modification
        if removals and additions:
            result.append("   MODIFIED:")
            result.append("")
            
            # Show removals first
            result.append("   REMOVED:")
            for line in removals:
                result.append(f"   - {line}")
            
            result.append("")
            
            # Then additions
            result.append("   ADDED:")
            for line in additions:
                result.append(f"   + {line}")
        
        # Only removals (pure deletion)
        elif removals:
            result.append("   DELETED:")
            for line in removals:
                result.append(f"   - {line}")
        
        # Only additions (pure addition)  
        elif additions:
            result.append("   ADDED:")
            for line in additions:
                result.append(f"   + {line}")
        
        result.append("")  # Empty line for separation
        return result
    
    def _parse_diff_stats(self, diff: str) -> Dict[str, int]:
        """
        Parse diff to count added and removed lines
        """
        added = 0
        removed = 0
        
        for line in diff.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                added += 1
            elif line.startswith('-') and not line.startswith('---'):
                removed += 1
        
        return {"added": added, "removed": removed}
    
    def _get_author_info(self, relative_path: str) -> Dict[str, str]:
        """
        Get author information from the most recent commit affecting this file
        """
        try:
            # Get the most recent commit that affected this file
            commits = list(self.repo.iter_commits(paths=relative_path, max_count=1))
            
            if commits:
                commit = commits[0]
                return {
                    "name": commit.author.name,
                    "email": commit.author.email,
                    "commit_hash": commit.hexsha[:8]  # Short hash
                }
            else:
                # If no commits found, get current git user config
                try:
                    config_reader = self.repo.config_reader()
                    name = config_reader.get_value("user", "name", fallback="unknown")
                    email = config_reader.get_value("user", "email", fallback="unknown")
                    return {
                        "name": name,
                        "email": email,
                        "commit_hash": None
                    }
                except:
                    pass
        
        except Exception as e:
            logger.error(f"Error getting author info for {relative_path}: {e}")
        
        return {
            "name": "unknown",
            "email": "unknown", 
            "commit_hash": None
        }
    
    def start_watching(self) -> bool:
        """
        Start monitoring the repository for changes
        """
        if self.is_running:
            logger.warning(f"Already watching repository: {self.repo_path}")
            return True
        
        try:
            # Create event handler first (needed for initialize_snapshots)
            self.event_handler = ChangeEventHandler(
                repo_path=self.repo_path,
                on_change_callback=self._on_file_change
            )
            
            # Initialize file snapshots for proper diff comparison
            self.initialize_snapshots()
            
            # Create and configure observer
            self.observer = Observer()
            self.observer.schedule(
                event_handler=self.event_handler,
                path=self.repo_path,
                recursive=True
            )
            
            # Start observer
            self.observer.start()
            self.is_running = True
            
            logger.info(f"Started watching repository: {self.repo_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting watcher for {self.repo_path}: {e}")
            self.is_running = False
            return False
    
    def stop_watching(self) -> bool:
        """
        Stop monitoring the repository
        """
        if not self.is_running:
            logger.warning(f"Not currently watching repository: {self.repo_path}")
            return True
        
        try:
            if self.observer:
                self.observer.stop()
                self.observer.join(timeout=5)  # Wait up to 5 seconds
                
            self.observer = None
            self.event_handler = None
            self.is_running = False
            
            logger.info(f"Stopped watching repository: {self.repo_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping watcher for {self.repo_path}: {e}")
            return False
    
    def get_repo_status(self) -> Dict:
        """
        Get current repository monitoring status and information
        """
        try:
            # Get repository statistics
            total_commits = len(list(self.repo.iter_commits()))
            
            # Get current branch
            try:
                current_branch = self.repo.active_branch.name
            except:
                current_branch = "detached HEAD"
            
            # Get latest commit info
            latest_commit = self.repo.head.commit
            
            # Check if repository has uncommitted changes
            is_dirty = self.repo.is_dirty()
            untracked_files = len(self.repo.untracked_files)
            
            return {
                "repository_id": self.repo_id,
                "path": self.repo_path,
                "is_watching": self.is_running,
                "is_valid_repo": True,
                "current_branch": current_branch,
                "total_commits": total_commits,
                "latest_commit": {
                    "hash": latest_commit.hexsha[:8],
                    "author": latest_commit.author.name,
                    "message": latest_commit.message.strip(),
                    "date": latest_commit.committed_datetime.isoformat()
                },
                "has_uncommitted_changes": is_dirty,
                "untracked_files_count": untracked_files,
                "snapshots_count": len(self.file_snapshots),
                "last_check": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting repo status for {self.repo_path}: {e}")
            return {
                "repository_id": self.repo_id,
                "path": self.repo_path,
                "is_watching": self.is_running,
                "is_valid_repo": False,
                "error": str(e),
                "last_check": datetime.utcnow().isoformat()
            }
    
    def __del__(self):
        """
        Cleanup when object is destroyed
        """
        if self.is_running:
            self.stop_watching()


class WatcherManager:
    """
    Manages multiple repository watchers
    """
    
    def __init__(self):
        self.watchers: Dict[str, RepoWatcher] = {}
        self.change_callbacks: List[Callable] = []
    
    def add_change_callback(self, callback: Callable):
        """
        Add global change callback for all watchers
        """
        self.change_callbacks.append(callback)
        
        # Add to existing watchers
        for watcher in self.watchers.values():
            watcher.add_change_callback(callback)
    
    def add_repository(self, repo_id: str, repo_path: str) -> bool:
        """
        Add a repository to watch
        """
        if repo_id in self.watchers:
            logger.warning(f"Repository {repo_id} already being watched")
            return True
        
        try:
            watcher = RepoWatcher(repo_path, repo_id)
            
            # Add all global callbacks
            for callback in self.change_callbacks:
                watcher.add_change_callback(callback)
            
            self.watchers[repo_id] = watcher
            logger.info(f"Added repository {repo_id}: {repo_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding repository {repo_id}: {e}")
            return False
    
    def remove_repository(self, repo_id: str) -> bool:
        """
        Remove a repository from watching
        """
        if repo_id not in self.watchers:
            logger.warning(f"Repository {repo_id} not found")
            return True
        
        try:
            # Stop watching if currently active
            self.watchers[repo_id].stop_watching()
            
            # Remove from watchers
            del self.watchers[repo_id]
            
            logger.info(f"Removed repository {repo_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing repository {repo_id}: {e}")
            return False
    
    def start_watching(self, repo_id: str) -> bool:
        """
        Start watching a specific repository
        """
        if repo_id not in self.watchers:
            logger.error(f"Repository {repo_id} not found")
            return False
        
        return self.watchers[repo_id].start_watching()
    
    def stop_watching(self, repo_id: str) -> bool:
        """
        Stop watching a specific repository
        """
        if repo_id not in self.watchers:
            logger.error(f"Repository {repo_id} not found")
            return False
        
        return self.watchers[repo_id].stop_watching()
    
    def start_all(self) -> Dict[str, bool]:
        """
        Start watching all repositories
        """
        results = {}
        for repo_id in self.watchers:
            results[repo_id] = self.start_watching(repo_id)
        return results
    
    def stop_all(self) -> Dict[str, bool]:
        """
        Stop watching all repositories
        """
        results = {}
        for repo_id in self.watchers:
            results[repo_id] = self.stop_watching(repo_id)
        return results
    
    def get_all_status(self) -> Dict[str, Dict]:
        """
        Get status of all repositories
        """
        status = {}
        for repo_id, watcher in self.watchers.items():
            status[repo_id] = watcher.get_repo_status()
        return status
    
    def get_watching_count(self) -> Dict[str, int]:
        """
        Get count of watching vs not watching repositories
        """
        watching = sum(1 for w in self.watchers.values() if w.is_running)
        total = len(self.watchers)
        
        return {
            "total_repositories": total,
            "currently_watching": watching,
            "not_watching": total - watching
        }